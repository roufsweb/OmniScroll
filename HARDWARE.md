# OmniScroll — Hardware Specifications

## Microcontroller
- **Lolin ESP32-S2 Mini**
  - **Role**: Main processing unit, USB HID interface, touch sensor controller, and haptic driver.
  - **Specs**: 320 KB SRAM, 4MB ROM. No PSRAM.
  - **Features Utilized**: Native USB support, hardware capacitive touch, high-resolution PWM.

## The Optical Bearing Encoder
Traditional rotary encoders suffer from physical wear, noise, and fixed "click" steps. OmniScroll uses a completely different paradigm:
- **Mechanics**: A freely spinning ball bearing acts as the dial. The outer ring is touched by the user.
- **Sensor (MX8650)**: An MX8650 optical mouse sensor is positioned directly beneath the bearing. It reads the micro-texture of the bearing's surface as it spins.
- **Advantage**: Infinite resolution, frictionless spinning, and no mechanical parts to break. The "clicks" are entirely simulated by the haptic motor.

## Feedback Mechanisms
- **Haptic Engine (LRA)**
  - **Type**: iPhone 6 Linear Resonant Actuator (LRA).
  - **Driver Circuit**: A PAM8403 Class-D audio amplifier module is used to safely drive the LRA. The ESP32 outputs a PWM square wave to the Left channel of the PAM8403.
  - **Role**: Provides simulated physical feedback (virtual detents, button click simulation).
- **RGB Indicator (Analog 5050)**
  - **Type**: 6-pin 5050 Analog RGB LED.
  - **Calibration**: The Red, Green, and Blue diodes have vastly different forward voltages. When using identical 470Ω resistors on a 3.3V circuit, Red draws significantly more current. The OmniScroll firmware includes extreme PWM scaling (`cal_R = 0.10`, `cal_G = 0.08`, `cal_B = 1.0`) to balance the luminosity based on fixed-ISO camera analysis.

## Pin Mapping
- **GPIO 0**: Built-in Boot Button (Used as secondary mode switch)
- **GPIO 9**: MX8650 SDIO (2-wire Serial Data I/O)
- **GPIO 11**: MX8650 SCLK (2-wire Serial Clock)
- **GPIO 12**: Capacitive Touch Input (Main click)
- **GPIO 16**: LED Green (PWM)
- **GPIO 17**: PAM8403 Haptic Motor Driver (PWM)
- **GPIO 18**: LED Red (PWM)
- **GPIO 33**: LED Blue (PWM)
