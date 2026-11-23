# OmniScroll Serial API & Communication Protocol

The OmniScroll uses a Web Serial API (via `USBCDC`) to communicate with the web-based control panel. The web UI is hosted completely client-side via `docs/index.html`.

All communication is line-based text, terminated by a newline (`\n`). 
Because we use `CDCOnBoot=dis_cdc`, the Serial stack works independently of the HID composite descriptors, meaning communication works even if the HID driver fails to enumerate on Windows.

## 1. Web to Device (Commands)

### SET Commands
Used to apply settings dynamically and save them to NVS (Non-Volatile Storage). These trigger a brief haptic click for confirmation.

**Global Parameters:**
* `SET:BRI:<0-100>` - Set global master LED brightness (percent).
* `SET:IDLE:<seconds>` - Set time before the LED dims (0 = disable).
* `SET:CPI:<0-3>` - Set MX8650 optical sensor DPI (0=400, 1=800, 2=1200, 3=1600).
* `SET:THR:<number>` - Set global capacitive touch threshold (100–3000). The Web UI exposes this as a 0% to 100% sensitivity slider (0% = 3000, 76% default = 800, 100% = 100).
* `SET:FLICK_FWD:<0-25>` - Set Flick Forward action (0=Off, 1=BrowBack, 2=BrowFwd, 3=Undo, 4=Redo [Ctrl+Shift+Z], 5=MediaPrev, 6=MediaNext, 7=TabPrev, 8=TabNext, 9=DeskPrev, 10=DeskNext, 11=VolDown, 12=VolUp, 13=Copy, 14=Paste, 15=NextMode, 16=PrevMode, 17..24=DirectMode, 25=PlayPause).
* `SET:FLICK_REV:<0-25>` - Set Flick Back action (same actions as above).
* `SET:TSPIN:<0-6>` - Set Touch & Spin modifier action (0=Off, 1=H-Scroll, 2=Universal Zoom, 3=Turbo 4x, 4=Timeline Scrub, 5=Quick Volume, 6=App Switcher Alt+Tab Clutch).
* `SET:SINGLE_TAP:<0-25, 99>` - Set Single Tap shortcut (99=Reject Neural Mis-Trigger [Default], 0=Off, 1..25=Standard actions e.g. Play/Pause, Browser Back/Forward, Next/Prev Mode, Direct Modes, Undo/Redo).
* `SET:GESTURE_PROFILE:<S>,<R>,<T>` - Sets the initial adaptive gesture centroid parameters (Stroke, Recoil, Dwell).
* `SET:GESTURE_REJECT` - Human-in-the-loop mis-trigger rejection. Rolls back TinyOL neural prototype centroids in volatile SRAM to the exact state before the last flick, suppresses NVS write (`gestureLearnedDirty = false`), triggers an 80Hz haptic rejection buzz, and flashes the LED amber/red.
* `SET:GESTURE_RESET` - Resets on-device TinyOL centroids back to the factory calibrated mathematical baseline (`S=85, R=52, T=24`) and commits to NVS.

**Wi-Fi Configuration & Provisioning:**
* `SET:WIFI:<SSID>:<PASS>` - Provisions Wi-Fi network credentials directly to OmniScroll over the USB wire and initiates connection. Persisted in NVS.
* `GET:WIFI:STATUS` - Requests current Wi-Fi connection state, active IP address, RSSI, and client status.
* `SET:WIFI:RESET` - Clears stored Wi-Fi credentials from NVS and disconnects the wireless radio.

**Hardware White Balance Calibration:**
* `SET:CAL:R:<float>` - Red channel scaling (0.0 to 1.0)
* `SET:CAL:G:<float>` - Green channel scaling (0.0 to 1.0)
* `SET:CAL:B:<float>` - Blue channel scaling (0.0 to 1.0)

