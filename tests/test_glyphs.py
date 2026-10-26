"""Glyph and packed-member controls shared by both rendering backends."""

from __future__ import annotations

import importlib
import math
from collections.abc import Callable
from itertools import pairwise
from typing import Any

import eunoia as eu
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest
from eunoia._eunoia import _place_glyph_boxes, _place_glyphs

SQUARE_RINGS = {"A": [[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]]}
BLOCKING_OBSTACLE = (5.0, 5.0, 20.0, 20.0)


def render(fit: eu.EulerFit[Any], backend: str, **kwargs: Any) -> Any:
    if backend == "plotly":
        pytest.importorskip("plotly")
        pytest.importorskip("fontTools")
        return fit.plot_plotly(hover=False, **kwargs)
    return fit.plot(**kwargs)


@pytest.mark.parametrize(
    ("placer", "values", "items_key", "size_key"),
    [
        (_place_glyphs, {"A": 8}, "positions", "radius"),
        (_place_glyph_boxes, {"A": [(1.0, 0.5)] * 8}, "boxes", "scale"),
    ],
)
def test_strict_obstacles_report_omissions_at_automatic_size_floor(
    placer: Callable[..., Any],
    values: dict[str, Any],
    items_key: str,
    size_key: str,
) -> None:
    options = {"obstacles": [BLOCKING_OBSTACLE]}
    default = placer(SQUARE_RINGS, values, **options)
    best_effort = placer(SQUARE_RINGS, values, obstacle_policy="best_effort", **options)
    strict = placer(SQUARE_RINGS, values, obstacle_policy="strict", **options)
    assert default == best_effort
    assert len(best_effort[items_key]["A"]) == 8
    assert strict[size_key] == best_effort[size_key] > 0
    assert strict[items_key]["A"] == []
    assert strict["unplaced"] == {"A": 8}


@pytest.mark.parametrize(
    ("placer", "values"),
    [(_place_glyphs, {"A": 1}), (_place_glyph_boxes, {"A": [(1.0, 0.5)]})],
)
def test_invalid_obstacle_policy_raises(
    placer: Callable[..., Any], values: dict[str, Any]
) -> None:
    with pytest.raises(eu.EunoiaError, match="invalid_obstacle_policy"):
        placer(SQUARE_RINGS, values, obstacle_policy="unknown")


@pytest.mark.parametrize("backend", ["matplotlib", "plotly"])
@pytest.mark.parametrize("category", ["glyphs", "members"])
@pytest.mark.parametrize("global_option", [False, True])
def test_renderers_apply_strict_obstacles_and_warn(
    monkeypatch: pytest.MonkeyPatch, backend: str, category: str, global_option: bool
) -> None:
    if backend == "plotly":
        pytest.importorskip("plotly")
        pytest.importorskip("fontTools")
    module = importlib.import_module(
        "eunoia._plotly" if backend == "plotly" else "eunoia._plot"
    )
    binding = "_place_glyphs" if category == "glyphs" else "_place_glyph_boxes"
    place = getattr(module, binding)

    def block_packing(*args: Any, **kwargs: Any) -> Any:
        kwargs["obstacles"] = [BLOCKING_OBSTACLE]
        return place(*args, **kwargs)

    monkeypatch.setattr(module, binding, block_packing)
    fit = eu.euler({"A": ["Ada", "Grace"], "B": ["Grace", "Barbara"]}, shape="square")
    config = {"obstacle_policy": "strict"}
    if category == "members":
        config["mode"] = "packed"
    defaults = {category: config if global_option else {}}
    explicit = {category: True if global_option else config}
    try:
        with eu.options(**defaults), pytest.warns(UserWarning, match="did not fit"):
            plot = render(fit, backend, labels=False, quantities=False, **explicit)
        if category == "members":
            texts = plot.layout.annotations if backend == "plotly" else plot.texts
            assert not texts
        elif backend == "plotly":
            assert all(len(trace.x) == 0 for trace in plot.data)
        else:
            assert not any(type(patch).__name__ == "Circle" for patch in plot.patches)
    finally:
        plt.close("all")


@pytest.mark.parametrize("arrangement", ["rectangular", "low_discrepancy"])
@pytest.mark.parametrize(
    ("placer", "values", "items_key"),
    [
        (_place_glyphs, {"A": 12}, "positions"),
        (_place_glyph_boxes, {"A": [(1.0, 0.5)] * 12}, "boxes"),
    ],
)
def test_new_arrangements_place_all_items_independently_of_seed(
    placer: Callable[..., Any],
    values: dict[str, Any],
    items_key: str,
    arrangement: str,
) -> None:
    first = placer(SQUARE_RINGS, values, arrangement=arrangement, seed=1)
    second = placer(SQUARE_RINGS, values, arrangement=arrangement, seed=99)
    assert first == second
    assert len(first[items_key]["A"]) == 12
    assert first["unplaced"] == {}


