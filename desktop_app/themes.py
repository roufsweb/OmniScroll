"""
themes.py — Apple Pro HIG & Nordic Walnut Theme Palettes for OmniScroll Desktop
Provides colors, gradients, and full QSS style generation for all 4 hardware themes:
1. Walnut (Nordic Walnut & Amber MagSafe)
2. Obsidian (Studio Pro Dark)
3. Aluminum (Silver Bezel & Studio Light)
4. Ultra (Apple Watch Ultra Tactical Dark & International Orange)
"""

THEMES = {
    "walnut": {
        "name": "Walnut",
        "bg": "#100C09",
        "surface": "#1A130E",
        "surface_raised": "#251B14",
        "surface_hover": "#34261C",
        "border": "rgba(212, 163, 115, 0.16)",
        "border_hover": "rgba(212, 163, 115, 0.35)",
        "text": "#FDF7F2",
        "text_secondary": "#D6C1B0",
        "muted": "#8D796B",
        "accent": "#FFA000",
        "accent_rgb": (255, 160, 0),
        "accent_text": "#000000",
        "accent_glow": "rgba(255, 160, 0, 0.40)",
        "card_bg": "#18120D",
        "pill_bg": "rgba(255, 180, 100, 0.08)",
        "groove": "rgba(255, 180, 100, 0.12)"
    },
    "obsidian": {
        "name": "Obsidian",
        "bg": "#0B0C0E",
        "surface": "#14161A",
        "surface_raised": "#1E2026",
        "surface_hover": "#2B2E37",
        "border": "rgba(255, 255, 255, 0.09)",
        "border_hover": "rgba(10, 132, 255, 0.40)",
        "text": "#F5F5F7",
        "text_secondary": "#A1A1A6",
        "muted": "#636366",
        "accent": "#0A84FF",
        "accent_rgb": (10, 132, 255),
        "accent_text": "#FFFFFF",
        "accent_glow": "rgba(10, 132, 255, 0.40)",
        "card_bg": "#121417",
        "pill_bg": "rgba(255, 255, 255, 0.06)",
        "groove": "rgba(255, 255, 255, 0.10)"
    },
    "aluminum": {
        "name": "Aluminum",
        "bg": "#EBECEF",
        "surface": "#F8F9FA",
        "surface_raised": "#E4E6EB",
        "surface_hover": "#D8DBE2",
        "border": "rgba(0, 0, 0, 0.10)",
        "border_hover": "rgba(0, 113, 227, 0.40)",
        "text": "#111827",
        "text_secondary": "#4B5563",
        "muted": "#7E8794",
        "accent": "#0071E3",
        "accent_rgb": (0, 113, 227),
        "accent_text": "#FFFFFF",
        "accent_glow": "rgba(0, 113, 227, 0.35)",
        "card_bg": "#FFFFFF",
        "pill_bg": "rgba(0, 0, 0, 0.05)",
        "groove": "rgba(0, 0, 0, 0.08)"
    },
    "ultra": {
        "name": "Ultra",
        "bg": "#09090B",
        "surface": "#141416",
        "surface_raised": "#1E1E22",
        "surface_hover": "#2B2B30",
        "border": "rgba(255, 90, 0, 0.18)",
        "border_hover": "rgba(255, 90, 0, 0.45)",
        "text": "#F4F4F5",
        "text_secondary": "#A1A1AA",
        "muted": "#71717A",
        "accent": "#FF5A00",
        "accent_rgb": (255, 90, 0),
        "accent_text": "#FFFFFF",
        "accent_glow": "rgba(255, 90, 0, 0.40)",
        "card_bg": "#101013",
        "pill_bg": "rgba(255, 90, 0, 0.08)",
        "groove": "rgba(255, 90, 0, 0.12)"
    }
}


def get_stylesheet(theme_key="walnut") -> str:
    """Generates complete native application QSS stylesheet for the selected theme."""
    t = THEMES.get(theme_key, THEMES["walnut"])

    return f"""
        QMainWindow, QWidget#CentralWidget, QWidget#ScrollContent, QScrollArea, QScrollArea > QWidget > QWidget {{
            background-color: {t['bg']};
            color: {t['text']};
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
        }}

        QScrollArea {{
            background-color: {t['bg']};
            border: none;
        }}


        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {t['muted']}55;
            min-height: 24px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {t['accent']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
        }}

        QToolTip {{
            background-color: {t['surface_raised']};
            color: {t['text']};
            border: 1px solid {t['border_hover']};
            border-radius: 6px;
            padding: 5px 8px;
            font-size: 11px;
        }}
    """
