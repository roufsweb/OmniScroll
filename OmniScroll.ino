// OmniScroll Firmware V2
// Architecture: Dynamic mode list with NVS persistence, 8 configurable modes,
// haptic profiles, LED brightness, idle dim, MX8650 CPI control.

#include <Arduino.h>
#include <USB.h>
#include "OmniScrollHID.h"
#include <USBHIDConsumerControl.h>
#include <USBHIDKeyboard.h>
#include <Preferences.h>
#include "TouchController.h"

// TinyUSB CDC Serial
USBCDC USBSerial;
#define Serial USBSerial

OmniScrollHID Mouse;

// -------------------------------------------------------
// Pin Definitions
// -------------------------------------------------------
#define SCLK_PIN     11
#define SDIO_PIN     9
#define BUTTON_PIN   0
#define TOUCH_PIN    12
#define HAPTIC_PIN   17
#define LED_R_PIN    18
#define LED_G_PIN    16
#define LED_B_PIN    33
#define COMMON_ANODE false

// -------------------------------------------------------
// HID & Peripherals
// -------------------------------------------------------
USBHIDConsumerControl ConsumerControl;
USBHIDKeyboard       Keyboard;
Preferences          prefs;
TouchController      touch(TOUCH_PIN, 800);

// -------------------------------------------------------
// Haptic Profiles
// -------------------------------------------------------
struct HapticProfile {
    const char* name;
    int freq;
    int dur;
};

const HapticProfile HAPTIC_PROFILES[] = {
    {"Click", 200, 20},  // 0 — Sharp, precise detent
    {"Thud",  120, 45},  // 1 — Deep, satisfying bump
    {"Tick",  300, 10},  // 2 — Light, high-speed ratchet
    {"Soft",  150, 25},  // 3 — Gentle, quiet nudge
    {"Off",   0,   0 },  // 4 — Silent
};
#define NUM_PROFILES 5

// -------------------------------------------------------
// Mode Configuration — V2 Dynamic Mode List
// -------------------------------------------------------
#define MAX_MODES 8

struct ModeConfig {
    char    name[12];
    uint8_t color[3];
    uint8_t hapticProfile;
    bool    enabled;
    bool    invertDirection;
    int     threshold;
};

// Default mode list — loaded from NVS on boot, overwritten by user config
ModeConfig modeList[MAX_MODES] = {
    {"SCROLL",     {0,   0,   255}, 0, true,  false, 10},
    {"VOLUME",     {0,   255, 0  }, 3, true,  false, 25},
    {"TIMELINE",   {255, 0,   128}, 0, true,  false, 15},
    {"ZOOM",       {255, 149, 0  }, 0, false, false, 15},
    {"H_SCROLL",   {0,   194, 168}, 2, false, false, 10},
    {"BRIGHTNESS", {255, 215, 0  }, 3, false, false, 20},
    {"TABBING",    {155, 89,  182}, 0, false, false, 20},
    {"UNDO_REDO",  {231, 76,  60 }, 1, false, false, 15},
};

int  currentModeIdx  = 0;
int  accumulationX   = 0;
unsigned long lastScrollTime = 0;

// -------------------------------------------------------
// Haptic State
// -------------------------------------------------------
unsigned long hapticStartTime = 0;
int  hapticDurActive  = 0; // duration saved at the time of firing
bool hapticPlaying    = false;

// -------------------------------------------------------
// LED State
// -------------------------------------------------------
// Software white-balance calibration (adjustable via Web Serial)
float cal_R = 0.10f;
float cal_G = 0.08f;
float cal_B = 1.0f;
float ledBrightness       = 1.0f; // 0.0–1.0 master dimmer
unsigned long lastActivityTime = 0;
int   idleDimMs           = 30000; // 0 = disabled
bool  isIdleDimmed        = false;

// -------------------------------------------------------
// Sensor
// -------------------------------------------------------
uint8_t sensorCPI = 1; // 0=400, 1=800, 2=1200, 3=1600

// -------------------------------------------------------
// Button Debounce
// -------------------------------------------------------
bool buttonState = HIGH, lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;


// =======================================================
// MX8650 Optical Sensor
// =======================================================
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

void setSensorCPI(uint8_t level) {
    mx8650_write(0x06, level & 0x03);
}


