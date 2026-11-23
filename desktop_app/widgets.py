"""
widgets.py — Native Apple Pro HIG & Nordic Walnut UI Components for OmniScroll
Contains pure Windows native widgets styled with pixel-perfect fidelity:
- HeaderBar & ThemeSegmentedBar (with colored theme dots and OMNI SCROLL logo)
- ActiveModeIsland & TestHapticButton
- PhotorealisticRotaryDial (1:1 bearing Crown tracking with real hardware WebP base,
  front slanted OLED diffuser bloom, perspective knurled ticks & radiant HomePod ripple)
- HapticDetentStrip (Click, Thud, Tick, Soft, Off with micro-tactile glyphs)
- AppleCapsuleSlider (Apple Control Center tactile floating pill sliders)
- AppleCapsulePicker (Gesture rows with round icon badges and dropdowns)
- AppleToggleSwitch (iOS-style tactile toggle switch)
- WifiStudioContainer (with 2.4 GHz vs 5 GHz compatibility display)
- NativeModeCard (8-mode studio grid component with Apple toggle and active mode glow)
- TinyOLNeuralCard (real-time learned gesture centroid metrics)
- CollapsibleDisclosure (Apple progressive disclosure container)
"""
import os
import sys
import math
from PySide6.QtCore import Qt, QRect, QRectF, QPointF, Signal, QTimer, Property, QPropertyAnimation, QUrl
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QCheckBox, QSizePolicy,
    QColorDialog, QDialog, QScrollArea
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QRadialGradient,
    QLinearGradient, QPainterPath, QPixmap, QPolygonF, QDesktopServices
)

from themes import THEMES

COUNTS_PER_REV = 520.0
DEG_PER_COUNT  = 360.0 / COUNTS_PER_REV

# Dial geometry constants matching docs/index.html perspective projection
DISK_CX = 670.1
DISK_CY = 258.1
DISK_RX = 423.0
DISK_RY = 225.6
DISK_ROTATION = 2.74
DISK_ASPECT = DISK_RY / DISK_RX  # 0.5333
TICK_COUNT = 48

ACTIONS = [
    (0, "Off"),
    (1, "Browser Back (Alt+←)"),
    (2, "Browser Forward (Alt+→)"),
    (3, "Undo (Ctrl+Z)"),
    (4, "Redo (Ctrl+Shift+Z)"),
    (5, "Media Prev Track"),
    (6, "Media Next Track"),
    (7, "Prev Tab (Ctrl+Shift+Tab)"),
    (8, "Next Tab (Ctrl+Tab)"),
    (9, "Prev Desktop (Win+Ctrl+←)"),
    (10, "Next Desktop (Win+Ctrl+→)"),
    (11, "Volume Down"),
    (12, "Volume Up"),
    (13, "Copy (Ctrl+C)"),
    (14, "Paste (Ctrl+V)"),
    (15, "Next Mode"),
    (16, "Previous Mode"),
    (25, "Play / Pause (Consumer)")
]

# Continuous 2-way modifier actions for Touch & Spin (CW/CCW bidirectional)
TSPIN_ACTIONS = [
    (0, "Disabled"),
    (1, "Horizontal Scroll"),
    (2, "Universal Zoom"),
    (3, "Turbo 4x Speed"),
    (4, "Timeline Scrub"),
    (5, "Volume"),
    (6, "App Switcher")
]

# Discrete shortcut actions for Single Tap
SINGLE_TAP_ACTIONS = [
    (99, "Reject Mis-trigger (Neural Engine)"),
    (0, "Disabled / No Action"),
    (25, "Play / Pause"),
    (1, "Browser Back (Alt+←)"),
    (2, "Browser Forward (Alt+→)"),
    (3, "Undo (Ctrl+Z)"),
    (4, "Redo (Ctrl+Shift+Z)"),
    (5, "Media Previous"),
    (6, "Media Next"),
    (7, "Prev Tab (Ctrl+Shift+Tab)"),
    (8, "Next Tab (Ctrl+Tab)"),
    (9, "Prev Desktop (Win+Ctrl+←)"),
    (10, "Next Desktop (Win+Ctrl+→)"),
    (11, "Volume Down"),
    (12, "Volume Up"),
    (13, "Copy (Ctrl+C)"),
    (14, "Paste (Ctrl+V)"),
    (15, "Next Mode"),
    (16, "Previous Mode")
]

PROFILES = [
    ("∿", "Click"),
    ("▬", "Thud"),
    ("·", "Tick"),
    ("~", "Soft"),
    ("✕", "Off")
]

MODE_ICONS = {
    "SCROLL": "↕",
    "VOLUME": "▲",
    "TIMELINE": "◫",
    "ZOOM": "⊕",
    "H_SCROLL": "↔",
    "BRIGHTNESS": "☼",
    "TABBING": "◫",
    "UNDO_REDO": "↶"
}


def ellipse_xy(cx, cy, rx, ry, angle_deg, rot_deg=0.0):
    """Calculates perspective 2D point on tilted ellipse."""
    a = math.radians(angle_deg)
    rot = math.radians(rot_deg)
    px = rx * math.cos(a)
    py = ry * math.sin(a)
    x = cx + px * math.cos(rot) - py * math.sin(rot)
    y = cy + px * math.sin(rot) + py * math.cos(rot)
    return x, y


# =============================================================================
# 1. Glass Container Base
# =============================================================================
class GlassPanel(QFrame):
    """Frosted surface container matching the Web Control Panel card styling."""
    def __init__(self, parent=None, theme_key="walnut"):
        super().__init__(parent)
        self.theme_key = theme_key
        self._apply_panel_style(theme_key)

    def _apply_panel_style(self, theme_key: str):
        t = THEMES.get(theme_key, THEMES["walnut"])
        self.setStyleSheet(f"""
            GlassPanel {{
                background-color: {t['card_bg']};
                border: 1px solid {t['border']};
                border-radius: 18px;
            }}
        """)

    def apply_theme(self, theme_key: str):
        self.theme_key = theme_key
        self._apply_panel_style(theme_key)


# =============================================================================
# 2. Apple Segmented Theme Switcher (with colored dots)
# =============================================================================
# =============================================================================
# 2. Apple Segmented Theme Switcher (Matching Web UI .apple-theme-segmented)
# =============================================================================
class ThemeSegmentButton(QPushButton):
    """
    Individual theme segment button matching Web UI .theme-seg-btn:
    - Dedicated circular color swatch (9px, scaled to 11px with glowing ring when active)
    - Aluminum swatch with high-contrast subtle white rim matching Web UI
    - Centered typography with 7px gap (500 weight when inactive, 600 when active)
    - Active slider pill thumb with border highlight
    """
    def __init__(self, key: str, title: str, swatch_color: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.title = title
        self.swatch_color = swatch_color
        self.theme_dict = None
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_theme_dict(self, t: dict):
        self.theme_dict = t
        self.update()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        w = self.width()
        h = self.height()
        t = self.theme_dict or THEMES["walnut"]

        is_active = self.isChecked()
        is_hover = self.underMouse()

        # 1. Background Pill Thumb if active or hovered
        if is_active:
            painter.setBrush(QBrush(QColor(t["surface_raised"])))
            painter.setPen(QPen(QColor(t["border_hover"]), 1))
            painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 14, 14)
        elif is_hover:
            painter.setBrush(QBrush(QColor(t.get("surface_hover", "#34261C"))))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 14, 14)

        # 2. Typography metrics for exact center alignment
        font = QFont("Segoe UI", 9)
        font.setWeight(QFont.Weight.DemiBold if is_active else QFont.Weight.Medium)
        painter.setFont(font)
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(self.title)

        swatch_size = 10.5 if is_active else 8.5
        gap = 7.0
        total_content_w = swatch_size + gap + text_w
        start_x = max(6.0, (w - total_content_w) / 2.0)

        # 3. Draw Swatch Circle
        swatch_x = start_x
        swatch_y = (h - swatch_size) / 2.0
        swatch_rect = QRectF(swatch_x, swatch_y, swatch_size, swatch_size)

        base_color = QColor(self.swatch_color)

        # Glow Ring when active
        if is_active:
            glow = QColor(base_color)
            glow.setAlpha(95)
            painter.setPen(QPen(glow, 2.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QRectF(swatch_x - 1.2, swatch_y - 1.2, swatch_size + 2.4, swatch_size + 2.4))

        # Swatch Rim: Aluminum has subtle white rim in Web UI
        if self.key == "aluminum":
            painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
        else:
            painter.setPen(Qt.NoPen)

        painter.setBrush(QBrush(base_color))
        painter.drawEllipse(swatch_rect)

        # 4. Draw Title
        text_color = QColor(t["text"] if (is_active or is_hover) else t["muted"])
        painter.setPen(QPen(text_color))

        text_x = int(start_x + swatch_size + gap)
        text_rect = QRect(text_x, 0, int(w - text_x), h)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.title)


class ThemeSegmentedBar(QFrame):
    """
    Apple Segmented Theme Switcher matching Web UI .apple-theme-segmented:
    - Frosted capsule base with 18px border radius
    - 4 themes with glowing circular swatches:
      * Obsidian (#00D4FF cyan glow)
      * Aluminum (#0071E3 with white rim & blue glow)
      * Walnut   (#FFA000 amber glow)
      * Ultra    (#FF6200 international orange glow)
    - Active slider pill thumb with border highlight
    - Mathematically fixed geometry (360x36)
    """
    themeSelected = Signal(str)

    def __init__(self, current_theme="walnut", parent=None):
        super().__init__(parent)
        self.current_theme = current_theme
        self.buttons = {}

        self.setFixedSize(360, 36)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        themes_list = [
            ("obsidian", "Obsidian", "#00D4FF"),
            ("aluminum", "Aluminum", "#0071E3"),
            ("walnut",   "Walnut",   "#FFA000"),
            ("ultra",    "Ultra",    "#FF6200")
        ]

        for key, name, swatch_color in themes_list:
            btn = ThemeSegmentButton(key, name, swatch_color, self)
            btn.setChecked(key == current_theme)
            btn.clicked.connect(lambda checked, k=key: self._on_btn_clicked(k))
            self.buttons[key] = btn
            layout.addWidget(btn)

        self.apply_theme(current_theme)

    def _on_btn_clicked(self, key: str):
        if key == self.current_theme:
            if key in self.buttons:
                self.buttons[key].setChecked(True)
            return
        self.current_theme = key
        for k, b in self.buttons.items():
            b.setChecked(k == key)
        self.apply_theme(key)
        self.themeSelected.emit(key)

    def apply_theme(self, theme_key: str):
        self.current_theme = theme_key
        t = THEMES.get(theme_key, THEMES["walnut"])
        self.setStyleSheet(f"""
            ThemeSegmentedBar {{
                background-color: {t['surface']};
                border: 1px solid {t['border']};
                border-radius: 18px;
            }}
        """)
        for b in self.buttons.values():
            b.set_theme_dict(t)


# =============================================================================
# 3. Header Bar
# =============================================================================
class HeaderBar(QWidget):
    """
    Top application header:
    - Logo: single unified 'Omniscroll' brand label (no spaces, no CONTROL badge)
    - Center Theme Switcher: mathematically pinned to dead horizontal center (never shifts on status changes)
    - Right Actions: Connect / Status Button + About ('i') Button
    """
    connectClicked = Signal()
    themeChanged   = Signal(str)
    aboutClicked   = Signal()

    def __init__(self, current_theme="walnut", parent=None):
        super().__init__(parent)
        self.current_theme = current_theme
        self.setFixedHeight(56)

        # 1. Left Container: OmniScroll from roufsweb Branding
        self.left_container = QWidget(self)
        left_layout = QHBoxLayout(self.left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(9)

        self.lbl_logo = QLabel("OmniScroll", self.left_container)
        self.lbl_logo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        left_layout.addWidget(self.lbl_logo)

        self.lbl_byline = QLabel("from roufsweb", self.left_container)
        self.lbl_byline.setFont(QFont("Segoe UI", 9.5, QFont.Weight.DemiBold))
        left_layout.addWidget(self.lbl_byline)

        # 2. Right Action Buttons: Connect / Status + About ("i")
        self.right_container = QWidget(self)
        right_layout = QHBoxLayout(self.right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.btn_conn = QPushButton("Disconnected", self.right_container)
        self.btn_conn.setCursor(Qt.PointingHandCursor)
        self.btn_conn.setFixedSize(148, 34)
        self.btn_conn.clicked.connect(self.connectClicked)
        right_layout.addWidget(self.btn_conn)

        self.btn_info = QPushButton("i", self.right_container)
        self.btn_info.setCursor(Qt.PointingHandCursor)
        self.btn_info.setFixedSize(34, 34)
        self.btn_info.setToolTip("About OmniScroll & Hardware Specifications")
        self.btn_info.clicked.connect(self.aboutClicked.emit)
        right_layout.addWidget(self.btn_info)

        self.apply_theme(current_theme)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout_header()

    def _relayout_header(self):
        w = self.width()
        h = self.height()

        # Left Container (OmniScroll from roufsweb Branding)
        self.left_container.adjustSize()
        lw = self.left_container.width()
        lh = self.left_container.height()
        self.left_container.setGeometry(18, (h - lh) // 2, lw, lh)

        # Right Container (Connect + About)
        self.right_container.adjustSize()
        rw = self.right_container.width()
        rh = self.right_container.height()
        self.right_container.setGeometry(w - rw - 18, (h - rh) // 2, rw, rh)

    def set_connection_status(self, connected: bool, text: str = "", color_hex: str = None):
        self.is_connected = connected
        self.conn_text = text
        t = THEMES.get(self.current_theme, THEMES["walnut"])

        text_lower = text.lower()
        if connected:
            if "cable" in text_lower or "usb" in text_lower:
                display_text = "Cable"
                state = "cable"
            elif "wifi" in text_lower or "wireless" in text_lower or "wi-fi" in text_lower:
                display_text = "Wireless"
                state = "wireless"
            else:
                display_text = text
                state = "connected"
        elif "search" in text_lower or "switch" in text_lower:
            display_text = "Searching..."
            state = "searching"
        else:
            display_text = "Disconnected"
            state = "disconnected"

        self.btn_conn.setText(display_text)

        if state in ("cable", "wireless", "connected"):
            # Glassmorphic green hue when connected (via Cable or Wi-Fi Wireless)
            self.btn_conn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(48, 209, 88, 0.16),
                        stop:1 rgba(48, 209, 88, 0.07));
                    color: #30D158;
                    border: 1px solid rgba(48, 209, 88, 0.40);
                    border-radius: 17px;
                    font-size: 11.5px;
                    font-weight: 700;
                    text-align: center;
                    padding: 0px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(48, 209, 88, 0.25),
                        stop:1 rgba(48, 209, 88, 0.12));
                    border: 1px solid rgba(48, 209, 88, 0.65);
                    color: #34C759;
                }
            """)
        elif state == "searching":
            # Glassmorphic amber hue when searching / transitioning
            self.btn_conn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(255, 159, 10, 0.16),
                        stop:1 rgba(255, 159, 10, 0.07));
                    color: #FF9F0A;
                    border: 1px solid rgba(255, 159, 10, 0.40);
                    border-radius: 17px;
                    font-size: 11.5px;
                    font-weight: 700;
                    text-align: center;
                    padding: 0px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(255, 159, 10, 0.25),
                        stop:1 rgba(255, 159, 10, 0.12));
                    border: 1px solid rgba(255, 159, 10, 0.65);
                    color: #FFB340;
                }
            """)
        else:
            # Glassmorphic red hue when disconnected
            self.btn_conn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(255, 69, 58, 0.16),
                        stop:1 rgba(255, 69, 58, 0.07));
                    color: #FF453A;
                    border: 1px solid rgba(255, 69, 58, 0.40);
                    border-radius: 17px;
                    font-size: 11.5px;
                    font-weight: 700;
                    text-align: center;
                    padding: 0px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(255, 69, 58, 0.25),
                        stop:1 rgba(255, 69, 58, 0.12));
                    border: 1px solid rgba(255, 69, 58, 0.65);
                    color: #FF6961;
                }
            """)

        self.right_container.adjustSize()
        self._relayout_header()

    def apply_theme(self, theme_key: str = "walnut"):
        self.current_theme = "walnut"
        t = THEMES["walnut"]
        self.lbl_logo.setStyleSheet(f"color: {t['text']}; font-weight: 700; letter-spacing: -0.2px;")
        self.lbl_byline.setStyleSheet(f"""
            QLabel {{
                color: {t['accent']};
                background: rgba(255, 160, 0, 0.12);
                border: 1px solid rgba(255, 160, 0, 0.28);
                border-radius: 10px;
                padding: 2px 8px;
                font-weight: 600;
                letter-spacing: 0.3px;
            }}
        """)
        self.btn_info.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['surface_raised']};
                color: {t['text_secondary']};
                border: 1px solid {t['border']};
                border-radius: 17px;
                font-family: 'Georgia', 'Times New Roman', serif;
                font-size: 15px;
                font-style: italic;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {t['accent']};
                color: {t['accent']};
                background-color: {t['pill_bg']};
            }}
        """)
        is_conn = getattr(self, 'is_connected', False)
        conn_txt = getattr(self, 'conn_text', "Disconnected")
        self.set_connection_status(is_conn, conn_txt)
        self._relayout_header()



