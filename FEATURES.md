# OmniScroll — Features & Roadmap

This document catalogs all functional capabilities of the OmniScroll project, tracking currently implemented features alongside active roadmap enhancements.

---

## 1. Implemented Features (Operational)

### Hardware & Mechanical Architecture
- [x] **Optical Bearing Dial**: A freely spinning ball bearing is used as the main rotary interface, allowing for frictionless, infinite scrolling with zero mechanical wear.
- [x] **Optical Surface Tracking**: An MX8650 optical mouse sensor reads the surface texture of the spinning bearing, translating physical rotation into high-resolution counts (~520 counts per 360° revolution, ~0.6923° per count).
- [x] **Solid-State Capacitive Touch**: Native ESP32-S2 capacitive touch sensing on GPIO 12 with hardware filtering and double-tap detection for instantaneous mode switching.
- [x] **Precision LRA Haptics**: An iPhone 6 Linear Resonant Actuator driven by a PAM8403 amplifier provides crisp, software-defined virtual detents and confirmation clicks with 5 distinct haptic profiles.
- [x] **Hardware RGB LEDC PWM**: The 5050 RGB LED is driven using native ESP32 Core v3 LEDC hardware PWM timers (5 kHz, 8-bit) for 100% max PWM output, ensuring pure color separation, flicker-free operation, and zero color bleed across modes.

### Firmware & Core Intelligence (`OmniScroll.ino`)
- [x] **8 Dynamic Configurable Modes**:
  - `SCROLL`: Standard vertical page scrolling with continuous sub-pixel smoothing.
  - `VOLUME`: System media volume control with gentle detents.
  - `TIMELINE`: Horizontal video editing scrubbing (Left/Right arrow keys).
  - `ZOOM`: Ctrl + Scroll wheel zooming for canvas, design, and CAD applications.
  - `H_SCROLL`: Native AC Pan / Horizontal scrolling axis.
  - `BRIGHTNESS`: System display brightness keys.
  - `TABBING`: Ctrl + Tab browser tab switching.
  - `UNDO_REDO`: Ctrl + Z / Ctrl + Shift + Z rapid undo/redo scrubbing.
- [x] **Native Windows High-Resolution Smooth Scrolling**:
  - Implements Microsoft & USB-IF compliant High-Resolution Scrolling using Generic Desktop Usage `0x48` (Resolution Multiplier).
  - Groups the Resolution Multiplier Feature Report inside a Logical Collection alongside Vertical Wheel and AC Pan (Report ID 11).
  - Automatically streams fractional sub-ticks ($120/\text{threshold}$) on raw optical counts when high-res is negotiated by Windows `mouhid.sys`, with remainder accumulator to avoid drift.
  - Fires crisp haptic detent clicks synchronously at full detent intervals (`threshold` counts) with automatic legacy fallback.
- [x] **Resting Anti-Jitter Gate & Stillness Detent Flusher**:
  - **Incomplete Detent Stillness Decay Flusher (200ms)**: When user scrolling stops, any uncompleted fractional detent in `accumulationX` and `subTickAcc` (e.g. 8 or 9 counts out of threshold 10) is automatically flushed to 0 after 200ms of stillness. Permanently eliminates the "one-step phantom scroll on the desk" caused by a single vibration count topping off a stale remainder.
  - **Resting Anti-Jitter Gate (80ms / 2-count window)**: When the knob is resting unattended on the desk (`isStationary` $> 150$ms and `!isPhysicallyTouched`), isolated 1-count noise ($|dx| = 1$) from desk vibrations (typing, bumping desk) or optical caustics on the polished steel ball bearing is held in an 80ms observation buffer. If no deliberate rotation follows, the noise decays to 0 with zero packets sent to Windows and zero wakeup from idle dimming.
  - **Zero-Loss Intentional Motion**: The instant intentional rotation begins, counts arrive in rapid succession ($< 20$ms), immediately unlocking the gate and dispatching all accumulated counts so zero movement or resolution is lost.
  - **Touch Contact Bypass**: Touching or resting a hand on the dial cap (`isPhysicallyTouched == true`) immediately bypasses the gate for 0ms ultra-low latency response.
- [x] **Host Connection & Organic Standby Breathing**:
  - Hardware-level TinyUSB host detection (`tud_mounted() && !tud_suspended()`).
  - When disconnected or in PC sleep, the LED breathes in Apple MagSafe Amber (`#FFA000`) following an organic resting respiratory curve (~4.5s cycle) with Gamma 2.8 perceptual correction.
  - Smooth 450ms cubic cross-fade into active mode color upon PC host connection with haptic confirmation.
  - Fully active precision controller on wall chargers: physical detents click, mode switches cycle with confirmation, and instant wake from amber breathing upon touch or rotation.
