//! `omniscroll-bridge`
//! High-performance native Windows input injector and async Wi-Fi UDP / Serial bridge.

pub mod win32_input;
pub mod udp_listener;
pub mod serial_listener;
pub mod wifi_scanner;
pub mod transport;

pub use win32_input::Win32Input;
pub use udp_listener::{UdpBridge, OmniEvent};
pub use serial_listener::{SerialBridge, SerialSender};
pub use wifi_scanner::{WifiScanner, WifiNetwork};
pub use transport::{TransportManager, TransportKind};
