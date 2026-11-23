#!/usr/bin/env python3
"""
OmniScroll — "Scrub & Commit" Multi-Window Multitasking Lab Runner
Provides a floating glassmorphic horizontal app deck that pops up when you touch
and scrub, smoothly highlighting open applications with ZERO screen flicker,
and cleanly brings the chosen app to front the moment you lift your finger.
"""

import sys
import os
import time
import threading
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk

try:
    import serial
    import serial.tools.list_ports
    HAVE_SERIAL = True
except ImportError:
    HAVE_SERIAL = False

# =============================================================================
# Win32 API Window Enumeration & Activation
# =============================================================================
user32 = ctypes.windll.user32
WM_MOUSEWHEEL = 0x020A
SW_RESTORE = 9

def get_open_windows():
    """Scans and returns all visible, switchable top-level desktop applications."""
    windows = []
    def enum_cb(hwnd, extra):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                # Exclude system/tray/overlay windows
                if w > 250 and h > 200:
                    ignore_titles = ["Program Manager", "Settings", "Windows Input Experience", "OmniScroll App Deck"]
                    if not any(ign in title for ign in ignore_titles):
                        windows.append({
                            "hwnd": hwnd,
                            "title": title,
                            "rect": (rect.left, rect.top, w, h)
                        })
        return True
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(EnumWindowsProc(enum_cb), 0)
    return windows

def focus_window(hwnd):
    """Gracefully activates and raises a window to the top."""
    try:
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
    except Exception as e:
        print(f"Error focusing window: {e}")

def post_mouse_wheel(hwnd, delta):
    w_param = (int(delta) & 0xFFFF) << 16
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    l_param = (pt.y << 16) | (pt.x & 0xFFFF)
    user32.PostMessageW(hwnd, WM_MOUSEWHEEL, w_param, l_param)


