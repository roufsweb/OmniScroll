//! Native Win32 Dynamic Glassmorphic Wheel HUD Overlay for OmniScroll Studio.

#![allow(unused_must_use)]

use std::sync::atomic::{AtomicBool, AtomicI32, AtomicIsize, AtomicU64, AtomicU8, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{Duration, Instant};

use tokio::sync::broadcast;
use tracing::warn;

use windows::core::w;
use windows::Win32::Foundation::{COLORREF, HINSTANCE, HWND, LPARAM, LRESULT, WPARAM};
use windows::Win32::Graphics::Gdi::{
    BeginPaint, CreateFontW, CreatePen, CreateSolidBrush, DeleteObject, DrawTextW, EndPaint,
    FillRect, RoundRect, SelectObject, SetBkMode, SetTextColor,
    DT_CENTER, DT_SINGLELINE, DT_VCENTER, FONT_CHARSET, FONT_CLIP_PRECISION,
    FONT_OUTPUT_PRECISION, FONT_QUALITY, FW_BOLD, FW_SEMIBOLD,
    HBRUSH, HGDIOBJ, PAINTSTRUCT, PS_SOLID, TRANSPARENT,
};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::WindowsAndMessaging::{
    CreateWindowExW, DefWindowProcW, DispatchMessageW, GetMessageW, GetSystemMetrics,
    PostQuitMessage, RegisterClassExW, SetLayeredWindowAttributes, SetTimer, ShowWindow,
    SetWindowPos, TranslateMessage, KillTimer, CS_HREDRAW, CS_VREDRAW, HICON, HCURSOR,
    LWA_ALPHA, SM_CXSCREEN, SM_CYSCREEN, SWP_NOACTIVATE, SWP_SHOWWINDOW, SW_HIDE, SW_SHOWNOACTIVATE,
    WM_DESTROY, WM_PAINT, WM_TIMER, WNDCLASSEXW,
    WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_POPUP,
};

use omniscroll_bridge::OmniEvent;
use omniscroll_core::config::DeviceConfig;
use omniscroll_core::modes::DEFAULT_MODES;

const TIMER_ANIM_ID: usize = 101;
const HUD_WIDTH: i32 = 240;
const HUD_HEIGHT: i32 = 280;

pub struct HudState {
    pub active_mode: AtomicU8,
    pub level_val: AtomicI32,
    pub is_visible: AtomicBool,
    pub is_enabled: AtomicBool,
    pub position: parking_lot::RwLock<String>,
    pub timeout_ms: AtomicU64,
    pub last_interaction: parking_lot::RwLock<Instant>,
    pub gesture_text: parking_lot::RwLock<String>,
    pub hwnd_val: AtomicIsize,
}

impl HudState {
    pub fn get_hwnd(&self) -> Option<HWND> {
        let v = self.hwnd_val.load(Ordering::SeqCst);
        if v != 0 {
            Some(HWND(v as *mut std::ffi::c_void))
        } else {
            None
        }
    }

    pub fn set_hwnd(&self, hwnd: Option<HWND>) {
        let v = match hwnd {
            Some(h) => h.0 as isize,
            None => 0,
        };
        self.hwnd_val.store(v, Ordering::SeqCst);
    }
}

static HUD_STATE: OnceLock<HudState> = OnceLock::new();

pub fn get_hud_state() -> &'static HudState {
    HUD_STATE.get_or_init(|| HudState {
        active_mode: AtomicU8::new(0),
        level_val: AtomicI32::new(65),
        is_visible: AtomicBool::new(false),
        is_enabled: AtomicBool::new(true),
        position: parking_lot::RwLock::new("right".to_string()),
        timeout_ms: AtomicU64::new(2500),
        last_interaction: parking_lot::RwLock::new(Instant::now()),
        gesture_text: parking_lot::RwLock::new("✨ OmniScroll Ready".to_string()),
        hwnd_val: AtomicIsize::new(0),
    })
}

#[derive(Clone)]
pub struct HudController;

impl HudController {
    pub fn trigger_test(&self) {
        let state = get_hud_state();
        *state.last_interaction.write() = Instant::now();
        *state.gesture_text.write() = "✨ Test HUD Pulse".to_string();
        state.is_visible.store(true, Ordering::SeqCst);
        if let Some(hwnd) = state.get_hwnd() {
            unsafe {
                ShowWindow(hwnd, SW_SHOWNOACTIVATE);
                windows::Win32::Graphics::Gdi::InvalidateRect(Some(hwnd), None, false);
            }
        }
    }

    pub fn set_enabled(&self, enabled: bool) {
        let state = get_hud_state();
        state.is_enabled.store(enabled, Ordering::SeqCst);
        if !enabled {
            state.is_visible.store(false, Ordering::SeqCst);
            if let Some(hwnd) = state.get_hwnd() {
                unsafe { ShowWindow(hwnd, SW_HIDE); }
            }
        }
    }

    pub fn set_position(&self, pos: &str) {
        let state = get_hud_state();
        *state.position.write() = pos.to_string();
        if let Some(hwnd) = state.get_hwnd() {
            unsafe { reposition_hud(hwnd, pos); }
        }
    }

    pub fn set_timeout_ms(&self, ms: u64) {
        let state = get_hud_state();
        state.timeout_ms.store(ms, Ordering::SeqCst);
    }
}

pub fn spawn_hud_overlay(
    mut event_rx: broadcast::Receiver<OmniEvent>,
    config: Arc<Mutex<DeviceConfig>>,
) -> HudController {
    let state = get_hud_state();

    // Initialize from loaded config
    {
        let cfg = config.lock().unwrap();
        state.is_enabled.store(cfg.hud_enabled, Ordering::SeqCst);
        *state.position.write() = cfg.hud_position.clone();
        state.timeout_ms.store(cfg.hud_timeout_ms, Ordering::SeqCst);
    }

    // Worker thread bridging hardware OmniEvents into HUD state
    std::thread::spawn(move || {
        let state = get_hud_state();
        while let Ok(event) = event_rx.blocking_recv() {
            if !state.is_enabled.load(Ordering::SeqCst) {
                continue;
            }

            *state.last_interaction.write() = Instant::now();
            state.is_visible.store(true, Ordering::SeqCst);

            match event {
                OmniEvent::Motion { delta, mode, .. } => {
                    state.active_mode.store(mode as u8, Ordering::SeqCst);
                    let cur = state.level_val.load(Ordering::SeqCst);
                    let updated = (cur + delta).clamp(0, 100);
                    state.level_val.store(updated, Ordering::SeqCst);
                }
                OmniEvent::Action { action, mode } => {
                    state.active_mode.store(mode as u8, Ordering::SeqCst);
                    *state.gesture_text.write() = format!("{:?}", action);
                }
                OmniEvent::Gesture { action, is_neural } => {
                    let tag = if is_neural { "✨ Neural Flick" } else { "Flick" };
                    *state.gesture_text.write() = format!("{} {:?}", tag, action);
                }
                OmniEvent::Status { mode, .. } => {
                    state.active_mode.store(mode as u8, Ordering::SeqCst);
                }
                OmniEvent::Wake => {
                    *state.gesture_text.write() = "OmniScroll Connected".to_string();
                }
                OmniEvent::ModeName(ref name) => {
                    *state.gesture_text.write() = name.clone();
                }
                OmniEvent::Tap => {
                    *state.gesture_text.write() = "Single Tap".to_string();
                }
                OmniEvent::TouchSpinEnd => {
                    *state.gesture_text.write() = "Window Selected".to_string();
                }
                _ => {}
            }

            if let Some(hwnd) = state.get_hwnd() {
                unsafe {
                    ShowWindow(hwnd, SW_SHOWNOACTIVATE);
                    windows::Win32::Graphics::Gdi::InvalidateRect(Some(hwnd), None, false);
                }
            }
        }
    });

    // Dedicated OS thread running the Win32 HUD window message loop
    std::thread::spawn(move || {
        if let Err(e) = run_win32_hud_loop() {
            warn!("HUD window loop terminated: {:?}", e);
        }
    });

    HudController
}

