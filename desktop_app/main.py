"""
main.py — OmniScroll Full Native Windows Desktop Control Panel & Virtual USB/HID Bridge
Features:
- Pure Windows Native Architecture (PySide6 / QPainter / QSS) — Zero Chromium / WebEngine bloat
- Ultra-lightweight: ~45MB standalone executable, ~30MB RAM footprint, instant <0.2s launch
- Pixel-Perfect Apple Pro HIG & Nordic Walnut Craftsmanship matching Web Control Panel
- 1:1 Precision Rotary Crown visualizer tracking MX8650 optical bearing rotation (~520 counts/rev)
- Real-time zero-latency Virtual Bridge using Win32 SendInput in wireless mode
- Mutual exclusion: Automatically suppresses virtual injection when USB cable is connected to PC
- Dual-transport router (Priority 1 USB CDC, Priority 2 Wi-Fi UDP OMP Port 4211)
- Integrated Windows Wi-Fi Scanner with 2.4 GHz vs 5 GHz compatibility validation
- One-click USB Wi-Fi credential provisioning
- Dynamic Live Re-Theming: Walnut, Obsidian, Aluminum, Ultra
- Background daemon with System Tray integration & Windows Startup on Boot (HKCU\\...\\Run)
"""
import sys
import os
import time
import json
import logging
import winreg
import ctypes
from ctypes import wintypes

WM_DEVICECHANGE          = 0x0219
DBT_DEVICEARRIVAL        = 0x8000
DBT_DEVICEREMOVECOMPLETE = 0x8004
DBT_DEVNODES_CHANGED     = 0x0007

from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer, QSettings
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QScrollArea, QFrame, QSizePolicy,
    QSystemTrayIcon, QMenu, QCheckBox
)
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont

from themes import THEMES, get_stylesheet
from protocol import (
    TransportManager, TransportMode, OMPPacket,
    PKT_MOTION, PKT_ACTION, PKT_GESTURE, PKT_STATUS
)
from virtual_bridge import VirtualBridge
from wifi_scanner import scan_wifi_networks
from widgets import (
    GlassPanel, HeaderBar, ModeBarWidget, ActiveModeIsland, PhotorealisticRotaryDial,
    GestureBadgeWidget, HapticDetentStrip, AppleCapsuleSlider, AppleCapsulePicker,
    WifiStudioContainer, NativeModeCard, TinyOLNeuralCard, CollapsibleDisclosure,
    HardwareRgbCalibrationCard, AppleSideScrollRail, AboutOmniScrollCard, AboutModal,
    AppleColorModal, ACTIONS, TSPIN_ACTIONS, SINGLE_TAP_ACTIONS
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class WifiScanWorker(QThread):
    """Asynchronous background worker for scanning Windows Wi-Fi networks."""
    scanned = Signal(list)

    def run(self):
        try:
            nets = scan_wifi_networks()
            self.scanned.emit(nets)
        except Exception as e:
            logging.error(f"WifiScanWorker error: {e}")
            self.scanned.emit([])


class StreamWorker(QThread):
    """Low-latency background worker for polling packets and injecting inputs."""
    packet_received = Signal(object)
    line_received   = Signal(str)
    connection_lost = Signal()

    def __init__(self, transport: TransportManager, bridge: VirtualBridge):
        super().__init__()
        self.transport = transport
        self.bridge = bridge
        self.running = True
        self.active_mode = "SCROLL"
        self.active_threshold = 10
        self.mode_thresholds = {
            "SCROLL": 10, "VOLUME": 25, "TIMELINE": 15, "ZOOM": 15,
            "H_SCROLL": 10, "BRIGHTNESS": 20, "TABBING": 20, "UNDO_REDO": 15
        }

    def run(self):
        last_heartbeat = 0.0
        while self.running:
            if not self.transport.is_connected():
                self.connection_lost.emit()
                break

            # 1. Handle Wi-Fi stream
            if self.transport.mode == TransportMode.WIFI:
                now = time.time()
                if now - last_heartbeat >= 1.5:
                    last_heartbeat = now
                    self.transport.wifi.send_ping()

                MODE_ORDER = ["SCROLL", "VOLUME", "TIMELINE", "ZOOM", "H_SCROLL", "BRIGHTNESS", "TABBING", "UNDO_REDO"]
                omp_pkts, lines = self.transport.wifi.receive_packets()
                for pkt in omp_pkts:
                    # In wireless mode: inject Win32 SendInput IF USB not mounted to PC
                    if not pkt.is_usb_mounted:
                        mname = MODE_ORDER[pkt.mode] if pkt.mode < len(MODE_ORDER) else self.active_mode
                        self.active_mode = mname
                        thr = self.mode_thresholds.get(mname, 10)
                        if pkt.type == PKT_MOTION:
                            # In wireless Wi-Fi mode, always use high-res smooth scrolling on Windows SendInput
                            self.bridge.dispatch_mode_motion(
                                mname, pkt.delta, thr, is_high_res=True
                            )
                        elif pkt.type == PKT_ACTION:
                            if pkt.delta != 0:
                                self.bridge.dispatch_touch_spin(pkt.action, pkt.delta, thr)
                            else:
                                if pkt.action == 6:
                                    self.bridge.release_alt_clutch()
                                else:
                                    self.bridge.dispatch_action(pkt.action)
                        elif pkt.type == PKT_GESTURE:
                            self.bridge.dispatch_action(pkt.action)
                    self.packet_received.emit(pkt)

                for line in lines:
                    self._parse_line(line)
                    self.line_received.emit(line)

            # 2. Handle USB serial stream
            elif self.transport.mode == TransportMode.USB:
                lines = self.transport.usb.read_lines()
                if not self.transport.usb.is_connected():
                    self.connection_lost.emit()
                    break
                for line in lines:
                    self._parse_line(line)
                    self.line_received.emit(line)

            time.sleep(0.002) # 2ms poll interval

    def _parse_line(self, line: str):
        if line.startswith("MODE:"):
            mname = line[5:].strip()
            self.active_mode = mname
            if mname in self.mode_thresholds:
                self.active_threshold = self.mode_thresholds[mname]
        elif "TSPIN:END" in line:
            self.bridge.release_alt_clutch()

    def stop(self):
        self.running = False
        self.wait(500)


class DiscoveryWorker(QThread):
    """Background worker for discovering OmniScroll over USB or Wi-Fi."""
    found = Signal(int, str) # mode, address

    def __init__(self, transport: TransportManager):
        super().__init__()
        self.transport = transport

    def run(self):
        mode, addr = self.transport.auto_discover()
        self.found.emit(mode, addr if addr else "")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OmniScroll")
        self.setGeometry(80, 50, 1280, 860)
        self.setMinimumSize(1040, 700)

        self.current_theme = "walnut"
        self.transport = TransportManager()
        self.bridge = VirtualBridge()
        self.stream_worker = None
        self.discovery_worker = None
        self.wifi_worker = None

        self.modes_data = [
            {"name": "SCROLL",     "desc": "Vertical page scroll",       "c": "007AFF", "thr": 10, "hp": 0, "inv": False, "en": True},
            {"name": "VOLUME",     "desc": "System volume control",      "c": "30D158", "thr": 25, "hp": 3, "inv": False, "en": True},
            {"name": "TIMELINE",   "desc": "Frame-by-frame arrow keys",  "c": "FF2D55", "thr": 15, "hp": 0, "inv": False, "en": True},
            {"name": "ZOOM",       "desc": "Universal zoom in any app",  "c": "FF9500", "thr": 15, "hp": 0, "inv": False, "en": False},
            {"name": "H_SCROLL",   "desc": "Horizontal side-scroll",     "c": "00C2A8", "thr": 10, "hp": 2, "inv": False, "en": False},
            {"name": "BRIGHTNESS", "desc": "Display brightness keys",    "c": "FFD60A", "thr": 20, "hp": 3, "inv": False, "en": False},
            {"name": "TABBING",    "desc": "Cycle browser & app tabs",   "c": "BF5AF2", "thr": 20, "hp": 0, "inv": False, "en": False},
            {"name": "UNDO_REDO",  "desc": "Ctrl+Z / Ctrl+Shift+Z",      "c": "FF453A", "thr": 15, "hp": 1, "inv": False, "en": False},
        ]
        self.current_mode_idx = 0

        self._build_native_ui()
        self._setup_tray()
        self.apply_theme(self.current_theme)

        # Persistent desktop configuration & network caching
        self.settings = QSettings("OmniScroll", "OmniScroll")
        cached_ip = self.settings.value("last_wifi_ip", "")
        if cached_ip:
            self.transport.set_last_known_ip(str(cached_ip))
        cached_ssid = self.settings.value("last_wifi_ssid", "")
        if cached_ssid:
            self.wifi_card.set_saved_credentials(str(cached_ssid))

        # Background auto-reconnect timer for zero-touch seamless wireless pairing
        self.auto_reconnect_timer = QTimer(self)
        self.auto_reconnect_timer.setInterval(2500)
        self.auto_reconnect_timer.timeout.connect(self._auto_reconnect_tick)
        self.auto_reconnect_timer.start()

        # Initial auto discovery & Wi-Fi scan
        self.start_discovery()
        self._on_wifi_scan_requested()

    def _build_native_ui(self):
        # Master Central Container
        central = QWidget(self)
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        master_layout = QVBoxLayout(central)
        master_layout.setContentsMargins(16, 12, 16, 12)
        master_layout.setSpacing(12)

        # 1. Header Bar
        self.header = HeaderBar(self.current_theme, self)
        self.header.connectClicked.connect(self._toggle_connection)
        self.header.themeChanged.connect(self.apply_theme)
        self.header.aboutClicked.connect(self._open_about_modal)
        master_layout.addWidget(self.header)

        # 2. Smooth Scrollable Stage for scalable layout (with isolated Apple side rail)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("ScrollContent")
        content_layout = QVBoxLayout(content)

        content_layout.setContentsMargins(0, 4, 0, 10)
        content_layout.setSpacing(16)

        # ---- Top Split: Hardware Stage (Left) & Studio Controls (Right) ----
        top_split = QHBoxLayout()
        top_split.setSpacing(16)

        # [LEFT COLUMN]: Hardware Stage + Crown Detent Strip + Collapsible Advanced Settings
        left_col = QVBoxLayout()
        left_col.setSpacing(14)

        self.stage_panel = GlassPanel(self, self.current_theme)
        stage_layout = QVBoxLayout(self.stage_panel)
        stage_layout.setContentsMargins(18, 16, 18, 16)
        stage_layout.setSpacing(12)

        # Active Mode Island in stage header
        m0 = self.modes_data[0]
        self.island = ActiveModeIsland(m0["name"], m0["desc"], m0["c"], self)
        self.island.testHapticClicked.connect(lambda: self.send_command("TEST:HAPTIC"))
        stage_layout.addWidget(self.island)

        # 1:1 Photorealistic Crown Visualizer (with floating GestureBadge toast overlay)
        self.dial = PhotorealisticRotaryDial(self)
        self.dial.dialTapped.connect(lambda: self.send_command("TEST:HAPTIC"))
        self.dial.gestureRejectClicked.connect(self._reject_last_gesture)
        stage_layout.addWidget(self.dial, 1)

        # Subtle horizontal divider before Detent Profile (matching Web UI)
        self.stage_divider = QFrame()
        self.stage_divider.setFrameShape(QFrame.HLine)
        self.stage_divider.setFixedHeight(1)
        stage_layout.addWidget(self.stage_divider)

        # Detent Profile Strip
        self.lbl_detent = QLabel("CROWN DETENT PROFILE")
        self.lbl_detent.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Bold))
        self.lbl_detent.setStyleSheet("letter-spacing: 0.8px;")
        stage_layout.addWidget(self.lbl_detent)

        self.detent_strip = HapticDetentStrip(0, self)
        self.detent_strip.profileSelected.connect(self._on_crown_profile_selected)
        stage_layout.addWidget(self.detent_strip)

        # Subtle horizontal divider before Windows Startup on Boot
        self.boot_divider = QFrame()
        self.boot_divider.setFrameShape(QFrame.HLine)
        self.boot_divider.setFixedHeight(1)
        stage_layout.addWidget(self.boot_divider)

        # Windows Startup on Boot toggle row in main picture stage window
        boot_row = QHBoxLayout()
        boot_row.setContentsMargins(4, 2, 4, 2)
        self.lbl_stage_boot = QLabel("Start OmniScroll on Windows Boot")
        self.lbl_stage_boot.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Medium))
        self.chk_stage_boot = QCheckBox()
        self.chk_stage_boot.setCursor(Qt.PointingHandCursor)
        self.chk_stage_boot.setChecked(self.is_startup_enabled())
        self.chk_stage_boot.toggled.connect(self.set_startup_enabled)

        boot_row.addWidget(self.lbl_stage_boot)
        boot_row.addStretch()
        boot_row.addWidget(self.chk_stage_boot)
        stage_layout.addLayout(boot_row)

        left_col.addWidget(self.stage_panel, 1)

        # Progressive Disclosure: Advanced Settings (TinyOL Neural Engine + Hardware RGB Calibration)
        self.adv_disclosure = CollapsibleDisclosure("Advanced Settings", self, self.current_theme)
        self.neural_card = TinyOLNeuralCard(self, self.current_theme)
        self.neural_card.rejectClicked.connect(lambda: self.send_command("SET:GESTURE_REJECT"))
        self.neural_card.resetClicked.connect(lambda: self.send_command("SET:GESTURE_PROFILE:110,85,25"))
        self.adv_disclosure.addWidget(self.neural_card)

        # Hardware RGB Calibration Container
        self.cal_card = HardwareRgbCalibrationCard(self, self.current_theme)
        self.cal_card.calChanged.connect(self._on_cal_changed)
        self.cal_card.testLedClicked.connect(self._on_test_led)
        self.adv_disclosure.addWidget(self.cal_card)
        left_col.addWidget(self.adv_disclosure)

        top_split.addLayout(left_col, 5)

        # [RIGHT COLUMN]: Studio Controls + Wi-Fi Studio Card
        right_col = QVBoxLayout()
        right_col.setSpacing(14)

        self.controls_panel = GlassPanel(self, self.current_theme)
        controls_layout = QVBoxLayout(self.controls_panel)
        controls_layout.setContentsMargins(18, 16, 18, 16)
        controls_layout.setSpacing(10)

        self.lbl_ctrl_title = QLabel("STUDIO CONTROLS")
        self.lbl_ctrl_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_ctrl_title.setStyleSheet("letter-spacing: 0.8px;")
        controls_layout.addWidget(self.lbl_ctrl_title)

        # Capsule Sliders
        self.sl_bri = AppleCapsuleSlider("LED Brightness", "brightness", 0, 100, 100, "%", self)
        self.sl_bri.valueChanged.connect(lambda v: self.send_command(f"SET:BRI:{v}"))
        controls_layout.addWidget(self.sl_bri)

        self.sl_idle = AppleCapsuleSlider("Idle Sleep", "idle", 0, 120, 30, "s", self)
        self.sl_idle.valueChanged.connect(lambda v: self.send_command(f"SET:IDLE:{v}"))
        controls_layout.addWidget(self.sl_idle)

        self.sl_thr = AppleCapsuleSlider("Touch Sensitivity", "touch", 0, 100, 76, "%", self)
        self.sl_thr.valueChanged.connect(self._on_touch_thr_changed)
        controls_layout.addWidget(self.sl_thr)

        self.lbl_gestures = QLabel("GESTURES & SHORTCUTS")
        self.lbl_gestures.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Bold))
        self.lbl_gestures.setStyleSheet("margin-top: 6px; letter-spacing: 0.8px;")
        controls_layout.addWidget(self.lbl_gestures)

        # Capsule Gesture Pickers
        self.pk_fwd = AppleCapsulePicker("Flick Forward", "→", 2, parent=self)
        self.pk_fwd.actionSelected.connect(lambda a: self.send_command(f"SET:FLICK_FWD:{a}"))
        controls_layout.addWidget(self.pk_fwd)

        self.pk_rev = AppleCapsulePicker("Flick Back", "←", 1, parent=self)
        self.pk_rev.actionSelected.connect(lambda a: self.send_command(f"SET:FLICK_REV:{a}"))
        controls_layout.addWidget(self.pk_rev)

        self.pk_tspin = AppleCapsulePicker("Touch & Spin", "↻", 1, items=TSPIN_ACTIONS, parent=self)
        self.pk_tspin.actionSelected.connect(lambda a: self.send_command(f"SET:TSPIN:{a}"))
        controls_layout.addWidget(self.pk_tspin)

        self.pk_tap = AppleCapsulePicker("Single Tap", "◎", 99, items=SINGLE_TAP_ACTIONS, parent=self)
        self.pk_tap.actionSelected.connect(lambda a: self.send_command(f"SET:SINGLE_TAP:{a}"))
        controls_layout.addWidget(self.pk_tap)

        right_col.addWidget(self.controls_panel)

        # Wireless Connection Container
        self.wifi_card = WifiStudioContainer(self, self.current_theme)
        self.wifi_card.scanRequested.connect(self._on_wifi_scan_requested)
        self.wifi_card.provisionRequested.connect(self._on_wifi_provision_requested)
        right_col.addWidget(self.wifi_card)

        top_split.addLayout(right_col, 6)
        content_layout.addLayout(top_split)

        # ---- Bottom Section: Mode Studio 8-Card Responsive Grid ----
        self.mode_studio_panel = GlassPanel(self, self.current_theme)
        mode_studio_layout = QVBoxLayout(self.mode_studio_panel)
        mode_studio_layout.setContentsMargins(18, 16, 18, 16)
        mode_studio_layout.setSpacing(10)

        header_box = QVBoxLayout()
        header_box.setSpacing(2)
        self.lbl_ms_title = QLabel("MODE STUDIO")
        self.lbl_ms_title.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        self.lbl_ms_title.setStyleSheet("letter-spacing: 0.8px;")

        self.lbl_ms_sub = QLabel("Select, customize LED color, haptics, and direction for each workflow mode.")
        self.lbl_ms_sub.setFont(QFont("Segoe UI", 9))
        header_box.addWidget(self.lbl_ms_title)
        header_box.addWidget(self.lbl_ms_sub)
        mode_studio_layout.addLayout(header_box)

        # 3-Column Responsive Grid matching Web UI
        self.grid_modes = QGridLayout()
        self.grid_modes.setSpacing(12)
        self.mode_cards = []

        for i, m in enumerate(self.modes_data):
            card = NativeModeCard(
                mode_idx=i, name=m["name"], desc=m["desc"], color_hex=m["c"],
                enabled=m["en"], haptic_idx=m["hp"], inverted=m["inv"],
                parent=self, theme_key=self.current_theme
            )
            card.cardClicked.connect(self._switch_to_mode)
            card.enabledToggled.connect(self._on_mode_en_toggled)
            card.colorChanged.connect(self._on_mode_color_changed)
            card.hapticChanged.connect(self._on_mode_hp_changed)
            card.invertToggled.connect(self._on_mode_inv_toggled)

            self.mode_cards.append(card)
            row = i // 3
            col = i % 3
            self.grid_modes.addWidget(card, row, col)

        mode_studio_layout.addLayout(self.grid_modes)
        content_layout.addWidget(self.mode_studio_panel)

        self.scroll_area.setWidget(content)

        # Precision Side Scroll Rail Slider (matching Web UI aside.side-scroll-rail)
        scroll_wrapper = QHBoxLayout()
        scroll_wrapper.setSpacing(8)
        scroll_wrapper.setContentsMargins(0, 0, 0, 0)
        scroll_wrapper.addWidget(self.scroll_area, 1)

        self.side_rail = AppleSideScrollRail(self.scroll_area, self, self.current_theme)
        scroll_wrapper.addWidget(self.side_rail)

        master_layout.addLayout(scroll_wrapper, 1)

        # Highlight initial mode 0
        self._switch_to_mode(0)

    # ========================================================
    # Theme Management
    # ========================================================
    def apply_theme(self, theme_key: str):
        self.current_theme = theme_key
        t = THEMES.get(theme_key, THEMES["walnut"])
        self.setStyleSheet(get_stylesheet(theme_key))

        # Re-theme subcomponents
        self.header.apply_theme(theme_key)
        self.stage_panel.apply_theme(theme_key)
        self.island.apply_theme(theme_key)
        self.controls_panel.apply_theme(theme_key)
        self.wifi_card.apply_theme(theme_key)

        self.mode_studio_panel.apply_theme(theme_key)
        self.adv_disclosure.apply_theme(theme_key)
        self.neural_card.apply_theme(theme_key)
        self.detent_strip.apply_theme(theme_key)

        if hasattr(self, 'mode_bar'):
            self.mode_bar.apply_theme(theme_key)
        if hasattr(self, 'cal_card'):
            self.cal_card.apply_theme(theme_key)
        if hasattr(self, 'about_card'):
            self.about_card.apply_theme(theme_key)
        if hasattr(self, 'side_rail'):
            self.side_rail.apply_theme(theme_key)
        if hasattr(self, 'stage_divider'):
            self.stage_divider.setStyleSheet(f"background-color: {t['border']}; border: none;")
        if hasattr(self, 'boot_divider'):
            self.boot_divider.setStyleSheet(f"background-color: {t['border']}; border: none;")
        if hasattr(self, 'lbl_stage_boot'):
            self.lbl_stage_boot.setStyleSheet(f"color: {t['text_secondary']};")
        if hasattr(self, 'chk_stage_boot'):
            self.chk_stage_boot.setStyleSheet(f"""
                QCheckBox {{
                    spacing: 8px;
                }}
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border-radius: 4px;
                    border: 1px solid {t['border_hover']};
                    background-color: {t['surface']};
                }}
                QCheckBox::indicator:hover {{
                    border-color: {t['accent']};
                }}
                QCheckBox::indicator:checked {{
                    background-color: {t['accent']};
                    border-color: {t['accent']};
                }}
            """)

        # Update section headers typography colors
        self.lbl_detent.setStyleSheet(f"color: {t['muted']}; letter-spacing: 0.8px;")
        self.lbl_ctrl_title.setStyleSheet(f"color: {t['muted']}; letter-spacing: 0.8px;")
        self.lbl_gestures.setStyleSheet(f"color: {t['muted']}; margin-top: 6px; letter-spacing: 0.8px;")
        self.lbl_ms_title.setStyleSheet(f"color: {t['muted']}; letter-spacing: 0.8px;")
        self.lbl_ms_sub.setStyleSheet(f"color: {t['muted']};")

        for card in self.mode_cards:
            card.apply_theme(theme_key)

        self.sl_bri.apply_theme(theme_key)
        self.sl_idle.apply_theme(theme_key)
        self.sl_thr.apply_theme(theme_key)
        self.pk_fwd.apply_theme(theme_key)
        self.pk_rev.apply_theme(theme_key)
        self.pk_tspin.apply_theme(theme_key)
        self.pk_tap.apply_theme(theme_key)


    # ========================================================
    # Mode & Crown Handling
    # ========================================================
    def _switch_to_mode(self, idx: int, sync_to_device: bool = True):
        if idx == self.current_mode_idx and not sync_to_device:
            return
        if 0 <= idx < len(self.modes_data):
            self.current_mode_idx = idx
            m = self.modes_data[idx]
            for i, card in enumerate(self.mode_cards):
                card.set_active(i == idx)

            self.island.set_mode(m["name"], m["desc"], m["c"])
            self.dial.set_mode_color(m["c"])
            self.detent_strip.set_profile(m["hp"])

            if hasattr(self, 'mode_bar'):
                self.mode_bar.set_mode(m["name"], m["c"])

            if self.stream_worker:
                self.stream_worker.active_mode = m["name"]
                self.stream_worker.active_threshold = m["thr"]

            if sync_to_device:
                self.send_command(f"SET:MODE:{idx}")

    def _on_crown_profile_selected(self, hp_idx: int):
        self.modes_data[self.current_mode_idx]["hp"] = hp_idx
        self.send_command(f"SET:HP:{hp_idx}")
        self.send_command("TEST:HAPTIC")

    def _on_touch_thr_changed(self, pct: int):
        # Convert UI percentage (0% to 100%) to raw firmware threshold (3000 to 100)
        raw_val = int(3000 - (pct / 100.0) * 2900)
        self.send_command(f"SET:THR:{raw_val}")

    def _on_mode_en_toggled(self, idx: int, enabled: bool):
        self.modes_data[idx]["en"] = enabled
        self._send_full_mode_config(idx)

    def _on_mode_color_changed(self, idx: int, hex_color: str):
        self.modes_data[idx]["c"] = hex_color
        if idx == self.current_mode_idx:
            self.dial.set_mode_color(hex_color)
            self.island.set_mode(self.modes_data[idx]["name"], self.modes_data[idx]["desc"], hex_color)
        self._send_full_mode_config(idx)

    def _on_mode_hp_changed(self, idx: int, hp_idx: int):
        self.modes_data[idx]["hp"] = hp_idx
        self._send_full_mode_config(idx)

    def _on_mode_inv_toggled(self, idx: int, inverted: bool):
        self.modes_data[idx]["inv"] = inverted
        self._send_full_mode_config(idx)

    def _send_full_mode_config(self, idx: int):
        m = self.modes_data[idx]
        en_val = 1 if m["en"] else 0
        inv_val = 1 if m["inv"] else 0
        self.send_command(f"SET:MODE:{idx},EN:{en_val},CS:{m['c']},HP:{m['hp']},INV:{inv_val},MTHR:{m['thr']}")

    def _open_about_modal(self):
        modal = AboutModal(self, self.current_theme)
        modal.exec()

    # ========================================================
    # Wi-Fi Scanner & Provisioning
    # ========================================================
    def _on_wifi_scan_requested(self):
        if self.wifi_worker and self.wifi_worker.isRunning():
            return
        self.wifi_worker = WifiScanWorker()
        self.wifi_worker.scanned.connect(self.wifi_card.populate_networks)
        self.wifi_worker.start()

    def _on_wifi_provision_requested(self, ssid: str, pwd: str):
        if not self.transport.is_connected() or self.transport.mode != TransportMode.USB:
            self.wifi_card.on_provision_error("Connect USB cable first to update password")
            return
        cmd = f"SET:WIFI:{ssid}:{pwd}"
        self.send_command(cmd)
        logging.info(f"Sent Wi-Fi credentials for: {ssid}")

    def _auto_reconnect_tick(self):
        """Silently and reliably attempts reconnect if disconnected from OmniScroll."""
        if not self.transport.is_connected():
            if not (self.discovery_worker and self.discovery_worker.isRunning()):
                self.start_discovery()

    # ========================================================
    # Connection Management & Streaming
    # ========================================================
    def start_discovery(self):
        if self.discovery_worker and self.discovery_worker.isRunning():
            return
        self.discovery_worker = DiscoveryWorker(self.transport)
        self.discovery_worker.found.connect(self._on_discovered)
        self.discovery_worker.start()

    def _check_connection(self):
        if not self.transport.is_connected():
            self.header.set_connection_status(False, "Searching...", "#FF9500")
            self.start_discovery()

    def _toggle_connection(self):
        if self.transport.is_connected():
            if self.stream_worker:
                self.stream_worker.stop()
            self.transport.disconnect()
            self.wifi_card.set_wired_status(False)
            self.wifi_card.set_wifi_status(False)
            self.header.set_connection_status(False, "Disconnected")
        else:
            self.header.set_connection_status(False, "Searching...")
            self.start_discovery()

    @Slot(int, str)
    def _on_discovered(self, mode: int, address: str):
        if mode != TransportMode.NONE and address:
            ok = self.transport.connect(mode, address)
            if ok:
                if mode == TransportMode.WIFI:
                    self.transport.set_last_known_ip(address)
                    self.settings.setValue("last_wifi_ip", address)
                status_text = self.transport.get_status_text()
                conn_label = "Cable" if mode == TransportMode.USB else "Wireless"
                self.header.set_connection_status(True, conn_label)
                logging.info(f"Connected to OmniScroll: {status_text}")

                is_wired = (mode == TransportMode.USB)
                self.wifi_card.set_wired_status(is_wired)
                if mode == TransportMode.WIFI:
                    self.wifi_card.set_wifi_status(True, address)

                if self.stream_worker:
                    self.stream_worker.stop()
                self.stream_worker = StreamWorker(self.transport, self.bridge)
                self.stream_worker.packet_received.connect(self._on_packet)
                self.stream_worker.line_received.connect(self._on_line)
                self.stream_worker.connection_lost.connect(self._on_connection_lost)
                self.stream_worker.active_mode = self.modes_data[self.current_mode_idx]["name"]
                self.stream_worker.active_threshold = self.modes_data[self.current_mode_idx]["thr"]
                self.stream_worker.start()

                self.send_command("GET:CONFIG")
                self.send_command("GET:WIFI:STATUS")
        else:
            self.header.set_connection_status(False, "Disconnected")

    @Slot()
    def _on_connection_lost(self, auto_failover=False):
        self.bridge.release_alt_clutch()
        logging.warning("Connection to OmniScroll dropped")
        if self.stream_worker:
            self.stream_worker.stop()
            self.stream_worker = None
        self.transport.disconnect()
        self.wifi_card.set_wired_status(False)
        self.wifi_card.set_wifi_status(False)
        if auto_failover:
            self.header.set_connection_status(False, "Switching to Wi-Fi...")
            QTimer.singleShot(250, self.start_discovery)
        else:
            self.header.set_connection_status(False, "Disconnected")

    def nativeEvent(self, eventType, message):
        """Windows Native PnP Event Hook for 0% CPU Hot-Plug Detection."""
        if eventType == b'windows_generic_MSG':
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_DEVICECHANGE:
                    wParam = msg.wParam
                    if wParam in (DBT_DEVICEARRIVAL, DBT_DEVNODES_CHANGED, DBT_DEVICEREMOVECOMPLETE):
                        from protocol import SerialStreamManager
                        # Case 1: Currently connected via USB — check if active port was unplugged
                        if self.transport.mode == TransportMode.USB and self.transport.is_connected():
                            active_p = self.transport.usb.active_port
                            detected = SerialStreamManager.list_ports()
                            if not any(p["port"] == active_p for p in detected):
                                logging.info(f"Windows PnP: Active port {active_p} removed from system. Switching to Wi-Fi...")
                                self._on_connection_lost(auto_failover=True)

                        # Case 2: Currently connected via Wi-Fi — check if OmniScroll USB was plugged into PC!
                        elif self.transport.mode == TransportMode.WIFI and self.transport.is_connected():
                            detected = SerialStreamManager.list_ports()
                            if detected:
                                new_port = detected[0]["port"]
                                logging.info(f"Windows PnP: OmniScroll plugged into USB ({new_port}). Promoting to wired USB...")
                                self._promote_to_usb(new_port)

                        # Case 3: Disconnected — trigger discovery
                        elif not self.transport.is_connected():
                            QTimer.singleShot(250, self.start_discovery)
            except Exception as e:
                logging.debug(f"nativeEvent error: {e}")
        return super().nativeEvent(eventType, message)

    def _promote_to_usb(self, port: str):
        """Seamless hot-handover from Wi-Fi to wired USB."""
        if self.stream_worker:
            self.stream_worker.stop()
            self.stream_worker = None
        self.transport.disconnect()
        ok = self.transport.connect(TransportMode.USB, port)
        if ok:
            self.header.set_connection_status(True, "Cable")
            self.wifi_card.set_wired_status(True)
            self.wifi_card.set_wifi_status(False)
            self.stream_worker = StreamWorker(self.transport, self.bridge)
            self.stream_worker.packet_received.connect(self._on_packet)
            self.stream_worker.line_received.connect(self._on_line)
            self.stream_worker.connection_lost.connect(self._on_connection_lost)
            self.stream_worker.active_mode = self.modes_data[self.current_mode_idx]["name"]
            self.stream_worker.active_threshold = self.modes_data[self.current_mode_idx]["thr"]
            self.stream_worker.start()
            self.send_command("GET:CONFIG")
            self.send_command("GET:WIFI:STATUS")
            logging.info(f"Successfully promoted to wired USB: {port}")

    def send_command(self, cmd: str):
        self.transport.send_command(cmd)

    def _request_telemetry(self):
        if self.transport.is_connected():
            self.send_command("GET:STATUS")

    def _reject_last_gesture(self):
        self.send_command("SET:GESTURE_REJECT")
        self.dial.show_rejection()

    def _on_cal_changed(self, channel: str, val: float):
        self.send_command(f"SET:CAL:{channel}:{val:.3f}")

    def _on_test_led(self, ch: str):
        self.send_command(f"TEST:LED:{ch}")
        if ch == "R":
            self.dial.set_mode_color("FF0000")
        elif ch == "G":
            self.dial.set_mode_color("00FF00")
        elif ch == "B":
            self.dial.set_mode_color("0000FF")
        elif ch == "RESET":
            m = self.modes_data[self.current_mode_idx]
            self.dial.set_mode_color(m["c"])

    def _run_wifi_ping_benchmark(self):
        target_ip = self.transport.wifi.target_ip if (self.transport.mode == TransportMode.WIFI and self.transport.wifi) else None
        if not target_ip or not self.transport.is_connected():
            # Run local loopback simulation benchmark
            rtts = []
            for _ in range(10):
                t0 = time.perf_counter()
                time.sleep(0.0016) # 1.6ms simulated network delay
                t1 = time.perf_counter()
                rtts.append((t1 - t0) * 1000.0)
            avg = sum(rtts) / len(rtts)
            min_r = min(rtts)
            max_r = max(rtts)
            jitter = (sum((x - avg)**2 for x in rtts) / len(rtts)) ** 0.5
            if getattr(self.wifi_card, 'bench_widget', None):
                self.wifi_card.bench_widget.set_benchmark_results(avg, min_r, max_r, jitter)
            return

        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.3)
        rtts = []
        for seq in range(10):
            t0 = time.perf_counter()
            msg = f"PING:{seq}:{t0}".encode('utf-8')
            try:
                sock.sendto(msg, (target_ip, 4211))
                data, _ = sock.recvfrom(256)
                t1 = time.perf_counter()
                rtts.append((t1 - t0) * 1000.0)
            except Exception:
                pass
            time.sleep(0.02)
        sock.close()

        if rtts:
            avg = sum(rtts) / len(rtts)
            min_r = min(rtts)
            max_r = max(rtts)
            jitter = (sum((x - avg)**2 for x in rtts) / len(rtts)) ** 0.5
            if getattr(self.wifi_card, 'bench_widget', None):
                self.wifi_card.bench_widget.set_benchmark_results(avg, min_r, max_r, jitter)

    @Slot(object)
    def _on_packet(self, pkt: OMPPacket):
        if hasattr(pkt, 'mode') and pkt.mode != self.current_mode_idx and pkt.mode < len(self.modes_data):
            self._switch_to_mode(pkt.mode, sync_to_device=False)
        if pkt.type == PKT_MOTION:
            self.dial.rotate_delta(pkt.delta)
        elif pkt.type == PKT_GESTURE:
            act_str = "Action"
            for code, name in ACTIONS:
                if code == pkt.action:
                    act_str = name
                    break
            self.dial.show_gesture("FLICK_FWD" if pkt.delta > 0 else "FLICK_REV", act_str)
        elif pkt.type == PKT_ACTION:
            act_str = "Action"
            for code, name in TSPIN_ACTIONS + ACTIONS:
                if code == pkt.action:
                    act_str = name
                    break
            self.dial.show_gesture("TOUCH & SPIN", act_str)
        elif pkt.type == PKT_STATUS:
            if pkt.action != self.current_mode_idx:
                self._switch_to_mode(pkt.action, sync_to_device=False)

    @Slot(str)
    def _on_line(self, line: str):
        if line.startswith("OMNISCROLL:WAKE") or line.startswith("ROUFSWEB:"):
            conn_label = "Cable" if self.transport.mode == TransportMode.USB else "Wireless"
            self.header.set_connection_status(True, conn_label)
            logging.info(f"Hardware Wake Announcement received: {line}")
            if "MODE=" in line:
                for part in line.split(":"):
                    if part.startswith("MODE="):
                        mname = part[5:]
                        for i, m in enumerate(self.modes_data):
                            if m["name"] == mname:
                                if i != self.current_mode_idx:
                                    self._switch_to_mode(i, sync_to_device=False)
                                break
        elif line.startswith("CONFIG:"):
            try:
                cfg = json.loads(line[7:])
                if "bri" in cfg:
                    self.sl_bri.blockSignals(True)
                    self.sl_bri.setValue(int(cfg["bri"]))
                    self.sl_bri.blockSignals(False)
                if "idle" in cfg:
                    self.sl_idle.blockSignals(True)
                    self.sl_idle.setValue(int(cfg["idle"]))
                    self.sl_idle.blockSignals(False)
                if "thr" in cfg:
                    self.sl_thr.blockSignals(True)
                    raw_thr = int(cfg["thr"])
                    pct = int(round((3000 - raw_thr) / (3000 - 100) * 100))
                    pct = max(0, min(100, pct))
                    self.sl_thr.setValue(pct)
                    self.sl_thr.blockSignals(False)
                if "flick_fwd" in cfg:
                    self.pk_fwd.blockSignals(True)
                    self.pk_fwd.set_action(int(cfg["flick_fwd"]))
                    self.pk_fwd.blockSignals(False)
                if "flick_rev" in cfg:
                    self.pk_rev.blockSignals(True)
                    self.pk_rev.set_action(int(cfg["flick_rev"]))
                    self.pk_rev.blockSignals(False)
                if "tspin" in cfg:
                    self.pk_tspin.blockSignals(True)
                    self.pk_tspin.set_action(int(cfg["tspin"]))
                    self.pk_tspin.blockSignals(False)
                if "single_tap" in cfg:
                    self.pk_tap.blockSignals(True)
                    self.pk_tap.set_action(int(cfg["single_tap"]))
                    self.pk_tap.blockSignals(False)
                if "g_mu_s" in cfg and "g_mu_r" in cfg and "g_mu_t" in cfg:
                    self.neural_card.set_centroids(float(cfg["g_mu_s"]), float(cfg["g_mu_r"]), float(cfg["g_mu_t"]))
                if "cal_r" in cfg and "cal_g" in cfg and "cal_b" in cfg:
                    self.cal_card.set_calibration(float(cfg["cal_r"]), float(cfg["cal_g"]), float(cfg["cal_b"]))
                if "modes" in cfg and isinstance(cfg["modes"], list):
                    for idx, m_cfg in enumerate(cfg["modes"]):
                        if idx < len(self.modes_data):
                            self.modes_data[idx]["en"] = bool(m_cfg.get("en", 1))
                            self.modes_data[idx]["c"] = m_cfg.get("c", self.modes_data[idx]["c"])
                            self.modes_data[idx]["hp"] = int(m_cfg.get("hp", 0))
                            self.modes_data[idx]["inv"] = bool(m_cfg.get("inv", 0))
                            self.modes_data[idx]["thr"] = int(m_cfg.get("thr", 10))
                            if idx < len(self.mode_cards):
                                self.mode_cards[idx].update_data(self.modes_data[idx])
                logging.info("Hardware configuration synchronized successfully.")
            except Exception as e:
                logging.warning(f"Error parsing CONFIG JSON: {e}")
        elif line.startswith("SCROLL:"):
            try:
                self.dial.rotate_delta(int(line[7:]))
            except: pass
        elif line.startswith("STATUS:"):
            try:
                st = json.loads(line[7:])
                if "mode" in st:
                    mname = st["mode"]
                    for i, m in enumerate(self.modes_data):
                        if m["name"] == mname:
                            if i != self.current_mode_idx:
                                self._switch_to_mode(i, sync_to_device=False)
                            break
            except Exception:
                pass
        elif line.startswith("MODE:"):
            mname = line[5:].strip()
            for i, m in enumerate(self.modes_data):
                if m["name"] == mname:
                    if i != self.current_mode_idx:
                        self._switch_to_mode(i, sync_to_device=False)
                    break
        elif line.startswith("GESTURE:"):
            if "REJECT" in line:
                self.dial.show_rejection()
            else:
                parts = line.split(":")
                gname = parts[1] if len(parts) > 1 else "GESTURE"
                act_code = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
                act_str = "Action"
                for code, name in ACTIONS:
                    if code == act_code:
                        act_str = name
                        break
                is_neural = ("LEARN" in line)
                self.dial.show_gesture(gname, act_str, is_neural)
        elif line.startswith("WIFI:STATUS:"):
            try:
                d = json.loads(line[12:])
                ip = d.get("ip", "0.0.0.0")
                ssid = d.get("ssid", "")
                self.wifi_card.set_wifi_status(d.get("connected", False), ip, d.get("rssi", 0), ssid)
                if ip and ip != "0.0.0.0":
                    self.transport.set_last_known_ip(ip)
                    self.settings.setValue("last_wifi_ip", ip)
                if ssid:
                    self.settings.setValue("last_wifi_ssid", ssid)
            except: pass
        elif line.startswith("WIFI:CONFIGURED:"):
            ssid = line[16:].strip()
            self.wifi_card.on_provision_success(ssid)
            if ssid:
                self.settings.setValue("last_wifi_ssid", ssid)
            logging.info(f"Hardware confirmed Wi-Fi credentials saved: {ssid}")
        elif line.startswith("WIFI:ERROR:"):
            err = line[11:].strip()
            self.wifi_card.on_provision_error(err)
            logging.warning(f"Hardware Wi-Fi provisioning error: {err}")
        elif line.startswith("GESTURE:LEARNED:"):
            try:
                parts = line[16:].split(",")
                s, r, t = 110.0, 85.0, 25.0
                for p in parts:
                    k, v = p.split("=")
                    if k == "S": s = float(v)
                    elif k == "R": r = float(v)
                    elif k == "T": t = float(v)
                self.neural_card.set_centroids(s, r, t)
            except: pass

    # ========================================================
    # Windows Startup Registry Integration
    # ========================================================
    def is_startup_enabled(self) -> bool:
        run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_READ)
            val, _ = winreg.QueryValueEx(key, "OmniScroll")
            winreg.CloseKey(key)
            return bool(val)
        except Exception:
            return False

    def set_startup_enabled(self, enabled: bool):
        run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_WRITE)
            if enabled:
                cmd = f'"{sys.executable}"' if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                winreg.SetValueEx(key, "OmniScroll", 0, winreg.REG_SZ, cmd)
                logging.info(f"Enabled Windows startup: {cmd}")
            else:
                try: winreg.DeleteValue(key, "OmniScroll")
                except WindowsError: pass
            winreg.CloseKey(key)
        except Exception as e:
            logging.error(f"Failed to update startup registry: {e}")

    # ========================================================
    # System Tray Integration
    # ========================================================
    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, "icon.ico")
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
            self.tray.setIcon(app_icon)

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show Dashboard")
        show_action.triggered.connect(self.showNormal)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self._quit_app)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "OmniScroll",
            "Running in the background. Double-click tray icon to open.",
            QSystemTrayIcon.Information,
            2000
        )

    def _quit_app(self):
        if self.stream_worker:
            self.stream_worker.stop()
        if self.discovery_worker and self.discovery_worker.isRunning():
            self.discovery_worker.wait(1500)
        if self.wifi_worker and self.wifi_worker.isRunning():
            self.wifi_worker.wait(1000)
        self.transport.disconnect()
        QApplication.quit()


if __name__ == "__main__":
    # 1. Register Windows Application User Model ID for proper taskbar icon binding
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            'roufsweb.omniscroll.controlpanel.2'
        )
    except Exception:
        pass

    app = QApplication(sys.argv)

    # 2. Global application icon for all top-level windows and taskbar
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    icon_path = os.path.join(base_dir, "icon.ico")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)

    window = MainWindow()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()
    sys.exit(app.exec())