# =============================================================================
# Floating Glassmorphic App Deck (The "Scrub & Commit" Carousel UI)
# =============================================================================
class AppDeckOverlay(tk.Toplevel):
    """Floating borderless horizontal ribbon displaying application cards."""
    def __init__(self, master):
        super().__init__(master)
        self.title("OmniScroll App Deck")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#121214")

        self.windows = []
        self.selected_idx = 0
        self.cards = []

        self.main_container = tk.Frame(self, bg="#18181C", padx=16, pady=12, highlightthickness=2, highlightbackground="#00F0DC")
        self.main_container.pack(fill=tk.BOTH, expand=True)

        header_frame = tk.Frame(self.main_container, bg="#18181C")
        header_frame.pack(fill=tk.X, pady=(0, 8))

        lbl_title = tk.Label(header_frame, text="OMNISCROLL APP CAROUSEL", font=("Segoe UI", 9, "bold"), fg="#00F0DC", bg="#18181C")
        lbl_title.pack(side=tk.LEFT)

        lbl_hint = tk.Label(header_frame, text="Rotate: Scrub Left/Right | Lift Finger: Switch", font=("Segoe UI", 8.5), fg="#8E8E93", bg="#18181C")
        lbl_hint.pack(side=tk.RIGHT)

        self.cards_frame = tk.Frame(self.main_container, bg="#18181C")
        self.cards_frame.pack(fill=tk.X)

        self.withdraw()

    def show_deck(self, window_list):
        self.windows = window_list if window_list else [
            {"hwnd": 0, "title": "Editor / VS Code", "rect": (0,0,0,0)},
            {"hwnd": 0, "title": "Browser / Chrome", "rect": (0,0,0,0)},
            {"hwnd": 0, "title": "Terminal / PowerShell", "rect": (0,0,0,0)},
            {"hwnd": 0, "title": "Documentation Spec", "rect": (0,0,0,0)}
        ]
        self.selected_idx = 0
        self._rebuild_cards()

        # Center horizontally at the bottom of the screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        deck_w = min(max(len(self.windows) * 170 + 40, 500), screen_w - 80)
        deck_h = 130
        x = (screen_w - deck_w) // 2
        y = screen_h - deck_h - 70

        self.geometry(f"{deck_w}x{deck_h}+{x}+{y}")
        self.deiconify()
        self.lift()

    def _rebuild_cards(self):
        for c in self.cards_frame.winfo_children():
            c.destroy()
        self.cards = []

        colors = ["#007AFF", "#30D158", "#FFA000", "#AF52DE", "#FF2D55", "#5856D6"]
        for idx, win in enumerate(self.windows):
            card_color = colors[idx % len(colors)]
            is_active = (idx == self.selected_idx)

            card = tk.Frame(
                self.cards_frame,
                bg="#24242A" if not is_active else "#2C2C34",
                highlightthickness=2,
                highlightbackground=card_color if is_active else "#333338",
                padx=10, pady=8, width=160, height=72
            )
            card.pack_propagate(False)
            card.pack(side=tk.LEFT, padx=5)

            # Badge pill
            badge_text = win["title"][:2].upper() if win["title"] else "AP"
            badge = tk.Label(card, text=badge_text, font=("Segoe UI", 9, "bold"), fg="#FFF", bg=card_color, padx=6, pady=2)
            badge.pack(anchor="w")

            # Title
            title_text = win["title"] if len(win["title"]) < 20 else win["title"][:18] + "..."
            lbl = tk.Label(card, text=title_text, font=("Segoe UI", 9, "bold" if is_active else "normal"),
                           fg="#FFFFFF" if is_active else "#A1A1A6", bg="#24242A" if not is_active else "#2C2C34")
            lbl.pack(anchor="w", pady=(4, 0))

            self.cards.append((card, lbl, card_color))

    def step_next(self):
        if not self.windows:
            return
        self.selected_idx = (self.selected_idx + 1) % len(self.windows)
        self._update_highlight()

    def step_prev(self):
        if not self.windows:
            return
        self.selected_idx = (self.selected_idx - 1) % len(self.windows)
        self._update_highlight()

    def _update_highlight(self):
        for idx, (card, lbl, color) in enumerate(self.cards):
            is_active = (idx == self.selected_idx)
            card.configure(
                bg="#2C2C34" if is_active else "#24242A",
                highlightbackground=color if is_active else "#333338"
            )
            lbl.configure(
                fg="#FFFFFF" if is_active else "#A1A1A6",
                bg="#2C2C34" if is_active else "#24242A",
                font=("Segoe UI", 9, "bold" if is_active else "normal")
            )

    def get_selected_hwnd(self):
        if self.windows and 0 <= self.selected_idx < len(self.windows):
            return self.windows[self.selected_idx]["hwnd"]
        return None

    def hide_deck(self):
        self.withdraw()