fn run_win32_hud_loop() -> Result<(), Box<dyn std::error::Error>> {
    unsafe {
        let instance = GetModuleHandleW(None)?;
        let class_name = w!("OmniScroll_Studio_HUD");

        let wnd_class = WNDCLASSEXW {
            cbSize: std::mem::size_of::<WNDCLASSEXW>() as u32,
            style: CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc: Some(hud_wnd_proc),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hInstance: HINSTANCE(instance.0),
            hIcon: HICON::default(),
            hCursor: HCURSOR::default(),
            hbrBackground: HBRUSH::default(),
            lpszMenuName: windows::core::PCWSTR::null(),
            lpszClassName: class_name,
            hIconSm: HICON::default(),
        };

        RegisterClassExW(&wnd_class);

        let screen_w = GetSystemMetrics(SM_CXSCREEN);
        let screen_h = GetSystemMetrics(SM_CYSCREEN);

        let state = get_hud_state();
        let pos_str = state.position.read().clone();
        let (pos_x, pos_y) = calc_coords(&pos_str, screen_w, screen_h);

        let hwnd = CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_LAYERED | WS_EX_NOACTIVATE,
            class_name,
            w!("OmniScroll Overlay"),
            WS_POPUP,
            pos_x,
            pos_y,
            HUD_WIDTH,
            HUD_HEIGHT,
            None,
            None,
            Some(HINSTANCE(instance.0)),
            None,
        )?;

        // Store HWND in global state
        state.set_hwnd(Some(hwnd));

        // Alpha transparency: 230/255 ≈ 90% acrylic glass
        SetLayeredWindowAttributes(hwnd, COLORREF(0), 230, LWA_ALPHA)?;

        // Animation watchdog timer (every 16ms ≈ 60 FPS)
        SetTimer(Some(hwnd), TIMER_ANIM_ID, 16, None);

        // Initially hidden until touched/rotated
        ShowWindow(hwnd, SW_HIDE);

        let mut msg = windows::Win32::UI::WindowsAndMessaging::MSG::default();
        while GetMessageW(&mut msg, None, 0, 0).into() {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }

        KillTimer(Some(hwnd), TIMER_ANIM_ID)?;
    }

    Ok(())
}

fn calc_coords(pos: &str, screen_w: i32, screen_h: i32) -> (i32, i32) {
    match pos {
        "left" => (24, (screen_h - HUD_HEIGHT) / 2),
        "top_right" => (screen_w - HUD_WIDTH - 24, 24),
        "center" => ((screen_w - HUD_WIDTH) / 2, 24),
        _ => (screen_w - HUD_WIDTH - 24, (screen_h - HUD_HEIGHT) / 2), // "right" (default)
    }
}

unsafe fn reposition_hud(hwnd: HWND, pos: &str) {
    let screen_w = GetSystemMetrics(SM_CXSCREEN);
    let screen_h = GetSystemMetrics(SM_CYSCREEN);
    let (x, y) = calc_coords(pos, screen_w, screen_h);
    SetWindowPos(hwnd, None, x, y, HUD_WIDTH, HUD_HEIGHT, SWP_NOACTIVATE | SWP_SHOWWINDOW);
}

