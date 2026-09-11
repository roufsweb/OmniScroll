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
#if !ARDUINO_USB_CDC_ON_BOOT
#include "USBCDC.h"
USBCDC USBSerial;
// Map standard Serial calls to the USB CDC object
#define Serial USBSerial
#endif

OmniScrollHID Mouse;

// TinyUSB device mount & suspend hooks
extern "C" bool tud_mounted(void);
extern "C" bool tud_suspended(void);

// -------------------------------------------------------
// Pin Definitions
// -------------------------------------------------------
#define SCLK_PIN     11
#define SDIO_PIN     9
#define BUTTON_PIN   0
#define TOUCH_PIN    12
#define HAPTIC_PIN   17
#define LED_R_PIN    18
#define LED_G_PIN    35
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
int  subTickAcc      = 0; // Fractional remainder accumulator for high-res scrolling
unsigned long lastScrollTime = 0;
bool isScrolling = false;

// -------------------------------------------------------
// Gesture Engine — Research-Calibrated Thresholds
// Sources: NIH motor control (40ms reflex floor), HCI/CHI (300ms imperceptible
// latency ceiling), IEEE two-stage gesture recognition, Schmitt trigger hysteresis
// -------------------------------------------------------
enum FlickState { FLICK_IDLE, FLICK_PRIMING, FLICK_COMMITTED, FLICK_COOLDOWN };
FlickState    flickState          = FLICK_IDLE;
int           flickInitDir        = 0;     // +1 CW, -1 CCW
int           flickTravelAcc      = 0;     // Committed travel accumulator
int           flickReversalAcc    = 0;     // Reversal travel counter
unsigned long flickStateEnterMs   = 0;     // Timestamp of last state transition
unsigned long flickReversalStart  = 0;     // When reversal direction first detected
unsigned long flickLastStrokeMs   = 0;     // Timestamp of last count in stroke direction

// Independent per-direction flick actions (0=disabled, 1–24 = specific action)
// Actions: 0=Off 1=BrowBack 2=BrowFwd 3=Undo 4=Redo 5=MediaPrev 6=MediaNext
//          7=TabPrev 8=TabNext 9=DeskPrev 10=DeskNext 11=VolDown 12=VolUp 13=Copy 14=Paste
//          15=NextMode 16=PrevMode 17..24=DirectMode(0..7)
uint8_t       flickFwdAction      = 2;     // CW→CCW: default Browser Forward
uint8_t       flickRevAction      = 1;     // CCW→CW: default Browser Back
uint8_t       touchSpinAction     = 1;     // NVS-persisted: 0=off,1=hscroll,2=zoom,3=turbo,4=scrub,5=volume

// Gesture LED flash confirmation (non-blocking)
bool          gestureLedFlashing  = false;
unsigned long gestureLedFlashStart= 0;
const unsigned long GESTURE_LED_FLASH_MS = 150; // 150ms warm-white confirmation flash

// -------------------------------------------------------
// Mathematical Self-Learning Gesture Engine (Phase-Energy TinyOL)
// -------------------------------------------------------
// Running personal flick prototype centroids (persisted in NVS)
float         gestureMuS          = 110.0f; // Mean stroke travel (counts)
float         gestureMuR          = 85.0f;  // Mean recoil rebound (counts)
float         gestureMuT          = 25.0f;  // Mean turnaround dwell (ms)

// Physiological variances for normalized distance calculation
const float   GESTURE_SIGMA_S     = 45.0f;
const float   GESTURE_SIGMA_R     = 35.0f;
const float   GESTURE_SIGMA_T     = 18.0f;
const float   GESTURE_LEARN_ALPHA = 0.08f;  // Recursive learning rate (EMA)
bool          gestureLearnedDirty = false;  // True when centroids modified in SRAM
unsigned long gestureLastLearnedMs = 0;      // Timestamp of last centroid update

// Mathematical bounds & physical envelopes
const int     FLICK_PRIME_THRESH          = 10;   // Spotting threshold (~6.9°)
const int     FLICK_COMMIT_THRESH         = 25;   // Minimum stroke to commit (~17.3°)
const int     FLICK_STROKE_CEILING        = 280;  // Continuous scroll ceiling (~194°)
const int     FLICK_REVERSAL_MIN          = 20;   // Minimum elastic snap (~13.8°)
const int     FLICK_REVERSAL_MAX          = 250;  // Recoil ceiling (~173°)
const unsigned long FLICK_COMMIT_WINDOW_MS   = 260;  // Rapid stroke window (<= 260ms)
const unsigned long FLICK_TURNAROUND_MAX_MS  = 75;   // Turnaround limit between stroke & recoil (<= 75ms)
const unsigned long FLICK_REVERSAL_WINDOW_MS = 200;  // Recoil duration limit (<= 200ms)
const unsigned long FLICK_MOTIONLESS_MS      = 85;   // Motionless silence watchdog: 85ms resets engine completely
const unsigned long FLICK_COOLDOWN_MS        = 220;  // Cooldown before next flick can be primed

unsigned long flickTurnaroundDwell        = 0;    // Captured dwell time of current candidate burst

// Touch & Spin Hold Gate & Disambiguation
unsigned long touchContactStart   = 0;
bool          touchSpinActive      = false;  // True strictly on sustained touch-and-hold (>= TOUCH_HOLD_MS)
bool          touchRotated         = false;  // True if rotation occurred while touching (locks out mode changes)
int           touchRotatedCounts   = 0;      // Counts accumulated during current touch contact
const unsigned long TOUCH_HOLD_MS  = 180;    // ms — sustained touch required to arm Touch & Spin (rejects taps)

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
float cal_R = 1.0f;
float cal_G = 1.0f;
float cal_B = 1.0f;
float ledBrightness       = 1.0f; // 0.0–1.0 master dimmer
unsigned long lastActivityTime = 0;
int   idleDimMs           = 30000; // 0 = disabled
bool  isIdleDimmed        = false;

// -------------------------------------------------------
// Host Connection & Standby State (Apple-Inspired)
// -------------------------------------------------------
enum UsbHostState {
    USB_HOST_DISCONNECTED,
    USB_HOST_CONNECTING,
    USB_HOST_CONNECTED
};

UsbHostState hostState = USB_HOST_DISCONNECTED;
unsigned long connectTransitionStartTime = 0;
const unsigned long CONNECT_TRANSITION_MS = 450; // 450ms smooth cubic cross-fade

