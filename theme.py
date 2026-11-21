"""Live Omarchy theme loader, watcher, and premium QSS generator for Cron Manager."""

from __future__ import annotations

import os
import re
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal


THEME_CANDIDATES = (
    Path.home() / ".local" / "state" / "omarchy" / "current" / "theme" / "colors.toml",
    Path.home() / ".config" / "omarchy" / "current" / "theme" / "colors.toml",
)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return (128, 128, 128)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return (128, 128, 128)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"


def _blend(c1: str, c2: str, ratio: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(
        int(r1 + (r2 - r1) * ratio),
        int(g1 + (g2 - g1) * ratio),
        int(b1 + (b2 - b1) * ratio),
    )


def _luminance(hex_color: str) -> float:
    r, g, b = _hex_to_rgb(hex_color)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _contrast_text(bg_hex: str) -> str:
    return "#0d1015" if _luminance(bg_hex) > 0.56 else "#ffffff"


def _hyprland_rounding(default: int = 10) -> int:
    try:
        res = subprocess.run(
            ["hyprctl", "getoption", "decoration:rounding"],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if res.returncode == 0:
            m = re.search(r"int:\s*(\d+)", res.stdout)
            if m:
                val = int(m.group(1))
                return max(6, min(18, val)) if val > 0 else 6
    except Exception:
        pass
    return default


@dataclass(frozen=True)
class ThemePalette:
    mode: str
    bg: str
    surface: str
    surface_alt: str
    surface_hover: str
    border: str
    fg: str
    fg_muted: str
    accent: str
    accent_soft: str
    accent_hover: str
    accent_fg: str
    success: str
    warning: str
    danger: str
    radius: int
    source_name: str


def load_omarchy_theme() -> ThemePalette:
    data: dict = {}
    source_path: Path | None = None
    for path in THEME_CANDIDATES:
        if path.exists():
            source_path = path
            try:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            break

    bg = str(data.get("background", "#111318"))
    is_light = str(data.get("mode", "")).lower() == "light" or _luminance(bg) > 0.55
    mode = "light" if is_light else "dark"

    fg = str(data.get("foreground", "#181c22" if is_light else "#e6eaf5"))
    fg_muted = str(
        data.get("dark_foreground")
        or data.get("muted")
        or _blend(fg, bg, 0.38)
    )
    accent = str(data.get("accent") or data.get("blue") or "#7376b7")

    lighter = str(data.get("lighter_background", ""))
    if lighter and lighter.lower() != bg.lower():
        surface = lighter
    else:
        surface = _blend(bg, "#000000" if is_light else "#ffffff", 0.04 if is_light else 0.07)

    surface_alt = _blend(surface, "#000000" if is_light else "#ffffff", 0.04 if is_light else 0.06)
    surface_hover = _blend(surface, accent, 0.16)
    border = _blend(surface, fg, 0.14)
    accent_soft = _blend(surface, accent, 0.22)
    accent_hover = _blend(accent, "#ffffff" if not is_light else "#000000", 0.16)
    accent_fg = _contrast_text(accent)

    success = str(data.get("green", "#3fb950"))
    warning = str(data.get("yellow") or data.get("orange") or "#e3b341")
    danger = str(data.get("red", "#f85149"))

    return ThemePalette(
        mode=mode,
        bg=bg,
        surface=surface,
        surface_alt=surface_alt,
        surface_hover=surface_hover,
        border=border,
        fg=fg,
        fg_muted=fg_muted,
        accent=accent,
        accent_soft=accent_soft,
        accent_hover=accent_hover,
        accent_fg=accent_fg,
        success=success,
        warning=warning,
        danger=danger,
        radius=_hyprland_rounding(10),
        source_name="Omarchy Live" if source_path else "Default",
    )


class ThemeWatcher(QObject):
    """Watches Omarchy's active colors.toml live."""

    theme_changed = Signal(object)

    def __init__(self, parent: QObject | None = None, interval_ms: int = 1200) -> None:
        super().__init__(parent)
        self._palette: ThemePalette = load_omarchy_theme()
        self._last_sig: str = self._snapshot_signature()

        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._check)
        self._timer.start()

    @property
    def palette(self) -> ThemePalette:
        return self._palette

    def _snapshot_signature(self) -> str:
        parts = []
        for p in THEME_CANDIDATES:
            try:
                st = os.stat(p)
                parts.append(f"{p}:{st.st_mtime_ns}:{st.st_size}")
            except OSError:
                parts.append(f"{p}:missing")
        return "|".join(parts)

    def _check(self) -> None:
        sig = self._snapshot_signature()
        if sig != self._last_sig:
            self._last_sig = sig
            new_palette = load_omarchy_theme()
            if new_palette != self._palette:
                self._palette = new_palette
                self.theme_changed.emit(new_palette)


def build_stylesheet(p: ThemePalette) -> str:
    r = p.radius
    r_sm = max(6, r)
    r_card = r + 6
    r_pill = r + 10
    grad_end = _blend(p.accent, p.success, 0.35)
    grad_hover_end = _blend(p.accent_hover, p.success, 0.45)

    return f"""
    QMainWindow, QDialog {{
        background-color: {p.bg};
        color: {p.fg};
        font-family: "Inter", "Noto Sans", "Segoe UI", sans-serif;
        font-size: 13px;
    }}
    QWidget {{
        color: {p.fg};
    }}
    QScrollArea, QScrollArea > QWidget > QWidget {{
        background: transparent;
        border: none;
    }}
    QFrame#HeaderCard {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {p.surface}, stop:1 {p.accent_soft});
        border: 1px solid {p.border};
        border-radius: {r_card + 2}px;
    }}
    QLabel#LogoBadge {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {p.accent}, stop:1 {grad_end});
        color: {p.accent_fg};
        border-radius: {r_sm + 3}px;
        font-size: 18px;
        font-weight: 800;
    }}
    QLabel#TitleLabel {{
        font-size: 21px;
        font-weight: 800;
        color: {p.fg};
    }}
    QLabel#SubtitleLabel {{
        font-size: 12px;
        color: {p.fg_muted};
    }}
    QLabel#StatPill {{
        background-color: {p.surface};
        border: 1px solid {p.border};
        border-radius: {r_pill}px;
        padding: 5px 13px;
        font-size: 12px;
        font-weight: 700;
        color: {p.fg};
    }}
    QLabel#CmdPill {{
        background-color: {p.bg};
        border: 1px solid {p.border};
        border-radius: {r_sm}px;
        padding: 6px 11px;
        font-family: "JetBrains Mono", "Fira Code", monospace;
        font-size: 12px;
        color: {p.fg};
    }}
    QFrame#JobCard {{
        background-color: {p.surface};
        border: 1px solid {p.border};
        border-radius: {r_card}px;
    }}
    QFrame#JobCard:hover {{
        background-color: {p.surface_hover};
        border: 1px solid {p.accent};
    }}
    QFrame#EmptyCard {{
        background-color: {p.surface};
        border: 1px dashed {p.border};
        border-radius: {r_card + 4}px;
    }}
    QFrame#ToastBanner {{
        background-color: {p.accent_soft};
        border: 1px solid {p.accent};
        border-radius: {r_sm + 2}px;
    }}
    QLineEdit, QPlainTextEdit, QSpinBox, QComboBox {{
        background-color: {p.surface};
        color: {p.fg};
        border: 1px solid {p.border};
        border-radius: {r_sm}px;
        padding: 8px 12px;
        selection-background-color: {p.accent};
        selection-color: {p.accent_fg};
    }}
    QLineEdit:hover, QPlainTextEdit:hover, QSpinBox:hover, QComboBox:hover {{
        border-color: {_blend(p.border, p.accent, 0.55)};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border: 1.5px solid {p.accent};
        background-color: {p.surface_alt};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {p.surface};
        color: {p.fg};
        border: 1px solid {p.accent};
        border-radius: {r_sm}px;
        selection-background-color: {p.accent};
        selection-color: {p.accent_fg};
    }}
    QPushButton {{
        background-color: {p.surface};
        color: {p.fg};
        border: 1px solid {p.border};
        border-radius: {r_sm}px;
        padding: 8px 15px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {p.surface_hover};
        border: 1px solid {p.accent};
    }}
    QPushButton:pressed {{
        background-color: {p.accent_soft};
        padding-top: 9px;
        padding-bottom: 7px;
    }}
    QPushButton#PrimaryButton {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {p.accent}, stop:1 {grad_end});
        color: {p.accent_fg};
        border: 1px solid {p.accent};
        border-radius: {r_sm + 2}px;
        padding: 9px 18px;
        font-weight: 700;
    }}
    QPushButton#PrimaryButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {p.accent_hover}, stop:1 {grad_hover_end});
        border-color: {p.accent_hover};
    }}
    QPushButton#PrimaryButton:pressed {{
        padding-top: 10px;
        padding-bottom: 8px;
    }}
    QPushButton#ChipButton {{
        background-color: {p.surface};
        color: {p.fg_muted};
        border: 1px solid {p.border};
        border-radius: {r_pill}px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton#ChipButton:hover {{
        color: {p.fg};
        border-color: {p.accent};
        background-color: {p.surface_hover};
    }}
    QPushButton#ChipButton:checked {{
        background-color: {p.accent};
        color: {p.accent_fg};
        border-color: {p.accent};
    }}
    QPushButton#CardAction {{
        background-color: {p.surface_alt};
        color: {p.fg};
        border: 1px solid {p.border};
        border-radius: {r_sm}px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton#CardAction:hover {{
        border-color: {p.accent};
        background-color: {p.accent_soft};
    }}
    QPushButton#RunAction {{
        background-color: {p.accent_soft};
        color: {p.fg};
        border: 1px solid {p.accent};
        border-radius: {r_sm}px;
        padding: 6px 13px;
        font-size: 12px;
        font-weight: 700;
    }}
    QPushButton#RunAction:hover {{
        background-color: {p.accent};
        color: {p.accent_fg};
    }}
    QPushButton#DangerAction {{
        background-color: transparent;
        color: {p.danger};
        border: 1px solid {p.border};
        border-radius: {r_sm}px;
        padding: 6px 11px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton#DangerAction:hover {{
        background-color: {p.danger};
        color: {_contrast_text(p.danger)};
        border-color: {p.danger};
    }}
    QCheckBox {{
        spacing: 8px;
        color: {p.fg};
        font-weight: 500;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 5px;
        border: 1px solid {p.border};
        background-color: {p.surface};
    }}
    QCheckBox::indicator:hover {{
        border-color: {p.accent};
    }}
    QCheckBox::indicator:checked {{
        background-color: {p.accent};
        border-color: {p.accent};
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px 0;
    }}
    QScrollBar::handle:vertical {{
        background: {p.border};
        border-radius: 4px;
        min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p.accent};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """
