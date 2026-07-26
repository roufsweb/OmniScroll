#include "TouchController.h"

TouchController::TouchController(uint8_t pin, uint16_t thresholdDelta) 
    : _pin(pin), _thresholdDelta(thresholdDelta), 
      _baseline(0), _state(IDLE), _doubleTappedFlag(false) {}

void TouchController::begin() {
    // Wait for touch peripheral to stabilize and average 25 readings
    long sum = 0;
    for (int i = 0; i < 5; i++) {
        touchRead(_pin);
        delay(10);
    }
    for (int i = 0; i < 25; i++) {
        sum += touchRead(_pin);
        delay(10);
    }
    _baseline = sum / 25;
}

bool TouchController::isTouched() {
    long currentVal = touchRead(_pin);
    long delta = abs(currentVal - _baseline);
    
    // If the difference is significant, register as touch
    if (delta > _thresholdDelta) {
        return true;
    }
    
    // Only smooth the baseline if untouched AND no interference is happening.
    // The metal wheel causes spikes up to ~300. We only track true slow drift (< 30).
    if (delta < 30) {
        _baseline = (_baseline * 15 + currentVal) / 16;
    }
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
