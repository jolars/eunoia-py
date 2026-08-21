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

import warnings
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from eunoia._eunoia import (
    _place_glyph_boxes,
    _place_glyphs,
    _place_labels,
    _place_set_labels,
)
from eunoia._metrics import TextMeasurer, default_measurer
from eunoia._models import VennFit
from eunoia._options import get_options
from eunoia._render_common import (
    blend_region_color,
    region_rings,
    requested_glyph_counts,
    resolve_glyph_options,
    resolve_label_controls,
    resolve_member_display,
    resolve_quantities,
    resolve_set_colors,
    resolve_set_edges,
    resolve_set_labels,
    shift_color,
    split_label_options,
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
_Box = tuple[float, float, float, float]


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
    glyphs: bool | dict[str, Any] = False,
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

    option_label_style, option_label_controls = split_label_options(opts["labels"])
    explicit_label_controls: dict[str, Any] = {}
    label_specs: dict[str, tuple[str, dict[str, Any]] | None]
    if isinstance(labels, dict):
        show_labels = True
        label_input, explicit_label_controls = split_label_options(labels)
        label_specs = resolve_set_labels(set_names, label_input)
    else:
        show_labels = (not bool(legend)) if labels is None else bool(labels)
        label_specs = {name: (name, {}) for name in set_names}
    set_position, placement_config, set_placement_config = resolve_label_controls(
        option_label_controls, explicit_label_controls
    )
    member_display = resolve_member_display(fit, members, opts["members"])

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
    region_lines, fallback_names, outside_names, packed_members = _compose_labels(
        fit,
        opts,
        set_names,
        label_specs,
        show_labels,
        set_anchors,
        set_anchor_regions,
        region_pieces,
        quantities,
        member_display,
        option_label_style,
        set_position,
    )

    rings = region_rings(region_pieces)
    bounds = _diagram_bounds(rings, container_box)

    placements: dict[str, Any] = {}
    measured: dict[str, list[_MeasuredLine]] = {}
    if region_lines:
        placements, measured, bounds = _measure_and_place(
            region_lines,
            rings,
            container_box,
            bounds,
            width,
            height,
            measurer,
            placement_config,
        )

    obstacles = _placement_boxes(placements, measured)
    set_placements: dict[str, Any] = {}
    set_measured: dict[str, _MeasuredLine] = {}
    if outside_names:
        set_placements, set_measured, bounds = _measure_and_place_set_labels(
            outside_names,
            shape_outlines,
            container_box,
            bounds,
            width,
            height,
            measurer,
            set_placement_config,
            obstacles,
        )
        obstacles.extend(_set_placement_boxes(set_placements, set_measured))

    packed_result: (
        tuple[dict[str, list[str]], dict[str, Any], dict[str, Any]] | None
    ) = None
    if packed_members is not None:
        packed_result = _place_packed_members(
            packed_members,
            region_rings(region_pieces, include_complement=True),
            bounds,
            width,
            height,
            measurer,
            obstacles,
        )
        obstacles.extend(_packed_member_boxes(packed_result[1]))

    glyph_options = resolve_glyph_options(glyphs, opts["glyphs"])
    if glyph_options is not None:
        _add_glyphs(
            fig,
            fit,
            region_rings(region_pieces, include_complement=True),
            set_colors,
            glyph_options,
            obstacles,
            bounds,
            width,
            height,
            opts["complement"],
        )
    if packed_result is not None:
        _draw_packed_members(fig, packed_result)
    if region_lines:
        _draw_labels(
            fig,
            placements,
            measured,
            cast("dict[str, Any]", placement_config.get("leader", {})),
        )
    if outside_names:
        _draw_set_labels(fig, outside_names, set_placements)

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
    member_display: tuple[str, dict[str, list[str]], dict[str, Any], dict[str, Any]]
    | None,
    option_label_style: dict[str, Any],
    set_position: str,
) -> tuple[
    dict[str, list[_Line]],
    list[tuple[float, float, str, dict[str, Any]]],
    dict[str, tuple[str, dict[str, Any]]],
    tuple[dict[str, list[str]], dict[str, Any], dict[str, Any]] | None,
]:
    """Build region label blocks and fallback set labels (see ``_plot.render``)."""
    region_lines: dict[str, list[_Line]] = {}
    fallback_names: list[tuple[float, float, str, dict[str, Any]]] = []
    outside_names: dict[str, tuple[str, dict[str, Any]]] = {}

    if show_labels:
        for name in set_names:
            spec = label_specs.get(name)
            if spec is None:
                continue
            text, style = spec
            line_style: dict[str, Any] = {**option_label_style, **style}
            if set_position == "outside":
                outside_names[name] = (text, line_style)
            else:
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

    packed_members: (
        tuple[dict[str, list[str]], dict[str, Any], dict[str, Any]] | None
    ) = None
    if member_display is not None:
        mode, content, packing, style = member_display
        if mode == "packed":
            packed_members = (content, packing, style)
        else:
            for combo, names in content.items():
                if combo not in region_pieces:
                    continue
                region_lines.setdefault(combo, []).append(("\n".join(names), style))

    return region_lines, fallback_names, outside_names, packed_members


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
    placement: dict[str, Any],
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

        placement_kwargs = {
            key: value
            for key, value in {
                "precision": placement.get("precision"),
                "exterior": placement.get("strategy", "raycast"),
                "tether": placement.get("tether"),
                "leader_gap": placement.get("leader_gap"),
                "margin": placement.get("margin"),
                "iterations": placement.get("iterations"),
                "min_gap": placement.get("min_gap"),
            }.items()
            if value is not None
        }
        placements = _place_labels(rings, sizes, container_box, **placement_kwargs)

        new_extra: list[tuple[float, float]] = []
        for region, pl in placements.items():
            if str(pl["kind"]).startswith("exterior"):
                dims = measured[region]
                width_data = max(d[2] for d in dims)
                height_data = sum(d[3] for d in dims)
                x, y = pl["anchor"]
                new_extra.extend(
                    [
                        (x - width_data / 2.0, y - height_data / 2.0),
                        (x + width_data / 2.0, y + height_data / 2.0),
                    ]
                )
                if pl["leader_end"] is not None:
                    new_extra.append(pl["leader_end"])
        if not new_extra or new_extra == extra:
            extra = new_extra
            break
        extra = new_extra

    bounds = _diagram_bounds(rings, container_box, extra)
    return placements, measured, bounds


