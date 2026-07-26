#ifndef TOUCHCONTROLLER_H
#define TOUCHCONTROLLER_H

#include <Arduino.h>

class TouchController {
public:
    TouchController(uint8_t pin, uint16_t thresholdDelta = 10000);
    
    void begin();
    void update();
    bool isDoubleTapped();
    bool isTouched();
    long getBaseline() const { return _baseline; }
    long getLastReading() const { return touchRead(_pin); }

private:
    uint8_t _pin;
    long _thresholdDelta;
    
    // Baseline tracking
    long _baseline;
    
    // State machine for double tap
    enum State { IDLE, WAIT_RELEASE_1, WAIT_TAP_2, WAIT_RELEASE_2 };
    State _state;
    
    unsigned long _lastTapTime;
    bool _doubleTappedFlag;
    
    // Configurable timings
    const unsigned long DOUBLE_TAP_MAX_DELAY = 400; // max ms between taps
    const unsigned long DEBOUNCE_TIME = 50;         // min ms per tap
};

#endif // TOUCHCONTROLLER_H
