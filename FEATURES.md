# OmniScroll — Features

## Hardware Features
- **Optical Bearing Dial**: A freely spinning ball bearing is used as the main rotary interface, allowing for frictionless, infinite scrolling with zero mechanical wear.
- **Optical Surface Tracking**: An MX8650 optical mouse sensor reads the surface texture of the spinning bearing, translating physical rotation into high-resolution counts (~520 counts per 360° revolution, ~0.6923° per count).
- **Solid-State Capacitive Touch**: Native ESP32-S2 capacitive touch sensing on GPIO 12 with hardware filtering and double-tap detection for instantaneous mode switching.
- **Precision LRA Haptics**: An iPhone 6 Linear Resonant Actuator driven by a PAM8403 amplifier provides crisp, software-defined virtual detents and confirmation clicks with 5 distinct haptic profiles.
- **Hardware RGB LEDC PWM**: The 5050 RGB LED is driven using native ESP32 Core v3 LEDC hardware PWM timers (5 kHz, 8-bit) for 100% max PWM output, ensuring pure color separation, flicker-free operation, and zero color bleed across modes.

## Software Architecture & Firmware Features
- **8 Dynamic Configurable Modes**:
  - `SCROLL`: Standard vertical page scrolling with continuous sub-pixel smoothing.
  - `VOLUME`: System media volume control with gentle detents.
  - `TIMELINE`: Horizontal video editing scrubbing (Left/Right arrow keys).
  - `ZOOM`: Ctrl + Scroll wheel zooming for canvas, design, and CAD applications.
  - `H_SCROLL`: Native AC Pan / Horizontal scrolling axis.
  - `BRIGHTNESS`: System display brightness keys.
  - `TABBING`: Ctrl + Tab browser tab switching.
  - `UNDO_REDO`: Ctrl + Z / Ctrl + Shift + Z rapid undo/redo scrubbing.
- **Native Windows High-Resolution Smooth Scrolling**:
  - Implements Microsoft & USB-IF compliant High-Resolution Scrolling using Generic Desktop Usage `0x48` (Resolution Multiplier).
  - Groups the Resolution Multiplier Feature Report inside a Logical Collection alongside Vertical Wheel and AC Pan.
  - Automatically streams fractional sub-ticks ($120/\text{threshold}$) on raw optical counts when high-res is negotiated by Windows `mouhid.sys`, with remainder accumulator to avoid drift.
  - Fires crisp haptic detent clicks synchronously at full detent intervals (`threshold` counts) with automatic legacy fallback.
- **Host Connection & Organic Standby Breathing**:
  - Hardware-level TinyUSB host detection (`tud_mounted() && !tud_suspended()`).
  - When disconnected or in PC sleep, the LED breathes in Apple MagSafe Amber (`#FFA000`) following an organic resting respiratory curve (~4.5s cycle) with Gamma 2.8 perceptual correction.
  - Smooth 450ms cubic cross-fade into active mode color upon PC host connection with haptic confirmation.
  - Haptic detents remain responsive even while disconnected so the knob never feels dead.
- **Touch & Spin Hold Gate & Disambiguation**:
  - Requires continuous touch contact for $\ge 180$ms before arming Touch & Spin modifier actions (Zoom, Timeline Scrub, Horizontal Scroll, Turbo 4x, Volume).
  - Quick finger taps (< 180ms) are 100% immune from triggering Touch & Spin, resolving any conflict with double-tap mode switching.
  - The instant the wheel is rotated while touching (`dx != 0`), double-tap and long-press mode switches are locked out for the entire touch session.
  - Lifting the finger instantly deactivates Touch & Spin and flushes pending touch states so finger release never accidentally triggers a mode change.
