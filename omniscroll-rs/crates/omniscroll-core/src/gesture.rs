//! TinyOL On-Device Kinematic Gesture Equations & Mahalanobis Distance Gating.

pub const GESTURE_SIGMA_S: f32 = 45.0; // Stroke travel variance
pub const GESTURE_SIGMA_R: f32 = 35.0; // Recoil rebound variance
pub const GESTURE_SIGMA_T: f32 = 18.0; // Turnaround dwell variance
pub const GESTURE_LEARN_ALPHA: f32 = 0.08; // EMA adaptation rate

// Physiological bounding box limits
pub const MU_S_MIN: f32 = 25.0;
pub const MU_S_MAX: f32 = 240.0;
pub const MU_R_MIN: f32 = 20.0;
pub const MU_R_MAX: f32 = 200.0;
pub const MU_T_MIN: f32 = 10.0;
pub const MU_T_MAX: f32 = 60.0;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TinyOLCentroids {
    pub mu_s: f32, // Mean stroke travel (counts)
    pub mu_r: f32, // Mean recoil rebound (counts)
    pub mu_t: f32, // Mean turnaround dwell (ms)
}

impl Default for TinyOLCentroids {
    fn default() -> Self {
        Self {
            mu_s: 110.0,
            mu_r: 85.0,
            mu_t: 25.0,
        }
    }
}

impl TinyOLCentroids {
    pub fn new(mu_s: f32, mu_r: f32, mu_t: f32) -> Self {
        Self { mu_s, mu_r, mu_t }
    }

    /// Clamps centroids strictly within physiological limits to prevent neural drift.
    pub fn clamp_physiological(&mut self) {
        self.mu_s = self.mu_s.clamp(MU_S_MIN, MU_S_MAX);
        self.mu_r = self.mu_r.clamp(MU_R_MIN, MU_R_MAX);
        self.mu_t = self.mu_t.clamp(MU_T_MIN, MU_T_MAX);
    }

    /// Recursively adapts personal centroids using Exponential Moving Average (EMA).
    pub fn adapt(&mut self, stroke: f32, recoil: f32, dwell: f32) {
        self.mu_s += GESTURE_LEARN_ALPHA * (stroke - self.mu_s);
        self.mu_r += GESTURE_LEARN_ALPHA * (recoil - self.mu_r);
        self.mu_t += GESTURE_LEARN_ALPHA * (dwell - self.mu_t);
        self.clamp_physiological();
    }
}

pub struct MahalanobisGate;

impl MahalanobisGate {
    /// Computes normalized Mahalanobis distance squared:
    /// d^2 = ((S - mu_S)/sigma_S)^2 + ((R - mu_R)/sigma_R)^2 + ((T - mu_T)/sigma_T)^2
    pub fn compute_d2(centroids: &TinyOLCentroids, stroke: f32, recoil: f32, dwell: f32) -> f32 {
        let ds = (stroke - centroids.mu_s) / GESTURE_SIGMA_S;
        let dr = (recoil - centroids.mu_r) / GESTURE_SIGMA_R;
        let dt = (dwell - centroids.mu_t) / GESTURE_SIGMA_T;

        ds * ds + dr * dr + dt * dt
    }

    /// Evaluates candidate snap energy:
    /// E_snap = R^2 / (T_dwell + 1)
    pub fn compute_snap_energy(recoil: f32, dwell_ms: f32) -> f32 {
        (recoil * recoil) / (dwell_ms + 1.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mahalanobis_at_mean() {
        let c = TinyOLCentroids::default();
        let d2 = MahalanobisGate::compute_d2(&c, 110.0, 85.0, 25.0);
        assert!((d2 - 0.0).abs() < 1e-6);
    }

    #[test]
    fn test_snap_energy() {
        let energy = MahalanobisGate::compute_snap_energy(85.0, 25.0);
        // 85^2 / 26 = 7225 / 26 ≈ 277.88 >> 20
        assert!(energy > 20.0);
    }
}