def _placement_boxes(
    placements: dict[str, Any], measured: dict[str, list[_MeasuredLine]]
) -> list[_Box]:
    boxes: list[_Box] = []
    for region, placement in placements.items():
        dims = measured.get(region)
        if not dims:
            continue
        x, y = placement["anchor"]
        boxes.append((x, y, max(d[2] for d in dims), sum(d[3] for d in dims)))
    return boxes


def _set_placement_boxes(
    placements: dict[str, Any], measured: dict[str, _MeasuredLine]
) -> list[_Box]:
    return [
        (
            placement["anchor"][0],
            placement["anchor"][1],
            measured[name][2],
            measured[name][3],
        )
        for name, placement in placements.items()
        if name in measured
    ]


def _bounds_with_boxes(base: _Bounds, boxes: list[_Box]) -> _Bounds:
    xmin, xmax, ymin, ymax = base
    for x, y, width, height in boxes:
        xmin = min(xmin, x - width / 2.0)
        xmax = max(xmax, x + width / 2.0)
        ymin = min(ymin, y - height / 2.0)
        ymax = max(ymax, y + height / 2.0)
    return xmin, xmax, ymin, ymax


def _measure_and_place_set_labels(
    names: dict[str, tuple[str, dict[str, Any]]],
    outlines: dict[str, list[tuple[float, float]]],
    container: _Bounds | None,
    bounds: _Bounds,
    width: int,
    height: int | None,
    measurer: TextMeasurer,
    config: dict[str, Any],
    obstacles: list[_Box],
) -> tuple[dict[str, Any], dict[str, _MeasuredLine], _Bounds]:
    base_bounds = bounds
    placements: dict[str, Any] = {}
    measured: dict[str, _MeasuredLine] = {}
    for _ in range(_PLACE_MAX_ITERS):
        scale = _px_per_data(bounds, width, height)
        sizes: dict[str, tuple[float, float]] = {}
        measured = {}
        for name, (text, style) in names.items():
            font_px = style.get("fontsize", 11) * _PT_TO_PX
            width_px, height_px = measurer.text_size_points(text, font_px)
            item = (text, style, width_px / scale, height_px / scale)
            measured[name] = item
            sizes[name] = (item[2], item[3])
        placements = _place_set_labels(
            outlines,
            sizes,
            container,
            margin=config.get("margin"),
            angular_steps=config.get("angular_steps"),
            precision=config.get("precision"),
            obstacles=obstacles,
        )
        new_bounds = _bounds_with_boxes(
            base_bounds, _set_placement_boxes(placements, measured)
        )
        if new_bounds == bounds:
            break
        bounds = new_bounds
    return placements, measured, bounds


def _draw_set_labels(
    fig: Any,
    names: dict[str, tuple[str, dict[str, Any]]],
    placements: dict[str, Any],
) -> None:
    for name, placement in placements.items():
        spec = names.get(name)
        if spec is None:
            continue
        text, style = spec
        _add_label_line(
            fig,
            placement["anchor"][0],
            placement["anchor"][1],
            text,
            style,
            xanchor=_HA_TO_XANCHOR.get(style.get("ha", "center"), "center"),
            yanchor="middle",
        )