// -------------------------------------------------------
// Sensor
// -------------------------------------------------------
bool streamTelemetry = false; // When true, streams raw optical `dx` via serial for python data logging

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


// =======================================================
// LED & Gamma Correction
// =======================================================
// Gamma 2.8 lookup table for smooth perceptual brightness
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

void setLedColor(uint8_t r, uint8_t g, uint8_t b) {
    float dim = isIdleDimmed ? 0.2f : 1.0f;
    // Apply Gamma Correction FIRST so perceptual brightness is linear
    uint8_t gammaR = gamma8[r];
    uint8_t gammaG = gamma8[g];
    uint8_t gammaB = gamma8[b];

    // Apply hardware max-brightness calibration (default 1.0 = 100% max PWM) and UI master dim
    uint32_t fR = (uint32_t)constrain((int)(gammaR * cal_R * ledBrightness * dim), 0, 255);
    uint32_t fG = (uint32_t)constrain((int)(gammaG * cal_G * ledBrightness * dim), 0, 255);
    uint32_t fB = (uint32_t)constrain((int)(gammaB * cal_B * ledBrightness * dim), 0, 255);

    if (COMMON_ANODE) {
        ledcWrite(LED_R_PIN, 255 - fR);
        ledcWrite(LED_G_PIN, 255 - fG);
        ledcWrite(LED_B_PIN, 255 - fB);
    } else {
        ledcWrite(LED_R_PIN, fR);
        ledcWrite(LED_G_PIN, fG);
        ledcWrite(LED_B_PIN, fB);
    }
}

void setLedColorDirect(uint8_t r, uint8_t g, uint8_t b) {
    uint8_t gammaR = gamma8[r];
    uint8_t gammaG = gamma8[g];
    uint8_t gammaB = gamma8[b];

    uint32_t fR = (uint32_t)constrain((int)(gammaR * cal_R * ledBrightness), 0, 255);
    uint32_t fG = (uint32_t)constrain((int)(gammaG * cal_G * ledBrightness), 0, 255);
    uint32_t fB = (uint32_t)constrain((int)(gammaB * cal_B * ledBrightness), 0, 255);

    if (COMMON_ANODE) {
        ledcWrite(LED_R_PIN, 255 - fR);
        ledcWrite(LED_G_PIN, 255 - fG);
        ledcWrite(LED_B_PIN, 255 - fB);
    } else {
        ledcWrite(LED_R_PIN, fR);
        ledcWrite(LED_G_PIN, fG);
        ledcWrite(LED_B_PIN, fB);
    }
}

void applyModeColor() {
    setLedColor(modeList[currentModeIdx].color[0],
                modeList[currentModeIdx].color[1],
                modeList[currentModeIdx].color[2]);
}

// -------------------------------------------------------
// Apple-Inspired Breathing & Cross-Fade Renderers
// -------------------------------------------------------
void renderAppleBreathing() {
    static unsigned long lastUpdate = 0;
    unsigned long now = millis();
    if (now - lastUpdate < 15) return; // ~60 FPS smooth render
    lastUpdate = now;

    // 4.5s human resting respiratory cycle (Apple Patent US6658577B2)
    float cycle = (float)(now % 4500) / 4500.0f;
    // Continuous smooth sinusoidal wave (0 at start/end, 1 at midpoint)
    float wave = (1.0f - cosf(cycle * 2.0f * (float)PI)) * 0.5f;
    // Apple physiological breathing curve (Gamma 2.8 perceptual curve)
    float breath = powf(wave, 2.8f);
    // Floor at 4% so the LED never cuts out completely, peaks at 90%
    float factor = 0.04f + 0.86f * breath;

    // Apple MagSafe Amber: #FFA000 -> (255, 140, 0)
    uint8_t r = (uint8_t)constrain((int)(255 * factor), 0, 255);
    uint8_t g = (uint8_t)constrain((int)(140 * factor), 0, 255);
    uint8_t b = 0;

    setLedColorDirect(r, g, b);
}

void renderConnectingCrossfade() {
    static unsigned long lastUpdate = 0;
    unsigned long now = millis();
    if (now - lastUpdate < 15) return;
    lastUpdate = now;

    unsigned long elapsed = now - connectTransitionStartTime;
    if (elapsed >= CONNECT_TRANSITION_MS) {
        hostState = USB_HOST_CONNECTED;
        applyModeColor();
        return;
    }

    float progress = (float)elapsed / (float)CONNECT_TRANSITION_MS;
    // Smooth cubic ease-in-out
    float ease = progress * progress * (3.0f - 2.0f * progress);

    // Cross-fade from Amber (255, 140, 0) to current mode color
    uint8_t targetR = modeList[currentModeIdx].color[0];
    uint8_t targetG = modeList[currentModeIdx].color[1];
    uint8_t targetB = modeList[currentModeIdx].color[2];

    uint8_t curR = (uint8_t)constrain((int)(255 * (1.0f - ease) + targetR * ease), 0, 255);
    uint8_t curG = (uint8_t)constrain((int)(140 * (1.0f - ease) + targetG * ease), 0, 255);
    uint8_t curB = (uint8_t)constrain((int)(0   * (1.0f - ease) + targetB * ease), 0, 255);

    setLedColorDirect(curR, curG, curB);
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

    accumulationX = 0;
    subTickAcc    = 0;

    hapticPlaying = false;
    noTone(HAPTIC_PIN);
    playHapticClick();
    
    if (hostState == USB_HOST_CONNECTED) {
        applyModeColor();
    }
    Serial.printf("MODE:%s\n", modeList[currentModeIdx].name);
}

void cycleModePrev() {
    do {
        currentModeIdx = (currentModeIdx - 1 + MAX_MODES) % MAX_MODES;
    } while (!modeList[currentModeIdx].enabled);
    
    prefs.begin("omniscroll", false);
    prefs.putInt("curMode", currentModeIdx);
    prefs.end();

    accumulationX = 0;
    subTickAcc    = 0;

    hapticPlaying = false;
    noTone(HAPTIC_PIN);
    playHapticClick();
    
    if (hostState == USB_HOST_CONNECTED) {
        applyModeColor();
    }
    Serial.printf("MODE:%s\n", modeList[currentModeIdx].name);
}

