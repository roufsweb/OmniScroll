# OmniScroll - Hardware Specifications

## Microcontroller
- **Lolin ESP32-S2 Mini**
  - **Role**: Main processing unit, USB HID interface, touch sensor controller, and haptic driver.
  - **Specs**: No PSRAM, 320 KB SRAM, 4MB ROM.
  - **Features Utilized**: Native USB support, capacitive touch pins, I2C/SPI/PWM for peripherals.

## Sensors
- **MX8650 Optical Mouse Sensor**
  - **Role**: Acts as the high-precision optical encoder.
  - **Placement**: Positioned directly under or beside the freely spinning bearing to track its rotational movement.
  - **Advantage**: Provides smoother and more accurate tracking than mechanical rotary encoders, without physical wear, taking full advantage of the free-spinning bearing.

## Feedback Mechanisms
- **Haptic Engine**
  - **Type**: Linear Resonant Actuator (LRA) or Eccentric Rotating Mass (ERM) motor (ideally paired with a dedicated driver IC like DRV2605L for crisp feedback).
  - **Role**: Provides simulated physical feedback (virtual detents, button click simulation, mode switch alerts, limits).

## Mechanical Components
- **Freely Spinning Bearing**
  - **Role**: The main physical interface (the dial). It will require a suitable surface texture or tracking tape on the edge being read by the optical sensor to track effectively.
  
## Inputs
- **Capacitive Touch Input**
  - **Role**: Touch-sensitive areas serving as physical buttons (e.g., left/right click, mode switch), driven by the ESP32-S2's internal touch peripheral.

## Displays
- **0.91" OLED Display**
  - **Type**: SSD1306 (128x32 pixels, I2C)
  - **Role**: Displays current mode and system status.
  - **Connections**: 5V (VCC), GND, SDA (GPIO 35), SCL (GPIO 33).
