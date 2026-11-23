#include "OmniScrollHID.h"

// ---------------------------------------------------------
// High-Resolution Mouse HID Descriptor with Resolution Multiplier
// Compliant with USB-IF HID Usage Tables & Microsoft mouhid.sys
// ---------------------------------------------------------
const uint8_t desc_hid_omni[] = {
    HID_USAGE_PAGE(HID_USAGE_PAGE_DESKTOP),        // 0x05, 0x01
    HID_USAGE(HID_USAGE_DESKTOP_MOUSE),            // 0x09, 0x02
    HID_COLLECTION(HID_COLLECTION_APPLICATION),    // 0xA1, 0x01
        HID_REPORT_ID(REPORT_ID_MOUSE_INPUT)       // 0x85, 0x0B (11)
        HID_USAGE(HID_USAGE_DESKTOP_POINTER),      // 0x09, 0x01
        HID_COLLECTION(HID_COLLECTION_PHYSICAL),   // 0xA1, 0x00
            // Buttons (3 buttons)
            HID_USAGE_PAGE(HID_USAGE_PAGE_BUTTON), // 0x05, 0x09
            HID_USAGE_MIN(1),                      // 0x19, 0x01
            HID_USAGE_MAX(3),                      // 0x29, 0x03
            HID_LOGICAL_MIN(0),                    // 0x15, 0x00
            HID_LOGICAL_MAX(1),                    // 0x25, 0x01
            HID_REPORT_COUNT(3),                   // 0x95, 0x03
            HID_REPORT_SIZE(1),                    // 0x75, 0x01
            HID_INPUT(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x02
            // Padding (5 bits)
            HID_REPORT_COUNT(1),                   // 0x95, 0x01
            HID_REPORT_SIZE(5),                    // 0x75, 0x05
            HID_INPUT(HID_CONSTANT | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x03
            
            // X, Y (16 bits)
            HID_USAGE_PAGE(HID_USAGE_PAGE_DESKTOP),// 0x05, 0x01
            HID_USAGE(HID_USAGE_DESKTOP_X),        // 0x09, 0x30
            HID_USAGE(HID_USAGE_DESKTOP_Y),        // 0x09, 0x31
            0x16, 0x00, 0x80,                      // LOGICAL_MIN (-32768)
            0x26, 0xFF, 0x7F,                      // LOGICAL_MAX (32767)
            HID_REPORT_SIZE(16),                   // 0x75, 0x10
            HID_REPORT_COUNT(2),                   // 0x95, 0x02
            HID_INPUT(HID_DATA | HID_VARIABLE | HID_RELATIVE), // 0x81, 0x06
            
            // Logical Collection for High-Res Wheel and Resolution Multiplier
            HID_COLLECTION(HID_COLLECTION_LOGICAL),// 0xA1, 0x02
                // Feature Report: Resolution Multiplier (2 bits data, 6 bits padding = 1 byte)
                0x09, 0x48,                        // USAGE (Resolution Multiplier)
                0x15, 0x00,                        // LOGICAL_MINIMUM (0)
                0x25, 0x01,                        // LOGICAL_MAXIMUM (1)
                0x35, 0x01,                        // PHYSICAL_MINIMUM (1)
                0x45, 0x78,                        // PHYSICAL_MAXIMUM (120) -> 120 sub-ticks per notch
                0x55, 0x00,                        // UNIT_EXPONENT (0)
                0x75, 0x02,                        // REPORT_SIZE (2 bits)
                0x95, 0x01,                        // REPORT_COUNT (1)
                0xB1, 0x02,                        // FEATURE (Data, Variable, Absolute)
                
                // Feature Padding (6 bits constant)
                0x35, 0x00,                        // PHYSICAL_MINIMUM (0)
                0x45, 0x00,                        // PHYSICAL_MAXIMUM (0)
                0x75, 0x06,                        // REPORT_SIZE (6 bits)
                0x95, 0x01,                        // REPORT_COUNT (1)
                0xB1, 0x03,                        // FEATURE (Constant)
                
                // Vertical Wheel Input (8 bits signed relative)
                0x09, 0x38,                        // USAGE (Wheel)
                0x15, 0x81,                        // LOGICAL_MINIMUM (-127)
                0x25, 0x7F,                        // LOGICAL_MAXIMUM (127)
                0x75, 0x08,                        // REPORT_SIZE (8 bits)
                0x95, 0x01,                        // REPORT_COUNT (1)
                0x81, 0x06,                        // INPUT (Data, Variable, Relative)
                
                // Horizontal Wheel Input (AC Pan) (8 bits signed relative)
                0x05, 0x0C,                        // USAGE_PAGE (Consumer)
                0x0A, 0x38, 0x02,                  // USAGE (AC Pan)
                0x15, 0x81,                        // LOGICAL_MINIMUM (-127)
                0x25, 0x7F,                        // LOGICAL_MAXIMUM (127)
                0x75, 0x08,                        // REPORT_SIZE (8 bits)
                0x95, 0x01,                        // REPORT_COUNT (1)
                0x81, 0x06,                        // INPUT (Data, Variable, Relative)
            HID_COLLECTION_END,                    // 0xC0 (End Logical Collection)
            
        HID_COLLECTION_END,                        // 0xC0 (End Physical Collection)
    HID_COLLECTION_END                             // 0xC0 (End Application Collection)
};

OmniScrollHID::OmniScrollHID() : _hires_enabled(false) {}

void OmniScrollHID::begin() {
    hid.addDevice(this, sizeof(desc_hid_omni));
    hid.begin();
}

uint16_t OmniScrollHID::_onGetDescriptor(uint8_t *buffer) {
    memcpy(buffer, desc_hid_omni, sizeof(desc_hid_omni));
    return sizeof(desc_hid_omni);
}

uint16_t OmniScrollHID::_onGetFeature(uint8_t report_id, uint8_t *buffer, uint16_t len) {
    if (report_id == REPORT_ID_MOUSE_INPUT) {
        if (len > 0) {
            buffer[0] = _hires_enabled ? 1 : 0;
            return 1;
        }
    }
    return 0;
}

void OmniScrollHID::_onSetFeature(uint8_t report_id, const uint8_t* buffer, uint16_t len) {
    if (report_id == REPORT_ID_MOUSE_INPUT) {
        if (len > 0) {
            _hires_enabled = (buffer[0] & 0x03) != 0;
            Serial.printf("HID: OS SetFeature Resolution Multiplier = %d (Hi-Res: %s)\n",
                          buffer[0], _hires_enabled ? "ON" : "OFF");
        }
    }
}

void OmniScrollHID::scroll(int16_t dy) {
    hid_omni_mouse_report_t report = {};
    if (dy > 127) dy = 127;
    if (dy < -127) dy = -127;
    report.wheel = (int8_t)dy;
    hid.SendReport(REPORT_ID_MOUSE_INPUT, &report, sizeof(report));
}

void OmniScrollHID::hScroll(int16_t dx) {
    hid_omni_mouse_report_t report = {};
    if (dx > 127) dx = 127;
    if (dx < -127) dx = -127;
    report.pan = (int8_t)dx;
    hid.SendReport(REPORT_ID_MOUSE_INPUT, &report, sizeof(report));
}

void OmniScrollHID::releaseScroll() {
    // No-op for standard mouse
}