# =============================================================================
# 4. Active Mode Stage Pill (inside Hero Stage Card header)
# =============================================================================
# =============================================================================
# 4. Apple Pulse Button & Active Mode Stage Pill (Matching Web UI .stage-header)
# =============================================================================
class ApplePulseButton(QPushButton):
    """
    Apple HIG tactile pulse trigger button matching Web UI #testHapticBtn (.apple-pulse-btn):
    - Exact SVG ECG pulse waveform icon: M 2 12 h3 l2 -6 4 12 4 -8 2 5 2 -3 h3
    - Bold 12px 'Test Haptic' label
    - Tactile hover feedback with accent color illumination
    """
    def __init__(self, parent=None, theme_key="walnut"):
        super().__init__("Test Haptic", parent)
        self.theme_key = theme_key
        self.setFixedHeight(34)
        self.setCursor(Qt.PointingHandCursor)
        self.apply_theme(theme_key)

    def apply_theme(self, theme_key: str):
        self.theme_key = theme_key
        t = THEMES.get(theme_key, THEMES["walnut"])
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['surface_raised']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 17px;
                padding-left: 32px;
                padding-right: 14px;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 0.2px;
            }}
            QPushButton:hover {{
                border-color: {t['accent']};
                color: {t['accent']};
                background-color: {t['pill_bg']};
            }}
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        t = THEMES.get(self.theme_key, THEMES["walnut"])
        col = QColor(t['accent'] if self.underMouse() else t['text'])

        pen = QPen(col, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        # SVG: M 2 12 h3 l2 -6 4 12 4 -8 2 5 2 -3 h3 (in 24x24 box) scaled into 13x13 box at x=13, y=10.5
        icon_x = 13.0
        icon_y = 10.5
        s = 13.0 / 24.0

        pts = [
            (2, 12), (5, 12), (7, 6), (11, 18), (15, 10), (17, 15), (19, 12), (22, 12)
        ]
        path = QPainterPath()
        path.moveTo(icon_x + pts[0][0] * s, icon_y + pts[0][1] * s)
        for px, py in pts[1:]:
            path.lineTo(icon_x + px * s, icon_y + py * s)
        painter.drawPath(path)


class ActiveModePillWidget(QWidget):
    """
    Unified painted Apple Capsule Pill matching Web UI .stage-badge-pill:
    - 36px height, rounded capsule pill (radius 18px)
    - Anti-aliased 9px circular glowing LED pip (zero square artifacts)
    - Mode title (bold uppercase text, 12px / 800 weight)
    - Crisp 1px vertical separator line matching Web UI border
    - Mode tag/description text (11px / 500 weight, muted color)
    - Absolutely ZERO rogue box borders or stylesheet leaking
    """
    def __init__(self, mode_name="SCROLL", tag="Vertical page scroll", color_hex="007AFF", theme_key="walnut", parent=None):
        super().__init__(parent)
        self.mode_name = mode_name.upper()
        self.tag = tag
        self.color_hex = color_hex
        self.theme_key = theme_key
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._recalc_size()

    def set_data(self, mode_name: str, tag: str, color_hex: str, theme_key: str):
        self.mode_name = mode_name.upper()
        self.tag = tag
        self.color_hex = color_hex
        self.theme_key = theme_key
        self._recalc_size()
        self.update()

    def _recalc_size(self):
        font_title = QFont("Segoe UI", 9)
        font_title.setWeight(QFont.Weight.ExtraBold)
        fm_title = QFontMetrics(font_title)
        title_w = fm_title.horizontalAdvance(self.mode_name)

        font_tag = QFont("Segoe UI", 8)
        font_tag.setWeight(QFont.Weight.Medium)
        fm_tag = QFontMetrics(font_tag)
        tag_w = fm_tag.horizontalAdvance(self.tag)

        total_w = 14 + 9 + 8 + title_w + 10 + 1 + 10 + tag_w + 16
        self.setFixedWidth(int(total_w))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        w = self.width()
        h = self.height()
        t = THEMES.get(self.theme_key, THEMES["walnut"])

        # 1. Capsule Pill Background & Border (matching Web UI .stage-badge-pill)
        pill_rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        painter.setBrush(QBrush(QColor(t["surface_raised"])))
        painter.setPen(QPen(QColor(t["border"]), 1))
        painter.drawRoundedRect(pill_rect, 18, 18)

        # 2. Glowing Antialiased 9px Circular LED Pip (.stage-led-dot)
        c = f"#{self.color_hex}" if not self.color_hex.startswith("#") else self.color_hex
        base_color = QColor(c)

        dot_x = 14.0
        dot_y = (h - 9.0) / 2.0
        dot_rect = QRectF(dot_x, dot_y, 9.0, 9.0)

        # Outer subtle glow halo
        glow_color = QColor(base_color)
        glow_color.setAlpha(80)
        painter.setPen(QPen(glow_color, 2.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(dot_x - 1.0, dot_y - 1.0, 11.0, 11.0))

        # Core LED pip circle
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(base_color))
        painter.drawEllipse(dot_rect)

        # 3. Mode Title (12px / 800 weight)
        font_title = QFont("Segoe UI", 9)
        font_title.setWeight(QFont.Weight.ExtraBold)
        font_title.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)
        painter.setFont(font_title)
        painter.setPen(QPen(QColor(t["text"])))

        fm_title = painter.fontMetrics()
        title_w = fm_title.horizontalAdvance(self.mode_name)
        title_x = int(dot_x + 9.0 + 8.0)
        title_y = int((h + fm_title.ascent() - fm_title.descent()) / 2.0)
        painter.drawText(title_x, title_y, self.mode_name)

        # 4. Vertical Separator Divider (single clean 1px line)
        sep_x = title_x + title_w + 10.0
        painter.setPen(QPen(QColor(t["border"]), 1))
        painter.drawLine(QPointF(sep_x, 8.0), QPointF(sep_x, h - 8.0))

        # 5. Mode Tag/Description (11px / 500 weight)
        font_tag = QFont("Segoe UI", 8)
        font_tag.setWeight(QFont.Weight.Medium)
        painter.setFont(font_tag)
        painter.setPen(QPen(QColor(t["muted"])))

        fm_tag = painter.fontMetrics()
        tag_x = int(sep_x + 10.0)
        tag_y = int((h + fm_tag.ascent() - fm_tag.descent()) / 2.0)
        painter.drawText(tag_x, tag_y, self.tag)


class ActiveModeIsland(QWidget):
    """
    Stage pill header matching Web UI .stage-header:
    - Dedicated ActiveModePillWidget (zero rogue boxes, 9px antialiased LED dot)
    - ApplePulseButton with tactile ECG waveform icon and 'Test Haptic'
    """
    testHapticClicked = Signal()

    def __init__(self, mode_name="SCROLL", tag="Vertical page scroll", color_hex="007AFF", parent=None, theme_key="walnut"):
        super().__init__(parent)
        self.theme_key = theme_key
        self.current_mode_name = mode_name
        self.current_tag = tag
        self.current_color = color_hex

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(12)

        # 1. Stage Badge Pill (.stage-badge-pill)
        self.pill = ActiveModePillWidget(mode_name, tag, color_hex, theme_key, self)
        layout.addWidget(self.pill)

        layout.addStretch()

        # 2. Apple Pulse Button (.apple-pulse-btn with waveform icon)
        self.btn_haptic = ApplePulseButton(self, theme_key)
        self.btn_haptic.clicked.connect(self.testHapticClicked)
        layout.addWidget(self.btn_haptic)

    def set_mode(self, mode_name: str, tag: str, color_hex: str):
        self.current_mode_name = mode_name
        self.current_tag = tag
        self.current_color = color_hex
        self.pill.set_data(mode_name, tag, color_hex, self.theme_key)

    def apply_theme(self, theme_key: str):
        self.theme_key = theme_key
        self.pill.set_data(self.current_mode_name, self.current_tag, self.current_color, theme_key)
        self.btn_haptic.apply_theme(theme_key)



# =============================================================================
# 5. Active Mode Bar Container (matching Web UI #modebar)
# =============================================================================
class ModeBarWidget(QWidget):
    """
    Active Mode Banner Bar matching Web UI #modebar:
    - Positioned directly underneath the top HeaderBar
    - 'ACTIVE MODE' micro-label
    - Rounded frosted badge with glowing LED pip and bold mode name
    """
    def __init__(self, current_mode="SCROLL", color_hex="007AFF", parent=None, theme_key="walnut"):
        super().__init__(parent)
        self.current_mode = current_mode
        self.color_hex = color_hex
        self.theme_key = theme_key
        self.setFixedHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(12)

        self.lbl_label = QLabel("ACTIVE MODE")
        self.lbl_label.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Bold))

        self.badge = QFrame()
        self.badge.setFixedHeight(28)
        badge_layout = QHBoxLayout(self.badge)
        badge_layout.setContentsMargins(10, 0, 12, 0)
        badge_layout.setSpacing(7)

        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)

        self.lbl_mode = QLabel(current_mode)
        self.lbl_mode.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))

        badge_layout.addWidget(self.dot)
        badge_layout.addWidget(self.lbl_mode)

        layout.addWidget(self.lbl_label)
        layout.addWidget(self.badge)
        layout.addStretch()

        self.apply_theme(theme_key)

    def set_mode(self, mode_name: str, color_hex: str):
        self.current_mode = mode_name
        self.color_hex = color_hex
        self.lbl_mode.setText(mode_name)
        c = f"#{color_hex}" if not color_hex.startswith("#") else color_hex
        self.dot.setStyleSheet(f"background-color: {c}; border-radius: 4px;")
        t = THEMES.get(self.theme_key, THEMES["walnut"])
        self.badge.setStyleSheet(f"""
            QFrame {{
                background-color: {t['surface_raised']};
                border: 1px solid {c}66;
                border-radius: 14px;
            }}
            QLabel {{ color: {t['text']}; }}
        """)

    def set_transport_status(self, text: str, is_active=True):
        """Retained as safe no-op for backward compatibility."""
        pass

    def apply_theme(self, theme_key: str):
        self.theme_key = theme_key
        t = THEMES.get(theme_key, THEMES["walnut"])
        c = f"#{self.color_hex}" if not self.color_hex.startswith("#") else self.color_hex

        self.setStyleSheet(f"""
            ModeBarWidget {{
                background-color: {t['surface']};
                border-bottom: 1px solid {t['border']};
            }}
        """)
        self.lbl_label.setStyleSheet(f"color: {t['muted']}; letter-spacing: 0.8px;")
        self.lbl_mode.setStyleSheet(f"color: {t['text']}; font-weight: 700; letter-spacing: 0.5px;")
        self.dot.setStyleSheet(f"background-color: {c}; border-radius: 4px;")
        self.badge.setStyleSheet(f"""
            QFrame {{
                background-color: {t['surface_raised']};
                border: 1px solid {t['border']};
                border-radius: 14px;
            }}
        """)


