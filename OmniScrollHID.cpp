#include "OmniScrollHID.h"

// ---------------------------------------------------------
// High-Resolution Mouse HID Descriptor
// ---------------------------------------------------------
const uint8_t desc_hid_omni[] = {
    HID_USAGE_PAGE(HID_USAGE_PAGE_DESKTOP),     // 0x05, 0x01
    HID_USAGE(HID_USAGE_DESKTOP_MOUSE),         // 0x09, 0x02
    HID_COLLECTION(HID_COLLECTION_APPLICATION), // 0xA1, 0x01
        HID_REPORT_ID(REPORT_ID_MOUSE_INPUT)
        HID_USAGE(HID_USAGE_DESKTOP_POINTER),   // 0x09, 0x01
        HID_COLLECTION(HID_COLLECTION_PHYSICAL),// 0xA1, 0x00
            // Buttons (3 buttons)
            HID_USAGE_PAGE(HID_USAGE_PAGE_BUTTON), // 0x05, 0x09
            HID_USAGE_MIN(1),                   // 0x19, 0x01
            HID_USAGE_MAX(3),                   // 0x29, 0x03
            HID_LOGICAL_MIN(0),                 // 0x15, 0x00
            HID_LOGICAL_MAX(1),                 // 0x25, 0x01
            HID_REPORT_COUNT(3),                // 0x95, 0x03
            HID_REPORT_SIZE(1),                 // 0x75, 0x01
            HID_INPUT(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x02
            // Padding (5 bits)
            HID_REPORT_COUNT(1),                // 0x95, 0x01
            HID_REPORT_SIZE(5),                 // 0x75, 0x05
            HID_INPUT(HID_CONSTANT | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x03
            
            // X, Y (16 bits)
            HID_USAGE_PAGE(HID_USAGE_PAGE_DESKTOP), // 0x05, 0x01
            HID_USAGE(HID_USAGE_DESKTOP_X),     // 0x09, 0x30
            HID_USAGE(HID_USAGE_DESKTOP_Y),     // 0x09, 0x31
            0x16, 0x00, 0x80,                   // LOGICAL_MIN (-32768)
            0x26, 0xFF, 0x7F,                   // LOGICAL_MAX (32767)
            HID_REPORT_SIZE(16),                // 0x75, 0x10
            HID_REPORT_COUNT(2),                // 0x95, 0x02
            HID_INPUT(HID_DATA | HID_VARIABLE | HID_RELATIVE), // 0x81, 0x06
            
            // High-Res Wheel (8 bits)
            HID_USAGE(HID_USAGE_DESKTOP_WHEEL), // 0x09, 0x38
            HID_LOGICAL_MIN(0x81),              // 0x15, 0x81 (-127)
            HID_LOGICAL_MAX(0x7F),              // 0x25, 0x7F (127)
            0x36, 0x00, 0x00,                   // PHYSICAL_MIN (0)
            0x46, 0x00, 0x00,                   // PHYSICAL_MAX (0)
            HID_REPORT_SIZE(8),                 // 0x75, 0x08
            HID_REPORT_COUNT(1),                // 0x95, 0x01
            HID_INPUT(HID_DATA | HID_VARIABLE | HID_RELATIVE), // 0x81, 0x06
        HID_COLLECTION_END,
        
        // Resolution Multiplier Feature Report
        HID_REPORT_ID(REPORT_ID_MOUSE_HIGH_RES)
        0x09, 0x48,                             // USAGE (Resolution Multiplier)
        HID_LOGICAL_MIN(0),                     // 0x15, 0x00
        0x25, 0x78,                             // LOGICAL_MAXIMUM (120)
        0x35, 0x01,                             // PHYSICAL_MINIMUM (1)
        0x45, 0x78,                             // PHYSICAL_MAXIMUM (120)
        HID_REPORT_SIZE(8),                     // 0x75, 0x08
        HID_REPORT_COUNT(1),                    // 0x95, 0x01
        HID_FEATURE(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0xB1, 0x02
        
    HID_COLLECTION_END
};

OmniScrollHID::OmniScrollHID() : res_multiplier(120) {}

void OmniScrollHID::begin() {
    hid.addDevice(this, sizeof(desc_hid_omni));
    hid.begin();
}

uint16_t OmniScrollHID::_onGetDescriptor(uint8_t *buffer) {
    memcpy(buffer, desc_hid_omni, sizeof(desc_hid_omni));
    return sizeof(desc_hid_omni);
}

uint16_t OmniScrollHID::_onGetFeature(uint8_t report_id, uint8_t *buffer, uint16_t len) {
    if (report_id == REPORT_ID_MOUSE_HIGH_RES) {
        if (len > 0) buffer[0] = res_multiplier;
        return 1;
    }
    return 0;
}

void OmniScrollHID::_onSetFeature(uint8_t report_id, const uint8_t* buffer, uint16_t len) {
    if (report_id == REPORT_ID_MOUSE_HIGH_RES) {
        if (len > 0) {
            res_multiplier = buffer[0];
            // We'll log it out in the main loop to see what Windows requests!
            Serial.printf("OS requested Resolution Multiplier: %d\n", res_multiplier);
        }
    }
}

void OmniScrollHID::scroll(int16_t dy) {
    hid_omni_mouse_report_t report = {};
    
    // Set wheel delta. Limit to bounds of int8_t just in case.
    if (dy > 127) dy = 127;
    if (dy < -127) dy = -127;
    
    report.wheel = (int8_t)dy;
    
    // Send to Windows
    hid.SendReport(REPORT_ID_MOUSE_INPUT, &report, sizeof(report));
}

void OmniScrollHID::releaseScroll() {
    // No-op for standard mouse
}

void OmniScrollHID::hScroll(int8_t amount) {
    // For horizontal scroll, we can just pan the X coordinates instead of Y
    // TODO: Implement later if needed. For now, empty to satisfy compiler.
}

