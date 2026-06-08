"""Matplotlib renderer for ``EulerFit``."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal, cast

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.patches import Rectangle as MplRectangle
from matplotlib.path import Path

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from eunoia._models import EulerFit

RGBA = tuple[float, float, float, float]


def render(
    fit: EulerFit[Any],
    *,
    ax: Axes | None = None,
    colors: Sequence[Any] | dict[str, Any] | None = None,
    fills: dict[str, dict[str, Any]] | None = None,
    edges: dict[str, Any] | Sequence[dict[str, Any]] | None = None,
    labels: bool = True,
    quantities: bool | Literal["original", "fitted"] = False,
    complement: dict[str, Any] | None = None,
) -> Axes:
    """Draw an EulerFit. See ``EulerFit.plot`` for parameter docs."""
    if ax is None:
        _, ax = plt.subplots()

    # Universe container box (drawn first, behind everything).
    container = fit.container
    if container is not None:
        w, h = container.width, container.height
        x0 = container.center.x - w / 2.0
        y0 = container.center.y - h / 2.0
        container_kwargs: dict[str, Any] = {
            "facecolor": "#f0f0f0",
            "edgecolor": "0.4",
            "linewidth": 1.0,
            "zorder": 0,
        }
        if complement:
            container_kwargs.update(complement)
        ax.add_patch(MplRectangle((x0, y0), w, h, **container_kwargs))

    plot_data = fit.plot_data
    region_pieces = cast(
        "dict[str, list[dict[str, Any]]]", plot_data.get("region_pieces", {})
    )
    region_anchors = cast(
        "dict[str, tuple[float, float]]", plot_data.get("region_anchors", {})
    )
    set_anchors = cast(
        "dict[str, tuple[float, float]]", plot_data.get("set_anchors", {})
    )
    shape_outlines = cast(
        "dict[str, list[tuple[float, float]]]", plot_data.get("shape_outlines", {})
    )

    set_names = [shape.set for shape in fit.shapes]
    set_colors = _resolve_set_colors(set_names, colors)
    set_edges = _resolve_set_edges(set_names, edges)

    # Region fills
    for combo, pieces in region_pieces.items():
        # The empty combination is the complement region; the container box
        # already provides its background.
        if combo == "":
            continue
        region_color = _blend_region_color(combo, set_colors)
        fill_kwargs: dict[str, Any] = {
            "facecolor": region_color,
            "edgecolor": "none",
            "alpha": 0.5,
        }
        if fills and combo in fills:
            fill_kwargs.update(fills[combo])
        for piece in pieces:
            outer: list[tuple[float, float]] = piece["outer"]
            holes: list[list[tuple[float, float]]] = piece["holes"]
            path = _make_compound_path(outer, holes)
            if path is not None:
                ax.add_patch(PathPatch(path, **fill_kwargs))

    # Set boundaries
    edge_defaults: dict[str, Any] = {
        "facecolor": "none",
        "linewidth": 1.0,
    }
    for name, outline in shape_outlines.items():
        if len(outline) < 3:
            continue
        ek: dict[str, Any] = {**edge_defaults, "edgecolor": set_colors[name]}
        ek.update(set_edges.get(name, {}))
        path = _make_compound_path(outline, [])
        if path is not None:
            ax.add_patch(PathPatch(path, **ek))

    # Resolve the quantity values up front so labels know whether a quantity
    # shares their anchor (and must make room for it).
    values: dict[str, float] = {}
    if quantities:
        kind: Literal["original", "fitted"] = (
            "fitted" if quantities == "fitted" else "original"
        )
        values = fit.original_values if kind == "original" else fit.fitted_values

    # A set label and a region quantity can land on the exact same anchor: the
    # core derives every set anchor from a region anchor (the set's own
    # exclusive region, or -- for a set nested inside another with no exclusive
    # area -- the largest containing region, copied verbatim). It does not tell
    # us which region, only the resulting point, but because that point is the
    # same `Point` the region anchor came from, exact equality identifies the
    # collision. When both are shown we stack the pair (name above, value below)
    # instead of letting them overlap.
    label_points = set(set_anchors.values()) if labels else set()
    quantity_points = (
        {xy for combo, xy in region_anchors.items() if combo in values}
        if quantities
        else set()
    )

    # Set labels
    if labels:
        for name, (x, y) in set_anchors.items():
            va = "bottom" if (x, y) in quantity_points else "center"
            ax.text(x, y, name, ha="center", va=va, fontsize=11)

    # Region quantities
    if quantities:
        for combo, (x, y) in region_anchors.items():
            if combo not in values:
                continue
            va = "top" if (x, y) in label_points else "center"
            ax.text(
                x,
                y,
                f"{values[combo]:.3g}",
                ha="center",
                va=va,
                fontsize=9,
                color="dimgray",
            )

    ax.relim()
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.axis("off")
    return ax


def _make_compound_path(
    outer: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
) -> Path | None:
    verts: list[tuple[float, float]] = []
    codes: list[int] = []
    for ring in [outer, *holes]:
        if len(ring) < 3:
            continue
        verts.append(ring[0])
        codes.append(int(Path.MOVETO))
        for v in ring[1:]:
            verts.append(v)
            codes.append(int(Path.LINETO))
        verts.append(ring[0])
        codes.append(int(Path.CLOSEPOLY))
    if not verts:
        return None
    return Path(verts, codes)


def _resolve_set_colors(
    set_names: list[str],
    colors: Sequence[Any] | dict[str, Any] | None,
) -> dict[str, RGBA]:
    if colors is None:
        cmap = plt.get_cmap("tab10")
        return {name: cmap(i % 10) for i, name in enumerate(set_names)}
    if isinstance(colors, dict):
        return {name: mcolors.to_rgba(colors[name]) for name in set_names}
    if isinstance(colors, str):
        raise TypeError("colors must be a sequence or dict, not a single color string")
    seq = list(colors)
    if len(seq) < len(set_names):
        raise ValueError(
            f"colors sequence has {len(seq)} entries but there are "
            f"{len(set_names)} sets"
        )
    return {name: mcolors.to_rgba(seq[i]) for i, name in enumerate(set_names)}


def _resolve_set_edges(
    set_names: list[str],
    edges: dict[str, Any] | Sequence[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Normalize ``edges`` to a per-set mapping of ``PathPatch`` kwargs.

    ``edges`` may be:

    * ``None`` — no overrides (every set gets ``{}``).
    * a flat dict of ``PathPatch`` kwargs — applied uniformly to every set.
    * a per-set dict keyed by set name, whose values are kwargs dicts — each
      set styled independently; sets absent from the dict get ``{}``.
    * a sequence of kwargs dicts — one per set, in shape order.

    A dict is read as per-set when *all* its values are themselves dicts;
    otherwise it is a single uniform style (no ``PathPatch`` kwarg takes a
    dict, so the two cases never collide).
    """
    if edges is None:
        return {name: {} for name in set_names}
    if isinstance(edges, dict):
        if edges and all(isinstance(v, dict) for v in edges.values()):
            unknown = [k for k in edges if k not in set_names]
            if unknown:
                raise ValueError(
                    f"edges has entries for unknown sets {unknown}; "
                    f"known sets are {set_names}"
                )
            return {name: dict(edges.get(name, {})) for name in set_names}
        return {name: dict(edges) for name in set_names}
    if isinstance(edges, str):
        raise TypeError("edges must be a dict or a sequence of dicts, not a string")
    seq = list(edges)
    if len(seq) < len(set_names):
        raise ValueError(
            f"edges sequence has {len(seq)} entries but there are {len(set_names)} sets"
        )
    return {name: dict(seq[i]) for i, name in enumerate(set_names)}


def _blend_region_color(
    combo: str,
    set_colors: dict[str, RGBA],
) -> RGBA:
    parts = [s.strip() for s in combo.split("&") if s.strip()]
    cs = [set_colors[p] for p in parts if p in set_colors]
    if not cs:
        return (0.5, 0.5, 0.5, 1.0)
    n = len(cs)
    return (
        sum(c[0] for c in cs) / n,
        sum(c[1] for c in cs) / n,
        sum(c[2] for c in cs) / n,
        sum(c[3] for c in cs) / n,
    )
