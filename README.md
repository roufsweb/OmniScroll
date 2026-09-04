# OmniScroll

A custom haptic rotary dial built around a freely spinning ball bearing and an MX8650 optical sensor. Connects to any PC or Mac as a standard USB HID device — no drivers, no software. Configure it from any Chromium browser over the same USB cable using the Web Serial API.

---

## Configure

Plug in your OmniScroll, then open the configurator in Chrome or Edge:

**[roufsweb.github.io/OmniScroll](https://roufsweb.github.io/OmniScroll/)**

No installation required. The page connects directly to the device over USB.

---

## How It Works

A freely spinning ball bearing acts as the dial. An MX8650 optical mouse sensor sits directly beneath it, reading the surface texture of the bearing as it rotates. This replaces a traditional mechanical encoder entirely — no physical contacts, no wear, no fixed step resolution.

The "clicks" you feel are not mechanical. An LRA (Linear Resonant Actuator) driven by a PAM8403 amplifier fires a precise tone burst on each virtual detent. Frequency, duration, and intensity are all tunable from the configurator.

---

## Modes

The dial operates in configurable modes. Double-tap the touch zone to cycle between active modes.

| Mode | Action | LED Color |
|---|---|---|
| Scroll | Vertical page scroll | Blue |
| Volume | System volume control | Green |
| Timeline | Frame-by-frame (arrow keys) | Pink |
| Zoom | Ctrl+Scroll — works in any app | Amber |
| Horizontal Scroll | Side-scroll axis | Teal |
| Brightness | Display brightness keys | Yellow |
| Tabbing | Ctrl+Tab — cycle browser tabs | Violet |
| Undo / Redo | Ctrl+Z / Ctrl+Shift+Z | Red |

All 8 modes are configurable. Enable only the ones you use. Colors and haptic profiles are set per mode.

---

## Hardware

| Component | Part | Notes |
|---|---|---|
| Microcontroller | Lolin ESP32-S2 Mini | Native USB OTG, hardware touch peripheral |
| Encoder | MX8650 Optical Sensor | Reads bearing surface via 2-wire serial |
| Haptic motor | iPhone 6 LRA | Driven by PAM8403 audio amplifier |
| Indicator | Analog 5050 RGB LED | Software white-balanced via PWM calibration |
| Input | ESP32-S2 capacitive touch (GPIO 12) | Hardware-filtered, double-tap & long-press |

Full pin mapping and electrical notes are in [HARDWARE.md](HARDWARE.md).

---

## Settings

All settings are stored in the ESP32's NVS flash and survive power cycles.

- **Haptic profile** — Choose from Click, Thud, Tick, Soft, or Off. Set per mode.
- **Mode color** — Full HSB color wheel. Any color for each mode.
- **Sensor resolution** — 400 / 800 / 1200 / 1600 CPI.
- **Touch sensitivity** — Adjust the detection threshold for your hand.
- **LED brightness** — Master dimmer, 0–100%.
- **Idle dim timeout** — LED fades to 20% after a set period of inactivity.
- **Direction invert** — Reverse rotation direction per mode.

---

## Building the Firmware

Requires the [Arduino IDE](https://www.arduino.cc/en/software) with the ESP32 board package installed.

**Board settings:**

| Setting | Value |
|---|---|
| Board | Lolin S2 Mini |
| USB CDC On Boot | Disabled |
| Partition Scheme | Huge APP |

**Flash procedure:**
1. Hold the `BOOT` button on the board.
2. Press and release `RST`.
3. Release `BOOT`.
4. Upload from the Arduino IDE.

---

## License

MIT
