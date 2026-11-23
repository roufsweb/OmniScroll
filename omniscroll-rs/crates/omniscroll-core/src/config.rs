//! Device configuration persistence, JSON schema, and command generation.

use std::fs;
use std::path::PathBuf;
use serde::{Deserialize, Serialize};
use crate::modes::{ModeConfig, DEFAULT_MODES};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DeviceConfig {
    #[serde(default = "default_bri")]
    pub bri: u8,
    #[serde(default = "default_idle")]
    pub idle: u16,
    #[serde(default = "default_thr")]
    pub thr: u16,
    #[serde(default = "default_cal")]
    pub cal_r: f32,
    #[serde(default = "default_cal")]
    pub cal_g: f32,
    #[serde(default = "default_cal")]
    pub cal_b: f32,
    #[serde(default = "default_flick_fwd")]
    pub flick_fwd: u8,
    #[serde(default = "default_flick_rev")]
    pub flick_rev: u8,
    #[serde(default = "default_tspin")]
    pub tspin: u8,
    #[serde(default = "default_single_tap")]
    pub single_tap: u8,
    #[serde(default = "default_mu_s")]
    pub g_mu_s: f32,
    #[serde(default = "default_mu_r")]
    pub g_mu_r: f32,
    #[serde(default = "default_mu_t")]
    pub g_mu_t: f32,
    #[serde(default = "default_modes_vec")]
    pub modes: Vec<ModeConfig>,

    // PC-side Desktop App preferences
    #[serde(default)]
    pub last_wifi_ip: String,
    #[serde(default)]
    pub last_wifi_ssid: String,
    #[serde(default)]
    pub start_on_boot: bool,
    #[serde(default = "default_theme")]
    pub theme: String,

    // Windows On-Screen Glassmorphic HUD overlay preferences
    #[serde(default = "default_hud_enabled")]
    pub hud_enabled: bool,
    #[serde(default = "default_hud_position")]
    pub hud_position: String,
    #[serde(default = "default_hud_timeout")]
    pub hud_timeout_ms: u64,
}

fn default_bri() -> u8 { 100 }
fn default_idle() -> u16 { 30 }
fn default_thr() -> u16 { 800 }
fn default_cal() -> f32 { 1.0 }
fn default_flick_fwd() -> u8 { 15 } // Next Mode
fn default_flick_rev() -> u8 { 16 } // Prev Mode
fn default_tspin() -> u8 { 6 }      // App Switcher Clutch (Alt+Tab)
fn default_single_tap() -> u8 { 25 } // Play/Pause
fn default_mu_s() -> f32 { 110.0 }
fn default_mu_r() -> f32 { 85.0 }
fn default_mu_t() -> f32 { 25.0 }
fn default_theme() -> String { "walnut".to_string() }
fn default_hud_enabled() -> bool { true }
fn default_hud_position() -> String { "right".to_string() }
fn default_hud_timeout() -> u64 { 2500 }

fn default_modes_vec() -> Vec<ModeConfig> {
    DEFAULT_MODES.iter().map(|m| ModeConfig {
        name: m.name.to_string(),
        desc: match m.name {
            "SCROLL" => "Vertical page scroll".to_string(),
            "VOLUME" => "System volume control".to_string(),
            "TIMELINE" => "Frame-by-frame arrow keys".to_string(),
            "ZOOM" => "Universal zoom in any app".to_string(),
            "H_SCROLL" => "Horizontal side-scroll".to_string(),
            "BRIGHTNESS" => "Display brightness keys".to_string(),
            "TABBING" => "Cycle browser & app tabs".to_string(),
            "UNDO_REDO" => "Ctrl+Z / Ctrl+Shift+Z".to_string(),
            _ => "Custom mode".to_string(),
        },
        color_rgb: m.color_rgb,
        haptic_profile: m.haptic_profile,
        enabled: m.enabled,
        invert: m.invert,
        threshold: m.threshold,
    }).collect()
}

impl Default for DeviceConfig {
    fn default() -> Self {
        Self {
            bri: default_bri(),
            idle: default_idle(),
            thr: default_thr(),
            cal_r: default_cal(),
            cal_g: default_cal(),
            cal_b: default_cal(),
            flick_fwd: default_flick_fwd(),
            flick_rev: default_flick_rev(),
            tspin: default_tspin(),
            single_tap: default_single_tap(),
            g_mu_s: default_mu_s(),
            g_mu_r: default_mu_r(),
            g_mu_t: default_mu_t(),
            modes: default_modes_vec(),
            last_wifi_ip: String::new(),
            last_wifi_ssid: String::new(),
            start_on_boot: false,
            theme: default_theme(),
            hud_enabled: default_hud_enabled(),
            hud_position: default_hud_position(),
            hud_timeout_ms: default_hud_timeout(),
        }
    }
}

