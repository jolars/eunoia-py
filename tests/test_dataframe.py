"""DataFrame (membership-matrix) input, exercised against pandas and polars."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import eunoia as eu
import pytest

pd = pytest.importorskip("pandas")
pl = pytest.importorskip("polars")

# A frame builder for each backend; tests are parametrized over both so the two
# interchange implementations (numpy-backed bytes vs. Arrow-style bit-packing)
# must agree.
Builder = Callable[[dict[str, list[Any]]], Any]
BACKENDS: list[tuple[str, Builder]] = [
    ("pandas", lambda cols: pd.DataFrame(cols)),
    ("polars", lambda cols: pl.DataFrame(cols)),
]


@pytest.fixture(params=BACKENDS, ids=[name for name, _ in BACKENDS])
def frame(request: pytest.FixtureRequest) -> Builder:
    return request.param[1]


def test_bool_matrix_counts_exclusive_regions(frame: Builder) -> None:
    df = frame({"A": [True, True, False], "B": [False, True, True]})
    fit = eu.euler(df)
    assert fit.original_values == {"A": 1.0, "B": 1.0, "A&B": 1.0}


def test_integer_0_1_matches_bool(frame: Builder) -> None:
    df = frame({"A": [1, 1, 0, 1], "B": [0, 1, 1, 1]})
    assert eu.euler(df).original_values == {"A": 1.0, "B": 1.0, "A&B": 2.0}


def test_float_0_1_matches_bool(frame: Builder) -> None:
    df = frame({"A": [1.0, 1.0, 0.0, 1.0], "B": [0.0, 1.0, 1.0, 1.0]})
    assert eu.euler(df).original_values == {"A": 1.0, "B": 1.0, "A&B": 2.0}


def test_all_false_rows_dropped(frame: Builder) -> None:
    df = frame({"A": [1, 0, 0], "B": [0, 0, 1]})
    # the middle row is a member of nothing and must not appear anywhere
    assert eu.euler(df).original_values == {"A": 1.0, "B": 1.0}


def test_triple_overlap(frame: Builder) -> None:
    df = frame(
        {
            "A": [1, 1, 0, 0],
            "B": [1, 0, 0, 0],
            "C": [1, 0, 1, 0],
        }
    )
    assert eu.euler(df).original_values == {"A": 1.0, "C": 1.0, "A&B&C": 1.0}


def test_canonical_keys_from_column_order(frame: Builder) -> None:
    # columns in B, A order still yield the canonical region key "A&B"
    df = frame({"B": [1, 1], "A": [1, 1]})
    assert eu.euler(df).original_values == {"A&B": 2.0}


def test_null_cell_counts_as_non_member(frame: Builder) -> None:
    df = frame({"A": [True, None, True], "B": [True, True, False]})
    assert eu.euler(df).original_values == {"A": 1.0, "B": 1.0, "A&B": 1.0}


def test_venn_uses_column_names(frame: Builder) -> None:
    df = frame({"cat": [1, 0], "dog": [0, 1], "fish": [1, 1]})
    fit = eu.venn(df)
    assert sorted(s.set for s in fit.shapes) == ["cat", "dog", "fish"]


def test_string_column_raises(frame: Builder) -> None:
    df = frame({"A": ["x", "y"], "B": ["y", "z"]})
    with pytest.raises(eu.EunoiaError, match="boolean or 0/1"):
        eu.euler(df)


def test_non_binary_numeric_raises(frame: Builder) -> None:
    df = frame({"A": [1, 2], "B": [0, 1]})
    with pytest.raises(eu.EunoiaError, match="boolean or 0/1"):
        eu.euler(df)


def test_inclusive_input_raises(frame: Builder) -> None:
    df = frame({"A": [1, 0], "B": [0, 1]})
    with pytest.raises(eu.EunoiaError, match="always exclusive"):
        eu.euler(df, input="inclusive")


def test_no_rows_raises(frame: Builder) -> None:
    df = frame({"A": [], "B": []})
    with pytest.raises(eu.EunoiaError, match="no rows"):
        eu.euler(df)


def test_pandas_and_polars_agree() -> None:
    cols: dict[str, list[Any]] = {
        "A": [1, 1, 0, 1, 0],
        "B": [0, 1, 1, 1, 0],
        "C": [0, 0, 1, 1, 1],
    }
    assert (
        eu.euler(pd.DataFrame(cols)).original_values
        == eu.euler(pl.DataFrame(cols)).original_values
    )
