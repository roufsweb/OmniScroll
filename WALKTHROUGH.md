# OmniScroll Firmware Walkthrough

This document covers the latest updates to the OmniScroll firmware.

## What was Changed
- **Triple-Mode Input**: The wheel now acts as a standard Scroll Wheel, a Volume Knob, and a Timeline Scrubber (for DaVinci Resolve/Premiere Pro).
- **Capacitive Touch Mode Switcher**: Added double-tap detection on a capacitive touch wire (GPIO 7) to cycle between the three modes.
- **Robust TouchController Module**: Created `TouchController.h` and `.cpp` to implement a slow-rolling baseline filter. This makes the capacitive touch extremely reliable and prevents false triggers from environmental drift.
- **OLED Display Integration**: Uses an I2C SSD1306 display to show the current mode.

## Testing & Verification
- **USB HID Stack**: The TinyUSB stack was correctly initialized *after* all HID interfaces (`Mouse`, `Keyboard`, `ConsumerControl`) and `USBSerial` were instantiated.
- **Double Tap Detection**: Tuned the double-tap maximum delay to 400ms and minimum debounce to 50ms. Verified switching via the touch wire.
