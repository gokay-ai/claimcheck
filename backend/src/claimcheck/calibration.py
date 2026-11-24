"""Measured behaviour of the marking rule, produced by the pilot evaluation."""

from __future__ import annotations

from pathlib import Path

from .schemas import Calibration


def load_calibration(data_dir: Path) -> Calibration:
    return Calibration.model_validate_json(
        (data_dir / "calibration.json").read_text(encoding="utf-8")
    )
