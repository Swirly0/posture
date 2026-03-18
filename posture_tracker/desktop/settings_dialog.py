from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from .config import AppConfig, Thresholds, save_config


class SettingsDialog(QtWidgets.QDialog):
    start_calibration = QtCore.Signal()
    use_manual_changed = QtCore.Signal(bool)
    manual_thresholds_changed = QtCore.Signal(float, float, float)  # gap, z, tilt
    grace_period_changed = QtCore.Signal(float)
    overlay_show_text_changed = QtCore.Signal(bool)
    overlay_enabled_changed = QtCore.Signal(bool)
    overlay_sound_changed = QtCore.Signal(bool)

    def __init__(self, cfg: AppConfig, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self._cfg = cfg

        self._tabs = QtWidgets.QTabWidget(self)
        self._calibration_tab = QtWidgets.QWidget(self)
        self._tuning_tab = QtWidgets.QWidget(self)
        self._tabs.addTab(self._calibration_tab, "Calibration")
        self._tabs.addTab(self._tuning_tab, "Tuning")

        self._build_calibration_tab()
        self._build_tuning_tab()

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close, parent=self
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(buttons)

    def _build_calibration_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self._calibration_tab)

        self._calib_status = QtWidgets.QLabel(self._calibration_tab)
        self._calib_status.setText(
            "Calibration sets your baseline thresholds.\n"
            "Sit with good posture and hold still while the app samples."
        )

        self._btn_calibrate = QtWidgets.QPushButton("Start calibration", self._calibration_tab)
        self._btn_calibrate.clicked.connect(self.start_calibration.emit)

        layout.addWidget(self._calib_status)
        layout.addSpacing(8)
        layout.addWidget(self._btn_calibrate)
        layout.addStretch(1)

    def _build_tuning_tab(self) -> None:
        outer = QtWidgets.QHBoxLayout(self._tuning_tab)

        left = QtWidgets.QVBoxLayout()
        right = QtWidgets.QVBoxLayout()
        outer.addLayout(left, 2)
        outer.addLayout(right, 1)

        group_detect = QtWidgets.QGroupBox("Detection", self._tuning_tab)
        left.addWidget(group_detect)
        form = QtWidgets.QFormLayout(group_detect)

        self._use_manual = QtWidgets.QCheckBox("Use manual thresholds", group_detect)
        self._use_manual.setChecked(self._cfg.use_manual_thresholds)
        self._use_manual.toggled.connect(self._on_use_manual_toggled)
        form.addRow(self._use_manual)

        self._spin_gap = QtWidgets.QDoubleSpinBox(group_detect)
        self._spin_gap.setRange(0.0, 1.0)
        self._spin_gap.setDecimals(4)
        self._spin_gap.setSingleStep(0.005)

        self._spin_z = QtWidgets.QDoubleSpinBox(group_detect)
        self._spin_z.setRange(-5.0, 5.0)
        self._spin_z.setDecimals(4)
        self._spin_z.setSingleStep(0.01)

        self._spin_tilt = QtWidgets.QDoubleSpinBox(group_detect)
        self._spin_tilt.setRange(0.0, 1.0)
        self._spin_tilt.setDecimals(4)
        self._spin_tilt.setSingleStep(0.005)

        self._load_manual_values()
        self._spin_gap.valueChanged.connect(self._emit_manual_thresholds)
        self._spin_z.valueChanged.connect(self._emit_manual_thresholds)
        self._spin_tilt.valueChanged.connect(self._emit_manual_thresholds)

        form.addRow("Gap threshold", self._spin_gap)
        form.addRow("Z-depth threshold", self._spin_z)
        form.addRow("Tilt threshold", self._spin_tilt)

        self._spin_grace = QtWidgets.QDoubleSpinBox(group_detect)
        self._spin_grace.setRange(0.0, 60.0)
        self._spin_grace.setDecimals(1)
        self._spin_grace.setSingleStep(0.5)
        self._spin_grace.setValue(float(self._cfg.grace_period_seconds))
        self._spin_grace.valueChanged.connect(self._on_grace_changed)
        form.addRow("Grace period (seconds)", self._spin_grace)

        group_overlay = QtWidgets.QGroupBox("Overlay", self._tuning_tab)
        right.addWidget(group_overlay)
        overlay_form = QtWidgets.QFormLayout(group_overlay)

        self._overlay_enabled = QtWidgets.QCheckBox("Enable warning overlay", group_overlay)
        self._overlay_enabled.setChecked(self._cfg.overlay.enabled)
        self._overlay_enabled.toggled.connect(self._on_overlay_enabled)
        overlay_form.addRow(self._overlay_enabled)

        self._overlay_text = QtWidgets.QCheckBox("Show text under icon", group_overlay)
        self._overlay_text.setChecked(self._cfg.overlay.show_text)
        self._overlay_text.toggled.connect(self._on_overlay_text)
        overlay_form.addRow(self._overlay_text)

        self._overlay_sound = QtWidgets.QCheckBox("Play sound when warning appears", group_overlay)
        self._overlay_sound.setChecked(self._cfg.overlay.sound_enabled)
        self._overlay_sound.toggled.connect(self._on_overlay_sound)
        overlay_form.addRow(self._overlay_sound)

        right.addStretch(1)

        self._set_manual_controls_enabled(self._cfg.use_manual_thresholds)

    def set_calibration_status(self, text: str) -> None:
        self._calib_status.setText(text)

    def set_calibrated_thresholds(self, t: Thresholds) -> None:
        self._cfg.calibrated_thresholds = t
        # Also update manual defaults so users can tweak after calibrating.
        self._cfg.manual_thresholds = t
        self._cfg.is_calibrated = True
        save_config(self._cfg)
        # Reflect new defaults in the tuning tab without emitting change signals.
        with QtCore.QSignalBlocker(self._spin_gap):
            self._spin_gap.setValue(float(t.gap))
        with QtCore.QSignalBlocker(self._spin_z):
            self._spin_z.setValue(float(t.z))
        with QtCore.QSignalBlocker(self._spin_tilt):
            self._spin_tilt.setValue(float(t.tilt))

    def _load_manual_values(self) -> None:
        t = self._cfg.manual_thresholds
        self._spin_gap.setValue(float(t.gap))
        self._spin_z.setValue(float(t.z))
        self._spin_tilt.setValue(float(t.tilt))

    def _set_manual_controls_enabled(self, enabled: bool) -> None:
        for w in (self._spin_gap, self._spin_z, self._spin_tilt):
            w.setEnabled(bool(enabled))

    def _on_use_manual_toggled(self, enabled: bool) -> None:
        self._cfg.use_manual_thresholds = bool(enabled)
        save_config(self._cfg)
        self._set_manual_controls_enabled(enabled)
        self.use_manual_changed.emit(bool(enabled))
        self._emit_manual_thresholds()

    def _on_grace_changed(self, value: float) -> None:
        seconds = max(0.0, float(value))
        self._cfg.grace_period_seconds = seconds
        save_config(self._cfg)
        self.grace_period_changed.emit(seconds)

    def _emit_manual_thresholds(self) -> None:
        gap = float(self._spin_gap.value())
        z = float(self._spin_z.value())
        tilt = float(self._spin_tilt.value())
        self._cfg.manual_thresholds = Thresholds(gap=gap, z=z, tilt=tilt)
        save_config(self._cfg)
        self.manual_thresholds_changed.emit(gap, z, tilt)

    def _on_overlay_text(self, enabled: bool) -> None:
        self._cfg.overlay.show_text = bool(enabled)
        save_config(self._cfg)
        self.overlay_show_text_changed.emit(bool(enabled))

    def _on_overlay_enabled(self, enabled: bool) -> None:
        self._cfg.overlay.enabled = bool(enabled)
        save_config(self._cfg)
        self.overlay_enabled_changed.emit(bool(enabled))

    def _on_overlay_sound(self, enabled: bool) -> None:
        self._cfg.overlay.sound_enabled = bool(enabled)
        save_config(self._cfg)
        self.overlay_sound_changed.emit(bool(enabled))

