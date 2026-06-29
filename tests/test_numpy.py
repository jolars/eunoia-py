"""NumPy array (membership-matrix) input to ``euler`` and ``venn``."""

from __future__ import annotations

import eunoia as eu
import numpy as np
import pytest


def test_bool_matrix_counts_exclusive_regions() -> None:
    arr = np.array([[True, False], [True, True], [False, True]])
    fit = eu.euler(arr)
    assert fit.original_values == {"A": 1.0, "B": 1.0, "A&B": 1.0}


def test_integer_0_1_matches_bool() -> None:
    arr = np.array([[1, 0], [1, 1], [0, 1], [1, 1]])
    assert eu.euler(arr).original_values == {"A": 1.0, "B": 1.0, "A&B": 2.0}


def test_float_0_1_matches_bool() -> None:
    arr = np.array([[1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [1.0, 1.0]])
    assert eu.euler(arr).original_values == {"A": 1.0, "B": 1.0, "A&B": 2.0}


def test_all_false_rows_dropped() -> None:
    arr = np.array([[1, 0], [0, 0], [0, 1]])
    # the middle row is a member of nothing and must not appear anywhere
    assert eu.euler(arr).original_values == {"A": 1.0, "B": 1.0}


def test_triple_overlap() -> None:
    arr = np.array([[1, 1, 1], [1, 0, 0], [0, 0, 1], [0, 0, 0]])
    assert eu.euler(arr).original_values == {"A": 1.0, "C": 1.0, "A&B&C": 1.0}


def test_one_dimensional_array_is_single_set() -> None:
    # 1D array -> a single set. euler can't fit a lone set (a core limitation,
    # shared with eu.euler({"A": 3.0})), but venn lays out one shape.
    arr = np.array([True, True, False, True])
    fit = eu.venn(arr, shape="circle", names=["A"])
    assert [s.set for s in fit.shapes] == ["A"]
    assert fit.original_values == {"A": 3.0}


def test_canonical_keys_regardless_of_column_order() -> None:
    # naming columns B, A still yields the canonical region key "A&B"
    arr = np.array([[1, 1], [1, 1]])
    assert eu.euler(arr, names=["B", "A"]).original_values == {"A&B": 2.0}


def test_nan_counts_as_non_member() -> None:
    arr = np.array([[1.0, 1.0], [np.nan, 1.0], [1.0, 0.0]])
    assert eu.euler(arr).original_values == {"A": 1.0, "B": 1.0, "A&B": 1.0}


def test_default_names_are_letters() -> None:
    arr = np.array([[1, 0, 1], [0, 1, 1]])
    fit = eu.euler(arr)
    assert sorted(s.set for s in fit.shapes) == ["A", "B", "C"]


def test_custom_names_override_defaults() -> None:
    arr = np.array([[1, 0], [0, 1], [1, 1]])
    fit = eu.euler(arr, names=["cat", "dog"])
    assert sorted(s.set for s in fit.shapes) == ["cat", "dog"]


def test_names_wrong_length_raises() -> None:
    arr = np.array([[1, 0], [0, 1]])
    with pytest.raises(eu.EunoiaError, match="names has 3 entries"):
        eu.euler(arr, names=["A", "B", "C"])


def test_names_must_be_unique() -> None:
    arr = np.array([[1, 0], [0, 1]])
    with pytest.raises(eu.EunoiaError, match="unique"):
        eu.euler(arr, names=["A", "A"])


def test_names_rejected_for_mapping_input() -> None:
    with pytest.raises(eu.EunoiaError, match="only valid for numpy array"):
        eu.euler({"A": 3.0, "B": 2.0}, names=["A", "B"])


def test_non_binary_numeric_raises() -> None:
    arr = np.array([[1, 2], [0, 1]])
    with pytest.raises(eu.EunoiaError, match="boolean or 0/1"):
        eu.euler(arr)


def test_string_array_raises() -> None:
    arr = np.array([["x", "y"], ["y", "z"]])
    with pytest.raises(eu.EunoiaError, match="boolean or 0/1"):
        eu.euler(arr)


def test_three_dimensional_array_raises() -> None:
    arr = np.zeros((2, 2, 2), dtype=bool)
    with pytest.raises(eu.EunoiaError, match="1- or 2-dimensional"):
        eu.euler(arr)


def test_inclusive_input_raises() -> None:
    arr = np.array([[1, 0], [0, 1]])
    with pytest.raises(eu.EunoiaError, match="always exclusive"):
        eu.euler(arr, input="inclusive")


def test_no_rows_raises() -> None:
    arr = np.empty((0, 2), dtype=bool)
    with pytest.raises(eu.EunoiaError, match="no rows"):
        eu.euler(arr)


def test_venn_default_names() -> None:
    arr = np.array([[1, 0, 1], [0, 1, 1]])
    fit = eu.venn(arr, shape="circle")
    assert sorted(s.set for s in fit.shapes) == ["A", "B", "C"]


def test_venn_custom_names_carry_counts() -> None:
    arr = np.array([[1, 0], [0, 1], [1, 1]])
    fit = eu.venn(arr, names=["cat", "dog"])
    assert sorted(s.set for s in fit.shapes) == ["cat", "dog"]
    assert fit.original_values == {"cat": 1.0, "dog": 1.0, "cat&dog": 1.0}


def test_venn_inclusive_rejected_for_array() -> None:
    arr = np.array([[1, 0], [0, 1]])
    with pytest.raises(eu.EunoiaError, match="always exclusive"):
        eu.venn(arr, input="inclusive")


def test_euler_and_dataframe_agree() -> None:
    pd = pytest.importorskip("pandas")
    cols = {"A": [1, 1, 0, 1, 0], "B": [0, 1, 1, 1, 0], "C": [0, 0, 1, 1, 1]}
    arr = np.column_stack([cols["A"], cols["B"], cols["C"]])
    assert (
        eu.euler(arr, names=["A", "B", "C"]).original_values
        == eu.euler(pd.DataFrame(cols)).original_values
    )


def test_thirteen_boolean_columns_euler_runs_and_plots() -> None:
    # The Reddit case: 13 boolean columns. A true Venn is impossible (see below),
    # but an area-proportional Euler diagram fits. Use circles + few restarts to
    # keep it fast.
    rng = np.random.default_rng(0)
    arr = rng.random((200, 13)) < 0.3
    fit = eu.euler(arr, shape="circle", seed=1, n_restarts=1, max_iterations=50)
    assert len(fit.shapes) == 13
    ax = fit.plot()
    assert ax is not None


def test_venn_thirteen_sets_rejected() -> None:
    arr = np.zeros((4, 13), dtype=bool)
    with pytest.raises(eu.EunoiaError, match="set count"):
        eu.venn(arr)