**Per-Mode Parameters (Max 8 Modes):**
Requires selecting the mode index first within the command chain.
* `SET:MODE:<0-7>,EN:<0|1>,CS:<HEX>,HP:<0-4>,INV:<0|1>,MTHR:<number>`
  * `EN` - Enabled boolean (1 = true)
  * `CS` - Color hex string (without `#`, e.g., `ff0000`)
  * `HP` - Haptic Profile (0=Click, 1=Thud, 2=Tick, 3=Soft, 4=Off)
  * `INV` - Invert scroll direction boolean (1 = true)
  * `MTHR` - Scroll threshold (higher = less sensitive, more wheel travel needed per tick)

*Commands can be chained:* `SET:BRI:100,MODE:0,CS:ff0000,HP:1`

### PREVIEW Commands
Identical to `SET:`, but does **not** save to NVS and does **not** trigger a haptic click. Used for real-time slider adjustments in the UI before committing.
* `PREVIEW:BRI:50`
* `PREVIEW:CAL:R:0.5`

### Query & Test Commands
* `GET:STATUS` - Requests a rapid telemetry update.
* `GET:CONFIG` - Requests the complete configuration state (to populate the UI on load).
* `GET:GESTURE_PROFILE` - Requests the live mathematical gesture prototype centroids (`{"s":...,"r":...,"t":...}`).
* `TEST:HAPTIC` - Plays the currently selected haptic profile once.
* `TEST:LED:<R|G|B|OFF|RESET>` - Forces a pure individual LED channel output or resets back to the active mode color for hardware diagnosis.
* `PING:<timestamp>` - Ultra-low latency UDP ping on Port 4211. OmniScroll echoes back `PONG:<timestamp>` instantly for round-trip time (RTT) and jitter benchmarking.
* `SCAN:WIFI` - Performs a fast 2.4 GHz RF scan across all channels and streams visible SSIDs, signal RSSI, and encryption (`WIFI:NET:<SSID>:<RSSI>:<AUTH>`).
* `SET:WIFI:<SSID>:<PASS>` - Provisions Wi-Fi network credentials into ESP32 NVS flash and initiates station connection.
* `GET:WIFI:STATUS` - Requests current Wi-Fi connection state, assigned local IP, and RSSI (`WIFI:STATUS:{"connected":...,"ssid":...,"ip":...,"rssi":...}`).
* `SET:WIFI:RESET` - Clears Wi-Fi credentials from NVS flash and disconnects the Wi-Fi radio.

## 2. Device to Web (Responses & Push Announcements)

### Hardware Wake Announcements (Device-Driven Push Architecture)
OmniScroll uses an event-driven hardware push architecture to eliminate active PC bus polling:
* `OMNISCROLL:WAKE:VER=2.0:MODE=<ModeName>:ID=OMNI-007` - Unsolicited push announcement emitted automatically on firmware boot completion and whenever the USB cable is mounted to a PC host (`tud_mounted() && !tud_suspended()`). The Desktop Application catches this announcement to transition instantly to `Connected (USB Cable COMxx)`.
* `OMNISCROLL:WAKE` - Unsolicited wake signal emitted immediately when the user touches the top capacitive disc, presses the button, or rotates the wheel from an idle dim state.
* `OMNISCROLL:WAKE:IP=<ip>:PORT=4211:VER=2.0:MODE=<mode>:USB=<0|1>` - Unsolicited UDP discovery wake datagram broadcast on Port 4210 when connecting to local Wi-Fi.

### STATUS Response & Push Telemetry
Rapid telemetry sent when `GET:STATUS` is received or pushed on state transitions, formatted as JSON string prefixed with `STATUS:`.
```json
STATUS:{"mode":"SCROLL","touch":1234,"baseline":0,"accX":10,"usb":1}
```
* `usb`: Host connection state (`1` = mounted and active with PC, `0` = standby / disconnected breathing).


