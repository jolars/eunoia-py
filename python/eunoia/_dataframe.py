"""DataFrame input via narwhals.

Accepts any dataframe narwhals understands (pandas, polars, pyarrow, modin, …)
as a *wide membership matrix*: each column is a set, each row an observation,
and a truthy cell means the observation belongs to that set. This mirrors
eulerr's ``data.frame`` or matrix idiom and is the wide-form cousin of the
membership-list path in :func:`eunoia._parse.parse_membership_input`.

We route through `narwhals <https://narwhals-dev.github.io/narwhals/>`_, a
lightweight, dataframe-agnostic compatibility layer recommended by both pandas
and polars, rather than the (now deprecated) dataframe interchange protocol.
"""

from __future__ import annotations

from typing import Any, TypeGuard

import narwhals as nw
import numpy as np
import numpy.typing as npt
from narwhals.typing import IntoFrame

from eunoia._eunoia import EunoiaError
from eunoia._numpy import matrix_to_combinations


def is_dataframe(obj: object) -> TypeGuard[IntoFrame]:
    """Return ``True`` for objects narwhals recognizes as a (lazy or eager)
    dataframe. Plain mappings/sequences pass through unchanged and return
    ``False``, so dict area/membership input keeps its existing path."""
    return isinstance(
        nw.from_native(obj, pass_through=True), (nw.DataFrame, nw.LazyFrame)
    )


def _column_to_bool(series: nw.Series[Any], name: str) -> npt.NDArray[np.bool_]:
    """Read one column into a boolean membership array.

    Columns must be boolean or ``0/1`` numeric; null cells count as non-members.
    Validation is by value (``np.isin``), so a pandas object column of
    ``bool`` or ``None`` is accepted while strings, datetimes, or out-of-range
    numbers raise."""
    values = series.to_numpy()
    nulls = series.is_null().to_numpy()
    present = values[~nulls]
    if present.size and not np.all(np.isin(present, (0, 1))):
        raise EunoiaError(
            f"invalid_input: DataFrame column {name!r} must be boolean or 0/1 "
            f"numeric to denote membership"
        )
    membership = np.zeros(len(values), dtype=bool)
    if present.size:
        membership[~nulls] = present.astype(bool)
    return membership


def _extract_bool_matrix(obj: IntoFrame) -> tuple[list[str], npt.NDArray[np.bool_]]:
    """Read a frame into column names and an ``(n_rows, n_sets)`` bool matrix."""
    frame = nw.from_native(obj)
    if isinstance(frame, nw.LazyFrame):
        frame = frame.collect()
    names = frame.columns
    if not names:
        raise EunoiaError("invalid_input: DataFrame has no columns")
    if frame.shape[0] == 0:
        raise EunoiaError("invalid_input: DataFrame has no rows")
    columns = [_column_to_bool(frame[name], name) for name in names]
    return names, np.column_stack(columns)


def dataframe_to_combinations(obj: IntoFrame) -> list[tuple[str, float]]:
    """Count a membership-matrix frame into ``[(canonical_combo, count), ...]``.

    Each row is assigned to the canonical region of the columns that are true;
    all-false rows (member of no set) are dropped. Returns the same shape the
    Rust binding consumes. Counting is shared with the numpy-array path via
    :func:`eunoia._numpy.matrix_to_combinations`."""
    names, matrix = _extract_bool_matrix(obj)
    return matrix_to_combinations(names, matrix)


def dataframe_column_names(obj: IntoFrame) -> list[str]:
    """Return the frame's column names (the set names, for ``venn``)."""
    frame = nw.from_native(obj)
    if isinstance(frame, nw.LazyFrame):
        frame = frame.collect()
    names = frame.columns
    if not names:
        raise EunoiaError("invalid_input: DataFrame has no columns")
    return names
