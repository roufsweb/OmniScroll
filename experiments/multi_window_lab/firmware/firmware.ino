// =============================================================================
// OmniScroll — Native Windows Multi-Method Multitasking Lab Firmware
// -----------------------------------------------------------------------------
// 100% PURE HARDWARE USB HID — ZERO SOFTWARE RUNNING ON PC!
// Implements and demonstrates all 3 window switching options:
//
//   🟠 Mode 0 (Amber): Method A — Touch & Spin Action 6 (Touch Clutch)
//       * Normal spin (untouched): Silky smooth mouse wheel scroll.
//       * Touch top disk + spin: Holds Alt, pulses Tab / Shift+Tab with haptics.
//       * Lift finger: Releases Alt, commits window with confirmation tone!
//
//   🟣 Mode 1 (Purple): Method B — Dedicated App Switcher Mode
//       * Pure rotary control with zero touch plate required.
//       * CW rotation: Steps to next window (Alt + Esc).
//       * CCW rotation: Steps to previous window (Alt + Shift + Esc).
//
//   ⚪ Mode 2 (Cyan): Method C — Gestural Ballistic Flick Trigger
//       * Normal spin: Normal smooth mouse wheel scroll.
//       * Quick thumb flick: Summons and latches Windows switcher (Ctrl+Alt+Tab).
//       * Rotate wheel: Scrubs through open apps.
//       * Single-tap top disk: Sends Enter to lock in and switch!
//
// Mode Selection: Double-tap the top capacitive touch plate in the middle!
// =============================================================================

#include <Arduino.h>
#include <USB.h>
#include "OmniScrollHID.h"
#include <USBHIDKeyboard.h>
#include "TouchController.h"

#if !ARDUINO_USB_CDC_ON_BOOT
#include "USBCDC.h"
USBCDC USBSerial;
#define Serial USBSerial
#endif

// -----------------------------------------------------------------------------
// Pin Definitions
// -----------------------------------------------------------------------------
#define SCLK_PIN     11
#define SDIO_PIN     9
#define TOUCH_PIN    12
#define HAPTIC_PIN   17
#define LED_R_PIN    18
#define LED_G_PIN    35
#define LED_B_PIN    33

// -----------------------------------------------------------------------------
// Peripherals
// -----------------------------------------------------------------------------
OmniScrollHID   Mouse;
USBHIDKeyboard Keyboard;
TouchController touch(TOUCH_PIN, 800);

// -----------------------------------------------------------------------------
// State & Modes
// -----------------------------------------------------------------------------
enum MultitaskMethod {
    METHOD_A_TOUCH_CLUTCH = 0, // Mode 0: Touch & Spin Clutch (Amber)
    METHOD_B_DEDICATED    = 1, // Mode 1: Dedicated Rotary Mode (Purple)
    METHOD_C_GESTURE_FLICK= 2  // Mode 2: Ballistic Flick Trigger (Cyan)
};
MultitaskMethod currentMethod = METHOD_A_TOUCH_CLUTCH;

const char* METHOD_NAMES[] = {
    "METHOD_A:TOUCH_CLUTCH",
    "METHOD_B:DEDICATED_MODE",
    "METHOD_C:GESTURE_FLICK"
};

const uint8_t METHOD_COLORS[][3] = {
    {255, 140, 0  }, // Method A: Apple MagSafe Amber
    {175, 82,  222}, // Method B: Radiant Purple
    {0,   240, 220}  // Method C: Electric Cyan
};

int  accumulation   = 0;
bool touchWasActive = false;
bool altHeld        = false;
bool switcherLatched= false;
unsigned long touchStartTime = 0;
const unsigned long TOUCH_HOLD_MS = 150; // ms required before arming clutch

// Flick gesture engine state (TinyOL Phase-Energy Gate)
enum FlickState { FLICK_IDLE, FLICK_PRIMING, FLICK_COMMITTED, FLICK_COOLDOWN };
FlickState flickState = FLICK_IDLE;
int flickInitDir = 0;
int flickTravelAcc = 0;
int flickReversalAcc = 0;
unsigned long flickStateEnterMs = 0;
unsigned long flickReversalStart = 0;
unsigned long flickLastStrokeMs = 0;

// Non-blocking haptic state
bool hapticPlaying = false;
unsigned long hapticStartTime = 0;
int hapticDur = 0;