### CONFIG Response
Full state payload sent when `GET:CONFIG` is received, formatted as JSON string prefixed with `CONFIG:`.
```json
CONFIG:{
  "bri": 100,
  "idle": 30,
  "cpi": 1,
  "thr": 800,
  "cal_r": 1.000,
  "cal_g": 1.000,
  "cal_b": 1.000,
  "flick_fwd": 2,
  "flick_rev": 1,
  "tspin": 1,
  "single_tap": 99,
  "modes": [
    {"name":"SCROLL","en":1,"c":"0000ff","hp":0,"inv":0,"thr":10},
    {"name":"VOLUME","en":1,"c":"00ff00","hp":3,"inv":0,"thr":25}
  ]
}
```

### Async Notifications
* `MODE:<ModeName>` - Broadcast automatically when the user physically switches modes via capacitive double-tap or the physical hardware button. The web UI uses this to instantly highlight the active mode.
* `SCROLL:<delta>` - Broadcast in real time when the optical wheel rotates. The web control panel uses this to smoothly animate the Apple-inspired precision rotary dial and watchOS Digital Crown haptic track live.
* `TOUCH:TAP` - Broadcast when the user touches the top capacitive disk. Triggers the radiant HomePod glass ripple in the Web UI.
* `TOUCH:DOUBLE` - Broadcast when a capacitive double-tap is registered. Triggers the dual-harmonic resonant wave in the Web UI.
* `GESTURE:FLICK:FWD` - Broadcast when a forward flick gesture is recognized and dispatched.
* `GESTURE:FLICK:REV` - Broadcast when a reverse flick gesture is recognized and dispatched.
* `GESTURE:LEARNED:S=<val>,R=<val>,T=<val>` - Broadcast when the on-device TinyOL engine adapts personal prototype centroids to the user's kinematic signature. Triggers a radiant Cyan pulse on the physical LED and updates the Web UI neural card.
* `GESTURE:REJECTED:ROLLBACK_OK` - Broadcast when a mis-triggered flick is successfully rolled back via physical single-tap or Web UI reject button.
* `GESTURE:REJECTED:NO_PREV_DATA` - Broadcast if a rejection is requested when no prior gesture snapshot exists.
* `GESTURE:RESET:OK` - Broadcast when gesture centroids are reset back to factory baseline.

## 3. Wireless Multi-Transport Protocol (RoufsWeb Protocol / RWP v2.1) & Virtual HID Bridge

When OmniScroll operates wirelessly (over 2.4 GHz 802.11b/g/n Wi-Fi), it streams real-time binary datagrams to the standalone Desktop Application via the **RoufsWeb Protocol (RWP v2.1)**. The Desktop Application acts as the **Virtual USB / HID Bridge**, translating packets into native Windows input events via Win32 `SendInput` with $<1$ms latency.

### 4-Tier Zero-Fail Discovery Engine
To ensure instantaneous and unbreakable discovery across all home router setups (including multi-band 2.4/5 GHz meshes, client AP isolation, and broadcast packet suppression), RWP v2.1 implements a 4-tier discovery pipeline:

1. **Tier 1: Instant Direct Unicast Quick-Probe (Port 4210, <15ms):** Desktop immediately sends probe to `last_wifi_ip` from persistent settings. If online, the device replies in 1–2ms.
2. **Tier 2: ZeroConf mDNS Discovery (`omniscroll.local`, <50ms):** ESP32 registers mDNS hostname `omniscroll.local` and advertises `_roufsweb._udp` on Port 4211. Resolves directly across subnets even when DHCP dynamic leases change.
3. **Tier 3: Multi-Broadcast Subnet Probing (Ports 4210 & 4211):** Desktop dispatches discovery probes (`OMNI` / `RWP:PING`) simultaneously to global broadcast (`255.255.255.255`) and directed local subnet broadcast (e.g. `192.168.0.255`). ESP32 responds immediately with beacon and binds client.
4. **Tier 4: Micro Subnet Ping Sweep (/24 fallback):** If broadcast and mDNS are suppressed by strict router AP isolation, the desktop app executes a parallel non-blocking UDP sweep across the active `/24` subnet.

