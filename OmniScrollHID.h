#ifndef OMNISCROLL_HID_H
#define OMNISCROLL_HID_H

#include <Arduino.h>
#include <USBHID.h>

// Report IDs (avoid 1 to prevent collision with USBHIDKeyboard)
#define REPORT_ID_MOUSE_INPUT      11
#define REPORT_ID_MOUSE_HIGH_RES   12

// Mouse Input Report Structure
typedef struct __attribute__ ((packed)) {
    uint8_t buttons;
    int16_t x;
    int16_t y;
    int8_t wheel;
} hid_omni_mouse_report_t;

extern const uint8_t desc_hid_omni[];

class OmniScrollHID : public USBHIDDevice {
private:
    USBHID hid;
    
    // Internal state
    uint8_t res_multiplier; // Captured from SET_FEATURE
    
public:
    OmniScrollHID();
    void begin();
    
    // High-res scroll
    void scroll(int16_t dy);
    
    // Kept for interface compatibility, does nothing for mouse
    void releaseScroll();
    
    // Legacy horizontal scroll
    void hScroll(int8_t amount);

    // USBHIDDevice overrides
    uint16_t _onGetDescriptor(uint8_t *buffer) override;
    uint16_t _onGetFeature(uint8_t report_id, uint8_t *buffer, uint16_t len) override;
    void _onSetFeature(uint8_t report_id, const uint8_t* buffer, uint16_t len) override;
};

#endif // OMNISCROLL_HID_H
