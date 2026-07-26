#include "TouchController.h"

TouchController::TouchController(uint8_t pin, uint16_t thresholdDelta) 
    : _pin(pin), _thresholdDelta(thresholdDelta), 
      _baseline(0), _state(IDLE), _doubleTappedFlag(false) {}

void TouchController::begin() {
    _baseline = touchRead(_pin);
}

bool TouchController::isTouched() {
    long currentVal = touchRead(_pin);
    
    // If the difference is significant, register as touch
    if (abs(currentVal - _baseline) > _thresholdDelta) {
        return true;
    }
    
    // Smooth the baseline if untouched (slow drift compensation)
    _baseline = (_baseline * 15 + currentVal) / 16;
    return false;
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