unsafe extern "system" fn hud_wnd_proc(
    hwnd: HWND,
    msg: u32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    let state = get_hud_state();

    match msg {
        WM_TIMER => {
            if wparam.0 == TIMER_ANIM_ID {
                let enabled = state.is_enabled.load(Ordering::SeqCst);
                if !enabled {
                    if state.is_visible.load(Ordering::SeqCst) {
                        state.is_visible.store(false, Ordering::SeqCst);
                        ShowWindow(hwnd, SW_HIDE);
                    }
                    return LRESULT(0);
                }

                let elapsed = state.last_interaction.read().elapsed();
                let timeout = Duration::from_millis(state.timeout_ms.load(Ordering::SeqCst));
                let should_be_visible = elapsed < timeout;

                if should_be_visible != state.is_visible.load(Ordering::SeqCst) {
                    state.is_visible.store(should_be_visible, Ordering::SeqCst);
                    if should_be_visible {
                        ShowWindow(hwnd, SW_SHOWNOACTIVATE);
                    } else {
                        ShowWindow(hwnd, SW_HIDE);
                    }
                }

                if should_be_visible {
                    windows::Win32::Graphics::Gdi::InvalidateRect(Some(hwnd), None, false);
                }
            }
            LRESULT(0)
        }
        WM_PAINT => {
            let mut ps = PAINTSTRUCT::default();
            let hdc = BeginPaint(hwnd, &mut ps);

            paint_glassmorphic_hud(hdc, state);

            EndPaint(hwnd, &ps);
            LRESULT(0)
        }
        WM_DESTROY => {
            PostQuitMessage(0);
            LRESULT(0)
        }
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}

unsafe fn create_hud_font(size: i32, weight: i32) -> windows::Win32::Graphics::Gdi::HFONT {
    CreateFontW(
        size,
        0,
        0,
        0,
        weight,
        0,
        0,
        0,
        FONT_CHARSET(0),
        FONT_OUTPUT_PRECISION(0),
        FONT_CLIP_PRECISION(0),
        FONT_QUALITY(0),
        0,
        w!("Segoe UI"),
    )
}

unsafe fn paint_glassmorphic_hud(hdc: windows::Win32::Graphics::Gdi::HDC, state: &HudState) {
    let mode_idx = state.active_mode.load(Ordering::SeqCst) as usize;
    let mode_cfg = &DEFAULT_MODES[mode_idx % DEFAULT_MODES.len()];
    let level = state.level_val.load(Ordering::SeqCst);

    // 1. Draw Translucent Dark Acrylic Surface (#121016)
    let bg_brush = CreateSolidBrush(COLORREF(0x161012));
    let border_pen = CreatePen(PS_SOLID, 1, COLORREF(0x353038));
    let old_brush = SelectObject(hdc, HGDIOBJ(bg_brush.0));
    let old_pen = SelectObject(hdc, HGDIOBJ(border_pen.0));

    RoundRect(hdc, 0, 0, HUD_WIDTH, HUD_HEIGHT, 24, 24);

    SelectObject(hdc, old_brush);
    SelectObject(hdc, old_pen);
    DeleteObject(HGDIOBJ(bg_brush.0));
    DeleteObject(HGDIOBJ(border_pen.0));

    SetBkMode(hdc, TRANSPARENT);

    // 2. Glowing LED Mode Pip
    let led_color = COLORREF(
        ((mode_cfg.color_rgb[2] as u32) << 16)
            | ((mode_cfg.color_rgb[1] as u32) << 8)
            | (mode_cfg.color_rgb[0] as u32),
    );
    let led_brush = CreateSolidBrush(led_color);
    let led_pen = CreatePen(PS_SOLID, 1, led_color);
    let old_brush = SelectObject(hdc, HGDIOBJ(led_brush.0));
    let old_pen = SelectObject(hdc, HGDIOBJ(led_pen.0));

    RoundRect(hdc, 20, 26, 32, 38, 12, 12);

    SelectObject(hdc, old_brush);
    SelectObject(hdc, old_pen);
    DeleteObject(HGDIOBJ(led_brush.0));
    DeleteObject(HGDIOBJ(led_pen.0));

    // 3. Mode Title
    let font_title = create_hud_font(-20, FW_BOLD.0 as i32);
    let old_font = SelectObject(hdc, HGDIOBJ(font_title.0));
    SetTextColor(hdc, COLORREF(0xFFFFFF));

    let mut rect_title = windows::Win32::Foundation::RECT {
        left: 42,
        top: 18,
        right: HUD_WIDTH - 20,
        bottom: 46,
    };
    let title_utf16: Vec<u16> = mode_cfg.name.encode_utf16().chain(std::iter::once(0)).collect();
    DrawTextW(hdc, &mut title_utf16.clone(), &mut rect_title, DT_SINGLELINE | DT_VCENTER);

    SelectObject(hdc, old_font);
    DeleteObject(HGDIOBJ(font_title.0));

    // 4. Mode Subtitle
    let font_sub = create_hud_font(-12, FW_SEMIBOLD.0 as i32);
    let old_font = SelectObject(hdc, HGDIOBJ(font_sub.0));
    SetTextColor(hdc, COLORREF(0x9A908A));

    let mut rect_sub = windows::Win32::Foundation::RECT {
        left: 42,
        top: 44,
        right: HUD_WIDTH - 20,
        bottom: 64,
    };
    let sub_str = match mode_cfg.name {
        "SCROLL" => "Vertical Page Scroll",
        "VOLUME" => "System Volume",
        "TIMELINE" => "Timeline Scrubbing",
        "ZOOM" => "Universal Zoom",
        "H_SCROLL" => "Horizontal Pan",
        "BRIGHTNESS" => "Hardware Brightness",
        "TABBING" => "Browser Tab Switcher",
        "UNDO_REDO" => "History Scrubbing",
        _ => "Rotary Control",
    };
    let sub_utf16: Vec<u16> = sub_str.encode_utf16().chain(std::iter::once(0)).collect();
    DrawTextW(hdc, &mut sub_utf16.clone(), &mut rect_sub, DT_SINGLELINE | DT_VCENTER);

    SelectObject(hdc, old_font);
    DeleteObject(HGDIOBJ(font_sub.0));

    // 5. Level Progress Track & Fill
    let track_rect = windows::Win32::Foundation::RECT {
        left: 20,
        top: 86,
        right: HUD_WIDTH - 20,
        bottom: 96,
    };
    let track_brush = CreateSolidBrush(COLORREF(0x28242A));
    FillRect(hdc, &track_rect, track_brush);
    DeleteObject(HGDIOBJ(track_brush.0));

    let fill_w = ((HUD_WIDTH - 40) as f32 * (level as f32 / 100.0)).clamp(4.0, (HUD_WIDTH - 40) as f32) as i32;
    let fill_rect = windows::Win32::Foundation::RECT {
        left: 20,
        top: 86,
        right: 20 + fill_w,
        bottom: 96,
    };
    let fill_brush = CreateSolidBrush(led_color);
    FillRect(hdc, &fill_rect, fill_brush);
    DeleteObject(HGDIOBJ(fill_brush.0));

    // 6. Gesture Toast Badge
    let toast_brush = CreateSolidBrush(COLORREF(0x201C24));
    let toast_pen = CreatePen(PS_SOLID, 1, COLORREF(0x38343E));
    let old_brush = SelectObject(hdc, HGDIOBJ(toast_brush.0));
    let old_pen = SelectObject(hdc, HGDIOBJ(toast_pen.0));

    RoundRect(hdc, 20, 116, HUD_WIDTH - 20, 168, 16, 16);

    SelectObject(hdc, old_brush);
    SelectObject(hdc, old_pen);
    DeleteObject(HGDIOBJ(toast_brush.0));
    DeleteObject(HGDIOBJ(toast_pen.0));

    let font_toast = create_hud_font(-13, FW_SEMIBOLD.0 as i32);
    let old_font = SelectObject(hdc, HGDIOBJ(font_toast.0));
    SetTextColor(hdc, COLORREF(0xDCD8D0));

    let mut rect_toast = windows::Win32::Foundation::RECT {
        left: 24,
        top: 116,
        right: HUD_WIDTH - 24,
        bottom: 168,
    };
    let gesture_msg = state.gesture_text.read().clone();
    let toast_utf16: Vec<u16> = gesture_msg.encode_utf16().chain(std::iter::once(0)).collect();
    DrawTextW(hdc, &mut toast_utf16.clone(), &mut rect_toast, DT_CENTER | DT_VCENTER | DT_SINGLELINE);

    SelectObject(hdc, old_font);
    DeleteObject(HGDIOBJ(font_toast.0));

    // 7. Footer Branding
    let font_footer = create_hud_font(-10, FW_SEMIBOLD.0 as i32);
    let old_font = SelectObject(hdc, HGDIOBJ(font_footer.0));
    SetTextColor(hdc, COLORREF(0x605A58));

    let mut rect_footer = windows::Win32::Foundation::RECT {
        left: 20,
        top: 190,
        right: HUD_WIDTH - 20,
        bottom: 210,
    };
    let footer_utf16: Vec<u16> = "OMNISCROLL • FROM ROUFSWEB".encode_utf16().chain(std::iter::once(0)).collect();
    DrawTextW(hdc, &mut footer_utf16.clone(), &mut rect_footer, DT_CENTER | DT_VCENTER | DT_SINGLELINE);

    SelectObject(hdc, old_font);
    DeleteObject(HGDIOBJ(font_footer.0));
}
