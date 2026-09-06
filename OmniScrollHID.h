#ifndef OMNISCROLL_HID_H
#define OMNISCROLL_HID_H

#include <Arduino.h>
#include <USBHID.h>

// Report IDs (avoid 1 to prevent collision with USBHIDKeyboard)
#define REPORT_ID_PTP_INPUT        11
#define REPORT_ID_PTP_MAX_CONTACTS 12
#define REPORT_ID_PTP_HQA          13

// Finger Contact Structure (matches the HID descriptor)
typedef struct __attribute__ ((packed)) {
    uint8_t tip_switch : 1;      // 1 = touching, 0 = lifted
    uint8_t confidence : 1;      // 1 = confident (finger), 0 = accidental (palm)
    uint8_t padding    : 6;
    uint8_t contact_id;          // Unique ID for the finger (e.g., 0 or 1)
    uint16_t x;                  // Absolute X coordinate
    uint16_t y;                  // Absolute Y coordinate
} hid_ptp_contact_t;

// Full Input Report Structure
typedef struct __attribute__ ((packed)) {
    hid_ptp_contact_t contacts[2]; // Two fingers for panning
    uint16_t scan_time;            // 100us intervals (optional, but good practice)
    uint8_t contact_count;         // Number of valid contacts (usually 2 for pan)
    uint8_t buttons;               // Button bitmask (usually 0 for simple scrolling)
} hid_ptp_report_t;

extern const uint8_t desc_hid_omni[];

class OmniScrollHID : public USBHIDDevice {
private:
    USBHID hid;
    
    // Internal state for the imaginary fingers
    uint16_t current_y;
    uint16_t current_scan_time;
    
public:
    OmniScrollHID();
    void begin();
    
    // Smooth scrolling via 2-finger PTP pan
    void scroll(int8_t amount);
    
    // Lift fingers to trigger kinetic momentum and end the pan
    void releaseScroll();
    
    // Legacy horizontal scroll
    void hScroll(int8_t amount);

    // USBHIDDevice overrides
    uint16_t _onGetDescriptor(uint8_t *buffer) override;
    uint16_t _onGetFeature(uint8_t report_id, uint8_t *buffer, uint16_t len) override;
};

#endif // OMNISCROLL_HID_H
