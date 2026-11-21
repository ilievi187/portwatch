#!/usr/bin/env python3
"""PortWatch — Sleek Live Linux Ports & Process Manager (Qt 6 / PySide6 + Live Omarchy Theme)."""

from __future__ import annotations

import sys
from typing import Callable

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QUrl, Qt, QTimer
from PySide6.QtGui import QColor, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import portwatch as pw
from theme import ThemePalette, ThemeWatcher, build_stylesheet


class GlowButton(QPushButton):
    def __init__(self, text: str = "", glow_hex: str = "#7376b7", max_blur: float = 18.0, parent=None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._max_blur = max_blur
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setOffset(0, 0)
        self._shadow.setBlurRadius(0.0)
        self.update_glow_color(glow_hex)
        self.setGraphicsEffect(self._shadow)

        self._anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def update_glow_color(self, hex_color: str) -> None:
        c = QColor(hex_color)
        c.setAlpha(150)
        self._shadow.setColor(c)

    def enterEvent(self, event) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._shadow.blurRadius())
        self._anim.setEndValue(self._max_blur)
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._shadow.blurRadius())
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(event)


class PortCard(QFrame):
    def __init__(
        self,
        entry: pw.PortEntry,
        palette: ThemePalette,
        on_open: Callable[[pw.PortEntry], None],
        on_copy: Callable[[pw.PortEntry], None],
        on_kill: Callable[[pw.PortEntry], None],
    ) -> None:
        super().__init__()
        self.setObjectName("JobCard")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 13, 16, 13)
        outer.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)

        port_badge = QLabel(f":{entry.port}")
        port_badge.setStyleSheet(
            f"background-color: {palette.accent}; color: {palette.accent_fg}; "
            f"border-radius: 8px; padding: 3px 10px; font-family: monospace; "
            f"font-size: 13px; font-weight: 800;"
        )
        top.addWidget(port_badge)

        proto_lbl = QLabel(entry.proto)
        proto_lbl.setStyleSheet(
            f"background-color: {palette.surface_alt}; color: {palette.fg_muted}; "
            f"border: 1px solid {palette.border}; border-radius: 7px; "
            f"padding: 2px 8px; font-size: 11px; font-weight: 700;"
        )
        top.addWidget(proto_lbl)

        proc_lbl = QLabel(entry.process)
        proc_lbl.setStyleSheet("font-size: 15px; font-weight: 700;")
        top.addWidget(proc_lbl)

        if entry.pid:
            pid_lbl = QLabel(f"PID {entry.pid}")
            pid_lbl.setStyleSheet(f"color: {palette.fg_muted}; font-family: monospace; font-size: 11px;")
            top.addWidget(pid_lbl)

        if entry.rss_mb > 0:
            ram_lbl = QLabel(f"{entry.rss_mb:.1f} MB")
            ram_lbl.setStyleSheet(f"color: {palette.fg_muted}; font-size: 11px;")
            top.addWidget(ram_lbl)

        top.addStretch()

        scope_color = palette.warning if entry.exposed else palette.success
        scope_text = f"LAN ({entry.address})" if entry.exposed else f"Local ({entry.address})"
        scope_badge = QLabel(scope_text)
        scope_badge.setStyleSheet(
            f"color: {scope_color}; border: 1px solid {scope_color}; "
            f"border-radius: 9px; padding: 2px 9px; font-size: 11px; font-weight: 700;"
        )
        top.addWidget(scope_badge)
        outer.addLayout(top)

        if entry.cmdline:
            cmd_lbl = QLabel(entry.cmdline[:140] + ("…" if len(entry.cmdline) > 140 else ""))
            cmd_lbl.setObjectName("CmdPill")
            cmd_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            outer.addWidget(cmd_lbl)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch()

        if entry.proto == "TCP":
            open_btn = GlowButton("↗  Open", glow_hex=palette.accent, max_blur=14.0)
            open_btn.setObjectName("RunAction")
            open_btn.clicked.connect(lambda: on_open(entry))
            actions.addWidget(open_btn)

        copy_btn = GlowButton("Copy URL", glow_hex=palette.accent, max_blur=12.0)
        copy_btn.setObjectName("CardAction")
        copy_btn.clicked.connect(lambda: on_copy(entry))
        actions.addWidget(copy_btn)

        if entry.pid:
            kill_btn = GlowButton("Kill Process", glow_hex=palette.danger, max_blur=16.0)
            kill_btn.setObjectName("DangerAction")
            kill_btn.clicked.connect(lambda: on_kill(entry))
            actions.addWidget(kill_btn)

        outer.addLayout(actions)


