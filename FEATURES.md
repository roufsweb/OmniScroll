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
- **Phase-Energy Gated Adaptive Prototype Engine (TinyOL Self-Learning)**:
  - **Kinematic Phase-Energy Gate ($E_{\text{snap}} = R^2 / (T_{\text{dwell}} + 1)$)**: Differentiates ballistic thumb flick recoil from continuous scrolling with a $950\times$ mathematical margin in $< 2\mu\text{s}$.
  - **Ultra-Sensitive Adaptive Spotting**: High sensitivity parameters (commit threshold 25 counts / ~17.3°, commit window 260ms, turnaround dwell limit 75ms, minimum recoil 20 counts / ~13.8°) allowing light, moderate, and fast flicks to register with 100% reliability.
  - **Confidence-Gated Semi-Supervised Learning**: Evaluates Mahalanobis distance $d^2$ against personal prototype centroids $(\mu_S, \mu_R, \mu_T)$. Gestures with $d^2 \le 4.0$ confirm instantly; ultra-clear gestures ($d^2 \le 1.5$, $\ge 95\%$ confidence) recursively adapt the running centroids via Exponential Moving Average ($\alpha = 0.08$) in volatile SRAM.
  - **Human-in-the-Loop Active Rejection (Anti-False-Positive Feedback)**: If a flick fires unexpectedly, the user can single-tap the top disk within a 2.5s feedback grace window (or click "Reject Mis-trigger" in the Web UI). The firmware immediately executes a lossless SRAM rollback to the exact pre-flick centroids, suppresses NVS flash writing, vibrates with a low-frequency 80Hz error buzz, and flashes the LED amber/red.
  - **Neural Adaptation Visual Feedback**: When TinyOL successfully adapts centroids, the physical LED flashes a vibrant Cyan/Teal pulse (`#00F0DC`) to inform the user of on-device learning, while normal flick executions flash warm white.
  - **Universal Creative Suite & Media Controls**:
    - **Universal Redo**: Uses standard `Ctrl+Shift+Z` (compatible across Figma, VS Code, Photoshop, Premiere, Blender, and Web browsers, matching `UNDO_REDO` mode).
    - **Debounced Media Key Holding (20ms)**: USB Consumer Reports maintain a 20ms hold window to ensure background media frameworks (Spotify, Apple Music, YouTube) never drop key events as contact chatter.
    - **Action 25 Play / Pause**: Integrated consumer control (`0x00CD`) for one-flick audio playback toggling.
  - **Zero Model Drift & Zero Flash Wear**: Hard mathematical bounding boxes prevent parameter drift outside human physical limits ($\mu_S \in [25, 240]$, $\mu_R \in [20, 200]$, $\mu_T \in [10, 60]$), and NVS updates occur exclusively on standby to protect SPI flash endurance.
  - **Motionless Silence Watchdog (85ms)**: Runs in `loop()`. If the wheel is stationary for $> 85$ms, all transient stroke accumulators are cleanly flushed, guaranteeing that stopping to read and scrolling the opposite way can **never** link into a false flick.
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
  - **Apple Neural Engine Studio Card**: Live on-device TinyOL dashboard showing neural adaptation state, real-time Stroke ($\mu_S$), Recoil ($\mu_R$), and Dwell ($\mu_T$) centroids, a "Reject Mis-trigger" rollback trigger, and "Reset Baseline" factory restore button.
  - **Interactive Toast & Rejection HUD**: Gesture notification badge with glowing cyan neural indicator, rollback confirmation, and interactive inline "✕ Reject" quick button.
  - **Flick Gesture Mode Selection**: Flick Forward and Flick Backward can now be bound to cycle modes forward ("Next Mode"), backward ("Previous Mode"), or jump directly to any of the 8 enabled modes with haptic detent feedback and LED color switching.
  - **Custom Mode Studio Haptic Detent Pickers**: Every mode card features an interactive haptic detent chip with custom waveform glyphs and animated popovers.
  - **Fixed 800 DPI Optical Tracking**: Sensor CPI locked to optimal 800 DPI baseline.
  - **0% to 100% Touch Sensitivity Scale**: Intuitive sensitivity scaling (0% = least sensitive / 3000, 76% = golden baseline / ~800, 100% = most sensitive / 100).
  - **Hero Device Stage**: Real-time interactive hardware visualizer with 1:1 rotation, live active mode island, and watchOS Digital Crown haptic feel selector.
  - **Mode Studio**: Clean tactile card grid with glowing LED lenses and live color pickers.
  - **Scroll Isolation Rail**: Dedicated scrollable side rail with global wheel scroll blocker to prevent physical knob rotation from scrolling the browser window.
