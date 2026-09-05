#ifndef OMNISCROLL_HID_H
#define OMNISCROLL_HID_H

#include <Arduino.h>
#include <USBHID.h>

// Report IDs
#define REPORT_ID_MOUSE 1
#define REPORT_ID_MULTIPLIER 2

extern const uint8_t desc_hid_omni[];

class OmniScrollHID : public USBHIDDevice {
private:
    USBHID hid;
    
public:
    OmniScrollHID();
    void begin();
    
    // High-resolution scroll function
    void scroll(int16_t amount);
    
    // Horizontal scroll (optional, standard resolution for now)
    void hScroll(int8_t amount);

    // USBHIDDevice overrides
    uint16_t _onGetDescriptor(uint8_t *buffer) override;
    uint16_t _onGetFeature(uint8_t report_id, uint8_t *buffer, uint16_t len) override;
};

#endif // OMNISCROLL_HID_H
