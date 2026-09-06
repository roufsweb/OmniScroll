# OmniScroll — Features

## Hardware Features
- **Optical Bearing Dial**: A freely spinning ball bearing is used as the main rotary interface, allowing for frictionless, infinite scrolling.
- **Optical Tracking**: An MX8650 optical mouse sensor replaces traditional mechanical encoders, translating the physical surface texture of the spinning bearing into high-resolution data.
- **Capacitive Touch Zones**: The ESP32-S2's native capacitive touch peripheral is used to turn the device housing into a solid-state button, eliminating the need for mechanical switches.
- **LRA Haptics**: An iPhone 6 Linear Resonant Actuator provides sharp, tactile virtual "detents" and clicks, entirely controlled by software.
- **Hardware RGB White Balancing**: The analog 5050 RGB LED is heavily calibrated in software to compensate for current draw discrepancies, producing accurate color mixing on a 3.3V circuit.

## Software Features
- **Triple Mode Functionality**:
  - `SCROLL MODE`: Acts as a standard vertical scroll wheel (Blue LED).
  - `VOLUME MODE`: Acts as a system media volume dial (Green LED).
  - `TIMELINE MODE`: Acts as horizontal left/right arrow keys for video editing timelines (Pink LED).
- **Native USB HID Integration**: The ESP32-S2 natively mounts to any PC or Mac as a composite Mouse/Keyboard/Consumer Control device. No drivers required.
- **Non-Blocking Architecture**: The firmware loop is fully non-blocking, ensuring the optical sensor is polled at maximum speed without being interrupted by haptic delays.

## Web Configuration
- **Web Serial API**: OmniScroll is configured using the Web Serial API. This allows Google Chrome or Microsoft Edge to communicate directly with the dial over the USB cable.
- **True Plug-and-Play**: There is no Wi-Fi to configure, no IP addresses to find, and no companion apps to install. The configurator is hosted publicly on GitHub Pages and runs entirely in the browser.
- **Live Tuning**: The Web UI allows for real-time adjustments to haptic frequency, haptic duration, touch sensitivity, and RGB mode colors.
- **Photorealistic Live Visualizer**: An interactive hardware visualizer featuring transparent alpha cutout of the physical device, real-time LED diffuser illumination matching the device's RGB state, and sleek curved directional rotation arrows indicating live wheel movement.
