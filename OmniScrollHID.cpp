#include "OmniScrollHID.h"

// ---------------------------------------------------------
// Windows Precision Touchpad (PTP) HID Descriptor
// ---------------------------------------------------------
const uint8_t desc_hid_omni[] = {
    // ---------------------------------------------------------
    // TOUCH PAD input TLC
    // ---------------------------------------------------------
    HID_USAGE_PAGE(HID_USAGE_PAGE_DIGITIZER), // 0x05, 0x0D
    HID_USAGE(HID_USAGE_DIGITIZER_TOUCH_PAD), // 0x09, 0x05
    HID_COLLECTION(HID_COLLECTION_APPLICATION), // 0xA1, 0x01
    
      HID_REPORT_ID(REPORT_ID_PTP_INPUT)

      // ================= FINGER 1 =================
      HID_USAGE(HID_USAGE_DIGITIZER_FINGER),    // 0x09, 0x22
      HID_COLLECTION(HID_COLLECTION_LOGICAL),   // 0xA1, 0x02
        // Tip Switch (1 bit), Confidence (1 bit)
        HID_LOGICAL_MIN(0),                     // 0x15, 0x00
        HID_LOGICAL_MAX(1),                     // 0x25, 0x01
        HID_USAGE(HID_USAGE_DIGITIZER_TIP_SWITCH), // 0x09, 0x42
        0x09, 0x47, // USAGE(Confidence)
        HID_REPORT_SIZE(1),                     // 0x75, 0x01
        HID_REPORT_COUNT(2),                    // 0x95, 0x02
        HID_INPUT(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x02
        
        // Padding (6 bits)
        HID_REPORT_SIZE(6),                     // 0x75, 0x06
        HID_REPORT_COUNT(1),                    // 0x95, 0x01
        HID_INPUT(HID_CONSTANT | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x03
        
        // Contact Identifier (8 bits)
        HID_LOGICAL_MIN(0),                     // 0x15, 0x00
        HID_LOGICAL_MAX(15),                    // 0x25, 0x0F
        HID_REPORT_SIZE(8),                     // 0x75, 0x08
        HID_REPORT_COUNT(1),                    // 0x95, 0x01
        0x09, 0x51, // USAGE(Contact Identifier)
        HID_INPUT(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x02
        
        // X, Y (16 bits each)
        HID_USAGE_PAGE(HID_USAGE_PAGE_DESKTOP), // 0x05, 0x01
        HID_LOGICAL_MIN(0),                     // 0x15, 0x00
        0x27, 0xff, 0xff, 0x00, 0x00,           // LOGICAL_MAXIMUM (65535)
        HID_REPORT_SIZE(16),                    // 0x75, 0x10
        HID_REPORT_COUNT(1),                    // 0x95, 0x01
        HID_USAGE(HID_USAGE_DESKTOP_X),         // 0x09, 0x30
        HID_INPUT(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x02
        HID_USAGE(HID_USAGE_DESKTOP_Y),         // 0x09, 0x31
        HID_INPUT(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x02
      HID_COLLECTION_END,
      
      // ================= FINGER 2 =================
      HID_USAGE_PAGE(HID_USAGE_PAGE_DIGITIZER), // 0x05, 0x0D
      HID_USAGE(HID_USAGE_DIGITIZER_FINGER),    // 0x09, 0x22
      HID_COLLECTION(HID_COLLECTION_LOGICAL),   // 0xA1, 0x02
        // Tip Switch (1 bit), Confidence (1 bit)
        HID_LOGICAL_MIN(0),                     // 0x15, 0x00
        HID_LOGICAL_MAX(1),                     // 0x25, 0x01
        HID_USAGE(HID_USAGE_DIGITIZER_TIP_SWITCH), // 0x09, 0x42
        0x09, 0x47, // USAGE(Confidence)
        HID_REPORT_SIZE(1),                     // 0x75, 0x01
        HID_REPORT_COUNT(2),                    // 0x95, 0x02
        HID_INPUT(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x02
        
        // Padding (6 bits)
        HID_REPORT_SIZE(6),                     // 0x75, 0x06
        HID_REPORT_COUNT(1),                    // 0x95, 0x01
        HID_INPUT(HID_CONSTANT | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x03
        
        // Contact Identifier (8 bits)
        HID_LOGICAL_MIN(0),                     // 0x15, 0x00
        HID_LOGICAL_MAX(15),                    // 0x25, 0x0F
        HID_REPORT_SIZE(8),                     // 0x75, 0x08
        HID_REPORT_COUNT(1),                    // 0x95, 0x01
        0x09, 0x51, // USAGE(Contact Identifier)
        HID_INPUT(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x02
        
        // X, Y (16 bits each)
        HID_USAGE_PAGE(HID_USAGE_PAGE_DESKTOP), // 0x05, 0x01
        HID_LOGICAL_MIN(0),                     // 0x15, 0x00
        0x27, 0xff, 0xff, 0x00, 0x00,           // LOGICAL_MAXIMUM (65535)
        HID_REPORT_SIZE(16),                    // 0x75, 0x10
        HID_REPORT_COUNT(1),                    // 0x95, 0x01
        HID_USAGE(HID_USAGE_DESKTOP_X),         // 0x09, 0x30
        HID_INPUT(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x02
        HID_USAGE(HID_USAGE_DESKTOP_Y),         // 0x09, 0x31
        HID_INPUT(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x02
      HID_COLLECTION_END,
      
      // ================= FOOTER =================
      HID_USAGE_PAGE(HID_USAGE_PAGE_DIGITIZER), // 0x05, 0x0D
      
      // Scan Time (16 bits)
      0x27, 0xff, 0xff, 0x00, 0x00,             // LOGICAL_MAXIMUM (65535)
      HID_REPORT_SIZE(16),                      // 0x75, 0x10
      HID_REPORT_COUNT(1),                      // 0x95, 0x01
      HID_USAGE(HID_USAGE_DIGITIZER_SCAN_TIME), // 0x09, 0x56
      HID_INPUT(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x02
      
      // Contact Count (8 bits)
      HID_LOGICAL_MAX(127),                     // 0x25, 0x7F
      HID_REPORT_SIZE(8),                       // 0x75, 0x08
      HID_USAGE(HID_USAGE_DIGITIZER_CONTACT_COUNT), // 0x09, 0x54
      HID_INPUT(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x02
      
      // Buttons (1 bit) + Padding (7 bits)
      HID_USAGE_PAGE(HID_USAGE_PAGE_BUTTON),    // 0x05, 0x09
      HID_USAGE_MIN(1),                         // 0x19, 0x01
      HID_USAGE_MAX(1),                         // 0x29, 0x01
      HID_LOGICAL_MAX(1),                       // 0x25, 0x01
      HID_REPORT_SIZE(1),                       // 0x75, 0x01
      HID_REPORT_COUNT(1),                      // 0x95, 0x01
      HID_INPUT(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x02
      
      HID_REPORT_SIZE(7),                       // 0x75, 0x07
      HID_REPORT_COUNT(1),                      // 0x95, 0x01
      HID_INPUT(HID_CONSTANT | HID_VARIABLE | HID_ABSOLUTE), // 0x81, 0x03
      
    // ---------------------------------------------------------
    // PTP Max Contacts Feature Report
    // ---------------------------------------------------------
    HID_REPORT_ID(REPORT_ID_PTP_MAX_CONTACTS)
    HID_USAGE_PAGE(HID_USAGE_PAGE_DIGITIZER),   // 0x05, 0x0D
    0x09, 0x55,                                 // USAGE(Contact Count Maximum)
    HID_REPORT_SIZE(8),                         // 0x75, 0x08
    HID_REPORT_COUNT(1),                        // 0x95, 0x01
    HID_LOGICAL_MAX(15),                        // 0x25, 0x0F
    HID_FEATURE(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0xB1, 0x02

    // ---------------------------------------------------------
    // PTPHQA Windows Certification Feature Report (Required)
    // ---------------------------------------------------------
    HID_REPORT_ID(REPORT_ID_PTP_HQA)
    0x06, 0x00, 0xff,                           // USAGE_PAGE (Vendor Defined)
    0x09, 0xC5,                                 // USAGE (Vendor Usage 0xC5)
    HID_LOGICAL_MIN(0),                         // 0x15, 0x00
    0x26, 0xff, 0x00,                           // LOGICAL_MAXIMUM (255)
    HID_REPORT_SIZE(8),                         // 0x75, 0x08
    0x96, 0x00, 0x01,                           // REPORT_COUNT (256)
    HID_FEATURE(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0xB1, 0x02

    HID_COLLECTION_END, // End of Touch Pad Application Collection

    // ---------------------------------------------------------
    // PTP Configuration TLC (Mandatory for Windows to enable PTP)
    // ---------------------------------------------------------
    HID_USAGE_PAGE(HID_USAGE_PAGE_DIGITIZER),   // 0x05, 0x0D
    0x09, 0x0E,                                 // USAGE(Configuration)
    HID_COLLECTION(HID_COLLECTION_APPLICATION), // 0xA1, 0x01
      HID_REPORT_ID(REPORT_ID_PTP_CONFIG)
      HID_USAGE(HID_USAGE_DIGITIZER_FINGER),    // 0x09, 0x22
      HID_COLLECTION(HID_COLLECTION_LOGICAL),   // 0xA1, 0x02
        0x09, 0x52,                             // USAGE(Input Mode)
        HID_LOGICAL_MIN(0),                     // 0x15, 0x00
        HID_LOGICAL_MAX(10),                    // 0x25, 0x0A
        HID_REPORT_SIZE(8),                     // 0x75, 0x08
        HID_REPORT_COUNT(1),                    // 0x95, 0x01
        HID_FEATURE(HID_DATA | HID_VARIABLE | HID_ABSOLUTE), // 0xB1, 0x02
      HID_COLLECTION_END,
    HID_COLLECTION_END
};

OmniScrollHID::OmniScrollHID() : current_y(32768), current_scan_time(0) {}

void OmniScrollHID::begin() {
    hid.addDevice(this, sizeof(desc_hid_omni));
    hid.begin();
}

uint16_t OmniScrollHID::_onGetDescriptor(uint8_t *buffer) {
    memcpy(buffer, desc_hid_omni, sizeof(desc_hid_omni));
    return sizeof(desc_hid_omni);
}

uint16_t OmniScrollHID::_onGetFeature(uint8_t report_id, uint8_t *buffer, uint16_t len) {
    if (report_id == REPORT_ID_PTP_MAX_CONTACTS) {
        if (len > 0) buffer[0] = 2; // We support 2 contacts for panning
        return 1;
    } else if (report_id == REPORT_ID_PTP_HQA) {
        // Windows expects a 256 byte blob. We just return all zeros (blank certification).
        memset(buffer, 0, min(len, (uint16_t)256));
        return min(len, (uint16_t)256);
    }
    return 0;
}

void OmniScrollHID::scroll(int8_t amount) {
    // 1. Update the imaginary Y coordinate for the fingers
    // We multiply 'amount' by a factor to control scroll speed. 
    // Since our coordinate plane is massive (0 to 65535), we can move by larger steps to feel responsive.
    int32_t new_y = current_y + (amount * 12);
    
    // Bounds checking
    if (new_y < 1000) new_y = 60000;
    if (new_y > 64500) new_y = 5000;
    
    current_y = (uint16_t)new_y;
    current_scan_time++; // Arbitrary increment for PTP specification
    
    // 2. Build the PTP report
    hid_ptp_report_t report = {};
    
    // Finger 1 (Constant X = 10000, Y moves)
    report.contacts[0].tip_switch = 1;
    report.contacts[0].confidence = 1;
    report.contacts[0].contact_id = 0;
    report.contacts[0].x = 10000;
    report.contacts[0].y = current_y;
    
    // Finger 2 (Constant X = 15000, Y moves parallel to Finger 1)
    report.contacts[1].tip_switch = 1;
    report.contacts[1].confidence = 1;
    report.contacts[1].contact_id = 1;
    report.contacts[1].x = 15000;
    report.contacts[1].y = current_y;
    
    report.scan_time = current_scan_time;
    report.contact_count = 2; // 2 fingers on the pad
    report.buttons = 0;
    
    // 3. Send to Windows
    hid.SendReport(REPORT_ID_PTP_INPUT, &report, sizeof(report));
}

void OmniScrollHID::releaseScroll() {
    // Lift fingers off the touchpad to trigger kinetic scroll momentum or simply stop tracking
    hid_ptp_report_t report = {};
    
    // Send 0 contacts, 0 tip_switch
    report.contacts[0].tip_switch = 0;
    report.contacts[1].tip_switch = 0;
    report.contact_count = 0;
    report.scan_time = ++current_scan_time;
    
    hid.SendReport(REPORT_ID_PTP_INPUT, &report, sizeof(report));
    
    // Reset Y to center so we have maximum runway for the next scroll
    current_y = 32768;
}

void OmniScrollHID::hScroll(int8_t amount) {
    // For horizontal scroll, we can just pan the X coordinates instead of Y
    // TODO: Implement later if needed. For now, empty to satisfy compiler.
}

