//! Operational mode definitions and action mappings.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum ModeId {
    Scroll = 0,
    Volume = 1,
    Timeline = 2,
    Zoom = 3,
    HScroll = 4,
    Brightness = 5,
    Tabbing = 6,
    UndoRedo = 7,
}

impl ModeId {
    pub fn from_index(idx: usize) -> Option<Self> {
        match idx {
            0 => Some(ModeId::Scroll),
            1 => Some(ModeId::Volume),
            2 => Some(ModeId::Timeline),
            3 => Some(ModeId::Zoom),
            4 => Some(ModeId::HScroll),
            5 => Some(ModeId::Brightness),
            6 => Some(ModeId::Tabbing),
            7 => Some(ModeId::UndoRedo),
            _ => None,
        }
    }

    pub fn name(&self) -> &'static str {
        match self {
            ModeId::Scroll => "SCROLL",
            ModeId::Volume => "VOLUME",
            ModeId::Timeline => "TIMELINE",
            ModeId::Zoom => "ZOOM",
            ModeId::HScroll => "H_SCROLL",
            ModeId::Brightness => "BRIGHTNESS",
            ModeId::Tabbing => "TABBING",
            ModeId::UndoRedo => "UNDO_REDO",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum ActionId {
    None = 0,
    BrowserBack = 1,
    BrowserForward = 2,
    Undo = 3,
    Redo = 4,
    MediaPrevious = 5,
    MediaNext = 6,
    PreviousTab = 7,
    NextTab = 8,
    PreviousDesktop = 9,
    NextDesktop = 10,
    VolumeDown = 11,
    VolumeUp = 12,
    Copy = 13,
    Paste = 14,
    NextMode = 15,
    PrevMode = 16,
    DirectMode0 = 17,
    DirectMode1 = 18,
    DirectMode2 = 19,
    DirectMode3 = 20,
    DirectMode4 = 21,
    DirectMode5 = 22,
    DirectMode6 = 23,
    DirectMode7 = 24,
    PlayPause = 25,
    NeuralReject = 99,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum TouchSpinAction {
    Disabled = 0,
    HorizontalScroll = 1,
    UniversalZoom = 2,
    TurboScroll = 3,
    TimelineScrub = 4,
    Volume = 5,
    AppSwitcher = 6,
}

impl From<u8> for TouchSpinAction {
    fn from(val: u8) -> Self {
        match val {
            0 => TouchSpinAction::Disabled,
            1 => TouchSpinAction::HorizontalScroll,
            2 => TouchSpinAction::UniversalZoom,
            3 => TouchSpinAction::TurboScroll,
            4 => TouchSpinAction::TimelineScrub,
            5 => TouchSpinAction::Volume,
            6 => TouchSpinAction::AppSwitcher,
            _ => TouchSpinAction::Disabled,
        }
    }
}

impl From<u8> for ActionId {
    fn from(val: u8) -> Self {
        match val {
            0 => ActionId::None,
            1 => ActionId::BrowserBack,
            2 => ActionId::BrowserForward,
            3 => ActionId::Undo,
            4 => ActionId::Redo,
            5 => ActionId::MediaPrevious,
            6 => ActionId::MediaNext,
            7 => ActionId::PreviousTab,
            8 => ActionId::NextTab,
            9 => ActionId::PreviousDesktop,
            10 => ActionId::NextDesktop,
            11 => ActionId::VolumeDown,
            12 => ActionId::VolumeUp,
            13 => ActionId::Copy,
            14 => ActionId::Paste,
            15 => ActionId::NextMode,
            16 => ActionId::PrevMode,
            17 => ActionId::DirectMode0,
            18 => ActionId::DirectMode1,
            19 => ActionId::DirectMode2,
            20 => ActionId::DirectMode3,
            21 => ActionId::DirectMode4,
            22 => ActionId::DirectMode5,
            23 => ActionId::DirectMode6,
            24 => ActionId::DirectMode7,
            25 => ActionId::PlayPause,
            99 => ActionId::NeuralReject,
            _ => ActionId::None,
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct HapticProfile {
    pub name: &'static str,
    pub freq_hz: u16,
    pub dur_ms: u16,
}

pub const HAPTIC_PROFILES: [HapticProfile; 5] = [
    HapticProfile { name: "Click", freq_hz: 200, dur_ms: 20 }, // 0 — Sharp detent
    HapticProfile { name: "Thud",  freq_hz: 120, dur_ms: 45 }, // 1 — Deep bump
    HapticProfile { name: "Tick",  freq_hz: 300, dur_ms: 10 }, // 2 — Light ratchet
    HapticProfile { name: "Soft",  freq_hz: 150, dur_ms: 25 }, // 3 — Gentle nudge
    HapticProfile { name: "Off",   freq_hz: 0,   dur_ms: 0  }, // 4 — Silent
];

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ModeConfig {
    pub name: String,
    pub desc: String,
    pub color_rgb: [u8; 3],
    pub haptic_profile: u8,
    pub enabled: bool,
    pub invert: bool,
    pub threshold: i32,
}

#[derive(Debug, Clone, Copy)]
pub struct StaticModeConfig {
    pub name: &'static str,
    pub color_rgb: [u8; 3],
    pub haptic_profile: u8,
    pub enabled: bool,
    pub invert: bool,
    pub threshold: i32,
}

pub const DEFAULT_MODES: [StaticModeConfig; 8] = [
    StaticModeConfig { name: "SCROLL",     color_rgb: [0,   0,   255], haptic_profile: 0, enabled: true,  invert: false, threshold: 10 },
    StaticModeConfig { name: "VOLUME",     color_rgb: [0,   255, 0  ], haptic_profile: 3, enabled: true,  invert: false, threshold: 25 },
    StaticModeConfig { name: "TIMELINE",   color_rgb: [255, 0,   128], haptic_profile: 0, enabled: true,  invert: false, threshold: 15 },
    StaticModeConfig { name: "ZOOM",       color_rgb: [255, 149, 0  ], haptic_profile: 0, enabled: false, invert: false, threshold: 15 },
    StaticModeConfig { name: "H_SCROLL",   color_rgb: [0,   194, 168], haptic_profile: 2, enabled: false, invert: false, threshold: 10 },
    StaticModeConfig { name: "BRIGHTNESS", color_rgb: [255, 215, 0  ], haptic_profile: 3, enabled: false, invert: false, threshold: 20 },
    StaticModeConfig { name: "TABBING",    color_rgb: [155, 89,  182], haptic_profile: 0, enabled: false, invert: false, threshold: 20 },
    StaticModeConfig { name: "UNDO_REDO",  color_rgb: [231, 76,  60 ], haptic_profile: 1, enabled: false, invert: false, threshold: 15 },
];
