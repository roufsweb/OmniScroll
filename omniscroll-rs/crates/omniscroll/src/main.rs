//! Windows Dynamic Glassmorphic Wheel HUD (On-Screen Dial Overlay) for OmniScroll.

#![allow(unused_must_use)]

use std::sync::atomic::{AtomicBool, AtomicI32, AtomicU8, Ordering};
use std::sync::OnceLock;
use std::time::{Duration, Instant};

use tokio::sync::broadcast;
use tracing::{info, Level};
use tracing_subscriber::FmtSubscriber;

use windows::core::w;
use windows::Win32::Foundation::{COLORREF, HINSTANCE, HWND, LPARAM, LRESULT, RECT, WPARAM};
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
    TranslateMessage, KillTimer, CS_HREDRAW, CS_VREDRAW, HICON, HCURSOR,
    LWA_ALPHA, SM_CXSCREEN, SM_CYSCREEN, SW_HIDE, SW_SHOWNOACTIVATE,
    WM_DESTROY, WM_PAINT, WM_TIMER, WNDCLASSEXW,
    WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_POPUP,
};

use omniscroll_bridge::{OmniEvent, SerialBridge, UdpBridge};
use omniscroll_core::modes::DEFAULT_MODES;

// Global HUD State shared between async UDP receiver and Win32 UI loop
struct HudState {
    pub active_mode: AtomicU8,
    pub level_val: AtomicI32,
    pub is_visible: AtomicBool,
    pub last_interaction: parking_lot::RwLock<Instant>,
    pub gesture_text: parking_lot::RwLock<String>,
}

static HUD_STATE: OnceLock<HudState> = OnceLock::new();

fn get_hud_state() -> &'static HudState {
    HUD_STATE.get_or_init(|| HudState {
        active_mode: AtomicU8::new(0),
        level_val: AtomicI32::new(65),
        is_visible: AtomicBool::new(true),
        last_interaction: parking_lot::RwLock::new(Instant::now()),
        gesture_text: parking_lot::RwLock::new("✨ OmniScroll Ready".to_string()),
    })
}

const TIMER_ANIM_ID: usize = 101;
const HUD_WIDTH: i32 = 240;
const HUD_HEIGHT: i32 = 280;
const IDLE_TIMEOUT: Duration = Duration::from_millis(2500);

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let subscriber = FmtSubscriber::builder()
        .with_max_level(Level::INFO)
        .finish();
    tracing::subscriber::set_global_default(subscriber).ok();

    info!("Starting OmniScroll Dynamic Glassmorphic HUD...");

    let (event_tx, mut event_rx) = broadcast::channel::<OmniEvent>(128);

    // Spawn the async UDP receiver on port 4211
    let udp_tx = event_tx.clone();
    tokio::spawn(async move {
        match UdpBridge::bind(udp_tx).await {
            Ok(bridge) => {
                info!("UDP Bridge bound. Awaiting hardware events...");
                bridge.run_stream_loop().await;
            }
            Err(e) => {
                tracing::error!("Could not bind UDP Bridge: {}. Running standalone.", e);
            }
        }
    });

    // Spawn the USB CDC Serial Listener (Auto-detects COM26 / VID 0x303A & PID 0x4F5B)
    let serial_tx = event_tx.clone();
    let is_usb_connected = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
    let _serial_sender = SerialBridge::spawn_listener(serial_tx, is_usb_connected);

    // Spawn a worker thread to bridge OmniEvents into Win32 state
    std::thread::spawn(move || {
        let state = get_hud_state();
        while let Ok(event) = event_rx.blocking_recv() {
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
                    *state.gesture_text.write() = "OmniScroll Awake".to_string();
                }
                OmniEvent::Config(_) => {}
                OmniEvent::ModeName(ref name) => {
                    *state.gesture_text.write() = name.clone();
                }
                OmniEvent::Tap => {
                    *state.gesture_text.write() = "Tap".to_string();
                }
                OmniEvent::TouchSpinEnd => {
                    *state.gesture_text.write() = "Window Selected".to_string();
                }
                _ => {}
            }
        }
    });

    // Run the native Windows GUI loop on the main thread
    run_win32_hud_window()?;

    Ok(())
}