// Perceptual Gamma 2.8 lookup
const uint8_t gamma8[] = {
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  1,  1,  1,
    1,  1,  1,  1,  1,  1,  1,  1,  1,  2,  2,  2,  2,  2,  2,  2,
    2,  3,  3,  3,  3,  3,  3,  3,  4,  4,  4,  4,  4,  5,  5,  5,
    5,  6,  6,  6,  6,  7,  7,  7,  7,  8,  8,  8,  9,  9,  9, 10,
   10, 10, 11, 11, 11, 12, 12, 13, 13, 13, 14, 14, 15, 15, 16, 16,
   17, 17, 18, 18, 19, 19, 20, 20, 21, 21, 22, 22, 23, 24, 24, 25,
   25, 26, 27, 27, 28, 29, 29, 30, 31, 32, 32, 33, 34, 35, 35, 36,
   37, 38, 39, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 50,
   51, 52, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 66, 67, 68,
   69, 70, 72, 73, 74, 75, 77, 78, 79, 81, 82, 83, 85, 86, 87, 89,
   90, 92, 93, 95, 96, 98, 99,101,102,104,105,107,109,110,112,114,
  115,117,119,120,122,124,126,127,129,131,133,135,137,138,140,142,
  144,146,148,150,152,154,156,158,160,162,164,167,169,171,173,175,
  177,180,182,184,186,189,191,193,196,198,200,203,205,208,210,213,
  215,218,220,223,225,228,231,233,236,239,241,244,247,249,252,255
};

// -----------------------------------------------------------------------------
// Sensor Drivers
// -----------------------------------------------------------------------------
void mx8650_write(uint8_t reg, uint8_t data) {
    pinMode(SDIO_PIN, OUTPUT);
    reg |= 0x80;
    for (int i = 7; i >= 0; i--) {
        digitalWrite(SCLK_PIN, LOW);
        digitalWrite(SDIO_PIN, (reg >> i) & 0x01);
        digitalWrite(SCLK_PIN, HIGH);
    }
    for (int i = 7; i >= 0; i--) {
        digitalWrite(SCLK_PIN, LOW);
        digitalWrite(SDIO_PIN, (data >> i) & 0x01);
        digitalWrite(SCLK_PIN, HIGH);
    }
}

uint8_t mx8650_read(uint8_t reg) {
    pinMode(SDIO_PIN, OUTPUT);
    reg &= 0x7F;
    for (int i = 7; i >= 0; i--) {
        digitalWrite(SCLK_PIN, LOW);
        digitalWrite(SDIO_PIN, (reg >> i) & 0x01);
        digitalWrite(SCLK_PIN, HIGH);
    }
    pinMode(SDIO_PIN, INPUT);
    uint8_t data = 0;
    delayMicroseconds(10);
    for (int i = 7; i >= 0; i--) {
        digitalWrite(SCLK_PIN, LOW);
        delayMicroseconds(1);
        digitalWrite(SCLK_PIN, HIGH);
        data |= (digitalRead(SDIO_PIN) << i);
    }
    return data;
}

// -----------------------------------------------------------------------------
// Haptics & LED
// -----------------------------------------------------------------------------
void playHapticTone(int freq, int dur) {
    tone(HAPTIC_PIN, freq);
    hapticStartTime = millis();
    hapticDur = dur;
    hapticPlaying = true;
}

void playDetentClick(int freq = 240, int dur = 14) {
    playHapticTone(freq, dur);
}

void playModeSwitchHaptic() {
    tone(HAPTIC_PIN, 220);
    delay(18);
    noTone(HAPTIC_PIN);
    delay(20);
    tone(HAPTIC_PIN, 360);
    delay(28);
    noTone(HAPTIC_PIN);
}

void setLed(uint8_t r, uint8_t g, uint8_t b) {
    ledcWrite(LED_R_PIN, gamma8[r]);
    ledcWrite(LED_G_PIN, gamma8[g]);
    ledcWrite(LED_B_PIN, gamma8[b]);
}

void applyModeColor() {
    setLed(METHOD_COLORS[currentMethod][0],
           METHOD_COLORS[currentMethod][1],
           METHOD_COLORS[currentMethod][2]);
    Serial.printf("MODE:%d:%s\n", (int)currentMethod, METHOD_NAMES[currentMethod]);
}

