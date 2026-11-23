//! Native Win32 `SendInput` injection with sub-microsecond latency.

use std::mem::size_of;
use std::thread::sleep;
use std::time::Duration;
use windows::Win32::UI::Input::KeyboardAndMouse::{
    SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, INPUT_MOUSE, KEYBDINPUT, KEYBD_EVENT_FLAGS,
    KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, MOUSEEVENTF_HWHEEL, MOUSEEVENTF_WHEEL, MOUSEINPUT,
    VIRTUAL_KEY, VK_BROWSER_BACK, VK_BROWSER_FORWARD, VK_C, VK_CONTROL,
    VK_LEFT, VK_LWIN, VK_MEDIA_NEXT_TRACK, VK_MEDIA_PLAY_PAUSE, VK_MEDIA_PREV_TRACK, VK_MENU, VK_RIGHT,
    VK_SHIFT, VK_TAB, VK_V, VK_VOLUME_DOWN, VK_VOLUME_UP, VK_Z,
};

use omniscroll_core::accumulator::SubTickAccumulator;
use omniscroll_core::modes::{ActionId, ModeId, TouchSpinAction};

/// Thread-safe Win32 input injector.
pub struct Win32Input {
    pub v_acc: SubTickAccumulator,
    pub h_acc: SubTickAccumulator,
    pub mode_acc: SubTickAccumulator,
    pub alt_held: bool,
}

impl Default for Win32Input {
    fn default() -> Self {
        Self::new()
    }
}

impl Win32Input {
    pub fn new() -> Self {
        Self {
            v_acc: SubTickAccumulator::new(),
            h_acc: SubTickAccumulator::new(),
            mode_acc: SubTickAccumulator::new(),
            alt_held: false,
        }
    }

