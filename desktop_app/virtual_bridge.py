"""
virtual_bridge.py — Zero-Latency Win32 SendInput Virtual HID Bridge
Translates wireless OMP packets from OmniScroll into native Windows
mouse wheel, horizontal pan, media keys, and keyboard shortcuts.
"""
import ctypes
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Win32 Constants
INPUT_MOUSE    = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_WHEEL  = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000

KEYEVENTF_KEYDOWN  = 0x0000
KEYEVENTF_KEYUP    = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001

# Virtual Key Codes
VK_BACK        = 0x08
VK_TAB         = 0x09
VK_SHIFT       = 0x10
VK_CONTROL     = 0x11
VK_MENU        = 0x12  # Alt
VK_LEFT        = 0x25
VK_RIGHT       = 0x27
VK_LWIN        = 0x5B
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP   = 0xAF
VK_MEDIA_NEXT  = 0xB0
VK_MEDIA_PREV  = 0xB1
VK_PLAY_PAUSE  = 0xB3
VK_C           = 0x43
VK_V           = 0x56
VK_Z           = 0x5A

# Windows SendInput C-Struct Definitions
ULONG_PTR = ctypes.c_ulong if ctypes.sizeof(ctypes.c_void_p) == 4 else ctypes.c_ulonglong

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          ctypes.c_long),
        ("dy",          ctypes.c_long),
        ("mouseData",   ctypes.c_ulong),
        ("dwFlags",     ctypes.c_ulong),
        ("time",        ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR)
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         ctypes.c_ushort),
        ("wScan",       ctypes.c_ushort),
        ("dwFlags",     ctypes.c_ulong),
        ("time",        ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR)
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg",    ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort)
    ]

class DUMMYUNIONNAME(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u",    DUMMYUNIONNAME)
    ]

user32 = ctypes.windll.user32


