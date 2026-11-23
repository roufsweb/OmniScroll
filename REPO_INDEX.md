# OmniScroll Codebase & Architectural Master Index

> **Purpose:** This file is the definitive architectural index of the OmniScroll project. It maps every file, subsystem, class, function, and UI element in the repository. AI assistants and developers should use this index to locate the exact file and line ranges for any task without rescanning the entire repository.

---

## 1. Master File Inventory

| Path | Language / Type | Lines | Size | Primary Responsibility |
| :--- | :--- | :---: | :---: | :--- |
| [`OmniScroll.ino`](file:///e:/rouf/hardware-project/OmniScroll/OmniScroll.ino) | C++ / Arduino | 1,872 | 79 KB | Core firmware: state machine, mode dispatch, TinyOL neural engine, NVS, serial parser, RoufsWeb Protocol (RWP v2.1) UDP streaming. |
| [`OmniScrollHID.h`](file:///e:/rouf/hardware-project/OmniScroll/OmniScrollHID.h) | C++ Header | 51 | 1.3 KB | Custom USB HID driver header: report descriptor declaration, high-res resolution multiplier interface. |
| [`OmniScrollHID.cpp`](file:///e:/rouf/hardware-project/OmniScroll/OmniScrollHID.cpp) | C++ Implementation | 131 | 6.5 KB | High-Resolution USB HID descriptor (Usage `0x48`), logical collection, Report ID 11, relative wheel & AC Pan dispatch. |
| [`TouchController.h`](file:///e:/rouf/hardware-project/OmniScroll/TouchController.h) | C++ Header | 47 | 1.2 KB | Capacitive touch controller interface: debounced tap, double-tap, hold, threshold management. |
| [`TouchController.cpp`](file:///e:/rouf/hardware-project/OmniScroll/TouchController.cpp) | C++ Implementation | 99 | 2.8 KB | ESP32-S2 hardware capacitive touch state machine (`touchRead`) with 40ms debounce, 600ms double-tap window. |
| [`upload.py`](file:///e:/rouf/hardware-project/OmniScroll/upload.py) | Python 3 | 180 | 6.2 KB | Flashing tool: 1200-bps bootloader trigger, COM port tracking, USB build props injection, Arduino CLI wrapper. |
| [`desktop_app/main.py`](file:///e:/rouf/hardware-project/OmniScroll/desktop_app/main.py) | Python 3 (PySide6) | 917 | 39.6 KB | Native desktop app entry point: window lifecycle, dual-transport management, background worker threads, tray icon, winreg startup. |
| [`desktop_app/protocol.py`](file:///e:/rouf/hardware-project/OmniScroll/desktop_app/protocol.py) | Python 3 | 475 | 16.7 KB | RWP v2.1 UDP 9-byte packet parser/unpacker, 4-tier discovery (Port 4210), serial transport with strict VID/PID whitelist. |
| [`desktop_app/virtual_bridge.py`](file:///e:/rouf/hardware-project/OmniScroll/desktop_app/virtual_bridge.py) | Python 3 (ctypes) | 274 | 9.9 KB | Windows Win32 `SendInput` virtual input bridge: high-res wheel sub-tick accumulator, horizontal panning, media keys, shortcuts. |
| [`desktop_app/widgets.py`](file:///e:/rouf/hardware-project/OmniScroll/desktop_app/widgets.py) | Python 3 (PySide6) | 3,036 | 117 KB | Bespoke Apple Pro HIG UI widget library: `PhotorealisticRotaryDial`, `AppleCapsuleSlider`, `AppleCapsulePicker`, `GestureBadgeWidget`, `ActiveModePillWidget`, etc. |
| [`desktop_app/themes.py`](file:///e:/rouf/hardware-project/OmniScroll/desktop_app/themes.py) | Python 3 | 135 | 4.4 KB | 4-theme styling system (Walnut, Obsidian, Aluminum, Ultra): colors, procedural textures, QSS stylesheets. |
| [`desktop_app/wifi_scanner.py`](file:///e:/rouf/hardware-project/OmniScroll/desktop_app/wifi_scanner.py) | Python 3 | 128 | 4.8 KB | Windows native WLAN scanner (`netsh wlan` parser) with 2.4 GHz vs 5 GHz validation. |
| [`desktop_app/OmniScroll.spec`](file:///e:/rouf/hardware-project/OmniScroll/desktop_app/OmniScroll.spec) | PyInstaller Spec | 55 | 1.2 KB | Standalone single-file executable packaging specification (`dist/OmniScroll.exe`). |
| [`docs/index.html`](file:///e:/rouf/hardware-project/OmniScroll/docs/index.html) | HTML5 / CSS / JS | 4,444 | 196 KB | Zero-install Web Control Panel: Web Serial API (`USBCDC`), Apple Pro HIG UI, live dial animation, SEO JSON-LD schema, FAQ accordion. |
| [`desktop_app/ui/index.html`](file:///e:/rouf/hardware-project/OmniScroll/desktop_app/ui/index.html) | HTML5 / CSS / JS | 4,907 | 212 KB | Offline HTML interface preview & browser test suite. |
| [`COMMUNICATION.md`](file:///e:/rouf/hardware-project/OmniScroll/COMMUNICATION.md) | Markdown | 160 | 14.6 KB | Complete protocol specification: Web Serial commands (`SET:`, `GET:`, `PREVIEW:`), UDP RWP v2.1 datagrams, push announcements. |
| [`FEATURES.md`](file:///e:/rouf/hardware-project/OmniScroll/FEATURES.md) | Markdown | 98 | 15.9 KB | Comprehensive feature documentation: hardware specs, 8 modes, smooth scrolling, TinyOL learning, UI themes. |
| [`HARDWARE.md`](file:///e:/rouf/hardware-project/OmniScroll/HARDWARE.md) | Markdown | 32 | 2.1 KB | Pinouts, circuit schematics, optical bearing encoder mechanics, PAM8403 LRA drive, 5050 RGB LED balancing. |
| [`AGENTS.md`](file:///e:/rouf/hardware-project/OmniScroll/AGENTS.md) | Markdown | 88 | 15.7 KB | AI project memory: quirks, calibration constants (~520 counts/rev), USB caching rules, peripheral safety whitelist. |
| [`README.md`](file:///e:/rouf/hardware-project/OmniScroll/README.md) | Markdown | 149 | 10.0 KB | Public repository front page: quick start, badges, SEO keywords, feature highlights, architecture diagrams. |
| [`gesture_session_30s.csv`](file:///e:/rouf/hardware-project/OmniScroll/gesture_session_30s.csv) | CSV Data | 3,578 | 104 KB | 3,577-sample ground-truth optical wheel telemetry session used to validate gesture engines. |
| [`tools/`](file:///e:/rouf/hardware-project/OmniScroll/tools) | Python 3 Suite | ~2,000 | ~75 KB | 20+ offline mathematical telemetry verification, kinematic analysis, and latency benchmarking scripts. |

---

## 2. Firmware Subsystems (`OmniScroll.ino`)

The firmware is structured into clear modular functional blocks:

| Lines | Subsystem / Functionality | Key Symbols & Constants |
| :--- | :--- | :--- |
| **1–255** | **Configuration, Enums & Globals** | `modes[MAX_MODES]`, `ActionCode`, `HapticProfile`, `TinyOLCentroids`, `RGB_R_PIN=18`, `RGB_G_PIN=35`, `RGB_B_PIN=33`, `TOUCH_PIN=12` |
| **256–294** | **MX8650 Optical Sensor Driver** | `mx8650_write(reg, data)`, `mx8650_read(reg)`, bit-banged 2-wire serial protocol (SDIO GPIO 9, SCLK GPIO 11) |
| **295–366** | **Hardware RGB LED & Gamma 2.8** | `gamma28[]` LUT, `setLedColor(r,g,b)`, `setLedColorDirect(r,g,b)`, `applyModeColor()`, LEDC hardware PWM |
| **367–422** | **Organic Standby & Host Connection** | `renderAppleBreathing()` (resting respiratory curve ~4.5s in Amber `#FFA000`), `renderConnectingCrossfade()` (450ms cubic ease-out) |
| **423–436** | **Haptic Feedback Engine** | `playHapticClick()`, PAM8403 square wave pulse generator, 5 profiles (Click, Thud, Tick, Soft, Off) |
| **437–507** | **Mode Management & Cycling** | `cycleMode()`, `cycleModePrev()`, `switchToMode(idx)` (supports 8 operational modes) |
| **508–613** | **NVS Persistence (Preferences)** | `loadPrefs()`, `savePrefs()` storing mode configs, white-balance calibration, idle timeout, brightness, CPI, gesture centroids |
| **614–666** | **Mode Action Dispatch** | `dispatchAction(direction)` mapping mode actions to native HID reports or OMP UDP packets |
| **667–872** | **Touch & Modifier Actions** | `playHapticDoubleClick()`, `triggerGestureFlash()`, `rejectLastGesture()`, `dispatchSingleAction()`, `dispatchTouchSpinAction()` |
| **873–1058** | **TinyOL Adaptive Gesture Engine** | `updateFlickEngine(dx)`: Phase-energy gate $E_{\text{snap}} = R^2 / (T_{\text{dwell}} + 1) \ge 20$, Mahalanobis distance $d^2$, EMA adaptation ($\alpha=0.08$), lossless SRAM snapshot rollback |
| **1059–1261** | **Serial Protocol Parser** | `buildConfigJSON()`, `parseSerialCommand()` (`SET:`, `PREVIEW:`, `GET:`, `TEST:`, `SCAN:WIFI`, `SET:WIFI:`, `SET:GESTURE_REJECT`) |
| **1262–1448** | **Wi-Fi & OMP UDP Stack** | `sendOMPPacket()`, `initWiFi()`, `executeUdpCommand()`, `processWiFi()` (Port 4210 beacons, Port 4211 streaming, PING/PONG keepalive) |
| **1449–1478** | **TinyUSB Descriptor Callbacks** | `tud_descriptor_string_cb` ensuring device strings report as "OmniScroll" / "OMNI-007" |
| **1479–1549** | **`setup()` Initialization** | LEDC attach (5kHz, 8-bit), MX8650 boot, Preferences load, TinyUSB start, Wi-Fi initialization |
| **1550–1872** | **`loop()` Execution Engine** | Host mount watchdog (`tud_mounted()`), breathing vs active mode, touch polling & hold gate, optical wheel tracking, high-res streaming vs stepped detents, motionless silence watchdog (85ms) |

---

## 3. Desktop Application Subsystems (`desktop_app/`)

### A. Window Lifecycle & Transport (`main.py`)
- **`MainWindow` (L154–917):** Main window UI container, status header, stage card, mode grid, advanced disclosures.
- **`StreamWorker` (L69–140):** Background `QThread` reading real-time OMP UDP packets on Port 4211 and serial CDC lines, feeding packets to `VirtualBridge`. Emits periodic keepalive `PING`s in Wi-Fi mode.
- **`DiscoveryWorker` (L141–153):** Background `QThread` handling multi-broadcast UDP discovery.
- **`WifiScanWorker` (L56–68):** Background worker invoking `wifi_scanner.scan_networks()`.
- **System Tray & Autostart (L840–891):** Windows registry run key synchronization (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`), close-to-tray minimization.

### B. Communication & Protocols (`protocol.py`)
- **`OMPPacket` (L35–88):** 9-byte binary UDP datagram unpacker (`0xAA55` magic, packet type, sequence, delta, mode, action, flags, XOR checksum).
- **`SerialStreamManager` (L90–222):** Peripheral safety whitelisting (`VID: 0x303A`, `PID: 0x4F5B`), DTR/RTS assertion, serial read/write.
- **`WiFiStreamManager` (L224–396):** Multi-broadcast subnet probe dispatch (Port 4210), UDP streaming listener (Port 4211), keepalive heartbeat.
- **`TransportManager` (L404–475):** Seamless dual-transport router with priority failover (USB CDC $\to$ Wi-Fi UDP).

### C. Win32 Input Injection (`virtual_bridge.py`)
- **`VirtualBridge` (L86–274):** Win32 `SendInput` wrapper (`ctypes.windll.user32.SendInput`).
  - `scroll_vertical(ticks)`: Injects continuous high-res sub-ticks (`WHEEL_DELTA * delta / threshold`).
  - `scroll_horizontal(ticks)`: Injects `MOUSEEVENTF_HWHEEL` horizontal pan events.
  - `dispatch_action(action_id)`: Dispatches keyboard shortcuts, Undo/Redo (`Ctrl+Shift+Z`), browser navigation, and media keys (`VK_MEDIA_PLAY_PAUSE`, `VK_VOLUME_UP`, etc.).

### D. UI Widget Library (`widgets.py`)
- **`PhotorealisticRotaryDial` (L856–1124):** Core hardware visualization widget with 48 perspective knurled ticks, HomePod radiant touch ripples, organic cubic bezier LED diffuser glow, and rotation synced 1:1 with optical counts.
- **`GestureBadgeWidget` (L748–854):** Live dynamic badge on the dial displaying flick direction, action icon, neural adaptation cyan indicator, and inline rollback button.
- **`HeaderBar` (L293–445):** Apple Pro HIG minimal header: `OmniScroll` brand typography with right-adjacent `from roufsweb` amber glassmorphic badge, invariant top-right connection status pill (`148px × 34px`) with glassmorphic states (red for Disconnected, green for Cable/Wireless, amber for Searching), and "ℹ" specs modal trigger. Single-theme Nordic Walnut architecture.
- **`ActiveModePillWidget` & `ActiveModeIsland` (L508–658):** Glowing circular LED pip, uppercase mode title, subtle divider, and animated ECG tactile pulse waveform button.
- **`AppleCapsuleSlider` (L1191–1386):** Continuous capsule slider for Brightness, Idle Sleep, and Touch Sensitivity.
- **`AppleCapsulePicker` (L1388–1481):** Apple Pro HIG popover pickers for Flick Forward, Flick Back, Touch & Spin, and Single Tap.
- **`WifiStudioContainer` (L1650–1900):** Streamlined Apple Pro HIG wireless container featuring pre-selected saved SSID, masked password (`••••••••`), single full-width "Update Password" button, on-demand wired-only warning trigger, and an ethereal, subtle glassmorphic green ambient hue when connected wirelessly.
- **`NativeModeCard` (L2093–2270):** 8-card tactile grid for mode configuration with custom color swatch modal and detent selector.
- **`TinyOLNeuralCard` (L2272–2393):** Real-time display of on-device learned prototype centroids $(\mu_S, \mu_R, \mu_T)$, live rollback trigger, baseline reset.
- **`HardwareRgbCalibrationCard` (L2456–2558):** Individual R, G, B channel calibration sliders with live channel test buttons.
- **`AppleSideScrollRail` (L2560–2703):** Isolated right-hand scroll rail ensuring physical wheel input never fights window scrolling.
- **`AboutModal` (L2845–3036):** Apple Pro HIG modal detailing device specs, architecture, and team credits.

---

## 4. UI & Design Philosophy

OmniScroll's visual and tactile experience is guided by **Apple Human Interface Guidelines (HIG)** and **Nordic Walnut Craftsmanship**:

### Core Visual Principles
1. **Material Authenticity & 4 Physical Themes:**
   - **Nordic Walnut (Default):** Deep organic walnut grain (`#281E16`), warm amber MagSafe accent (`#FFA000`), tactile wooden warmth.
   - **Obsidian:** Void black (`#0A0A0C`), deep charcoal cards, electric cyan/blue accents (`#00D4FF`).
   - **Aluminum:** Bead-blasted Mac Studio silver/titanium, crisp Apple Blue (`#0071E3`) accents.
   - **Ultra:** Apple Watch Ultra titanium (`#242220`), international safety orange (`#FF5A00`) accents.
2. **Tactile-Visual Resonance:**
   - Visual animations correspond directly to physical sensations:
     - Single Tap $\to$ Acoustic radial ripple wave (HomePod glass).
     - Double Tap $\to$ Dual-harmonic resonant wave.
     - Detents $\to$ watchOS Digital Crown haptic feedback strip.
     - Neural Adaptation $\to$ Radiant Cyan pulse (`#00F0DC`) on both physical LED and software badge.
     - Standby / Disconnected $\to$ Organic MagSafe Amber (`#FFA000`) resting respiratory curve (~4.5s cycle) with Gamma 2.8 perceptual correction.
3. **Minimalism with Progressive Disclosure:**
   - Clean, uncluttered primary interface (Dial hero stage, Active mode pill, Studio Controls sliders).
   - Complex configuration (TinyOL neural metrics, RGB channel calibration, Wi-Fi latency benchmark) is tucked inside smooth collapsible progressive disclosures (`CollapsibleDisclosure`).
4. **Zero-Leak LED Diffuser Light:**
   - In both Web and Desktop UI, the LED indicator is mathematically modeled as an organic handmade curved diffuser slot using cubic bezier paths (`QPainterPath`), strictly clipped to the physical hardware geometry without harsh polygon borders or light bleeding.

---

## 5. Feature-to-Code Cross-Reference Matrix

| Desired Feature / Modification | Relevant Files | Line Numbers / Symbols |
| :--- | :--- | :--- |
| **High-Res Smooth Scrolling** | `OmniScrollHID.cpp`, `OmniScroll.ino`, `desktop_app/virtual_bridge.py` | `desc_hid_omni` (L7–78), `updateFlickEngine` (L1680–1750), `scroll_vertical` (L92–100) |
| **Haptic Profiles & Virtual Detents** | `OmniScroll.ino`, `HARDWARE.md`, `desktop_app/widgets.py` | `playHapticClick` (L425–436), `HapticDetentStrip` (L1126–1165) |
| **TinyOL Neural Gesture Recognizer** | `OmniScroll.ino`, `tools/test_final_engine.py` | `updateFlickEngine` (L873–1058), Mahalanobis $d^2$, EMA centroid update |
| **Gesture Mis-Trigger Rejection (Rollback)** | `OmniScroll.ino`, `desktop_app/widgets.py` | `rejectLastGesture` (L699–727), `show_rejection` (L814–830) |
| **Capacitive Touch Sensing & Debounce** | `TouchController.cpp`, `TouchController.h`, `OmniScroll.ino` | `TouchController::update` (L30–98), `TOUCH_HOLD_MS` (L1580–1620) |
| **RGB LED Hardware PWM & Calibration** | `OmniScroll.ino`, `HARDWARE.md` | `setLedColor` (L318–360), `cal_R`, `cal_G`, `cal_B` constants |
| **Organic Standby MagSafe Amber Breathing** | `OmniScroll.ino` | `renderAppleBreathing` (L370–392), Gamma 2.8 LUT |
| **Wi-Fi OMP UDP Real-Time Streaming** | `OmniScroll.ino`, `desktop_app/protocol.py` | `sendOMPPacket` (L1264–1285), `OMPPacket` (L35–88), Port 4211 |
| **Auto-Discovery & UDP Keepalive** | `OmniScroll.ino`, `desktop_app/protocol.py`, `desktop_app/main.py` | `processWiFi` (L1348–1448), `StreamWorker` (L69–140), Port 4210 |
| **Web Serial API Control Panel** | `docs/index.html`, `COMMUNICATION.md` | `connectSerial()`, `parseSerialResponse()`, `sendCmd()` |
| **Photorealistic Rotary Dial Rendering** | `desktop_app/widgets.py` | `PhotorealisticRotaryDial::paintEvent` (L967–1100), 48 perspective knurled ticks |
| **Theme Switching & Procedural Textures** | `desktop_app/themes.py`, `desktop_app/widgets.py` | `THEMES` dictionary (L12–65), `ThemeSegmentedBar` (L225–290) |
| **Peripheral Safety Isolation Whitelist** | `desktop_app/protocol.py`, `AGENTS.md` | `list_ports()` (L97–120), filters `BTHENUM` and third-party devices |
| **Firmware Flashing & Bootloader Tool** | `upload.py` | 1200-bps reset trick, Arduino CLI wrapper, COM port tracking |