// -----------------------------------------------------------------------------
// Setup
// -----------------------------------------------------------------------------
void setup() {
    USB.productName("OmniScroll-Lab");
    USB.manufacturerName("OmniScroll");
    USB.serialNumber("OMNI-007");
    USB.VID(0x303A);
    USB.PID(0x4F5B);

    Mouse.begin();
    Keyboard.begin();
#if !ARDUINO_USB_CDC_ON_BOOT
    USBSerial.begin();
#endif
    USB.begin();
    Serial.begin(115200);

    pinMode(SCLK_PIN, OUTPUT);
    digitalWrite(SCLK_PIN, HIGH);

    pinMode(HAPTIC_PIN, OUTPUT);
    digitalWrite(HAPTIC_PIN, LOW);

    ledcAttach(LED_R_PIN, 5000, 8);
    ledcAttach(LED_G_PIN, 5000, 8);
    ledcAttach(LED_B_PIN, 5000, 8);

    touch.begin();
    touch.setThreshold(800);

    delay(50);
    mx8650_write(0x06, 0x80); // Reset
    delay(10);
    mx8650_write(0x05, 0xA0); // Continuous sleep-disabled polling
    mx8650_write(0x06, 0x01); // 800 CPI
    delay(10);

    applyModeColor();
    playModeSwitchHaptic();
    Serial.println("INIT:OMNISCROLL_MULTITASK_LAB:READY");
}