# =============================================================================
# 6. Live Gesture Badge Overlay (matching Web UI #gestureBadge)
# =============================================================================
class GestureBadgeWidget(QFrame):
    """
    Live gesture toast overlay with Reject button matching Web UI #gestureBadge.
    Floats over the Photorealistic Crown dial.
    """
    rejectClicked = Signal()

    def __init__(self, parent=None, theme_key="walnut"):
        super().__init__(parent)
        self.theme_key = theme_key
        self.setFixedHeight(38)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 10, 0)
        layout.setSpacing(8)

        self.lbl_icon = QLabel("⟳")
        self.lbl_icon.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))

        self.lbl_text = QLabel("Flick Forward")
        self.lbl_text.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))

        self.btn_reject = QPushButton("✕ Reject")
        self.btn_reject.setCursor(Qt.PointingHandCursor)
        self.btn_reject.setFixedHeight(24)
        self.btn_reject.clicked.connect(self.rejectClicked)

        layout.addWidget(self.lbl_icon)
        layout.addWidget(self.lbl_text)
        layout.addWidget(self.btn_reject)

        self.fade_timer = QTimer(self)
        self.fade_timer.setSingleShot(True)
        self.fade_timer.timeout.connect(self.hide)

        self.hide()
        self.apply_theme(theme_key)

    def show_gesture(self, gesture_name: str, action_name: str, is_neural=False):
        t = THEMES.get(self.theme_key, THEMES["walnut"])
        icon_map = {
            "FLICK_FWD": "⟳",
            "FLICK_REV": "⟲",
            "TSPIN": "↻",
            "SINGLE_TAP": "◎"
        }
        icon = icon_map.get(gesture_name, "→")
        self.lbl_icon.setText(icon)
        self.lbl_text.setText(f"{gesture_name}: {action_name}")
        self.btn_reject.show()

        accent_color = "#00F0DC" if is_neural else t['accent']
        self.lbl_icon.setStyleSheet(f"color: {accent_color};")
        self.setStyleSheet(f"""
            GestureBadgeWidget {{
                background-color: rgba(20, 16, 12, 0.94);
                border: 1px solid {accent_color};
                border-radius: 19px;
            }}
            QLabel {{ color: {t['text']}; }}
        """)
        self.adjustSize()
        self.show()
        self.raise_()
        self.fade_timer.start(2500)

    def show_rejection(self):
        self.lbl_icon.setText("✕")
        self.lbl_text.setText("Mis-trigger Rejected (Centroids Rolled Back)")
        self.lbl_icon.setStyleSheet("color: #FF453A;")
        self.btn_reject.hide()
        self.setStyleSheet("""
            GestureBadgeWidget {{
                background-color: rgba(28, 12, 12, 0.96);
                border: 1px solid #FF453A;
                border-radius: 19px;
            }}
            QLabel {{ color: #FFF; }}
        """)
        self.adjustSize()
        self.show()
        self.raise_()
        self.fade_timer.start(2200)

    def apply_theme(self, theme_key: str):
        self.theme_key = theme_key
        t = THEMES.get(theme_key, THEMES["walnut"])
        self.btn_reject.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 12px;
                color: {t['text']};
                padding: 0 8px;
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 69, 58, 0.35);
                border-color: #FF453A;
                color: #FF453A;
            }}
        """)


# =============================================================================
# 7. Photorealistic Optical Rotary Dial & Crown Visualizer
# =============================================================================
class PhotorealisticRotaryDial(QWidget):
    """
    1:1 Photorealistic Hardware Visualizer:
    - Renders omniscroll_neutral.webp as base hardware image
    - Slanted front LED diffuser light polygon + soft optical bloom
    - 48 rotating perspective ticks on the knurled bezel (1:1 with MX8650 optical sensor)
    - Radiant HomePod touch wave ripple on tap
    - Floating Gesture Badge overlay with mis-trigger rejection
    """
    dialTapped = Signal()
    gestureRejectClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.target_angle = 0.0
        self.current_angle = 0.0
        self.mode_color = QColor(0, 122, 255)

        # HomePod touch ripple animation
        self.ripple_radius = 0.0
        self.ripple_alpha = 0.0

        # Embedded Live Gesture Toast Badge
        self.gesture_badge = GestureBadgeWidget(self)
        self.gesture_badge.rejectClicked.connect(lambda: self.gestureRejectClicked.emit())

        # On-demand render loop (runs strictly when rotating or animating ripples)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)

        # Load device base image
        self.device_pixmap = None
        self._load_device_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        bw = min(320, max(220, self.width() - 40))
        bh = 38
        bx = (self.width() - bw) // 2
        by = self.height() - bh - 14
        self.gesture_badge.setGeometry(bx, by, bw, bh)

    def show_gesture(self, gesture_name: str, action_name: str, is_neural=False):
        self.gesture_badge.show_gesture(gesture_name, action_name, is_neural)

    def show_rejection(self):
        self.gesture_badge.show_rejection()

    def _load_device_pixmap(self):
        possible_dirs = [
            getattr(sys, '_MEIPASS', ''),
            os.path.dirname(os.path.abspath(__file__)),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs"),
            r"e:\rouf\hardware-project\OmniScroll\desktop_app\ui",
            r"e:\rouf\hardware-project\OmniScroll\docs"
        ]
        for d in possible_dirs:
            if not d:
                continue
            for fname in ["omniscroll_neutral.webp", "omniscroll_neutral.png"]:
                p = os.path.join(d, fname)
                if os.path.exists(p):
                    px = QPixmap(p)
                    if not px.isNull() and px.width() > 0:
                        self.device_pixmap = px
                        return

    def rotate_delta(self, delta_counts: int):
        self.target_angle += delta_counts * DEG_PER_COUNT
        if not self.timer.isActive():
            self.timer.start(16)

    def set_mode_color(self, hex_color: str):
        c = f"#{hex_color}" if not hex_color.startswith("#") else hex_color
        self.mode_color = QColor(c)
        self.update()

    def trigger_touch_ripple(self):
        self.ripple_radius = 12.0
        self.ripple_alpha = 200.0
        if not self.timer.isActive():
            self.timer.start(16)
        self.update()

    def _on_tick(self):
        needs_update = False
        diff = self.target_angle - self.current_angle
        if abs(diff) > 0.02:
            self.current_angle += diff * 0.28
            needs_update = True
        else:
            self.current_angle = self.target_angle

        if self.ripple_alpha > 2.0:
            self.ripple_radius += 3.0
            self.ripple_alpha *= 0.88
            needs_update = True
        elif self.ripple_radius != 0:
            self.ripple_radius = 0
            self.ripple_alpha = 0
            needs_update = True

        if needs_update:
            self.update()
        else:
            self.timer.stop() # Zero-power rest state when stationary

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w = self.width()
        h = self.height()

        # Fit 1330x1240 aspect ratio
        aspect = 1330.0 / 1240.0
        if w / max(1, h) > aspect:
            target_h = h
            target_w = target_h * aspect
        else:
            target_w = w
            target_h = target_w / aspect

        dx = (w - target_w) / 2.0
        dy = (h - target_h) / 2.0
        scale = target_w / 1330.0

        # 1. Base Hardware Image (Nordic Walnut / Chamfered Aluminum / Acrylic)
        if self.device_pixmap and not self.device_pixmap.isNull():
            target_rect = QRectF(dx, dy, target_w, target_h)
            painter.drawPixmap(target_rect, self.device_pixmap, QRectF(self.device_pixmap.rect()))
        else:
            # Fallback dark background
            painter.setBrush(QBrush(QColor(24, 18, 13)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRectF(dx, dy, target_w, target_h), 18, 18)

        # 2. Slanted Front LED Diffuser Light (Organic handmade slot aperture - ZERO leak, NO streak line)
        r, g, b = self.mode_color.red(), self.mode_color.green(), self.mode_color.blue()

        # Subtle ambient optical bloom hugging the front aperture
        bloom_cx = dx + 890.0 * scale
        bloom_cy = dy + 960.0 * scale
        bloom_grad = QRadialGradient(bloom_cx, bloom_cy, 240.0 * scale)
        bloom_grad.setColorAt(0.0, QColor(r, g, b, 25))
        bloom_grad.setColorAt(0.5, QColor(r, g, b, 8))
        bloom_grad.setColorAt(1.0, QColor(r, g, b, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(bloom_grad)
        painter.drawEllipse(QPointF(bloom_cx, bloom_cy), 240.0 * scale, 120.0 * scale)

        # Handmade Organic Slot Cutout Path (curved perspective matching physical product)
        slot_path = QPainterPath()
        p0 = QPointF(dx + 678.0 * scale, dy + 960.0 * scale)
        slot_path.moveTo(p0)
        # Top curve
        slot_path.cubicTo(
            QPointF(dx + 800.0 * scale, dy + 922.0 * scale),
            QPointF(dx + 960.0 * scale, dy + 892.0 * scale),
            QPointF(dx + 1106.0 * scale, dy + 876.0 * scale)
        )
        # Right rounded cap
        slot_path.cubicTo(
            QPointF(dx + 1114.0 * scale, dy + 895.0 * scale),
            QPointF(dx + 1114.0 * scale, dy + 945.0 * scale),
            QPointF(dx + 1106.0 * scale, dy + 966.0 * scale)
        )
        # Bottom curve
        slot_path.cubicTo(
            QPointF(dx + 960.0 * scale, dy + 1000.0 * scale),
            QPointF(dx + 800.0 * scale, dy + 1030.0 * scale),
            QPointF(dx + 675.0 * scale, dy + 1055.0 * scale)
        )
        # Left rounded cap
        slot_path.cubicTo(
            QPointF(dx + 668.0 * scale, dy + 1035.0 * scale),
            QPointF(dx + 668.0 * scale, dy + 985.0 * scale),
            p0
        )
        slot_path.closeSubpath()

        # Strict clip to physical slot
        painter.save()
        painter.setClipPath(slot_path)

        # Radiant Diffuser fill (natural organic LED illumination, NO artificial line)
        grad_cx = dx + 890.0 * scale
        grad_cy = dy + 960.0 * scale
        diffuser_grad = QRadialGradient(grad_cx, grad_cy, 260.0 * scale)
        diffuser_grad.setColorAt(0.0, QColor(min(255, r + 50), min(255, g + 50), min(255, b + 50), 245))
        diffuser_grad.setColorAt(0.42, QColor(r, g, b, 230))
        diffuser_grad.setColorAt(0.72, QColor(r, g, b, 170))
        diffuser_grad.setColorAt(1.0, QColor(r, g, b, 100))
        painter.setPen(Qt.NoPen)
        painter.setBrush(diffuser_grad)
        painter.drawPath(slot_path)
        painter.restore()

        # 3. Rotating 3D Perspective Ticks (Strictly on silver knurled metal bevel - ZERO spiky needles)
        for i in range(TICK_COUNT):
            is_pip = (i == 0)
            is_thin = (i % 2 != 0)

            if is_pip:
                r_in = 416.0
                r_out = 438.0
                pen = QPen(self.mode_color, 3.0 * scale, Qt.SolidLine, Qt.RoundCap)
            elif is_thin:
                r_in = 422.0
                r_out = 436.0
                pen = QPen(QColor(215, 220, 230, 110), 1.2 * scale, Qt.SolidLine, Qt.RoundCap)
            else:
                r_in = 418.0
                r_out = 438.0
                pen = QPen(QColor(255, 255, 255, 220), 2.0 * scale, Qt.SolidLine, Qt.RoundCap)

            a_deg = (i / TICK_COUNT) * 360.0 + self.current_angle
            x1, y1 = ellipse_xy(DISK_CX, DISK_CY, r_in, r_in * DISK_ASPECT, a_deg, DISK_ROTATION)
            x2, y2 = ellipse_xy(DISK_CX, DISK_CY, r_out, r_out * DISK_ASPECT, a_deg, DISK_ROTATION)

            painter.setPen(pen)
            painter.drawLine(
                QPointF(dx + x1 * scale, dy + y1 * scale),
                QPointF(dx + x2 * scale, dy + y2 * scale)
            )

        # 4. Radiant HomePod Touch Ripple Wave
        if self.ripple_radius > 0:
            touch_cx = dx + 662.0 * scale
            touch_cy = dy + 188.0 * scale
            rx = self.ripple_radius * 2.8 * scale
            ry = self.ripple_radius * 1.16 * scale
            alpha = int(min(255, self.ripple_alpha))

            rip_grad = QRadialGradient(touch_cx, touch_cy, rx)
            rip_grad.setColorAt(0.0, QColor(255, 255, 255, alpha))
            rip_grad.setColorAt(0.35, QColor(r, g, b, int(alpha * 0.75)))
            rip_grad.setColorAt(1.0, QColor(r, g, b, 0))

            painter.setPen(QPen(QColor(r, g, b, alpha), 1.8 * scale))
            painter.setBrush(rip_grad)
            painter.drawEllipse(QPointF(touch_cx, touch_cy), rx, ry)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.trigger_touch_ripple()
            self.dialTapped.emit()
        self._last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if hasattr(self, '_last_mouse_pos') and event.buttons() & Qt.LeftButton:
            delta_y = event.pos().y() - self._last_mouse_pos.y()
            delta_x = event.pos().x() - self._last_mouse_pos.x()
            diff = delta_x - delta_y
            if abs(diff) > 2:
                self.target_angle += diff * 0.8
                self._last_mouse_pos = event.pos()
                self.update()
        super().mouseMoveEvent(event)


# =============================================================================
# 6. Apple Detent Profile Strip (Click, Thud, Tick, Soft, Off)
# =============================================================================
class HapticDetentStrip(QWidget):
    """5-button detent profile selector with Apple micro-tactile glyphs."""
    profileSelected = Signal(int)

    def __init__(self, current_profile=0, parent=None):
        super().__init__(parent)
        self.current_profile = current_profile
        self.buttons = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(6)

        for i, (glyph, name) in enumerate(PROFILES):
            btn = QPushButton(f"{glyph}\n{name}")
            btn.setCheckable(True)
            btn.setChecked(i == current_profile)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(48)
            btn.clicked.connect(lambda checked, idx=i: self._on_btn_clicked(idx))
            self.buttons.append(btn)
            layout.addWidget(btn)

        self.apply_theme("walnut")

    def _on_btn_clicked(self, idx: int):
        self.set_profile(idx)
        self.profileSelected.emit(idx)

    def set_profile(self, idx: int):
        self.current_profile = idx
        for i, b in enumerate(self.buttons):
            b.setChecked(i == idx)

    def apply_theme(self, theme_key: str):
        t = THEMES.get(theme_key, THEMES["walnut"])
        rgb = t.get('accent_rgb', (255, 160, 0))
        for b in self.buttons:
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t['surface']};
                    color: {t['muted']};
                    border: 1px solid {t['border']};
                    border-radius: 10px;
                    font-size: 10px;
                    font-weight: 600;
                    line-height: 14px;
                }}
                QPushButton:hover {{
                    border-color: {t['border_hover']};
                    color: {t['text']};
                }}
                QPushButton:checked {{
                    background-color: rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.16);
                    color: {t['accent']};
                    border: 1.5px solid {t['accent']};
                    font-weight: 700;
                }}
            """)



