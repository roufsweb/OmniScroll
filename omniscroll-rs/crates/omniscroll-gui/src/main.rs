//! OmniScroll Studio — Native Desktop Control Panel in Rust & Slint.
//! Full feature parity with Nordic Walnut Apple Pro HIG, hardware transport, and NVS persistence.

use std::sync::{Arc, Mutex};
use tokio::sync::broadcast;
use tracing::{info, Level};
use tracing_subscriber::FmtSubscriber;

use omniscroll_bridge::{OmniEvent, TransportManager, UdpBridge, WifiScanner};
use omniscroll_core::config::DeviceConfig;
use omniscroll_core::modes::DEFAULT_MODES;

mod hud;

slint::include_modules!();

fn mode_color(idx: usize) -> slint::Color {
    match idx {
        0 => slint::Color::from_rgb_u8(0, 122, 255),   // SCROLL: Blue
        1 => slint::Color::from_rgb_u8(52, 199, 89),   // VOLUME: Green
        2 => slint::Color::from_rgb_u8(255, 149, 0),   // TIMELINE: Orange
        3 => slint::Color::from_rgb_u8(175, 82, 222),  // ZOOM: Purple
        4 => slint::Color::from_rgb_u8(88, 86, 214),   // H_SCROLL: Indigo
        5 => slint::Color::from_rgb_u8(255, 204, 0),   // BRIGHTNESS: Yellow
        6 => slint::Color::from_rgb_u8(255, 45, 85),   // TABBING: Pink
        7 => slint::Color::from_rgb_u8(0, 199, 190),   // UNDO_REDO: Teal
        _ => slint::Color::from_rgb_u8(255, 160, 0),   // MagSafe Amber
    }
}

fn mode_description(idx: usize) -> &'static str {
    match idx {
        0 => "Vertical page scroll & sub-pixel smoothing",
        1 => "System volume control & mute clutch",
        2 => "Frame-by-frame scrubbing & arrow keys",
        3 => "Universal pinch-to-zoom in any application",
        4 => "Horizontal side-scroll & document panning",
        5 => "Display hardware brightness adjustment",
        6 => "Cycle browser tabs & macOS/Windows spaces",
        7 => "History undo (Ctrl+Z) and redo (Ctrl+Shift+Z)",
        _ => "Custom rotary mode",
    }
}

