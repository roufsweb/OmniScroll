//! Fractional remainder accumulator for Microsoft High-Resolution Smooth Scrolling
//! and stepped mechanical detents.

/// Manages fractional sub-ticks and stepped mechanical detents with zero drift.
#[derive(Debug, Clone, Default)]
pub struct SubTickAccumulator {
    remainder: i32,
    detent_acc: i32,
}

impl SubTickAccumulator {
    pub const WINDOWS_DETENT_TICKS: i32 = 120; // Windows standard units per full notch

    pub fn new() -> Self {
        Self {
            remainder: 0,
            detent_acc: 0,
        }
    }

    /// Resets all accumulated remainders to zero.
    pub fn reset(&mut self) {
        self.remainder = 0;
        self.detent_acc = 0;
    }

    /// Converts raw optical counts `dx` into Microsoft High-Res sub-ticks
    /// using the mode's configured detent `threshold` (e.g. 10 or 25 counts per detent).
    /// Preserves fractional remainders so cumulative rotation never loses sub-pixels.
    pub fn compute_high_res_subticks(&mut self, dx: i32, threshold: i32) -> i32 {
        let thr = threshold.max(1);
        let total = (dx * Self::WINDOWS_DETENT_TICKS) + self.remainder;
        let sub_ticks = total / thr;
        self.remainder = total % thr;
        sub_ticks
    }

    /// Accumulates raw counts for stepped legacy fallback mode.
    /// Returns the number of discrete detent clicks fired (+1, -1, or multiple).
    pub fn accumulate_stepped(&mut self, dx: i32, threshold: i32) -> i32 {
        let thr = threshold.max(1);
        self.detent_acc += dx;
        let mut steps = 0;

        while self.detent_acc >= thr {
            steps += 1;
            self.detent_acc -= thr;
        }

        while self.detent_acc <= -thr {
            steps -= 1;
            self.detent_acc += thr;
        }

        steps
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_high_res_subticks_even_division() {
        let mut acc = SubTickAccumulator::new();
        // Threshold 10 evenly divides 120 (12 sub-ticks per raw count)
        let sub_ticks = acc.compute_high_res_subticks(1, 10);
        assert_eq!(sub_ticks, 12);

        let sub_ticks_5 = acc.compute_high_res_subticks(5, 10);
        assert_eq!(sub_ticks_5, 60);
    }

    #[test]
    fn test_high_res_remainder_preservation() {
        let mut acc = SubTickAccumulator::new();
        // Threshold 25 does not evenly divide 120 (120/25 = 4.8)
        // 25 counts should produce exactly 120 sub-ticks total!
        let mut total_subticks = 0;
        for _ in 0..25 {
            total_subticks += acc.compute_high_res_subticks(1, 25);
        }
        assert_eq!(total_subticks, 120);
    }

    #[test]
    fn test_stepped_accumulation() {
        let mut acc = SubTickAccumulator::new();
        assert_eq!(acc.accumulate_stepped(5, 10), 0);
        assert_eq!(acc.accumulate_stepped(5, 10), 1);
        assert_eq!(acc.accumulate_stepped(-12, 10), -1);
    }
}
