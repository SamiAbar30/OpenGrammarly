#!/usr/bin/env python3
"""
OpenGrammarly in-place text auto-fixer for macOS.
Reads selected text from clipboard, checks with local engine,
replaces errors, updates clipboard, and sends a notification.
"""

import os
import subprocess
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
if DIR not in sys.path:
    sys.path.insert(0, DIR)

try:
    from app import auto_correct_text
except Exception:
    import urllib.parse
    import urllib.request
    import json
    def auto_correct_text(text: str, language: str = "en-US") -> tuple[str, int]:
        data = urllib.parse.urlencode({"text": text, "language": language}).encode("utf-8")
        req = urllib.request.Request("http://localhost:8081/v2/check", data=data, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                matches = sorted(res.get("matches", []), key=lambda m: m["offset"], reverse=True)
                corrected = list(text)
                last_end = len(text) + 1
                count = 0
                for m in matches:
                    start, length = m["offset"], m["length"]
                    end = start + length
                    reps = m.get("replacements", [])
                    if end <= last_end and reps:
                        corrected[start:end] = list(reps[0]["value"])
                        last_end = start
                        count += 1
                return "".join(corrected), count
        except Exception:
            return text, 0


def notify(title: str, message: str):
    """Send a native macOS notification banner."""
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], check=False)


def main():
    use_stdin = "--stdin" in sys.argv
    if use_stdin:
        raw_text = sys.stdin.read()
    else:
        try:
            raw_text = subprocess.check_output(["pbpaste"], text=True)
        except Exception:
            raw_text = ""

    if not raw_text or not raw_text.strip():
        if use_stdin:
            sys.stdout.write(raw_text or "")
        return

    fixed_text, count = auto_correct_text(raw_text, "auto")

    if count > 0 and fixed_text != raw_text:
        if use_stdin:
            sys.stdout.write(fixed_text)
            notify("OpenGrammarly", f"✨ Automatically fixed {count} error(s)!")
        else:
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
            proc.communicate(fixed_text)
            notify("OpenGrammarly", f"✨ Automatically fixed {count} error(s)!")
            print(f"FIXED:{count}")
    else:
        if use_stdin:
            sys.stdout.write(raw_text)
        else:
            print("NO_CHANGES")


if __name__ == "__main__":
    main()