# =============================================================================
# Main Lab Control Application
# =============================================================================
class MultiWindowLabApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OmniScroll — Scrub & Commit Multitasking Lab")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(bg="#141416")

        self.ser = None
        self.running = True

        self.overlay = AppDeckOverlay(self)
        self.build_ui()
        self.lift()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))
        self.focus_force()
        self.start_serial_monitor()

    def build_ui(self):
        # 1. Header Bar
        header = tk.Frame(self, bg="#1E1E22", height=60)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        title = tk.Label(header, text="OmniScroll Multi-Window Lab", font=("Segoe UI", 13, "bold"), fg="#FFF", bg="#1E1E22")
        title.pack(side=tk.LEFT, padx=16, pady=12)

        self.lbl_port = tk.Label(header, text="Scanning COM ports...", font=("Segoe UI", 9.5), fg="#8E8E93", bg="#1E1E22")
        self.lbl_port.pack(side=tk.LEFT, padx=8)

        self.lbl_status_pill = tk.Label(header, text="Carousel Ready (Touch + Turn)", font=("Segoe UI", 9.5, "bold"),
                                        fg="#00F0DC", bg="#1E282A", padx=12, pady=4, highlightthickness=1, highlightbackground="#00F0DC")
        self.lbl_status_pill.pack(side=tk.RIGHT, padx=16)

        # 2. Instruction Strip
        sub = tk.Frame(self, bg="#242428", height=36)
        sub.pack(fill=tk.X, side=tk.TOP)
        sub.pack_propagate(False)

        lbl_instruct = tk.Label(
            sub,
            text="HOW TO TEST: 1. Rest finger on top disk & turn knob -> Carousel ribbon appears | 2. Turn Left/Right to scrub | 3. Lift finger to commit!",
            font=("Segoe UI", 9), fg="#E5E5EA", bg="#242428"
        )
        lbl_instruct.pack(side=tk.LEFT, padx=16, pady=8)

        # Manual test buttons for testing with mouse/keyboard
        btn_start = tk.Button(sub, text="Simulate Touch+Turn", command=self.on_carousel_start,
                              font=("Segoe UI", 8, "bold"), bg="#3A3A3C", fg="#FFF", relief=tk.FLAT, padx=6)
        btn_start.pack(side=tk.RIGHT, padx=6, pady=4)

        btn_next = tk.Button(sub, text="Next (CW)", command=self.on_carousel_step_next,
                             font=("Segoe UI", 8), bg="#2C2C2E", fg="#FFF", relief=tk.FLAT, padx=6)
        btn_next.pack(side=tk.RIGHT, padx=4, pady=4)

        btn_commit = tk.Button(sub, text="Lift Finger (Commit)", command=self.on_carousel_commit,
                               font=("Segoe UI", 8, "bold"), bg="#007AFF", fg="#FFF", relief=tk.FLAT, padx=6)
        btn_commit.pack(side=tk.RIGHT, padx=6, pady=4)

        # 3. Split-Screen Document Panes (Main vs Reference)
        panes = tk.Frame(self, bg="#141416")
        panes.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # Pane A
        self.frame_a = tk.Frame(panes, bg="#1C1C1E", highlightthickness=2, highlightbackground="#00F0DC")
        self.frame_a.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        lbl_a = tk.Label(self.frame_a, text="◀ Work Document A (Source Code)", font=("Segoe UI", 10.5, "bold"), fg="#00F0DC", bg="#1C1C1E")
        lbl_a.pack(anchor="w", padx=10, pady=8)

        self.txt_a = tk.Text(self.frame_a, bg="#141416", fg="#D1D1D6", font=("Consolas", 10), relief=tk.FLAT, padx=8, pady=8)
        self.txt_a.pack(fill=tk.BOTH, expand=True)

        # Pane B
        self.frame_b = tk.Frame(panes, bg="#1C1C1E", highlightthickness=2, highlightbackground="#3A3A3C")
        self.frame_b.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        lbl_b = tk.Label(self.frame_b, text="▶ Reference Document B (API Specs)", font=("Segoe UI", 10.5, "bold"), fg="#FFA000", bg="#1C1C1E")
        lbl_b.pack(anchor="w", padx=10, pady=8)

        self.txt_b = tk.Text(self.frame_b, bg="#141416", fg="#D1D1D6", font=("Segoe UI", 9.5), relief=tk.FLAT, padx=8, pady=8)
        self.txt_b.pack(fill=tk.BOTH, expand=True)

        for i in range(1, 151):
            self.txt_a.insert(tk.END, f"{i:03d} | fn handle_carousel_scrub(step: i32) -> Result<()> {{\n")
            self.txt_a.insert(tk.END, f"    |     // Card notch index: {i} | Tactile click: 240 Hz\n")
            self.txt_a.insert(tk.END, f"    |     overlay.step(step);\n    | }}\n")

            self.txt_b.insert(tk.END, f"Section {i}.0: Multi-Window Architectural Specification\n")
            self.txt_b.insert(tk.END, f"  • Smooth 60fps card scrub without background focus stealing.\n\n")

        # 4. Footer Telemetry
        footer = tk.Frame(self, bg="#1E1E22", height=32)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        self.lbl_telemetry = tk.Label(footer, text="Telemetry: Ready | Touch: Released | Wheel: Idle", font=("Consolas", 9), fg="#8E8E93", bg="#1E1E22")
        self.lbl_telemetry.pack(side=tk.LEFT, padx=16)

    # =========================================================================
    # Carousel Event Handlers
    # =========================================================================
    def on_carousel_start(self):
        windows = get_open_windows()
        self.overlay.show_deck(windows)
        self.lbl_status_pill.configure(text="Deck Active (Scrubbing...)", fg="#00F0DC")

    def on_carousel_step_next(self):
        self.overlay.step_next()

    def on_carousel_step_prev(self):
        self.overlay.step_prev()

    def on_carousel_commit(self):
        hwnd = self.overlay.get_selected_hwnd()
        self.overlay.hide_deck()
        self.lbl_status_pill.configure(text="Committed & Switched", fg="#30D158")
        if hwnd:
            focus_window(hwnd)

    # =========================================================================
    # Serial Port Background Listener
    # =========================================================================
    def start_serial_monitor(self):
        t = threading.Thread(target=self._serial_worker, daemon=True)
        t.start()

    def _serial_worker(self):
        while self.running:
            if not self.ser or not self.ser.is_open:
                port = self._find_port()
                if port:
                    try:
                        self.ser = serial.Serial(port, 115200, timeout=0.1)
                        self.ser.dtr = True
                        self.ser.rts = True
                        time.sleep(0.1)
                        self.ser.reset_input_buffer()
                        self.lbl_port.configure(text=f"Connected: {port} (DTR/RTS Active)", fg="#30D158")
                    except Exception:
                        self.ser = None
                        time.sleep(1)
                else:
                    self.lbl_port.configure(text="Waiting for OmniScroll...", fg="#8E8E93")
                    time.sleep(1.5)
                    continue

            try:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    self.after(0, self._process_line, line)
            except Exception:
                if self.ser:
                    try: self.ser.close()
                    except: pass
                self.ser = None
                time.sleep(1)

    def _find_port(self):
        if not HAVE_SERIAL:
            return None
        for p in serial.tools.list_ports.comports():
            hwid = str(p.hwid).upper()
            if "303A" in hwid or p.vid == 0x303A:
                return p.device
        return None

    def _process_line(self, line):
        self.lbl_telemetry.configure(text=f"Telemetry: {line}")

        if line == "CAROUSEL:START":
            self.on_carousel_start()
        elif line == "CAROUSEL:STEP:1":
            self.on_carousel_step_next()
        elif line == "CAROUSEL:STEP:-1":
            self.on_carousel_step_prev()
        elif line == "CAROUSEL:COMMIT":
            self.on_carousel_commit()
        elif line.startswith("ACTION:SNAP:RIGHT"):
            self.frame_a.configure(highlightbackground="#3A3A3C")
            self.frame_b.configure(highlightbackground="#00F0DC")
            self.txt_b.focus_set()
        elif line.startswith("ACTION:SNAP:LEFT"):
            self.frame_a.configure(highlightbackground="#00F0DC")
            self.frame_b.configure(highlightbackground="#3A3A3C")
            self.txt_a.focus_set()
        elif line.startswith("ACTION:DUAL_SCROLL:DOWN"):
            self.txt_a.yview_scroll(3, "units")
            self.txt_b.yview_scroll(3, "units")
        elif line.startswith("ACTION:DUAL_SCROLL:UP"):
            self.txt_a.yview_scroll(-3, "units")
            self.txt_b.yview_scroll(-3, "units")


if __name__ == "__main__":
    app = MultiWindowLabApp()
    app.mainloop()