- **Physical-Calibrated 5-Guard Flick Gesture Engine**:
  - Spotting $\rightarrow$ Velocity Burst $\rightarrow$ Sharp Directional Snap-Back Reversal classification engine derived directly from 30-second physical hardware telemetry (3,577 data points).
  - **Guard 1 (Continuous Scroll Ceiling, 230 counts & 180ms window)**: Automatically aborts to IDLE if wheel rotation exceeds 230 counts ($\sim 159^\circ$) or takes longer than 180ms, completely preventing continuous fast scrolling down a long page from priming a gesture.
  - **Guard 2 (Motionless Silence Watchdog, 80ms)**: Actively runs in `loop()` whenever the wheel is stationary. If the wheel stops for $> 80$ms, the entire gesture engine cleanly resets to IDLE. Guarantees that scrolling in one direction, stopping to read, and scrolling in the opposite direction can **NEVER** link up into an accidental flick gesture.
  - **Guard 3 (Turnaround Dwell Limit & Jitter Recovery, 50ms)**: Requires the directional snap-back recoil to initiate within $\le 50$ms of stroke peak. If forward motion resumes after any micro-jitter, the reversal state is instantly cleared.
  - **Guard 4 (Recoil Magnitude Bounds & Duration Ceiling, 35 to 220 counts in $\le 160$ms)**: Reversal must achieve at least 35 counts ($\sim 24.2^\circ$) within $\le 160$ms. Slow reverse rolling or resting bounce ($\le 10$ counts) is rejected.
  - **Guard 5 (Symmetrical Recoil Ratio, $\ge 1/3$)**: Requires `reversal >= travel / 3`. In real thumb flicks, elastic recoil is $64\%\text{--}126\%$ of stroke travel. In normal scrolling, reverse counts are $\le 3\%$, physically barring directional reversals from mis-triggering.
  - Delivers **100% true flick recognition** with **0% false positives** during normal scrolling, stopping, or reversing direction.
- **Full Non-Volatile Storage (NVS) Persistence**:
  - All per-mode parameters (enabled, RGB color, haptic profile, direction invert, threshold).
  - Hardware RGB white-balance calibration constants (`cal_R`, `cal_G`, `cal_B`).
  - Global preferences: Idle sleep timeout (`idle_ms`), master LED brightness (`bri`), Touch & Spin action (`tspin_act`), and optical sensor CPI (`cpi`).
  - Settings survive power cycles and USB re-plugs completely.

## Web Control Panel (Web Serial API)
- **Zero-Install Client-Side Configurator**: Hosted on GitHub Pages ([roufsweb.github.io/OmniScroll](https://roufsweb.github.io/OmniScroll/)) and communicates directly via Web Serial API (`USBCDC`).
- **Apple Pro HIG & Nordic Walnut Craftsmanship**:
  - **4 Handcrafted Themes**: Nordic Walnut (with procedural organic wood grain, default), Obsidian Dark, Precision Aluminum, and Apple Watch Ultra Titanium.
  - **Continuous Capsule Sliders & Custom Glassmorphism Pickers**: Studio Controls capsule rows with dynamic fill sliders (LED Brightness, Idle Sleep, Touch Sensitivity) and bespoke Apple-grade custom glassmorphic dropdown popovers (Flick Forward, Flick Back, Touch & Spin) featuring custom SVG icons, shortcut badges, active checkmarks, and theme-adaptive styling—zero ugly native browser selects. Elevated CSS stacking hierarchy (`z-index: 5000`) and parent-card elevation ensures dropdowns always float seamlessly over the Mode Studio card without clipping.
  - **Flick Gesture Mode Selection**: Flick Forward and Flick Backward can now be bound to cycle modes forward ("Next Mode"), backward ("Previous Mode"), or jump directly to any of the 8 enabled modes with haptic detent feedback and LED color switching.
  - **Custom Mode Studio Haptic Detent Pickers**: Every mode card features an interactive haptic detent chip with custom waveform glyphs and animated popovers.
  - **Fixed 800 DPI Optical Tracking**: Sensor CPI locked to optimal 800 DPI baseline.
  - **0% to 100% Touch Sensitivity Scale**: Intuitive sensitivity scaling (0% = least sensitive / 3000, 76% = golden baseline / ~800, 100% = most sensitive / 100).
  - **Hero Device Stage**: Real-time interactive hardware visualizer with 1:1 rotation, live active mode island, and watchOS Digital Crown haptic feel selector.
  - **Mode Studio**: Clean tactile card grid with glowing LED lenses and live color pickers.
  - **Scroll Isolation Rail**: Dedicated scrollable side rail with global wheel scroll blocker to prevent physical knob rotation from scrolling the browser window.