class PortWatchWindow(QMainWindow):
    def __init__(self, watcher: ThemeWatcher) -> None:
        super().__init__()
        self.watcher = watcher
        self.palette_data: ThemePalette = watcher.palette
        self.entries: list[pw.PortEntry] = []
        self.active_filter = "all"
        self._glow_buttons: list[GlowButton] = []

        self.setWindowTitle("PortWatch — Live Linux Ports")
        self.resize(960, 660)
        self.setMinimumSize(760, 520)

        self._build_ui()
        self._bind_shortcuts()
        self.apply_theme(self.palette_data)
        self.watcher.theme_changed.connect(self.apply_theme)

        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(3000)
        self._auto_timer.timeout.connect(self.refresh_ports)
        self._auto_timer.start()

        QTimer.singleShot(30, self.refresh_ports)

    def _btn(self, text: str, obj_name: str = "", blur: float = 16.0) -> GlowButton:
        b = GlowButton(text, glow_hex=self.palette_data.accent, max_blur=blur)
        if obj_name:
            b.setObjectName(obj_name)
        self._glow_buttons.append(b)
        return b

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(14)

        # Header Card
        header_card = QFrame()
        header_card.setObjectName("HeaderCard")
        hl = QHBoxLayout(header_card)
        hl.setContentsMargins(20, 16, 20, 16)
        hl.setSpacing(14)

        logo = QLabel("⚡")
        logo.setObjectName("LogoBadge")
        logo.setFixedSize(44, 44)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(logo)

        tcol = QVBoxLayout()
        tcol.setSpacing(2)
        t = QLabel("PortWatch")
        t.setObjectName("TitleLabel")
        sub = QLabel("Live Linux listening ports, processes & quick actions")
        sub.setObjectName("SubtitleLabel")
        tcol.addWidget(t)
        tcol.addWidget(sub)
        hl.addLayout(tcol)

        hl.addStretch()

        self.count_pill = QLabel("0 Ports")
        self.count_pill.setObjectName("StatPill")
        self.lan_pill = QLabel("0 LAN")
        self.lan_pill.setObjectName("StatPill")
        hl.addWidget(self.count_pill)
        hl.addWidget(self.lan_pill)

        self.auto_check = QCheckBox("Live (3s)")
        self.auto_check.setChecked(True)
        self.auto_check.toggled.connect(self._toggle_auto)
        hl.addWidget(self.auto_check)

        refresh_btn = self._btn("↻  Refresh", obj_name="PrimaryButton", blur=20.0)
        refresh_btn.clicked.connect(self.refresh_ports)
        hl.addWidget(refresh_btn)
        root.addWidget(header_card)

        # Search + Filters
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by port (e.g. 3000), process name, or command... (Ctrl+F)")
        self.search_input.textChanged.connect(self._render)
        ctrl.addWidget(self.search_input, 1)

        self._filter_btns: dict[str, GlowButton] = {}
        for key, label in (("all", "All"), ("tcp", "TCP"), ("udp", "UDP"), ("lan", "LAN Exposed")):
            fb = self._btn(label, obj_name="ChipButton", blur=12.0)
            fb.setCheckable(True)
            fb.setChecked(key == "all")
            fb.clicked.connect(lambda checked, k=key: self._set_filter(k))
            ctrl.addWidget(fb)
            self._filter_btns[key] = fb
        root.addLayout(ctrl)

        # Toast
        self.toast = QFrame()
        self.toast.setObjectName("ToastBanner")
        tl = QHBoxLayout(self.toast)
        tl.setContentsMargins(14, 8, 14, 8)
        self.toast_lbl = QLabel("")
        self.toast_lbl.setStyleSheet("font-weight: 600;")
        tl.addWidget(self.toast_lbl)
        self.toast.hide()
        root.addWidget(self.toast)

        # Scroll list
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.cards_layout = QVBoxLayout(self.container)
        self.cards_layout.setContentsMargins(2, 2, 6, 6)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)

        # Footer
        footer = QHBoxLayout()
        self.status_lbl = QLabel("Ready")
        self.status_lbl.setObjectName("SubtitleLabel")
        self.theme_lbl = QLabel("")
        self.theme_lbl.setObjectName("SubtitleLabel")
        support_btn = self._btn("☕  Support", obj_name="ChipButton", blur=14.0)
        support_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://buymeacoffee.com/aurorauap")))
        footer.addWidget(self.status_lbl)
        footer.addStretch()
        footer.addWidget(self.theme_lbl)
        footer.addWidget(support_btn)
        root.addLayout(footer)

    def _bind_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+F"), self, self.search_input.setFocus)
        QShortcut(QKeySequence("Ctrl+R"), self, self.refresh_ports)
        QShortcut(QKeySequence("F5"), self, self.refresh_ports)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)

    def _toggle_auto(self, enabled: bool) -> None:
        if enabled:
            self._auto_timer.start()
        else:
            self._auto_timer.stop()

    def _set_filter(self, key: str) -> None:
        self.active_filter = key
        for k, b in self._filter_btns.items():
            b.setChecked(k == key)
        self._render()

    def _show_toast(self, msg: str) -> None:
        self.toast_lbl.setText(msg)
        self.toast.show()
        QTimer.singleShot(3500, self.toast.hide)

    def apply_theme(self, palette: ThemePalette) -> None:
        self.palette_data = palette
        app = QApplication.instance()
        if app:
            app.setStyleSheet(build_stylesheet(palette))
        for b in self._glow_buttons:
            b.update_glow_color(palette.accent)
        self.theme_lbl.setText(f"{palette.source_name} ({palette.mode}) · {palette.accent}")
        self._render()

    def refresh_ports(self) -> None:
        try:
            self.entries = pw.list_listening_ports()
            lan_n = sum(1 for e in self.entries if e.exposed)
            self.count_pill.setText(f"{len(self.entries)} Ports")
            self.lan_pill.setText(f"{lan_n} LAN")
            self.status_lbl.setText(f"Updated · {len(self.entries)} listening socket(s)")
            self._render()
        except Exception as exc:
            self._show_toast(f"Error: {exc}")

    def _render(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        q = self.search_input.text().strip().lower()
        shown = []
        for e in self.entries:
            if self.active_filter == "tcp" and e.proto != "TCP":
                continue
            if self.active_filter == "udp" and e.proto != "UDP":
                continue
            if self.active_filter == "lan" and not e.exposed:
                continue
            if q and q not in f"{e.port} {e.process} {e.address} {e.cmdline} {e.pid}".lower():
                continue
            shown.append(e)

        if not shown:
            lbl = QLabel("No matching listening ports found.")
            lbl.setObjectName("SubtitleLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards_layout.addSpacing(30)
            self.cards_layout.addWidget(lbl)
            self.cards_layout.addStretch()
            return

        for entry in shown:
            self.cards_layout.addWidget(
                PortCard(
                    entry=entry,
                    palette=self.palette_data,
                    on_open=lambda e: QDesktopServices.openUrl(QUrl(e.url)),
                    on_copy=self._copy_url,
                    on_kill=self._kill_entry,
                )
            )
        self.cards_layout.addStretch()

    def _copy_url(self, entry: pw.PortEntry) -> None:
        QApplication.clipboard().setText(entry.url)
        self._show_toast(f"Copied {entry.url}")

    def _kill_entry(self, entry: pw.PortEntry) -> None:
        if not entry.pid:
            return
        reply = QMessageBox.question(
            self,
            "Terminate Process",
            f"Send SIGTERM to '{entry.process}' (PID {entry.pid}) listening on :{entry.port}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            msg = pw.kill_process(entry.pid)
            self._show_toast(msg)
            QTimer.singleShot(300, self.refresh_ports)
        except Exception as exc:
            self._show_toast(f"Error: {exc}")


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("PortWatch")
    app.setDesktopFileName("portwatch")
    watcher = ThemeWatcher(app)
    win = PortWatchWindow(watcher)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