// =======================================================
// LED
// =======================================================
void setLedColor(uint8_t r, uint8_t g, uint8_t b) {
    float dim = isIdleDimmed ? 0.2f : 1.0f;
    uint8_t fR = (uint8_t)(r * cal_R * ledBrightness * dim);
    uint8_t fG = (uint8_t)(g * cal_G * ledBrightness * dim);
    uint8_t fB = (uint8_t)(b * cal_B * ledBrightness * dim);
    if (COMMON_ANODE) {
        analogWrite(LED_R_PIN, 255 - fR);
        analogWrite(LED_G_PIN, 255 - fG);
        analogWrite(LED_B_PIN, 255 - fB);
    } else {
        analogWrite(LED_R_PIN, fR);
        analogWrite(LED_G_PIN, fG);
        analogWrite(LED_B_PIN, fB);
    }
}

void applyModeColor() {
    setLedColor(modeList[currentModeIdx].color[0],
                modeList[currentModeIdx].color[1],
                modeList[currentModeIdx].color[2]);
}


// =======================================================
// Haptics
// =======================================================
void playHapticClick() {
    uint8_t prof = modeList[currentModeIdx].hapticProfile;
    if (prof >= NUM_PROFILES || HAPTIC_PROFILES[prof].freq == 0) return;
    if (hapticPlaying) return;
    tone(HAPTIC_PIN, HAPTIC_PROFILES[prof].freq);
    hapticDurActive  = HAPTIC_PROFILES[prof].dur;
    hapticStartTime  = millis();
    hapticPlaying    = true;
}


// =======================================================
// Mode Cycling
// =======================================================
void cycleMode() {
    do {
        currentModeIdx = (currentModeIdx + 1) % MAX_MODES;
    } while (!modeList[currentModeIdx].enabled);
    
    // Save the newly selected mode to survive power cycle
    prefs.begin("omniscroll", false);
    prefs.putInt("curMode", currentModeIdx);
    prefs.end();

    hapticPlaying = false;
    noTone(HAPTIC_PIN);
    playHapticClick();
    
    applyModeColor();
    Serial.printf("MODE:%s\n", modeList[currentModeIdx].name);
}


// =======================================================
// NVS Persistence — Preferences
// =======================================================
void loadPrefs() {
    prefs.begin("omniscroll", false);
    for (int i = 0; i < MAX_MODES; i++) {
        String base = "m" + String(i);
        if (prefs.isKey((base + "e").c_str())) {
            modeList[i].enabled = prefs.getBool((base + "e").c_str());
            modeList[i].color[0] = prefs.getUChar((base + "r").c_str());
            modeList[i].color[1] = prefs.getUChar((base + "g").c_str());
            modeList[i].color[2] = prefs.getUChar((base + "b").c_str());
            modeList[i].hapticProfile = prefs.getUChar((base + "h").c_str());
            modeList[i].invertDirection = prefs.getBool((base + "i").c_str());
            modeList[i].threshold = prefs.getInt((base + "t").c_str());
        }
    }
    // Load global RGB calibration
    if (prefs.isKey("cal_R")) cal_R = prefs.getFloat("cal_R", 0.10f);
    if (prefs.isKey("cal_G")) cal_G = prefs.getFloat("cal_G", 0.08f);
    if (prefs.isKey("cal_B")) cal_B = prefs.getFloat("cal_B", 1.0f);
    
    // Load last active mode
    if (prefs.isKey("curMode")) {
        currentModeIdx = prefs.getInt("curMode", 0);
        if (currentModeIdx >= MAX_MODES || !modeList[currentModeIdx].enabled) currentModeIdx = 0;
    }
    prefs.end();
}

void savePrefs() {
    prefs.begin("omniscroll", false);
    for (int i = 0; i < MAX_MODES; i++) {
        String base = "m" + String(i);
        prefs.putBool((base + "e").c_str(), modeList[i].enabled);
        prefs.putUChar((base + "r").c_str(), modeList[i].color[0]);
        prefs.putUChar((base + "g").c_str(), modeList[i].color[1]);
        prefs.putUChar((base + "b").c_str(), modeList[i].color[2]);
        prefs.putUChar((base + "h").c_str(), modeList[i].hapticProfile);
        prefs.putBool((base + "i").c_str(), modeList[i].invertDirection);
        prefs.putInt((base + "t").c_str(), modeList[i].threshold);
    }
    prefs.putFloat("cal_R", cal_R);
    prefs.putFloat("cal_G", cal_G);
    prefs.putFloat("cal_B", cal_B);
    prefs.putInt("curMode", currentModeIdx);
    prefs.end();
}


