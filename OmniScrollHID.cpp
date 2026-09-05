#include "OmniScrollHID.h"

// HID descriptor
const uint8_t desc_hid_omni[] = {
  HID_USAGE_PAGE(HID_USAGE_PAGE_DESKTOP),
  HID_USAGE(HID_USAGE_DESKTOP_MOUSE),
  HID_COLLECTION(HID_COLLECTION_APPLICATION),
    
    // Mouse Report
    HID_REPORT_ID(HID_REPORT_ID_MOUSE)
    HID_USAGE(HID_USAGE_DESKTOP_POINTER),
    HID_COLLECTION(HID_COLLECTION_PHYSICAL),
      
      // Buttons (5 buttons)
      HID_USAGE_PAGE(HID_USAGE_PAGE_BUTTON),
      HID_USAGE_MIN(1),
      HID_USAGE_MAX(5),
      HID_LOGICAL_MIN(0),
      HID_LOGICAL_MAX(1),
      HID_REPORT_COUNT(5),
      HID_REPORT_SIZE(1),
      HID_INPUT(HID_DATA | HID_VARIABLE | HID_ABSOLUTE),
      // Padding (3 bits)
      HID_REPORT_COUNT(1),
      HID_REPORT_SIZE(3),
      HID_INPUT(HID_CONSTANT),

      // X, Y (8-bit)
      HID_USAGE_PAGE(HID_USAGE_PAGE_DESKTOP),
      HID_USAGE(HID_USAGE_DESKTOP_X),
      HID_USAGE(HID_USAGE_DESKTOP_Y),
      HID_LOGICAL_MIN_N(0x81, 1), // -127
      HID_LOGICAL_MAX_N(0x7F, 1), // 127
      HID_REPORT_COUNT(2),
      HID_REPORT_SIZE(8),
      HID_INPUT(HID_DATA | HID_VARIABLE | HID_RELATIVE),
      
      // Vertical Wheel (16-bit for High Res!)
      HID_USAGE(HID_USAGE_DESKTOP_WHEEL),
      HID_LOGICAL_MIN_N(0x8001, 2), // -32767
      HID_LOGICAL_MAX_N(0x7FFF, 2), // 32767
      HID_REPORT_COUNT(1),
      HID_REPORT_SIZE(16),
      HID_INPUT(HID_DATA | HID_VARIABLE | HID_RELATIVE),
      
      // Horizontal Wheel (8-bit)
      HID_USAGE_PAGE(HID_USAGE_PAGE_CONSUMER),
      HID_USAGE_N(HID_USAGE_CONSUMER_AC_PAN, 2),
      HID_LOGICAL_MIN_N(0x81, 1), // -127
      HID_LOGICAL_MAX_N(0x7F, 1), // 127
      HID_REPORT_COUNT(1),
      HID_REPORT_SIZE(8),
      HID_INPUT(HID_DATA | HID_VARIABLE | HID_RELATIVE),
    
    HID_COLLECTION_END,
    
    // Resolution Multiplier Feature Report
    // Usage 0x48 tells Windows this device supports high-res scrolling
    HID_REPORT_ID(REPORT_ID_MULTIPLIER)
    HID_USAGE_PAGE(HID_USAGE_PAGE_DESKTOP),
    HID_USAGE(0x48), // Resolution Multiplier
    HID_LOGICAL_MIN(0),
    HID_LOGICAL_MAX(1), 
    HID_REPORT_COUNT(1),
    HID_REPORT_SIZE(2),
    HID_FEATURE(HID_DATA | HID_VARIABLE | HID_ABSOLUTE),
    // Padding 6 bits
    HID_REPORT_COUNT(1),
    HID_REPORT_SIZE(6),
    HID_FEATURE(HID_CONSTANT),
    
  HID_COLLECTION_END
};

typedef struct __attribute__ ((packed)) {
    uint8_t buttons;
    int8_t  x;
    int8_t  y;
    int16_t wheel;
    int8_t  pan;
} hid_mouse_hires_report_t;

OmniScrollHID::OmniScrollHID() {
}

void OmniScrollHID::begin() {
    hid.addDevice(this, sizeof(desc_hid_omni));
}

uint16_t OmniScrollHID::_onGetDescriptor(uint8_t *buffer) {
    memcpy(buffer, desc_hid_omni, sizeof(desc_hid_omni));
    return sizeof(desc_hid_omni);
}

uint16_t OmniScrollHID::_onGetFeature(uint8_t report_id, uint8_t *buffer, uint16_t len) {
    if (report_id == REPORT_ID_MULTIPLIER) {
        // Windows expects the multiplier value.
        // We set our logical max to 1 in the descriptor, so we return 1 (enabled).
        // 1 means high resolution scrolling is supported by this wheel.
        if (len > 0) buffer[0] = 1; 
        return 1;
    }
    return 0;
}

void OmniScrollHID::scroll(int16_t amount) {
    hid_mouse_hires_report_t report;
    report.buttons = 0;
    report.x = 0;
    report.y = 0;
    report.wheel = amount;
    report.pan = 0;
    
    hid.SendReport(HID_REPORT_ID_MOUSE, &report, sizeof(report));
}

void OmniScrollHID::hScroll(int8_t amount) {
    hid_mouse_hires_report_t report;
    report.buttons = 0;
    report.x = 0;
    report.y = 0;
    report.wheel = 0;
    report.pan = amount;
    
    hid.SendReport(HID_REPORT_ID_MOUSE, &report, sizeof(report));
}
