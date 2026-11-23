//! USB CDC Serial Listener with strict Espressif VID/PID hardware whitelisting.

use std::io::{Read, Write};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{channel, Receiver, Sender};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::broadcast;
use tracing::{info, warn};

use omniscroll_core::modes::{ActionId, ModeId};
use crate::udp_listener::OmniEvent;

#[derive(Clone)]
pub struct SerialSender {
    cmd_tx: Sender<String>,
}

impl SerialSender {
    pub fn send(&self, cmd: impl Into<String>) -> bool {
        self.cmd_tx.send(cmd.into()).is_ok()
    }
}

pub struct SerialBridge;

impl SerialBridge {
    pub const ESP32_VID: u16 = 0x303A;
    pub const ESP32_PID: u16 = 0x4F5B;

    /// Multi-tier port scanner for universal auto-detection across any Windows PC:
    /// Tier 1: Exact VID 0x303A and known PIDs (0x4F5B production app or 0x0002 bootloader)
    /// Tier 2: Product or Manufacturer substring matching ("OmniScroll", "Espressif", "USB JTAG/serial")
    /// Tier 3: Any USB port with VID 0x303A
    /// Tier 4: If single USB serial port present, select as candidate
    pub fn find_omniscroll_port() -> Option<String> {
        let ports = serialport::available_ports().ok()?;

        // Tier 1: VID 0x303A + known PIDs
        for p in &ports {
            if let serialport::SerialPortType::UsbPort(usb) = &p.port_type {
                if usb.vid == Self::ESP32_VID && (usb.pid == Self::ESP32_PID || usb.pid == 0x0002) {
                    return Some(p.port_name.clone());
                }
            }
        }

        // Tier 2: Product / Manufacturer string search
        for p in &ports {
            if let serialport::SerialPortType::UsbPort(usb) = &p.port_type {
                let prod = usb.product.as_deref().unwrap_or("").to_lowercase();
                let mfg = usb.manufacturer.as_deref().unwrap_or("").to_lowercase();
                if prod.contains("omniscroll") || mfg.contains("omniscroll") || prod.contains("espressif") || mfg.contains("espressif") {
                    return Some(p.port_name.clone());
                }
            }
        }

        // Tier 3: Any port with VID 0x303A
        for p in &ports {
            if let serialport::SerialPortType::UsbPort(usb) = &p.port_type {
                if usb.vid == Self::ESP32_VID {
                    return Some(p.port_name.clone());
                }
            }
        }

        // Tier 4: Exactly one USB serial port found on system
        let usb_ports: Vec<&serialport::SerialPortInfo> = ports.iter().filter(|p| {
            matches!(&p.port_type, serialport::SerialPortType::UsbPort(_))
        }).collect();

        if usb_ports.len() == 1 {
            return Some(usb_ports[0].port_name.clone());
        }

        None
    }

    /// Spawns a background thread that continuously maintains connection to OmniScroll USB CDC.
    pub fn spawn_listener(
        event_tx: broadcast::Sender<OmniEvent>,
        is_connected: Arc<AtomicBool>,
    ) -> SerialSender {
        let (cmd_tx, cmd_rx): (Sender<String>, Receiver<String>) = channel();

        std::thread::spawn(move || {
            loop {
                let port_name = match Self::find_omniscroll_port() {
                    Some(name) => name,
                    None => {
                        is_connected.store(false, Ordering::SeqCst);
                        std::thread::sleep(Duration::from_millis(1000));
                        continue;
                    }
                };

                info!("Opening USB CDC on {} (115200 baud)...", port_name);

                let port_builder = serialport::new(&port_name, 115_200)
                    .timeout(Duration::from_millis(50));

                let mut port = match port_builder.open() {
                    Ok(p) => p,
                    Err(e) => {
                        let err_msg = e.to_string();
                        let in_use = err_msg.contains("Access is denied") || err_msg.contains("Permission denied") || err_msg.contains("in use");
                        if in_use {
                            warn!("Port {} detected but currently in use by another app (e.g. Chrome Web Serial). Retrying...", port_name);
                            let _ = event_tx.send(OmniEvent::PortBusy(port_name.clone()));
                        } else {
                            warn!("Could not open {}: {}. Retrying...", port_name, e);
                        }
                        is_connected.store(false, Ordering::SeqCst);
                        std::thread::sleep(Duration::from_millis(1500));
                        continue;
                    }
                };

                // ESP32-S2 TinyUSB CDC requires both DTR and RTS asserted by host
                let _ = port.write_data_terminal_ready(true);
                let _ = port.write_request_to_send(true);

                is_connected.store(true, Ordering::SeqCst);
                info!("OmniScroll USB CDC Connected on {}! Listening for hardware events...", port_name);
                let _ = event_tx.send(OmniEvent::PortConnected(port_name.clone()));
                let _ = event_tx.send(OmniEvent::Wake);

                let mut active_mode = ModeId::Scroll;
                let mut read_buf = [0u8; 512];
                let mut line_acc = String::with_capacity(1024);

                loop {
                    // 1. Flush any pending outgoing commands to the hardware
                    while let Ok(cmd) = cmd_rx.try_recv() {
                        let mut bytes = cmd.into_bytes();
                        if !bytes.ends_with(b"\n") {
                            bytes.push(b'\n');
                        }
                        if let Err(e) = port.write_all(&bytes) {
                            warn!("Error writing to serial port: {}", e);
                            break;
                        }
                        let _ = port.flush();
                    }

                    // 2. Read incoming serial stream from the device
                    match port.read(&mut read_buf) {
                        Ok(0) => {
                            std::thread::sleep(Duration::from_millis(2));
                        }
                        Ok(n) => {
                            if let Ok(chunk) = std::str::from_utf8(&read_buf[..n]) {
                                line_acc.push_str(chunk);
                                while let Some(pos) = line_acc.find('\n') {
                                    let line = line_acc[..pos].trim().to_string();
                                    line_acc.drain(..=pos);
                                    if !line.is_empty() {
                                        Self::handle_serial_line(&line, &mut active_mode, &event_tx);
                                    }
                                }
                            }
                        }
                        Err(ref e) if e.kind() == std::io::ErrorKind::TimedOut => {
                            // Normal idle timeout
                            continue;
                        }
                        Err(e) => {
                            warn!("Lost USB CDC connection to {}: {}. Reconnecting...", port_name, e);
                            is_connected.store(false, Ordering::SeqCst);
                            break;
                        }
                    }
                }

                is_connected.store(false, Ordering::SeqCst);
                std::thread::sleep(Duration::from_millis(500));
            }
        });

        SerialSender { cmd_tx }
    }

