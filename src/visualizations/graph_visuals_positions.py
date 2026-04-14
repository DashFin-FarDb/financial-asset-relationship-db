"""Position normalization helpers for graph visualizations."""

import math
from typing import Sequence, Tuple

Position3D = Tuple[float, float, float]
PositionMatrix = list[Position3D]


def _as_sequence(value: object, error_message: str) -> Sequence[object]:
    """Return value as non-string sequence or raise ValueError."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(error_message)
    return value


def _parse_position_value(value: object) -> float:
    """Parse one position component as float with clear error."""
    if not isinstance(value, (int, float, str, bytes, bytearray)):
        raise ValueError("Invalid positions: values must be numeric")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid positions: values must be numeric") from exc


def _normalize_position_row(row: object) -> Position3D:
    """Normalize one position row and validate shape/finite values."""
    row_seq = _as_sequence(row, "Invalid positions shape: expected (n, 3)")
    if len(row_seq) != 3:
        raise ValueError("Invalid positions shape: expected (n, 3)")
    x = _parse_position_value(row_seq[0])
    y = _parse_position_value(row_seq[1])
    z = _parse_position_value(row_seq[2])
    if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
        raise ValueError("Invalid positions: values must be finite numbers")
    return x, y, z


def _normalize_positions(positions: object) -> PositionMatrix:
    """Normalize positions to a finite numeric (n, 3) matrix."""
    rows = _as_sequence(positions, "positions must be a sequence of 3D coordinates")
    return [_normalize_position_row(row) for row in rows]
