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


def test_plot_labels_per_set_text(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot(labels={"A": "Group A", "B": r"$\beta$"})
    text_strings = [t.get_text() for t in ax.texts]
    assert "Group A" in text_strings
    assert r"$\beta$" in text_strings
    assert "A" not in text_strings  # replaced
    plt.close(ax.figure)


def test_plot_labels_per_set_partial(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    # Only A is relabeled; B keeps its name.
    ax = simple_fit.plot(labels={"A": "Group A"})
    text_strings = [t.get_text() for t in ax.texts]
    assert "Group A" in text_strings
    assert "B" in text_strings
    plt.close(ax.figure)


def test_plot_labels_per_set_style(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot(labels={"A": {"text": "alpha", "fontsize": 20}})
    a_label = next(t for t in ax.texts if t.get_text() == "alpha")
    assert a_label.get_fontsize() == 20
    plt.close(ax.figure)


def test_plot_labels_hide_one(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot(labels={"A": None})
    text_strings = [t.get_text() for t in ax.texts]
    assert "A" not in text_strings
    assert "B" in text_strings
    plt.close(ax.figure)


def test_plot_labels_uniform_style(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot(labels={"fontsize": 18})
    set_labels = [t for t in ax.texts if t.get_text() in ("A", "B")]
    assert len(set_labels) == 2
    assert all(t.get_fontsize() == 18 for t in set_labels)
    plt.close(ax.figure)


def test_plot_labels_dict_overrides_legend_default(
    simple_fit: eu.EulerFit[eu.Circle],
) -> None:
    # A dict turns labels on even when a legend would otherwise hide them.
    ax = simple_fit.plot(legend=True, labels={"A": "Group A"})
    text_strings = [t.get_text() for t in ax.texts]
    assert "Group A" in text_strings
    plt.close(ax.figure)


def test_plot_labels_mixed_keys_raises(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    with pytest.raises(ValueError, match="mixes set names"):
        simple_fit.plot(labels={"A": "Group A", "fontsize": 14})


def test_plot_with_quantities(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot(quantities=True)
    text_strings = [t.get_text() for t in ax.texts]
    # Set labels are still drawn AND quantity labels appear
    assert any(t in text_strings for t in ("A", "B"))
    plt.close(ax.figure)


def test_plot_label_quantity_collision_stacks(
    simple_fit: eu.EulerFit[eu.Circle],
) -> None:
    # A set label and the quantity for its anchor region are composed into one
    # block and placed together, so the name sits directly above its value at
    # the same x. (A=10, B=5 are exclusive-region quantities paired with their
    # set names; A&B=3 is an intersection quantity drawn on its own.)
    ax = simple_fit.plot(quantities=True)
    by_text = {t.get_text(): t.get_position() for t in ax.texts}
    for name, value in (("A", "10"), ("B", "5")):
        nx, ny = by_text[name]
        vx, vy = by_text[value]
        assert nx == pytest.approx(vx)  # same column
        assert ny > vy  # name stacked above its quantity
    plt.close(ax.figure)


def test_plot_quantities_counts_equals_true(
    simple_fit: eu.EulerFit[eu.Circle],
) -> None:
    # "counts" is the explicit name for the default raw-value display.
    a_true = sorted(t.get_text() for t in simple_fit.plot(quantities=True).texts)
    a_counts = sorted(t.get_text() for t in simple_fit.plot(quantities="counts").texts)
    assert a_true == a_counts


def test_plot_quantities_percent(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    # Original (exclusive) areas A=10, B=5, A&B=3, total=18 → shares of total.
    ax = simple_fit.plot(quantities="percent", labels=False)
    text_strings = [t.get_text() for t in ax.texts]
    assert all(t.endswith("%") for t in text_strings)
    assert {"55.6%", "27.8%", "16.7%"} == set(text_strings)
    plt.close(ax.figure)


def test_plot_quantities_counts_and_percent(
    simple_fit: eu.EulerFit[eu.Circle],
) -> None:
    ax = simple_fit.plot(quantities={"type": ["counts", "percent"]}, labels=False)
    text_strings = [t.get_text() for t in ax.texts]
    # Count on top, percentage in parentheses below, on one text object.
    assert "3\n(16.7%)" in text_strings
    plt.close(ax.figure)


def test_plot_quantities_dict_source_and_style(
    simple_fit: eu.EulerFit[eu.Circle],
) -> None:
    ax = simple_fit.plot(
        quantities={"source": "fitted", "color": "crimson", "fontsize": 7},
        labels=False,
    )
    assert ax.texts  # fitted values present
    assert all(t.get_color() == "crimson" for t in ax.texts)
    assert all(t.get_fontsize() == 7 for t in ax.texts)
    plt.close(ax.figure)


def test_plot_quantities_empty_dict_is_on(
    simple_fit: eu.EulerFit[eu.Circle],
) -> None:
    # An empty dict is falsy but means "on with defaults", unlike False.
    ax = simple_fit.plot(quantities={}, labels=False)
    assert ax.texts
    plt.close(ax.figure)


def test_plot_quantities_bad_string_raises(
    simple_fit: eu.EulerFit[eu.Circle],
) -> None:
    with pytest.raises(ValueError, match="quantities string"):
        simple_fit.plot(quantities="nonsense")


def test_plot_quantities_bad_type_raises(
    simple_fit: eu.EulerFit[eu.Circle],
) -> None:
    with pytest.raises(ValueError, match="'counts' or 'percent'"):
        simple_fit.plot(quantities={"type": "fraction"})


def test_plot_quantities_bad_source_raises(
    simple_fit: eu.EulerFit[eu.Circle],
) -> None:
    with pytest.raises(ValueError, match="'original' or 'fitted'"):
        simple_fit.plot(quantities={"source": "guessed"})


def test_plot_legend_lists_sets(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot(legend=True)
    legend = ax.get_legend()
    assert legend is not None
    entries = [t.get_text() for t in legend.get_texts()]
    assert entries == ["A", "B"]
    plt.close(ax.figure)


def test_plot_legend_hides_inline_labels(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    # With a legend, in-diagram set labels default off.
    ax = simple_fit.plot(legend=True)
    text_strings = [t.get_text() for t in ax.texts]
    assert "A" not in text_strings
    assert "B" not in text_strings
    plt.close(ax.figure)


def test_plot_legend_with_labels_shows_both(
    simple_fit: eu.EulerFit[eu.Circle],
) -> None:
    ax = simple_fit.plot(legend=True, labels=True)
    assert ax.get_legend() is not None
    text_strings = [t.get_text() for t in ax.texts]
    assert any(t in text_strings for t in ("A", "B"))
    plt.close(ax.figure)


def test_plot_legend_forwards_kwargs(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot(legend={"loc": "upper right", "title": "Sets"})
    legend = ax.get_legend()
    assert legend is not None
    assert legend.get_title().get_text() == "Sets"
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


def _outline_patches(ax: Axes) -> list[PathPatch]:
    # Set outlines are the PathPatches with no fill (facecolor alpha 0).
    return [
        p
        for p in ax.patches
        if isinstance(p, PathPatch) and p.get_facecolor()[3] == 0.0
    ]


def test_plot_uniform_edges(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot(edges={"linewidth": 3.0})
    outlines = _outline_patches(ax)
    assert outlines
    assert all(p.get_linewidth() == 3.0 for p in outlines)
    plt.close(ax.figure)


def test_plot_per_set_edges_dict(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot(edges={"A": {"linewidth": 4.0}, "B": {"linewidth": 2.0}})
    by_lw = sorted(p.get_linewidth() for p in _outline_patches(ax))
    assert by_lw == [2.0, 4.0]
    plt.close(ax.figure)


def test_plot_per_set_edges_partial(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    # Only A is styled; B keeps the default linewidth (1.0).
    ax = simple_fit.plot(edges={"A": {"linewidth": 5.0}})
    by_lw = sorted(p.get_linewidth() for p in _outline_patches(ax))
    assert by_lw == [1.0, 5.0]
    plt.close(ax.figure)


def test_plot_per_set_edges_sequence(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = simple_fit.plot(edges=[{"linewidth": 6.0}, {"linewidth": 3.0}])
    by_lw = sorted(p.get_linewidth() for p in _outline_patches(ax))
    assert by_lw == [3.0, 6.0]
    plt.close(ax.figure)


def test_plot_per_set_edges_unknown_set(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    with pytest.raises(ValueError, match="unknown sets"):
        simple_fit.plot(edges={"Z": {"linewidth": 2.0}})


def test_plot_edges_sequence_too_short(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    with pytest.raises(ValueError, match="2 sets"):
        simple_fit.plot(edges=[{"linewidth": 2.0}])


def test_plot_saves_to_png(simple_fit: eu.EulerFit[eu.Circle], tmp_path) -> None:  # type: ignore[no-untyped-def]
    ax = simple_fit.plot()
    out = tmp_path / "euler.png"
    ax.figure.savefig(out)
    assert out.exists() and out.stat().st_size > 0
    plt.close(ax.figure)
