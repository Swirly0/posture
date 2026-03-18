from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .config import Thresholds


@dataclass
class EvalOutput:
    posture_status: str
    alert_active: bool
    is_calibrated: bool
    calibrated_thresholds: Optional[Thresholds] = None


@dataclass
class PostureEvaluator:
    calibration_samples_needed: int = 30
    bad_posture_grace_seconds: float = 3.0
    hysteresis_off_seconds: float = 0.4

    # (gap, tilt, z_depth)
    _calibration_data: List[Tuple[float, float, float]] = field(default_factory=list)
    _is_calibrating: bool = False
    _is_calibrated: bool = False
    _bad_start: Optional[float] = None
    _alert_active: bool = False
    _last_good_time: Optional[float] = None

    thresholds: Thresholds = field(default_factory=Thresholds)

    def start_calibration(self) -> None:
        self._calibration_data.clear()
        self._is_calibrating = True
        self._is_calibrated = False
        self._bad_start = None
        self._alert_active = False
        self._last_good_time = None

    def set_calibrated_thresholds(self, thresholds: Thresholds, is_calibrated: bool) -> None:
        self.thresholds = thresholds
        self._is_calibrated = is_calibrated
        self._is_calibrating = False

    @property
    def is_calibrating(self) -> bool:
        return self._is_calibrating

    @property
    def calibration_progress(self) -> Tuple[int, int]:
        return len(self._calibration_data), self.calibration_samples_needed

    def _finish_calibration(self) -> Thresholds:
        n = max(1, len(self._calibration_data))
        avg_gap = sum(g for g, t, z in self._calibration_data) / n
        avg_tilt = sum(t for g, t, z in self._calibration_data) / n
        avg_z = sum(z for g, t, z in self._calibration_data) / n

        # Tilt is considered "bad" when tilt > threshold. Set the calibrated tilt
        # above the baseline to allow natural asymmetry/jitter.
        calibrated_tilt = max(avg_tilt * 2.0, avg_tilt + 0.015)
        calibrated = Thresholds(
            gap=avg_gap * 0.85,
            z=avg_z * 1.30,
            tilt=calibrated_tilt,
        )
        self.thresholds = calibrated
        self._is_calibrated = True
        self._is_calibrating = False
        self._calibration_data.clear()
        return calibrated

    def update(self, gap: float, tilt: float, z_depth: float, thresholds: Thresholds) -> EvalOutput:
        self.thresholds = thresholds

        if self._is_calibrating:
            self._calibration_data.append((gap, tilt, z_depth))
            done, total = self.calibration_progress
            if done >= total:
                calibrated = self._finish_calibration()
                return EvalOutput(
                    posture_status="Calibrated",
                    alert_active=False,
                    is_calibrated=True,
                    calibrated_thresholds=calibrated,
                )
            return EvalOutput(
                posture_status=f"CALIBRATING... Hold Still ({done}/{total})",
                alert_active=False,
                is_calibrated=False,
            )

        is_bad = (z_depth < thresholds.z) or (gap < thresholds.gap) or (tilt > thresholds.tilt)
        now = time.time()

        if is_bad:
            self._last_good_time = None
            if self._bad_start is None:
                self._bad_start = now
            elapsed = now - self._bad_start
            if elapsed >= self.bad_posture_grace_seconds:
                self._alert_active = True
                return EvalOutput(
                    posture_status=f"WARNING: FIX POSTURE! ({int(elapsed)}s)",
                    alert_active=True,
                    is_calibrated=self._is_calibrated,
                )
            self._alert_active = False
            return EvalOutput(
                posture_status="Good (grace period)",
                alert_active=False,
                is_calibrated=self._is_calibrated,
            )

        self._bad_start = None
        if self._alert_active:
            if self._last_good_time is None:
                self._last_good_time = now
            if (now - self._last_good_time) < self.hysteresis_off_seconds:
                return EvalOutput(
                    posture_status="Good Posture",
                    alert_active=True,
                    is_calibrated=self._is_calibrated,
                )
            self._alert_active = False

        self._last_good_time = None
        return EvalOutput(
            posture_status="Good Posture",
            alert_active=False,
            is_calibrated=self._is_calibrated,
        )

