#!/usr/bin/env python3
"""
OpenGrammarly - System-wide Any-Input Detector for macOS.
Inspects the currently focused text field in ANY application (Safari, Chrome, Notes, Slack, etc.)
using the macOS Accessibility API (AXUIElement).
"""

import argparse
import ctypes
import ctypes.util
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

# Load ApplicationServices and CoreFoundation
app_services = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
core_foundation = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

# CoreFoundation Types
CFTypeRef = ctypes.c_void_p
CFStringRef = ctypes.c_void_p
AXUIElementRef = ctypes.c_void_p

# Setup function prototypes
app_services.AXIsProcessTrusted.restype = ctypes.c_bool
app_services.AXUIElementCreateSystemWide.restype = AXUIElementRef
app_services.AXUIElementCopyAttributeValue.restype = ctypes.c_int
app_services.AXUIElementCopyAttributeValue.argtypes = [
    AXUIElementRef,
    CFStringRef,
    ctypes.POINTER(CFTypeRef),
]
app_services.AXUIElementSetAttributeValue.restype = ctypes.c_int
app_services.AXUIElementSetAttributeValue.argtypes = [AXUIElementRef, CFStringRef, CFTypeRef]

core_foundation.CFStringCreateWithCString.restype = CFStringRef
core_foundation.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
core_foundation.CFStringGetLength.restype = ctypes.c_long
core_foundation.CFStringGetLength.argtypes = [CFStringRef]
core_foundation.CFStringGetCString.restype = ctypes.c_bool
core_foundation.CFStringGetCString.argtypes = [
    CFStringRef,
    ctypes.c_char_p,
    ctypes.c_long,
    ctypes.c_uint32,
]
core_foundation.CFRelease.argtypes = [ctypes.c_void_p]

kCFStringEncodingUTF8 = 0x08000100


def to_cfstring(py_str: str) -> CFStringRef:
    return core_foundation.CFStringCreateWithCString(None, py_str.encode("utf-8"), kCFStringEncodingUTF8)


def from_cfstring(cf_str: CFStringRef) -> str:
    if not cf_str:
        return ""
    length = core_foundation.CFStringGetLength(cf_str)
    buffer_size = length * 4 + 1
    buf = ctypes.create_string_buffer(buffer_size)
    if core_foundation.CFStringGetCString(cf_str, buf, buffer_size, kCFStringEncodingUTF8):
        return buf.value.decode("utf-8", errors="replace")
    return ""


# Pre-create CFStrings
kAXFocusedUIElement = to_cfstring("AXFocusedUIElement")
kAXValue = to_cfstring("AXValue")
kAXSelectedText = to_cfstring("AXSelectedText")
kAXTitle = to_cfstring("AXTitle")
kAXRole = to_cfstring("AXRole")

SERVER_URL = "http://localhost:8081/v2/check"


def notify(message: str, title: str = "OpenGrammarly"):
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], check=False)