    fn handle_serial_line(
        line: &str,
        active_mode: &mut ModeId,
        event_tx: &broadcast::Sender<OmniEvent>,
    ) {
        if line.starts_with("SCROLL:") {
            if let Ok(delta) = line[7..].parse::<i32>() {
                let _ = event_tx.send(OmniEvent::Motion {
                    delta,
                    mode: *active_mode,
                    threshold: 10,
                    is_high_res: true,
                    touch_active: false,
                    usb_mounted: true,
                });
            }
        } else if line.starts_with("CONFIG:") {
            let _ = event_tx.send(OmniEvent::Config(line.to_string()));
        } else if line.starts_with("MODE:") {
            let mode_str = line[5..].trim();
            for i in 0..8 {
                if let Some(m) = ModeId::from_index(i) {
                    if m.name() == mode_str {
                        *active_mode = m;
                        let _ = event_tx.send(OmniEvent::Status {
                            mode: *active_mode,
                            usb_mounted: true,
                        });
                        break;
                    }
                }
            }
            let _ = event_tx.send(OmniEvent::ModeName(mode_str.to_string()));
        } else if line == "TOUCH:TAP" {
            let _ = event_tx.send(OmniEvent::Tap);
        } else if line == "TOUCH:DOUBLE" {
            let next_idx = ((*active_mode as usize) + 1) % 8;
            if let Some(m) = ModeId::from_index(next_idx) {
                *active_mode = m;
                let _ = event_tx.send(OmniEvent::Status {
                    mode: *active_mode,
                    usb_mounted: true,
                });
            }
        } else if line == "LONGPRESS" {
            let prev_idx = if (*active_mode as usize) == 0 { 7 } else { (*active_mode as usize) - 1 };
            if let Some(m) = ModeId::from_index(prev_idx) {
                *active_mode = m;
                let _ = event_tx.send(OmniEvent::Status {
                    mode: *active_mode,
                    usb_mounted: true,
                });
            }
        } else if line.starts_with("GESTURE:FLICK:FWD") {
            let _ = event_tx.send(OmniEvent::Gesture {
                action: ActionId::BrowserForward,
                is_neural: false,
            });
        } else if line.starts_with("GESTURE:FLICK:REV") {
            let _ = event_tx.send(OmniEvent::Gesture {
                action: ActionId::BrowserBack,
                is_neural: false,
            });
        } else if line.starts_with("GESTURE:TSPIN:END") {
            let _ = event_tx.send(OmniEvent::TouchSpinEnd);
        } else if line == "OMNISCROLL:WAKE" || line.starts_with("OMNISCROLL:WAKE:") || line.starts_with("ROUFSWEB:") {
            let _ = event_tx.send(OmniEvent::Wake);
        } else if line.starts_with("GESTURE_PROFILE:") {
            if let Ok(val) = serde_json::from_str::<serde_json::Value>(&line[16..]) {
                let s = val.get("s").and_then(|v| v.as_f64()).map(|f| f as f32).unwrap_or(110.0);
                let r = val.get("r").and_then(|v| v.as_f64()).map(|f| f as f32).unwrap_or(85.0);
                let t = val.get("t").and_then(|v| v.as_f64()).map(|f| f as f32).unwrap_or(25.0);
                let _ = event_tx.send(OmniEvent::GestureProfile { s, r, t });
            }
        } else if line.starts_with("WIFI:STATUS:") {
            if let Ok(val) = serde_json::from_str::<serde_json::Value>(&line[12..]) {
                let connected = val.get("connected").and_then(|v| v.as_bool()).unwrap_or(false);
                let ssid = val.get("ssid").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let ip = val.get("ip").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let _ = event_tx.send(OmniEvent::WifiStatus { connected, ssid, ip });
            }
        } else {
            let _ = event_tx.send(OmniEvent::RawLine(line.to_string()));
        }
    }
}
