#ifndef TOUCHCONTROLLER_H
#define TOUCHCONTROLLER_H

#include <Arduino.h>

class TouchController {
public:
    TouchController(uint8_t pin, long thresholdDelta = 10000);
    
    void begin();
    void update();
    bool isDoubleTapped();
    bool isTouched();
    void reset();
    long getThreshold() const { return _thresholdDelta; }
    long getBaseline() const { return 0; } // Hardware handles baseline natively
    long getLastReading() const { return touchRead(_pin); }
    void setThreshold(long threshold) { 
        _thresholdDelta = threshold; 
        touchAttachInterrupt(_pin, nullptr, _thresholdDelta); // Re-attach with new threshold
    }

private:
    uint8_t _pin;
    long _thresholdDelta;
    
    // Baseline tracking
    bool _isCurrentlyTouched;
    
    // State machine for double tap
    enum State { IDLE, WAIT_RELEASE_1, WAIT_TAP_2, WAIT_RELEASE_2 };
    State _state;
    
    unsigned long _lastTapTime;
    bool _doubleTappedFlag;
    
    // Configurable timings
    const unsigned long DOUBLE_TAP_MAX_DELAY = 1500; // 1.5 seconds max between taps
    const unsigned long DEBOUNCE_TIME = 40;          // min ms per tap
};

#endif // TOUCHCONTROLLER_H
