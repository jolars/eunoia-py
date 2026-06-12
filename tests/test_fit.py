from __future__ import annotations

import math

import eunoia as eu
import pytest


def test_returns_eulerfit_with_circles_by_default() -> None:
    fit = eu.euler({"A": 10, "B": 5, "A&B": 3})
    assert isinstance(fit, eu.EulerFit)
    assert len(fit.shapes) == 2
    assert all(isinstance(s, eu.Circle) for s in fit.shapes)
    assert fit.diag_error < 0.01


def test_three_set_eulerr_readme_circles() -> None:
    fit = eu.euler(
        {"A": 2, "B": 2, "C": 2, "A&B": 1, "A&C": 1, "B&C": 1},
    )
    # 3-circle symmetric pairwise-overlap arrangement: not exactly fittable
    # with circles (each circle's area is composed entirely of two overlap
    # regions); residual ~6% is expected
    assert fit.diag_error < 0.1


def test_three_set_eulerr_readme_ellipses() -> None:
    fit = eu.euler(
        {"A": 2, "B": 2, "C": 2, "A&B": 1, "A&C": 1, "B&C": 1},
        shape="ellipse",
    )
    # ellipses fit this exactly (~1e-13 numerical floor)
    assert fit.diag_error < 1e-9
    assert all(isinstance(s, eu.Ellipse) for s in fit.shapes)


def test_exclusive_input_preserves_original_values() -> None:
    fit = eu.euler({"A": 10, "B": 5, "A&B": 3}, input="exclusive")
    assert fit.original_values["A"] == 10.0
    assert fit.original_values["B"] == 5.0
    assert fit.original_values["A&B"] == 3.0


def test_inclusive_input_scale() -> None:
    # If A=13 includes the 3 in overlap, exclusive A_only = 10.
    fit = eu.euler({"A": 13, "B": 8, "A&B": 3}, input="inclusive")
    assert fit.original_values["A"] == 13.0
    # fitted A should be in inclusive scale, close to 13
    assert math.isclose(fit.fitted_values["A"], 13.0, abs_tol=0.5)


def test_seed_reproducibility() -> None:
    # The same seed reproduces the same fit to floating-point precision. (The
    # 1.1 default optimizer is not bit-exact across runs — parallel summation
    # wiggles the last ~1e-16 of derived metrics — but the solution matches.)
    fit1 = eu.euler({"A": 10, "B": 5, "A&B": 3}, seed=42)
    fit2 = eu.euler({"A": 10, "B": 5, "A&B": 3}, seed=42)
    assert fit1.diag_error == pytest.approx(fit2.diag_error, abs=1e-12)
    for s1, s2 in zip(fit1.shapes, fit2.shapes, strict=True):
        assert s1.center.x == pytest.approx(s2.center.x, abs=1e-9)
        assert s1.center.y == pytest.approx(s2.center.y, abs=1e-9)


def test_invalid_input_kind_raises_eunoia_error() -> None:
    with pytest.raises(eu.EunoiaError):
        eu.euler({"A": 10, "B": 5, "A&B": 3}, input="bogus")  # type: ignore[arg-type]


def test_invalid_shape_raises_value_error() -> None:
    with pytest.raises(ValueError):
        eu.euler({"A": 10, "B": 5}, shape="hexagon")  # type: ignore[arg-type]


@pytest.mark.parametrize("shape", ["square", "rectangle"])
def test_square_and_rectangle_shapes(shape: str) -> None:
    fit = eu.euler({"A": 10, "B": 8, "A&B": 4}, shape=shape)  # type: ignore[arg-type]
    assert len(fit.shapes) == 2
    assert type(fit.shapes[0]).__name__.lower() == shape
    # Axis-aligned shapes fit two-set overlaps well.
    assert fit.diag_error < 0.1


def test_square_shape_fields() -> None:
    fit = eu.euler({"A": 10, "B": 8, "A&B": 4}, shape="square")
    sq = fit.shapes[0]
    assert isinstance(sq, eu.Square)
    assert sq.side > 0


def test_rectangle_shape_fields() -> None:
    fit = eu.euler({"A": 10, "B": 8, "A&B": 4}, shape="rectangle")
    rect = fit.shapes[0]
    assert isinstance(rect, eu.Rectangle)
    assert rect.width > 0
    assert rect.height > 0


@pytest.mark.parametrize("shape", ["circle", "ellipse", "square", "rectangle"])
def test_complement_returns_container(shape: str) -> None:
    fit = eu.euler({"A": 10, "B": 8, "A&B": 4}, shape=shape, complement=20)  # type: ignore[arg-type]
    assert fit.container is not None
    assert isinstance(fit.container, eu.Container)
    assert fit.container.width > 0
    assert fit.container.height > 0