// =======================================================
// Mode Action Dispatch
// =======================================================
void dispatchAction(int dir) {
    if (modeList[currentModeIdx].invertDirection) {
        dir = -dir;
    }

    const char* n = modeList[currentModeIdx].name;

    if      (strcmp(n, "SCROLL") == 0) {
        // High-resolution scroll: sending larger values provides smoother gliding on supported OS
        Mouse.scroll(-dir * 20); 
    }
    else if (strcmp(n, "VOLUME") == 0) {
        ConsumerControl.press(dir > 0 ? CONSUMER_CONTROL_VOLUME_INCREMENT : CONSUMER_CONTROL_VOLUME_DECREMENT);
        delay(2); ConsumerControl.release();
    }
    else if (strcmp(n, "TIMELINE") == 0) {
        Keyboard.press(dir > 0 ? KEY_RIGHT_ARROW : KEY_LEFT_ARROW);
        delay(2); Keyboard.releaseAll();
    }
    else if (strcmp(n, "ZOOM") == 0) {
        Keyboard.press(KEY_LEFT_CTRL);
        Mouse.scroll(dir * 20);
        delay(2); Keyboard.releaseAll();
    }
    else if (strcmp(n, "H_SCROLL") == 0) {
        Mouse.hScroll(dir); // Horizontal scroll
    }
    else if (strcmp(n, "BRIGHTNESS") == 0) {
        // HID Usage 0x006F = Brightness Up, 0x0070 = Brightness Down
        ConsumerControl.press(dir > 0 ? 0x006F : 0x0070);
        delay(2); ConsumerControl.release();
    }
    else if (strcmp(n, "TABBING") == 0) {
        Keyboard.press(KEY_LEFT_CTRL);
        if (dir < 0) Keyboard.press(KEY_LEFT_SHIFT);
        Keyboard.press(KEY_TAB);
        delay(2); Keyboard.releaseAll();
    }
    else if (strcmp(n, "UNDO_REDO") == 0) {
        Keyboard.press(KEY_LEFT_CTRL);
        if (dir > 0) Keyboard.press(KEY_LEFT_SHIFT); // Ctrl+Shift+Z = Redo (universal)
        Keyboard.press('z');
        delay(2); Keyboard.releaseAll();
    }

    playHapticClick();
    lastActivityTime = millis();

    // Wake from idle dim on activity
    if (isIdleDimmed) {
        isIdleDimmed = false;
        applyModeColor();
    }
}


// =======================================================
// Serial Protocol
// =======================================================
void buildConfigJSON(String& out) {
    char hexBuf[8];
    out = "{";
    out += "\"bri\":"  + String((int)(ledBrightness * 100));
    out += ",\"idle\":" + String(idleDimMs / 1000);
    out += ",\"cpi\":"  + String(sensorCPI);
    out += ",\"thr\":"  + String(touch.getThreshold());
    out += ",\"cal_r\":" + String(cal_R, 3);
    out += ",\"cal_g\":" + String(cal_G, 3);
    out += ",\"cal_b\":" + String(cal_B, 3);
    out += ",\"modes\":[";
    for (int i = 0; i < MAX_MODES; i++) {
        if (i > 0) out += ",";
        sprintf(hexBuf, "%02x%02x%02x",
                modeList[i].color[0], modeList[i].color[1], modeList[i].color[2]);
        out += "{";
        out += "\"name\":\"" + String(modeList[i].name) + "\"";
        out += ",\"en\":"   + String(modeList[i].enabled ? 1 : 0);
        out += ",\"c\":\""  + String(hexBuf) + "\"";
        out += ",\"hp\":"   + String(modeList[i].hapticProfile);
        out += ",\"inv\":"  + String(modeList[i].invertDirection ? 1 : 0);
        out += ",\"thr\":"  + String(modeList[i].threshold);
        out += "}";
    }
    out += "]}";
}