### Reverse Host Registration
OmniScroll persists `last_host_ip` in ESP32 NVS. Whenever Wi-Fi reconnects or the device boots, it actively pushes a proactive unicast announcement datagram directly to the PC host IP (`ROUFSWEB:<ip>:PORT=4211:VER=2.1:MODE=<mode>:USB=<0|1>`), immediately alerting the Desktop App without waiting for a PC scan.

### Symmetrical UDP Sockets & State
The desktop bridge binds its UDP streaming socket to local port 4211 (or dynamic fallback), allowing outgoing bidirectional commands (`SET:`, `GET:`, `PREVIEW:`, `PING`) and incoming binary RWP streams to traverse stateful router NAT tables and Windows Firewall without packet dropping.

### Real-Time RWP v2.1 Streaming Datagram (UDP Port 4211)
Binary 9-byte low-overhead datagram transmitted on optical movement, gestures, and touch interactions:
```
Offset  Type     Field       Description
0-1     uint16   Magic       0x5257 ('R', 'W') [OMP 0xAA55 legacy backward-compatible]
2       uint8    Packet Type 0x01 = Motion/Scroll, 0x02 = Action/Key, 0x03 = Gesture, 0x04 = Status
3       uint8    Seq Number  0–255 (to detect packet loss)
4       int8     Delta       Motion delta (-128 to 127)
5       uint8    Mode Index  Active mode index (0–7)
6       uint8    Action Code Action ID (0–25, 99)
7       uint8    Flags       Bit 0: High-Res active, Bit 1: Touch active, Bit 2: USB mounted
8       uint8    Checksum    XOR sum of bytes 0–7
```

### First-Class Wireless Host State & Detent Safety
* **Host State (`isHostActive`):** Defined as `(hostState == USB_HOST_CONNECTED) || (WiFi.isConnected() && bridgeClientBound)`. When connected over Wi-Fi, the device maintains full active mode colors and brightness, and only falls back to Apple MagSafe amber breathing when disconnected from both USB and desktop bridge.
* **Detent Runaway Protection:** The haptic accumulation loop guarantees strict convergence on negative deltas (`accumulationX += thr` when `dx < 0`), eliminating runaway vibration bugs.
* **Bi-directional Settings Sync:** All slider and setting adjustments (`SET:BRI`, `SET:IDLE`, `SET:THR`, `SET:MODE`, `SET:HP`, etc.) sent over UDP immediately update firmware state and persist to NVS.

### Mutual Exclusion & Seamless Handover
* When OmniScroll is plugged into the PC via USB, `Flags & 0x04 == 0x04` (`usbMounted = 1`). The native ESP32 USB HID composite device fires directly into Windows, and the Virtual Bridge suppresses its `SendInput` worker to prevent duplicate inputs.
* **Dynamic Wi-Fi Power Modulation (Wired vs Wireless):**
  * **Wired Lightweight Standby:** When plugged into the PC (`hostState == USB_HOST_CONNECTED`), the firmware activates Wi-Fi modem sleep (`WiFi.setSleep(true)`), dropping RF current consumption by ~80% (from ~110mA down to ~20mA) while keeping the Wi-Fi link fully connected and registered with the router/AP. High-rate optical motion UDP streaming is suppressed to prevent RF noise and network congestion, while lightweight 2.5s status beacons maintain bidirectional link awareness.
  * **Instant Zero-Lag Wireless Promotion:** The instant the USB cable is unplugged (`hostState != USB_HOST_CONNECTED`), the firmware disables modem sleep in hardware (`WiFi.setSleep(false)`), unlocking ultra-low sub-2ms network latency, and immediately promotes optical motion streaming to UDP Port 4211 with $<10$ms failover time.
