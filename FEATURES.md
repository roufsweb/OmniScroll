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
- **Full Non-Volatile Storage (NVS) Persistence**:
  - All per-mode parameters (enabled, RGB color, haptic profile, direction invert, threshold).
  - Hardware RGB white-balance calibration constants (`cal_R`, `cal_G`, `cal_B`).
  - Global preferences: Idle sleep timeout (`idle_ms`), master LED brightness (`bri`), and optical sensor CPI (`cpi`).
  - Settings survive power cycles and USB re-plugs completely.

## Web Control Panel (Web Serial API)
- **Zero-Install Client-Side Configurator**: Hosted on GitHub Pages ([roufsweb.github.io/OmniScroll](https://roufsweb.github.io/OmniScroll/)) and communicates directly via Web Serial API (`USBCDC`).
- **Apple Pro HIG & Nordic Walnut Craftsmanship**:
  - **4 Handcrafted Themes**: Nordic Walnut (with procedural organic wood grain, default), Obsidian Dark, Precision Aluminum, and Apple Watch Ultra Titanium.
  - **Continuous Capsule Sliders**: Control Center style capsule sliders with dynamic fill, Apple/Google tactile floating pill indicator, and instant commit on drag release.
  - **0% to 100% Touch Sensitivity Scale**: Intuitive sensitivity scaling (0% = least sensitive / 3000, 76% = golden baseline / ~800, 100% = most sensitive / 100).
  - **Hero Device Stage**: Real-time interactive hardware visualizer with 1:1 rotation, live active mode island, and watchOS Digital Crown haptic feel selector.
  - **Mode Studio**: Tactile card grid with glowing LED lenses and live color pickers.
  - **Scroll Isolation Rail**: Dedicated scrollable side rail with global wheel scroll blocker to prevent physical knob rotation from scrolling the browser window.