- [x] **Touch & Spin Hold Gate & Disambiguation**:
  - Requires continuous touch contact for $\ge 180$ms before arming Touch & Spin modifier actions (Zoom, Timeline Scrub, Horizontal Scroll, Turbo 4x, Volume, App Switcher).
  - Quick finger taps (< 180ms) are 100% immune from triggering Touch & Spin, resolving conflicts with double-tap mode switching.
  - The instant the wheel is rotated while touching (`dx != 0`), double-tap and long-press mode switches are locked out for the entire touch session.
  - Lifting the finger instantly deactivates Touch & Spin and flushes pending touch states so finger release never accidentally triggers a mode change.
  - **App Switcher Clutch (Action 6)**: Native Windows application switcher clutch (`Alt + Tab`). Engaging contact and rotating holds `Alt`, scrubs open window cards with detent feedback, shifts LED to Electric Cyan (`#00F0DC`), and releases `Alt` to commit the selected window upon finger release with a 320Hz confirmation tone. Fully supported across hardware USB HID, Web Serial UI, PySide6 desktop bridge, and Rust daemon.
- [x] **Configurable Single Tap Dial Cap Shortcut**:
  - By default assigned to TinyOL neural engine active rollback / mis-trigger rejection (rolling back centroids if tapped within the 2.5s feedback window).
  - Fully rebindable via Web UI and Serial API (`SET:SINGLE_TAP:<0-25, 99>`) to 25 system actions (Play/Pause, Next/Prev Mode, Direct Mode jumps, Browser Navigation, Undo/Redo) with NVS persistence (`stap_act`).
- [x] **Phase-Energy Gated Adaptive Prototype Engine (TinyOL Self-Learning)**:
  - **Kinematic Phase-Energy Gate ($E_{\text{snap}} = R^2 / (T_{\text{dwell}} + 1) \ge 20$)**: Differentiates ballistic thumb flick recoil from continuous scrolling with a $950\times$ mathematical margin in $< 2\mu\text{s}$.
  - **Ultra-Sensitive Adaptive Spotting**: High sensitivity parameters (commit threshold 25 counts, commit window 260ms, turnaround dwell limit 75ms, minimum recoil 20 counts) allowing light, moderate, and fast flicks to register with 100% reliability.
  - **Confidence-Gated Semi-Supervised Learning**: Evaluates Mahalanobis distance $d^2$ against personal prototype centroids. Gestures with $d^2 \le 4.0$ confirm instantly; ultra-clear gestures ($d^2 \le 1.5$) recursively adapt centroids via EMA ($\alpha = 0.08$) in volatile SRAM.
  - **Human-in-the-Loop Active Rejection (Anti-False-Positive Feedback)**: Single-tapping the top disk within a 2.5s feedback grace window (or clicking "Reject Mis-trigger" in the UI) triggers an immediate SRAM rollback to pre-flick centroids, suppresses flash writes, plays an 80Hz error buzz, and flashes the LED amber/red.
  - **Neural Adaptation Visual Feedback**: Adapting centroids flashes a vibrant Cyan/Teal pulse (`#00F0DC`), while standard flicks flash warm white.
  - **Universal Creative Suite & Media Controls**: Universal Redo (`Ctrl+Shift+Z`), 20ms debounced media key holding, and Action 25 Play/Pause (`0x00CD`).
  - **Motionless Silence Watchdog (85ms)**: Wheel stillness $> 85$ms cleanly flushes stroke accumulators, preventing direction changes from causing false flicks.
  - **100% Recognition & 0% False Positives**: Verified across 3,577-sample ground-truth dataset (`gesture_session_30s.csv`).
- [x] **Full Non-Volatile Storage (NVS) Persistence**:
  - All per-mode parameters (enabled, RGB color, haptic profile, direction invert, threshold).
  - Hardware RGB white-balance calibration constants (`cal_R`, `cal_G`, `cal_B`).
  - Global preferences: Idle sleep timeout (`idle_ms`), master LED brightness (`bri`), Touch & Spin action (`tspin_act`), Single Tap shortcut (`stap_act`), and optical sensor CPI (`cpi`).
- [x] **Dynamic Wi-Fi Power Modulation & Seamless Standby Handover**:
  - Automatically activates Wi-Fi modem sleep (`WiFi.setSleep(true)`) while wired via USB, cutting Wi-Fi power by ~80% (~20mA) while maintaining continuous AP association and 2.5s status heartbeats.
  - Automatically suppresses high-rate optical UDP streaming over Wi-Fi when USB is active, preventing network congestion and RF noise.
  - The instant USB is unplugged, modem sleep is disabled (`WiFi.setSleep(false)`) and high-rate sub-2ms UDP streaming resumes with $<10$ms zero-latency failover.

