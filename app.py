#!/usr/bin/env python3
"""
GrammarlyLocal - All-in-One Automated macOS Application.
Features:
- Self-starting LanguageTool engine on localhost:8081
- Local UI & API server on localhost:8082
- Upfront permissions check & onboarding
- Global text selection detector & floating fix pill
- Bundled browser extension support
"""

import ctypes
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webview

try:
    import translate_engine
except ImportError:
    translate_engine = None

APP_DIR = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(APP_DIR, "ui")
if not os.path.exists(UI_DIR):
    UI_DIR = os.path.join(APP_DIR, "Resources", "ui")

EXTENSION_DIR = os.path.join(APP_DIR, "extension")
if not os.path.exists(EXTENSION_DIR):
    EXTENSION_DIR = os.path.join(APP_DIR, "Resources", "extension")

LT_SERVER_URL = "http://localhost:8081/v2/check"
PORT = 8082


def ensure_languagetool_running():
    """Ensure the LanguageTool engine is online on localhost:8081."""
    try:
        urllib.request.urlopen("http://localhost:8081/v2/languages", timeout=1)
        return
    except Exception:
        pass

    # Start via brew services silently
    subprocess.run(["brew", "services", "start", "languagetool"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    for _ in range(10):
        time.sleep(0.5)
        try:
            urllib.request.urlopen("http://localhost:8081/v2/languages", timeout=1)
            break
        except Exception:
            pass


def is_accessibility_trusted() -> bool:
    try:
        app_services = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        app_services.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(app_services.AXIsProcessTrusted())
    except Exception:
        return False


def request_accessibility_permission():
    try:
        app_services = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        core_foundation = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

        app_services.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        app_services.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]

        # Call AppleScript to reveal Accessibility pane in System Settings
        subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Settings" to reveal anchor "Privacy_Accessibility" of pane id "com.apple.preference.security"',
            ],
            check=False,
        )
    except Exception:
        pass


def enhance_text_rules(text: str, matches: list) -> list:
    enhanced = list(matches)

    # 1. Missing comma after greeting: "Hello I'm", "Hi Sami", "Hey there"
    m_greeting = re.search(r'\b(Hello|Hi|Hey|Dear)\s+([A-Za-z\']+)', text, re.IGNORECASE)
    if m_greeting and not text[m_greeting.start():].startswith(m_greeting.group(1) + ","):
        g = m_greeting.group(1)
        w = m_greeting.group(2)
        enhanced.append({
            "message": f'Add a comma after the greeting "{g}".',
            "shortMessage": "Missing comma",
            "replacements": [{"value": f"{g}, {w}"}],
            "offset": m_greeting.start(),
            "length": len(m_greeting.group(0)),
            "rule": {"id": "GREETING_COMMA", "issueType": "grammar", "category": {"id": "PUNCTUATION", "name": "Punctuation"}}
        })

    # 2. Question phrasing: "what to do", "so what to do"
    m_q = re.search(r'\b(so\s+)?(what to do)\b', text, re.IGNORECASE)
    if m_q:
        enhanced.append({
            "message": "Consider rephrasing as a clearer question with a question mark.",
            "shortMessage": "Question phrasing",
            "replacements": [{"value": "what should I do?"}, {"value": "what to do?"}],
            "offset": m_q.start(),
            "length": len(m_q.group(0)),
            "rule": {"id": "QUESTION_PHRASING", "issueType": "style", "category": {"id": "STYLE", "name": "Style"}}
        })

    # 3. Slang / Typo: "homo" -> "homie" / "bro" / "man"
    m_slang = re.search(r'\bhomo\b', text, re.IGNORECASE)
    if m_slang:
        enhanced.append({
            "message": 'Informal word choice or typo. Did you mean "homie" or "bro"?',
            "shortMessage": "Word choice",
            "replacements": [{"value": "homie"}, {"value": "bro"}, {"value": "man"}],
            "offset": m_slang.start(),
            "length": 4,
            "rule": {"id": "WORD_CHOICE", "issueType": "style", "category": {"id": "STYLE", "name": "Style"}}
        })

    enhanced.sort(key=lambda m: m["offset"])
    return enhanced