void parseSerialCommand(String& cmd) {
    if (cmd == "GET:STATUS") {
        String json = "{";
        json += "\"mode\":\"" + String(modeList[currentModeIdx].name) + "\"";
        json += ",\"touch\":"  + String(touch.getLastReading());
        json += ",\"baseline\":0";
        json += ",\"accX\":"   + String(accumulationX);
        json += "}";
        Serial.println("STATUS:" + json);
    }
    else if (cmd == "GET:CONFIG") {
        String json;
        buildConfigJSON(json);
        Serial.println("CONFIG:" + json);
    }
    else if (cmd == "TEST:HAPTIC") {
        hapticPlaying = false;
        noTone(HAPTIC_PIN);
        playHapticClick();
    }
    else if (cmd.startsWith("SET:CAL:R:")) { cal_R = cmd.substring(10).toFloat(); savePrefs(); applyModeColor(); }
    else if (cmd.startsWith("SET:CAL:G:")) { cal_G = cmd.substring(10).toFloat(); savePrefs(); applyModeColor(); }
    else if (cmd.startsWith("SET:CAL:B:")) { cal_B = cmd.substring(10).toFloat(); savePrefs(); applyModeColor(); }
    else if (cmd.startsWith("SET:") || cmd.startsWith("PREVIEW:")) {
        // Global settings:  SET:BRI:80,IDLE:30,CPI:1,THR:800
        // Per-mode settings: SET:MODE:0,EN:1,CS:0000ff,HP:0,INV:0,MTHR:10
        // Both can be in a single SET: command separated by commas.
        
        bool isPreview = cmd.startsWith("PREVIEW:");
        String params = cmd.substring(isPreview ? 8 : 4);
        int modeTarget = -1;
        int nextComma  = -1;

        do {
            nextComma     = params.indexOf(',');
            String pair   = (nextComma == -1) ? params : params.substring(0, nextComma);
            int    colon  = pair.indexOf(':');

            if (colon != -1) {
                String key = pair.substring(0, colon);
                String val = pair.substring(colon + 1);

                // Global keys
                if      (key == "BRI")  { ledBrightness = constrain(val.toInt(), 0, 100) / 100.0f; applyModeColor(); }
                else if (key == "IDLE") { idleDimMs = val.toInt() * 1000; }
                else if (key == "CPI")  { sensorCPI = constrain(val.toInt(), 0, 3); setSensorCPI(sensorCPI); }
                else if (key == "THR")  { touch.setThreshold(val.toInt()); }

                // Mode target selector
                else if (key == "MODE") { modeTarget = constrain(val.toInt(), 0, MAX_MODES - 1); }

                // Per-mode keys (require MODE: to precede them in the command)
                else if (modeTarget >= 0) {
                    if      (key == "EN")  { modeList[modeTarget].enabled = (val == "1"); }
                    else if (key == "CS")  {
                        long c = strtol(val.c_str(), NULL, 16);
                        modeList[modeTarget].color[0] = (c >> 16) & 0xFF;
                        modeList[modeTarget].color[1] = (c >>  8) & 0xFF;
                        modeList[modeTarget].color[2] =  c        & 0xFF;
                        if (modeTarget == currentModeIdx) applyModeColor();
                    }
                    else if (key == "HP")  { modeList[modeTarget].hapticProfile = constrain(val.toInt(), 0, NUM_PROFILES - 1); }
                    else if (key == "INV") { modeList[modeTarget].invertDirection = (val == "1"); }
                    else if (key == "MTHR"){ modeList[modeTarget].threshold = val.toInt(); }
                }
            }

            if (nextComma != -1) params = params.substring(nextComma + 1);
        } while (nextComma != -1);

        if (!isPreview) {
            savePrefs();
            // Confirm with a click
            hapticPlaying = false;
            noTone(HAPTIC_PIN);
            playHapticClick();
        }
    }
}