    /// Injects vertical mouse wheel scroll (sub-ticks or full detent notches).
    pub fn scroll_vertical(&self, ticks: i32) {
        if ticks == 0 {
            return;
        }

        let input = INPUT {
            r#type: INPUT_MOUSE,
            Anonymous: INPUT_0 {
                mi: MOUSEINPUT {
                    dx: 0,
                    dy: 0,
                    mouseData: ticks as u32,
                    dwFlags: MOUSEEVENTF_WHEEL,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };

        unsafe {
            SendInput(&[input], size_of::<INPUT>() as i32);
        }
    }

    /// Injects horizontal mouse wheel scroll (AC Pan).
    pub fn scroll_horizontal(&self, ticks: i32) {
        if ticks == 0 {
            return;
        }

        let input = INPUT {
            r#type: INPUT_MOUSE,
            Anonymous: INPUT_0 {
                mi: MOUSEINPUT {
                    dx: 0,
                    dy: 0,
                    mouseData: ticks as u32,
                    dwFlags: MOUSEEVENTF_HWHEEL,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };

        unsafe {
            SendInput(&[input], size_of::<INPUT>() as i32);
        }
    }

    /// Presses a virtual key.
    pub fn press_key(&self, vk: VIRTUAL_KEY, extended: bool) {
        let mut flags = KEYBD_EVENT_FLAGS(0);
        if extended {
            flags |= KEYEVENTF_EXTENDEDKEY;
        }

        let input = INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: vk,
                    wScan: 0,
                    dwFlags: flags,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };

        unsafe {
            SendInput(&[input], size_of::<INPUT>() as i32);
        }
    }

    /// Releases a virtual key.
    pub fn release_key(&self, vk: VIRTUAL_KEY, extended: bool) {
        let mut flags = KEYEVENTF_KEYUP;
        if extended {
            flags |= KEYEVENTF_EXTENDEDKEY;
        }

        let input = INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: vk,
                    wScan: 0,
                    dwFlags: flags,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };

        unsafe {
            SendInput(&[input], size_of::<INPUT>() as i32);
        }
    }

    /// Taps a key with 15ms hold duration.
    pub fn tap_key(&self, vk: VIRTUAL_KEY, extended: bool) {
        self.press_key(vk, extended);
        sleep(Duration::from_millis(15));
        self.release_key(vk, extended);
    }

    /// Taps a key combination in order, then releases in reverse.
    pub fn tap_combo(&self, keys: &[VIRTUAL_KEY]) {
        for &k in keys {
            self.press_key(k, false);
        }
        sleep(Duration::from_millis(15));
        for &k in keys.iter().rev() {
            self.release_key(k, false);
        }
    }

    /// Dispatches a single action (Flick gesture, shortcut, or single-tap).
    pub fn dispatch_action(&self, action: ActionId) {
        match action {
            ActionId::None => {}
            ActionId::BrowserBack => self.tap_key(VK_BROWSER_BACK, true),
            ActionId::BrowserForward => self.tap_key(VK_BROWSER_FORWARD, true),
            ActionId::Undo => self.tap_combo(&[VK_CONTROL, VK_Z]),
            ActionId::Redo => self.tap_combo(&[VK_CONTROL, VK_SHIFT, VK_Z]),
            ActionId::MediaPrevious => self.tap_key(VK_MEDIA_PREV_TRACK, true),
            ActionId::MediaNext => self.tap_key(VK_MEDIA_NEXT_TRACK, true),
            ActionId::PreviousTab => self.tap_combo(&[VK_CONTROL, VK_SHIFT, VK_TAB]),
            ActionId::NextTab => self.tap_combo(&[VK_CONTROL, VK_TAB]),
            ActionId::PreviousDesktop => self.tap_combo(&[VK_LWIN, VK_CONTROL, VK_LEFT]),
            ActionId::NextDesktop => self.tap_combo(&[VK_LWIN, VK_CONTROL, VK_RIGHT]),
            ActionId::VolumeDown => self.tap_key(VK_VOLUME_DOWN, true),
            ActionId::VolumeUp => self.tap_key(VK_VOLUME_UP, true),
            ActionId::Copy => self.tap_combo(&[VK_CONTROL, VK_C]),
            ActionId::Paste => self.tap_combo(&[VK_CONTROL, VK_V]),
            ActionId::PlayPause => self.tap_key(VK_MEDIA_PLAY_PAUSE, true),
            _ => {}
        }
    }

    /// Translates raw optical motion delta in the context of the active mode.
    pub fn dispatch_mode_motion(
        &mut self,
        mode: ModeId,
        delta: i32,
        threshold: i32,
        is_high_res: bool,
    ) {
        match mode {
            ModeId::Scroll => {
                if is_high_res {
                    let sub_ticks = self.v_acc.compute_high_res_subticks(delta, threshold);
                    if sub_ticks != 0 {
                        self.scroll_vertical(sub_ticks);
                    }
                } else {
                    let steps = self.v_acc.accumulate_stepped(delta, threshold);
                    if steps != 0 {
                        self.scroll_vertical(steps * 120);
                    }
                }
            }
            ModeId::HScroll => {
                if is_high_res {
                    let sub_ticks = self.h_acc.compute_high_res_subticks(delta, threshold);
                    if sub_ticks != 0 {
                        self.scroll_horizontal(sub_ticks);
                    }
                } else {
                    let steps = self.h_acc.accumulate_stepped(delta, threshold);
                    if steps != 0 {
                        self.scroll_horizontal(steps * 120);
                    }
                }
            }
            ModeId::Volume => {
                let steps = self.mode_acc.accumulate_stepped(delta, threshold);
                for _ in 0..steps {
                    self.tap_key(VK_VOLUME_UP, true);
                }
                for _ in 0..(-steps) {
                    self.tap_key(VK_VOLUME_DOWN, true);
                }
            }
            ModeId::Timeline => {
                let steps = self.mode_acc.accumulate_stepped(delta, threshold);
                for _ in 0..steps {
                    self.tap_key(VK_RIGHT, true);
                }
                for _ in 0..(-steps) {
                    self.tap_key(VK_LEFT, true);
                }
            }
            ModeId::Zoom => {
                let steps = self.mode_acc.accumulate_stepped(delta, threshold);
                if steps != 0 {
                    self.press_key(VK_CONTROL, false);
                    self.scroll_vertical(steps * 120);
                    self.release_key(VK_CONTROL, false);
                }
            }
            ModeId::Tabbing => {
                let steps = self.mode_acc.accumulate_stepped(delta, threshold);
                for _ in 0..steps {
                    self.tap_combo(&[VK_CONTROL, VK_TAB]);
                }
                for _ in 0..(-steps) {
                    self.tap_combo(&[VK_CONTROL, VK_SHIFT, VK_TAB]);
                }
            }
            ModeId::UndoRedo => {
                let steps = self.mode_acc.accumulate_stepped(delta, threshold);
                for _ in 0..steps {
                    self.tap_combo(&[VK_CONTROL, VK_SHIFT, VK_Z]); // Redo
                }
                for _ in 0..(-steps) {
                    self.tap_combo(&[VK_CONTROL, VK_Z]); // Undo
                }
            }
            ModeId::Brightness => {
                // Windows doesn't provide standard consumer keys for internal display brightness
                // without WMI/DxgKrnl calls. We can map steps to volume/fallback or custom hook.
            }
        }
    }

    /// Dispatches continuous bidirectional Touch & Spin motion.
    pub fn dispatch_touch_spin(&mut self, action: TouchSpinAction, delta: i32, threshold: i32) {
        match action {
            TouchSpinAction::Disabled => {}
            TouchSpinAction::HorizontalScroll => {
                let sub_ticks = self.h_acc.compute_high_res_subticks(delta, threshold);
                if sub_ticks != 0 {
                    self.scroll_horizontal(sub_ticks);
                }
            }
            TouchSpinAction::UniversalZoom => {
                self.press_key(VK_CONTROL, false);
                self.scroll_vertical(if delta > 0 { 120 } else { -120 });
                self.release_key(VK_CONTROL, false);
            }
            TouchSpinAction::TurboScroll => {
                let sub_ticks = self.v_acc.compute_high_res_subticks(delta * 4, threshold);
                if sub_ticks != 0 {
                    self.scroll_vertical(sub_ticks);
                }
            }
            TouchSpinAction::TimelineScrub => {
                self.press_key(VK_SHIFT, false);
                self.tap_key(if delta > 0 { VK_RIGHT } else { VK_LEFT }, true);
                self.release_key(VK_SHIFT, false);
            }
            TouchSpinAction::Volume => {
                self.tap_key(if delta > 0 { VK_VOLUME_UP } else { VK_VOLUME_DOWN }, true);
            }
            TouchSpinAction::AppSwitcher => {
                if !self.alt_held {
                    self.press_key(VK_MENU, false);
                    self.alt_held = true;
                }
                let steps = self.mode_acc.accumulate_stepped(delta, threshold);
                for _ in 0..steps {
                    self.tap_key(VK_TAB, false);
                }
                for _ in 0..(-steps) {
                    self.press_key(VK_SHIFT, false);
                    self.tap_key(VK_TAB, false);
                    self.release_key(VK_SHIFT, false);
                }
            }
        }
    }

    /// Releases Alt clutch key and commits the selected window.
    pub fn release_alt_clutch(&mut self) {
        if self.alt_held {
            self.release_key(VK_MENU, false);
            self.alt_held = false;
        }
    }
}
