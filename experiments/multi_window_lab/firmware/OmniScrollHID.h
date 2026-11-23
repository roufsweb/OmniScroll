#ifndef OMNISCROLL_HID_H
#define OMNISCROLL_HID_H

#include <Arduino.h>
#include <USBHID.h>

// Report ID for unified mouse input and feature reports (avoid 1 to prevent collision with USBHIDKeyboard)
#define REPORT_ID_MOUSE_INPUT      11

// Mouse Input Report Structure (7 bytes total)
typedef struct __attribute__ ((packed)) {
    uint8_t buttons;
    int16_t x;
    int16_t y;
    int8_t  wheel;
    int8_t  pan;
} hid_omni_mouse_report_t;

extern const uint8_t desc_hid_omni[];

class OmniScrollHID : public USBHIDDevice {
private:
    USBHID hid;
    
    // Internal state
    bool _hires_enabled;
    
public:
    OmniScrollHID();
    void begin();
    
    // Query whether OS has activated Resolution Multiplier
    bool isHighRes() const { return _hires_enabled; }
    
    // Vertical scroll (sub-ticks when high-res is active, or notches)
    void scroll(int16_t dy);
    
    // Horizontal scroll (AC Pan)
    void hScroll(int16_t dx);

    // Kept for interface compatibility
    void releaseScroll();

    // USBHIDDevice overrides
    uint16_t _onGetDescriptor(uint8_t *buffer) override;
    uint16_t _onGetFeature(uint8_t report_id, uint8_t *buffer, uint16_t len) override;
    void _onSetFeature(uint8_t report_id, const uint8_t* buffer, uint16_t len) override;
};

#endif // OMNISCROLL_HID_H

