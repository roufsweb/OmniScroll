#include <Arduino.h>
#include <USB.h>
#include <USBHIDMouse.h>
#include <USBHIDConsumerControl.h>
#include <USBHIDKeyboard.h>
#include "TouchController.h"

// TinyUSB Serial
USBCDC USBSerial;
#define Serial USBSerial

// Sensor, Button, Haptic & LED Pins
#define SCLK_PIN 11
#define SDIO_PIN 9
#define BUTTON_PIN 0
#define TOUCH_PIN 12
#define HAPTIC_PIN 17

// RGB LED Pins
#define LED_R_PIN 18
#define LED_G_PIN 16
#define LED_B_PIN 33
#define COMMON_ANODE false // Set to true if tying LED Anodes to 3.3V instead of Cathodes to GND

USBHIDMouse Mouse;
USBHIDConsumerControl ConsumerControl;
USBHIDKeyboard Keyboard;

TouchController touch(TOUCH_PIN, 800);

enum Mode { MODE_SCROLL, MODE_VOLUME, MODE_TIMELINE };
Mode currentMode = MODE_SCROLL;

bool buttonState = HIGH;
bool lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;

int accumulationX = 0;
unsigned long lastScrollTime = 0;

const int SCROLL_THRESHOLD = 10;
const int VOLUME_THRESHOLD = 25; 
const int TIMELINE_THRESHOLD = 15;

// Haptic Tuning Variables
int hapticFreq = 200;
int hapticDuration = 30;
bool hapticEnabled = true;

// RGB Mode Colors
uint8_t colorScroll[3] = {0, 0, 255};
uint8_t colorVolume[3] = {0, 255, 0};
uint8_t colorTimeline[3] = {255, 0, 128};

// Software Color Calibration (White Balance)
// Calculated based on visual fixed-ISO camera analysis
float cal_R = 0.10; // Red is very bright, choke to 10%
float cal_G = 0.08; // Green is the brightest, choke to 8%
float cal_B = 1.0;  // Blue is very dim, stays at 100%

// Non-blocking haptic state
unsigned long hapticStartTime = 0;
bool hapticPlaying = false;

// Wi-Fi and WebServer removed in favor of Web Serial API

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

void setLedColor(uint8_t r, uint8_t g, uint8_t b) {
  // Apply hardware white-balance calibration
  uint8_t final_R = r * cal_R;
  uint8_t final_G = g * cal_G;
  uint8_t final_B = b * cal_B;

  if (COMMON_ANODE) {
    analogWrite(LED_R_PIN, 255 - final_R);
    analogWrite(LED_G_PIN, 255 - final_G);
    analogWrite(LED_B_PIN, 255 - final_B);
  } else {
    analogWrite(LED_R_PIN, final_R);
    analogWrite(LED_G_PIN, final_G);
    analogWrite(LED_B_PIN, final_B);
  }
}

void playHapticClick() {
  if (!hapticEnabled) return;
  // Prevent spamming tone() which crashes the ESP32 hardware timer
  if (!hapticPlaying) {
    tone(HAPTIC_PIN, hapticFreq); 
    hapticStartTime = millis();
    hapticPlaying = true;
  }
}

void cycleMode() {
    playHapticClick();

    if (currentMode == MODE_SCROLL) {
        currentMode = MODE_VOLUME;
        setLedColor(colorVolume[0], colorVolume[1], colorVolume[2]);
        Serial.println("Switched Mode to: VOLUME");
    } else if (currentMode == MODE_VOLUME) {
        currentMode = MODE_TIMELINE;
        setLedColor(colorTimeline[0], colorTimeline[1], colorTimeline[2]);
        Serial.println("Switched Mode to: TIMELINE");
    } else {
        currentMode = MODE_SCROLL;
        setLedColor(colorScroll[0], colorScroll[1], colorScroll[2]);
        Serial.println("Switched Mode to: SCROLL");
    }
    accumulationX = 0; 
}

// Hex color conversion removed (handled by UI now)

