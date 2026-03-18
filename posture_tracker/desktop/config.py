from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .resources import appdata_dir


@dataclass
class OverlayConfig:
    enabled: bool = True
    position: str = "top_right"  # top_right | top_left | bottom_right | bottom_left
    always_on_top: bool = True
    show_text: bool = False
    sound_enabled: bool = True


@dataclass
class Thresholds:
    gap: float = 0.20
    z: float = -1.10
    tilt: float = 0.06


@dataclass
class AppConfig:
    camera_index: int = 0
    show_preview: bool = True
    grace_period_seconds: float = 3.0
    use_manual_thresholds: bool = False
    manual_thresholds: Thresholds = field(default_factory=Thresholds)
    calibrated_thresholds: Thresholds = field(default_factory=Thresholds)
    is_calibrated: bool = False
    overlay: OverlayConfig = field(default_factory=OverlayConfig)


def _coerce_thresholds(value: Any) -> Thresholds:
    if isinstance(value, Thresholds):
        return value
    if isinstance(value, dict):
        return Thresholds(
            gap=float(value.get("gap", 0.20)),
            z=float(value.get("z", -1.10)),
            tilt=float(value.get("tilt", 0.06)),
        )
    return Thresholds()


def _coerce_overlay(value: Any) -> OverlayConfig:
    if isinstance(value, OverlayConfig):
        return value
    if isinstance(value, dict):
        return OverlayConfig(
            enabled=bool(value.get("enabled", True)),
            position=str(value.get("position", "top_right")),
            always_on_top=bool(value.get("always_on_top", True)),
            show_text=bool(value.get("show_text", False)),
            sound_enabled=bool(value.get("sound_enabled", True)),
        )
    return OverlayConfig()


def config_path() -> Path:
    return appdata_dir() / "config.json"


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        return AppConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return AppConfig()

    cfg = AppConfig()
    cfg.camera_index = int(raw.get("camera_index", cfg.camera_index))
    cfg.show_preview = bool(raw.get("show_preview", cfg.show_preview))
    cfg.grace_period_seconds = float(raw.get("grace_period_seconds", cfg.grace_period_seconds))
    cfg.use_manual_thresholds = bool(raw.get("use_manual_thresholds", cfg.use_manual_thresholds))
    cfg.manual_thresholds = _coerce_thresholds(raw.get("manual_thresholds", {}))
    cfg.calibrated_thresholds = _coerce_thresholds(raw.get("calibrated_thresholds", {}))
    cfg.is_calibrated = bool(raw.get("is_calibrated", cfg.is_calibrated))
    cfg.overlay = _coerce_overlay(raw.get("overlay", {}))
    return cfg


def save_config(cfg: AppConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = asdict(cfg)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def effective_thresholds(cfg: AppConfig) -> Thresholds:
    if cfg.use_manual_thresholds:
        return cfg.manual_thresholds
    if cfg.is_calibrated:
        return cfg.calibrated_thresholds
    return Thresholds()

