#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <USB.h>
#include <USBHIDMouse.h>
#include <USBHIDConsumerControl.h>
#include <USBHIDKeyboard.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32
#define OLED_RESET    -1 

// I2C Pins for ESP32-S2
#define SDA_PIN 35
#define SCL_PIN 33

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Sensor & Button Pins
#define SCLK_PIN 11
#define SDIO_PIN 12
#define BUTTON_PIN 0

USBHIDMouse Mouse;
USBHIDConsumerControl ConsumerControl;
USBHIDKeyboard Keyboard;

enum Mode { MODE_SCROLL, MODE_VOLUME, MODE_TIMELINE };
Mode currentMode = MODE_SCROLL;

bool buttonState = HIGH;
bool lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;

// Accumulator for smooth, non-stuttery movement
int accumulationX = 0;

// Thresholds for how much optical movement equals 1 "tick"
const int SCROLL_THRESHOLD = 10;
const int VOLUME_THRESHOLD = 25; 
const int TIMELINE_THRESHOLD = 15; // Smooth but precise for scrubbing frames

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

void updateDisplay(const char* modeName) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("OmniScroll Mode:");
  display.setTextSize(2);
  display.setCursor(0, 16);
  display.println(modeName);
  display.display();
}

void setup() {
  Serial.begin(115200);
  delay(2000); // Wait for Serial to settle
  
  Serial.println("\n--- OmniScroll Booting ---");
  Serial.println("Initializing I2C on SDA: 35, SCL: 33");
  Wire.begin(SDA_PIN, SCL_PIN);

  Serial.println("Scanning I2C bus...");
  byte error, address;
  int nDevices = 0;
  for(address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();
    if (error == 0) {
      Serial.print("I2C device found at address 0x");
      if (address < 16) Serial.print("0");
      Serial.println(address, HEX);
      nDevices++;
    } else if (error == 4) {
      Serial.print("Unknown error at address 0x");
      if (address < 16) Serial.print("0");
      Serial.println(address, HEX);
    }
  }
  if (nDevices == 0) {
    Serial.println("No I2C devices found\n");
  } else {
    Serial.println("done\n");
  }
  
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) { 
    Serial.println("SSD1306 allocation failed or device not found at 0x3C");
  } else {
    display.clearDisplay();
    display.display();
  }
  
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(SCLK_PIN, OUTPUT);
  digitalWrite(SCLK_PIN, HIGH);
  
  // Initialize USB HID
  Mouse.begin();
  ConsumerControl.begin();
  Keyboard.begin();
  USB.begin(); // Start the TinyUSB stack
  
  delay(1000); 
  uint8_t pid = mx8650_read(0x00); 
  Serial.printf("OmniScroll HID Ready! PID: 0x%02X\n", pid);
  Serial.println("Current Mode: SCROLL");
  updateDisplay("SCROLL");
}

void loop() {
  bool reading = digitalRead(BUTTON_PIN);
  if (reading != lastButtonState) {
    lastDebounceTime = millis();
  }
  
  if ((millis() - lastDebounceTime) > debounceDelay) {
    if (reading != buttonState) {
      buttonState = reading;
      if (buttonState == LOW) { 
        // Cycle through the 3 modes
        if (currentMode == MODE_SCROLL) {
            currentMode = MODE_VOLUME;
            Serial.println("Switched Mode to: VOLUME");
            updateDisplay("VOLUME");
        } else if (currentMode == MODE_VOLUME) {
            currentMode = MODE_TIMELINE;
            Serial.println("Switched Mode to: TIMELINE");
            updateDisplay("TIMELINE");
        } else {
            currentMode = MODE_SCROLL;
            Serial.println("Switched Mode to: SCROLL");
            updateDisplay("SCROLL");
        }
        accumulationX = 0; 
      }
    }
  }
  lastButtonState = reading;

  uint8_t motion = mx8650_read(0x02);
  if (motion & 0x80) { 
    int8_t dx = (int8_t)mx8650_read(0x03);
    
    if (dx != 0) {
      accumulationX += dx;
      
      if (currentMode == MODE_SCROLL) {
        if (accumulationX >= SCROLL_THRESHOLD) {
          Mouse.move(0, 0, -1); 
          accumulationX -= SCROLL_THRESHOLD;
        } else if (accumulationX <= -SCROLL_THRESHOLD) {
          Mouse.move(0, 0, 1); 
          accumulationX += SCROLL_THRESHOLD;
        }
      } 
      else if (currentMode == MODE_VOLUME) {
        if (accumulationX >= VOLUME_THRESHOLD) {
          ConsumerControl.press(CONSUMER_CONTROL_VOLUME_DECREMENT); 
          ConsumerControl.release();
          accumulationX -= VOLUME_THRESHOLD;
        } else if (accumulationX <= -VOLUME_THRESHOLD) {
          ConsumerControl.press(CONSUMER_CONTROL_VOLUME_INCREMENT);
          ConsumerControl.release();
          accumulationX += VOLUME_THRESHOLD;
        }
      }
      else if (currentMode == MODE_TIMELINE) {
        if (accumulationX >= TIMELINE_THRESHOLD) {
          Keyboard.press(KEY_LEFT_ARROW); 
          Keyboard.release(KEY_LEFT_ARROW);
          accumulationX -= TIMELINE_THRESHOLD;
        } else if (accumulationX <= -TIMELINE_THRESHOLD) {
          Keyboard.press(KEY_RIGHT_ARROW);
          Keyboard.release(KEY_RIGHT_ARROW);
          accumulationX += TIMELINE_THRESHOLD;
        }
      }
    }
  }
  
  delay(5); 
}
