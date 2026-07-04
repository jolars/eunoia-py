"""Input parsing and inclusive/exclusive area conversion helpers."""

from __future__ import annotations

from collections.abc import Collection, Mapping

_MEMBERSHIP_TYPES = (list, tuple, set, frozenset)


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


def is_membership_input(values: Mapping[str, object]) -> bool:
    """Return ``True`` when ``values`` maps set names to membership collections
    (``list``/``tuple``/``set``/``frozenset``) rather than to region areas.

    Raises ``ValueError`` if the values are *mixed* (some collections, some
    not), since that is ambiguous. An empty mapping returns ``False`` so the
    area path handles it as before."""
    if not values:
        return False
    flags = [isinstance(v, _MEMBERSHIP_TYPES) for v in values.values()]
    if all(flags):
        return True
    if any(flags):
        raise ValueError(
            "invalid_input: mix of membership collections and non-collections; "
            "values must be all areas or all membership lists"
        )
    return False


def parse_membership_input(
    values: Mapping[str, Collection[object]],
) -> tuple[list[tuple[str, float]], dict[str, list[str]]]:
    """Convert membership lists to exclusive region counts and member lists.

    Each element is assigned to the canonical combination of the sets it
    belongs to, then elements are counted per region. Elements are deduplicated
    within a set and stringified, so ``{"A": ["x", "x"], "B": [1]}`` is valid.
    Returns ``([(canonical_combo, count), ...], {canonical_combo: [member, ...]})``:
    the first for the Rust binding, the second (member names sorted within each
    region for reproducibility) for member labels."""
    membership: dict[str, set[str]] = {}
    for set_name, members in values.items():
        for element in set(members):
            membership.setdefault(str(element), set()).add(set_name)

    counts: dict[str, float] = {}
    members_map: dict[str, list[str]] = {}
    for element, sets in membership.items():
        if not sets:
            continue
        combo = canonicalize("&".join(sorted(sets)))
        counts[combo] = counts.get(combo, 0.0) + 1.0
        members_map.setdefault(combo, []).append(element)
    for names in members_map.values():
        names.sort()
    return list(counts.items()), members_map


def to_inclusive(
    fitted_exclusive: Mapping[str, float],
    keys: list[str],
) -> dict[str, float]:
    """For each key X, sum the fitted exclusive areas of every region that is
    a superset of X. Used to express fitted areas in the user's input scale
    when ``input="inclusive"``."""
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