fn run_win32_hud_window() -> Result<(), Box<dyn std::error::Error>> {
    unsafe {
        let instance = GetModuleHandleW(None)?;
        let class_name = w!("OmniScroll_Glassmorphic_HUD");

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

        // Position on the right side of the screen like a sidebar pill
        let pos_x = screen_w - HUD_WIDTH - 24;
        let pos_y = (screen_h - HUD_HEIGHT) / 2;

        let hwnd = CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_LAYERED | WS_EX_NOACTIVATE,
            class_name,
            w!("OmniScroll HUD"),
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

        // Set initial alpha transparency (225/255 ≈ 88% glass opacity)
        SetLayeredWindowAttributes(hwnd, COLORREF(0), 225, LWA_ALPHA)?;

        // Animation and idle watchdog timer (every 16ms ≈ 60 FPS)
        SetTimer(Some(hwnd), TIMER_ANIM_ID, 16, None);

        // Show welcome preview on launch, then fades after idle timeout
        ShowWindow(hwnd, SW_SHOWNOACTIVATE);

        let mut msg = windows::Win32::UI::WindowsAndMessaging::MSG::default();
        while GetMessageW(&mut msg, None, 0, 0).into() {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }

        KillTimer(Some(hwnd), TIMER_ANIM_ID)?;
    }

    Ok(())
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
                let elapsed = state.last_interaction.read().elapsed();
                let should_be_visible = elapsed < IDLE_TIMEOUT;

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

/// Helper to create clean Segoe UI fonts
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

/// Renders the Nordic Walnut / Obsidian dark glassmorphic card
unsafe fn paint_glassmorphic_hud(hdc: windows::Win32::Graphics::Gdi::HDC, state: &HudState) {
    let mode_idx = state.active_mode.load(Ordering::SeqCst) as usize;
    let mode_cfg = &DEFAULT_MODES[mode_idx % DEFAULT_MODES.len()];
    let level = state.level_val.load(Ordering::SeqCst);

    // 1. Draw Glassmorphic Dark Container
    let bg_brush = CreateSolidBrush(COLORREF(0x121016)); // Dark Walnut Obsidian (#161012 BGR)
    let border_pen = CreatePen(PS_SOLID, 1, COLORREF(0x353038)); // Subtle border
    let old_brush = SelectObject(hdc, HGDIOBJ(bg_brush.0));
    let old_pen = SelectObject(hdc, HGDIOBJ(border_pen.0));

    RoundRect(hdc, 0, 0, HUD_WIDTH, HUD_HEIGHT, 24, 24);

    SelectObject(hdc, old_brush);
    SelectObject(hdc, old_pen);
    DeleteObject(HGDIOBJ(bg_brush.0));
    DeleteObject(HGDIOBJ(border_pen.0));

    SetBkMode(hdc, TRANSPARENT);

    // 2. Draw Glowing LED Mode Pip
    let led_color = COLORREF(
        ((mode_cfg.color_rgb[2] as u32) << 16)
            | ((mode_cfg.color_rgb[1] as u32) << 8)
            | (mode_cfg.color_rgb[0] as u32),
    );
    let led_brush = CreateSolidBrush(led_color);
    let led_pen = CreatePen(PS_SOLID, 1, led_color);
    let old_brush = SelectObject(hdc, HGDIOBJ(led_brush.0));
    let old_pen = SelectObject(hdc, HGDIOBJ(led_pen.0));

    RoundRect(hdc, 20, 24, 32, 36, 12, 12);

    SelectObject(hdc, old_brush);
    SelectObject(hdc, old_pen);
    DeleteObject(HGDIOBJ(led_brush.0));
    DeleteObject(HGDIOBJ(led_pen.0));

    // 3. Draw Header Title: "OmniScroll"
    let brand_font = create_hud_font(13, FW_SEMIBOLD.0 as i32);
    let old_font = SelectObject(hdc, HGDIOBJ(brand_font.0));
    SetTextColor(hdc, COLORREF(0x9E9080)); // Muted warm grey (#80909E BGR)

    let mut brand_rect = RECT {
        left: 40,
        top: 20,
        right: HUD_WIDTH - 20,
        bottom: 38,
    };
    let mut brand_text: Vec<u16> = "OmniScroll".encode_utf16().collect();
    DrawTextW(hdc, &mut brand_text, &mut brand_rect, DT_SINGLELINE | DT_VCENTER);

    // 4. Draw Mode Name (Bold)
    let mode_font = create_hud_font(22, FW_BOLD.0 as i32);
    SelectObject(hdc, HGDIOBJ(mode_font.0));
    SetTextColor(hdc, COLORREF(0xFFFFFF));

    let mut mode_rect = RECT {
        left: 20,
        top: 50,
        right: HUD_WIDTH - 20,
        bottom: 82,
    };
    let mut mode_utf16: Vec<u16> = mode_cfg.name.encode_utf16().collect();
    DrawTextW(hdc, &mut mode_utf16, &mut mode_rect, DT_SINGLELINE | DT_VCENTER);

    // 5. Draw Dynamic Level Track & Fill Bar
    let track_rect = RECT {
        left: 20,
        top: 100,
        right: HUD_WIDTH - 20,
        bottom: 114,
    };
    let track_brush = CreateSolidBrush(COLORREF(0x28242A));
    FillRect(hdc, &track_rect, track_brush);
    DeleteObject(HGDIOBJ(track_brush.0));

    let fill_w = ((HUD_WIDTH - 40) * level) / 100;
    let fill_rect = RECT {
        left: 20,
        top: 100,
        right: 20 + fill_w,
        bottom: 114,
    };
    let fill_brush = CreateSolidBrush(COLORREF(0xFFA000)); // Apple Amber MagSafe
    FillRect(hdc, &fill_rect, fill_brush);
    DeleteObject(HGDIOBJ(fill_brush.0));

    // 6. Draw Value Label (e.g. "50%")
    let val_font = create_hud_font(14, FW_BOLD.0 as i32);
    SelectObject(hdc, HGDIOBJ(val_font.0));
    SetTextColor(hdc, COLORREF(0xDADADA));

    let mut val_rect = RECT {
        left: 20,
        top: 122,
        right: HUD_WIDTH - 20,
        bottom: 144,
    };
    let mut val_utf16: Vec<u16> = format!("{}%", level).encode_utf16().collect();
    DrawTextW(hdc, &mut val_utf16, &mut val_rect, DT_SINGLELINE | DT_VCENTER);

    // 7. Draw Gesture / Status Toast
    let gesture = state.gesture_text.read().clone();
    if !gesture.is_empty() {
        let toast_brush = CreateSolidBrush(COLORREF(0x201C1A));
        let toast_pen = CreatePen(PS_SOLID, 1, COLORREF(0x00F0DC)); // Cyan neural border
        let old_b = SelectObject(hdc, HGDIOBJ(toast_brush.0));
        let old_p = SelectObject(hdc, HGDIOBJ(toast_pen.0));

        RoundRect(hdc, 20, 180, HUD_WIDTH - 20, 230, 16, 16);

        SelectObject(hdc, old_b);
        SelectObject(hdc, old_p);
        DeleteObject(HGDIOBJ(toast_brush.0));
        DeleteObject(HGDIOBJ(toast_pen.0));

        let toast_font = create_hud_font(12, FW_SEMIBOLD.0 as i32);
        SelectObject(hdc, HGDIOBJ(toast_font.0));
        SetTextColor(hdc, COLORREF(0x00F0DC)); // Radiant Cyan text

        let mut toast_rect = RECT {
            left: 24,
            top: 184,
            right: HUD_WIDTH - 24,
            bottom: 226,
        };
        let mut toast_utf16: Vec<u16> = gesture.encode_utf16().collect();
        DrawTextW(
            hdc,
            &mut toast_utf16,
            &mut toast_rect,
            DT_CENTER | DT_SINGLELINE | DT_VCENTER,
        );

        SelectObject(hdc, old_font);
        DeleteObject(HGDIOBJ(toast_font.0));
    } else {
        SelectObject(hdc, old_font);
    }

    DeleteObject(HGDIOBJ(brand_font.0));
    DeleteObject(HGDIOBJ(mode_font.0));
    DeleteObject(HGDIOBJ(val_font.0));
}