void switchToMode(int modeIdx) {
    if (modeIdx < 0 || modeIdx >= MAX_MODES) return;
    if (!modeList[modeIdx].enabled) return;
    currentModeIdx = modeIdx;

    prefs.begin("omniscroll", false);
    prefs.putInt("curMode", currentModeIdx);
    prefs.end();

    accumulationX = 0;
    subTickAcc    = 0;

    hapticPlaying = false;
    noTone(HAPTIC_PIN);
    playHapticClick();
    
    if (hostState == USB_HOST_CONNECTED) {
        applyModeColor();
    }
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
    // Load global RGB calibration (defaulting to 1.0f = 100% max PWM)
    if (prefs.isKey("cal_max_v1")) {
        cal_R = prefs.getFloat("cal_R", 1.0f);
        cal_G = prefs.getFloat("cal_G", 1.0f);
        cal_B = prefs.getFloat("cal_B", 1.0f);
    } else {
        // Reset legacy dimmed calibrations to full max PWM
        cal_R = 1.0f;
        cal_G = 1.0f;
        cal_B = 1.0f;
        prefs.putFloat("cal_R", 1.0f);
        prefs.putFloat("cal_G", 1.0f);
        prefs.putFloat("cal_B", 1.0f);
        prefs.putBool("cal_max_v1", true);
    }
    
    // Load last active mode
    if (prefs.isKey("curMode")) {
        currentModeIdx = prefs.getInt("curMode", 0);
        if (currentModeIdx >= MAX_MODES || !modeList[currentModeIdx].enabled) currentModeIdx = 0;
    }

    // Load global preferences
    if (prefs.isKey("idle_ms")) {
        idleDimMs = prefs.getInt("idle_ms", 30000);
        if (idleDimMs < 0 || idleDimMs > 300000) idleDimMs = 30000;
    }
    if (prefs.isKey("bri")) {
        ledBrightness = prefs.getFloat("bri", 1.0f);
        if (ledBrightness < 0.0f || ledBrightness > 1.0f) ledBrightness = 1.0f;
    }

    // Load gesture settings
    flickFwdAction  = constrain(prefs.getUChar("flick_fwd", 2), 0, 24);
    flickRevAction  = constrain(prefs.getUChar("flick_rev", 1), 0, 24);
    touchSpinAction = constrain(prefs.getUChar("tspin_act", 1), 0, 5);

    // Load adaptive gesture prototype centroids (TinyOL)
    if (prefs.isKey("g_mu_s")) {
        gestureMuS = constrain(prefs.getFloat("g_mu_s", 110.0f), (float)FLICK_COMMIT_THRESH, 240.0f);
        gestureMuR = constrain(prefs.getFloat("g_mu_r", 85.0f),  (float)FLICK_REVERSAL_MIN,  200.0f);
        gestureMuT = constrain(prefs.getFloat("g_mu_t", 25.0f),  10.0f,                       60.0f);
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
    prefs.putBool("cal_max_v1", true);
    prefs.putInt("curMode", currentModeIdx);

    // Save global preferences
    prefs.putInt("idle_ms", idleDimMs);
    prefs.putFloat("bri", ledBrightness);

    // Save gesture settings
    prefs.putUChar("flick_fwd",  flickFwdAction);
    prefs.putUChar("flick_rev",  flickRevAction);
    prefs.putUChar("tspin_act",  touchSpinAction);

    // Save adaptive gesture prototype centroids
    prefs.putFloat("g_mu_s", gestureMuS);
    prefs.putFloat("g_mu_r", gestureMuR);
    prefs.putFloat("g_mu_t", gestureMuT);
    prefs.end();
}


// =======================================================
// Mode Action Dispatch
// =======================================================
void dispatchAction(int direction) {
    playHapticClick();
    
    const char* n = modeList[currentModeIdx].name;

    if (strcmp(n, "VOLUME") == 0) {
        ConsumerControl.press(direction > 0 ? CONSUMER_CONTROL_VOLUME_INCREMENT : CONSUMER_CONTROL_VOLUME_DECREMENT);
        delay(2); ConsumerControl.release();
    }
    else if (strcmp(n, "TIMELINE") == 0) {
        Keyboard.press(direction > 0 ? KEY_RIGHT_ARROW : KEY_LEFT_ARROW);
        delay(2); Keyboard.releaseAll();
    }
    else if (strcmp(n, "ZOOM") == 0) {
        Keyboard.press(KEY_LEFT_CTRL);
        Mouse.scroll(Mouse.isHighRes() ? (int16_t)(120 * direction) : (int16_t)direction);
        delay(2); Keyboard.releaseAll();
    }
    else if (strcmp(n, "H_SCROLL") == 0) {
        Mouse.hScroll(Mouse.isHighRes() ? (int16_t)(120 * direction) : (int16_t)direction);
    }
    else if (strcmp(n, "BRIGHTNESS") == 0) {
        // HID Usage 0x006F = Brightness Up, 0x0070 = Brightness Down
        ConsumerControl.press(direction > 0 ? 0x006F : 0x0070);
        delay(2); ConsumerControl.release();
    }
    else if (strcmp(n, "TABBING") == 0) {
        Keyboard.press(KEY_LEFT_CTRL);
        if (direction < 0) Keyboard.press(KEY_LEFT_SHIFT);
        Keyboard.press(KEY_TAB);
        delay(2); Keyboard.releaseAll();
    }
    else if (strcmp(n, "UNDO_REDO") == 0) {
        Keyboard.press(KEY_LEFT_CTRL);
        if (direction > 0) Keyboard.press(KEY_LEFT_SHIFT); // Ctrl+Shift+Z = Redo (universal)
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
// Gesture Engine
// =======================================================

// Double-click haptic: two rapid taps confirming a gesture fired.
void playHapticDoubleClick() {
    hapticPlaying = false;
    noTone(HAPTIC_PIN);
    tone(HAPTIC_PIN, 250);
    delay(18);
    noTone(HAPTIC_PIN);
    delay(30);
    tone(HAPTIC_PIN, 250);
    delay(18);
    noTone(HAPTIC_PIN);
    hapticPlaying = false;
}

// Non-blocking LED flash: 150ms warm-white burst on gesture fire,
// auto-returns to mode color. Does NOT interfere with haptic or scroll.
void triggerGestureFlash() {
    // Warm white flash — perceptually distinct from mode color
    setLedColorDirect(255, 245, 200);
    gestureLedFlashing  = true;
    gestureLedFlashStart = millis();
}

// Unified single-action dispatcher: maps action ID to HID command.
// Used by both Flick Forward and Flick Back independently.
void dispatchSingleAction(uint8_t action) {
    switch (action) {
        case 0:  break; // Disabled
        case 1:  // Browser Back (Alt+Left)
            Keyboard.press(KEY_LEFT_ALT); Keyboard.press(KEY_LEFT_ARROW);
            delay(2); Keyboard.releaseAll(); break;
        case 2:  // Browser Forward (Alt+Right)
            Keyboard.press(KEY_LEFT_ALT); Keyboard.press(KEY_RIGHT_ARROW);
            delay(2); Keyboard.releaseAll(); break;
        case 3:  // Undo (Ctrl+Z)
            Keyboard.press(KEY_LEFT_CTRL); Keyboard.press('z');
            delay(2); Keyboard.releaseAll(); break;
        case 4:  // Redo (Ctrl+Y)
            Keyboard.press(KEY_LEFT_CTRL); Keyboard.press('y');
            delay(2); Keyboard.releaseAll(); break;
        case 5:  // Media Previous
            ConsumerControl.press(CONSUMER_CONTROL_SCAN_PREVIOUS);
            delay(2); ConsumerControl.release(); break;
        case 6:  // Media Next
            ConsumerControl.press(CONSUMER_CONTROL_SCAN_NEXT);
            delay(2); ConsumerControl.release(); break;
        case 7:  // Previous Tab (Ctrl+Shift+Tab)
            Keyboard.press(KEY_LEFT_CTRL); Keyboard.press(KEY_LEFT_SHIFT); Keyboard.press(KEY_TAB);
            delay(2); Keyboard.releaseAll(); break;
        case 8:  // Next Tab (Ctrl+Tab)
            Keyboard.press(KEY_LEFT_CTRL); Keyboard.press(KEY_TAB);
            delay(2); Keyboard.releaseAll(); break;
        case 9:  // Previous Desktop (Win+Ctrl+Left)
            Keyboard.press(KEY_LEFT_GUI); Keyboard.press(KEY_LEFT_CTRL); Keyboard.press(KEY_LEFT_ARROW);
            delay(2); Keyboard.releaseAll(); break;
        case 10: // Next Desktop (Win+Ctrl+Right)
            Keyboard.press(KEY_LEFT_GUI); Keyboard.press(KEY_LEFT_CTRL); Keyboard.press(KEY_RIGHT_ARROW);
            delay(2); Keyboard.releaseAll(); break;
        case 11: // Volume Down
            ConsumerControl.press(CONSUMER_CONTROL_VOLUME_DECREMENT);
            delay(2); ConsumerControl.release(); break;
        case 12: // Volume Up
            ConsumerControl.press(CONSUMER_CONTROL_VOLUME_INCREMENT);
            delay(2); ConsumerControl.release(); break;
        case 13: // Copy (Ctrl+C)
            Keyboard.press(KEY_LEFT_CTRL); Keyboard.press('c');
            delay(2); Keyboard.releaseAll(); break;
        case 14: // Paste (Ctrl+V)
            Keyboard.press(KEY_LEFT_CTRL); Keyboard.press('v');
            delay(2); Keyboard.releaseAll(); break;
        case 15: // Next Mode (Cycle forward)
            cycleMode();
            break;
        case 16: // Previous Mode (Cycle backward)
            cycleModePrev();
            break;
        case 17: case 18: case 19: case 20:
        case 21: case 22: case 23: case 24: // Direct Mode Jump (0 to 7)
            switchToMode(action - 17);
            break;
    }
}

// Dispatch the Touch & Spin action for the current scroll delta.
void dispatchTouchSpinAction(int8_t dx, int dir, int thr) {
    switch (touchSpinAction) {
        case 0: break; // Disabled — fall through to normal scroll in caller
        case 1: // Horizontal Scroll
            if (Mouse.isHighRes()) {
                subTickAcc += dx * 120 * dir;
                int toSend = subTickAcc / thr;
                if (toSend != 0) { Mouse.hScroll((int16_t)toSend); subTickAcc -= toSend * thr; }
            } else {
                accumulationX += dx;
                while (accumulationX >= thr)  { Mouse.hScroll( dir); playHapticClick(); accumulationX -= thr; }
                while (accumulationX <= -thr) { Mouse.hScroll(-dir); playHapticClick(); accumulationX += thr; }
            }
            break;
        case 2: // Universal Zoom (Ctrl+Scroll)
            accumulationX += dx;
            while (accumulationX >= thr) {
                Keyboard.press(KEY_LEFT_CTRL);
                Mouse.scroll(Mouse.isHighRes() ? (int16_t)(120 * dir) : (int16_t)dir);
                Keyboard.releaseAll();
                playHapticClick();
                accumulationX -= thr;
            }
            while (accumulationX <= -thr) {
                Keyboard.press(KEY_LEFT_CTRL);
                Mouse.scroll(Mouse.isHighRes() ? (int16_t)(-120 * dir) : (int16_t)(-dir));
                Keyboard.releaseAll();
                playHapticClick();
                accumulationX += thr;
            }
            break;
        case 3: { // Turbo 4x — send normal scroll at 4× speed
            int turboThr = max(1, thr / 4);
            accumulationX += dx;
            while (accumulationX >= turboThr) {
                if (Mouse.isHighRes()) Mouse.scroll((int16_t)(120 * dir));
                else                  Mouse.scroll((int16_t)dir);
                playHapticClick();
                accumulationX -= turboThr;
            }
            while (accumulationX <= -turboThr) {
                if (Mouse.isHighRes()) Mouse.scroll((int16_t)(-120 * dir));
                else                  Mouse.scroll((int16_t)(-dir));
                playHapticClick();
                accumulationX += turboThr;
            }
            break;
        }
        case 4: // Timeline Scrub (Shift+Left/Right)
            accumulationX += dx;
            while (accumulationX >= thr) {
                Keyboard.press(KEY_LEFT_SHIFT);
                Keyboard.press(dir > 0 ? KEY_RIGHT_ARROW : KEY_LEFT_ARROW);
                delay(2); Keyboard.releaseAll();
                playHapticClick();
                accumulationX -= thr;
            }
            while (accumulationX <= -thr) {
                Keyboard.press(KEY_LEFT_SHIFT);
                Keyboard.press(dir > 0 ? KEY_LEFT_ARROW : KEY_RIGHT_ARROW);
                delay(2); Keyboard.releaseAll();
                playHapticClick();
                accumulationX += thr;
            }
            break;
        case 5: // Quick Volume
            accumulationX += dx;
            while (accumulationX >= thr) {
                ConsumerControl.press(dir > 0 ? CONSUMER_CONTROL_VOLUME_INCREMENT : CONSUMER_CONTROL_VOLUME_DECREMENT);
                delay(2); ConsumerControl.release();
                playHapticClick();
                accumulationX -= thr;
            }
            while (accumulationX <= -thr) {
                ConsumerControl.press(dir > 0 ? CONSUMER_CONTROL_VOLUME_DECREMENT : CONSUMER_CONTROL_VOLUME_INCREMENT);
                delay(2); ConsumerControl.release();
                playHapticClick();
                accumulationX += thr;
            }
            break;
    }
}

// =======================================================
// Mathematical Self-Learning Gesture Engine (TinyOL)
// Phase-Energy Gated Adaptive Prototype Architecture
//
// 1. Phase-Energy Snap Gate:
//    Dimensionless Kinetic Snap Metric: E_snap = (R^2 / (T_dwell + 1))
//    Separates ballistic recoil from scrolling by ~950x.
//    Requires: R >= 20 counts, Ratio >= 22%, E_snap >= 20.
//
// 2. Adaptive Prototype Classifier (Mahalanobis Distance):
//    d^2 = ((S - mu_S)/sigma_S)^2 + ((R - mu_R)/sigma_R)^2 + ((T - mu_T)/sigma_T)^2
//    Confirms flick within 2-sigma envelope (d^2 <= 4.0).
//
// 3. Confidence-Gated Semi-Supervised Learning:
//    Ultra-clear gestures (d^2 <= 1.5, >= 95% confidence) passively adapt
//    running centroids (mu_S, mu_R, mu_T) in volatile SRAM without flash wear.
// =======================================================
int updateFlickEngine(int8_t dx) {
    if (flickFwdAction == 0 && flickRevAction == 0) return 0; // Both disabled — skip entirely

    unsigned long now = millis();

    // --- Cooldown guard ---
    if (flickState == FLICK_COOLDOWN) {
        if (now - flickStateEnterMs >= FLICK_COOLDOWN_MS) {
            flickState         = FLICK_IDLE;
            flickTravelAcc     = 0;
            flickReversalAcc   = 0;
            flickInitDir       = 0;
            flickReversalStart = 0;
        }
        return 0;
    }

    if (dx == 0) return 0;

    int curDir = (dx > 0) ? 1 : -1;
    int absDx  = abs((int)dx);

    switch (flickState) {

        case FLICK_IDLE:
            // Stage 1 — Spotting: accumulate counts in initial stroke direction
            if (flickInitDir == 0 || curDir != flickInitDir) {
                flickInitDir      = curDir;
                flickTravelAcc    = absDx;
                flickStateEnterMs = now;
                flickLastStrokeMs = now;
            } else {
                flickTravelAcc += absDx;
                flickLastStrokeMs = now;
                // Burst commit window timeout: slow scroll resets burst window
                if (now - flickStateEnterMs > FLICK_COMMIT_WINDOW_MS) {
                    flickTravelAcc    = absDx;
                    flickStateEnterMs = now;
                } else if (flickTravelAcc >= FLICK_PRIME_THRESH) {
                    flickState = FLICK_PRIMING;
                }
            }
            break;

        case FLICK_PRIMING:
            // Timeout guard: rapid burst must complete within commit window
            if (now - flickStateEnterMs > FLICK_COMMIT_WINDOW_MS) {
                flickState = FLICK_IDLE; flickTravelAcc = 0; flickInitDir = 0;
                break;
            }
            if (curDir == flickInitDir) {
                flickTravelAcc += absDx;
                flickLastStrokeMs = now;
                // Guard: Continuous fast scroll ceiling
                if (flickTravelAcc > FLICK_STROKE_CEILING) {
                    flickState = FLICK_IDLE; flickTravelAcc = 0; flickInitDir = 0;
                    break;
                }
                if (flickTravelAcc >= FLICK_COMMIT_THRESH) {
                    flickState         = FLICK_COMMITTED;
                    flickReversalAcc   = 0;
                    flickReversalStart = 0;
                }
            } else {
                // Direction reversed before reaching commit threshold — abort (noise / micro-scrub)
                flickState = FLICK_IDLE; flickTravelAcc = 0; flickInitDir = 0;
            }
            break;

        case FLICK_COMMITTED:
            if (curDir == flickInitDir) {
                // Jitter recovery: motion continues in initial direction -> clear any brief reverse blip
                if (flickReversalStart != 0) {
                    flickReversalStart = 0;
                    flickReversalAcc   = 0;
                }
                flickTravelAcc += absDx;
                flickLastStrokeMs = now;
                // Stroke ceiling or stroke duration window exceeded -> continuous scrolling
                if (flickTravelAcc > FLICK_STROKE_CEILING || (now - flickStateEnterMs > FLICK_COMMIT_WINDOW_MS)) {
                    flickState = FLICK_IDLE; flickTravelAcc = 0; flickInitDir = 0; flickReversalAcc = 0; flickReversalStart = 0;
                    break;
                }
            } else {
                // Direction reversal detected! (Elastic snap-back recoil)
                unsigned long dwell = now - flickLastStrokeMs;
                if (flickReversalStart == 0 && dwell > FLICK_TURNAROUND_MAX_MS) {
                    flickState = FLICK_IDLE; flickTravelAcc = 0; flickInitDir = 0; flickReversalAcc = 0; flickReversalStart = 0;
                    break;
                }

                if (flickReversalStart == 0) {
                    flickReversalStart   = now;
                    flickTurnaroundDwell = dwell;
                }

                // Guard: Reversal duration limit (elastic snap must complete promptly)
                if (now - flickReversalStart > FLICK_REVERSAL_WINDOW_MS) {
                    flickState = FLICK_IDLE; flickTravelAcc = 0; flickInitDir = 0; flickReversalAcc = 0; flickReversalStart = 0;
                    break;
                }

                flickReversalAcc += absDx;

                // Guard: If reversal counts exceed snap ceiling, user is actively scrolling in reverse!
                if (flickReversalAcc > FLICK_REVERSAL_MAX) {
                    flickState = FLICK_IDLE; flickTravelAcc = 0; flickInitDir = 0; flickReversalAcc = 0; flickReversalStart = 0;
                    break;
                }

                // Mathematical Phase-Energy Gate
                int S = flickTravelAcc;
                int R = flickReversalAcc;
                unsigned long T = flickTurnaroundDwell;
                long snapEnergy = (long)R * R / (long)(T + 1);
                long ratioPct   = (long)R * 100 / (long)S;

                if (R >= FLICK_REVERSAL_MIN && ratioPct >= 22 && snapEnergy >= 20) {
                    // GESTURE CONFIRMED! All physical & kinetic criteria satisfied.
                    int fireDir = flickInitDir;

                    // Confidence-Gated Semi-Supervised Learning (TinyOL)
                    float dS = (S - gestureMuS) / GESTURE_SIGMA_S;
                    float dR = (R - gestureMuR) / GESTURE_SIGMA_R;
                    float dT = (T - gestureMuT) / GESTURE_SIGMA_T;
                    float d2 = dS*dS + dR*dR + dT*dT;

                    // High-confidence learning zone (d^2 <= 1.5, >= 95% confidence)
                    if (d2 <= 1.5f) {
                        gestureMuS = (1.0f - GESTURE_LEARN_ALPHA) * gestureMuS + GESTURE_LEARN_ALPHA * S;
                        gestureMuR = (1.0f - GESTURE_LEARN_ALPHA) * gestureMuR + GESTURE_LEARN_ALPHA * R;
                        gestureMuT = (1.0f - GESTURE_LEARN_ALPHA) * gestureMuT + GESTURE_LEARN_ALPHA * T;
                        // Clamp to hard physiological bounds
                        gestureMuS = constrain(gestureMuS, (float)FLICK_COMMIT_THRESH, 240.0f);
                        gestureMuR = constrain(gestureMuR, (float)FLICK_REVERSAL_MIN, 200.0f);
                        gestureMuT = constrain(gestureMuT, 10.0f, 60.0f);
                        gestureLearnedDirty = true;
                        gestureLastLearnedMs = now;
                        Serial.printf("GESTURE:LEARNED:S=%.1f,R=%.1f,T=%.1f\n", gestureMuS, gestureMuR, gestureMuT);
                    }

                    flickState         = FLICK_COOLDOWN;
                    flickStateEnterMs  = now;
                    flickTravelAcc     = 0;
                    flickReversalAcc   = 0;
                    flickInitDir       = 0;
                    flickReversalStart = 0;
                    return fireDir;
                }
            }
            break;

        default:
            flickState = FLICK_IDLE;
            break;
    }
    return 0;
}


// =======================================================
// Serial Protocol
// =======================================================
void buildConfigJSON(String& out) {
    char hexBuf[8];
    out = "{";
    out += "\"bri\":"  + String((int)(ledBrightness * 100));
    out += ",\"idle\":" + String(idleDimMs / 1000);

    out += ",\"thr\":"     + String(touch.getThreshold());
    out += ",\"cal_r\":"   + String(cal_R, 3);
    out += ",\"cal_g\":"   + String(cal_G, 3);
    out += ",\"cal_b\":"   + String(cal_B, 3);
    out += ",\"flick_fwd\":" + String(flickFwdAction);
    out += ",\"flick_rev\":" + String(flickRevAction);
    out += ",\"tspin\":"    + String(touchSpinAction);
    out += ",\"g_mu_s\":"   + String(gestureMuS, 1);
    out += ",\"g_mu_r\":"   + String(gestureMuR, 1);
    out += ",\"g_mu_t\":"   + String(gestureMuT, 1);
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
        json += ",\"usb\":"    + String(hostState == USB_HOST_CONNECTED ? 1 : 0);
        json += "}";
        Serial.println("STATUS:" + json);
    }
    else if (cmd == "GET:CONFIG") {
        String json;
        buildConfigJSON(json);
        Serial.println("CONFIG:" + json);
    }
    else if (cmd == "GET:GESTURE_PROFILE") {
        Serial.printf("GESTURE_PROFILE:{\"s\":%.1f,\"r\":%.1f,\"t\":%.1f}\n", gestureMuS, gestureMuR, gestureMuT);
    }
    else if (cmd.startsWith("SET:GESTURE_PROFILE:")) {
        // Format: SET:GESTURE_PROFILE:<S>,<R>,<T>
        String params = cmd.substring(20);
        int c1 = params.indexOf(',');
        int c2 = params.indexOf(',', c1 + 1);
        if (c1 != -1 && c2 != -1) {
            float s = params.substring(0, c1).toFloat();
            float r = params.substring(c1 + 1, c2).toFloat();
            float t = params.substring(c2 + 1).toFloat();
            gestureMuS = constrain(s, (float)FLICK_COMMIT_THRESH, 240.0f);
            gestureMuR = constrain(r, (float)FLICK_REVERSAL_MIN, 200.0f);
            gestureMuT = constrain(t, 10.0f, 60.0f);
            savePrefs();
            Serial.printf("GESTURE_PROFILE:{\"s\":%.1f,\"r\":%.1f,\"t\":%.1f}\n", gestureMuS, gestureMuR, gestureMuT);
        }
    }
    else if (cmd == "TEST:HAPTIC") {
        hapticPlaying = false;
        noTone(HAPTIC_PIN);
        playHapticClick();
    }
    else if (cmd.startsWith("TEST:LED:")) {
        String ch = cmd.substring(9);
        ch.toUpperCase();
        if      (ch == "R") setLedColor(255, 0, 0);
        else if (ch == "G") setLedColor(0, 255, 0);
        else if (ch == "B") setLedColor(0, 0, 255);
        else if (ch == "OFF") setLedColor(0, 0, 0);
        else if (ch == "RESET") applyModeColor();
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
                else if (key == "IDLE") { idleDimMs = constrain(val.toInt(), 0, 300) * 1000; }
                else if (key == "STREAM") { streamTelemetry = (val.toInt() == 1); }
                else if (key == "THR")  { touch.setThreshold(val.toInt()); }
                else if (key == "FLICK_FWD"){ flickFwdAction  = constrain(val.toInt(), 0, 24); }
                else if (key == "FLICK_REV"){ flickRevAction  = constrain(val.toInt(), 0, 24); }
                else if (key == "TSPIN")    { touchSpinAction = constrain(val.toInt(), 0, 5); }

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
        else if (index == 3) str = "OMNI-007";          // Serial
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
    USB.serialNumber("OMNI-007"); 
    USB.VID(0x303A); // Espressif standard VID
    USB.PID(0x4F5B); // High-Res Mouse Descriptor cache bust (OMNI-007)

    Mouse.begin();
    ConsumerControl.begin();
    Keyboard.begin();
#if !ARDUINO_USB_CDC_ON_BOOT
    USBSerial.begin();
#endif
    USB.begin();
    Serial.begin(115200);
    delay(2000);

    Serial.println("OmniScroll V2 Booting...");

    pinMode(HAPTIC_PIN, OUTPUT);
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(SCLK_PIN,   OUTPUT);
    
    // Initialize hardware LEDC PWM for all 3 RGB LED channels
    // 5000 Hz, 8-bit resolution (0-255) for smooth, flicker-free max PWM
    ledcAttach(LED_R_PIN, 5000, 8);
    ledcAttach(LED_G_PIN, 5000, 8);
    ledcAttach(LED_B_PIN, 5000, 8);
    ledcWrite(LED_R_PIN, 0);
    ledcWrite(LED_G_PIN, 0);
    ledcWrite(LED_B_PIN, 0);
    digitalWrite(SCLK_PIN, HIGH);

    // Load all persistent settings from NVS
    loadPrefs();

    touch.begin();
    Serial.printf("Touch Threshold: %ld\n", touch.getThreshold());

    // Disable MX8650 sleep for continuous polling
    mx8650_write(0x05, 0xA0);
    mx8650_write(0x06, 0x01); // Hardcode MX8650 to 800 CPI (Optimal resolution for our optical layout)

    uint8_t pid = mx8650_read(0x00);
    Serial.printf("MX8650 PID: 0x%02X | CPI Level: 800 (Fixed)\n", pid);

    // Check initial USB host connection state
    if (tud_mounted() && !tud_suspended()) {
        hostState = USB_HOST_CONNECTED;
        applyModeColor();
    } else {
        hostState = USB_HOST_DISCONNECTED;
    }

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

    // --- Gesture LED flash return-to-mode (non-blocking) ---
    if (gestureLedFlashing && (millis() - gestureLedFlashStart >= GESTURE_LED_FLASH_MS)) {
        gestureLedFlashing = false;
        applyModeColor();
    }

    // --- USB Host Connection & Standby Status (Apple Design Language) ---
    bool isMounted = tud_mounted() && !tud_suspended();
    if (isMounted) {
        if (hostState == USB_HOST_DISCONNECTED) {
            hostState = USB_HOST_CONNECTING;
            connectTransitionStartTime = millis();
            playHapticClick(); // Apple Taptic confirmation click
            Serial.println("USB: Host Connected (Handshake complete)");
        }
    } else {
        if (hostState != USB_HOST_DISCONNECTED) {
            hostState = USB_HOST_DISCONNECTED;
            isIdleDimmed = false;
            Serial.println("USB: Host Disconnected / Standby");
        }
    }

    if (hostState == USB_HOST_DISCONNECTED) {
        renderAppleBreathing();
    } else if (hostState == USB_HOST_CONNECTING) {
        renderConnectingCrossfade();
    } else {
        // --- Idle dim (only when host is connected) ---
        if (idleDimMs > 0 && !isIdleDimmed && (millis() - lastActivityTime >= (unsigned long)idleDimMs)) {
            isIdleDimmed = true;
            applyModeColor();
        }
    }

    // --- Touch handling & hold gate ---
    bool wheelMovingNormally = (millis() - lastScrollTime <= 150) && !touchRotated;
    if (wheelMovingNormally) {
        touch.reset(); // Reject capacitive crosstalk while spinning normally
    } else {
        touch.update();
    }

    static bool lastPhysicalTouchState = false;
    bool isPhysicallyTouched = touch.isTouched();

    if (isPhysicallyTouched) {
        if (touchContactStart == 0) {
            touchContactStart = millis();
        }

        // Touch & Spin Hold Gate:
        // Must be held continuously for >= TOUCH_HOLD_MS (180ms)
        if (touchSpinAction != 0 && (millis() - touchContactStart >= TOUCH_HOLD_MS)) {
            if (!touchSpinActive) {
                touchSpinActive = true;
                Serial.println("GESTURE:TSPIN:START");
            }
        }
    } else {
        if (touchSpinActive) {
            Serial.println("GESTURE:TSPIN:END");
        }
        touchSpinActive   = false;
        touchContactStart = 0;

        // If the user rotated the wheel while touching, flush TouchController
        // so releasing the finger is NEVER interpreted as a tap or long-press!
        if (touchRotated) {
            touch.reset();
            touchRotated       = false;
            touchRotatedCounts = 0;
        }
    }

    if (isPhysicallyTouched && !lastPhysicalTouchState && !wheelMovingNormally) {
        Serial.println("TOUCH:TAP");
    }
    lastPhysicalTouchState = isPhysicallyTouched;

    // Double-tap mode switch:
    // Allowed ONLY when stationary, not in Touch & Spin, and wheel was NOT rotated
    if (touch.isDoubleTapped() && !touchSpinActive && !touchRotated && (millis() - lastScrollTime > 150)) {
        if (isIdleDimmed) { isIdleDimmed = false; applyModeColor(); }
        cycleMode();
        lastActivityTime = millis();
        Serial.println("TOUCH:DOUBLE");
    }

    if (touch.isLongPressed() && !touchSpinActive && !touchRotated && (millis() - lastScrollTime > 250)) {
        // Long press = mode cycle in reverse (wraps around)
        // Allowed ONLY when stationary, not in Touch & Spin, and wheel was NOT rotated
        if (isIdleDimmed) { isIdleDimmed = false; applyModeColor(); }
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
                if (isIdleDimmed) { isIdleDimmed = false; applyModeColor(); }
                cycleMode();
                lastActivityTime = millis();
            }
        }
    }
    lastButtonState = reading;

    // --- Optical sensor ---
    uint8_t motion = mx8650_read(0x02);
    if (motion & 0x80) {
        int8_t dx = -(int8_t)mx8650_read(0x03); // Invert sensor orientation: clockwise rotation = positive
        if (dx != 0) {
            if (isIdleDimmed) { isIdleDimmed = false; applyModeColor(); }
            lastScrollTime = millis();
            lastActivityTime = millis();
            isScrolling = true;

            if (isPhysicallyTouched) {
                touchRotated = true;
                touchRotatedCounts += abs((int)dx);
            }

            int dir = modeList[currentModeIdx].invertDirection ? -1 : 1;

            // Broadcast live telemetry if requested
            if (streamTelemetry) {
                Serial.printf("TELEMETRY:%d,%lu\n", dx, millis());
            }

            // Broadcast live scroll data for Web UI visual knob
            Serial.println("SCROLL:" + String(dx * dir));

            int thr = modeList[currentModeIdx].threshold;
            if (thr <= 0) thr = 10;

            if (hostState != USB_HOST_CONNECTED) {
                // Standby / disconnected: keep physical detent haptics active
                accumulationX += dx;
                while (accumulationX >= thr)  { playHapticClick(); accumulationX -= thr; }
                while (accumulationX <= -thr) { playHapticClick(); accumulationX += thr; }

            } else {
                // -------------------------------------------------------
                // Flick gesture engine (runs in parallel with normal scroll)
                // Two-stage Schmitt + state machine — never blocks scroll.
                // -------------------------------------------------------
                int flickResult = updateFlickEngine(dx);
                if (flickResult != 0) {
                    uint8_t action = (flickResult > 0) ? flickFwdAction : flickRevAction;
                    if (action != 0) {
                        dispatchSingleAction(action);
                        playHapticDoubleClick();
                        triggerGestureFlash();
                        Serial.println(flickResult > 0 ? "GESTURE:FLICK:FWD" : "GESTURE:FLICK:REV");
                    }
                    // Always clear accumulator on confirmed flick (even if action=disabled)
                    accumulationX = 0;
                    subTickAcc    = 0;

                // -------------------------------------------------------
                // Touch & Spin (active on sustained hold or decisive rotation while touched)
                // -------------------------------------------------------
                } else if ((touchSpinActive || (isPhysicallyTouched && touchRotatedCounts >= 4)) && touchSpinAction != 0) {
                    if (!touchSpinActive) {
                        touchSpinActive = true;
                        Serial.println("GESTURE:TSPIN:START");
                    }
                    Serial.println("GESTURE:TSPIN");
                    dispatchTouchSpinAction(dx, dir, thr);

                // -------------------------------------------------------
                // Normal scroll / mode dispatch
                // -------------------------------------------------------
                } else if (strcmp(modeList[currentModeIdx].name, "SCROLL") == 0) {
                    if (Mouse.isHighRes()) {
                        // High-Resolution Smooth Scrolling (USB-IF + Microsoft compliant)
                        subTickAcc += dx * 120 * dir;
                        int toSend = subTickAcc / thr;
                        if (toSend != 0) { Mouse.scroll((int16_t)toSend); subTickAcc -= toSend * thr; }
                        // Haptic click at physical detent intervals
                        accumulationX += dx;
                        while (accumulationX >= thr)  { playHapticClick(); accumulationX -= thr; }
                        while (accumulationX <= -thr) { playHapticClick(); accumulationX += thr; }
                    } else {
                        accumulationX += dx;
                        while (accumulationX >= thr)  { Mouse.scroll( dir); playHapticClick(); accumulationX -= thr; }
                        while (accumulationX <= -thr) { Mouse.scroll(-dir); playHapticClick(); accumulationX += thr; }
                    }
                } else if (strcmp(modeList[currentModeIdx].name, "H_SCROLL") == 0) {
                    if (Mouse.isHighRes()) {
                        subTickAcc += dx * 120 * dir;
                        int toSend = subTickAcc / thr;
                        if (toSend != 0) { Mouse.hScroll((int16_t)toSend); subTickAcc -= toSend * thr; }
                        accumulationX += dx;
                        while (accumulationX >= thr)  { playHapticClick(); accumulationX -= thr; }
                        while (accumulationX <= -thr) { playHapticClick(); accumulationX += thr; }
                    } else {
                        accumulationX += dx;
                        while (accumulationX >= thr)  { Mouse.hScroll( dir); playHapticClick(); accumulationX -= thr; }
                        while (accumulationX <= -thr) { Mouse.hScroll(-dir); playHapticClick(); accumulationX += thr; }
                    }
                } else {
                    // All other modes: discrete action dispatch at threshold
                    accumulationX += dx;
                    while (accumulationX >= thr)  { dispatchAction( dir); accumulationX -= thr; }
                    while (accumulationX <= -thr) { dispatchAction(-dir); accumulationX += thr; }
                }
            }
        }
    }

    // Motionless watchdog: if wheel is stationary for > FLICK_MOTIONLESS_MS, cleanly reset flick engine
    // Guarantees that scrolling in one direction, stopping, and scrolling the other direction
    // NEVER links up into an accidental flick gesture!
    if (millis() - lastScrollTime > FLICK_MOTIONLESS_MS) {
        if (flickState != FLICK_IDLE && flickState != FLICK_COOLDOWN) {
            flickState         = FLICK_IDLE;
            flickTravelAcc     = 0;
            flickReversalAcc   = 0;
            flickInitDir       = 0;
            flickReversalStart = 0;
        }
    }

    // Auto-save learned gesture centroids to NVS after 10s of quiet (protects flash wear)
    if (gestureLearnedDirty && (millis() - gestureLastLearnedMs > 10000)) {
        gestureLearnedDirty = false;
        prefs.begin("omniscroll", false);
        prefs.putFloat("g_mu_s", gestureMuS);
        prefs.putFloat("g_mu_r", gestureMuR);
        prefs.putFloat("g_mu_t", gestureMuT);
        prefs.end();
        Serial.println("NVS:GESTURE_PROFILE_SAVED");
    }

    // --- Serial command handler ---
    if (Serial.available() > 0) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        parseSerialCommand(cmd);
    }

    delay(1);
}
