#include "TouchController.h"

static void touchDummyISR() {}

TouchController::TouchController(uint8_t pin, long thresholdDelta)
    : _pin(pin), _thresholdDelta(thresholdDelta),
      _state(IDLE), _doubleTappedFlag(false), _longPressFlag(false),
      _lastTapTime(0), _pressStartTime(0) {}

void TouchController::begin() {
    touchAttachInterrupt(_pin, touchDummyISR, _thresholdDelta);
}

bool TouchController::isTouched() {
    return touchInterruptGetLastStatus(_pin);
}

void TouchController::reset() {
    _state           = IDLE;
    _doubleTappedFlag = false;
    _longPressFlag   = false;
}

void TouchController::update() {
    _doubleTappedFlag = false;
    _longPressFlag    = false;

    bool touched = isTouched();
    unsigned long now = millis();

    switch (_state) {

        case IDLE:
            if (touched) {
                _pressStartTime = now;
                _lastTapTime    = now;
                _state = WAIT_RELEASE_1;
            }
            break;

        case WAIT_RELEASE_1:
            if (!touched && (now - _lastTapTime > DEBOUNCE_TIME)) {
                // Finger lifted — start waiting for a second tap
                _lastTapTime = now;
                _state = WAIT_TAP_2;
            } else if (touched && (now - _pressStartTime >= LONG_PRESS_TIME)) {
                // Still held long enough — fire long press
                _longPressFlag = true;
                _state = HELD;
            }
            break;

        case WAIT_TAP_2:
            if (touched) {
                _lastTapTime = now;
                _state = WAIT_RELEASE_2;
            } else if (now - _lastTapTime >= DOUBLE_TAP_MAX_DELAY) {
                // Second tap window expired — treat as single tap (no action assigned yet)
                _state = IDLE;
            }
            break;

        case WAIT_RELEASE_2:
            if (!touched && (now - _lastTapTime > DEBOUNCE_TIME)) {
                _doubleTappedFlag = true;
                _state = IDLE;
            } else if (touched && (now - _lastTapTime > DOUBLE_TAP_MAX_DELAY)) {
                _state = IDLE;
            }
            break;

        case HELD:
            // Wait for release before returning to IDLE
            if (!touched) {
                _state = IDLE;
            }
            break;
    }
}

bool TouchController::isDoubleTapped() {
    return _doubleTappedFlag;
}

bool TouchController::isLongPressed() {
    return _longPressFlag;
}