impl DeviceConfig {
    /// Returns the standard config path under `%APPDATA%\OmniScroll\config.json`.
    pub fn config_path() -> PathBuf {
        let mut path = if let Ok(appdata) = std::env::var("APPDATA") {
            PathBuf::from(appdata)
        } else {
            PathBuf::from(".")
        };
        path.push("OmniScroll");
        path.push("config.json");
        path
    }

    /// Loads the configuration from disk, falling back to default if not found.
    pub fn load_from_disk() -> Self {
        let p = Self::config_path();
        if p.exists() {
            if let Ok(content) = fs::read_to_string(&p) {
                if let Ok(cfg) = serde_json::from_str::<DeviceConfig>(&content) {
                    return cfg;
                }
            }
        }
        Self::default()
    }

    /// Atomically persists configuration to `%APPDATA%\OmniScroll\config.json`.
    pub fn save_to_disk(&self) -> std::io::Result<()> {
        let p = Self::config_path();
        if let Some(parent) = p.parent() {
            fs::create_dir_all(parent)?;
        }
        let json_str = serde_json::to_string_pretty(self)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
        fs::write(p, json_str)
    }

    /// Parses a raw `CONFIG:{...}` payload emitted by OmniScroll hardware over Serial or UDP.
    pub fn parse_hardware_config(line: &str) -> Option<Self> {
        let payload = if let Some(stripped) = line.strip_prefix("CONFIG:") {
            stripped.trim()
        } else {
            line.trim()
        };

        #[derive(Deserialize)]
        struct RawHwMode {
            name: String,
            #[serde(default)]
            en: u8,
            #[serde(default)]
            c: String,
            #[serde(default)]
            hp: u8,
            #[serde(default)]
            inv: u8,
            #[serde(default)]
            thr: i32,
        }

        #[derive(Deserialize)]
        struct RawHwConfig {
            #[serde(default)]
            bri: Option<u8>,
            #[serde(default)]
            idle: Option<u16>,
            #[serde(default)]
            thr: Option<u16>,
            #[serde(default)]
            cal_r: Option<f32>,
            #[serde(default)]
            cal_g: Option<f32>,
            #[serde(default)]
            cal_b: Option<f32>,
            #[serde(default)]
            flick_fwd: Option<u8>,
            #[serde(default)]
            flick_rev: Option<u8>,
            #[serde(default)]
            tspin: Option<u8>,
            #[serde(default)]
            single_tap: Option<u8>,
            #[serde(default)]
            g_mu_s: Option<f32>,
            #[serde(default)]
            g_mu_r: Option<f32>,
            #[serde(default)]
            g_mu_t: Option<f32>,
            #[serde(default)]
            modes: Vec<RawHwMode>,
        }

        let raw: RawHwConfig = serde_json::from_str(payload).ok()?;
        let mut cfg = Self::default();

        if let Some(v) = raw.bri { cfg.bri = v; }
        if let Some(v) = raw.idle { cfg.idle = v; }
        if let Some(v) = raw.thr { cfg.thr = v; }
        if let Some(v) = raw.cal_r { cfg.cal_r = v; }
        if let Some(v) = raw.cal_g { cfg.cal_g = v; }
        if let Some(v) = raw.cal_b { cfg.cal_b = v; }
        if let Some(v) = raw.flick_fwd { cfg.flick_fwd = v; }
        if let Some(v) = raw.flick_rev { cfg.flick_rev = v; }
        if let Some(v) = raw.tspin { cfg.tspin = v; }
        if let Some(v) = raw.single_tap { cfg.single_tap = v; }
        if let Some(v) = raw.g_mu_s { cfg.g_mu_s = v; }
        if let Some(v) = raw.g_mu_r { cfg.g_mu_r = v; }
        if let Some(v) = raw.g_mu_t { cfg.g_mu_t = v; }

        if !raw.modes.is_empty() {
            cfg.modes = raw.modes.into_iter().map(|rm| {
                // Parse hex color string "FFA000" or "007AFF"
                let rgb = if rm.c.len() == 6 {
                    let r = u8::from_str_radix(&rm.c[0..2], 16).unwrap_or(0);
                    let g = u8::from_str_radix(&rm.c[2..4], 16).unwrap_or(0);
                    let b = u8::from_str_radix(&rm.c[4..6], 16).unwrap_or(255);
                    [r, g, b]
                } else {
                    [0, 122, 255]
                };

                let desc = match rm.name.as_str() {
                    "SCROLL" => "Vertical page scroll".to_string(),
                    "VOLUME" => "System volume control".to_string(),
                    "TIMELINE" => "Frame-by-frame arrow keys".to_string(),
                    "ZOOM" => "Universal zoom in any app".to_string(),
                    "H_SCROLL" => "Horizontal side-scroll".to_string(),
                    "BRIGHTNESS" => "Display brightness keys".to_string(),
                    "TABBING" => "Cycle browser & app tabs".to_string(),
                    "UNDO_REDO" => "Ctrl+Z / Ctrl+Shift+Z".to_string(),
                    _ => "Custom mode".to_string(),
                };

                ModeConfig {
                    name: rm.name,
                    desc,
                    color_rgb: rgb,
                    haptic_profile: rm.hp,
                    enabled: rm.en == 1,
                    invert: rm.inv == 1,
                    threshold: rm.thr,
                }
            }).collect();
        }

        Some(cfg)
    }