// -----------------------------------------------------------------------------
// Main Loop
// -----------------------------------------------------------------------------
void loop() {
    // 1. Non-blocking haptic stop
    if (hapticPlaying && (millis() - hapticStartTime >= (unsigned long)hapticDur)) {
        noTone(HAPTIC_PIN);
        hapticPlaying = false;
    }

    touch.update();
    bool isTouched = touch.isTouched();

    // 2. Double-Tap in Middle: Cycles between the 3 Multitasking Methods
    if (touch.isDoubleTapped()) {
        if (altHeld) {
            Keyboard.releaseAll();
            altHeld = false;
        }
        switcherLatched = false;

        currentMethod = (MultitaskMethod)((currentMethod + 1) % 3);
        accumulation = 0;
        playModeSwitchHaptic();
        applyModeColor();
        delay(120);
        return;
    }

    // Single-Tap in Method C commits the latched switcher
    if (currentMethod == METHOD_C_GESTURE_FLICK && touch.isSingleTapped()) {
        if (switcherLatched) {
            Keyboard.press(KEY_RETURN);
            delay(5);
            Keyboard.releaseAll();
            switcherLatched = false;
            playHapticTone(320, 25);
            applyModeColor();
            Serial.println("ACTION:GESTURE_SWITCHER:COMMIT");
        }
    }

    // 3. Touch Transitions (For Method A: Clutch)
    if (isTouched && !touchWasActive) {
        touchWasActive = true;
        touchStartTime = millis();
    } else if (!isTouched && touchWasActive) {
        touchWasActive = false;

        // METHOD A: Finger lifted -> Cleanly release Alt & commit selected window!
        if (currentMethod == METHOD_A_TOUCH_CLUTCH && altHeld) {
            Keyboard.releaseAll();
            altHeld = false;
            playHapticTone(320, 22);
            applyModeColor();
            Serial.println("ACTION:TOUCH_CLUTCH:COMMIT");
        }
    }

    // 4. Optical Sensor Reading
    uint8_t motion = mx8650_read(0x02);
    if (motion & 0x80) {
        int8_t dx = -(int8_t)mx8650_read(0x03);
        if (dx != 0) {
            unsigned long now = millis();

            // =================================================================
            // 🟠 METHOD A: Touch & Spin Action 6 (Touch Clutch Alt+Tab)
            // =================================================================
            if (currentMethod == METHOD_A_TOUCH_CLUTCH) {
                // If finger is touching top plate for >= 150ms hold gate
                if (isTouched && (now - touchStartTime >= TOUCH_HOLD_MS)) {
                    // Arm clutch if not already armed
                    if (!altHeld) {
                        Keyboard.press(KEY_LEFT_ALT);
                        altHeld = true;
                        setLed(0, 240, 220); // Cyan while scrubbing
                    }

                    accumulation += dx;
                    int thr = 14;
                    while (accumulation >= thr) {
                        playDetentClick(260, 14);
                        Keyboard.press(KEY_TAB);
                        delay(5);
                        Keyboard.release(KEY_TAB);
                        Serial.println("CLUTCH:STEP:FWD");
                        accumulation -= thr;
                    }
                    while (accumulation <= -thr) {
                        playDetentClick(220, 14);
                        Keyboard.press(KEY_LEFT_SHIFT);
                        Keyboard.press(KEY_TAB);
                        delay(5);
                        Keyboard.release(KEY_TAB);
                        Keyboard.release(KEY_LEFT_SHIFT);
                        Serial.println("CLUTCH:STEP:REV");
                        accumulation += thr;
                    }
                } else {
                    // Not touching top plate: Standard smooth mouse wheel scroll!
                    Mouse.scroll(Mouse.isHighRes() ? (int16_t)(dx * 12) : (int16_t)(dx > 0 ? 1 : -1));
                    accumulation = 0;
                }
            }

            // =================================================================
            // 🟣 METHOD B: Dedicated Mode (Direct Rotary Alt+Esc Window Cycle)
            // =================================================================
            else if (currentMethod == METHOD_B_DEDICATED) {
                accumulation += dx;
                int thr = 16;
                while (accumulation >= thr) {
                    playDetentClick(190, 20);
                    Keyboard.press(KEY_LEFT_ALT);
                    Keyboard.press(KEY_ESC);
                    delay(6);
                    Keyboard.releaseAll();
                    Serial.println("DEDICATED:WINDOW:NEXT");
                    accumulation -= thr;
                }
                while (accumulation <= -thr) {
                    playDetentClick(190, 20);
                    Keyboard.press(KEY_LEFT_ALT);
                    Keyboard.press(KEY_LEFT_SHIFT);
                    Keyboard.press(KEY_ESC);
                    delay(6);
                    Keyboard.releaseAll();
                    Serial.println("DEDICATED:WINDOW:PREV");
                    accumulation += thr;
                }
            }

            // =================================================================
            // ⚪ METHOD C: Ballistic Flick Trigger (TinyOL Gesture Engine)
            // =================================================================
            else if (currentMethod == METHOD_C_GESTURE_FLICK) {
                if (switcherLatched) {
                    // Switcher is open: knob scrubs through the open cards!
                    accumulation += dx;
                    int thr = 14;
                    while (accumulation >= thr) {
                        playDetentClick(240, 14);
                        Keyboard.press(KEY_TAB);
                        delay(5);
                        Keyboard.release(KEY_TAB);
                        accumulation -= thr;
                    }
                    while (accumulation <= -thr) {
                        playDetentClick(240, 14);
                        Keyboard.press(KEY_LEFT_SHIFT);
                        Keyboard.press(KEY_TAB);
                        delay(5);
                        Keyboard.release(KEY_TAB);
                        Keyboard.release(KEY_LEFT_SHIFT);
                        accumulation += thr;
                    }
                } else {
                    // Normal state: Process flick gesture vs smooth scroll
                    int dir = dx > 0 ? 1 : -1;
                    flickLastStrokeMs = now;

                    // TinyOL Kinematic Ballistic Flick Detector
                    if (flickState == FLICK_IDLE) {
                        if (abs(dx) >= 3) {
                            flickState = FLICK_PRIMING;
                            flickInitDir = dir;
                            flickTravelAcc = abs(dx);
                            flickReversalAcc = 0;
                            flickStateEnterMs = now;
                        }
                    } else if (flickState == FLICK_PRIMING) {
                        if (dir == flickInitDir) {
                            flickTravelAcc += abs(dx);
                            if (flickTravelAcc >= 25) { // 25 counts commit
                                flickState = FLICK_COMMITTED;
                                flickStateEnterMs = now;
                            }
                        } else {
                            flickState = FLICK_IDLE;
                        }
                    } else if (flickState == FLICK_COMMITTED) {
                        if (dir != flickInitDir) {
                            if (flickReversalAcc == 0) flickReversalStart = now;
                            flickReversalAcc += abs(dx);

                            // Snap Energy check: R >= 20 counts recoil in < 75ms dwell
                            if (flickReversalAcc >= 20 && (now - flickReversalStart <= 75)) {
                                // FLICK GESTURE DETECTED! Summon & latch switcher!
                                switcherLatched = true;
                                playHapticTone(300, 30);
                                setLed(255, 255, 255); // Flash white

                                // Native Windows Ctrl+Alt+Tab locks switcher open!
                                Keyboard.press(KEY_LEFT_CTRL);
                                Keyboard.press(KEY_LEFT_ALT);
                                Keyboard.press(KEY_TAB);
                                delay(10);
                                Keyboard.releaseAll();

                                Serial.println("GESTURE:FLICK:SWITCHER_LATCHED");
                                flickState = FLICK_COOLDOWN;
                                flickStateEnterMs = now;
                            }
                        }
                    }

                    // Standard mouse scroll if not latched
                    if (!switcherLatched) {
                        Mouse.scroll(Mouse.isHighRes() ? (int16_t)(dx * 12) : (int16_t)(dx > 0 ? 1 : -1));
                    }
                }
            }
        }
    }

    // Cooldown reset for gesture engine
    if (flickState == FLICK_COOLDOWN && (millis() - flickStateEnterMs > 250)) {
        flickState = FLICK_IDLE;
    }

    delay(2);
}
