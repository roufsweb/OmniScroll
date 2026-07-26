# OmniScroll - Features

## Core Features
- **Optical Bearing Dial**: A freely spinning bearing used as a multi-function scroll wheel.
- **Optical Encoder (MX8650)**: High-resolution optical tracking using a mouse sensor instead of a traditional mechanical or magnetic encoder, allowing for smooth, precise, and freely spinning movement.
- **Capacitive Touch Buttons**: Utilizing the ESP32-S2's built-in capacitive touch capabilities to turn the housing or specific zones into buttons, eliminating the need for physical mechanical switches.
- **Haptic Feedback**: Integrated haptic engine (LRA or ERM) to simulate physical detents, clicks, and multi-function feedback dynamically based on the current mode.
- **Multi-Function Modes**: Configurable modes for the dial (e.g., standard vertical scroll, horizontal scroll, volume control, zoom, timeline scrubbing).
- **OLED Status Display**: Integrated 0.91" 128x32 OLED display (I2C) for visual feedback on the current active mode.
- **USB HID Integration**: The ESP32-S2 natively supports USB OTG, allowing it to act as a plug-and-play USB Human Interface Device (Mouse/Keyboard/Media Controller).