    /// Generates batch `SET:...` command strings to synchronize hardware NVS to match this configuration.
    pub fn to_sync_commands(&self) -> Vec<String> {
        let mut cmds = Vec::with_capacity(16);
        cmds.push(format!("SET:BRI:{}", self.bri));
        cmds.push(format!("SET:IDLE:{}", self.idle));
        cmds.push(format!("SET:THR:{}", self.thr));
        cmds.push(format!("SET:FLICK_FWD:{}", self.flick_fwd));
        cmds.push(format!("SET:FLICK_REV:{}", self.flick_rev));
        cmds.push(format!("SET:TSPIN:{}", self.tspin));
        cmds.push(format!("SET:SINGLE_TAP:{}", self.single_tap));

        for (idx, m) in self.modes.iter().enumerate() {
            let hex_c = format!("{:02x}{:02x}{:02x}", m.color_rgb[0], m.color_rgb[1], m.color_rgb[2]);
            cmds.push(format!(
                "SET:MODE:{},EN:{},C:#{},THR:{},HP:{},INV:{}",
                idx,
                if m.enabled { 1 } else { 0 },
                hex_c,
                m.threshold,
                m.haptic_profile,
                if m.invert { 1 } else { 0 }
            ));
        }

        cmds
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_device_config_roundtrip() {
        let cfg = DeviceConfig::default();
        let json = serde_json::to_string_pretty(&cfg).unwrap();
        let decoded: DeviceConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(cfg.bri, decoded.bri);
        assert_eq!(cfg.tspin, 6);
        assert_eq!(cfg.modes.len(), 8);
    }

    #[test]
    fn test_parse_real_hardware_payload() {
        let raw = r#"CONFIG:{"bri":100,"idle":33,"thr":800,"cal_r":1.000,"cal_g":1.000,"cal_b":1.000,"flick_fwd":15,"flick_rev":7,"tspin":6,"single_tap":25,"g_mu_s":110.0,"g_mu_r":85.0,"g_mu_t":25.0,"modes":[{"name":"SCROLL","en":1,"c":"0000ff","hp":0,"inv":0,"thr":10},{"name":"VOLUME","en":0,"c":"00ff00","hp":0,"inv":0,"thr":25}]}"#;
        let parsed = DeviceConfig::parse_hardware_config(raw).expect("Failed to parse hardware payload");
        assert_eq!(parsed.bri, 100);
        assert_eq!(parsed.idle, 33);
        assert_eq!(parsed.thr, 800);
        assert_eq!(parsed.tspin, 6);
        assert_eq!(parsed.single_tap, 25);
        assert_eq!(parsed.modes.len(), 2);
        assert_eq!(parsed.modes[0].name, "SCROLL");
        assert_eq!(parsed.modes[0].color_rgb, [0, 0, 255]);
        assert_eq!(parsed.modes[0].enabled, true);
        assert_eq!(parsed.modes[1].name, "VOLUME");
        assert_eq!(parsed.modes[1].color_rgb, [0, 255, 0]);
        assert_eq!(parsed.modes[1].enabled, false);
    }

    #[test]
    fn test_generate_sync_commands() {
        let cfg = DeviceConfig::default();
        let cmds = cfg.to_sync_commands();
        assert!(cmds.iter().any(|c| c == "SET:BRI:100"));
        assert!(cmds.iter().any(|c| c == "SET:TSPIN:6"));
        assert!(cmds.iter().any(|c| c.starts_with("SET:MODE:0")));
    }
}
