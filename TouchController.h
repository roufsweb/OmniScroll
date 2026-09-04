#ifndef TOUCHCONTROLLER_H
#define TOUCHCONTROLLER_H

#include <Arduino.h>

class TouchController {
public:
    TouchController(uint8_t pin, long thresholdDelta = 10000);

    void begin();
    void update();
    void reset();

    bool isDoubleTapped();
    bool isLongPressed();

    bool isTouched();

    long getThreshold() const { return _thresholdDelta; }
    long getLastReading() const { return touchRead(_pin); }
    long getBaseline() const { return 0; } // Hardware handles baseline natively

    void setThreshold(long threshold) {
        _thresholdDelta = threshold;
        touchAttachInterrupt(_pin, nullptr, _thresholdDelta);
    }

private:
    uint8_t _pin;
    long    _thresholdDelta;

    // State machine for double-tap & long-press
    enum State { IDLE, WAIT_RELEASE_1, WAIT_TAP_2, WAIT_RELEASE_2, HELD };
    State _state;

    unsigned long _lastTapTime;
    unsigned long _pressStartTime;

    bool _doubleTappedFlag;
    bool _longPressFlag;

    // Timing constants
    const unsigned long DOUBLE_TAP_MAX_DELAY = 600;  // ms — window to detect second tap
    const unsigned long DEBOUNCE_TIME        = 40;   // ms — minimum tap duration
    const unsigned long LONG_PRESS_TIME      = 700;  // ms — hold duration to fire long press
};

#endif // TOUCHCONTROLLER_H
