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

from collections.abc import Sequence
from typing import Any, TypeGuard

import narwhals as nw
import numpy as np
import numpy.typing as npt
from narwhals.typing import IntoFrame

from eunoia._eunoia import EunoiaError
from eunoia._numpy import matrix_to_combinations, matrix_to_members


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


def _read_frame(
    obj: IntoFrame, ids: str | Sequence[object] | None
) -> tuple[list[str], npt.NDArray[np.bool_], list[str] | None]:
    """Collect a frame into set names, an ``(n_rows, n_sets)`` bool matrix, and
    an optional per-row id list.

    ``ids`` may name a column (dropped from the set columns and read as the
    member-id source) or be an explicit per-row sequence; ``None`` means no
    member ids. Ids are stringified."""
    frame = nw.from_native(obj)
    if isinstance(frame, nw.LazyFrame):
        frame = frame.collect()
    all_names = list(frame.columns)
    if not all_names:
        raise EunoiaError("invalid_input: DataFrame has no columns")
    if frame.shape[0] == 0:
        raise EunoiaError("invalid_input: DataFrame has no rows")

    id_values: list[str] | None = None
    set_names = all_names
    if isinstance(ids, str):
        if ids not in all_names:
            raise EunoiaError(
                f"invalid_input: ids column {ids!r} not found in DataFrame"
            )
        id_values = [str(v) for v in frame[ids].to_list()]
        set_names = [n for n in all_names if n != ids]
        if not set_names:
            raise EunoiaError(
                "invalid_input: DataFrame has no set columns besides ids "
                f"column {ids!r}"
            )
    elif ids is not None:
        id_values = [str(v) for v in ids]

    columns = [_column_to_bool(frame[name], name) for name in set_names]
    return set_names, np.column_stack(columns), id_values


def dataframe_to_combinations(
    obj: IntoFrame, ids: str | Sequence[object] | None = None
) -> tuple[list[str], list[tuple[str, float]], dict[str, list[str]] | None]:
    """Read a membership-matrix frame into ``(set_names, [(combo, count)], members)``.

    Each row is assigned to the canonical region of the columns that are true;
    all-false rows (member of no set) are dropped. When ``ids`` is given (a
    column name or an explicit per-row sequence) the third element maps each
    region to its member ids; otherwise it is ``None``. Counting and
    canonicalization are shared with the numpy-array path via
    :func:`eunoia._numpy.matrix_to_combinations`."""
    set_names, matrix, id_values = _read_frame(obj, ids)
    combinations = matrix_to_combinations(set_names, matrix)
    members = (
        matrix_to_members(set_names, matrix, id_values)
        if id_values is not None
        else None
    )
    return set_names, combinations, members
