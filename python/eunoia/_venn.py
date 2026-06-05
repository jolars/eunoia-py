"""Public ``venn()`` function — non-proportional Venn diagrams."""

from __future__ import annotations

import string
from collections.abc import Collection, Mapping, Sequence
from typing import Any, Literal, overload

from eunoia._eunoia import EunoiaError
from eunoia._eunoia import _venn as _venn_rust
from eunoia._fit import (
    build_circles,
    build_container,
    build_ellipses,
    build_plot_data,
    build_rectangles,
    build_squares,
)
from eunoia._models import Circle, Ellipse, Rectangle, S, Square, VennFit
from eunoia._parse import canonicalize

VennInput = int | Sequence[str] | Mapping[str, float] | Mapping[str, Collection[str]]


@overload
def venn(
    sets: VennInput,
    *,
    shape: Literal["ellipse"] = ...,
    complement: float | None = ...,
) -> VennFit[Ellipse]: ...


@overload
def venn(
    sets: VennInput,
    *,
    shape: Literal["circle"],
    complement: float | None = ...,
) -> VennFit[Circle]: ...


@overload
def venn(
    sets: VennInput,
    *,
    shape: Literal["square"],
    complement: float | None = ...,
) -> VennFit[Square]: ...


@overload
def venn(
    sets: VennInput,
    *,
    shape: Literal["rectangle"],
    complement: float | None = ...,
) -> VennFit[Rectangle]: ...


def venn(
    sets: VennInput,
    *,
    shape: Literal["circle", "ellipse", "square", "rectangle"] = "ellipse",
    complement: float | None = None,
) -> VennFit[Circle] | VennFit[Ellipse] | VennFit[Square] | VennFit[Rectangle]:
    """Lay out a (non-proportional) Venn diagram.

    Unlike :func:`euler`, every set intersection is always drawn, regardless
    of area. The arrangement is *topological* — the shapes come from the
    eunoia core's canonical Venn layouts, not from numerical optimization.

    Parameters
    ----------
    sets:
        The sets to show. One of:

        * an ``int`` *n* — *n* sets with default names ``"A"``, ``"B"``, …;
        * a sequence of set names, e.g. ``["cat", "dog", "fish"]``;
        * a mapping whose keys are set/combination labels (the distinct base
          set names are extracted; values are ignored, since a Venn layout is
          non-proportional).
    shape:
        ``"ellipse"`` (default), ``"square"`` or ``"rectangle"``. Ellipses
        support 1--5 sets; squares and rectangles 1--3. ``"circle"`` is
        accepted but the pinned eunoia core (0.15) has no canonical circular
        Venn layout, so it raises :class:`EunoiaError` for now; use ellipses.
    complement:
        Optional universe area outside every set. For a Venn diagram this only
        adds a visual container box (the padded bounding box); it does not
        drive optimization.

    Returns
    -------
    VennFit
        A topological fit whose ``plot()`` works like :class:`EulerFit`.
        ``fitted_values`` holds the geometric area of each region.
    """
    if shape not in ("circle", "ellipse", "square", "rectangle"):
        raise EunoiaError(
            "invalid_shape: shape must be 'circle', 'ellipse', 'square' or "
            f"'rectangle', got {shape!r}"
        )

    names = _resolve_names(sets)
    result: Any = _venn_rust(len(names), shape, names, complement)

    if shape == "circle":
        return _make_venn(result, build_circles(result["shapes"]))
    if shape == "ellipse":
        return _make_venn(result, build_ellipses(result["shapes"]))
    if shape == "square":
        return _make_venn(result, build_squares(result["shapes"]))
    return _make_venn(result, build_rectangles(result["shapes"]))


def _make_venn(result: Mapping[str, Any], shapes: tuple[S, ...]) -> VennFit[S]:
    """Assemble a ``VennFit`` from a raw ``_venn`` result and built shapes."""
    return VennFit(
        shapes=shapes,
        original_values={},
        fitted_values={k: float(v) for k, v in result["fitted_exclusive"].items()},
        residuals={},
        region_error={},
        diag_error=0.0,
        stress=0.0,
        loss=0.0,
        container=build_container(result.get("container")),
        plot_data=build_plot_data(result),
    )


def _default_name(i: int) -> str:
    if i < len(string.ascii_uppercase):
        return string.ascii_uppercase[i]
    return f"set{i + 1}"


def _resolve_names(sets: VennInput) -> list[str]:
    # bool is an int subclass; reject it explicitly to avoid venn(True).
    if isinstance(sets, bool):
        raise TypeError("venn: 'sets' must be an int, a list of names, or a mapping")
    if isinstance(sets, int):
        if sets < 1:
            raise ValueError("venn: number of sets must be >= 1")
        return [_default_name(i) for i in range(sets)]
    if isinstance(sets, Mapping):
        names: list[str] = []
        for key in sets:
            for part in canonicalize(key).split("&"):
                if part and part not in names:
                    names.append(part)
        if not names:
            raise ValueError("venn: no sets found in mapping")
        return names
    if isinstance(sets, str):
        raise TypeError("venn: pass a list of set names, not a single string")
    names = [str(s) for s in sets]
    if not names:
        raise ValueError("venn: need at least one set name")
    if len(set(names)) != len(names):
        raise ValueError("venn: set names must be unique")
    return names