### Web Control Panel (Web Serial API — `docs/index.html`)
- [x] **Zero-Install Client-Side Configurator**: Communicates directly via Web Serial API (`USBCDC`) from the browser without drivers.
- [x] **Apple Pro HIG & Nordic Walnut Craftsmanship**:
  - 4 Handcrafted Themes: Nordic Walnut (procedural grain), Obsidian Dark, Precision Aluminum, Apple Watch Ultra Titanium.
  - Continuous Capsule Sliders and custom glassmorphic dropdown popovers (Flick Forward, Flick Back, Touch & Spin, Single Tap) with z-index elevation.
  - Progressive disclosure Advanced Settings pane unifying the Apple Neural Engine Studio Card and Hardware RGB Calibration.
  - Real-time interactive hardware stage visualizer with 1:1 rotation and watchOS Digital Crown haptic selector.
  - Full Google Search Central Schema.org JSON-LD structured data and rich snippet FAQ accordion.

### Wireless Multi-Transport & Desktop Bridge (Python Prototype)
- [x] **Zero-Latency Wi-Fi Streaming (RWP v2.1 / OMP)**: 9-byte binary UDP datagram protocol on Port 4211 with sub-2ms network latency over 2.4 GHz Wi-Fi.
- [x] **Win32 Virtual HID Bridge**: Uses `ctypes.windll.user32.SendInput` to inject high-res wheel sub-ticks, horizontal panning, and media keys.
- [x] **Smart Dual-Transport Router**: Seamless priority handover between physical USB cable and Wi-Fi UDP.
- [x] **Strict Hardware Whitelisting**: Strict filtering of Espressif `VID: 0x303A` / `PID: 0x4F5B` (`OMNI-007`), isolating all Bluetooth virtual COM links.
- [x] **Event-Driven Push Wake**: Passive desktop listener with zero-polling hardware wake push.

---

## 2. Roadmap & Upcoming Features (In Progress & Planned)

### High-Performance Rust Ecosystem (`omniscroll-rs`)
- [x] **Phase 1: Standardized Cargo Workspace Initialization**:
  - Set up `omniscroll-rs` workspace with standard naming convention:
    - **`OmniScroll`** (`OmniScroll.exe`): The flagship native desktop application & glassmorphic HUD.
    - **`omniscroll-cli`** (`omniscroll-cli.exe`): Standalone developer CLI for hardware detection, telemetry monitoring, and flashing.
    - **`omniscroll-core`**: Pure Rust shared `no_std` protocol and mathematics engine.
    - **`omniscroll-bridge`**: Win32 `SendInput` and dual-transport networking engine.
- [x] **`omniscroll-core` Shared Crate (`no_std`)**:
  - Zero-copy RWP v2.1 9-byte packet parser and bitwise XOR checksum validator.
  - High-res sub-tick remainder accumulator ($120/\text{threshold}$) with integer precision.
  - Core mode structures, action codes, Gamma 2.8 perceptual LUT, and TinyOL kinematic equations.
  - Verified with 100% passing unit tests.
- [x] **`omniscroll-bridge` Input & Transport Crate**:
  - Native Win32 `SendInput` driver using Microsoft's official `windows` crate (sub-microsecond injection, zero GIL overhead).
  - High-throughput asynchronous UDP streaming listener via `tokio` on Port 4211 with event broadcast channels.
  - USB CDC Serial auto-detection matching `VID: 0x303A` / `PID: 0x4F5B`.
  - Native Windows Wi-Fi network scanner via `WifiScanner` without spawning console windows.
  - Unified `TransportManager` routing bi-directional commands seamlessly across USB CDC and Wi-Fi UDP.
  - PING/PONG keepalive responder and push-wake event handler.