def check_grammar(text: str, language: str = "en-US") -> list:
    if not text or not text.strip() or len(text) > 8000:
        return []
    data = urllib.parse.urlencode({"text": text, "language": language}).encode("utf-8")
    req = urllib.request.Request(SERVER_URL, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("matches", [])
    except Exception:
        return []


def auto_fix(text: str, matches: list) -> str:
    sorted_matches = sorted(matches, key=lambda m: m["offset"], reverse=True)
    corrected = list(text)
    last_end = len(text) + 1
    for m in sorted_matches:
        start = m["offset"]
        length = m["length"]
        end = start + length
        reps = m.get("replacements", [])
        if end <= last_end and reps:
            best = reps[0]["value"]
            corrected[start:end] = list(best)
            last_end = start
    return "".join(corrected)


def get_focused_input_text(system_wide: AXUIElementRef) -> tuple[AXUIElementRef, str, str]:
    """Get the currently focused UI element and its text/selected text."""
    var_focused = CFTypeRef()
    res = app_services.AXUIElementCopyAttributeValue(system_wide, kAXFocusedUIElement, ctypes.byref(var_focused))
    if res != 0 or not var_focused.value:
        return None, "", ""

    focused_elem = AXUIElementRef(var_focused.value)

    # Read value
    var_val = CFTypeRef()
    val_str = ""
    if app_services.AXUIElementCopyAttributeValue(focused_elem, kAXValue, ctypes.byref(var_val)) == 0:
        if var_val.value:
            val_str = from_cfstring(var_val.value)
            core_foundation.CFRelease(var_val)

    # Read selected text
    var_sel = CFTypeRef()
    sel_str = ""
    if app_services.AXUIElementCopyAttributeValue(focused_elem, kAXSelectedText, ctypes.byref(var_sel)) == 0:
        if var_sel.value:
            sel_str = from_cfstring(var_sel.value)
            core_foundation.CFRelease(var_sel)

    return focused_elem, val_str, sel_str


def main():
    parser = argparse.ArgumentParser(description="OpenGrammarly - Any Input Detector")
    parser.add_argument("--auto-replace", action="store_true", help="Automatically replace errors directly in the input")
    parser.add_argument("-l", "--language", default="en-US", help="Language (default: en-US)")
    args = parser.parse_args()

    # Check Accessibility permissions
    is_trusted = app_services.AXIsProcessTrusted()
    if not is_trusted:
        print("\n=======================================================")
        print("⚠️  macOS ACCESSIBILITY PERMISSION REQUIRED")
        print("=======================================================")
        print("To detect text in any input (Chrome, Safari, Slack, Notes):")
        print("1. Open System Settings -> Privacy & Security -> Accessibility")
        print("2. Enable permission for Terminal (or Python / OpenGrammarly)")
        print("=======================================================\n")
        # Trigger macOS permission prompt
        subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Settings" to reveal anchor "Privacy_Accessibility" of pane id "com.apple.preference.security"',
            ],
            check=False,
        )

    print(f"OpenGrammarly Input Watcher started (Language: {args.language})...")
    print("Monitoring focused input fields across all macOS apps...\n")

    system_wide = app_services.AXUIElementCreateSystemWide()
    last_text = ""
    last_check_time = 0

    while True:
        try:
            elem, val_text, sel_text = get_focused_input_text(system_wide)

            # Analyze either the selected text or the active field value
            target_text = sel_text if sel_text.strip() else val_text

            if target_text and target_text != last_text and len(target_text.strip()) > 3:
                now = time.time()
                # Debounce checks by 600ms to allow the user to finish typing
                if now - last_check_time > 0.6:
                    last_text = target_text
                    last_check_time = now

                    matches = check_grammar(target_text, language=args.language)
                    if matches:
                        count = len(matches)
                        first_err = matches[0]
                        err_word = target_text[first_err["offset"] : first_err["offset"] + first_err["length"]]
                        best_rep = first_err.get("replacements", [{}])[0].get("value", "")

                        print(f"[{time.strftime('%H:%M:%S')}] Detected {count} error(s) in active input:")
                        print(f"  Issue: \"{err_word}\" → Suggestion: \"{best_rep}\"")

                        if args.auto_replace and elem:
                            fixed_text = auto_fix(target_text, matches)
                            cf_fixed = to_cfstring(fixed_text)
                            app_services.AXUIElementSetAttributeValue(elem, kAXValue, cf_fixed)
                            core_foundation.CFRelease(cf_fixed)
                            notify(f"✨ Auto-fixed {count} error(s) in input!", "OpenGrammarly")
                        else:
                            notify(f"⚠️ {count} error(s) found! (e.g. \"{err_word}\" → \"{best_rep}\")", "OpenGrammarly")

            if elem:
                core_foundation.CFRelease(elem)

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception:
            pass

        time.sleep(0.5)


if __name__ == "__main__":
    main()