# =============================================================================
# 7. Apple Control Center Capsule Slider
# =============================================================================
class AppleCapsuleSlider(QWidget):
    """
    Apple Control Center Tactile Capsule Slider:
    - 48px rounded pill with smooth gradient fill
    - Floating tactile pill thumb indicator
    - Left title with icon, right frosted glass value readout
    - Interactive click & horizontal drag
    """
    valueChanged = Signal(int)

    def __init__(self, title: str, icon_str: str, min_val: int, max_val: int, default_val: int, unit="", parent=None):
        super().__init__(parent)
        self.title = title
        self.icon_str = icon_str
        self.min_val = min_val
        self.max_val = max_val
        self.curr_val = default_val
        self.unit = unit
        self.theme_key = "walnut"

        self.setFixedHeight(48)
        self.setCursor(Qt.PointingHandCursor)
        self.dragging = False

    def value(self) -> int:
        return self.curr_val

    def setValue(self, val: int):
        val = max(self.min_val, min(self.max_val, val))
        if val != self.curr_val:
            self.curr_val = val
            self.update()

    def apply_theme(self, theme_key: str):
        self.theme_key = theme_key
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        t = THEMES.get(self.theme_key, THEMES["walnut"])
        w = self.width()
        h = self.height()
        r = h / 2.0

        pct = (self.curr_val - self.min_val) / max(1, (self.max_val - self.min_val))
        pct = max(0.0, min(1.0, pct))

        # 1. Base Pill Container
        base_rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        painter.setBrush(QBrush(QColor(t['surface_raised'])))
        painter.setPen(QPen(QColor(t['border']), 1.0))
        painter.drawRoundedRect(base_rect, r, r)

        # 2. Capsule Fill Track (Warm Accent Gradient)
        fill_w = w * pct
        if fill_w > 4:
            fill_path = QPainterPath()
            fill_path.addRoundedRect(base_rect, r, r)

            painter.save()
            painter.setClipPath(fill_path)

            rgb = t.get('accent_rgb', (255, 160, 0))
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, QColor(rgb[0], rgb[1], rgb[2], 30))
            grad.setColorAt(1.0, QColor(rgb[0], rgb[1], rgb[2], 75))

            painter.setBrush(grad)
            painter.setPen(Qt.NoPen)
            painter.drawRect(QRectF(0, 0, fill_w, h))

            # 3. Apple Tactile Floating Pill Indicator Thumb
            thumb_w = 4.5
            thumb_h = 22.0
            thumb_x = fill_w - thumb_w - 3.0
            thumb_y = (h - thumb_h) / 2.0
            if thumb_x >= 4:
                painter.setBrush(QBrush(QColor(t['accent'])))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(QRectF(thumb_x, thumb_y, thumb_w, thumb_h), 2.25, 2.25)

            painter.restore()

        # 4. Left Content: Clean Vector Icon + Title
        icon_str = str(self.icon_str).lower()
        if icon_str in ("brightness", "sun", "bri", "☼"):
            painter.save()
            painter.setPen(QPen(QColor(t['accent']), 1.6))
            painter.setBrush(Qt.NoBrush)
            cx, cy = 26.0, h / 2.0
            painter.drawEllipse(QPointF(cx, cy), 3.5, 3.5)
            for deg in (0, 45, 90, 135, 180, 225, 270, 315):
                rad = math.radians(deg)
                x1 = cx + 5.5 * math.cos(rad)
                y1 = cy + 5.5 * math.sin(rad)
                x2 = cx + 7.5 * math.cos(rad)
                y2 = cy + 7.5 * math.sin(rad)
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            painter.restore()
            title_x = 42
        elif icon_str in ("idle", "moon", "sleep", "☾"):
            painter.save()
            painter.setPen(QPen(QColor(t['accent']), 1.5))
            painter.setBrush(Qt.NoBrush)
            path = QPainterPath()
            path.moveTo(28, h / 2.0 - 6)
            path.cubicTo(22, h / 2.0 - 6, 20, h / 2.0 + 6, 28, h / 2.0 + 6)
            path.cubicTo(24, h / 2.0 + 4, 24, h / 2.0 - 4, 28, h / 2.0 - 6)
            painter.drawPath(path)
            painter.restore()
            title_x = 42
        elif icon_str in ("touch", "sens", "thr", "📶"):
            painter.save()
            painter.setPen(QPen(QColor(t['accent']), 1.5))
            painter.setBrush(QBrush(QColor(t['accent'])))
            cx, cy = 26.0, h / 2.0
            painter.drawEllipse(QPointF(cx, cy), 2.0, 2.0)
            painter.setBrush(Qt.NoBrush)
            painter.drawArc(QRectF(cx - 5, cy - 5, 10, 10), -45 * 16, 90 * 16)
            painter.drawArc(QRectF(cx - 5, cy - 5, 10, 10), 135 * 16, 90 * 16)
            painter.drawArc(QRectF(cx - 8, cy - 8, 16, 16), -45 * 16, 90 * 16)
            painter.drawArc(QRectF(cx - 8, cy - 8, 16, 16), 135 * 16, 90 * 16)
            painter.restore()
            title_x = 42
        elif self.icon_str in ("R", "G", "B"):
            col_map = {"R": "#FF453A", "G": "#32D74B", "B": "#0A84FF"}
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(col_map.get(self.icon_str, t['accent']))))
            painter.drawEllipse(QPointF(25.0, h / 2.0), 3.5, 3.5)
            painter.restore()
            title_x = 38
        else:
            painter.save()
            painter.setFont(QFont("Segoe UI", 9.5))
            painter.setPen(QPen(QColor(t['accent'])))
            painter.drawText(QRectF(16, 0, 20, h), Qt.AlignCenter, str(self.icon_str))
            painter.restore()
            title_x = 40

        painter.setPen(QPen(QColor(t['text'])))
        painter.setFont(QFont("Segoe UI", 9.5, QFont.Weight.DemiBold))
        painter.drawText(QRectF(title_x, 0, w - title_x - 70, h), Qt.AlignLeft | Qt.AlignVCenter, self.title)

        # 5. Right Value Badge (Frosted glass pill)
        val_str = f"{self.curr_val}{self.unit}"
        badge_w = 48
        badge_h = 24
        badge_x = w - badge_w - 14
        badge_y = (h - badge_h) / 2.0
        badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)

        painter.setBrush(QBrush(QColor(0, 0, 0, 45)))
        painter.setPen(QPen(QColor(t['border']), 1.0))
        painter.drawRoundedRect(badge_rect, 7, 7)

        painter.setPen(QPen(QColor(t['accent'])))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(badge_rect, Qt.AlignCenter, val_str)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self._update_from_x(event.position().x())

    def mouseMoveEvent(self, event):
        if self.dragging:
            self._update_from_x(event.position().x())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False

    def wheelEvent(self, event):
        step = 1 if (self.max_val - self.min_val) <= 120 else 5
        delta = step if event.angleDelta().y() > 0 else -step
        new_val = max(self.min_val, min(self.max_val, self.curr_val + delta))
        if new_val != self.curr_val:
            self.curr_val = new_val
            self.update()
            self.valueChanged.emit(new_val)

    def _update_from_x(self, x: float):
        w = max(1, self.width())
        pct = max(0.0, min(1.0, x / w))
        new_val = int(round(self.min_val + pct * (self.max_val - self.min_val)))
        if new_val != self.curr_val:
            self.curr_val = new_val
            self.update()
            self.valueChanged.emit(new_val)


# =============================================================================
# 8. Apple Capsule Dropdown Row (Gestures & Shortcuts)
# =============================================================================
class AppleCapsulePicker(QFrame):
    """Gesture shortcut row with round icon pill badge and sleek dropdown."""
    actionSelected = Signal(int)

    def __init__(self, title: str, icon_symbol="→", default_action=0, items=None, parent=None):
        if isinstance(items, QWidget) and parent is None:
            parent = items
            items = None
        super().__init__(parent)
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        # Round Icon Pill Badge
        self.lbl_icon = QLabel(icon_symbol)
        self.lbl_icon.setFixedSize(28, 28)
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        self.lbl_icon.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))

        # Title
        self.lbl_title = QLabel(title)
        self.lbl_title.setFont(QFont("Segoe UI", 9.5, QFont.Weight.DemiBold))

        # Dropdown Combobox
        self.combo = QComboBox()
        self.combo.setFixedHeight(30)
        self.combo.setCursor(Qt.PointingHandCursor)

        item_list = items if items is not None else ACTIONS
        for code, name in item_list:
            self.combo.addItem(name, code)

        self.set_action(default_action)
        self.combo.currentIndexChanged.connect(self._on_change)

        layout.addWidget(self.lbl_icon)
        layout.addWidget(self.lbl_title)
        layout.addStretch()
        layout.addWidget(self.combo)

        self.apply_theme("walnut")

    def _on_change(self, idx: int):
        code = self.combo.currentData()
        self.actionSelected.emit(code)

    def set_action(self, action_code: int):
        idx = self.combo.findData(action_code)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)

    def current_action(self) -> int:
        data = self.combo.currentData()
        return data if data is not None else 0

    def apply_theme(self, theme_key: str):
        t = THEMES.get(theme_key, THEMES["walnut"])
        rgb = t.get('accent_rgb', (255, 160, 0))
        self.setStyleSheet(f"""
            AppleCapsulePicker {{
                background-color: {t['surface_raised']};
                border: 1px solid {t['border']};
                border-radius: 24px;
            }}
        """)
        self.lbl_icon.setStyleSheet(f"""
            background-color: rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.15);
            color: {t['accent']};
            border-radius: 14px;
        """)

        self.lbl_title.setStyleSheet(f"color: {t['text']};")
        self.combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {t['surface']};
                border: 1px solid {t['border']};
                border-radius: 10px;
                padding: 4px 10px;
                color: {t['text']};
                font-size: 11px;
                font-weight: 600;
                min-width: 140px;
            }}
            QComboBox:hover {{
                border-color: {t['accent']};
            }}
            QComboBox QAbstractItemView {{
                background-color: {t['surface_raised']};
                border: 1px solid {t['border_hover']};
                border-radius: 10px;
                color: {t['text']};
                selection-background-color: {t['accent']}33;
                selection-color: {t['accent']};
                padding: 4px;
            }}
        """)


# =============================================================================
# 9. Apple iOS-Style Toggle Switch
# =============================================================================
class AppleToggleSwitch(QWidget):
    """iOS-style smooth tactile toggle switch (36x20px)."""
    toggled = Signal(bool)

    def __init__(self, checked=True, parent=None, theme_key="walnut"):
        super().__init__(parent)
        self.checked = checked
        self.theme_key = theme_key
        self.setFixedSize(36, 20)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self) -> bool:
        return self.checked

    def setChecked(self, checked: bool):
        if self.checked != checked:
            self.checked = checked
            self.update()
            self.toggled.emit(checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self.checked)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        t = THEMES.get(self.theme_key, THEMES["walnut"])
        w = self.width()
        h = self.height()
        r = h / 2.0

        # Track
        if self.checked:
            painter.setBrush(QBrush(QColor(t['accent'])))
            painter.setPen(Qt.NoPen)
        else:
            painter.setBrush(QBrush(QColor(44, 44, 46)))
            painter.setPen(QPen(QColor(60, 60, 65), 1.0))

        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), r, r)

        # Thumb
        thumb_diam = 16.0
        thumb_x = w - thumb_diam - 2.0 if self.checked else 2.0
        thumb_y = 2.0
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(thumb_x, thumb_y, thumb_diam, thumb_diam))

    def apply_theme(self, theme_key: str):
        self.theme_key = theme_key
        self.update()


# =============================================================================
# 10. Real-Time Wi-Fi Latency & Ping Performance Benchmark Widget
# =============================================================================
class WifiLatencyBenchmarkWidget(QFrame):
    """
    Real-Time Wi-Fi Latency & Ping Performance Benchmark:
    - Measures high-precision round-trip time (RTT) over UDP port 4211
    - Displays Min, Avg, Max latency and Jitter
    - Status badge: Ultra-Low Latency (<3ms)
    """
    runPingRequested = Signal()

    def __init__(self, parent=None, theme_key="walnut"):
        super().__init__(parent)
        self.theme_key = theme_key
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header Row
        hdr = QHBoxLayout()
        self.lbl_title = QLabel("WI-FI LATENCY BENCHMARK")
        self.lbl_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))

        self.badge_status = QLabel("Ultra-Low (<3ms)")
        self.badge_status.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.badge_status.setStyleSheet("color: #30D158;")

        hdr.addWidget(self.lbl_title)
        hdr.addStretch()
        hdr.addWidget(self.badge_status)
        layout.addLayout(hdr)

        # Metrics Row
        m_row = QHBoxLayout()
        self.lbl_rtt_main = QLabel("1.8 ms")
        self.lbl_rtt_main.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))

        stats_box = QVBoxLayout()
        stats_box.setSpacing(1)
        self.lbl_sub_stats = QLabel("Avg: 1.8ms • Min: 1.2ms • Jitter: 0.4ms")
        self.lbl_sub_stats.setFont(QFont("Segoe UI", 8))
        self.lbl_sub_rating = QLabel("Sub-frame delay (faster than 60Hz/120Hz refresh)")
        self.lbl_sub_rating.setFont(QFont("Segoe UI", 8))

        stats_box.addWidget(self.lbl_sub_stats)
        stats_box.addWidget(self.lbl_sub_rating)

        m_row.addWidget(self.lbl_rtt_main)
        m_row.addSpacing(10)
        m_row.addLayout(stats_box)
        m_row.addStretch()

        self.btn_test = QPushButton("Test Ping")
        self.btn_test.setFixedHeight(30)
        self.btn_test.setCursor(Qt.PointingHandCursor)
        self.btn_test.clicked.connect(self.runPingRequested)
        m_row.addWidget(self.btn_test)

        layout.addLayout(m_row)
        self.apply_theme(theme_key)

    def set_benchmark_results(self, avg_ms: float, min_ms: float, max_ms: float, jitter_ms: float):
        self.lbl_rtt_main.setText(f"{avg_ms:.1f} ms")
        self.lbl_sub_stats.setText(f"Avg: {avg_ms:.1f}ms • Min: {min_ms:.1f}ms • Jitter: {jitter_ms:.1f}ms")

        if avg_ms < 3.0:
            self.badge_status.setText("Ultra-Low (<3ms)")
            self.badge_status.setStyleSheet("color: #30D158;")
            self.lbl_sub_rating.setText("Sub-frame delay (faster than 60Hz/120Hz refresh)")
        elif avg_ms < 10.0:
            self.badge_status.setText("Excellent (<10ms)")
            self.badge_status.setStyleSheet("color: #00D4FF;")
            self.lbl_sub_rating.setText("Fluid & responsive (< 1 display frame)")
        else:
            self.badge_status.setText("Elevated (>10ms)")
            self.badge_status.setStyleSheet("color: #FF9500;")
            self.lbl_sub_rating.setText("Check router 2.4 GHz channel interference")

    def apply_theme(self, theme_key: str):
        self.theme_key = theme_key
        t = THEMES.get(theme_key, THEMES["walnut"])
        self.setStyleSheet(f"""
            WifiLatencyBenchmarkWidget {{
                background-color: {t['surface']};
                border: 1px solid {t['border']};
                border-radius: 12px;
            }}
        """)
        self.lbl_title.setStyleSheet(f"color: {t['muted']}; letter-spacing: 0.8px;")
        self.lbl_rtt_main.setStyleSheet(f"color: {t['accent']};")
        self.lbl_sub_stats.setStyleSheet(f"color: {t['text']}; font-weight: 600;")
        self.lbl_sub_rating.setStyleSheet(f"color: {t['muted']};")

        self.btn_test.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['surface_raised']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {t['accent']};
                color: {t['accent']};
            }}
        """)