- [x] **`omniscroll-gui` Flagship Native Desktop Studio (`OmniScroll-Studio.exe`)**:
  - **Pure Native Rust & Slint 1.19**: Delivers the complete Nordic Walnut / Apple Pro HIG desktop experience in a lightweight, single-file native executable (`11.8 MB`).
  - **8-Mode Horizontal Selector Strip**: Quick-select buttons for all 8 modes (`SCROLL`, `VOLUME`, `TIMELINE`, `ZOOM`, `H_SCROLL`, `BRIGHTNESS`, `TABBING`, `UNDO_REDO`) with designated Apple accent colors.
  - **Photorealistic Rotary Dial Stage**: Real-time 360° crown visualizer with Apple MagSafe Amber dot (`#FFA000`), optical count angle reflection, and detent threshold sensitivity slider.
  - **Invert Direction & Auto-Start**: Per-mode rotation invert toggle and Windows auto-launch (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`) integration.
  - **Touch & Spin Modifier Studio Card**: Complete configuration for Action 6 (`App Switcher Alt+Tab Clutch`), Action 1 (`H-Scroll`), Action 2 (`Zoom`), and Action 0 (`Disabled`).
  - **Apple Neural Engine TinyOL Studio Card**: Real-time display of on-device adaptive centroids ($\mu_S$ Spotting, $\mu_R$ Snap Recoil, $\mu_T$ Dwell Turnaround) with 1-click "Reject Mis-trigger" and "Reset Baseline" buttons.
  - **Hardware White-Balance RGB Calibration**: Real-time calibration sliders for Red, Green, and Blue LED channels.
  - **Wi-Fi Scanner & Credential Provisioning**: Discovers local 2.4 GHz networks via `WifiScanner`, displays signal strength, and dispatches credentials directly to ESP32 NVS over USB wire.
  - **Resource Embedding**: Embedded Windows application icon (`icon.ico`) and PE metadata (`winres`) with $<15$ MB RAM usage and $<400$ms instant startup.
- [x] **`OmniScroll` HUD (On-Screen Dial Overlay & Companion)**:
  - **Visual Dial Presence on Windows**: A sleek, translucent glassmorphic overlay (Windows dark Nordic Walnut / Obsidian aesthetic) that complements the physical knob's single RGB LED.
  - **Auto-Summon on Interaction**: Hidden when idle (0% CPU usage); the moment the wheel is spun or touched, it glides smoothly into view on the desktop without stealing window focus (`WS_EX_NOACTIVATE | WS_EX_TOPMOST`).
  - **Live Dynamic Value Feedback**: Displays current mode card, glowing mode LED pip, real-time value meters (volume percentage, zoom factor, scrub offset), and optical speed feedback.
  - **Gesture Toast**: Cyan glowing badge for TinyOL flicks and rollback confirmations.
  - **Auto-Fade Timer**: Smoothly glides/fades out after configurable idle timeout (1.8s) to remain completely unobtrusive.
  - **Ultra-Compact Footprint**: 1.8 MB executable (`OmniScroll.exe`), compiled in <3s, <10 MB RAM footprint.
- [x] **`omniscroll-cli` Native Diagnostic & Monitoring CLI**:
  - Standalone binary (`omniscroll-cli.exe`) for instant device scanning (`omniscroll-cli ports`), hardware discovery, and live serial monitoring without Python or pip dependencies.
- [ ] **`OmniScroll` Advanced Visual Polish**:
  - Fluid carousel sliding animation on mode transitions.
  - DirectComposition / Windows 11 Acrylic blur material.
  - User configuration for positioning (docked to sidebar rail, floating corner pill, or floating near active cursor).
- [ ] **`omniscroll-wasm` WebAssembly Integration**:
  - Compile `omniscroll-core` to Wasm via `wasm-bindgen` for the Web Control Panel.
  - Eliminates logic duplication between desktop and web platforms.
- [ ] **Phase 4: Embedded Rust Firmware (`esp-rs`)**:
  - Evaluate porting `OmniScroll.ino` to `esp-idf-hal` / `no_std` on ESP32-S2 for compile-time memory safety.

---

## 3. Experimental Prototypes & Lab Environments

### Multi-Window Multitasking Lab (`experiments/multi_window_lab/`)
- [x] **Isolated Test Architecture**:
  - Completely separated sandbox environment that leaves the main golden firmware (`OmniScroll.ino`) 100% untouched.
  - Dedicated uploader (`upload_lab.py`) with `--compile-only` verification.
- [x] **Lightweight Lab Firmware (`firmware/firmware.ino`)**:
  - Dedicated multi-window multitasking prototype featuring MX8650 optical tracking, PAM8403 LRA detents, LEDC PWM RGB indication, and double-tap middle selection.
  - 4 Interactive Test Modes:
    - **Mode 0 (Blue):** `APP_CAROUSEL` — Rotary Alt+Tab with tactile haptic detent per open window.
    - **Mode 1 (Green):** `SPATIAL_SNAP` — Left $\leftrightarrow$ Right split-screen focus jumping.
    - **Mode 2 (Amber):** `DUAL_SCROLL` — Dual-Window Synchronized Multi-Scroll (lockstep scrolling).
    - **Mode 3 (Purple):** `HOVER_FOCUS` — Smart Hover-Scroll with auto-focus activation.
- [x] **Interactive Test Bench Runner (`pc_lab_runner.py`)**:
  - Dark-themed Tkinter GUI featuring side-by-side mock document/code split panes.
  - Win32 hooks (`EnumWindows`, `SetForegroundWindow`, `WM_MOUSEWHEEL`, `WindowFromPoint`) to test against real Windows OS applications.
  - Real-time hardware serial telemetry parsing and manual simulation buttons.
