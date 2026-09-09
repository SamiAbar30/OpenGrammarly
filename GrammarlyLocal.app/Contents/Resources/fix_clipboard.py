#!/usr/bin/env python3
"""
Grammarly-like in-place text auto-fixer for macOS.
Reads selected text from clipboard, checks with local LanguageTool server,
replaces errors, updates clipboard, and sends a notification.
"""

import json
import subprocess
import sys
import urllib.parse
import urllib.request


def notify(title: str, message: str):
    """Send a native macOS notification banner."""
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], check=False)


def check_and_fix(text: str, language: str = "en-US") -> tuple[str, int]:
    """Check text with local LanguageTool and return (fixed_text, error_count)."""
    if not text or not text.strip():
        return text, 0

    data = urllib.parse.urlencode({"text": text, "language": language}).encode("utf-8")
    req = urllib.request.Request("http://localhost:8081/v2/check", data=data, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        notify("LanguageTool Error", f"Cannot connect to server: {e}")
        return text, 0

    matches = result.get("matches", [])
    if not matches:
        return text, 0

    # Sort matches in reverse order by offset
    matches.sort(key=lambda m: m["offset"], reverse=True)

    corrected = list(text)
    last_end = len(text) + 1
    applied_count = 0

    for match in matches:
        start = match["offset"]
        length = match["length"]
        end = start + length
        replacements = match.get("replacements", [])

        if end > last_end:
            continue
        if replacements:
            best_fix = replacements[0]["value"]
            corrected[start:end] = list(best_fix)
            last_end = start
            applied_count += 1

    return "".join(corrected), applied_count


def main():
    use_stdin = "--stdin" in sys.argv
    if use_stdin:
        raw_text = sys.stdin.read()
    else:
        raw_text = subprocess.check_output(["pbpaste"], text=True)

    fixed_text, count = check_and_fix(raw_text)

    if count > 0 and fixed_text != raw_text:
        # Write fixed text to pbcopy
        proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
        proc.communicate(fixed_text)
        notify("LanguageTool Grammarly", f"✨ Automatically fixed {count} error(s)!")
        print(f"FIXED:{count}")
    else:
        print("NO_CHANGES")


if __name__ == "__main__":
    main()