def _place_packed_members(
    spec: tuple[dict[str, list[str]], dict[str, Any], dict[str, Any]],
    rings: dict[str, list[list[tuple[float, float]]]],
    bounds: _Bounds,
    width: int,
    height: int | None,
    measurer: TextMeasurer,
    obstacles: list[_Box],
) -> tuple[dict[str, list[str]], dict[str, Any], dict[str, Any]]:
    content, packing, style = spec
    pixels_per_data = _px_per_data(bounds, width, height)
    font_px = style.get("fontsize", 9) * _PT_TO_PX
    sizes: dict[str, list[tuple[float, float]]] = {}
    for region, names in content.items():
        if region not in rings:
            continue
        sizes[region] = []
        for name in names:
            width_px, height_px = measurer.text_size_points(name, font_px)
            sizes[region].append(
                (width_px / pixels_per_data, height_px / pixels_per_data)
            )
    placed = _place_glyph_boxes(
        rings,
        sizes,
        arrangement=packing.get("arrangement"),
        scale=packing.get("scale"),
        min_scale=packing.get("min_scale"),
        gap=packing.get("gap"),
        seed=packing.get("seed"),
        precision=packing.get("precision"),
        max_attempts=packing.get("max_attempts"),
        obstacles=obstacles,
    )
    if placed["unplaced"]:
        warnings.warn(
            f"packed member labels did not fit: {placed['unplaced']}",
            UserWarning,
            stacklevel=3,
        )
    return content, cast("dict[str, Any]", placed), style


def _packed_member_boxes(placed: dict[str, Any]) -> list[_Box]:
    return [box for boxes in placed["boxes"].values() for box in boxes]


def _draw_packed_members(
    fig: Any,
    result: tuple[dict[str, list[str]], dict[str, Any], dict[str, Any]],
) -> None:
    content, placed, style = result
    draw_style = dict(style)
    draw_style["fontsize"] = style.get("fontsize", 9) * float(placed["scale"])
    for region, boxes in placed["boxes"].items():
        for name, (x, y, _, _) in zip(content.get(region, []), boxes, strict=False):
            _add_label_line(
                fig,
                x,
                y,
                name,
                draw_style,
                xanchor=_HA_TO_XANCHOR.get(style.get("ha", "center"), "center"),
                yanchor="middle",
            )


def _add_glyphs(
    fig: Any,
    fit: EulerFit[Any],
    rings: dict[str, list[list[tuple[float, float]]]],
    set_colors: dict[str, Any],
    resolved: tuple[dict[str, Any], dict[str, Any]],
    obstacles: list[_Box],
    bounds: _Bounds,
    width: int,
    height: int | None,
    complement_style: dict[str, Any],
) -> None:
    import plotly.graph_objects as go

    placement, style = resolved
    placed = _place_glyphs(
        rings,
        requested_glyph_counts(fit),
        arrangement=placement.get("arrangement"),
        radius=placement.get("radius"),
        gap=placement.get("gap"),
        seed=placement.get("seed"),
        precision=placement.get("precision"),
        max_attempts=placement.get("max_attempts"),
        obstacles=obstacles,
    )
    if placed["unplaced"]:
        warnings.warn(
            f"unit glyphs did not fit: {placed['unplaced']}",
            UserWarning,
            stacklevel=3,
        )
    tint = float(style.get("tint", 0.45))
    edge_tint = float(style.get("edge_tint", -0.35))
    marker_size = 2.0 * placed["radius"] * _px_per_data(bounds, width, height)
    for region, points in placed["positions"].items():
        base = (
            complement_style.get("facecolor", "#f0f0f0")
            if region == ""
            else blend_region_color(region, set_colors)
        )
        fig.add_trace(
            go.Scatter(
                x=[point[0] for point in points],
                y=[point[1] for point in points],
                mode="markers",
                marker={
                    "size": marker_size,
                    "color": _to_rgba_str(
                        style.get("facecolor", shift_color(base, tint)),
                        style.get("alpha", 1.0),
                    ),
                    "line": {
                        "color": _to_rgba_str(
                            style.get("edgecolor", shift_color(base, edge_tint))
                        ),
                        "width": style.get("linewidth", 0.5),
                    },
                },
                hoverinfo="skip",
                showlegend=False,
                name=f"{region} glyphs",
            )
        )


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
    leader_style: dict[str, Any] | None = None,
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
            style = leader_style or {}
            leader_color = _to_rgba_str(
                style.get("color", dims[0][1].get("color", "dimgray"))
            )
            fig.add_shape(
                type="path",
                path=path,
                line={
                    "color": leader_color,
                    "width": style.get("linewidth", 0.8),
                    "dash": style.get("linestyle", "solid"),
                },
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
