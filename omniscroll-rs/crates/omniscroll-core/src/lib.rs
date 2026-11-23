//! `omniscroll-core`
//! Pure Rust shared core logic for OmniScroll: RWP v2.1 protocol parsing,
//! detent remainder accumulator, mode and action mappings, Gamma 2.8 tables,
//! and TinyOL kinematic gesture equations.

pub mod protocol;
pub mod modes;
pub mod accumulator;
pub mod gamma;
pub mod gesture;
pub mod config;

pub use protocol::{RwpPacket, PacketType, Flags, RWP_MAGIC, OMP_LEGACY_MAGIC};
pub use modes::{ModeId, ActionId, TouchSpinAction, ModeConfig, StaticModeConfig, HapticProfile, DEFAULT_MODES, HAPTIC_PROFILES};
pub use accumulator::SubTickAccumulator;
pub use gamma::gamma_correct_28;
pub use gesture::{TinyOLCentroids, MahalanobisGate};
pub use config::DeviceConfig;
