"""Screen-aware UI scale factor. Call init() once after QApplication is created."""

from __future__ import annotations

import re

_factor: float = 1.0


def init(factor: float) -> None:
    global _factor
    _factor = max(0.5, min(factor, 2.0))


def factor() -> float:
    return _factor


def px(value: int) -> int:
    return round(value * _factor)


def style(css: str) -> str:
    """Return css with all font-size: Xpx values scaled by the current factor."""

    def _scale(m: re.Match) -> str:
        return f"font-size: {round(int(m.group(1)) * _factor)}px"

    return re.sub(r"font-size:\s*(\d+)px", _scale, css)