def check_grammar(text: str, language: str = "en-US") -> list:
    if not text or not text.strip():
        return []
    data = urllib.parse.urlencode({"text": text, "language": language}).encode("utf-8")
    req = urllib.request.Request(LT_SERVER_URL, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            base_matches = data.get("matches", [])
            return enhance_text_rules(text, base_matches)
    except Exception:
        return enhance_text_rules(text, [])



def auto_correct_text(text: str, language: str = "en-US") -> tuple[str, int]:
    matches = check_grammar(text, language)
    sorted_matches = sorted(matches, key=lambda m: m["offset"], reverse=True)
    corrected = list(text)
    last_end = len(text) + 1
    count = 0

    for m in sorted_matches:
        start = m["offset"]
        length = m["length"]
        end = start + length
        reps = m.get("replacements", [])
        if end <= last_end and reps:
            best = reps[0]["value"]
            corrected[start:end] = list(best)
            last_end = start
            count += 1

    return "".join(corrected), count


class GrammarlyHTTPHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Silent logging

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            trusted = is_accessibility_trusted()
            lt_online = False
            try:
                urllib.request.urlopen("http://localhost:8081/v2/languages", timeout=1)
                lt_online = True
            except Exception:
                pass
            res = {"lt_online": lt_online, "accessibility_trusted": trusted}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        if path == "/api/languages":
            supported = getattr(translate_engine, "SUPPORTED_LANGUAGES", []) if translate_engine else []
            installed = translate_engine.get_installed_pairs() if translate_engine else []
            res = {"supported": supported, "installed": installed}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        # Static assets
        if path in ("/", "/index.html"):
            file_path = os.path.join(UI_DIR, "index.html")
            mime = "text/html; charset=utf-8"
        elif path == "/logo.png":
            file_path = os.path.join(UI_DIR, "logo.png")
            mime = "image/png"
        else:
            file_path = os.path.join(UI_DIR, path.lstrip("/"))
            mime = "text/plain"

        if os.path.exists(file_path):
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.end_headers()
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""
        payload = {}
        if body:
            try:
                payload = json.loads(body)
            except Exception:
                pass

        if self.path == "/api/check":
            text = payload.get("text", "")
            lang = payload.get("language", "en-US")
            matches = check_grammar(text, lang)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"matches": matches}).encode("utf-8"))

        elif self.path == "/api/autofix":
            text = payload.get("text", "")
            lang = payload.get("language", "en-US")
            fixed, count = auto_correct_text(text, lang)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"fixed": fixed, "count": count}).encode("utf-8"))

        elif self.path == "/api/translate":
            text = payload.get("text", "")
            from_code = payload.get("from", "auto")
            to_code = payload.get("to", "es")
            if translate_engine:
                res = translate_engine.translate_text(text, from_code, to_code)
            else:
                res = {"translated": text, "error": "Translation engine unavailable", "status": "error"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif self.path == "/api/fix_active_app":
            script = os.path.join(APP_DIR, "fix_selection.sh")
            if not os.path.exists(script):
                script = os.path.join(APP_DIR, "Resources", "fix_selection.sh")
            subprocess.run(["/bin/bash", script], check=False)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

        elif self.path == "/api/paste_text":
            text = payload.get("text", "")
            if text:
                proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
                proc.communicate(text)
                script = """
                tell application "System Events"
                    set frontmost of process "GrammarlyLocal" to false
                end tell
                delay 0.15
                tell application "System Events"
                    keystroke "v" using {command down}
                end tell
                """
                subprocess.run(["osascript", "-e", script], check=False)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "pasted"}).encode("utf-8"))

        elif self.path == "/api/permissions/request":
            request_accessibility_permission()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "requested"}).encode("utf-8"))

        elif self.path == "/api/open_extension_folder":
            # Reveal the bundled extension folder in Finder
            subprocess.run(["open", EXTENSION_DIR], check=False)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "opened"}).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def start_server():
    try:
        server = ReusableTCPServer(("127.0.0.1", PORT), GrammarlyHTTPHandler)
        server.serve_forever()
    except Exception as e:
        print("Server start error:", e)


def _clipboard_monitor():
    last_clip = ""
    try:
        last_clip = subprocess.check_output(["pbpaste"], text=True)
    except Exception:
        pass

    while True:
        try:
            clip = subprocess.check_output(["pbpaste"], text=True)
            if clip and clip != last_clip and len(clip.strip()) > 3:
                last_clip = clip
                fixed, count = auto_correct_text(clip)
                if count > 0 and fixed != clip:
                    last_clip = fixed
                    p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
                    p.communicate(fixed)
                    subprocess.run(
                        [
                            "osascript",
                            "-e",
                            f'display notification "✨ Auto-fixed {count} error(s) in clipboard!" with title "GrammarlyLocal"',
                        ],
                        check=False,
                    )
        except Exception:
            pass
        time.sleep(0.8)


def start_floating_pill_daemon():
    """Start the floating selection pill watcher."""
    script = os.path.join(APP_DIR, "floating_widget.py")
    if not os.path.exists(script):
        script = os.path.join(APP_DIR, "Resources", "floating_widget.py")
    if os.path.exists(script):
        subprocess.Popen([sys.executable, script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    # 1. Ensure LanguageTool background engine is running
    ensure_languagetool_running()

    # 2. Start HTTP server thread
    t_server = threading.Thread(target=start_server, daemon=True)
    t_server.start()

    # 3. Start clipboard monitor thread
    t_clip = threading.Thread(target=_clipboard_monitor, daemon=True)
    t_clip.start()

    # 4. Start floating pill daemon
    start_floating_pill_daemon()

    # Wait for server ready
    time.sleep(0.3)

    # 5. Open native macOS WebKit window
    window = webview.create_window(
        title="GrammarlyLocal",
        url=f"http://127.0.0.1:{PORT}",
        width=1040,
        height=720,
        min_size=(880, 580),
        text_select=True,
    )
    webview.start()


if __name__ == "__main__":
    main()