* When unplugged from the PC (`DBT_DEVICEREMOVECOMPLETE`), the desktop application automatically triggers seamless Wi-Fi failover (`Switching to Wi-Fi...`), discovering the device over UDP and resuming operation without manual user intervention.
* When running wirelessly on a wall adapter, power bank, or battery, `Flags & 0x04 == 0`. Physical detents continue firing locally on the iPhone 6 LRA, and the Desktop App injects the Windows mouse wheel, horizontal pan, media keys, and keyboard shortcuts seamlessly.

### Standalone Windows Desktop App Architecture (Pure Native PySide6)
The standalone desktop application (`OmniScroll.exe`, ~48 MB single-file executable) is engineered using pure Windows native widgets (`PySide6`, `QPainter`, and QSS stylesheets) without Chromium or WebEngine runtime overhead (<35 MB RAM footprint, <0.2s launch time).

Every container and interactive widget from the Web Control Panel is replicated natively with 1:1 behavioral parity:
* **`PhotorealisticRotaryDial`:** Custom `QPainter` widget rendering photorealistic Nordic Walnut / Obsidian / Aluminum / Ultra hardware with 48 rotating perspective knurled ticks synced 1:1 with optical encoder counts, live HomePod radiant touch ripples, embedded **`GestureBadgeWidget`** with dynamic action icon, and **Zero-Leak LED Diffuser Light** strictly clipped to the physical slanted slot geometry (`QPainter.setClipPath`) and clamped at the 83.3% right border.
* **`HeaderBar` & `ThemeSegmentedBar`:** Minimalist header with unified brand title **`Omniscroll`** (single word, no badge clutter), top-right "ℹ" info button opening dedicated Apple Pro HIG About & Specifications modal (`AboutModal`), and connect/status capsule. The 4-segment theme switcher (`ThemeSegmentedBar`) replicates Web UI `.apple-theme-segmented` 1:1 with glowing circular swatches (Obsidian `#00D4FF`, Aluminum `#0071E3` with white rim, Walnut `#FFA000`, Ultra `#FF6200`) and is geometrically pinned to the dead horizontal center `(w - 360) // 2` in `HeaderBar.resizeEvent`, ensuring 0px movement when scanning or connection status text changes.
* **`ActiveModeIsland` & `ApplePulseButton`:** Unified active mode stage header matching Web UI `.stage-header` (eliminating the redundant separate "ACTIVE MODE" top banner). Features a frosted mode pill badge with 9px glowing LED pip, bold uppercase mode title, border-left tag divider, and custom `ApplePulseButton` with animated ECG tactile pulse waveform icon (`M 2 12 h3 l2 -6 4 12 4 -8 2 5 2 -3 h3`).
* **`WifiStudioContainer`:** Streamlined Apple Pro HIG wireless container. When the device has stored credentials, the SSID is pre-selected and the password field displays masked `••••••••` characters. All clutter (old "Provision via USB", "Reset Wi-Fi", and raw IP badges) is replaced by a single full-width **"Update Password"** button. The container maintains a completely clean state without permanent warning text; if the user attempts to update the password while unwired, the button and container dynamically surface a temporary warning (*"⚠️ Connect USB cable first"*). Connection feedback is communicated via an ethereal, subtle **glassmorphic green ambient hue** (`rgba(48, 209, 88, 0.08)`) and a subtle `Connected to <SSID>` tag, providing instant visual confirmation with zero cognitive load.
* **`HardwareRgbCalibrationCard`:** Triple continuous slider card (Red, Green, Blue from 0 to 100.0%) and diagnostic test triggers (`TEST:LED:R`, `TEST:LED:G`, `TEST:LED:B`, `RESET`) matching the Web UI Advanced Settings pane.
* **`AppleColorModal`:** Bespoke Apple HIG color palette modal providing 12 curated swatches, hex input field, and live color swatch preview, replacing standard system color pickers.
* **`AppleSideScrollRail`:** Precision vertical slider rail matching the Web UI `aside.side-scroll-rail` with smooth step buttons and draggable thumb bidirectionally bound to `QScrollArea`. The native scrollbar closest to the widgets is disabled (`ScrollBarAlwaysOff`), providing clean single-rail isolation.
* **`AboutModal`:** Dedicated Apple Pro HIG modal dialog displaying the comprehensive hardware specifications grid and interactive FAQ accordions, keeping the main interface uncluttered.