// =======================================================
// TinyUSB Descriptor Override
// Bypasses the Arduino core's string caching entirely.
// =======================================================
extern "C" const uint16_t* tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
    (void)langid;
    static uint16_t _desc_str[32];
    uint8_t chr_count = 0;
    const char* str = "";

    if (index == 0) {
        _desc_str[1] = 0x0409; // English
        chr_count = 1;
    } else {
        if (index == 1) str = "OmniScroll Project"; // Manufacturer
        else if (index == 2) str = "OmniScroll";        // Product
        else if (index == 3) str = "OMNI-001";          // Serial
        else return NULL;

        chr_count = strlen(str);
        if (chr_count > 31) chr_count = 31;
        for (uint8_t i = 0; i < chr_count; i++) {
            _desc_str[1 + i] = str[i];
        }
    }

    _desc_str[0] = (TUSB_DESC_STRING << 8) | (2 * chr_count + 2);
    return _desc_str;
}

// =======================================================
// setup()
// =======================================================
void setup() {
    // Set USB descriptor strings BEFORE any USB or HID components begin
    USB.productName("OmniScroll");
    USB.manufacturerName("OmniScroll");
    USB.serialNumber("OMNI-001");
    USB.VID(0x303A);
    USB.PID(0x4F54); // Changed PID to force Windows to forget cached name

    Mouse.begin();
    ConsumerControl.begin();
    Keyboard.begin();
    USBSerial.begin();
    USB.begin();
    Serial.begin(115200);
    delay(2000);

    Serial.println("OmniScroll V2 Booting...");

    pinMode(HAPTIC_PIN, OUTPUT);
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(SCLK_PIN,   OUTPUT);
    digitalWrite(SCLK_PIN, HIGH);
    pinMode(LED_R_PIN, OUTPUT);
    pinMode(LED_G_PIN, OUTPUT);
    pinMode(LED_B_PIN, OUTPUT);

    // Load all persistent settings from NVS
    loadPrefs();

    touch.begin();
    Serial.printf("Touch Threshold: %ld\n", touch.getThreshold());

    // Disable MX8650 sleep for continuous polling
    mx8650_write(0x05, 0xA0);
    setSensorCPI(sensorCPI);

    uint8_t pid = mx8650_read(0x00);
    Serial.printf("MX8650 PID: 0x%02X | CPI Level: %d\n", pid, sensorCPI);

    applyModeColor();
    lastActivityTime = millis();
    Serial.printf("Mode: %s\n", modeList[currentModeIdx].name);

    playHapticClick();
}


// =======================================================
// loop()
// =======================================================
void loop() {
    // --- Haptic stop ---
    if (hapticPlaying && (millis() - hapticStartTime >= (unsigned long)hapticDurActive)) {
        noTone(HAPTIC_PIN);
        hapticPlaying = false;
    }

    // --- Idle dim ---
    if (idleDimMs > 0 && !isIdleDimmed && (millis() - lastActivityTime >= (unsigned long)idleDimMs)) {
        isIdleDimmed = true;
        applyModeColor();
    }

    // --- Touch (with scroll lockout) ---
    bool inLockout = (millis() - lastScrollTime <= 200);
    if (inLockout) { touch.reset(); } else { touch.update(); }

    if (touch.isDoubleTapped()) {
        cycleMode();
        lastActivityTime = millis();
    }

    if (touch.isLongPressed()) {
        // Long press = mode cycle in reverse (wraps around)
        // Future: assignable action via Web UI
        Serial.println("LONGPRESS");
        lastActivityTime = millis();
    }

    // --- Physical button ---
    bool reading = digitalRead(BUTTON_PIN);
    if (reading != lastButtonState) lastDebounceTime = millis();
    if ((millis() - lastDebounceTime) > debounceDelay) {
        if (reading != buttonState) {
            buttonState = reading;
            if (buttonState == LOW) {
                cycleMode();
                lastActivityTime = millis();
            }
        }
    }
    lastButtonState = reading;

    // --- Optical sensor ---
    uint8_t motion = mx8650_read(0x02);
    if (motion & 0x80) {
        int8_t dx = (int8_t)mx8650_read(0x03);
        if (dx != 0) {
            accumulationX += dx;
            lastScrollTime = millis();

            int thr = modeList[currentModeIdx].threshold;
            int dir = modeList[currentModeIdx].invertDirection ? -1 : 1;

            while (accumulationX >= thr) {
                dispatchAction(dir);
                accumulationX -= thr;
            }
            while (accumulationX <= -thr) {
                dispatchAction(-dir);
                accumulationX += thr;
            }
        }
    }

    // --- Serial command handler ---
    if (Serial.available() > 0) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        parseSerialCommand(cmd);
    }

    delay(1);
}
