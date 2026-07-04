"""NumPy array (membership-matrix) input: the matrix idiom from eulerr.

A 2-D boolean ndarray where each column is a set and each row an observation
(a truthy cell denoting membership), or a 1-D array read as a single set. This
is the array cousin of the DataFrame path in :mod:`eunoia._dataframe`; both feed
the same pre-aggregated ``list[(combo, count)]`` to the core, and both go through
:func:`matrix_to_combinations` for the counting and canonicalization.

Unlike a DataFrame, a bare array carries no column names, so set names are taken
from the ``names=`` argument or generated (``A``, ``B``, … via
:func:`default_name`).
"""

from __future__ import annotations

import string
from collections.abc import Sequence
from typing import Any, TypeGuard

import numpy as np
import numpy.typing as npt

from eunoia._eunoia import EunoiaError
from eunoia._parse import canonicalize


def default_name(i: int) -> str:
    """Default set name for index ``i``: ``A``--``Z`` then ``set27``, ``set28``…

    Shared by ``venn(n)`` and array input so both name unnamed sets identically.
    """
    if i < len(string.ascii_uppercase):
        return string.ascii_uppercase[i]
    return f"set{i + 1}"


def is_ndarray(obj: object) -> TypeGuard[npt.NDArray[Any]]:
    """Return ``True`` for a numpy ``ndarray``; everything else passes through."""
    return isinstance(obj, np.ndarray)


def matrix_to_combinations(
    names: Sequence[str], matrix: npt.NDArray[np.bool_]
) -> list[tuple[str, float]]:
    """Count an ``(n_rows, n_sets)`` boolean matrix into ``[(combo, count)]``.

    Each unique row is assigned to the canonical region of the columns that are
    true; all-false rows (member of no set) are dropped. Shared by the DataFrame
    and numpy-array paths so canonicalization is identical for both."""
    uniq, counts = np.unique(matrix, axis=0, return_counts=True)
    out: dict[str, float] = {}
    for row, count in zip(uniq, counts, strict=True):
        sets = [names[i] for i in range(len(names)) if row[i]]
        if not sets:
            continue
        combo = canonicalize("&".join(sets))
        out[combo] = out.get(combo, 0.0) + float(count)
    return list(out.items())


def matrix_to_members(
    names: Sequence[str],
    matrix: npt.NDArray[np.bool_],
    ids: Sequence[object],
) -> dict[str, list[str]]:
    """Map each row's canonical region to its ``ids`` entry, keeping identities.

    Unlike :func:`matrix_to_combinations`, rows are *not* collapsed: every row
    contributes its id to the region of the columns that are true. All-false
    rows are dropped, ids are stringified, and each region's list is sorted for
    reproducibility. ``ids`` must have exactly one entry per row. Shared by the
    DataFrame and numpy-array member paths."""
    if len(ids) != matrix.shape[0]:
        raise EunoiaError(
            f"invalid_input: ids has {len(ids)} entries but the data has "
            f"{matrix.shape[0]} row(s)"
        )
    out: dict[str, list[str]] = {}
    for row, ident in zip(matrix, ids, strict=True):
        sets = [names[i] for i in range(len(names)) if row[i]]
        if not sets:
            continue
        combo = canonicalize("&".join(sets))
        out.setdefault(combo, []).append(str(ident))
    for members in out.values():
        members.sort()
    return out


def resolve_set_names(n_sets: int, names: Sequence[str] | None) -> list[str]:
    """Names for ``n_sets`` columns: generated if ``names is None``, else checked.

    A supplied ``names`` must have exactly ``n_sets`` unique entries."""
    if names is None:
        return [default_name(i) for i in range(n_sets)]
    resolved = [str(x) for x in names]
    if len(resolved) != n_sets:
        raise EunoiaError(
            f"invalid_input: names has {len(resolved)} entries but the array has "
            f"{n_sets} column(s)"
        )
    if len(set(resolved)) != len(resolved):
        raise EunoiaError("invalid_input: set names must be unique")
    return resolved


def _as_bool_matrix(arr: npt.NDArray[Any]) -> npt.NDArray[np.bool_]:
    """Validate and coerce an array into an ``(n_rows, n_sets)`` boolean matrix.

    1-D arrays become a single column. Values must be boolean or ``0/1`` numeric;
    ``NaN`` cells count as non-members (parity with DataFrame nulls). Strings,
    datetimes, object arrays, and out-of-range numbers raise."""
    array = np.asarray(arr)
    if array.ndim == 1:
        array = array.reshape(-1, 1)
    elif array.ndim != 2:
        raise EunoiaError(
            "invalid_input: array must be 1- or 2-dimensional to denote a "
            "membership matrix"
        )
    if array.shape[1] == 0:
        raise EunoiaError("invalid_input: array has no columns")
    if array.shape[0] == 0:
        raise EunoiaError("invalid_input: array has no rows")

    if array.dtype == np.bool_:
        return array
    if not np.issubdtype(array.dtype, np.number):
        raise EunoiaError(
            "invalid_input: array must be boolean or 0/1 numeric to denote membership"
        )

    is_float = np.issubdtype(array.dtype, np.floating)
    present = array[~np.isnan(array)] if is_float else array
    if present.size and not np.all(np.isin(present, (0, 1))):
        raise EunoiaError(
            "invalid_input: array must be boolean or 0/1 numeric to denote membership"
        )

    membership = np.zeros(array.shape, dtype=bool)
    if is_float:
        mask = ~np.isnan(array)
        membership[mask] = array[mask].astype(bool)
    else:
        membership = array.astype(bool)
    return membership


def ndarray_to_named_combinations(
    arr: npt.NDArray[Any], names: Sequence[str] | None
) -> tuple[list[str], list[tuple[str, float]]]:
    """Read an array into ``(set_names, [(combo, count), ...])``."""
    matrix = _as_bool_matrix(arr)
    resolved = resolve_set_names(matrix.shape[1], names)
    return resolved, matrix_to_combinations(resolved, matrix)


def ndarray_to_combinations(
    arr: npt.NDArray[Any], names: Sequence[str] | None
) -> list[tuple[str, float]]:
    """Count an array membership matrix into ``[(canonical_combo, count), ...]``."""
    return ndarray_to_named_combinations(arr, names)[1]


def ndarray_to_members(
    arr: npt.NDArray[Any], names: Sequence[str] | None, ids: Sequence[object]
) -> dict[str, list[str]]:
    """Read an array membership matrix into ``{canonical_combo: [member, ...]}``.

    ``ids`` supplies one member identifier per row (arrays carry no row labels),
    keyed by the same canonical regions as :func:`ndarray_to_combinations`."""
    matrix = _as_bool_matrix(arr)
    resolved = resolve_set_names(matrix.shape[1], names)
    return matrix_to_members(resolved, matrix, ids)
