//! Unified bi-directional Transport Manager (USB CDC + Wi-Fi UDP).

use std::net::SocketAddr;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, RwLock};
use tokio::sync::broadcast;

use crate::serial_listener::{SerialBridge, SerialSender};
use crate::udp_listener::{OmniEvent, UdpBridge};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TransportKind {
    None,
    Usb,
    Wifi,
}

#[derive(Clone)]
pub struct TransportManager {
    serial_sender: Arc<RwLock<Option<SerialSender>>>,
    udp_bridge: Arc<RwLock<Option<Arc<UdpBridge>>>>,
    active_device_ip: Arc<RwLock<Option<SocketAddr>>>,
    pub is_usb_connected: Arc<AtomicBool>,
    pub is_wifi_connected: Arc<AtomicBool>,
}

impl Default for TransportManager {
    fn default() -> Self {
        Self::new()
    }
}

impl TransportManager {
    pub fn new() -> Self {
        Self {
            serial_sender: Arc::new(RwLock::new(None)),
            udp_bridge: Arc::new(RwLock::new(None)),
            active_device_ip: Arc::new(RwLock::new(None)),
            is_usb_connected: Arc::new(AtomicBool::new(false)),
            is_wifi_connected: Arc::new(AtomicBool::new(false)),
        }
    }

    /// Spawns the background USB CDC serial listener and registers the command sender.
    pub fn start_usb(&self, event_tx: broadcast::Sender<OmniEvent>) {
        let is_connected = self.is_usb_connected.clone();
        let sender = SerialBridge::spawn_listener(event_tx, is_connected);
        if let Ok(mut g) = self.serial_sender.write() {
            *g = Some(sender);
        }
    }

    /// Registers the active UDP bridge and updates active Wi-Fi state.
    pub fn register_udp(&self, bridge: Arc<UdpBridge>, device_addr: Option<SocketAddr>) {
        if let Ok(mut g) = self.udp_bridge.write() {
            *g = Some(bridge);
        }
        if let Some(addr) = device_addr {
            if let Ok(mut g) = self.active_device_ip.write() {
                *g = Some(addr);
            }
            self.is_wifi_connected.store(true, Ordering::SeqCst);
        }
    }

    /// Updates the target Wi-Fi UDP socket address for outgoing commands.
    pub fn set_wifi_target(&self, addr: SocketAddr) {
        if let Ok(mut g) = self.active_device_ip.write() {
            *g = Some(addr);
        }
        self.is_wifi_connected.store(true, Ordering::SeqCst);
    }

    /// Returns the currently active transport mode (USB preferred over Wi-Fi).
    pub fn active_transport(&self) -> TransportKind {
        if self.is_usb_connected.load(Ordering::SeqCst) {
            TransportKind::Usb
        } else if self.is_wifi_connected.load(Ordering::SeqCst) {
            TransportKind::Wifi
        } else {
            TransportKind::None
        }
    }

    /// Sends a command string (`SET:...`, `GET:CONFIG`, etc.) over the active transport.
    pub fn send_command(&self, cmd: &str) -> bool {
        // Prefer USB CDC if connected
        if self.is_usb_connected.load(Ordering::SeqCst) {
            if let Ok(g) = self.serial_sender.read() {
                if let Some(ref sender) = *g {
                    if sender.send(cmd) {
                        return true;
                    }
                }
            }
        }

        // Fallback to Wi-Fi UDP
        if let Ok(g_bridge) = self.udp_bridge.read() {
            if let Some(ref bridge) = *g_bridge {
                if let Ok(g_ip) = self.active_device_ip.read() {
                    if let Some(addr) = *g_ip {
                        let bridge_clone = bridge.clone();
                        let cmd_owned = cmd.to_string();
                        tokio::spawn(async move {
                            let _ = bridge_clone.send_command(&cmd_owned, addr).await;
                        });
                        return true;
                    }
                }
            }
        }

        false
    }
}