def test_no_complement_has_no_container() -> None:
    fit = eu.euler({"A": 10, "B": 8, "A&B": 4})
    assert fit.container is None


def test_complement_with_disjoint_sets_raises() -> None:
    # A and B don't overlap, so a single shared container is rejected.
    with pytest.raises(eu.EunoiaError):
        eu.euler({"A": 10, "B": 5}, complement=5)


def test_canonical_keys_in_output() -> None:
    # User passes "B&A"; canonical form is "A&B"
    fit = eu.euler({"A": 10, "B": 5, "B&A": 3})
    assert "A&B" in fit.original_values
    assert "A&B" in fit.fitted_values
    assert "A&B" in fit.residuals


def test_residuals_match_original_minus_fitted() -> None:
    fit = eu.euler({"A": 10, "B": 5, "A&B": 3})
    for k in fit.original_values:
        assert math.isclose(
            fit.residuals[k],
            fit.original_values[k] - fit.fitted_values[k],
            abs_tol=1e-12,
        )


def test_membership_list_input_counts_exclusive_regions() -> None:
    fit = eu.euler({"A": ["x", "y"], "B": ["y", "z"]})
    assert fit.original_values == {"A": 1.0, "B": 1.0, "A&B": 1.0}


def test_membership_three_sets_with_triple_overlap() -> None:
    fit = eu.euler(
        {
            "A": ["x", "shared"],
            "B": ["y", "shared"],
            "C": ["z", "shared"],
        }
    )
    assert fit.original_values["A&B&C"] == 1.0
    assert fit.original_values["A"] == 1.0
    assert fit.original_values["B"] == 1.0
    assert fit.original_values["C"] == 1.0


def test_membership_dedupes_within_set() -> None:
    fit = eu.euler({"A": ["x", "x", "y"], "B": ["z"]})
    assert fit.original_values["A"] == 2.0
    assert fit.original_values["B"] == 1.0


def test_membership_non_string_elements_stringified() -> None:
    fit = eu.euler({"A": [1, 2], "B": [2, 3]})
    assert fit.original_values == {"A": 1.0, "B": 1.0, "A&B": 1.0}


def test_membership_set_and_tuple_values() -> None:
    fit = eu.euler({"A": {"x", "y"}, "B": ("y", "z")})
    assert fit.original_values == {"A": 1.0, "B": 1.0, "A&B": 1.0}


def test_membership_mixed_values_raises() -> None:
    with pytest.raises(eu.EunoiaError):
        eu.euler({"A": ["x"], "B": 3})  # type: ignore[dict-item]


def test_membership_str_value_not_treated_as_membership() -> None:
    # A bare string value is ambiguous; treated as an area and rejected when it
    # cannot be coerced to a float (ValueError, which EunoiaError subclasses).
    with pytest.raises(ValueError):
        eu.euler({"A": "xy"})  # type: ignore[dict-item]


def test_membership_with_inclusive_input_raises() -> None:
    with pytest.raises(eu.EunoiaError):
        eu.euler({"A": ["x", "y"], "B": ["y", "z"]}, input="inclusive")


# A symmetric 3-Venn that no circle layout fits exactly, so different loss
# objectives land in measurably different places.
_LOSS_SPEC = {
    "A": 10.0,
    "B": 10.0,
    "C": 10.0,
    "A&B": 4.0,
    "A&C": 4.0,
    "B&C": 4.0,
    "A&B&C": 2.0,
}


def test_loss_default_matches_sum_squared() -> None:
    default = eu.euler(_LOSS_SPEC, seed=0)
    explicit = eu.euler(_LOSS_SPEC, loss="sum_squared", seed=0)
    assert default.loss == pytest.approx(explicit.loss)


def test_loss_each_objective_minimizes_itself() -> None:
    # The sum_squared fit should have the lowest stress (a squared-residual
    # metric); the diag_error fit should have the lowest diag_error.
    sq = eu.euler(_LOSS_SPEC, loss="sum_squared", seed=0)
    de = eu.euler(_LOSS_SPEC, loss="diag_error", seed=0)
    assert sq.stress < de.stress
    assert de.diag_error < sq.diag_error


@pytest.mark.parametrize(
    "loss",
    [
        "sum_squared",
        "sum_absolute",
        "stress",
        "diag_error",
        "max_absolute",
        "root_mean_squared",
    ],
)
def test_loss_options_run(loss: str) -> None:
    fit = eu.euler(_LOSS_SPEC, loss=loss, seed=0)
    assert math.isfinite(fit.loss)
    assert len(fit.shapes) == 3


def test_invalid_loss_raises_eunoia_error() -> None:
    with pytest.raises(eu.EunoiaError):
        eu.euler(_LOSS_SPEC, loss="not_a_loss")  # type: ignore[arg-type]
