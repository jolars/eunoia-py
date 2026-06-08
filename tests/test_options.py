from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

from collections.abc import Iterator

import eunoia as eu
import matplotlib.pyplot as plt
import pytest
from matplotlib.patches import PathPatch
from matplotlib.patches import Rectangle as MplRectangle


@pytest.fixture(autouse=True)
def _reset_options() -> Iterator[None]:
    """Keep global option state from leaking between tests."""
    eu.reset_options()
    yield
    eu.reset_options()


@pytest.fixture
def simple_fit() -> eu.EulerFit[eu.Circle]:
    return eu.euler({"A": 10, "B": 5, "A&B": 3})


def _fill_alphas(ax: object) -> list[float]:
    return [
        p.get_alpha()
        for p in ax.patches  # type: ignore[attr-defined]
        if isinstance(p, PathPatch) and p.get_alpha() is not None
    ]


def test_options_no_args_returns_snapshot() -> None:
    snap = eu.options()
    assert snap["fills"]["alpha"] == 0.5
    assert snap["palette"] == "tab10"
    # Mutating the snapshot must not affect live options.
    snap["fills"]["alpha"] = 0.1
    assert eu.options()["fills"]["alpha"] == 0.5


def test_options_set_is_persistent() -> None:
    eu.options(fills={"alpha": 0.25})
    assert eu.options()["fills"]["alpha"] == 0.25
    # Merge, don't replace: other categories untouched.
    assert eu.options()["labels"]["fontsize"] == 11


def test_options_set_returns_prior_via_context() -> None:
    eu.options(fills={"alpha": 0.25})
    with eu.options(fills={"alpha": 0.9}):
        assert eu.options()["fills"]["alpha"] == 0.9
    assert eu.options()["fills"]["alpha"] == 0.25


def test_context_restores_on_exception() -> None:
    with pytest.raises(RuntimeError), eu.options(labels={"fontsize": 30}):
        raise RuntimeError
    assert eu.options()["labels"]["fontsize"] == 11


def test_unknown_category_raises() -> None:
    with pytest.raises(ValueError, match="unknown option category"):
        eu.options(bogus={"x": 1})


def test_non_mapping_value_raises() -> None:
    with pytest.raises(TypeError, match="must be a mapping"):
        eu.options(fills=0.5)  # type: ignore[arg-type]


def test_global_fill_alpha_applied_to_plot(
    simple_fit: eu.EulerFit[eu.Circle],
) -> None:
    eu.options(fills={"alpha": 0.2})
    ax = simple_fit.plot()
    assert _fill_alphas(ax)
    assert all(a == pytest.approx(0.2) for a in _fill_alphas(ax))
    plt.close(ax.figure)


def test_explicit_kwarg_beats_global_option(
    simple_fit: eu.EulerFit[eu.Circle],
) -> None:
    eu.options(fills={"alpha": 0.2})
    ax = simple_fit.plot(fills={"A": {"alpha": 0.95}})
    alphas = _fill_alphas(ax)
    assert pytest.approx(0.95) in alphas  # the A-only region used the override
    plt.close(ax.figure)


def test_palette_sequence_option(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    eu.options(palette=["red", "blue"])
    # Should not raise and should produce a normal plot.
    ax = simple_fit.plot()
    assert ax.patches
    plt.close(ax.figure)


def test_complement_option_styles_container() -> None:
    fit = eu.euler({"A": 10, "B": 5, "A&B": 3}, complement=20)
    eu.options(complement={"facecolor": "#123456"})
    ax = fit.plot()
    boxes = [p for p in ax.patches if isinstance(p, MplRectangle)]
    assert boxes
    plt.close(ax.figure)
