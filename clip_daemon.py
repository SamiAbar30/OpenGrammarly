#!/usr/bin/env python3
"""
Background clipboard auto-fixer for macOS.
Continuously monitors clipboard. When you copy text with grammatical or spelling errors,
it automatically fixes it and updates your clipboard with a notification.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

SERVER_URL = "http://localhost:8081/v2/check"


def notify(message: str, title: str = "OpenGrammarly"):
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], check=False)


def check_and_fix(text: str, language: str = "en-US") -> tuple[str, int]:
    if not text or not text.strip() or len(text) > 10000:
        return text, 0

    data = urllib.parse.urlencode({"text": text, "language": language}).encode("utf-8")
    req = urllib.request.Request(SERVER_URL, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return text, 0

    matches = data.get("matches", [])
    if not matches:
        return text, 0

    matches.sort(key=lambda m: m["offset"], reverse=True)
    corrected = list(text)
    last_end = len(text) + 1
    count = 0

    for m in matches:
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


def paste_into_active_app():
    """Simulate Cmd+V to paste the fixed text directly into the active field."""
    script = '''
    tell application "System Events"
        keystroke "v" using {command down}
    end tell
    '''
    subprocess.run(["osascript", "-e", script], check=False)


def main():
    parser = argparse.ArgumentParser(description="LanguageTool Background Clipboard Auto-Fixer")
    parser.add_argument("-l", "--language", default="en-US", help="Language code (default: en-US)")
    parser.add_argument("--auto-paste", action="store_true", help="Automatically paste fixed text into active app")
    args = parser.parse_args()

    print("==================================================")
    print(" OpenGrammarly Clipboard Monitor Running")
    print(f" Language: {args.language}")
    print(f" Auto-paste: {'Enabled' if args.auto_paste else 'Disabled (Updates clipboard only)'}")
    print(" Press Ctrl+C to stop")
    print("==================================================")

    last_text = ""
    try:
        last_text = subprocess.check_output(["pbpaste"], text=True)
    except Exception:
        pass

    while True:
        try:
            current = subprocess.check_output(["pbpaste"], text=True)
            if current and current != last_text and current.strip():
                last_text = current
                fixed, count = check_and_fix(current, language=args.language)
                if count > 0 and fixed != current:
                    last_text = fixed
                    p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
                    p.communicate(fixed)
                    print(f"[{time.strftime('%H:%M:%S')}] Fixed {count} issue(s):")
                    print(f"  Before: {current.strip()[:60]}...")
                    print(f"  After : {fixed.strip()[:60]}...\n")
                    notify(f"✨ Auto-fixed {count} error(s)!", "OpenGrammarly")
                    if args.auto_paste:
                        time.sleep(0.1)
                        paste_into_active_app()
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception:
            pass
        time.sleep(0.8)


if __name__ == "__main__":
    main()
