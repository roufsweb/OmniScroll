# OmniScroll — Multi-Window Multitasking Lab

This folder provides an **isolated prototype sandbox** to test and experience the multi-window multitasking navigation paradigms before merging them into the main codebase.

None of the files in this directory alter, touch, or affect the main firmware (`OmniScroll.ino`), the desktop app (`desktop_app/`), or the Rust workspace (`omniscroll-rs/`).

---

## 1. What's Inside

| File | Purpose |
|---|---|
| [`firmware/multi_window_firmware.ino`](file:///e:/rouf/hardware-project/OmniScroll/experiments/multi_window_lab/firmware/multi_window_firmware.ino) | Minimal test firmware with MX8650 tracking, LRA haptic detents, double-tap middle selection, and LED feedback. |
| [`pc_lab_runner.py`](file:///e:/rouf/hardware-project/OmniScroll/experiments/multi_window_lab/pc_lab_runner.py) | Interactive Windows GUI lab featuring split-screen test panes AND real Windows OS Win32 hooks. |
| [`upload_lab.py`](file:///e:/rouf/hardware-project/OmniScroll/experiments/multi_window_lab/upload_lab.py) | Dedicated uploader script for flashing the lab firmware without touching `upload.py`. |

---

## 2. The 4 Multi-Window Paradigms

Double-tap the **top capacitive touch plate in the middle** to cycle between modes:

### Mode 0: App Carousel (Rotary Alt+Tab)
* **LED Color:** Vibrant Blue (`#007AFF`)
* **Haptics:** Crisp tactile click per open application.
* **Behavior:** Rotating the knob cycles through open windows. Releasing or tapping focuses that window.

### Mode 1: Spatial Snap (Left $\leftrightarrow$ Right Split-Screen Focus)
* **LED Color:** Emerald Green (`#30D158`)
* **Haptics:** Solid detent bump.
* **Behavior:** Clockwise rotation instantly focuses the right-hand tiled window; counter-clockwise rotation focuses the left-hand tiled window.

### Mode 2: Dual Synchronous Multi-Scroll
* **LED Color:** Amber MagSafe (`#FFA000`)
* **Haptics:** Silky continuous ratchet clicks.
* **Behavior:** Rotating the knob scrolls **both documents/windows simultaneously in lockstep**, ideal for reading documentation alongside code or comparing diffs.

### Mode 3: Smart Hover-Scroll with Auto-Focus
* **LED Color:** Deep Purple (`#AF52DE`)
* **Haptics:** Gentle confirmation click.
* **Behavior:** Move your cursor over any window or pane, spin the wheel, and it is instantly focused and scrolled without clicking.

---

## 3. How to Run & Test

### Option A: Test with In-App Split-Screen Lab (No Flashing Required!)
You can test the interactive behavior right now in the GUI lab:
```powershell
python experiments\multi_window_lab\pc_lab_runner.py
```
* Use the **"Simulate Double-Tap"** button to cycle modes.
* If your OmniScroll is plugged in, turn the physical knob to control the split panes!
* Check **"Hook Real Windows OS"** to test with real applications (VS Code, Chrome, Terminal).

### Option B: Flash the Test Firmware to OmniScroll
If you want to flash the isolated test firmware to your physical knob:
```powershell
# 1. Verify compilation without flashing:
python experiments\multi_window_lab\upload_lab.py --compile-only

# 2. Flash to device:
python experiments\multi_window_lab\upload_lab.py
```

### Option C: Restore the Golden Release Firmware
Whenever you are finished testing, restoring your main firmware is 100% lossless:
```powershell
python upload.py --port COM26 --no-reset
```
*(Targets definitive Gold Release tag `v1.0.0`)*
