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
    fit1 = eu.euler({"A": 10, "B": 5, "A&B": 3}, seed=42)
    fit2 = eu.euler({"A": 10, "B": 5, "A&B": 3}, seed=42)
    assert fit1.diag_error == fit2.diag_error


def test_invalid_input_kind_raises_eunoia_error() -> None:
    with pytest.raises(eu.EunoiaError):
        eu.euler({"A": 10, "B": 5, "A&B": 3}, input="bogus")  # type: ignore[arg-type]


def test_invalid_shape_raises_value_error() -> None:
    with pytest.raises(ValueError):
        eu.euler({"A": 10, "B": 5}, shape="square")  # type: ignore[arg-type]


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
