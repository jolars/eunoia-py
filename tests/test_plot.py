from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import eunoia as eu
import matplotlib.pyplot as plt
import pytest
from matplotlib.axes import Axes
from matplotlib.patches import PathPatch
from matplotlib.patches import Rectangle as MplRectangle


@pytest.fixture
def simple_fit() -> eu.EulerFit[eu.Circle]:
    return eu.euler({"A": 10, "B": 5, "A&B": 3})


def test_plot_returns_axes(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot()
    assert isinstance(ax, Axes)
    plt.close(ax.figure)


def test_plot_uses_provided_axes(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    fig, ax_in = plt.subplots()
    ax_out = simple_fit.plot(ax=ax_in)
    assert ax_out is ax_in
    plt.close(fig)


def test_plot_renders_path_patches(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot()
    patches = [p for p in ax.patches if isinstance(p, PathPatch)]
    # 3 region fills (A_only, B_only, A&B) + 2 set outlines = 5
    assert len(patches) >= 4
    plt.close(ax.figure)


def test_plot_equal_aspect(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot()
    assert ax.get_aspect() == 1.0
    plt.close(ax.figure)


def test_plot_with_labels_off(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot(labels=False)
    text_strings = [t.get_text() for t in ax.texts]
    assert "A" not in text_strings
    assert "B" not in text_strings
    plt.close(ax.figure)


def test_plot_with_quantities(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot(quantities=True)
    text_strings = [t.get_text() for t in ax.texts]
    # Set labels are still drawn AND quantity labels appear
    assert any(t in text_strings for t in ("A", "B"))
    plt.close(ax.figure)


def test_plot_ellipses() -> None:
    fit = eu.euler({"A": 10, "B": 5, "A&B": 3}, shape="ellipse")
    ax = fit.plot()
    patches = [p for p in ax.patches if isinstance(p, PathPatch)]
    assert len(patches) >= 4
    plt.close(ax.figure)


@pytest.mark.parametrize("shape", ["square", "rectangle"])
def test_plot_squares_and_rectangles(shape: str) -> None:
    fit = eu.euler({"A": 10, "B": 5, "A&B": 3}, shape=shape)  # type: ignore[arg-type]
    ax = fit.plot()
    patches = [p for p in ax.patches if isinstance(p, PathPatch)]
    assert len(patches) >= 4
    plt.close(ax.figure)


def test_plot_complement_draws_container() -> None:
    fit = eu.euler({"A": 10, "B": 8, "A&B": 4}, complement=20)
    ax = fit.plot()
    rects = [p for p in ax.patches if isinstance(p, MplRectangle)]
    assert len(rects) == 1  # the universe container box
    plt.close(ax.figure)


def test_plot_complement_style_override() -> None:
    fit = eu.euler({"A": 10, "B": 8, "A&B": 4}, complement=20)
    ax = fit.plot(complement={"facecolor": "lightblue"})
    rects = [p for p in ax.patches if isinstance(p, MplRectangle)]
    assert rects
    assert rects[0].get_facecolor()[:3] == pytest.approx(
        matplotlib.colors.to_rgb("lightblue")
    )
    plt.close(ax.figure)


def test_plot_custom_colors_dict(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot(colors={"A": "red", "B": "blue"})
    assert ax.patches  # rendered something
    plt.close(ax.figure)


def test_plot_saves_to_png(simple_fit: eu.EulerFit[eu.Circle], tmp_path) -> None:  # type: ignore[no-untyped-def]
    ax = simple_fit.plot()
    out = tmp_path / "euler.png"
    ax.figure.savefig(out)
    assert out.exists() and out.stat().st_size > 0
    plt.close(ax.figure)
