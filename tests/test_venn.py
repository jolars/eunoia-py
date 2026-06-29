from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import eunoia as eu
import matplotlib.pyplot as plt
import pytest
from matplotlib.axes import Axes


def test_venn_int_default_ellipse() -> None:
    v = eu.venn(3)
    assert isinstance(v, eu.VennFit)
    assert len(v.shapes) == 3
    assert [s.set for s in v.shapes] == ["A", "B", "C"]
    assert isinstance(v.shapes[0], eu.Ellipse)


def test_venn_list_of_names() -> None:
    v = eu.venn(["cat", "dog", "fish"])
    assert [s.set for s in v.shapes] == ["cat", "dog", "fish"]


def test_venn_mapping_extracts_base_sets() -> None:
    v = eu.venn({"A": 1, "B": 2, "A&B": 3})
    assert [s.set for s in v.shapes] == ["A", "B"]


@pytest.mark.parametrize("shape", ["square", "rectangle"])
def test_venn_axis_aligned_shapes(shape: str) -> None:
    v = eu.venn(3, shape=shape)  # type: ignore[arg-type]
    assert len(v.shapes) == 3
    assert type(v.shapes[0]).__name__.lower() == shape


def test_venn_ellipse_five_sets() -> None:
    v = eu.venn(5)
    assert len(v.shapes) == 5
    # All 31 regions present in a 5-set Venn.
    assert len(v.fitted_values) == 2**5 - 1


def test_venn_fitted_values_are_region_areas() -> None:
    v = eu.venn(2)
    assert v.original_values == {}
    assert set(v.fitted_values) == {"A", "B", "A&B"}
    assert all(area > 0 for area in v.fitted_values.values())


def test_venn_complement_adds_container() -> None:
    v = eu.venn(2, complement=5)
    assert v.container is not None
    assert isinstance(v.container, eu.Container)


def test_venn_repr() -> None:
    assert repr(eu.venn(2)).startswith("VennFit (2 sets [ellipse]: A, B)")


def test_venn_plot_returns_axes() -> None:
    ax = eu.venn(3).plot()
    assert isinstance(ax, Axes)
    assert ax.patches
    plt.close(ax.figure)


def test_venn_unsupported_counts_raise() -> None:
    with pytest.raises(eu.EunoiaError):
        eu.venn(6)  # ellipse max is 5
    with pytest.raises(eu.EunoiaError):
        eu.venn(4, shape="square")


def test_venn_rotated_rectangle_supported_up_to_four() -> None:
    for n in (1, 2, 3, 4):
        fit = eu.venn(n, shape="rotated_rectangle")
        assert all(isinstance(s, eu.RotatedRectangle) for s in fit.shapes)
        assert len(fit.shapes) == n
        # Every region is present in the topological layout.
        assert len(fit.fitted_values) == 2**n - 1
    # The four-set layout rotates the rectangles to open all 15 regions.
    four = eu.venn(4, shape="rotated_rectangle")
    assert any(s.rotation != 0.0 for s in four.shapes)
    # Five or more has no canonical layout.
    with pytest.raises(eu.EunoiaError):
        eu.venn(5, shape="rotated_rectangle")


def test_venn_circle_supported_up_to_three() -> None:
    # eunoia 0.18 added a canonical circular Venn layout for 1--3 sets.
    for n in (1, 2, 3):
        fit = eu.venn(n, shape="circle")
        assert all(isinstance(s, eu.Circle) for s in fit.shapes)
        assert len(fit.shapes) == n
    # Four or more circles has no canonical layout.
    with pytest.raises(eu.EunoiaError):
        eu.venn(4, shape="circle")


def test_venn_invalid_shape_raises() -> None:
    with pytest.raises(eu.EunoiaError):
        eu.venn(3, shape="hexagon")  # type: ignore[arg-type]


def test_venn_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        eu.venn(0)
    with pytest.raises(TypeError):
        eu.venn("ABC")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        eu.venn(["A", "A"])  # duplicate names


def test_venn_membership_dict_extracts_base_sets() -> None:
    v = eu.venn({"A": ["x", "y"], "B": ["y", "z"]})
    assert [s.set for s in v.shapes] == ["A", "B"]


def test_venn_mapping_carries_original_values() -> None:
    v = eu.venn({"A": 1, "B": 2, "A&B": 3})
    assert v.original_values == {"A": 1, "B": 2, "A&B": 3}


def test_venn_mapping_canonicalizes_keys() -> None:
    v = eu.venn({"B&A": 3, "A": 1})
    assert v.original_values == {"A&B": 3, "A": 1}


def test_venn_membership_carries_counts() -> None:
    # x -> A only, y -> A&B, z -> B only.
    v = eu.venn({"A": ["x", "y"], "B": ["y", "z"]})
    assert v.original_values == {"A": 1, "A&B": 1, "B": 1}


def test_venn_dataframe_carries_counts() -> None:
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"A": [True, True, False], "B": [False, True, True]})
    v = eu.venn(df)
    assert [s.set for s in v.shapes] == ["A", "B"]
    assert v.original_values == {"A": 1, "A&B": 1, "B": 1}


def test_venn_int_input_has_no_original_values() -> None:
    v = eu.venn(3)
    assert v.original_values == {}


def test_venn_inclusive_input_accepted_for_mapping() -> None:
    v = eu.venn({"A": 10, "B": 7, "A&B": 3}, input="inclusive")
    assert v.original_values == {"A": 10, "B": 7, "A&B": 3}


def test_venn_inclusive_rejected_for_membership() -> None:
    with pytest.raises(eu.EunoiaError):
        eu.venn({"A": ["x"], "B": ["y"]}, input="inclusive")


def test_venn_inclusive_rejected_for_dataframe() -> None:
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"A": [True], "B": [False]})
    with pytest.raises(eu.EunoiaError):
        eu.venn(df, input="inclusive")


def test_venn_invalid_input_value_raises() -> None:
    with pytest.raises(eu.EunoiaError):
        eu.venn(3, input="bogus")  # type: ignore[arg-type]


def test_venn_quantities_auto_on_with_values() -> None:
    ax = eu.venn({"A": 1, "B": 2, "A&B": 3}).plot()
    texts = sorted(t.get_text() for t in ax.texts)
    # Three region quantities plus two set labels.
    assert "1" in texts and "2" in texts and "3" in texts
    plt.close(ax.figure)


def test_venn_quantities_off_without_values() -> None:
    ax = eu.venn(3).plot()
    # No region values to show; only set labels (A, B, C) appear.
    assert sorted(t.get_text() for t in ax.texts) == ["A", "B", "C"]
    plt.close(ax.figure)


def test_venn_quantities_false_suppresses_with_values() -> None:
    ax = eu.venn({"A": 1, "B": 2, "A&B": 3}).plot(quantities=False, labels=False)
    assert len(ax.texts) == 0
    plt.close(ax.figure)
