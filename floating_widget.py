#!/usr/bin/env python3
"""
GrammarlyLocal - Floating Selection Action Pill.
Monitors selected text across macOS applications.
When text with errors is highlighted, displays a floating pill near the cursor with 1-click auto-fix.
"""

import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CHECK_API = "http://127.0.0.1:8082/api/check"

# Accessibility API setup
try:
    app_services = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
    core_foundation = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

    CFTypeRef = ctypes.c_void_p
    CFStringRef = ctypes.c_void_p
    AXUIElementRef = ctypes.c_void_p

    app_services.AXUIElementCreateSystemWide.restype = AXUIElementRef
    app_services.AXUIElementCopyAttributeValue.restype = ctypes.c_int
    app_services.AXUIElementCopyAttributeValue.argtypes = [AXUIElementRef, CFStringRef, ctypes.POINTER(CFTypeRef)]
    app_services.AXUIElementSetAttributeValue.restype = ctypes.c_int
    app_services.AXUIElementSetAttributeValue.argtypes = [AXUIElementRef, CFStringRef, CFTypeRef]

    core_foundation.CFStringCreateWithCString.restype = CFStringRef
    core_foundation.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
    core_foundation.CFStringGetLength.restype = ctypes.c_long
    core_foundation.CFStringGetLength.argtypes = [CFStringRef]
    core_foundation.CFStringGetCString.restype = ctypes.c_bool
    core_foundation.CFStringGetCString.argtypes = [CFStringRef, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
    core_foundation.CFRelease.argtypes = [ctypes.c_void_p]

    kUTF8 = 0x08000100
    kAXFocusedUIElement = core_foundation.CFStringCreateWithCString(None, b"AXFocusedUIElement", kUTF8)
    kAXSelectedText = core_foundation.CFStringCreateWithCString(None, b"AXSelectedText", kUTF8)
    system_wide = app_services.AXUIElementCreateSystemWide()
except Exception:
    system_wide = None


def get_current_selection() -> tuple[any, str]:
    if not system_wide:
        return None, ""
    try:
        var_focused = CFTypeRef()
        if app_services.AXUIElementCopyAttributeValue(system_wide, kAXFocusedUIElement, ctypes.byref(var_focused)) == 0 and var_focused.value:
            elem = AXUIElementRef(var_focused.value)
            var_sel = CFTypeRef()
            sel_str = ""
            if app_services.AXUIElementCopyAttributeValue(elem, kAXSelectedText, ctypes.byref(var_sel)) == 0 and var_sel.value:
                length = core_foundation.CFStringGetLength(var_sel.value)
                buf = ctypes.create_string_buffer(length * 4 + 1)
                if core_foundation.CFStringGetCString(var_sel.value, buf, len(buf), kUTF8):
                    sel_str = buf.value.decode("utf-8", errors="replace")
                core_foundation.CFRelease(var_sel)
            return elem, sel_str
    except Exception:
        pass
    return None, ""


def check_text(text: str) -> list:
    if not text or len(text.strip()) < 3 or len(text) > 4000:
        return []
    try:
        data = json.dumps({"text": text, "language": "en-US"}).encode("utf-8")
        req = urllib.request.Request(CHECK_API, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return json.loads(resp.read().decode("utf-8")).get("matches", [])
    except Exception:
        return []


def auto_correct(text: str, matches: list) -> str:
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


class FloatingPill:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()

        self.pill = tk.Toplevel(self.root)
        self.pill.overrideredirect(True)
        self.pill.wm_attributes("-topmost", True)
        self.pill.configure(bg="#0f172a", highlightthickness=1, highlightbackground="#10b981")
        self.pill.withdraw()

        # Layout inside pill
        self.frame = tk.Frame(self.pill, bg="#0f172a", padx=8, pady=4)
        self.frame.pack()

        self.logo_lbl = tk.Label(self.frame, text="✍️", font=("SF Pro Text", 12), bg="#0f172a", fg="white")
        self.logo_lbl.pack(side=tk.LEFT, padx=(0, 4))

        self.info_lbl = tk.Label(
            self.frame,
            text="2 errors",
            font=("SF Pro Text", 11, "bold"),
            bg="#0f172a",
            fg="#fb7185",
        )
        self.info_lbl.pack(side=tk.LEFT, padx=(0, 6))

        self.fix_btn = tk.Button(
            self.frame,
            text="⚡ Fix",
            font=("SF Pro Text", 10, "bold"),
            bg="#10b981",
            fg="white",
            activebackground="#059669",
            activeforeground="white",
            relief=tk.FLAT,
            padx=8,
            pady=1,
            cursor="pointinghand",
            command=self.on_fix_click,
        )
        self.fix_btn.pack(side=tk.LEFT)

        self.current_elem = None
        self.current_text = ""
        self.current_matches = []
        self.last_checked_text = ""
        self.visible = False

        # Start background polling
        self.poll_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.poll_thread.start()

    def show(self, x, y, count):
        self.info_lbl.config(text=f"{count} error{'s' if count > 1 else ''}")
        self.pill.geometry(f"+{x + 15}+{y + 15}")
        self.pill.deiconify()
        self.pill.lift()
        self.visible = True

    def hide(self):
        if self.visible:
            self.pill.withdraw()
            self.visible = False

    def on_fix_click(self):
        if not self.current_text or not self.current_matches:
            self.hide()
            return

        fixed = auto_correct(self.current_text, self.current_matches)

        # Method A: Direct Accessibility Replacement
        replaced = False
        if self.current_elem:
            try:
                cf_fixed = core_foundation.CFStringCreateWithCString(None, fixed.encode("utf-8"), kUTF8)
                res = app_services.AXUIElementSetAttributeValue(self.current_elem, kAXSelectedText, cf_fixed)
                core_foundation.CFRelease(cf_fixed)
                if res == 0:
                    replaced = True
            except Exception:
                pass

        # Method B: Clipboard + Cmd+V Fallback
        if not replaced:
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
            p.communicate(fixed)
            subprocess.run(["osascript", "-e", 'tell application "System Events" to keystroke "v" using {command down}'], check=False)

        subprocess.run(["osascript", "-e", f'display notification "✨ Fixed {len(self.current_matches)} error(s)!" with title "GrammarlyLocal"'], check=False)
        self.hide()
        self.last_checked_text = fixed

    def _monitor_loop(self):
        while True:
            try:
                elem, sel_text = get_current_selection()
                sel_clean = sel_text.strip()

                if sel_clean and len(sel_clean) > 3:
                    if sel_clean != self.last_checked_text:
                        self.last_checked_text = sel_clean
                        matches = check_text(sel_clean)
                        if matches:
                            self.current_elem = elem
                            self.current_text = sel_text
                            self.current_matches = matches
                            px, py = self.root.winfo_pointerxy()
                            self.root.after(0, lambda x=px, y=py, c=len(matches): self.show(x, y, c))
                        else:
                            self.root.after(0, self.hide)
                else:
                    if self.visible:
                        self.root.after(0, self.hide)
            except Exception:
                pass
            time.sleep(0.4)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    pill = FloatingPill()
    pill.run()
