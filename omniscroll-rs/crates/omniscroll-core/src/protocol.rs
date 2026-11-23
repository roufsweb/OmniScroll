//! RWP v2.1 (RoufsWeb Protocol) 9-byte binary packet parser and serializer.

pub const RWP_MAGIC: u16 = 0x5257;        // 'R', 'W' in ASCII
pub const OMP_LEGACY_MAGIC: u16 = 0xAA55; // Legacy OMP fallback magic
pub const UDP_DISCOVERY_PORT: u16 = 4210;
pub const UDP_STREAM_PORT: u16 = 4211;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum PacketType {
    Motion = 0x01,  // Wheel motion / scroll delta
    Action = 0x02,  // Key press / shortcut / modifier
    Gesture = 0x03, // Ballistic flick gesture execution
    Status = 0x04,  // Status / heartbeat
    Unknown(u8),
}

impl From<u8> for PacketType {
    fn from(val: u8) -> Self {
        match val {
            0x01 => PacketType::Motion,
            0x02 => PacketType::Action,
            0x03 => PacketType::Gesture,
            0x04 => PacketType::Status,
            other => PacketType::Unknown(other),
        }
    }
}

pub struct Flags(pub u8);

impl Flags {
    pub const HIGH_RES: u8 = 0x01;
    pub const TOUCH_ACTIVE: u8 = 0x02;
    pub const USB_MOUNTED: u8 = 0x04;

    #[inline(always)]
    pub fn is_high_res(&self) -> bool {
        (self.0 & Self::HIGH_RES) != 0
    }

    #[inline(always)]
    pub fn is_touch_active(&self) -> bool {
        (self.0 & Self::TOUCH_ACTIVE) != 0
    }

    #[inline(always)]
    pub fn is_usb_mounted(&self) -> bool {
        (self.0 & Self::USB_MOUNTED) != 0
    }
}

/// 9-byte tightly packed binary packet matching ESP32-S2 memory layout:
/// `[magic_lo, magic_hi, type, seq, delta, mode, action, flags, checksum]`
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RwpPacket {
    pub magic: u16,
    pub packet_type: PacketType,
    pub seq: u8,
    pub delta: i8,
    pub mode: u8,
    pub action: u8,
    pub flags: u8,
    pub checksum: u8,
}

impl RwpPacket {
    /// Deserializes a raw 9-byte slice into an `RwpPacket`, validating magic and XOR checksum.
    pub fn parse(bytes: &[u8]) -> Result<Self, &'static str> {
        if bytes.len() < 9 {
            return Err("Packet too short (minimum 9 bytes)");
        }

        let magic = u16::from_le_bytes([bytes[0], bytes[1]]);
        if magic != RWP_MAGIC && magic != OMP_LEGACY_MAGIC {
            return Err("Invalid magic header");
        }

        // Validate XOR checksum across first 8 bytes
        let mut expected_xor: u8 = 0;
        for &b in &bytes[0..8] {
            expected_xor ^= b;
        }

        let actual_checksum = bytes[8];
        if expected_xor != actual_checksum {
            return Err("Checksum mismatch");
        }

        Ok(Self {
            magic,
            packet_type: PacketType::from(bytes[2]),
            seq: bytes[3],
            delta: bytes[4] as i8,
            mode: bytes[5],
            action: bytes[6],
            flags: bytes[7],
            checksum: actual_checksum,
        })
    }

    /// Serializes packet into a 9-byte buffer with computed XOR checksum.
    pub fn serialize(&self) -> [u8; 9] {
        let magic_bytes = self.magic.to_le_bytes();
        let type_byte = match self.packet_type {
            PacketType::Motion => 0x01,
            PacketType::Action => 0x02,
            PacketType::Gesture => 0x03,
            PacketType::Status => 0x04,
            PacketType::Unknown(b) => b,
        };

        let mut out = [
            magic_bytes[0],
            magic_bytes[1],
            type_byte,
            self.seq,
            self.delta as u8,
            self.mode,
            self.action,
            self.flags,
            0,
        ];

        let mut xor_sum: u8 = 0;
        for &b in &out[0..8] {
            xor_sum ^= b;
        }
        out[8] = xor_sum;
        out
    }

    #[inline(always)]
    pub fn flags(&self) -> Flags {
        Flags(self.flags)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_packet_roundtrip() {
        let pkt = RwpPacket {
            magic: RWP_MAGIC,
            packet_type: PacketType::Motion,
            seq: 42,
            delta: -5,
            mode: 0,
            action: 0,
            flags: Flags::HIGH_RES | Flags::TOUCH_ACTIVE,
            checksum: 0, // will be computed in serialize
        };

        let raw = pkt.serialize();
        let parsed = RwpPacket::parse(&raw).expect("Parsing valid packet failed");

        assert_eq!(parsed.magic, RWP_MAGIC);
        assert_eq!(parsed.packet_type, PacketType::Motion);
        assert_eq!(parsed.seq, 42);
        assert_eq!(parsed.delta, -5);
        assert_eq!(parsed.flags().is_high_res(), true);
        assert_eq!(parsed.flags().is_touch_active(), true);
        assert_eq!(parsed.flags().is_usb_mounted(), false);
    }

    #[test]
    fn test_checksum_corruption() {
        let mut raw = [0x57, 0x52, 0x01, 0x00, 0x0A, 0x00, 0x00, 0x01, 0x00];
        let mut expected = 0;
        for &b in &raw[0..8] { expected ^= b; }
        raw[8] = expected ^ 0xFF; // corrupt checksum

        assert!(RwpPacket::parse(&raw).is_err());
    }
}
