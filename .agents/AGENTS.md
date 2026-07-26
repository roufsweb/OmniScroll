# OmniScroll Agent Rules

These rules apply to all AI agents working on the OmniScroll workspace.

## Hardware Stack Context
- **MCU**: Lolin ESP32-S2 Mini.
- **MCU Specs**: No PSRAM, 320 KB SRAM, 4MB ROM.
- **Sensor**: MX8650 Optical Mouse Sensor (acting as encoder).
- **Haptics**: LRA/ERM motor driven by the ESP32.
- **Key Capability**: Native USB OTG (for USB HID).

## Coding Guidelines
- **Language**: C++ using Arduino framework or ESP-IDF (default to Arduino for rapid prototyping unless otherwise specified).
- **Style**: Keep the firmware modular. Separate the optical sensor driver, haptic driver, touch processing, and HID logic into distinct classes/files.
- **Debouncing**: Always implement robust software debouncing and baseline filtering for the capacitive touch inputs.
- **Non-blocking Code**: Ensure the main loop is non-blocking to maintain high polling rates for the optical sensor and smooth HID reporting.

## Documentation
- Always update `FEATURES.md` and `HARDWARE.md` if the hardware specifications or project goals change.
- When generating schematics or wiring diagrams, double-check the Lolin ESP32-S2 Mini pinout (e.g., ensure touch pins are actually touch-capable, ensure USB D+/D- pins are correctly mapped).
