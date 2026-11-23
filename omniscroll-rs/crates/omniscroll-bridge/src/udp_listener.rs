//! Asynchronous UDP streaming and multi-tier auto-discovery engine (Ports 4211 & 4210).

use std::net::SocketAddr;
use std::sync::Arc;
use tokio::net::UdpSocket;
use tokio::sync::{broadcast, Mutex};
use tracing::{debug, error, info};

use omniscroll_core::protocol::{PacketType, RwpPacket, UDP_STREAM_PORT};
use omniscroll_core::modes::{ActionId, ModeId, TouchSpinAction};

use crate::win32_input::Win32Input;

/// Real-time hardware events broadcast to input bridges and UI overlays.
#[derive(Debug, Clone)]
pub enum OmniEvent {
    Motion {
        delta: i32,
        mode: ModeId,
        threshold: i32,
        is_high_res: bool,
        touch_active: bool,
        usb_mounted: bool,
    },
    Action {
        action: ActionId,
        mode: ModeId,
    },
    Gesture {
        action: ActionId,
        is_neural: bool,
    },
    Status {
        mode: ModeId,
        usb_mounted: bool,
    },
    Wake,
    Config(String),
    ModeName(String),
    Tap,
    TouchSpinEnd,
    GestureProfile {
        s: f32,
        r: f32,
        t: f32,
    },
    WifiStatus {
        connected: bool,
        ssid: String,
        ip: String,
    },
    PortBusy(String),
    PortConnected(String),
    WifiPeer(SocketAddr),
    RawLine(String),
}

pub struct UdpBridge {
    pub stream_socket: Arc<UdpSocket>,
    pub event_tx: broadcast::Sender<OmniEvent>,
    pub win32_input: Arc<Mutex<Win32Input>>,
}

impl UdpBridge {
    /// Binds the low-latency stream listener on port 4211.
    pub async fn bind(event_tx: broadcast::Sender<OmniEvent>) -> Result<Self, std::io::Error> {
        let addr: SocketAddr = format!("0.0.0.0:{}", UDP_STREAM_PORT).parse().unwrap();
        let socket = UdpSocket::bind(addr).await?;
        let _ = socket.set_broadcast(true);
        info!("OmniScroll UDP Stream listening on {}", addr);

        let bridge = Self {
            stream_socket: Arc::new(socket),
            event_tx,
            win32_input: Arc::new(Mutex::new(Win32Input::new())),
        };

        // Proactive background auto-discovery prober (dispatches every 3.5s to locate dial on Wi-Fi)
        let sock_clone = bridge.stream_socket.clone();
        tokio::spawn(async move {
            loop {
                tokio::time::sleep(tokio::time::Duration::from_millis(3500)).await;
                let broadcast_addr: SocketAddr = "255.255.255.255:4210".parse().unwrap();
                let _ = sock_clone.send_to(b"GET:STATUS\n", broadcast_addr).await;
            }
        });

        Ok(bridge)
    }

    /// Sends a command string (`SET:...`, `GET:CONFIG`, etc.) to a target Wi-Fi device address over UDP.
    pub async fn send_command(&self, cmd: &str, target: SocketAddr) -> std::io::Result<usize> {
        let mut bytes = cmd.as_bytes().to_vec();
        if !bytes.ends_with(b"\n") {
            bytes.push(b'\n');
        }
        self.stream_socket.send_to(&bytes, target).await
    }

    /// Runs the real-time event loop processing 9-byte binary datagrams.
    pub async fn run_stream_loop(&self) {
        let mut buf = [0u8; 128];

        loop {
            let (len, peer) = match self.stream_socket.recv_from(&mut buf).await {
                Ok(res) => res,
                Err(e) => {
                    error!("UDP stream receive error: {}", e);
                    continue;
                }
            };

            if len == 0 {
                continue;
            }

            // Lock in peer as active Wi-Fi device address
            let _ = self.event_tx.send(OmniEvent::WifiPeer(peer));

            // Check if packet is string command (e.g. "PING" keepalive or "OMNISCROLL:WAKE")
            if let Ok(text) = std::str::from_utf8(&buf[..len]) {
                if text.starts_with("PING") {
                    let _ = self.stream_socket.send_to(b"PONG", peer).await;
                    continue;
                } else if text.starts_with("OMNISCROLL:WAKE") {
                    info!("Hardware push wake received from {}", peer);
                    let _ = self.event_tx.send(OmniEvent::Wake);
                    continue;
                }
            }

            // Process binary 9-byte RWP v2.1 packet
            if len >= 9 {
                match RwpPacket::parse(&buf[..9]) {
                    Ok(packet) => {
                        self.handle_packet(packet).await;
                    }
                    Err(err) => {
                        debug!("Ignoring non-RWP packet ({} bytes): {}", len, err);
                    }
                }
            }
        }
    }

    /// Handles a verified RWP datagram.
    async fn handle_packet(&self, packet: RwpPacket) {
        let flags = packet.flags();
        let mode = ModeId::from_index(packet.mode as usize).unwrap_or(ModeId::Scroll);
        let action = ActionId::from(packet.action);
        let is_high_res = flags.is_high_res();
        let touch_active = flags.is_touch_active();
        let usb_mounted = flags.is_usb_mounted();

        match packet.packet_type {
            PacketType::Motion => {
                let event = OmniEvent::Motion {
                    delta: packet.delta as i32,
                    mode,
                    threshold: 10, // Default threshold, configurable per mode
                    is_high_res,
                    touch_active,
                    usb_mounted,
                };

                let _ = self.event_tx.send(event);

                // Inject input if physical USB cable is NOT already handling input on PC
                if !usb_mounted {
                    let mut input = self.win32_input.lock().await;
                    input.dispatch_mode_motion(mode, packet.delta as i32, 10, is_high_res);
                }
            }
            PacketType::Action => {
                let event = OmniEvent::Action { action, mode };
                let _ = self.event_tx.send(event);

                if !usb_mounted {
                    let mut input = self.win32_input.lock().await;
                    if packet.delta != 0 {
                        input.dispatch_touch_spin(TouchSpinAction::from(packet.action), packet.delta as i32, 10);
                    } else {
                        if packet.action == 6 {
                            input.release_alt_clutch();
                        } else {
                            input.dispatch_action(action);
                        }
                    }
                }
            }
            PacketType::Gesture => {
                let event = OmniEvent::Gesture {
                    action,
                    is_neural: true,
                };
                let _ = self.event_tx.send(event);

                if !usb_mounted {
                    let input = self.win32_input.lock().await;
                    input.dispatch_action(action);
                }
            }
            PacketType::Status => {
                let event = OmniEvent::Status { mode, usb_mounted };
                let _ = self.event_tx.send(event);
            }
            PacketType::Unknown(_) => {}
        }
    }
}
