"""Settings live in config/*.yml; code reads them here and nowhere else."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"


@cache
def load(name: str) -> dict[str, Any]:
    path = CONFIG / f"{name}.yml"
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict), path
    return data


def site(name: str = "plant") -> dict[str, Any]:
    return load(f"sites/{name}")