# =============================================================================
# 11. Wi-Fi & Wireless Bridge Studio Container (Apple Pro HIG Glassmorphism)
# =============================================================================
class WifiStudioContainer(GlassPanel):
    """
    Unified native container for 2.4 GHz Wi-Fi credentials and wireless bridge status.
    Features subtle glassmorphic green ambient hue when connected wirelessly,
    masked credentials display, single full-width 'Update Password' button, and
    clear wired-only guidance.
    """
    scanRequested = Signal()
    provisionRequested = Signal(str, str)
    startupToggled = Signal(bool)
    pingRequested = Signal()

    def __init__(self, parent=None, theme_key="walnut"):
        super().__init__(parent, theme_key)
        self.setObjectName("WifiStudioContainer")
        self.current_theme = theme_key
        self.is_connected = False
        self.is_wired = False
        self.saved_ssid = ""
        self.wifi_ip = ""
        self.wifi_rssi = 0
        self.bench_widget = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Header: Title + Subtle Connection Tag
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self.lbl_title = QLabel("Wireless Connection")
        self.lbl_title.setFont(QFont("Segoe UI", 10.5, QFont.Weight.Bold))

        self.lbl_subtitle = QLabel("")
        self.lbl_subtitle.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        self.lbl_subtitle.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header.addWidget(self.lbl_title)
        header.addStretch()
        header.addWidget(self.lbl_subtitle)
        layout.addLayout(header)

        # Scan & Dropdown Row
        scan_row = QHBoxLayout()
        scan_row.setContentsMargins(0, 0, 0, 0)
        scan_row.setSpacing(8)
        self.combo_networks = QComboBox()
        self.combo_networks.setFixedHeight(34)
        self.combo_networks.setCursor(Qt.PointingHandCursor)
        self.combo_networks.addItem("Select Wi-Fi Network (click Scan)...", "")
        self.combo_networks.currentIndexChanged.connect(self._on_network_selected)

        self.btn_scan = QPushButton("Scan")
        self.btn_scan.setFixedSize(65, 34)
        self.btn_scan.setCursor(Qt.PointingHandCursor)
        self.btn_scan.clicked.connect(self.scanRequested)

        scan_row.addWidget(self.combo_networks, 1)
        scan_row.addWidget(self.btn_scan)
        layout.addLayout(scan_row)

        # Password input row
        pwd_row = QHBoxLayout()
        pwd_row.setContentsMargins(0, 0, 0, 0)
        pwd_row.setSpacing(8)
        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.Password)
        self.txt_pass.setPlaceholderText("Wi-Fi Password")
        self.txt_pass.setFixedHeight(34)

        self.btn_eye = QPushButton("Show")
        self.btn_eye.setFixedSize(65, 34)
        self.btn_eye.setCursor(Qt.PointingHandCursor)
        self.btn_eye.clicked.connect(self._toggle_eye)

        pwd_row.addWidget(self.txt_pass, 1)
        pwd_row.addWidget(self.btn_eye)
        layout.addLayout(pwd_row)

        # Single Full-Width "Update Password" Button
        self.btn_update_pass = QPushButton("Update Password")
        self.btn_update_pass.setFixedHeight(36)
        self.btn_update_pass.setCursor(Qt.PointingHandCursor)
        self.btn_update_pass.clicked.connect(self._on_update_password)
        layout.addWidget(self.btn_update_pass)

        # Dynamic Notification & Wire-Only Helper (only displayed when triggered)
        self.lbl_wire_note = QLabel("")
        self.lbl_wire_note.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Medium))
        self.lbl_wire_note.setAlignment(Qt.AlignCenter)
        self.lbl_wire_note.setFixedHeight(18)
        layout.addWidget(self.lbl_wire_note)

        self.apply_theme(theme_key)

    def _toggle_eye(self):
        if self.txt_pass.echoMode() == QLineEdit.Password:
            self.txt_pass.setEchoMode(QLineEdit.Normal)
            self.btn_eye.setText("Hide")
        else:
            self.txt_pass.setEchoMode(QLineEdit.Password)
            self.btn_eye.setText("Show")

    def _on_network_selected(self, index: int):
        if index < 0:
            return
        ssid = self.combo_networks.itemData(index)
        if not ssid:
            return
        if self.saved_ssid and ssid == self.saved_ssid:
            self.txt_pass.setText("••••••••")
            self.txt_pass.setPlaceholderText("Wi-Fi Password (Saved)")
        else:
            self.txt_pass.clear()
            self.txt_pass.setPlaceholderText(f"Password for {ssid}")
            self.txt_pass.setFocus()

    def set_saved_credentials(self, ssid: str):
        if not ssid:
            return
        self.saved_ssid = ssid
        self.combo_networks.blockSignals(True)
        found = False
        for i in range(self.combo_networks.count()):
            if self.combo_networks.itemData(i) == ssid or self.combo_networks.itemText(i) == ssid:
                self.combo_networks.setCurrentIndex(i)
                found = True
                break
        if not found:
            self.combo_networks.insertItem(0, f"{ssid} (Saved)", ssid)
            self.combo_networks.setCurrentIndex(0)
        self.combo_networks.blockSignals(False)

        self.txt_pass.setText("••••••••")
        self.txt_pass.setPlaceholderText("Wi-Fi Password (Saved)")

    def set_wired_status(self, is_wired: bool):
        self.is_wired = is_wired
        self._clear_wire_note()

    def _clear_wire_note(self):
        self.lbl_wire_note.setText("")

    def _on_update_password(self):
        ssid = self.combo_networks.currentData()
        if not ssid:
            ssid = self.combo_networks.currentText().strip()
            if " (" in ssid:
                ssid = ssid.split(" (")[0].strip()

        pwd = self.txt_pass.text().strip()

        # Check if connected via wire - only show error if user attempts to update without wire
        if not self.is_wired:
            self.btn_update_pass.setText("⚠️ Connect USB cable first")
            self.lbl_wire_note.setText("⚠️ Connect USB cable first to update password")
            self.lbl_wire_note.setStyleSheet("color: #FF9F0A; font-weight: 600; font-size: 11px;")
            QTimer.singleShot(3500, self._reset_update_button)
            return

        if not ssid or "Select" in ssid:
            self.lbl_wire_note.setText("⚠️ Please select a Wi-Fi network first")
            self.lbl_wire_note.setStyleSheet("color: #FF9F0A; font-weight: 600; font-size: 11px;")
            QTimer.singleShot(3000, self._clear_wire_note)
            return

        if pwd == "••••••••":
            self.lbl_wire_note.setText("⚠️ Enter new password in the field above to update")
            self.lbl_wire_note.setStyleSheet("color: #FF9F0A; font-weight: 600; font-size: 11px;")
            self.txt_pass.setFocus()
            self.txt_pass.selectAll()
            QTimer.singleShot(3500, self._clear_wire_note)
            return

        self.btn_update_pass.setText("⏳ Updating Password...")
        self.btn_update_pass.setEnabled(False)
        self.lbl_wire_note.setText("Writing credentials to device NVS flash...")
        self.lbl_wire_note.setStyleSheet("color: #8E8E93; font-weight: 500; font-size: 11px;")
        self.provisionRequested.emit(ssid, pwd)

    def on_provision_success(self, ssid: str):
        self.btn_update_pass.setEnabled(True)
        self.btn_update_pass.setText("✓ Password Updated!")
        self.set_saved_credentials(ssid)
        self.lbl_wire_note.setText(f"✓ Network '{ssid}' stored securely in OmniScroll")
        self.lbl_wire_note.setStyleSheet("color: #30D158; font-weight: 600; font-size: 11px;")
        QTimer.singleShot(3500, self._reset_update_button)

    def on_provision_error(self, err_msg: str):
        self.btn_update_pass.setEnabled(True)
        self.btn_update_pass.setText("Update Password")
        self.lbl_wire_note.setText(f"⚠️ {err_msg}")
        self.lbl_wire_note.setStyleSheet("color: #FF453A; font-weight: 600; font-size: 11px;")
        QTimer.singleShot(4000, self._clear_wire_note)

    def _reset_update_button(self):
        self.btn_update_pass.setText("Update Password")
        self._clear_wire_note()

    def populate_networks(self, networks: list):
        self.combo_networks.blockSignals(True)
        self.combo_networks.clear()
        if self.saved_ssid:
            self.combo_networks.addItem(f"{self.saved_ssid} (Saved)", self.saved_ssid)
        self.combo_networks.addItem(f"Available Wi-Fi ({len(networks)} networks)...", "")
        for n in networks:
            ssid = n.get("ssid", "")
            if ssid == self.saved_ssid:
                continue
            sig = n.get("signal", 0)
            compat = n.get("compatible", True)
            tag = "2.4 GHz" if compat else "5 GHz"
            label = f"{ssid} ({sig}% • {tag})"
            self.combo_networks.addItem(label, ssid)
        self.combo_networks.setCurrentIndex(0)
        self.combo_networks.blockSignals(False)
        self._on_network_selected(0)

    def set_wifi_status(self, connected: bool, ip: str = "", rssi: int = 0, ssid: str = ""):
        self.is_connected = connected
        if ip: self.wifi_ip = ip
        if rssi: self.wifi_rssi = rssi
        if ssid: self.set_saved_credentials(ssid)
        self._apply_glassmorphic_feedback()

    def _apply_glassmorphic_feedback(self):
        t = THEMES.get(self.current_theme, THEMES["walnut"])
        if self.is_connected:
            # Subtle glassmorphic green ambient hue when connected wirelessly
            self.setStyleSheet(f"""
                #WifiStudioContainer {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(48, 209, 88, 0.08),
                        stop:0.4 rgba(48, 209, 88, 0.035),
                        stop:1 rgba(48, 209, 88, 0.065));
                    border: 1px solid rgba(48, 209, 88, 0.38);
                    border-radius: 18px;
                }}
            """)
            display_name = self.saved_ssid or "Wi-Fi"
            self.lbl_subtitle.setText(f"Connected to {display_name}")
            self.lbl_subtitle.setStyleSheet("color: #30D158; font-weight: 600; font-size: 11px;")
        else:
            # Standard theme card style when disconnected
            self.setStyleSheet(f"""
                #WifiStudioContainer {{
                    background-color: {t['card_bg']};
                    border: 1px solid {t['border']};
                    border-radius: 18px;
                }}
            """)
            self.lbl_subtitle.setText("")

    def apply_theme(self, theme_key: str):
        super().apply_theme(theme_key)
        self.current_theme = theme_key
        t = THEMES.get(theme_key, THEMES["walnut"])
        self.lbl_title.setStyleSheet(f"color: {t['text']};")
        self.set_wired_status(self.is_wired)
        self._apply_glassmorphic_feedback()

        self.combo_networks.setStyleSheet(f"""
            QComboBox {{
                background-color: {t['surface']};
                border: 1px solid {t['border']};
                border-radius: 10px;
                padding: 0 10px;
                color: {t['text']};
                font-size: 11.5px;
                font-weight: 600;
            }}
            QComboBox:hover {{ border-color: {t['accent']}; }}
        """)

        self.btn_scan.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['surface']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {t['accent']};
                color: {t['accent']};
            }}
        """)

        self.txt_pass.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t['surface']};
                border: 1px solid {t['border']};
                border-radius: 10px;
                padding: 0 10px;
                color: {t['text']};
                font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {t['accent']}; }}
        """)

        self.btn_eye.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['surface']};
                color: {t['muted']};
                border: 1px solid {t['border']};
                border-radius: 10px;
            }}
            QPushButton:hover {{ color: {t['text']}; }}
        """)

        self.btn_update_pass.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['accent']};
                color: {t['accent_text']};
                border: none;
                border-radius: 10px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{ filter: brightness(1.12); }}
            QPushButton:disabled {{
                background-color: {t['surface']};
                color: {t['muted']};
            }}
        """)