void setup() {
  Mouse.begin();
  ConsumerControl.begin();
  Keyboard.begin();
  USBSerial.begin();
  USB.begin();
  
  Serial.begin(115200);
  delay(2000); 
  
  Serial.println("\n--- OmniScroll Booting ---");
  
  pinMode(HAPTIC_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(SCLK_PIN, OUTPUT);
  digitalWrite(SCLK_PIN, HIGH);
  
  pinMode(LED_R_PIN, OUTPUT);
  pinMode(LED_G_PIN, OUTPUT);
  pinMode(LED_B_PIN, OUTPUT);
  setLedColor(0, 0, 255); // Default Mode: SCROLL (Blue)
  
  touch.begin();
  Serial.printf("Touch Sensor Base Reading: %ld\n", touch.getBaseline());
  
  delay(1000); 
  uint8_t pid = mx8650_read(0x00); 
  Serial.printf("OmniScroll HID Ready! PID: 0x%02X\n", pid);
  Serial.println("Current Mode: SCROLL");
  playHapticClick();
}

void loop() {
  // Handle non-blocking haptic tone stop
  if (hapticPlaying && (millis() - hapticStartTime >= hapticDuration)) {
      noTone(HAPTIC_PIN);
      hapticPlaying = false;
  }
  
  static unsigned long lastLogTime = 0;
  if (millis() - lastLogTime > 1000) {
      long rawTouch = touch.getLastReading();
      long baseline = touch.getBaseline();
      long delta = abs(rawTouch - baseline);
      lastLogTime = millis();
  }

  bool inLockout = (millis() - lastScrollTime <= 200);
  if (inLockout) {
      touch.reset(); 
  } else {
      touch.update(); 
  }
  
  if (touch.isDoubleTapped()) {
      Serial.println("Double Tap Detected!");
      cycleMode();
  }
  
  bool reading = digitalRead(BUTTON_PIN);
  if (reading != lastButtonState) {
    lastDebounceTime = millis();
  }
  if ((millis() - lastDebounceTime) > debounceDelay) {
    if (reading != buttonState) {
      buttonState = reading;
      if (buttonState == LOW) { 
        Serial.println("Physical Button Pressed!");
        cycleMode();
      }
    }
  }
  lastButtonState = reading;

  uint8_t motion = mx8650_read(0x02);
  if (motion & 0x80) { 
    int8_t dx = (int8_t)mx8650_read(0x03);
    if (dx != 0) {
      accumulationX += dx;
      lastScrollTime = millis(); // Reverted to original logic (tracks ALL movement for lockout window)
      
      if (currentMode == MODE_SCROLL) {
        if (accumulationX >= SCROLL_THRESHOLD) {
          Mouse.move(0, 0, -1); 
          playHapticClick(); 
          accumulationX -= SCROLL_THRESHOLD;
        } else if (accumulationX <= -SCROLL_THRESHOLD) {
          Mouse.move(0, 0, 1); 
          playHapticClick(); 
          accumulationX += SCROLL_THRESHOLD;
        }
      } 
      else if (currentMode == MODE_VOLUME) {
        if (accumulationX >= VOLUME_THRESHOLD) {
          ConsumerControl.press(CONSUMER_CONTROL_VOLUME_DECREMENT); 
          delay(2);
          ConsumerControl.release();
          playHapticClick(); 
          accumulationX -= VOLUME_THRESHOLD;
        } else if (accumulationX <= -VOLUME_THRESHOLD) {
          ConsumerControl.press(CONSUMER_CONTROL_VOLUME_INCREMENT);
          delay(2);
          ConsumerControl.release();
          playHapticClick(); 
          accumulationX += VOLUME_THRESHOLD;
        }
      }
      else if (currentMode == MODE_TIMELINE) {
        if (accumulationX >= TIMELINE_THRESHOLD) {
          Keyboard.press(KEY_LEFT_ARROW); 
          delay(2);
          Keyboard.release(KEY_LEFT_ARROW);
          playHapticClick(); 
          accumulationX -= TIMELINE_THRESHOLD;
        } else if (accumulationX <= -TIMELINE_THRESHOLD) {
          Keyboard.press(KEY_RIGHT_ARROW);
          delay(2);
          Keyboard.release(KEY_RIGHT_ARROW);
          playHapticClick(); 
          accumulationX += TIMELINE_THRESHOLD;
        }
      }
    }
  }
  
  if (Serial.available() > 0) {
      String cmd = Serial.readStringUntil('\n');
      cmd.trim();
      
      if (cmd == "GET:STATUS") {
          String json = "{";
          json += "\"mode\":";
          json += (currentMode == MODE_SCROLL ? "\"SCROLL\"" : (currentMode == MODE_VOLUME ? "\"VOLUME\"" : "\"TIMELINE\""));
          json += ", \"touch\":";
          json += String(touch.getLastReading());
          json += ", \"baseline\":";
          json += String(touch.getBaseline());
          json += ", \"accX\":";
          json += String(accumulationX);
          json += "}";
          Serial.println("STATUS:" + json);
      }
      else if (cmd == "GET:CONFIG") {
          String json = "{";
          json += "\"freq\":" + String(hapticFreq);
          json += ", \"dur\":" + String(hapticDuration);
          json += ", \"thr\":" + String(touch.getThreshold());
          json += ", \"en\":" + String(hapticEnabled ? 1 : 0);
          
          char hexBuf[32];
          sprintf(hexBuf, ",\"cs\":\"%02x%02x%02x\",\"cv\":\"%02x%02x%02x\",\"ct\":\"%02x%02x%02x\"", 
                  colorScroll[0], colorScroll[1], colorScroll[2],
                  colorVolume[0], colorVolume[1], colorVolume[2],
                  colorTimeline[0], colorTimeline[1], colorTimeline[2]);
          json += String(hexBuf);
          json += "}";
          Serial.println("CONFIG:" + json);
      }
      else if (cmd == "TEST:HAPTIC") {
          hapticPlaying = false; 
          noTone(HAPTIC_PIN);
          playHapticClick();
      }
      else if (cmd.startsWith("SET:")) {
          // Format: SET:FREQ:200,DUR:30,THR:800,EN:1,CS:0000FF,CV:00FF00,CT:FF0080
          String params = cmd.substring(4);
          int nextComma = -1;
          do {
            nextComma = params.indexOf(',');
            String pair = (nextComma == -1) ? params : params.substring(0, nextComma);
            
            int colon = pair.indexOf(':');
            if (colon != -1) {
              String key = pair.substring(0, colon);
              String val = pair.substring(colon + 1);
              
              if (key == "FREQ") hapticFreq = val.toInt();
              else if (key == "DUR") hapticDuration = val.toInt();
              else if (key == "THR") touch.setThreshold(val.toInt());
              else if (key == "EN") hapticEnabled = (val == "1");
              else if (key == "CS") {
                long c = strtol(val.c_str(), NULL, 16);
                colorScroll[0] = (c >> 16) & 0xFF; colorScroll[1] = (c >> 8) & 0xFF; colorScroll[2] = c & 0xFF;
              }
              else if (key == "CV") {
                long c = strtol(val.c_str(), NULL, 16);
                colorVolume[0] = (c >> 16) & 0xFF; colorVolume[1] = (c >> 8) & 0xFF; colorVolume[2] = c & 0xFF;
              }
              else if (key == "CT") {
                long c = strtol(val.c_str(), NULL, 16);
                colorTimeline[0] = (c >> 16) & 0xFF; colorTimeline[1] = (c >> 8) & 0xFF; colorTimeline[2] = c & 0xFF;
              }
            }
            if (nextComma != -1) params = params.substring(nextComma + 1);
          } while (nextComma != -1);
          
          if (currentMode == MODE_SCROLL) setLedColor(colorScroll[0], colorScroll[1], colorScroll[2]);
          else if (currentMode == MODE_VOLUME) setLedColor(colorVolume[0], colorVolume[1], colorVolume[2]);
          else if (currentMode == MODE_TIMELINE) setLedColor(colorTimeline[0], colorTimeline[1], colorTimeline[2]);

          hapticPlaying = false; 
          noTone(HAPTIC_PIN);
          playHapticClick();
      }
  }
  
  delay(1); 
}
