"""Glyph and packed-member controls shared by both rendering backends."""

from __future__ import annotations

import importlib
from collections.abc import Callable
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