# =============================================================================
# 12. Apple Pro HIG Color Picker Dialog
# =============================================================================
class AppleColorModal(QDialog):
    """
    Apple Pro HIG Color Picker Dialog:
    - Replaces native Windows QColorDialog with pixel-perfect Apple aesthetic
    - 12 Curated Apple Watch / macOS Palette Swatches
    - Direct Hex input (#RRGGBB)
    - Real-time preview chip
    - Cancel / Apply buttons
    """
    colorChosen = Signal(str)

    PALETTE = [
        ("007AFF", "Azure"),
        ("30D158", "Emerald"),
        ("FF2D55", "Rose"),
        ("FFA000", "Amber MagSafe"),
        ("00C2A8", "Mint"),
        ("FFD60A", "Sunshine"),
        ("BF5AF2", "Purple"),
        ("FF453A", "Crimson"),
        ("00D4FF", "Obsidian"),
        ("5E5CE6", "Indigo"),
        ("FF9F0A", "Tangerine"),
        ("FFFFFF", "Pure White")
    ]

    def __init__(self, initial_hex="007AFF", parent=None, theme_key="walnut"):
        super().__init__(parent)
        self.setWindowTitle("Select Mode LED Color")
        self.setFixedSize(360, 340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.current_hex = initial_hex.replace("#", "").upper()
        self.theme_key = theme_key

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # Title
        self.lbl_title = QLabel("Select Mode LED Color")
        self.lbl_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(self.lbl_title)

        # Palette Grid
        palette_lbl = QLabel("APPLE HIG COLOR PALETTE")
        palette_lbl.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Bold))
        layout.addWidget(palette_lbl)

        grid = QGridLayout()
        grid.setSpacing(8)
        self.swatch_btns = []

        for i, (hex_code, name) in enumerate(self.PALETTE):
            btn = QPushButton()
            btn.setFixedSize(36, 36)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(f"{name} (#{hex_code})")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #{hex_code};
                    border: 2px solid rgba(255, 255, 255, 0.35);
                    border-radius: 18px;
                }}
                QPushButton:hover {{
                    border-color: #FFFFFF;
                }}
            """)
            btn.clicked.connect(lambda _, h=hex_code: self._select_palette(h))
            row = i // 6
            col = i % 6
            grid.addWidget(btn, row, col)
            self.swatch_btns.append(btn)

        layout.addLayout(grid)

        # Live Preview & Hex Input Row
        preview_box = QHBoxLayout()
        preview_box.setSpacing(10)

        self.preview_chip = QLabel()
        self.preview_chip.setFixedSize(34, 34)
        self._update_chip()

        self.txt_hex = QLineEdit(f"#{self.current_hex}")
        self.txt_hex.setFixedHeight(34)
        self.txt_hex.setMaxLength(7)
        self.txt_hex.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        self.txt_hex.textChanged.connect(self._on_hex_text_changed)

        preview_box.addWidget(self.preview_chip)
        preview_box.addWidget(self.txt_hex)
        layout.addLayout(preview_box)

        layout.addStretch()

        # Action Buttons
        act_box = QHBoxLayout()
        act_box.setSpacing(10)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(34)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_apply = QPushButton("Apply Color")
        self.btn_apply.setFixedHeight(34)
        self.btn_apply.setCursor(Qt.PointingHandCursor)
        self.btn_apply.clicked.connect(self._apply)

        act_box.addWidget(self.btn_cancel)
        act_box.addWidget(self.btn_apply)
        layout.addLayout(act_box)

        self._apply_theme()

    def _select_palette(self, hex_code: str):
        self.current_hex = hex_code.upper()
        self.txt_hex.setText(f"#{self.current_hex}")
        self._update_chip()

    def _on_hex_text_changed(self, text: str):
        clean = text.replace("#", "").strip()
        if len(clean) == 6:
            self.current_hex = clean.upper()
            self._update_chip()

    def _update_chip(self):
        self.preview_chip.setStyleSheet(f"""
            background-color: #{self.current_hex};
            border: 2px solid rgba(255, 255, 255, 0.5);
            border-radius: 17px;
        """)

    def _apply(self):
        self.colorChosen.emit(self.current_hex)
        self.accept()

    def _apply_theme(self):
        t = THEMES.get(self.theme_key, THEMES["walnut"])
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {t['surface']};
                color: {t['text']};
            }}
            QLabel {{
                color: {t['text']};
            }}
            QLineEdit {{
                background-color: {t['surface_raised']};
                border: 1px solid {t['border']};
                border-radius: 10px;
                color: {t['text']};
                padding: 0 10px;
            }}
            QLineEdit:focus {{
                border-color: {t['accent']};
            }}
            QPushButton {{
                background-color: {t['surface_raised']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 10px;
                font-weight: 600;
            }}
        """)
        self.btn_apply.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['accent']};
                color: {t['accent_text']};
                border: none;
                border-radius: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                filter: brightness(1.1);
            }}
        """)


# =============================================================================
# 13. Native Mode Studio Card (8-card grid component matching Web UI)
# =============================================================================
class NativeModeCard(QFrame):
    """
    Mode studio card with:
    - Glowing LED color swatch circle
    - Mode name + icon + description
    - iOS tactile toggle switch
    - Bottom detent dropdown + Invert button
    - Active mode glowing border
    """
    cardClicked    = Signal(int)
    enabledToggled = Signal(int, bool)
    colorChanged   = Signal(int, str)
    hapticChanged  = Signal(int, int)
    invertToggled  = Signal(int, bool)

    def __init__(self, mode_idx: int, name: str, desc: str, color_hex: str,
                 enabled=True, haptic_idx=0, inverted=False, parent=None, theme_key="walnut"):
        super().__init__(parent)
        self.mode_idx = mode_idx
        self.name = name
        self.desc = desc
        self.color_hex = color_hex
        self.enabled = enabled
        self.haptic_idx = haptic_idx
        self.inverted = inverted
        self.is_active = False
        self.theme_key = theme_key

        self.setFixedHeight(120)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header Row: Swatch + Title/Desc + AppleToggleSwitch
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.btn_swatch = QPushButton()
        self.btn_swatch.setFixedSize(16, 16)
        self.btn_swatch.setCursor(Qt.PointingHandCursor)
        self.btn_swatch.clicked.connect(self._on_swatch_clicked)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        icon_char = MODE_ICONS.get(name, "↕")
        self.lbl_name = QLabel(f"{icon_char}  {name}")
        self.lbl_name.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))

        self.lbl_desc = QLabel(desc)
        self.lbl_desc.setFont(QFont("Segoe UI", 8.5))
        title_vbox.addWidget(self.lbl_name)
        title_vbox.addWidget(self.lbl_desc)

        self.toggle = AppleToggleSwitch(checked=enabled, parent=self, theme_key=theme_key)
        self.toggle.toggled.connect(self._on_toggle_changed)

        top_row.addWidget(self.btn_swatch)
        top_row.addLayout(title_vbox)
        top_row.addStretch()
        top_row.addWidget(self.toggle)
        layout.addLayout(top_row)

        layout.addStretch()

        # Controls Row: Detent picker + Invert button
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)

        self.combo_haptic = QComboBox()
        self.combo_haptic.setFixedHeight(26)
        for i, (glyph, p) in enumerate(PROFILES):
            self.combo_haptic.addItem(f"{glyph} {p}", i)
        self.combo_haptic.setCurrentIndex(haptic_idx)
        self.combo_haptic.currentIndexChanged.connect(lambda idx: self.hapticChanged.emit(self.mode_idx, idx))

        self.btn_inv = QPushButton("⇄ Inverted" if inverted else "⇄ Standard")
        self.btn_inv.setFixedHeight(26)
        self.btn_inv.setCheckable(True)
        self.btn_inv.setChecked(inverted)
        self.btn_inv.clicked.connect(self._on_invert_clicked)

        ctrl_row.addWidget(self.combo_haptic, 1)
        ctrl_row.addWidget(self.btn_inv, 1)
        layout.addLayout(ctrl_row)

        self.apply_theme(theme_key)

    def _on_toggle_changed(self, chk: bool):
        self.enabled = chk
        self.enabledToggled.emit(self.mode_idx, chk)
        self.apply_theme(self.theme_key)

    def _on_swatch_clicked(self):
        modal = AppleColorModal(self.color_hex, self, self.theme_key)
        modal.colorChosen.connect(self._on_color_chosen)
        modal.exec()

    def _on_color_chosen(self, hex_str: str):
        self.color_hex = hex_str
        self.colorChanged.emit(self.mode_idx, hex_str)
        self.apply_theme(self.theme_key)

    def _on_invert_clicked(self):
        self.inverted = not self.inverted
        self.btn_inv.setText("⇄ Inverted" if self.inverted else "⇄ Standard")
        self.btn_inv.setChecked(self.inverted)
        self.invertToggled.emit(self.mode_idx, self.inverted)

    def update_data(self, data: dict):
        if "c" in data:
            self.color_hex = data["c"]
        if "en" in data:
            self.enabled = bool(data["en"])
            self.toggle.blockSignals(True)
            self.toggle.setChecked(self.enabled)
            self.toggle.blockSignals(False)
        if "hp" in data:
            self.haptic_idx = int(data["hp"])
            idx = self.combo_haptic.findData(self.haptic_idx)
            if idx >= 0:
                self.combo_haptic.blockSignals(True)
                self.combo_haptic.setCurrentIndex(idx)
                self.combo_haptic.blockSignals(False)
        if "inv" in data:
            self.inverted = bool(data["inv"])
            self.btn_inv.blockSignals(True)
            self.btn_inv.setText("⇄ Inverted" if self.inverted else "⇄ Standard")
            self.btn_inv.setChecked(self.inverted)
            self.btn_inv.blockSignals(False)
        self.apply_theme(self.theme_key)

    def set_active(self, active: bool):
        self.is_active = active
        self.apply_theme(self.theme_key)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.cardClicked.emit(self.mode_idx)
        super().mousePressEvent(event)

    def apply_theme(self, theme_key: str):
        self.theme_key = theme_key
        t = THEMES.get(theme_key, THEMES["walnut"])
        c = f"#{self.color_hex}" if not self.color_hex.startswith("#") else self.color_hex

        # Swatch button
        self.btn_swatch.setStyleSheet(f"""
            QPushButton {{
                background-color: {c};
                border: 2px solid rgba(255, 255, 255, 0.4);
                border-radius: 8px;
            }}
        """)

        self.lbl_name.setStyleSheet(f"color: {t['text']};")
        self.lbl_desc.setStyleSheet(f"color: {t['muted']};")

        # Card outline & opacity
        opacity_style = "1.0" if self.enabled else "0.38"
        border_style = f"1.5px solid {t['accent']}" if self.is_active else f"1px solid {t['border']}"
        bg_style = t['surface_hover'] if self.is_active else t['surface_raised']

        self.setStyleSheet(f"""
            NativeModeCard {{
                background-color: {bg_style};
                border: {border_style};
                border-radius: 14px;
                opacity: {opacity_style};
            }}
            NativeModeCard:hover {{
                border-color: {t['border_hover']};
            }}
            QComboBox {{
                background-color: {t['surface']};
                border: 1px solid {t['border']};
                border-radius: 6px;
                padding: 2px 6px;
                color: {t['text']};
                font-size: 11px;
            }}
            QPushButton {{
                background-color: {t['surface']};
                border: 1px solid {t['border']};
                border-radius: 6px;
                padding: 2px 6px;
                color: {t['text_secondary']};
                font-size: 11px;
            }}
            QPushButton:hover {{
                border-color: {t['accent']};
                color: {t['accent']};
            }}
        """)
        self.toggle.apply_theme(theme_key)


# =============================================================================
# 12. TinyOL Neural Engine Card (Apple Neural Engine Studio)
# =============================================================================
class TinyOLNeuralCard(GlassPanel):
    """Real-time neural engine telemetry displaying user personal flick centroids."""
    rejectClicked = Signal()
    resetClicked  = Signal()

    def __init__(self, parent=None, theme_key="walnut"):
        super().__init__(parent, theme_key)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        self.lbl_title = QLabel("TinyOL Neural Engine")
        self.lbl_title.setFont(QFont("Segoe UI", 10.5, QFont.Weight.Bold))

        self.lbl_status = QLabel("●  Learning Active")
        self.lbl_status.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_status.setStyleSheet("color: #00F0DC;")

        header.addWidget(self.lbl_title)
        header.addStretch()
        header.addWidget(self.lbl_status)
        layout.addLayout(header)

        # Centroid Metrics Grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)

        self.lbl_stroke_val = QLabel("110.0")
        self.lbl_stroke_val.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lbl_stroke_val.setAlignment(Qt.AlignCenter)
        lbl_stroke_sub = QLabel("Stroke Travel (~76°)")
        lbl_stroke_sub.setFont(QFont("Segoe UI", 8))
        lbl_stroke_sub.setAlignment(Qt.AlignCenter)

        self.lbl_recoil_val = QLabel("85.0")
        self.lbl_recoil_val.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lbl_recoil_val.setAlignment(Qt.AlignCenter)
        lbl_recoil_sub = QLabel("Snap Recoil (~59°)")
        lbl_recoil_sub.setFont(QFont("Segoe UI", 8))
        lbl_recoil_sub.setAlignment(Qt.AlignCenter)

        self.lbl_dwell_val = QLabel("25.0")
        self.lbl_dwell_val.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lbl_dwell_val.setAlignment(Qt.AlignCenter)
        lbl_dwell_sub = QLabel("Turnaround (ms)")
        lbl_dwell_sub.setFont(QFont("Segoe UI", 8))
        lbl_dwell_sub.setAlignment(Qt.AlignCenter)

        grid.addWidget(self.lbl_stroke_val, 0, 0)
        grid.addWidget(lbl_stroke_sub, 1, 0)
        grid.addWidget(self.lbl_recoil_val, 0, 1)
        grid.addWidget(lbl_recoil_sub, 1, 1)
        grid.addWidget(self.lbl_dwell_val, 0, 2)
        grid.addWidget(lbl_dwell_sub, 1, 2)
        layout.addLayout(grid)

        # Actions
        btn_row = QHBoxLayout()
        self.btn_reject = QPushButton("Reject Mis-trigger")
        self.btn_reject.setFixedHeight(30)
        self.btn_reject.setCursor(Qt.PointingHandCursor)
        self.btn_reject.clicked.connect(self.rejectClicked)

        self.btn_reset = QPushButton("Reset Baseline")
        self.btn_reset.setFixedHeight(30)
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.clicked.connect(self.resetClicked)

        btn_row.addWidget(self.btn_reject)
        btn_row.addWidget(self.btn_reset)
        layout.addLayout(btn_row)

        self.apply_theme(theme_key)

    def set_centroids(self, mu_s: float, mu_r: float, mu_t: float):
        self.lbl_stroke_val.setText(f"{mu_s:.1f}")
        self.lbl_recoil_val.setText(f"{mu_r:.1f}")
        self.lbl_dwell_val.setText(f"{mu_t:.1f}")

    def apply_theme(self, theme_key: str):
        super().apply_theme(theme_key)
        t = THEMES.get(theme_key, THEMES["walnut"])
        self.lbl_title.setStyleSheet(f"color: {t['text']};")
        self.lbl_stroke_val.setStyleSheet(f"color: {t['text']};")
        self.lbl_recoil_val.setStyleSheet(f"color: {t['text']};")
        self.lbl_dwell_val.setStyleSheet(f"color: {t['text']};")

        self.btn_reject.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 69, 58, 0.12);
                color: #FF453A;
                border: 1px solid rgba(255, 69, 58, 0.35);
                border-radius: 8px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 69, 58, 0.25);
            }}
        """)

        self.btn_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['surface']};
                color: {t['text_secondary']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {t['accent']};
                color: {t['accent']};
            }}
        """)


# =============================================================================
# 13. Progressive Disclosure Container (Advanced Settings)
# =============================================================================
class CollapsibleDisclosure(QWidget):
    """Apple-style collapsible progressive disclosure card."""
    def __init__(self, title="Advanced Settings", parent=None, theme_key="walnut"):
        super().__init__(parent)
        self.theme_key = theme_key
        self.is_expanded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header Toggle Button
        self.btn_header = QPushButton(f"›   {title}")
        self.btn_header.setFixedHeight(38)
        self.btn_header.setCursor(Qt.PointingHandCursor)
        self.btn_header.clicked.connect(self.toggle)
        layout.addWidget(self.btn_header)

        # Expandable Body
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(4, 4, 4, 4)
        self.body_layout.setSpacing(10)
        self.body.setVisible(False)
        layout.addWidget(self.body)

        self.title_text = title
        self.apply_theme(theme_key)

    def addWidget(self, widget: QWidget):
        self.body_layout.addWidget(widget)

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self.body.setVisible(self.is_expanded)
        chevron = "⌄" if self.is_expanded else "›"
        self.btn_header.setText(f"{chevron}   {self.title_text}")

    def apply_theme(self, theme_key: str):
        self.theme_key = theme_key
        t = THEMES.get(theme_key, THEMES["walnut"])
        self.btn_header.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['surface_raised']};
                border: 1px solid {t['border']};
                border-radius: 12px;
                padding: 0 14px;
                color: {t['text']};
                font-size: 11.5px;
                font-weight: 600;
                text-align: left;
            }}
            QPushButton:hover {{
                border-color: {t['border_hover']};
            }}
        """)


