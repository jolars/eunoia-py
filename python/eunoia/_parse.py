"""Input parsing and inclusive/exclusive area conversion helpers."""

from __future__ import annotations

from collections.abc import Mapping


def canonicalize(combo: str) -> str:
    """Return ``combo`` in canonical form: trim, drop empty parts, sort,
    rejoin with ``&``. Matches the eunoia core's Combination::Display."""
    parts = sorted(s.strip() for s in combo.split("&") if s.strip())
    if not parts:
        raise ValueError(f"invalid_combination: {combo!r}")
    return "&".join(parts)


def parse_dict_input(values: Mapping[str, float]) -> list[tuple[str, float]]:
    """Convert a user-supplied dict to ``[(combo, area), ...]`` for the
    Rust binding, validating each combination label."""
    out: list[tuple[str, float]] = []
    for key, val in values.items():
        canonicalize(key)
        out.append((key, float(val)))
    return out


def to_inclusive(
    fitted_exclusive: Mapping[str, float],
    keys: list[str],
) -> dict[str, float]:
    """For each key X, sum the fitted exclusive areas of every region that is
    a superset of X. Used to express fitted areas in the user's input scale
    when ``input="union"``."""
    result: dict[str, float] = {}
    for k in keys:
        x_sets = frozenset(s.strip() for s in k.split("&") if s.strip())
        total = 0.0
        for combo, val in fitted_exclusive.items():
            y_sets = frozenset(s.strip() for s in combo.split("&") if s.strip())
            if x_sets <= y_sets:
                total += val
        result[k] = total
    return result