class VirtualBridge:
    """Dispatches native Windows input events with <1ms latency."""
    def __init__(self):
        self.sub_tick_acc = 0
        self.accumulation = 0
        self.tspin_acc = 0
        self.alt_held = False

    def scroll_vertical(self, ticks: int):
        """Injects vertical mouse wheel scroll."""
        inp = INPUT()
        inp.type = INPUT_MOUSE
        # Cast ticks to signed 32-bit int, then c_ulong bitwise
        val = int(ticks)
        inp.u.mi.mouseData = ctypes.c_ulong(val & 0xFFFFFFFF).value
        inp.u.mi.dwFlags = MOUSEEVENTF_WHEEL
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def scroll_horizontal(self, ticks: int):
        """Injects horizontal mouse wheel scroll (AC Pan)."""
        inp = INPUT()
        inp.type = INPUT_MOUSE
        val = int(ticks)
        inp.u.mi.mouseData = ctypes.c_ulong(val & 0xFFFFFFFF).value
        inp.u.mi.dwFlags = MOUSEEVENTF_HWHEEL
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def press_key(self, vk: int, extended=False):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.u.ki.wVk = vk
        flags = KEYEVENTF_KEYDOWN
        if extended:
            flags |= KEYEVENTF_EXTENDEDKEY
        inp.u.ki.dwFlags = flags
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def release_key(self, vk: int, extended=False):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.u.ki.wVk = vk
        flags = KEYEVENTF_KEYUP
        if extended:
            flags |= KEYEVENTF_EXTENDEDKEY
        inp.u.ki.dwFlags = flags
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def tap_key(self, vk: int, extended=False):
        self.press_key(vk, extended)
        time.sleep(0.015)
        self.release_key(vk, extended)

    def tap_combo(self, keys: list):
        """Presses keys in order, holds for 15ms, then releases in reverse order."""
        for k in keys:
            self.press_key(k)
        time.sleep(0.015)
        for k in reversed(keys):
            self.release_key(k)

    def register_custom_action(self, action_id: int, callback):
        """Allows registering user-defined macro/shortcut callbacks for future expansion."""
        if not hasattr(self, '_custom_actions'):
            self._custom_actions = {}
        self._custom_actions[action_id] = callback

    def dispatch_action(self, action_id: int):
        """Executes one of the standard OmniScroll actions or a registered custom macro."""
        if action_id == 0:
            return

        if hasattr(self, '_custom_actions') and action_id in self._custom_actions:
            try:
                self._custom_actions[action_id]()
                return
            except Exception as e:
                logging.error(f"Custom action {action_id} error: {e}")

        if action_id == 1:   # Browser Back (Alt+Left)
            self.tap_combo([VK_MENU, VK_LEFT])
        elif action_id == 2:   # Browser Forward (Alt+Right)
            self.tap_combo([VK_MENU, VK_RIGHT])
        elif action_id == 3:   # Undo (Ctrl+Z)
            self.tap_combo([VK_CONTROL, VK_Z])
        elif action_id == 4:   # Redo (Ctrl+Shift+Z)
            self.tap_combo([VK_CONTROL, VK_SHIFT, VK_Z])
        elif action_id == 5:   # Media Previous
            self.tap_key(VK_MEDIA_PREV, extended=True)
        elif action_id == 6:   # Media Next
            self.tap_key(VK_MEDIA_NEXT, extended=True)
        elif action_id == 7:   # Previous Tab (Ctrl+Shift+Tab)
            self.tap_combo([VK_CONTROL, VK_SHIFT, VK_TAB])
        elif action_id == 8:   # Next Tab (Ctrl+Tab)
            self.tap_combo([VK_CONTROL, VK_TAB])
        elif action_id == 9:   # Previous Desktop (Win+Ctrl+Left)
            self.tap_combo([VK_LWIN, VK_CONTROL, VK_LEFT])
        elif action_id == 10:  # Next Desktop (Win+Ctrl+Right)
            self.tap_combo([VK_LWIN, VK_CONTROL, VK_RIGHT])
        elif action_id == 11:  # Volume Down
            self.tap_key(VK_VOLUME_DOWN, extended=True)
        elif action_id == 12:  # Volume Up
            self.tap_key(VK_VOLUME_UP, extended=True)
        elif action_id == 13:  # Copy (Ctrl+C)
            self.tap_combo([VK_CONTROL, VK_C])
        elif action_id == 14:  # Paste (Ctrl+V)
            self.tap_combo([VK_CONTROL, VK_V])
        elif action_id == 25:  # Play / Pause
            self.tap_key(VK_PLAY_PAUSE, extended=True)

    def dispatch_touch_spin(self, action_id: int, delta: int, thr: int = 10):
        """Translates continuous bidirectional Touch & Spin motion."""
        if action_id == 0:
            return
        elif action_id == 1:  # Horizontal Scroll
            self.scroll_horizontal(int(delta * 120 / max(1, thr)))
        elif action_id == 2:  # Universal Zoom (Ctrl + Wheel)
            self.press_key(VK_CONTROL)
            self.scroll_vertical(120 if delta > 0 else -120)
            self.release_key(VK_CONTROL)
        elif action_id == 3:  # Turbo 4x Speed
            self.scroll_vertical(int(delta * 480 / max(1, thr)))
        elif action_id == 4:  # Timeline Scrub (Shift + Left/Right)
            self.press_key(VK_SHIFT)
            self.tap_key(VK_RIGHT if delta > 0 else VK_LEFT, extended=True)
            self.release_key(VK_SHIFT)
        elif action_id == 5:  # Volume (CW = Up, CCW = Down)
            self.tap_key(VK_VOLUME_UP if delta > 0 else VK_VOLUME_DOWN, extended=True)
        elif action_id == 6:  # App Switcher Clutch (Alt + Tab / Shift+Tab)
            if not self.alt_held:
                self.press_key(VK_MENU)
                self.alt_held = True
            self.tspin_acc += delta
            while self.tspin_acc >= thr:
                self.tap_key(VK_TAB)
                self.tspin_acc -= thr
            while self.tspin_acc <= -thr:
                self.press_key(VK_SHIFT)
                self.tap_key(VK_TAB)
                self.release_key(VK_SHIFT)
                self.tspin_acc += thr

    def release_alt_clutch(self):
        """Releases Alt clutch key and commits the selected window."""
        if self.alt_held:
            self.release_key(VK_MENU)
            self.alt_held = False
            self.tspin_acc = 0

    def dispatch_mode_motion(self, mode_name: str, delta: int, thr: int, is_high_res=True):
        """Translates motion delta in the context of the active mode."""
        direction = 1 if delta > 0 else -1

        if mode_name == "SCROLL":
            if is_high_res:
                # Microsoft High-Res Scrolling: 120 units per full detent notch
                # delta raw counts mapped to sub-ticks
                sub_ticks = int(delta * 120 / max(1, thr))
                if sub_ticks != 0:
                    self.scroll_vertical(sub_ticks)
            else:
                self.accumulation += delta
                while self.accumulation >= thr:
                    self.scroll_vertical(120)
                    self.accumulation -= thr
                while self.accumulation <= -thr:
                    self.scroll_vertical(-120)
                    self.accumulation += thr

        elif mode_name == "H_SCROLL":
            if is_high_res:
                sub_ticks = int(delta * 120 / max(1, thr))
                if sub_ticks != 0:
                    self.scroll_horizontal(sub_ticks)
            else:
                self.accumulation += delta
                while self.accumulation >= thr:
                    self.scroll_horizontal(120)
                    self.accumulation -= thr
                while self.accumulation <= -thr:
                    self.scroll_horizontal(-120)
                    self.accumulation += thr

        elif mode_name == "VOLUME":
            self.accumulation += delta
            while self.accumulation >= thr:
                self.tap_key(VK_VOLUME_UP, extended=True)
                self.accumulation -= thr
            while self.accumulation <= -thr:
                self.tap_key(VK_VOLUME_DOWN, extended=True)
                self.accumulation += thr

        elif mode_name == "TIMELINE":
            self.accumulation += delta
            while self.accumulation >= thr:
                self.tap_key(VK_RIGHT, extended=True)
                self.accumulation -= thr
            while self.accumulation <= -thr:
                self.tap_key(VK_LEFT, extended=True)
                self.accumulation += thr

        elif mode_name == "ZOOM":
            self.accumulation += delta
            while self.accumulation >= thr:
                self.press_key(VK_CONTROL)
                self.scroll_vertical(120)
                self.release_key(VK_CONTROL)
                self.accumulation -= thr
            while self.accumulation <= -thr:
                self.press_key(VK_CONTROL)
                self.scroll_vertical(-120)
                self.release_key(VK_CONTROL)
                self.accumulation += thr

        elif mode_name == "TABBING":
            self.accumulation += delta
            while self.accumulation >= thr:
                self.tap_combo([VK_CONTROL, VK_TAB])
                self.accumulation -= thr
            while self.accumulation <= -thr:
                self.tap_combo([VK_CONTROL, VK_SHIFT, VK_TAB])
                self.accumulation += thr

        elif mode_name == "UNDO_REDO":
            self.accumulation += delta
            while self.accumulation >= thr:
                self.tap_combo([VK_CONTROL, VK_SHIFT, VK_Z]) # Redo
                self.accumulation -= thr
            while self.accumulation <= -thr:
                self.tap_combo([VK_CONTROL, VK_Z])           # Undo
                self.accumulation += thr