def test_rectangular_glyphs_form_an_aligned_grid() -> None:
    placed = _place_glyphs(
        SQUARE_RINGS, {"A": 12}, arrangement="rectangular", radius=0.3
    )
    points = placed["positions"]["A"]
    assert len(points) == 12
    xs = sorted({round(x, 8) for x, _ in points})
    ys = sorted({round(y, 8) for _, y in points})
    assert len(xs) > 1 and len(ys) > 1
    step = xs[1] - xs[0]
    assert all(b - a == pytest.approx(step) for a, b in pairwise(xs))
    assert all(b - a == pytest.approx(step) for a, b in pairwise(ys))


@pytest.mark.parametrize("backend", ["matplotlib", "plotly"])
@pytest.mark.parametrize("arrangement", ["rectangular", "low_discrepancy"])
@pytest.mark.parametrize("category", ["glyphs", "members"])
def test_renderers_draw_new_arrangements(
    backend: str, arrangement: str, category: str
) -> None:
    names = [f"member_{i:02d}" for i in range(12)]
    fit = eu.venn({"A": names}, shape="square")
    config = {"arrangement": arrangement}
    if category == "members":
        config["mode"] = "packed"
    try:
        plot = render(
            fit, backend, labels=False, quantities=False, **{category: config}
        )
        if category == "members":
            if backend == "plotly":
                texts = [text.text for text in plot.layout.annotations]
            else:
                texts = [text.get_text() for text in plot.texts]
            assert texts == names
        elif backend == "plotly":
            assert sum(len(trace.x) for trace in plot.data) == 12
        else:
            assert sum(type(patch).__name__ == "Circle" for patch in plot.patches) == 12
    finally:
        plt.close("all")


@pytest.mark.parametrize(
    ("placer", "values"),
    [(_place_glyphs, {"A": 1}), (_place_glyph_boxes, {"A": [(1.0, 0.5)]})],
)
def test_invalid_arrangement_lists_new_choices(
    placer: Callable[..., Any], values: dict[str, Any]
) -> None:
    with pytest.raises(eu.EunoiaError, match=r"'rectangular'.*'low_discrepancy'"):
        placer(SQUARE_RINGS, values, arrangement="unknown")


@pytest.mark.parametrize("ratio", [0.25, 1.0, 4.0])
def test_balanced_rows_approach_target_ratio_without_losing_names(ratio: float) -> None:
    sizes = {"A": [(1.0, 0.25)] * 12}
    default = _place_glyph_boxes(SQUARE_RINGS, sizes)
    balanced = _place_glyph_boxes(SQUARE_RINGS, sizes, target_aspect_ratio=ratio)

    def aspect_ratio(boxes: list[tuple[float, float, float, float]]) -> float:
        width = max(x + w / 2 for x, _, w, _ in boxes) - min(
            x - w / 2 for x, _, w, _ in boxes
        )
        height = max(y + h / 2 for _, y, _, h in boxes) - min(
            y - h / 2 for _, y, _, h in boxes
        )
        return width / height

    assert balanced["scale"] == default["scale"]
    assert len(balanced["boxes"]["A"]) == len(default["boxes"]["A"]) == 12
    assert balanced["unplaced"] == {}
    assert abs(math.log(aspect_ratio(balanced["boxes"]["A"]) / ratio)) < abs(
        math.log(aspect_ratio(default["boxes"]["A"]) / ratio)
    )


@pytest.mark.parametrize("backend", ["matplotlib", "plotly"])
def test_renderers_balance_member_rows(backend: str) -> None:
    names = [f"member_{i:02d}" for i in range(12)]
    fit = eu.venn({"A": names}, shape="square")

    def member_rows(ratio: float | None) -> int:
        plot = render(
            fit,
            backend,
            labels=False,
            quantities=False,
            members={"mode": "packed", "target_aspect_ratio": ratio},
        )
        if backend == "plotly":
            labels = [(text.text, text.y) for text in plot.layout.annotations]
        else:
            labels = [(text.get_text(), text.get_position()[1]) for text in plot.texts]
        assert [name for name, _ in labels] == names
        return len({round(y, 8) for _, y in labels})

    try:
        assert member_rows(1.0) > member_rows(None)
    finally:
        plt.close("all")
