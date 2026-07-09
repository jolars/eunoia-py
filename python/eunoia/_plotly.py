"""Interactive plotly renderer for ``EulerFit`` (the ``eunoia[plotly]`` extra).

A purely additive companion to the matplotlib renderer in ``eunoia._plot``: it
reuses that module's backend-neutral content helpers (color, quantity, member,
and label resolution) and the Rust core's size-aware label placement
(``_place_labels``), and emits a :class:`plotly.graph_objects.Figure` instead of
drawing onto an ``Axes``.

The one thing plotly cannot do that matplotlib can is measure text
synchronously, so label placement is fed by :mod:`eunoia._metrics` (glyph
advances via fontTools) rather than a live renderer. The metrics are approximate
-- the browser renders a different font -- but the size-aware placement only
needs to know roughly whether a block fits, and per-region hover tooltips (this
backend's reason for existing) cover regions too small for any text.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from eunoia._eunoia import _place_labels
from eunoia._metrics import TextMeasurer, default_measurer
from eunoia._models import VennFit
from eunoia._options import get_options
from eunoia._render_common import (
    blend_region_color,
    region_rings,
    resolve_members,
    resolve_quantities,
    resolve_set_colors,
    resolve_set_edges,
    resolve_set_labels,
)

if TYPE_CHECKING:
    from eunoia._models import EulerFit

# Matplotlib point sizes map to plotly's pixel font sizes at the conventional
# 96 dpi so the two backends render text at a similar visual scale. The same
# factor is used when measuring, so measured and rendered sizes stay consistent.
_PT_TO_PX = 96.0 / 72.0

# Mirrors ``_plot._PLACE_MAX_ITERS``: each round re-measures against the
# (possibly expanded) view and re-places; exterior labels enlarge the view,
# which changes the data-unit size of the text. Interior-only diagrams settle in
# one round.
_PLACE_MAX_ITERS = 4

_Line = tuple[str, dict[str, Any]]
_MeasuredLine = tuple[str, dict[str, Any], float, float]
_Bounds = tuple[float, float, float, float]


def render_plotly(
    fit: EulerFit[Any],
    *,
    width: int = 700,
    height: int | None = None,
    colors: Sequence[Any] | dict[str, Any] | None = None,
    fills: dict[str, dict[str, Any]] | None = None,
    edges: dict[str, Any] | Sequence[dict[str, Any]] | None = None,
    labels: bool | dict[str, Any] | None = None,
    quantities: bool | str | dict[str, Any] | None = None,
    members: bool | dict[str, Any] | None = None,
    legend: bool | dict[str, Any] = False,
    complement: dict[str, Any] | None = None,
    hover: bool | str = True,
    measurer: TextMeasurer | None = None,
) -> Any:
    """Render an ``EulerFit`` to a plotly Figure. See ``EulerFit.plot_plotly``."""
    try:
        import plotly.graph_objects as go
    except ImportError as e:  # pragma: no cover - exercised only without plotly
        raise ImportError(
            "the plotly backend requires plotly and fonttools; "
            "install them with: pip install 'eunoia[plotly]'"
        ) from e

    if measurer is None:
        measurer = default_measurer()

    # ``quantities=None`` means "context default": off for a proportional
    # EulerFit, on for a topological VennFit built with supplied values.
    if quantities is None:
        quantities = isinstance(fit, VennFit) and bool(fit.original_values)

    opts = get_options()

    plot_data = fit.plot_data
    region_pieces = cast(
        "dict[str, list[dict[str, Any]]]", plot_data.get("region_pieces", {})
    )
    set_anchors = cast(
        "dict[str, tuple[float, float]]", plot_data.get("set_anchors", {})
    )
    set_anchor_regions = cast("dict[str, str]", plot_data.get("set_anchor_regions", {}))
    shape_outlines = cast(
        "dict[str, list[tuple[float, float]]]", plot_data.get("shape_outlines", {})
    )

    set_names = [shape.set for shape in fit.shapes]
    set_colors = resolve_set_colors(set_names, colors, opts["palette"])
    set_edges = resolve_set_edges(set_names, edges)

    label_specs: dict[str, tuple[str, dict[str, Any]] | None]
    if isinstance(labels, dict):
        show_labels = True
        label_specs = resolve_set_labels(set_names, labels)
    else:
        show_labels = (not bool(legend)) if labels is None else bool(labels)
        label_specs = {name: (name, {}) for name in set_names}

    fig = go.Figure()

    container = fit.container
    container_box: _Bounds | None = None
    if container is not None:
        container_box = (
            container.center.x,
            container.center.y,
            container.width,
            container.height,
        )
        _add_container(fig, container, opts["complement"], complement)

    fill_alpha = opts["fills"].get("alpha", 0.5)
    _add_fills(fig, region_pieces, set_colors, fill_alpha, fills)
    _add_outlines(fig, shape_outlines, set_colors, opts["edges"], set_edges)

    # Compose per-region label blocks exactly as ``_plot.render`` does: each set
    # name into the region its anchor was derived from, each quantity into its
    # region, members below. A set name and its region's quantity stack as one
    # block, placed together by the core so a block that doesn't fit is pushed
    # out with a leader instead of overflowing a thin region.
    region_lines, fallback_names = _compose_labels(
        fit,
        opts,
        set_names,
        label_specs,
        show_labels,
        set_anchors,
        set_anchor_regions,
        region_pieces,
        quantities,
        members,
    )

    rings = region_rings(region_pieces)
    bounds = _diagram_bounds(rings, container_box)

    if region_lines:
        placements, measured, bounds = _measure_and_place(
            region_lines, rings, container_box, bounds, width, height, measurer
        )
        _draw_labels(fig, placements, measured)

    for fx, fy, ftext, fstyle in fallback_names:
        _add_label_line(fig, fx, fy, ftext, fstyle, xanchor="center", yanchor="middle")

    if hover:
        _add_hover(fig, fit, region_pieces, hover)

    if legend:
        _add_legend(fig, set_names, set_colors, fill_alpha)

    _finalize_layout(fig, bounds, width, height, bool(legend))
    return fig


def _to_rgba_str(color: Any, alpha: float | None = None) -> str:
    """Normalize any matplotlib color to a plotly ``rgba(...)`` string."""
    from matplotlib.colors import to_rgba

    r, g, b, a = to_rgba(color)
    a = a if alpha is None else alpha
    return f"rgba({round(r * 255)},{round(g * 255)},{round(b * 255)},{a})"


def _svg_path(rings: list[list[tuple[float, float]]]) -> str | None:
    """Build an SVG path (``M``/``L``/``Z`` subpaths) from a list of rings.

    Holes are just extra subpaths; plotly fills the compound path with the
    even-odd rule, matching matplotlib's compound ``Path``.
    """
    segments: list[str] = []
    for ring in rings:
        if len(ring) < 3:
            continue
        x0, y0 = ring[0]
        segments.append(f"M{x0},{y0}")
        segments.extend(f"L{x},{y}" for x, y in ring[1:])
        segments.append("Z")
    return "".join(segments) or None


def _add_container(
    fig: Any,
    container: Any,
    opt_style: dict[str, Any],
    override: dict[str, Any] | None,
) -> None:
    style = {**opt_style, **(override or {})}
    w, h = container.width, container.height
    x0 = container.center.x - w / 2.0
    y0 = container.center.y - h / 2.0
    fig.add_shape(
        type="rect",
        x0=x0,
        y0=y0,
        x1=x0 + w,
        y1=y0 + h,
        fillcolor=_to_rgba_str(style.get("facecolor", "#f0f0f0")),
        line={
            "color": _to_rgba_str(style.get("edgecolor", "0.4")),
            "width": style.get("linewidth", 1.0),
        },
        layer="below",
    )


def _add_fills(
    fig: Any,
    region_pieces: dict[str, list[dict[str, Any]]],
    set_colors: dict[str, Any],
    fill_alpha: float,
    fills: dict[str, dict[str, Any]] | None,
) -> None:
    for combo, pieces in region_pieces.items():
        # The empty combination is the complement; the container box already
        # provides its background.
        if combo == "":
            continue
        override = (fills or {}).get(combo, {})
        base_color = override.get("facecolor", blend_region_color(combo, set_colors))
        alpha = override.get("alpha", fill_alpha)
        for piece in pieces:
            path = _svg_path([piece["outer"], *piece["holes"]])
            if path is None:
                continue
            fig.add_shape(
                type="path",
                path=path,
                fillcolor=_to_rgba_str(base_color, alpha),
                fillrule="evenodd",
                line={"width": 0},
                layer="below",
            )


def _add_outlines(
    fig: Any,
    shape_outlines: dict[str, list[tuple[float, float]]],
    set_colors: dict[str, Any],
    opt_edges: dict[str, Any],
    set_edges: dict[str, dict[str, Any]],
) -> None:
    for name, outline in shape_outlines.items():
        if len(outline) < 3:
            continue
        style = {"edgecolor": set_colors[name], **opt_edges, **set_edges.get(name, {})}
        path = _svg_path([outline])
        if path is None:
            continue
        fig.add_shape(
            type="path",
            path=path,
            fillcolor="rgba(0,0,0,0)",
            line={
                "color": _to_rgba_str(style.get("edgecolor", "black")),
                "width": style.get("linewidth", 1.0),
            },
            layer="below",
        )


def _compose_labels(
    fit: EulerFit[Any],
    opts: dict[str, Any],
    set_names: list[str],
    label_specs: dict[str, tuple[str, dict[str, Any]] | None],
    show_labels: bool,
    set_anchors: dict[str, tuple[float, float]],
    set_anchor_regions: dict[str, str],
    region_pieces: dict[str, list[dict[str, Any]]],
    quantities: bool | str | dict[str, Any],
    members: bool | dict[str, Any] | None,
) -> tuple[dict[str, list[_Line]], list[tuple[float, float, str, dict[str, Any]]]]:
    """Build region label blocks and fallback set labels (see ``_plot.render``)."""
    region_lines: dict[str, list[_Line]] = {}
    fallback_names: list[tuple[float, float, str, dict[str, Any]]] = []

    if show_labels:
        for name in set_names:
            spec = label_specs.get(name)
            if spec is None:
                continue
            text, style = spec
            line_style: dict[str, Any] = {**opts["labels"], **style}
            region = set_anchor_regions.get(name)
            if region is not None and region in region_pieces:
                region_lines.setdefault(region, []).append((text, line_style))
            elif name in set_anchors:
                x, y = set_anchors[name]
                fallback_names.append((x, y, text, line_style))

    quant = resolve_quantities(fit, quantities)
    if quant is not None:
        values, fmt, q_style = quant
        for combo in region_pieces:
            if combo == "" or combo not in values:
                continue
            line_style = {**opts["quantities"], **q_style}
            region_lines.setdefault(combo, []).append((fmt(values[combo]), line_style))

    mem = resolve_members(fit, members)
    if mem is not None:
        mem_text, mem_style = mem
        for combo, text in mem_text.items():
            if combo not in region_pieces:
                continue
            line_style = {**opts["members"], **mem_style}
            region_lines.setdefault(combo, []).append((text, line_style))

    return region_lines, fallback_names


def _diagram_bounds(
    rings: dict[str, list[list[tuple[float, float]]]],
    container_box: _Bounds | None,
    extra: list[tuple[float, float]] | None = None,
) -> _Bounds:
    """Data-space ``(xmin, xmax, ymin, ymax)`` over rings, container, and extras."""
    xs: list[float] = []
    ys: list[float] = []
    for region in rings.values():
        for ring in region:
            for x, y in ring:
                xs.append(x)
                ys.append(y)
    if container_box is not None:
        cx, cy, w, h = container_box
        xs.extend((cx - w / 2.0, cx + w / 2.0))
        ys.extend((cy - h / 2.0, cy + h / 2.0))
    for x, y in extra or ():
        xs.append(x)
        ys.append(y)
    if not xs or not ys:
        return (0.0, 1.0, 0.0, 1.0)
    return (min(xs), max(xs), min(ys), max(ys))


def _px_per_data(bounds: _Bounds, width: int, height: int | None) -> float:
    """Pixels per data unit under equal aspect, from the current view bounds."""
    xmin, xmax, ymin, ymax = bounds
    dw = (xmax - xmin) or 1.0
    dh = (ymax - ymin) or 1.0
    if height is None:
        return width / dw
    # An explicit figure box: plotly's equal-aspect fit is limited by the
    # tighter of the two dimensions.
    return min(width / dw, height / dh)


def _measure_and_place(
    region_lines: dict[str, list[_Line]],
    rings: dict[str, list[list[tuple[float, float]]]],
    container_box: _Bounds | None,
    bounds: _Bounds,
    width: int,
    height: int | None,
    measurer: TextMeasurer,
) -> tuple[dict[str, Any], dict[str, list[_MeasuredLine]], _Bounds]:
    """Measure each block in data units and place it, expanding the view for
    exterior labels until it settles. Returns placements, measured lines, and the
    final view bounds."""
    placements: dict[str, Any] = {}
    measured: dict[str, list[_MeasuredLine]] = {}
    extra: list[tuple[float, float]] = []

    for _ in range(_PLACE_MAX_ITERS):
        bounds = _diagram_bounds(rings, container_box, extra)
        scale = _px_per_data(bounds, width, height)

        sizes: dict[str, tuple[float, float]] = {}
        measured = {}
        for region, lines in region_lines.items():
            dims: list[_MeasuredLine] = []
            for text, style in lines:
                px = style.get("fontsize", 11) * _PT_TO_PX
                w_px, h_px = measurer.text_size_points(text, px)
                dims.append((text, style, w_px / scale, h_px / scale))
            sizes[region] = (max(d[2] for d in dims), sum(d[3] for d in dims))
            measured[region] = dims

        placements = _place_labels(rings, sizes, container_box, exterior="raycast")

        new_extra: list[tuple[float, float]] = []
        for pl in placements.values():
            if str(pl["kind"]).startswith("exterior"):
                new_extra.append(pl["anchor"])
                if pl["leader_end"] is not None:
                    new_extra.append(pl["leader_end"])
        if not new_extra or new_extra == extra:
            extra = new_extra
            break
        extra = new_extra

    bounds = _diagram_bounds(rings, container_box, extra)
    return placements, measured, bounds


def _add_label_line(
    fig: Any,
    x: float,
    y: float,
    text: str,
    style: dict[str, Any],
    *,
    xanchor: str,
    yanchor: str,
) -> None:
    font: dict[str, Any] = {"size": style.get("fontsize", 11) * _PT_TO_PX}
    if "color" in style:
        font["color"] = _to_rgba_str(style["color"])
    fig.add_annotation(
        x=x,
        y=y,
        text=text.replace("\n", "<br>"),
        showarrow=False,
        xanchor=xanchor,
        yanchor=yanchor,
        align="center",
        font=font,
    )


_HA_TO_XANCHOR = {"center": "center", "left": "left", "right": "right"}


def _draw_labels(
    fig: Any,
    placements: dict[str, Any],
    measured: dict[str, list[_MeasuredLine]],
) -> None:
    """Draw each placed block: leader (if exterior) then stacked lines."""
    for region, dims in measured.items():
        placement = placements.get(region)
        if placement is None:
            continue
        ax_x, ax_y = placement["anchor"]

        if (
            str(placement["kind"]).startswith("exterior")
            and placement["tether"] is not None
            and placement["leader_end"] is not None
        ):
            waypoints = placement["leader_waypoints"]
            points = [placement["tether"], *waypoints, placement["leader_end"]]
            path = "M" + "L".join(f"{x},{y}" for x, y in points)
            leader_color = _to_rgba_str(dims[0][1].get("color", "dimgray"))
            fig.add_shape(
                type="path",
                path=path,
                line={"color": leader_color, "width": 0.8},
                layer="below",
            )

        # Stack lines centered on the anchor (the block's center), top first,
        # each drawn with ``yanchor="top"`` at a descending cursor.
        total_h = sum(d[3] for d in dims)
        y_cursor = ax_y + total_h / 2.0
        for text, style, _, h in dims:
            xanchor = _HA_TO_XANCHOR.get(style.get("ha", "center"), "center")
            _add_label_line(
                fig, ax_x, y_cursor, text, style, xanchor=xanchor, yanchor="top"
            )
            y_cursor -= h


def _hover_text(
    combo: str,
    values: dict[str, float] | None,
    members_map: dict[str, list[str]] | None,
    hover: bool | str,
) -> str | None:
    """Compose a region's tooltip from its key, count, and member names.

    ``hover=True`` shows whatever is available; a string restricts to
    ``"members"``, ``"quantities"`` (alias ``"counts"``), or ``"all"``.
    """
    want_counts = hover in (True, "all", "quantities", "counts")
    want_members = hover in (True, "all", "members")
    lines = [f"<b>{combo}</b>"]
    if want_counts and values is not None and combo in values:
        lines.append(f"n = {values[combo]:.3g}")
    if want_members and members_map is not None and members_map.get(combo):
        lines.extend(members_map[combo])
    return "<br>".join(lines)


def _add_hover(
    fig: Any,
    fit: EulerFit[Any],
    region_pieces: dict[str, list[dict[str, Any]]],
    hover: bool | str,
) -> None:
    """Add one transparent, fill-hoverable trace per region for tooltips.

    The visible fill is drawn as a shape; these traces exist only to carry
    ``hovertext`` over each region's area (``hoveron="fills"``).
    """
    import plotly.graph_objects as go

    # Prefer the values the user would recognize (input scale) for the count.
    values = fit.original_values or fit.fitted_values
    members_map = fit.members
    for combo, pieces in region_pieces.items():
        if combo == "":
            continue
        text = _hover_text(combo, values, members_map, hover)
        if not text:
            continue
        for piece in pieces:
            outer = piece["outer"]
            if len(outer) < 3:
                continue
            xs = [p[0] for p in outer]
            ys = [p[1] for p in outer]
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    fill="toself",
                    fillcolor="rgba(0,0,0,0)",
                    line={"width": 0},
                    mode="lines",
                    hoveron="fills",
                    hoverinfo="text",
                    text=text,
                    name=combo,
                    showlegend=False,
                )
            )


def _add_legend(
    fig: Any,
    set_names: list[str],
    set_colors: dict[str, Any],
    fill_alpha: float,
) -> None:
    """Add one legend-only trace per set with its (alpha-matched) fill color."""
    import plotly.graph_objects as go

    for name in set_names:
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker={
                    "size": 12,
                    "color": _to_rgba_str(set_colors[name], fill_alpha),
                    "symbol": "square",
                },
                name=name,
                showlegend=True,
            )
        )


def _finalize_layout(
    fig: Any,
    bounds: _Bounds,
    width: int,
    height: int | None,
    show_legend: bool,
) -> None:
    xmin, xmax, ymin, ymax = bounds
    dw = (xmax - xmin) or 1.0
    dh = (ymax - ymin) or 1.0
    pad = 0.02 * max(dw, dh)
    if height is None:
        height = round(width * (dh + 2 * pad) / (dw + 2 * pad))

    fig.update_layout(
        width=width,
        height=height,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="white",
        showlegend=show_legend,
        hovermode="closest",
        xaxis={
            "visible": False,
            "range": [xmin - pad, xmax + pad],
            "constrain": "domain",
        },
        yaxis={
            "visible": False,
            "range": [ymin - pad, ymax + pad],
            "scaleanchor": "x",
            "scaleratio": 1,
        },
    )