### High-Performance Native Rust Desktop Studio (`omniscroll-rs`)
The project desktop companion software has migrated to a unified, production-grade native Rust workspace (`omniscroll-rs/`), replacing legacy Python runtimes with sub-microsecond input dispatch and an ultra-lean memory footprint (<15 MB RAM, <400ms startup):
* **`omniscroll-core` (`no_std` compatible):** Core mathematical and protocol engine. Implements zero-copy RWP v2.1 binary parser, high-res remainder accumulator ($120/\text{threshold}$), TinyOL kinematic phase-energy equations, and `DeviceConfig` serialization (`%APPDATA%\OmniScroll\config.json`).
* **`omniscroll-bridge`:** Low-latency Win32 input injector via Microsoft `windows` crate, async UDP listener on Port 4211 (`tokio`), background USB CDC auto-discovery matching VID `0x303A` / PID `0x4F5B`, and native Windows WLAN API scanner (`WifiScanner`).
* **`omniscroll-gui` (`OmniScroll-Studio.exe`, 11.8 MB standalone binary):** The flagship Nordic Walnut / Apple Pro HIG Desktop Studio built with Slint 1.19. Features an 8-mode horizontal selector strip, 360° physical rotary crown visualizer with MagSafe Amber dot (`#FFA000`), detent sensitivity slider, rotation invert switch, Touch & Spin Action 6 (App Switcher Alt+Tab clutch), TinyOL neural centroids card with mis-trigger rollback, hardware RGB white-balance calibration, background Wi-Fi scanner & one-click provisioning, and Windows auto-start (`HKCU\...\Run`).
* **`omniscroll` (HUD):** Lightweight 1.8 MB on-screen dynamic glassmorphic HUD overlay.
* **`omniscroll-cli`:** Port discovery and serial telemetry monitoring utility.

> [!NOTE]
> The legacy Python desktop application (`desktop_app/`, PySide6) is deprecated in favor of the standalone native Rust executable `OmniScroll-Studio.exe`.

### Multi-Window Multitasking Lab Telemetry & Protocols (`experiments/multi_window_lab/`)
* **Isolated Sandbox Architecture:** Resides entirely in `experiments/multi_window_lab/`, keeping production firmware (`OmniScroll.ino`) and release assets uncompromised.
* **Firmware Protocol (`firmware/firmware.ino`):**
  * `MODE:<idx>:<name>`: Emitted on boot and on mode cycle via double-tap.
  * `EVENT:ROT:<dx>`: Raw optical movement counts from MX8650 sensor.
  * `EVENT:TOUCH:<1|0>`: Capacitive touch contact assertions on GPIO 12.
  * `EVENT:DOUBLE_TAP`: Middle capacitive disk double-tap event triggering next test mode.
* **4 Dedicated Test Modes:**
  * `Mode 0 (Blue #007AFF)`: `APP_CAROUSEL` — Rotary Alt+Tab with LRA detent per open window.
  * `Mode 1 (Green #30D158)`: `SPATIAL_SNAP` — Left/Right split-screen focus toggle.
  * `Mode 2 (Amber #FFA000)`: `DUAL_SCROLL` — Dual-Window Synchronized Multi-Scroll (lockstep).
  * `Mode 3 (Purple #AF52DE)`: `HOVER_FOCUS` — Smart Hover-Scroll with auto-focus activation.
* **PC Lab Runner (`pc_lab_runner.py`):** Provides interactive dark split-screen document panes and Win32 `WM_MOUSEWHEEL` / `SetForegroundWindow` hooks for real Windows OS testing.