fn is_autostart_enabled() -> bool {
    let mut cmd = std::process::Command::new("reg");
    cmd.args(["query", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run", "/v", "OmniScroll"]);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }
    cmd.status().map(|s| s.success()).unwrap_or(false)
}

fn set_autostart(enable: bool) {
    if enable {
        if let Ok(current_exe) = std::env::current_exe() {
            let exe_str = current_exe.to_string_lossy().to_string();
            let mut cmd = std::process::Command::new("reg");
            cmd.args([
                "add",
                r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                "/v",
                "OmniScroll",
                "/t",
                "REG_SZ",
                "/d",
                &exe_str,
                "/f",
            ]);
            #[cfg(windows)]
            {
                use std::os::windows::process::CommandExt;
                cmd.creation_flags(0x08000000);
            }
            let _ = cmd.status();
        }
    } else {
        let mut cmd = std::process::Command::new("reg");
        cmd.args([
            "delete",
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
            "/v",
            "OmniScroll",
            "/f",
        ]);
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x08000000);
        }
        let _ = cmd.status();
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let subscriber = FmtSubscriber::builder()
        .with_max_level(Level::INFO)
        .finish();
    tracing::subscriber::set_global_default(subscriber).ok();

    info!("Starting OmniScroll Studio (Slint Native Rust GUI)...");

    let ui = MainWindow::new()?;
    let ui_weak = ui.as_weak();

    let (event_tx, mut event_rx) = broadcast::channel::<OmniEvent>(256);
    let transport = TransportManager::new();

    // Spawn USB CDC Listener
    transport.start_usb(event_tx.clone());

    // Spawn Wi-Fi UDP Listener
    let udp_tx = event_tx.clone();
    let transport_clone = transport.clone();
    tokio::spawn(async move {
        if let Ok(bridge) = UdpBridge::bind(udp_tx).await {
            let bridge_arc = Arc::new(bridge);
            transport_clone.register_udp(bridge_arc.clone(), None);
            bridge_arc.run_stream_loop().await;
        }
    });

    // Load persisted configuration
    let config = Arc::new(Mutex::new(DeviceConfig::load_from_disk()));
    let initial_cfg = config.lock().unwrap().clone();

    // Spawn Win32 Dynamic Glassmorphic HUD Overlay
    let hud_ctrl = hud::spawn_hud_overlay(event_tx.subscribe(), config.clone());

    // Dial angle state for crown visualizer
    let dial_angle_state = Arc::new(Mutex::new(0.0f32));

    // Initialize UI properties
    ui.set_active_mode_idx(0);
    ui.set_active_mode_name(DEFAULT_MODES[0].name.into());
    ui.set_active_mode_desc(mode_description(0).into());
    ui.set_active_mode_color(mode_color(0));
    ui.set_active_threshold(initial_cfg.modes.get(0).map(|m| m.threshold).unwrap_or(10));
    ui.set_active_invert(initial_cfg.modes.get(0).map(|m| m.invert).unwrap_or(false));

    ui.set_master_brightness(initial_cfg.bri as i32);
    ui.set_idle_timeout(initial_cfg.idle as i32);
    ui.set_tspin_action(initial_cfg.tspin as i32);
    ui.set_g_mu_s(initial_cfg.g_mu_s);
    ui.set_g_mu_r(initial_cfg.g_mu_r);
    ui.set_g_mu_t(initial_cfg.g_mu_t);
    ui.set_cal_r(initial_cfg.cal_r);
    ui.set_cal_g(initial_cfg.cal_g);
    ui.set_cal_b(initial_cfg.cal_b);
    ui.set_wifi_input_ssid(initial_cfg.last_wifi_ssid.into());
    ui.set_start_on_boot(is_autostart_enabled());

    ui.set_hud_enabled(initial_cfg.hud_enabled);
    ui.set_hud_position(initial_cfg.hud_position.clone().into());
    ui.set_hud_timeout(initial_cfg.hud_timeout_ms as i32);
    ui.set_dial_angle(0.0);
    ui.set_dial_dot_x(59.0);
    ui.set_dial_dot_y(12.0);
    ui.set_dial_angle_text("0°".into());

    // Query hardware configuration and gesture baseline on startup
    let transport_startup = transport.clone();
    tokio::spawn(async move {
        tokio::time::sleep(tokio::time::Duration::from_millis(600)).await;
        transport_startup.send_command("GET:CONFIG");
        tokio::time::sleep(tokio::time::Duration::from_millis(150)).await;
        transport_startup.send_command("GET:GESTURE_PROFILE");
    });

    // Hardware Event Dispatcher Thread
    let ui_thread_weak = ui_weak.clone();
    let config_event = config.clone();
    let dial_angle_event = dial_angle_state.clone();
    let transport_event = transport.clone();
    std::thread::spawn(move || {
        while let Ok(event) = event_rx.blocking_recv() {
            match event {
                OmniEvent::PortBusy(port) => {
                    let ui_handle = ui_thread_weak.clone();
                    slint::invoke_from_event_loop(move || {
                        if let Some(ui) = ui_handle.upgrade() {
                            ui.set_is_connected(false);
                            ui.set_is_busy(true);
                            ui.set_connection_status(format!("{} In Use", port).into());
                            ui.set_port_name(port.into());
                        }
                    }).ok();
                }

                OmniEvent::PortConnected(port) => {
                    let ui_handle = ui_thread_weak.clone();
                    slint::invoke_from_event_loop(move || {
                        if let Some(ui) = ui_handle.upgrade() {
                            ui.set_is_connected(true);
                            ui.set_is_busy(false);
                            ui.set_connection_status("Cable".into());
                            ui.set_port_name(port.into());
                        }
                    }).ok();
                }

                OmniEvent::WifiPeer(peer) => {
                    transport_event.set_wifi_target(peer);
                    let ui_handle = ui_thread_weak.clone();
                    slint::invoke_from_event_loop(move || {
                        if let Some(ui) = ui_handle.upgrade() {
                            if !ui.get_is_connected() {
                                ui.set_is_connected(true);
                                ui.set_is_busy(false);
                                ui.set_connection_status("Wireless".into());
                            }
                        }
                    }).ok();
                }

                OmniEvent::Motion { delta, .. } => {
                    let angle = {
                        let mut a = dial_angle_event.lock().unwrap();
                        *a = (*a + (delta as f32) * 0.6923).rem_euclid(360.0);
                        *a
                    };
                    let rad = (angle - 90.0).to_radians();
                    let cx = 65.0;
                    let cy = 65.0;
                    let radius = 48.0;
                    let dot_x = cx + radius * rad.cos() - 6.0;
                    let dot_y = cy + radius * rad.sin() - 6.0;
                    let angle_text = format!("{}°", angle.round() as i32);

                    let ui_handle = ui_thread_weak.clone();
                    slint::invoke_from_event_loop(move || {
                        if let Some(ui) = ui_handle.upgrade() {
                            ui.set_dial_angle(angle);
                            ui.set_dial_dot_x(dot_x);
                            ui.set_dial_dot_y(dot_y);
                            ui.set_dial_angle_text(angle_text.into());
                        }
                    }).ok();
                }
                OmniEvent::Status { mode, usb_mounted } => {
                    let mode_idx = mode as usize;
                    let mode_name = DEFAULT_MODES.get(mode_idx)
                        .map(|m| m.name)
                        .unwrap_or("SCROLL")
                        .to_string();
                    let desc = mode_description(mode_idx).to_string();
                    let col = mode_color(mode_idx);

                    let (thr, inv) = {
                        let cfg = config_event.lock().unwrap();
                        let m = cfg.modes.get(mode_idx);
                        (
                            m.map(|x| x.threshold).unwrap_or(10),
                            m.map(|x| x.invert).unwrap_or(false),
                        )
                    };

                    let ui_handle = ui_thread_weak.clone();
                    slint::invoke_from_event_loop(move || {
                        if let Some(ui) = ui_handle.upgrade() {
                            ui.set_active_mode_idx(mode_idx as i32);
                            ui.set_active_mode_name(mode_name.into());
                            ui.set_active_mode_desc(desc.into());
                            ui.set_active_mode_color(col);
                            ui.set_active_threshold(thr);
                            ui.set_active_invert(inv);
                            ui.set_is_connected(true);
                            ui.set_connection_status(if usb_mounted { "Cable".into() } else { "Wireless".into() });
                        }
                    }).ok();
                }

                OmniEvent::Wake => {
                    let ui_handle = ui_thread_weak.clone();
                    slint::invoke_from_event_loop(move || {
                        if let Some(ui) = ui_handle.upgrade() {
                            ui.set_is_connected(true);
                        }
                    }).ok();
                }

                OmniEvent::GestureProfile { s, r, t } => {
                    {
                        let mut cfg = config_event.lock().unwrap();
                        cfg.g_mu_s = s;
                        cfg.g_mu_r = r;
                        cfg.g_mu_t = t;
                        let _ = cfg.save_to_disk();
                    }
                    let ui_handle = ui_thread_weak.clone();
                    slint::invoke_from_event_loop(move || {
                        if let Some(ui) = ui_handle.upgrade() {
                            ui.set_g_mu_s(s);
                            ui.set_g_mu_r(r);
                            ui.set_g_mu_t(t);
                        }
                    }).ok();
                }

                OmniEvent::WifiStatus { connected, ssid, ip } => {
                    let status_str = if connected {
                        format!("Connected ({})", ip)
                    } else {
                        "Standby / Disconnected".to_string()
                    };
                    let ui_handle = ui_thread_weak.clone();
                    slint::invoke_from_event_loop(move || {
                        if let Some(ui) = ui_handle.upgrade() {
                            ui.set_wifi_connected(connected);
                            ui.set_wifi_status_text(status_str.into());
                            if !ssid.is_empty() {
                                ui.set_wifi_ssid(ssid.into());
                            }
                        }
                    }).ok();
                }

                OmniEvent::Config(line) => {
                    if let Some(hw_cfg) = DeviceConfig::parse_hardware_config(&line) {
                        let mut cfg = config_event.lock().unwrap();
                        *cfg = hw_cfg.clone();
                        let _ = cfg.save_to_disk();

                        let bri = hw_cfg.bri as i32;
                        let idle = hw_cfg.idle as i32;
                        let tspin = hw_cfg.tspin as i32;
                        let s = hw_cfg.g_mu_s;
                        let r = hw_cfg.g_mu_r;
                        let t = hw_cfg.g_mu_t;
                        let cal_r = hw_cfg.cal_r;
                        let cal_g = hw_cfg.cal_g;
                        let cal_b = hw_cfg.cal_b;

                        let ui_handle = ui_thread_weak.clone();
                        slint::invoke_from_event_loop(move || {
                            if let Some(ui) = ui_handle.upgrade() {
                                ui.set_master_brightness(bri);
                                ui.set_idle_timeout(idle);
                                ui.set_tspin_action(tspin);
                                ui.set_g_mu_s(s);
                                ui.set_g_mu_r(r);
                                ui.set_g_mu_t(t);
                                ui.set_cal_r(cal_r);
                                ui.set_cal_g(cal_g);
                                ui.set_cal_b(cal_b);
                            }
                        }).ok();
                    }
                }

                OmniEvent::RawLine(line) => {
                    if line.starts_with("WIFI:CONFIGURED:") {
                        let ssid = line.strip_prefix("WIFI:CONFIGURED:").unwrap_or("").to_string();
                        let ui_handle = ui_thread_weak.clone();
                        slint::invoke_from_event_loop(move || {
                            if let Some(ui) = ui_handle.upgrade() {
                                ui.set_wifi_status_text(format!("Credentials Sent: {}", ssid).into());
                            }
                        }).ok();
                    }
                }

                _ => {}
            }
        }
    });

    // -----------------------------------------------------------------
    // UI Callbacks
    // -----------------------------------------------------------------

    // 1. Select Mode
    let transport_mode = transport.clone();
    let config_mode = config.clone();
    let ui_mode_weak = ui_weak.clone();
    ui.on_select_mode(move |idx| {
        let mode_idx = idx as usize;
        transport_mode.send_command(&format!("SET:MODE:{}", mode_idx));

        let mode_name = DEFAULT_MODES.get(mode_idx)
            .map(|m| m.name)
            .unwrap_or("SCROLL");
        let desc = mode_description(mode_idx);
        let col = mode_color(mode_idx);

        let (thr, inv) = {
            let cfg = config_mode.lock().unwrap();
            let m = cfg.modes.get(mode_idx);
            (
                m.map(|x| x.threshold).unwrap_or(10),
                m.map(|x| x.invert).unwrap_or(false),
            )
        };

        if let Some(ui) = ui_mode_weak.upgrade() {
            ui.set_active_mode_idx(idx);
            ui.set_active_mode_name(mode_name.into());
            ui.set_active_mode_desc(desc.into());
            ui.set_active_mode_color(col);
            ui.set_active_threshold(thr);
            ui.set_active_invert(inv);
        }
    });

    // 2. Detent Threshold
    let transport_thr = transport.clone();
    let config_thr = config.clone();
    let ui_thr_weak = ui_weak.clone();
    ui.on_threshold_changed(move |val| {
        let active_idx = ui_thr_weak.upgrade().map(|ui| ui.get_active_mode_idx() as usize).unwrap_or(0);
        transport_thr.send_command(&format!("SET:MODE:{},MTHR:{}", active_idx, val));

        let mut cfg = config_thr.lock().unwrap();
        if let Some(m) = cfg.modes.get_mut(active_idx) {
            m.threshold = val;
            let _ = cfg.save_to_disk();
        }
    });

    // 3. Invert Rotation
    let transport_inv = transport.clone();
    let config_inv = config.clone();
    let ui_inv_weak = ui_weak.clone();
    ui.on_invert_toggled(move |val| {
        let active_idx = ui_inv_weak.upgrade().map(|ui| ui.get_active_mode_idx() as usize).unwrap_or(0);
        transport_inv.send_command(&format!("SET:MODE:{},INV:{}", active_idx, if val { 1 } else { 0 }));

        if let Some(ui) = ui_inv_weak.upgrade() {
            ui.set_active_invert(val);
        }

        let mut cfg = config_inv.lock().unwrap();
        if let Some(m) = cfg.modes.get_mut(active_idx) {
            m.invert = val;
            let _ = cfg.save_to_disk();
        }
    });

    // 4. Brightness
    let transport_bri = transport.clone();
    let config_bri = config.clone();
    ui.on_brightness_changed(move |val| {
        transport_bri.send_command(&format!("SET:BRI:{}", val));
        let mut cfg = config_bri.lock().unwrap();
        cfg.bri = val as u8;
        let _ = cfg.save_to_disk();
    });

    // 5. Idle Timeout
    let transport_idle = transport.clone();
    let config_idle = config.clone();
    ui.on_idle_changed(move |val| {
        transport_idle.send_command(&format!("SET:IDLE:{}", val));
        let mut cfg = config_idle.lock().unwrap();
        cfg.idle = val as u16;
        let _ = cfg.save_to_disk();
    });

    // 6. Touch & Spin Action (Action 6 = App Switcher Alt+Tab)
    let transport_tspin = transport.clone();
    let config_tspin = config.clone();
    let ui_tspin_weak = ui_weak.clone();
    ui.on_tspin_changed(move |val| {
        transport_tspin.send_command(&format!("SET:TSPIN:{}", val));
        if let Some(ui) = ui_tspin_weak.upgrade() {
            ui.set_tspin_action(val);
        }
        let mut cfg = config_tspin.lock().unwrap();
        cfg.tspin = val as u8;
        let _ = cfg.save_to_disk();
    });

    // 7. Reject Gesture
    let transport_rej = transport.clone();
    ui.on_reject_gesture(move || {
        transport_rej.send_command("SET:GESTURE_REJECT");
        let t = transport_rej.clone();
        tokio::spawn(async move {
            tokio::time::sleep(tokio::time::Duration::from_millis(200)).await;
            t.send_command("GET:GESTURE_PROFILE");
        });
    });

    // 8. Reset Centroids Baseline
    let transport_reset = transport.clone();
    let config_reset = config.clone();
    let ui_reset_weak = ui_weak.clone();
    ui.on_reset_centroids(move || {
        transport_reset.send_command("SET:GESTURE_PROFILE:110,85,25");
        if let Some(ui) = ui_reset_weak.upgrade() {
            ui.set_g_mu_s(110.0);
            ui.set_g_mu_r(85.0);
            ui.set_g_mu_t(25.0);
        }
        let mut cfg = config_reset.lock().unwrap();
        cfg.g_mu_s = 110.0;
        cfg.g_mu_r = 85.0;
        cfg.g_mu_t = 25.0;
        let _ = cfg.save_to_disk();
    });

    // 9. Hardware White-Balance RGB Calibration
    let transport_cal_r = transport.clone();
    let config_cal_r = config.clone();
    ui.on_cal_r_changed(move |val| {
        transport_cal_r.send_command(&format!("SET:CAL:R:{:.3}", val));
        let mut cfg = config_cal_r.lock().unwrap();
        cfg.cal_r = val;
        let _ = cfg.save_to_disk();
    });

    let transport_cal_g = transport.clone();
    let config_cal_g = config.clone();
    ui.on_cal_g_changed(move |val| {
        transport_cal_g.send_command(&format!("SET:CAL:G:{:.3}", val));
        let mut cfg = config_cal_g.lock().unwrap();
        cfg.cal_g = val;
        let _ = cfg.save_to_disk();
    });

    let transport_cal_b = transport.clone();
    let config_cal_b = config.clone();
    ui.on_cal_b_changed(move |val| {
        transport_cal_b.send_command(&format!("SET:CAL:B:{:.3}", val));
        let mut cfg = config_cal_b.lock().unwrap();
        cfg.cal_b = val;
        let _ = cfg.save_to_disk();
    });

    // 10. Wi-Fi Scanner
    let ui_wifi_scan_weak = ui_weak.clone();
    let transport_wifi_scan = transport.clone();
    ui.on_scan_wifi(move || {
        if let Some(ui) = ui_wifi_scan_weak.upgrade() {
            ui.set_wifi_status_text("Scanning for 2.4 GHz networks...".into());
        }
        transport_wifi_scan.send_command("SCAN:WIFI");

        let ui_scan_handle = ui_wifi_scan_weak.clone();
        tokio::spawn(async move {
            let nets = WifiScanner::scan_networks_async().await;
            slint::invoke_from_event_loop(move || {
                if let Some(ui) = ui_scan_handle.upgrade() {
                    if let Some(first) = nets.first() {
                        ui.set_wifi_status_text(format!("Found {} networks (Best: {} {}%)", nets.len(), first.ssid, first.signal).into());
                        if ui.get_wifi_input_ssid().is_empty() {
                            ui.set_wifi_input_ssid(first.ssid.clone().into());
                        }
                    } else {
                        ui.set_wifi_status_text("Scan complete. Enter SSID manually.".into());
                    }
                }
            }).ok();
        });
    });

    // 11. Wi-Fi Connect
    let transport_wifi_conn = transport.clone();
    let config_wifi_conn = config.clone();
    let ui_wifi_conn_weak = ui_weak.clone();
    ui.on_connect_wifi(move |ssid, pass| {
        let ssid_str = ssid.to_string();
        let pass_str = pass.to_string();

        transport_wifi_conn.send_command(&format!("SET:WIFI:{}:{}", ssid_str, pass_str));

        if let Some(ui) = ui_wifi_conn_weak.upgrade() {
            ui.set_wifi_status_text(format!("Credentials sent to dial. Connecting to {}...", ssid_str).into());
        }

        let mut cfg = config_wifi_conn.lock().unwrap();
        cfg.last_wifi_ssid = ssid_str;
        let _ = cfg.save_to_disk();
    });

    // 12. Windows Auto-Start on Boot
    let ui_boot_weak = ui_weak.clone();
    ui.on_start_on_boot_toggled(move |val| {
        set_autostart(val);
        if let Some(ui) = ui_boot_weak.upgrade() {
            ui.set_start_on_boot(val);
        }
    });

    // 13. HUD Enabled Changed
    let hud_ctrl_en = hud_ctrl.clone();
    let config_hud_en = config.clone();
    let ui_hud_en_weak = ui_weak.clone();
    ui.on_hud_enabled_changed(move |val| {
        hud_ctrl_en.set_enabled(val);
        if let Some(ui) = ui_hud_en_weak.upgrade() {
            ui.set_hud_enabled(val);
        }
        let mut cfg = config_hud_en.lock().unwrap();
        cfg.hud_enabled = val;
        let _ = cfg.save_to_disk();
    });

    // 14. HUD Position Changed
    let hud_ctrl_pos = hud_ctrl.clone();
    let config_hud_pos = config.clone();
    let ui_hud_pos_weak = ui_weak.clone();
    ui.on_hud_position_changed(move |pos| {
        let pos_str = pos.to_string();
        hud_ctrl_pos.set_position(&pos_str);
        if let Some(ui) = ui_hud_pos_weak.upgrade() {
            ui.set_hud_position(pos);
        }
        let mut cfg = config_hud_pos.lock().unwrap();
        cfg.hud_position = pos_str;
        let _ = cfg.save_to_disk();
    });

    // 15. HUD Timeout Changed
    let hud_ctrl_to = hud_ctrl.clone();
    let config_hud_to = config.clone();
    let ui_hud_to_weak = ui_weak.clone();
    ui.on_hud_timeout_changed(move |ms| {
        hud_ctrl_to.set_timeout_ms(ms as u64);
        if let Some(ui) = ui_hud_to_weak.upgrade() {
            ui.set_hud_timeout(ms);
        }
        let mut cfg = config_hud_to.lock().unwrap();
        cfg.hud_timeout_ms = ms as u64;
        let _ = cfg.save_to_disk();
    });

    // 16. HUD Test Clicked
    let hud_ctrl_test = hud_ctrl.clone();
    ui.on_hud_test_clicked(move || {
        hud_ctrl_test.trigger_test();
    });

    ui.run()?;
    Ok(())
}