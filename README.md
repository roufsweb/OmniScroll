# OmniScroll

A premium, open-source haptic rotary dial powered by the ESP32-S2 and MX8650 optical sensor. Features seamless browser-based configuration via Web Serial API, beautiful RGB mode indication, and tactile haptics.

## Features
- **Triple Mode Functionality:** Scroll Mode, Volume Mode, and Timeline Mode.
- **Native USB HID:** Instantly works on PC/Mac without drivers.
- **Capacitive Touch:** Hardware-interrupt driven capacitive touch sensor for gesture detection.
- **Haptic Feedback:** Precision tuning of haptic clicks via an LRA motor.
- **Plug-and-Play Web Configurator:** Configure colors, frequency, and touch sensitivity directly from Chrome over the USB cable!

## ⚙️ Web Configuration
OmniScroll uses the modern Web Serial API for configuration, eliminating the need to install software or connect to Wi-Fi.

Simply plug in your OmniScroll, open Chrome/Edge, and visit the live configurator:
👉 **[Configure OmniScroll](https://roufsweb.github.io/OmniScroll/)** 👈

## Hardware Stack
- **MCU:** Lolin ESP32-S2 Mini
- **Sensor:** MX8650 Optical Mouse Sensor
- **Haptics:** LRA Motor (driven by PAM8403)
- **Lighting:** Analog 5050 RGB LED (White balanced via PWM calibration)

*(See `HARDWARE.md` and `FEATURES.md` for pinouts and advanced electrical details).*

## Development
To flash the firmware, connect the board via USB, put it into BOOT mode (Hold BOOT, Press RST, Release RST, Release BOOT), and run:
```bash
python upload.py --port COMX
```
