# OmniScroll - Hardware Specifications

## Microcontroller
- **Lolin ESP32-S2 Mini**
  - **Role**: Main processing unit, USB HID interface, touch sensor controller, and haptic driver.
  - **Specs**: No PSRAM, 320 KB SRAM, 4MB ROM.
  - **Features Utilized**: Native USB support, capacitive touch pins, PWM for peripherals.

## Pin Mapping
- **GPIO 0**: Built-in Boot Button (Used as general-purpose physical input button)
- **GPIO 9**: MX8650 SDIO (Serial Data I/O)
- **GPIO 11**: MX8650 SCLK (Serial Clock)
- **GPIO 12**: Capacitive Touch Input
- **GPIO 17**: Haptic Motor Driver (PWM to PAM8403 Left Channel)

## Sensors
- **MX8650 Optical Mouse Sensor**
  - **Role**: Acts as the high-precision optical encoder.
  - **Placement**: Positioned directly under or beside the freely spinning bearing to track its rotational movement.
  - **Advantage**: Provides smoother and more accurate tracking than mechanical rotary encoders, without physical wear, taking full advantage of the free-spinning bearing.

## Feedback Mechanisms
- **Haptic Engine**
  - **Type**: iPhone 6 Linear Resonant Actuator (LRA).
  - **Driver**: PAM8403 audio amplifier module (Left channel connected to GPIO 17).
  - **Role**: Provides simulated physical feedback (virtual detents, button click simulation, mode switch alerts).
- **RGB Mode Indicator**
  - **Type**: 6-pin 5050 Analog RGB LED.
  - **Wiring**: Red (GPIO 18), Green (GPIO 16), Blue (GPIO 33) via 470Ω resistors.
  - **Role**: Visually indicates the currently active scroll mode.

## Mechanical Components
- **Freely Spinning Bearing**
  - **Role**: The main physical interface (the dial). It will require a suitable surface texture or tracking tape on the edge being read by the optical sensor to track effectively.
  
## Inputs
- **Capacitive Touch Input**
  - **Role**: Touch-sensitive areas serving as physical buttons (e.g., left/right click, mode switch), driven by the ESP32-S2's internal touch peripheral (GPIO 12).
- **Physical Button**
  - **Role**: Fallback or secondary button using the ESP32-S2's built-in BOOT button (GPIO 0).