# =============================================================================
# 16. Hardware RGB Calibration Container (matching Web UI)
# =============================================================================
class HardwareRgbCalibrationCard(GlassPanel):
    """
    Hardware RGB Calibration card:
    - 3 Channel sliders (Red, Green, Blue, 0-1000 => 0.0% to 100.0%)
    - 4 Diagnostic test buttons (Red, Green, Blue, Active)
    """
    calChanged = Signal(str, float) # channel ('R'/'G'/'B'), value (0.0 to 1.0)
    testLedClicked = Signal(str)    # 'R', 'G', 'B', 'RESET'

    def __init__(self, parent=None, theme_key="walnut"):
        super().__init__(parent, theme_key)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header
        self.lbl_title = QLabel("HARDWARE RGB CALIBRATION")
        self.lbl_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))

        self.lbl_sub = QLabel("Fine-tune individual hardware channel limits to calibrate color accuracy and run diagnostic tests.")
        self.lbl_sub.setFont(QFont("Segoe UI", 8.5))
        self.lbl_sub.setWordWrap(True)

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_sub)

        # 3 Sliders
        self.channels = {}
        for ch, name, color in [("R", "Red Channel", "#FF453A"), ("G", "Green Channel", "#32D74B"), ("B", "Blue Channel", "#0A84FF")]:
            row = QHBoxLayout()
            lbl_pip = QLabel("●")
            lbl_pip.setStyleSheet(f"color: {color}; font-size: 10px;")
            lbl_name = QLabel(name)
            lbl_name.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))

            lbl_val = QLabel("100.0%")
            lbl_val.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            lbl_val.setFixedWidth(52)
            lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            row.addWidget(lbl_pip)
            row.addWidget(lbl_name)
            row.addStretch()
            row.addWidget(lbl_val)
            layout.addLayout(row)

            sl = AppleCapsuleSlider(name, ch, 0, 1000, 1000, "", self)
            sl.setFixedHeight(36)
            sl.valueChanged.connect(lambda v, c=ch, lv=lbl_val: self._on_sl_change(c, v, lv))
            self.channels[ch] = (sl, lbl_val)
            layout.addWidget(sl)

        # 4 Diagnostic Test Buttons Grid
        btn_grid = QGridLayout()
        btn_grid.setSpacing(6)

        self.test_btns = []
        for i, (code, lbl_text, col) in enumerate([("R", "Red", "#FF453A"), ("G", "Green", "#32D74B"), ("B", "Blue", "#0A84FF"), ("RESET", "Active", None)]):
            btn = QPushButton(lbl_text)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, c=code: self.testLedClicked.emit(c))
            btn_grid.addWidget(btn, 0, i)
            self.test_btns.append((btn, col))

        layout.addLayout(btn_grid)
        self.apply_theme(theme_key)

    def _on_sl_change(self, channel: str, val: int, lbl_val: QLabel):
        pct = (val / 10.0)
        lbl_val.setText(f"{pct:.1f}%")
        self.calChanged.emit(channel, val / 1000.0)

    def set_calibration(self, r: float, g: float, b: float):
        for ch, val in [("R", r), ("G", g), ("B", b)]:
            if ch in self.channels:
                sl, lbl_val = self.channels[ch]
                int_val = int(round(val * 1000.0))
                sl.blockSignals(True)
                sl.setValue(int_val)
                sl.blockSignals(False)
                lbl_val.setText(f"{(int_val / 10.0):.1f}%")

    def apply_theme(self, theme_key: str):
        super().apply_theme(theme_key)
        t = THEMES.get(theme_key, THEMES["walnut"])
        self.lbl_title.setStyleSheet(f"color: {t['muted']}; letter-spacing: 0.8px;")
        self.lbl_sub.setStyleSheet(f"color: {t['muted']}; line-height: 1.4;")

        for ch, (sl, lv) in self.channels.items():
            sl.apply_theme(theme_key)
            lv.setStyleSheet(f"color: {t['text']}; background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 5px; padding: 1px 4px;")

        for btn, col in self.test_btns:
            accent_col = col if col else t['accent']
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t['surface']};
                    color: {accent_col};
                    border: 1px solid {t['border']};
                    border-radius: 8px;
                    font-size: 10.5px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    border-color: {accent_col};
                    background-color: {t['pill_bg']};
                }}
            """)


# =============================================================================
# 17. Apple Precision Side Scroll Rail Slider (matching Web UI side-scroll-rail)
# =============================================================================
class AppleSideScrollRail(QWidget):
    """
    Apple Precision Side Scroll Rail:
    - Up step button (▲)
    - Track groove with draggable rounded thumb
    - Down step button (▼)
    - Syncs 1:1 with QScrollArea vertical scrollbar
    """
    def __init__(self, scroll_area: QScrollArea, parent=None, theme_key="walnut"):
        super().__init__(parent)
        self.scroll_area = scroll_area
        self.theme_key = theme_key
        self.setFixedWidth(28)
        self.dragging = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 6, 3, 6)
        layout.setSpacing(4)

        self.btn_up = QPushButton("▲")
        self.btn_up.setFixedSize(22, 22)
        self.btn_up.setCursor(Qt.PointingHandCursor)
        self.btn_up.clicked.connect(self._step_up)
        layout.addWidget(self.btn_up)

        # Track area
        self.track = QWidget()
        self.track.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.track.setCursor(Qt.PointingHandCursor)
        self.track.installEventFilter(self)
        layout.addWidget(self.track)

        self.btn_down = QPushButton("▼")
        self.btn_down.setFixedSize(22, 22)
        self.btn_down.setCursor(Qt.PointingHandCursor)
        self.btn_down.clicked.connect(self._step_down)
        layout.addWidget(self.btn_down)

        # Connect to scrollbar changes
        vsb = self.scroll_area.verticalScrollBar()
        vsb.valueChanged.connect(lambda _: self.track.update())
        vsb.rangeChanged.connect(lambda *_: self.track.update())

        self.apply_theme(theme_key)

    def _step_up(self):
        vsb = self.scroll_area.verticalScrollBar()
        vsb.setValue(vsb.value() - 60)

    def _step_down(self):
        vsb = self.scroll_area.verticalScrollBar()
        vsb.setValue(vsb.value() + 60)

    def eventFilter(self, obj, event):
        if obj == self.track:
            vsb = self.scroll_area.verticalScrollBar()
            th = self.track.height()
            max_v = vsb.maximum()

            if event.type() == event.Type.Paint:
                painter = QPainter(self.track)
                painter.setRenderHint(QPainter.Antialiasing)
                t = THEMES.get(self.theme_key, THEMES["walnut"])

                # Groove
                w = self.track.width()
                groove_w = 4.0
                gx = (w - groove_w) / 2.0
                painter.setBrush(QBrush(QColor(t.get('groove', 'rgba(255,180,100,0.12)'))))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(QRectF(gx, 0, groove_w, th), 2.0, 2.0)

                # Thumb
                if max_v > 0:
                    pct = vsb.value() / max(1, max_v)
                else:
                    pct = 0.0

                w_h = self.scroll_area.widget().height() if self.scroll_area.widget() else 1
                thumb_h = max(28.0, th * (self.scroll_area.height() / max(1, w_h)))
                thumb_h = min(th - 4, thumb_h)
                travel = max(1.0, th - thumb_h)
                ty = pct * travel

                painter.setBrush(QBrush(QColor(t['surface_raised'])))
                painter.setPen(QPen(QColor(t['border']), 1.0))
                thumb_rect = QRectF((w - 18) / 2.0, ty, 18, thumb_h)
                painter.drawRoundedRect(thumb_rect, 6.0, 6.0)

                # Grip lines
                painter.setPen(QPen(QColor(t['muted']), 1.2))
                cy = ty + thumb_h / 2.0
                painter.drawLine(QPointF((w - 8) / 2.0, cy - 2), QPointF((w + 8) / 2.0, cy - 2))
                painter.drawLine(QPointF((w - 8) / 2.0, cy + 2), QPointF((w + 8) / 2.0, cy + 2))
                return True

            elif event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self.dragging = True
                    self._update_scroll_from_y(event.position().y())
                    return True
            elif event.type() == event.Type.MouseMove:
                if self.dragging:
                    self._update_scroll_from_y(event.position().y())
                    return True
            elif event.type() == event.Type.MouseButtonRelease:
                if event.button() == Qt.LeftButton:
                    self.dragging = False
                    return True

        return super().eventFilter(obj, event)

    def _update_scroll_from_y(self, y: float):
        th = max(1, self.track.height())
        pct = max(0.0, min(1.0, y / th))
        vsb = self.scroll_area.verticalScrollBar()
        vsb.setValue(int(pct * vsb.maximum()))

    def apply_theme(self, theme_key: str):
        self.theme_key = theme_key
        t = THEMES.get(theme_key, THEMES["walnut"])
        self.setStyleSheet(f"""
            AppleSideScrollRail {{
                background-color: {t['card_bg']};
                border: 1px solid {t['border']};
                border-radius: 14px;
            }}
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 6px;
                color: {t['muted']};
                font-size: 9px;
            }}
            QPushButton:hover {{
                color: {t['text']};
                background-color: {t['surface_raised']};
            }}
        """)
        self.track.update()


# =============================================================================
# 18. About OmniScroll Project Overview & FAQ Card (matching Web UI)
# =============================================================================
class AboutOmniScrollCard(GlassPanel):
    """
    Project Overview, Hardware Specs Grid & FAQ Disclosure Accordion:
    Matches .seo-overview-card in Web Control Panel.
    """
    def __init__(self, parent=None, theme_key="walnut"):
        super().__init__(parent, theme_key)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # Header with GitHub Button
        hdr = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        self.lbl_title = QLabel("About OmniScroll (Omni Scroll)")
        self.lbl_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))

        self.lbl_sub = QLabel("Open-source DIY haptic rotary dial & high-resolution optical controller")
        self.lbl_sub.setFont(QFont("Segoe UI", 9))

        title_box.addWidget(self.lbl_title)
        title_box.addWidget(self.lbl_sub)
        hdr.addLayout(title_box)
        hdr.addStretch()

        self.btn_gh = QPushButton("GitHub Repository")
        self.btn_gh.setFixedHeight(32)
        self.btn_gh.setCursor(Qt.PointingHandCursor)
        self.btn_gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/roufsweb/OmniScroll")))
        hdr.addWidget(self.btn_gh)
        layout.addLayout(hdr)

        # Description
        self.lbl_desc = QLabel(
            "OmniScroll is a zero-contact haptic computer controller engineered around a freely spinning "
            "industrial steel ball bearing and an MX8650 optical sensor. Powered by an ESP32-S2 microcontroller, "
            "OmniScroll delivers native Windows & macOS sub-pixel smooth scrolling, customizable iPhone 6 LRA tactile detents, "
            "and real-time on-device adaptive flick gesture recognition (TinyOL)."
        )
        self.lbl_desc.setFont(QFont("Segoe UI", 9.5))
        self.lbl_desc.setWordWrap(True)
        layout.addWidget(self.lbl_desc)

        # 4-Spec Grid
        specs_grid = QGridLayout()
        specs_grid.setSpacing(10)

        specs = [
            ("TRACKING", "MX8650 Optical Sensor (Up to 1600 CPI)"),
            ("HAPTICS", "iPhone LRA + PAM8403 Amplifier"),
            ("CONTROLLER", "ESP32-S2 (Native USB HID + Web Serial)"),
            ("CONFIGURATOR", "Zero Drivers (Native Windows + Web Serial)")
        ]
        self.spec_cards = []
        for i, (label, val) in enumerate(specs):
            card = QFrame()
            card.setFixedHeight(54)
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(12, 6, 12, 6)
            c_layout.setSpacing(1)

            lbl_l = QLabel(label)
            lbl_l.setFont(QFont("Segoe UI", 7.5, QFont.Weight.Bold))
            lbl_v = QLabel(val)
            lbl_v.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))

            c_layout.addWidget(lbl_l)
            c_layout.addWidget(lbl_v)
            specs_grid.addWidget(card, i // 2, i % 2)
            self.spec_cards.append((card, lbl_l, lbl_v))

        layout.addLayout(specs_grid)

        # FAQ Section Accordion
        faq_title = QLabel("FREQUENTLY ASKED QUESTIONS")
        faq_title.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Bold))
        layout.addWidget(faq_title)

        faqs = [
            ("What is OmniScroll?", "OmniScroll is an open-source DIY haptic computer rotary dial and precision optical scroll wheel controller engineered around a freely spinning steel ball bearing and an MX8650 optical mouse sensor, powered by an ESP32-S2."),
            ("How does the optical bearing mechanism work?", "Instead of using mechanical encoders that wear out, OmniScroll reads microscopic surface textures of an industrial steel ball bearing at ~520 counts per 360° revolution (0.6923° per count) with infinite lifespan."),
            ("Does OmniScroll require companion software?", "No. OmniScroll operates as a standard USB HID input device on Windows, macOS, Linux, and ChromeOS. Configuration is handled 100% in-browser or via this ultra-lightweight native bridge."),
            ("What gestures and shortcut actions are supported?", "OmniScroll features ballistic Flick Forward and Flick Backward gestures, a Touch & Spin hold-to-scroll modifier, and Single Tap on the dial cap.")
        ]
        self.faq_widgets = []
        for q, a in faqs:
            disc = CollapsibleDisclosure(q, self, theme_key)
            ans_lbl = QLabel(a)
            ans_lbl.setFont(QFont("Segoe UI", 8.5))
            ans_lbl.setWordWrap(True)
            disc.addWidget(ans_lbl)
            layout.addWidget(disc)
            self.faq_widgets.append((disc, ans_lbl))

        self.apply_theme(theme_key)

    def apply_theme(self, theme_key: str):
        super().apply_theme(theme_key)
        t = THEMES.get(theme_key, THEMES["walnut"])
        self.lbl_title.setStyleSheet(f"color: {t['text']};")
        self.lbl_sub.setStyleSheet(f"color: {t['muted']};")
        self.lbl_desc.setStyleSheet(f"color: {t['text_secondary']}; line-height: 1.5;")

        self.btn_gh.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['surface_raised']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {t['accent']};
                color: {t['accent']};
            }}
        """)

        for card, lbl_l, lbl_v in self.spec_cards:
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {t['surface_raised']};
                    border: 1px solid {t['border']};
                    border-radius: 10px;
                }}
            """)
            lbl_l.setStyleSheet(f"color: {t['muted']}; letter-spacing: 0.6px;")
            lbl_v.setStyleSheet(f"color: {t['text']};")

        for disc, ans in self.faq_widgets:
            disc.apply_theme(theme_key)
            ans.setStyleSheet(f"color: {t['text_secondary']}; line-height: 1.45;")


# =============================================================================
# 19. About OmniScroll Modal Dialog (Apple Pro HIG)
# =============================================================================
class AboutModal(QDialog):
    """
    Dedicated About Modal Dialog:
    - Triggered via the top-right 'i' button in HeaderBar
    - Displays clean project description, 4 hardware specification cards,
      support/donate crypto wallet with 1-click copy, and FAQs
    - Clean frosted glass background matching the active theme
    """
    def __init__(self, parent=None, theme_key="walnut"):
        super().__init__(parent)
        self.theme_key = theme_key
        self.setWindowTitle("About OmniScroll")
        self.setFixedWidth(560)
        self.setFixedHeight(640)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.container = QFrame(self)
        self.container.setObjectName("AboutModalContainer")
        layout.addWidget(self.container)

        c_layout = QVBoxLayout(self.container)
        c_layout.setContentsMargins(22, 18, 22, 18)
        c_layout.setSpacing(12)

        # Header Row: Title with Branding & Close Button
        hdr = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        title_brand_row = QHBoxLayout()
        title_brand_row.setSpacing(8)

        self.lbl_title = QLabel("OmniScroll")
        self.lbl_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))

        self.badge_brand = QLabel("from roufsweb")
        self.badge_brand.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.badge_brand.setFixedHeight(20)

        title_brand_row.addWidget(self.lbl_title)
        title_brand_row.addWidget(self.badge_brand)
        title_brand_row.addStretch()

        self.lbl_sub = QLabel("Open-source DIY haptic rotary dial & optical controller")
        self.lbl_sub.setFont(QFont("Segoe UI", 9))

        title_box.addLayout(title_brand_row)
        title_box.addWidget(self.lbl_sub)
        hdr.addLayout(title_box)
        hdr.addStretch()

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.accept)
        hdr.addWidget(self.btn_close)
        c_layout.addLayout(hdr)

        # Scroll Area for Body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        inner = QWidget()
        inner.setStyleSheet("background: transparent; border: none;")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 6, 0)
        inner_layout.setSpacing(14)

        # Description
        self.lbl_desc = QLabel(
            "OmniScroll is a zero-contact haptic computer controller engineered around a freely spinning "
            "industrial steel ball bearing and an MX8650 optical sensor. Powered by an ESP32-S2 microcontroller, "
            "OmniScroll delivers native Windows & macOS sub-pixel smooth scrolling, customizable iPhone 6 LRA tactile detents, "
            "and real-time on-device adaptive flick gesture recognition (TinyOL)."
        )
        self.lbl_desc.setFont(QFont("Segoe UI", 9.5))
        self.lbl_desc.setWordWrap(True)
        inner_layout.addWidget(self.lbl_desc)

        # 4-Spec Grid
        specs_grid = QGridLayout()
        specs_grid.setSpacing(8)
        specs = [
            ("TRACKING", "MX8650 Optical Sensor (Up to 1600 CPI)"),
            ("HAPTICS", "iPhone LRA + PAM8403 Amplifier"),
            ("CONTROLLER", "ESP32-S2 (Native USB HID + Web Serial)"),
            ("CONFIGURATOR", "Zero Drivers (Native Windows + Web Serial)")
        ]
        self.spec_cards = []
        for i, (label, val) in enumerate(specs):
            card = QFrame()
            card.setObjectName("SpecCard")
            card.setFixedHeight(52)
            card_box = QVBoxLayout(card)
            card_box.setContentsMargins(10, 5, 10, 5)
            card_box.setSpacing(1)
            lbl_l = QLabel(label)
            lbl_l.setFont(QFont("Segoe UI", 7.5, QFont.Weight.Bold))
            lbl_v = QLabel(val)
            lbl_v.setFont(QFont("Segoe UI", 8.5, QFont.Weight.DemiBold))
            card_box.addWidget(lbl_l)
            card_box.addWidget(lbl_v)
            specs_grid.addWidget(card, i // 2, i % 2)
            self.spec_cards.append((card, lbl_l, lbl_v))
        inner_layout.addLayout(specs_grid)

        # Support & Buy Me a Coffee / Donation Card
        self.card_support = QFrame()
        self.card_support.setObjectName("SupportCard")
        supp_layout = QVBoxLayout(self.card_support)
        supp_layout.setContentsMargins(14, 12, 14, 12)
        supp_layout.setSpacing(8)

        supp_hdr = QHBoxLayout()
        self.lbl_supp_title = QLabel("☕ Support & Buy Me a Coffee")
        self.lbl_supp_title.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))

        self.badge_eth = QLabel("Ethereum / MetaMask")
        self.badge_eth.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.badge_eth.setStyleSheet("""
            background: rgba(98, 126, 234, 0.16);
            color: #8C9EFF;
            border: 1px solid rgba(98, 126, 234, 0.40);
            border-radius: 8px;
            padding: 2px 7px;
        """)

        supp_hdr.addWidget(self.lbl_supp_title)
        supp_hdr.addStretch()
        supp_hdr.addWidget(self.badge_eth)
        supp_layout.addLayout(supp_hdr)

        self.lbl_supp_desc = QLabel(
            "If OmniScroll helped you or made your setup feel magic, you can support development with an Ethereum tip:"
        )
        self.lbl_supp_desc.setFont(QFont("Segoe UI", 8.5))
        self.lbl_supp_desc.setWordWrap(True)
        supp_layout.addWidget(self.lbl_supp_desc)

        # Wallet address row with 1-click copy
        wallet_row = QHBoxLayout()
        wallet_row.setSpacing(8)

        self.lbl_wallet_box = QFrame()
        self.lbl_wallet_box.setObjectName("WalletPill")
        w_box_layout = QHBoxLayout(self.lbl_wallet_box)
        w_box_layout.setContentsMargins(10, 4, 10, 4)
        w_box_layout.setSpacing(4)

        self.lbl_wallet_addr = QLabel("0x609e0AB78d5174F72fF8709564f8337DebEa5BD7")
        self.lbl_wallet_addr.setFont(QFont("Consolas", 8.5))
        self.lbl_wallet_addr.setTextInteractionFlags(Qt.TextSelectableByMouse)
        w_box_layout.addWidget(self.lbl_wallet_addr)

        self.btn_copy_wallet = QPushButton("📋 Copy Address")
        self.btn_copy_wallet.setFixedHeight(30)
        self.btn_copy_wallet.setCursor(Qt.PointingHandCursor)
        self.btn_copy_wallet.clicked.connect(self._copy_wallet_address)

        wallet_row.addWidget(self.lbl_wallet_box, 1)
        wallet_row.addWidget(self.btn_copy_wallet)
        supp_layout.addLayout(wallet_row)

        inner_layout.addWidget(self.card_support)

        # FAQ Accordions
        self.lbl_faq_title = QLabel("FREQUENTLY ASKED QUESTIONS")
        self.lbl_faq_title.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Bold))
        inner_layout.addWidget(self.lbl_faq_title)

        faqs = [
            ("What is OmniScroll?", "OmniScroll is an open-source DIY haptic computer rotary dial and precision optical scroll wheel controller engineered around a freely spinning steel ball bearing and an MX8650 optical mouse sensor, powered by an ESP32-S2."),
            ("How does the optical bearing mechanism work?", "Instead of using mechanical encoders that wear out, OmniScroll reads microscopic surface textures of an industrial steel ball bearing at ~520 counts per 360° revolution (0.6923° per count) with infinite lifespan."),
            ("Does OmniScroll require companion software?", "No. OmniScroll operates as a standard USB HID input device on Windows, macOS, Linux, and ChromeOS. Configuration is handled 100% in-browser or via this ultra-lightweight native bridge."),
            ("What gestures and shortcut actions are supported?", "OmniScroll features ballistic Flick Forward and Flick Backward gestures, a Touch & Spin hold-to-scroll modifier, and Single Tap on the dial cap.")
        ]
        self.faq_widgets = []
        for q, a in faqs:
            disc = CollapsibleDisclosure(q, self, theme_key)
            ans_lbl = QLabel(a)
            ans_lbl.setFont(QFont("Segoe UI", 8.5))
            ans_lbl.setWordWrap(True)
            disc.addWidget(ans_lbl)
            inner_layout.addWidget(disc)
            self.faq_widgets.append((disc, ans_lbl))

        # GitHub Repo Link
        self.btn_gh = QPushButton("GitHub Repository")
        self.btn_gh.setFixedHeight(34)
        self.btn_gh.setCursor(Qt.PointingHandCursor)
        self.btn_gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/roufsweb/OmniScroll")))
        inner_layout.addWidget(self.btn_gh)

        scroll.setWidget(inner)
        c_layout.addWidget(scroll, 1)

        self.apply_theme(theme_key)

    def _copy_wallet_address(self):
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        clipboard.setText("0x609e0AB78d5174F72fF8709564f8337DebEa5BD7")
        self.btn_copy_wallet.setText("✓ Copied!")
        self.btn_copy_wallet.setStyleSheet("""
            QPushButton {
                background-color: rgba(48, 209, 88, 0.16);
                color: #30D158;
                border: 1px solid rgba(48, 209, 88, 0.45);
                border-radius: 8px;
                font-weight: bold;
                font-size: 11px;
                padding: 0 12px;
            }
        """)
        QTimer.singleShot(2500, self._reset_copy_button)

    def _reset_copy_button(self):
        t = THEMES.get(self.theme_key, THEMES["walnut"])
        self.btn_copy_wallet.setText("📋 Copy Address")
        self.btn_copy_wallet.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['surface_raised']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {t['accent']};
                color: {t['accent']};
            }}
        """)

    def apply_theme(self, theme_key: str):
        self.theme_key = theme_key
        t = THEMES.get(theme_key, THEMES["walnut"])

        # Style the container strictly using ID selector to prevent QLabel border inheritance
        self.container.setStyleSheet(f"""
            #AboutModalContainer {{
                background-color: {t['card_bg']};
                border: 1px solid {t['border_hover']};
                border-radius: 18px;
            }}
            #AboutModalContainer QLabel {{
                border: none;
                background: transparent;
            }}
        """)

        self.lbl_title.setStyleSheet(f"color: {t['text']}; border: none;")
        self.badge_brand.setStyleSheet("""
            background: rgba(255, 160, 0, 0.14);
            color: #FFA000;
            border: 1px solid rgba(255, 160, 0, 0.40);
            border-radius: 10px;
            padding: 1px 7px;
        """)
        self.lbl_sub.setStyleSheet(f"color: {t['muted']}; border: none;")
        self.lbl_desc.setStyleSheet(f"color: {t['text_secondary']}; line-height: 1.5; border: none;")
        self.lbl_faq_title.setStyleSheet(f"color: {t['muted']}; letter-spacing: 0.8px; border: none;")

        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['surface_raised']};
                color: {t['muted']};
                border: 1px solid {t['border']};
                border-radius: 14px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {t['text']};
                background-color: {t['surface_hover']};
            }}
        """)

        self.btn_gh.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['surface_raised']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {t['accent']};
                color: {t['accent']};
            }}
        """)

        # Hardware Spec Cards
        for card, lbl_l, lbl_v in self.spec_cards:
            card.setStyleSheet(f"""
                #SpecCard {{
                    background-color: {t['surface_raised']};
                    border: 1px solid {t['border']};
                    border-radius: 10px;
                }}
                #SpecCard QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
            lbl_l.setStyleSheet(f"color: {t['muted']}; letter-spacing: 0.6px; border: none;")
            lbl_v.setStyleSheet(f"color: {t['text']}; border: none;")

        # Support & Donation Card
        self.card_support.setStyleSheet(f"""
            #SupportCard {{
                background-color: {t['surface_raised']};
                border: 1px solid {t['border']};
                border-radius: 12px;
            }}
            #SupportCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        self.lbl_supp_title.setStyleSheet(f"color: {t['text']}; border: none;")
        self.lbl_supp_desc.setStyleSheet(f"color: {t['text_secondary']}; border: none;")
        self.lbl_wallet_box.setStyleSheet(f"""
            #WalletPill {{
                background: rgba(0, 0, 0, 0.28);
                border: 1px solid {t['border']};
                border-radius: 7px;
            }}
        """)
        self.lbl_wallet_addr.setStyleSheet(f"color: {t['accent']}; border: none;")
        self._reset_copy_button()

        # FAQs
        for disc, ans in self.faq_widgets:
            disc.apply_theme(theme_key)
            ans.setStyleSheet(f"color: {t['text_secondary']}; line-height: 1.45; border: none;")


