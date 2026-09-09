#!/usr/bin/env bash
# Grammarly in-place fixer for selected text in ANY active macOS application.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

osascript << EOF
tell application "System Events"
    -- 1. Copy selected text
    keystroke "c" using {command down}
end tell

delay 0.15

-- 2. Check and fix text in clipboard
set fixResult to do shell script "python3 '$DIR/fix_clipboard.py'"

-- 3. If fixed, paste the corrected text back
if fixResult starts with "FIXED" then
    tell application "System Events"
        keystroke "v" using {command down}
    end tell
end if
EOF
