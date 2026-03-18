from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .config import AppConfig, effective_thresholds, load_config, save_config
from .engine import EngineFrame, PostureEngine
from .overlay import WarningOverlay
from .qt_utils import bgr_to_qimage
from .settings_dialog import SettingsDialog


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Smart Posture Tracker")
        self.resize(980, 620)

        self._cfg: AppConfig = load_config()
        self._engine = PostureEngine(self._cfg)
        self._overlay = WarningOverlay()
        self._overlay.set_show_text(self._cfg.overlay.show_text)
        self._overlay.clicked.connect(self._show_settings)

        self._settings: Optional[SettingsDialog] = None
        self._overlay_was_active: bool = False
        self._engine_running: bool = False

        self._build_ui()
        self._wire_signals()

        self._apply_overlay_position()
        # Start posture tracking automatically on launch
        QtCore.QTimer.singleShot(0, self._start_engine)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        self._engine.stop()
        self._overlay.hide()
        event.accept()

    def _graceful_quit(self) -> None:
        self._engine.stop()
        self._overlay.hide()
        QtCore.QTimer.singleShot(0, self.close)

    def _start_engine(self) -> None:
        if self._cfg.show_preview:
            self._set_preview_message("Starting…")
        self._engine.start()

    def _stop_engine(self) -> None:
        # Hide overlay immediately (stop is async).
        self._overlay.hide()
        self._overlay_was_active = False
        self._engine_running = False
        self._engine.stop()

    def _set_preview_message(self, text: str) -> None:
        # QLabel shows the pixmap over the text, so we must clear it.
        self._preview.setPixmap(QtGui.QPixmap())
        self._preview.setText(text)

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        layout = QtWidgets.QHBoxLayout(central)
        left = QtWidgets.QVBoxLayout()
        right = QtWidgets.QVBoxLayout()
        layout.addLayout(left, 3)
        layout.addLayout(right, 2)

        self._preview = QtWidgets.QLabel(central)
        self._preview.setMinimumSize(520, 360)
        self._preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet("background:#111; color:#ddd; border-radius:8px;")
        self._set_preview_message("Preview disabled")
        left.addWidget(self._preview, 1)

        status_row = QtWidgets.QHBoxLayout()
        self._status = QtWidgets.QLabel("Initializing…", central)
        self._status.setStyleSheet("font-size: 14px; font-weight: 600;")
        status_row.addWidget(self._status, 1)
        left.addLayout(status_row)

        self._metrics = QtWidgets.QLabel("gap: —   tilt: —   z: —", central)
        self._metrics.setStyleSheet("color:#000;")
        self._metrics.setTextFormat(QtCore.Qt.TextFormat.RichText)
        left.addWidget(self._metrics)

        self._metrics_help = QtWidgets.QLabel(central)
        self._metrics_help.setWordWrap(True)
        self._metrics_help.setStyleSheet("color:#555; font-size: 11px;")
        self._metrics_help.setText(
            "gap: vertical distance from shoulders to ears (slouching lowers it)\n"
            "tilt: difference between left and right shoulder height (side lean)\n"
            "z: how far your head is from the camera (forward head posture)"
        )
        left.addWidget(self._metrics_help)

        controls = QtWidgets.QGroupBox("Controls", central)
        right.addWidget(controls)
        form = QtWidgets.QFormLayout(controls)

        self._btn_start = QtWidgets.QPushButton("Start", controls)
        self._btn_stop = QtWidgets.QPushButton("Stop", controls)
        self._btn_quit = QtWidgets.QPushButton("Quit", controls)
        self._btn_stop.setEnabled(False)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self._btn_start)
        row.addWidget(self._btn_stop)
        row.addWidget(self._btn_quit)
        form.addRow(row)

        self._chk_preview = QtWidgets.QCheckBox("Show preview", controls)
        self._chk_preview.setChecked(self._cfg.show_preview)
        form.addRow(self._chk_preview)

        self._btn_settings = QtWidgets.QPushButton("Settings…", controls)
        form.addRow(self._btn_settings)

        self._needs_calib = QtWidgets.QLabel("", central)
        self._needs_calib.setWordWrap(True)
        self._needs_calib.setStyleSheet("color:#a85;")
        right.addWidget(self._needs_calib)

        right.addStretch(1)

        menu = self.menuBar().addMenu("&App")
        act_settings = QtGui.QAction("Settings…", self)
        act_settings.triggered.connect(self._show_settings)
        menu.addAction(act_settings)
        act_quit = QtGui.QAction("Quit", self)
        act_quit.triggered.connect(self.close)
        menu.addAction(act_quit)

        self._btn_start.clicked.connect(self._start_engine)
        self._btn_stop.clicked.connect(self._stop_engine)
        self._btn_quit.clicked.connect(self._graceful_quit)
        self._btn_settings.clicked.connect(self._show_settings)
        self._chk_preview.toggled.connect(self._on_preview_toggled)

        self._refresh_calibration_banner()

    def _wire_signals(self) -> None:
        self._engine.status_ready.connect(self._status.setText)
        self._engine.metrics_ready.connect(self._on_metrics)
        self._engine.frame_ready.connect(self._on_frame)
        self._engine.alert_changed.connect(self._on_alert)
        self._engine.calibrated.connect(self._on_calibrated)
        self._engine.running_changed.connect(self._on_running)
        self._engine.error.connect(self._on_error)

    def _on_running(self, running: bool) -> None:
        self._engine_running = bool(running)
        self._btn_start.setEnabled(not running)
        self._btn_stop.setEnabled(running)
        if not running:
            self._set_preview_message("Stopped")
            self._overlay.hide()
            self._overlay_was_active = False

    def _on_preview_toggled(self, enabled: bool) -> None:
        self._engine.set_show_preview(bool(enabled))
        if not enabled:
            self._set_preview_message("Preview disabled")
        elif self._btn_stop.isEnabled():
            # Engine is running; show something until next frame arrives.
            self._set_preview_message("Starting…")

    def _on_error(self, msg: str) -> None:
        QtWidgets.QMessageBox.critical(self, "Error", msg)

    def _on_metrics(self, gap: float, tilt: float, z: float) -> None:
        thresholds = effective_thresholds(self._cfg)
        gap_bad = gap < thresholds.gap
        tilt_bad = tilt > thresholds.tilt
        z_bad = z < thresholds.z

        def fmt(value: float, bad: bool) -> str:
            color = "#ff5555" if bad else "#000000"
            return f"<span style='color:{color};'>{value:.4f}</span>"

        text = (
            f"gap: {fmt(gap, gap_bad)}   "
            f"tilt: {fmt(tilt, tilt_bad)}   "
            f"z: {fmt(z, z_bad)}"
        )
        self._metrics.setText(text)
        if self._settings and not self._cfg.is_calibrated:
            self._settings.set_calibration_status(
                "Calibration sets your baseline thresholds.\n"
                "Sit with good posture and hold still while the app samples."
            )

    def _on_frame(self, frame: EngineFrame) -> None:
        if not self._cfg.show_preview:
            self._set_preview_message("Preview disabled")
            return
        img = bgr_to_qimage(frame.bgr)
        if img is None:
            return
        pix = QtGui.QPixmap.fromImage(img)
        self._preview.setPixmap(
            pix.scaled(self._preview.size(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        )

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._preview.pixmap() is not None:
            pm = self._preview.pixmap()
            if pm:
                self._preview.setPixmap(
                    pm.scaled(
                        self._preview.size(),
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation,
                    )
                )

    def _on_alert(self, active: bool) -> None:
        # During/after stop we may still receive queued alert signals; never show overlay unless running.
        if not self._engine_running:
            self._overlay.hide()
            self._overlay_was_active = False
            return
        if not self._cfg.overlay.enabled:
            self._overlay.hide()
            self._overlay_was_active = False
            return
        if active:
            self._apply_overlay_position()
            self._overlay.show()
            if not self._overlay_was_active and self._cfg.overlay.sound_enabled:
                QtWidgets.QApplication.beep()
        else:
            self._overlay.hide()
        self._overlay_was_active = bool(active)

    def _on_calibrated(self, thresholds) -> None:
        self._cfg.is_calibrated = True
        self._cfg.calibrated_thresholds = thresholds
        # Use calibrated values as the new manual defaults so users can tweak from baseline.
        self._cfg.manual_thresholds = thresholds
        save_config(self._cfg)
        self._refresh_calibration_banner()
        if self._settings:
            self._settings.set_calibration_status("Calibration complete.")
            self._settings.set_calibrated_thresholds(thresholds)

    def _refresh_calibration_banner(self) -> None:
        if self._cfg.is_calibrated:
            self._needs_calib.setText("")
        else:
            self._needs_calib.setText("Calibration recommended: open Settings → Calibration.")

    def _apply_overlay_position(self) -> None:
        screen = QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        margin = 18
        size = self._overlay.size()

        pos = self._cfg.overlay.position
        if pos == "top_left":
            x, y = geo.left() + margin, geo.top() + margin
        elif pos == "bottom_left":
            x, y = geo.left() + margin, geo.bottom() - size.height() - margin
        elif pos == "bottom_right":
            x, y = geo.right() - size.width() - margin, geo.bottom() - size.height() - margin
        else:
            x, y = geo.right() - size.width() - margin, geo.top() + margin
        self._overlay.move(x, y)

    def _show_settings(self) -> None:
        if self._settings is None:
            self._settings = SettingsDialog(self._cfg, parent=self)
            self._settings.start_calibration.connect(self._engine.start_calibration)
            self._settings.use_manual_changed.connect(self._engine.set_use_manual_thresholds)
            self._settings.manual_thresholds_changed.connect(self._engine.set_manual_thresholds)
            self._settings.grace_period_changed.connect(self._engine.set_grace_period_seconds)
            self._settings.overlay_show_text_changed.connect(self._on_overlay_text_changed)
            self._settings.overlay_enabled_changed.connect(self._on_overlay_enabled_changed)
            self._settings.overlay_sound_changed.connect(self._on_overlay_sound_changed)

        self._settings.show()
        self._settings.raise_()
        self._settings.activateWindow()

    def _on_overlay_text_changed(self, enabled: bool) -> None:
        self._cfg.overlay.show_text = bool(enabled)
        save_config(self._cfg)
        self._overlay.set_show_text(bool(enabled))

    def _on_overlay_enabled_changed(self, enabled: bool) -> None:
        self._cfg.overlay.enabled = bool(enabled)
        save_config(self._cfg)
        if not enabled:
            self._overlay.hide()
            self._overlay_was_active = False

    def _on_overlay_sound_changed(self, enabled: bool) -> None:
        self._cfg.overlay.sound_enabled = bool(enabled)
        save_config(self._cfg)

