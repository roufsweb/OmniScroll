#include "TouchController.h"

TouchController::TouchController(uint8_t pin, long thresholdDelta) 
    : _pin(pin), _thresholdDelta(thresholdDelta), 
      _state(IDLE), _doubleTappedFlag(false) {}

static void touchDummyISR() {}

void TouchController::begin() {
    // Enable Native ESP32-S2 Touch Hardware
    // The hardware handles baseline tracking, EMA filtering, and hysteresis internally!
    touchAttachInterrupt(_pin, touchDummyISR, _thresholdDelta);
}

bool TouchController::isTouched() {
    // Read the native hardware state (true if pressed, false if released)
    return touchInterruptGetLastStatus(_pin);
}

void TouchController::reset() {
    _state = IDLE;
    _doubleTappedFlag = false;
}

void TouchController::update() {
    _doubleTappedFlag = false; 
    
    bool currentTouch = isTouched();
    unsigned long now = millis();
    
    switch (_state) {
        case IDLE:
            if (currentTouch) {
                _lastTapTime = now;
                _state = WAIT_RELEASE_1;
            }
            break;
            
        case WAIT_RELEASE_1:
            if (!currentTouch && (now - _lastTapTime > DEBOUNCE_TIME)) {
                _lastTapTime = now;
                _state = WAIT_TAP_2;
            } else if (currentTouch && (now - _lastTapTime > DOUBLE_TAP_MAX_DELAY)) {
                // Holding it too long
                _state = IDLE; 
            }
            break;
            
        case WAIT_TAP_2:
            if (currentTouch) {
                _lastTapTime = now;
                _state = WAIT_RELEASE_2;
            } else if (now - _lastTapTime >= DOUBLE_TAP_MAX_DELAY) {
                _state = IDLE; 
            }
            break;
            
        case WAIT_RELEASE_2:
            if (!currentTouch && (now - _lastTapTime > DEBOUNCE_TIME)) {
                _doubleTappedFlag = true;
                _state = IDLE;
            } else if (currentTouch && (now - _lastTapTime > DOUBLE_TAP_MAX_DELAY)) {
                _state = IDLE;
            }
            break;
    }
}

bool TouchController::isDoubleTapped() {
    return _doubleTappedFlag;
}
