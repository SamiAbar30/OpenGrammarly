#!/usr/bin/env python3
"""
OpenGrammarly - All-in-One Automated macOS Application.
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

try:
    import AppKit
    import Quartz
except Exception:
    AppKit = None
    Quartz = None

try:
    from pynput import keyboard
except Exception:
    keyboard = None

APP_DIR = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(APP_DIR, "ui")
if not os.path.exists(UI_DIR):
    UI_DIR = os.path.join(APP_DIR, "Resources", "ui")

EXTENSION_DIR = os.path.join(APP_DIR, "extension")
if not os.path.exists(EXTENSION_DIR):
    EXTENSION_DIR = os.path.join(APP_DIR, "Resources", "extension")

USER_EXTENSION_DIR = os.path.expanduser("~/Downloads/OpenGrammarly-Extension")

def ensure_extension_exported():
    """Exports Chrome extension to ~/Downloads/OpenGrammarly-Extension for easy 1-click loading."""
    try:
        if not os.path.exists(EXTENSION_DIR):
            return
        os.makedirs(USER_EXTENSION_DIR, exist_ok=True)
        import shutil
        for item in os.listdir(EXTENSION_DIR):
            s = os.path.join(EXTENSION_DIR, item)
            d = os.path.join(USER_EXTENSION_DIR, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
    except Exception as e:
        print("[OpenGrammarly] Export extension error:", e)

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
        from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
        AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
    except Exception:
        try:
            app_services = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
            app_services.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
            app_services.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
            app_services.AXIsProcessTrustedWithOptions(None)
        except Exception:
            pass

    # Open the Accessibility pane in System Settings directly
    subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"], check=False)


# Common word sets for instant, offline language identification
COMMON_EN = {'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at', 'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she', 'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what', 'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go', 'me', 'when', 'make', 'can', 'like', 'time', 'no', 'just', 'him', 'know', 'take', 'person', 'into', 'year', 'your', 'good', 'some', 'could', 'them', 'see', 'other', 'than', 'then', 'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also', 'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first', 'well', 'way', 'even', 'new', 'want', 'because', 'any', 'these', 'give', 'day', 'most', 'us', 'hello', 'hi', 'hey', 'im', 'am', 'is', 'are', 'was', 'were', 'been', 'thanks', 'thank', 'please', 'dont', 'cant', 'wont', 'ive', 'youre', 'theyre', 'sami'}
COMMON_FR = {'le', 'la', 'les', 'un', 'une', 'des', 'bonjour', 'salut', 'merci', 'oui', 'non', 'vous', 'nous', 'ils', 'elles', 'avec', 'pour', 'dans', 'sur', 'est', 'sont', 'cette', 'cet', 'mais', 'donc', 'alors', 'très', 'bien', 'comment', 'quoi', 'où', 'pourquoi', 'être', 'avoir', 'je', 'tu', 'il', 'elle', 'ça', 'va', 'suis', 'mon', 'ma', 'mes', 'ton', 'ta', 'tes', 'son', 'sa', 'ses'}
COMMON_ES = {'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'hola', 'gracias', 'buenos', 'días', 'tardes', 'noches', 'qué', 'cómo', 'dónde', 'cuándo', 'por', 'para', 'con', 'pero', 'más', 'este', 'esta', 'esto', 'está', 'son', 'tienen', 'tienes', 'amigo', 'favor', 'usted', 'yo', 'tú', 'él', 'ella', 'nosotros', 'bien'}
COMMON_DE = {'der', 'die', 'das', 'ein', 'eine', 'hallo', 'guten', 'morgen', 'tag', 'danke', 'bitte', 'und', 'ist', 'sind', 'nicht', 'mit', 'für', 'auf', 'wie', 'was', 'warum', 'ich', 'du', 'er', 'sie', 'wir', 'ihr', 'haben', 'sein', 'werden', 'gut'}
COMMON_IT = {'ciao', 'grazie', 'buongiorno', 'buonasera', 'per', 'favore', 'come', 'dove', 'quando', 'perché', 'sono', 'siamo', 'hanno', 'questo', 'questa', 'molto'}


def detect_language(text: str) -> str:
    """Detect language offline accurately even on short snippets."""
    if not text or not text.strip():
        return "en-US"
    if re.search(r'[\u0600-\u06FF]', text):
        return "ar"
    if re.search(r'[\u0400-\u04FF]', text):
        return "ru"

    words = set(re.findall(r"[a-zA-Z']+", text.lower()))
    scores = [
        ("fr", len(words & COMMON_FR)),
        ("es", len(words & COMMON_ES)),
        ("de", len(words & COMMON_DE)),
        ("it", len(words & COMMON_IT)),
        ("en-US", len(words & COMMON_EN)),
    ]
    scores.sort(key=lambda x: x[1], reverse=True)
    if scores[0][1] > 0:
        return scores[0][0]

    # Secondary check with langdetect if installed
    try:
        from langdetect import detect as ld_detect
        detected = ld_detect(text)
        lang_map = {"en": "en-US", "fr": "fr", "es": "es", "de": "de-DE", "it": "it", "pt": "pt-PT", "ar": "ar"}
        if detected in lang_map:
            return lang_map[detected]
    except Exception:
        pass

    return "en-US"


def enhance_text_rules(text: str, matches: list) -> list:
    enhanced = list(matches)

    # 1. Missing comma after greeting or missing subject: "Hi am Sami" -> "Hi, I'm Sami"
    m_hi_am = re.search(r'\b(Hi|Hello|Hey)\s+am\s+([A-Za-z\']+)', text, re.IGNORECASE)
    if m_hi_am:
        g = m_hi_am.group(1).capitalize()
        name = m_hi_am.group(2)
        enhanced.append({
            "message": f'Did you mean "{g}, I\'m {name}"?',
            "shortMessage": "Missing subject",
            "replacements": [{"value": f"{g}, I'm {name}"}, {"value": f"{g}, I am {name}"}],
            "offset": m_hi_am.start(),
            "length": len(m_hi_am.group(0)),
            "rule": {"id": "GREETING_IM_NAME", "issueType": "grammar", "category": {"id": "GRAMMAR", "name": "Grammar"}}
        })
    else:
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
    if language == "auto" or not language:
        language = detect_language(text)
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
    if language == "auto" or not language:
        language = detect_language(text)
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
                    set frontmost of process "OpenGrammarly" to false
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
            ensure_extension_exported()
            subprocess.run(["open", USER_EXTENSION_DIR], check=False)
            # Copy path to clipboard for instant pasting if needed
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
            p.communicate(USER_EXTENSION_DIR)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "opened", "path": USER_EXTENSION_DIR}).encode("utf-8"))

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
                            f'display notification "✨ Auto-fixed {count} error(s) in clipboard!" with title "OpenGrammarly"',
                        ],
                        check=False,
                    )
        except Exception:
            pass
        time.sleep(0.8)


def _simulate_cmd_key(keycode: int):
    """Simulate Cmd + <key> via Quartz or osascript fallback."""
    if Quartz:
        try:
            ev_down = Quartz.CGEventCreateKeyboardEvent(None, keycode, True)
            Quartz.CGEventSetFlags(ev_down, Quartz.kCGEventFlagMaskCommand)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_down)
            time.sleep(0.02)
            ev_up = Quartz.CGEventCreateKeyboardEvent(None, keycode, False)
            Quartz.CGEventSetFlags(ev_up, Quartz.kCGEventFlagMaskCommand)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_up)
            return
        except Exception:
            pass

    key_char = "c" if keycode == 8 else "v"
    subprocess.run([
        "osascript", "-e",
        f'tell application "System Events" to keystroke "{key_char}" using {{command down}}'
    ], check=False)


def fix_active_selection():
    """
    Called by Global Hotkey (Cmd+Alt+G / Cmd+Shift+G) or Menu Bar Item.
    Copies selected text from current frontmost app, auto-fixes mistakes locally,
    and pastes the corrected text back into the active application.
    """
    try:
        # Give frontmost app focus if triggered from menu bar
        time.sleep(0.05)

        # 1. Simulate Cmd+C to copy selected text (keycode 8 is 'c')
        _simulate_cmd_key(8)
        time.sleep(0.12)

        # 2. Read copied text from pbpaste
        try:
            raw_text = subprocess.check_output(["pbpaste"], text=True)
        except Exception:
            raw_text = ""

        if not raw_text or not raw_text.strip():
            subprocess.run([
                "osascript", "-e",
                'display notification "💡 Highlight text first, then press ⌘⌥G (or ⌘⇧G) to auto-fix!" with title "OpenGrammarly"'
            ], check=False)
            return

        # 3. Auto-correct text using our engine
        fixed, count = auto_correct_text(raw_text, "auto")

        if count > 0 and fixed != raw_text:
            # 4. Copy fixed text back to clipboard
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
            p.communicate(fixed)
            time.sleep(0.06)

            # 5. Paste back into active window (keycode 9 is 'v')
            _simulate_cmd_key(9)

            subprocess.run([
                "osascript", "-e",
                f'display notification "✨ Auto-fixed {count} error(s) in place!" with title "OpenGrammarly"'
            ], check=False)
        else:
            subprocess.run([
                "osascript", "-e",
                'display notification "✨ All clear! No errors found in selection." with title "OpenGrammarly"'
            ], check=False)
    except Exception as e:
        print("[OpenGrammarly] fix_active_selection error:", e)


_hotkey_listener = None

def _hotkey_supervisor():
    """Continuously monitors accessibility permissions and ensures global hotkeys remain active."""
    global _hotkey_listener
    if not keyboard:
        return

    def on_hotkey():
        threading.Thread(target=fix_active_selection, daemon=True).start()

    was_trusted = False
    registered = False

    while True:
        trusted = is_accessibility_trusted()
        if not registered or (trusted and not was_trusted):
            if _hotkey_listener:
                try:
                    _hotkey_listener.stop()
                except Exception:
                    pass
            try:
                _hotkey_listener = keyboard.GlobalHotKeys({
                    '<cmd>+<alt>+g': on_hotkey,
                    '<cmd>+<shift>+g': on_hotkey,
                })
                _hotkey_listener.start()
                registered = True
                print("[OpenGrammarly] Global Hotkeys (⌘⌥G / ⌘⇧G) successfully initialized!")
            except Exception as e:
                print("[OpenGrammarly] Hotkey supervisor init error:", e)

        was_trusted = trusted
        time.sleep(2.0)


def start_global_hotkey_daemon():
    """Starts global hotkey supervisor daemon."""
    t = threading.Thread(target=_hotkey_supervisor, daemon=True)
    t.start()


LAUNCH_AGENT_PATH = os.path.expanduser("~/Library/LaunchAgents/org.opengrammarly.app.plist")

def is_launch_at_login_enabled() -> bool:
    return os.path.exists(LAUNCH_AGENT_PATH)

def toggle_launch_at_login() -> bool:
    if is_launch_at_login_enabled():
        try:
            os.remove(LAUNCH_AGENT_PATH)
        except Exception:
            pass
        return False
    else:
        try:
            os.makedirs(os.path.dirname(LAUNCH_AGENT_PATH), exist_ok=True)
            plist_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>org.opengrammarly.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/open</string>
        <string>/Applications/OpenGrammarly.app</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
            with open(LAUNCH_AGENT_PATH, "w") as f:
                f.write(plist_content)
            return True
        except Exception:
            return False


if AppKit:
    class MenuHandler(AppKit.NSObject):
        def setWindow_(self, win):
            self._window = win

        def showWindow_(self, sender):
            if self._window:
                self._window.show()
                self._window.restore()
                AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

        def fixSelection_(self, sender):
            threading.Thread(target=fix_active_selection, daemon=True).start()

        def openTranslator_(self, sender):
            if self._window:
                self._window.show()
                self._window.restore()
                AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
                self._window.evaluate_js("if (typeof switchTab === 'function') switchTab('translate');")

        def openExtension_(self, sender):
            ensure_extension_exported()
            subprocess.run(["open", USER_EXTENSION_DIR], check=False)

        def toggleLaunchAtLogin_(self, sender):
            new_state = toggle_launch_at_login()
            sender.setState_(AppKit.NSControlStateValueOn if new_state else AppKit.NSControlStateValueOff)

        def quitApp_(self, sender):
            AppKit.NSApplication.sharedApplication().terminate_(self)

_status_item = None
_menu_handler = None

def setup_menu_bar(window):
    global _status_item, _menu_handler
    if not AppKit:
        return
    try:
        status_bar = AppKit.NSStatusBar.systemStatusBar()
        _status_item = status_bar.statusItemWithLength_(AppKit.NSVariableStatusItemLength)
        button = _status_item.button()
        button.setTitle_("✍️")
        button.setToolTip_("OpenGrammarly - Click for Fast Access")

        _menu_handler = MenuHandler.alloc().init()
        _menu_handler.setWindow_(window)

        menu = AppKit.NSMenu.alloc().init()

        # Open Window
        item_open = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Open OpenGrammarly", "showWindow:", "o")
        item_open.setTarget_(_menu_handler)
        menu.addItem_(item_open)

        # Fix Selection
        item_fix = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Fix Selected Text (⌘⌥G)", "fixSelection:", "g")
        item_fix.setKeyEquivalentModifierMask_(AppKit.NSEventModifierFlagCommand | AppKit.NSEventModifierFlagOption)
        item_fix.setTarget_(_menu_handler)
        menu.addItem_(item_fix)

        # DeepL Translator Tab
        item_trans = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("DeepL Translator Tab", "openTranslator:", "t")
        item_trans.setTarget_(_menu_handler)
        menu.addItem_(item_trans)

        menu.addItem_(AppKit.NSMenuItem.separatorItem())

        # Chrome Extension Folder
        item_ext = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Chrome Extension Folder...", "openExtension:", "")
        item_ext.setTarget_(_menu_handler)
        menu.addItem_(item_ext)

        # Launch at Login
        item_login = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Launch on Mac Startup", "toggleLaunchAtLogin:", "")
        item_login.setTarget_(_menu_handler)
        item_login.setState_(AppKit.NSControlStateValueOn if is_launch_at_login_enabled() else AppKit.NSControlStateValueOff)
        menu.addItem_(item_login)

        menu.addItem_(AppKit.NSMenuItem.separatorItem())

        # Quit
        item_quit = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit OpenGrammarly", "quitApp:", "q")
        item_quit.setTarget_(_menu_handler)
        menu.addItem_(item_quit)

        _status_item.setMenu_(menu)
        print("[OpenGrammarly] Menu bar status item configured successfully!")
    except Exception as e:
        print("[OpenGrammarly] Menu bar setup error:", e)


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

    # 4. Start global hotkey daemon (Cmd+Alt+G / Cmd+Shift+G)
    start_global_hotkey_daemon()

    # 5. Start floating pill daemon
    start_floating_pill_daemon()

    # 6. Ensure Chrome extension is exported to ~/Downloads/OpenGrammarly-Extension
    ensure_extension_exported()

    # Wait for server ready
    time.sleep(0.3)

    # 6. Open native macOS WebKit window
    window = webview.create_window(
        title="OpenGrammarly",
        url=f"http://127.0.0.1:{PORT}",
        width=1040,
        height=720,
        min_size=(880, 580),
        text_select=True,
    )

    # 7. Setup macOS Menu Bar fast-access icon
    setup_menu_bar(window)

    # 8. Keep app running in Menu Bar when window is closed (red X button)
    def on_closing():
        window.hide()
        return False

    window.events.closing += on_closing

    # Start PyWebView Cocoa event loop
    webview.start()


if __name__ == "__main__":
    main()
