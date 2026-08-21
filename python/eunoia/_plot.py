"""Matplotlib renderer for ``EulerFit``."""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Circle as MplCircle
from matplotlib.patches import Patch, PathPatch
from matplotlib.patches import Rectangle as MplRectangle
from matplotlib.path import Path

from eunoia._eunoia import (
    _place_glyph_boxes,
    _place_glyphs,
    _place_labels,
    _place_set_labels,
)
from eunoia._models import VennFit
from eunoia._options import get_options
from eunoia._render_common import (
    blend_region_color as _blend_region_color,
)
from eunoia._render_common import (
    region_rings as _region_rings,
)
from eunoia._render_common import requested_glyph_counts as _requested_glyph_counts
from eunoia._render_common import resolve_glyph_options as _resolve_glyph_options
from eunoia._render_common import resolve_label_controls as _resolve_label_controls
from eunoia._render_common import resolve_member_display as _resolve_member_display
from eunoia._render_common import (
    resolve_quantities as _resolve_quantities,
)
from eunoia._render_common import (
    resolve_set_colors as _resolve_set_colors,
)
from eunoia._render_common import (
    resolve_set_edges as _resolve_set_edges,
)
from eunoia._render_common import (
    resolve_set_labels as _resolve_set_labels,
)
from eunoia._render_common import shift_color as _shift_color
from eunoia._render_common import split_label_options as _split_label_options

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from eunoia._models import EulerFit


def render(
    fit: EulerFit[Any],
    *,
    ax: Axes | None = None,
    colors: Sequence[Any] | dict[str, Any] | None = None,
    fills: dict[str, dict[str, Any]] | None = None,
    edges: dict[str, Any] | Sequence[dict[str, Any]] | None = None,
    labels: bool | dict[str, Any] | None = None,
    quantities: bool | str | dict[str, Any] | None = None,
    members: bool | dict[str, Any] | None = None,
    glyphs: bool | dict[str, Any] = False,
    legend: bool | dict[str, Any] = False,
    complement: dict[str, Any] | None = None,
) -> Axes:
    """Draw an EulerFit. See ``EulerFit.plot`` for parameter docs."""
    if ax is None:
        _, ax = plt.subplots()

    # ``quantities=None`` means "context default": off for a proportional
    # EulerFit, but on for a topological VennFit that was built with supplied
    # values (which live in ``original_values``). An explicit value always wins.
    if quantities is None:
        quantities = isinstance(fit, VennFit) and bool(fit.original_values)

    # Global defaults (eunoia.options). Each call's explicit kwargs win over
    # these, which in turn win over matplotlib's own defaults.
    opts = get_options()

    # Universe container box (drawn first, behind everything).
    container = fit.container
    if container is not None:
        w, h = container.width, container.height
        x0 = container.center.x - w / 2.0
        y0 = container.center.y - h / 2.0
        container_kwargs: dict[str, Any] = {"zorder": 0, **opts["complement"]}
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
    set_anchor_regions = cast("dict[str, str]", plot_data.get("set_anchor_regions", {}))
    shape_outlines = cast(
        "dict[str, list[tuple[float, float]]]", plot_data.get("shape_outlines", {})
    )

    set_names = [shape.set for shape in fit.shapes]
    set_colors = _resolve_set_colors(set_names, colors, opts["palette"])
    set_edges = _resolve_set_edges(set_names, edges)

    # In-diagram set labels default off when a legend is shown (the legend
    # carries the names instead); an explicit ``labels=`` always wins. A dict
    # turns labels on and carries per-set text/style overrides.
    option_label_style, option_label_controls = _split_label_options(opts["labels"])
    explicit_label_controls: dict[str, Any] = {}
    label_specs: dict[str, tuple[str, dict[str, Any]] | None]
    if isinstance(labels, dict):
        show_labels = True
        label_input, explicit_label_controls = _split_label_options(labels)
        label_specs = _resolve_set_labels(set_names, label_input)
    else:
        show_labels = (not bool(legend)) if labels is None else bool(labels)
        label_specs = {name: (name, {}) for name in set_names}
    set_position, placement_config, set_placement_config = _resolve_label_controls(
        option_label_controls, explicit_label_controls
    )

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
            **opts["fills"],
        }
        if fills and combo in fills:
            fill_kwargs.update(fills[combo])
        for piece in pieces:
            outer: list[tuple[float, float]] = piece["outer"]
            holes: list[list[tuple[float, float]]] = piece["holes"]
            path = _make_compound_path(outer, holes)
            if path is not None:
                ax.add_patch(PathPatch(path, **fill_kwargs))

    # Set boundaries. Computed set color is the base edge color; a global
    # ``edges`` option (and then a per-call override) layers on top, so an
    # explicit ``edgecolor`` in either replaces the computed one.
    for name, outline in shape_outlines.items():
        if len(outline) < 3:
            continue
        ek: dict[str, Any] = {"facecolor": "none", "edgecolor": set_colors[name]}
        ek.update(opts["edges"])
        ek.update(set_edges.get(name, {}))
        path = _make_compound_path(outline, [])
        if path is not None:
            ax.add_patch(PathPatch(path, **ek))

    # Compose the per-region label content. Each set's name goes into the
    # region its anchor was derived from (``set_anchor_regions``: set name ->
    # canonical region key, the set's own exclusive region or, for a set with
    # no exclusive area, a containing region), and each shown quantity into its
    # own region. A set name and its region's quantity therefore land in the
    # same block and stack as one unit. We then place each block via the core's
    # size-aware placement (``_place_labels``), so a block that doesn't fit its
    # region is pushed outside with a leader line instead of overflowing the
    # boundary -- which a bare point anchor cannot avoid for a thin region.
    quant = _resolve_quantities(fit, quantities)
    values: dict[str, float] = quant[0] if quant is not None else {}

    # region key -> list of (text, ax.text style) lines, set names first.
    region_lines: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    # Set labels whose anchor was not derived from a region we have pieces for
    # fall back to the raw set anchor point (no size-aware placement).
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

    if quant is not None:
        _, fmt, q_style = quant
        for combo in region_anchors:
            if combo not in values:
                continue
            line_style = {**opts["quantities"], **q_style}
            region_lines.setdefault(combo, []).append((fmt(values[combo]), line_style))

    # Member names go into their region's block below any set name and quantity.
    # Only regions we actually drew (present in ``region_pieces``) can be placed;
    # a region with members but no geometry is skipped rather than measured
    # against a ring the core does not have.
    member_display = _resolve_member_display(fit, members, opts["members"])
    packed_members: (
        tuple[dict[str, list[str]], dict[str, Any], dict[str, Any]] | None
    ) = None
    if member_display is not None:
        member_mode, member_content, member_packing, member_style = member_display
        if member_mode == "packed":
            packed_members = (member_content, member_packing, member_style)
        else:
            for combo, names in member_content.items():
                if combo not in region_pieces:
                    continue
                line_style = dict(member_style)
                region_lines.setdefault(combo, []).append(
                    ("\n".join(names), line_style)
                )

    # Establish the data->display transform from the diagram geometry before
    # measuring any text: matplotlib only knows text extents in pixels, and only
    # once a renderer and axis limits exist.
    ax.relim()
    ax.autoscale_view()
    ax.set_aspect("equal")

    container_box = (
        (container.center.x, container.center.y, container.width, container.height)
        if container is not None
        else None
    )
    rings = _region_rings(region_pieces)
    placements: dict[str, Any] = {}
    measured: dict[str, list[_MeasuredLine]] = {}
    if region_lines:
        placements, measured = _place_region_labels(
            ax, region_lines, rings, container_box, placement_config
        )

    label_obstacles = _placement_boxes(placements, measured)
    set_placements: dict[str, Any] = {}
    set_measured: dict[str, _MeasuredLine] = {}
    if outside_names:
        set_placements, set_measured = _place_exterior_set_labels(
            ax,
            outside_names,
            shape_outlines,
            container_box,
            set_placement_config,
            label_obstacles,
        )
        label_obstacles.extend(_set_placement_boxes(set_placements, set_measured))

    packed_result: (
        tuple[dict[str, list[str]], dict[str, Any], dict[str, Any]] | None
    ) = None
    if packed_members is not None:
        packed_result = _place_packed_members(
            ax,
            packed_members,
            _region_rings(region_pieces, include_complement=True),
            label_obstacles,
        )
        label_obstacles.extend(_packed_member_boxes(packed_result[1]))

    glyph_options = _resolve_glyph_options(glyphs, opts["glyphs"])
    if glyph_options is not None:
        _draw_glyphs(
            ax,
            fit,
            _region_rings(region_pieces, include_complement=True),
            set_colors,
            glyph_options,
            label_obstacles,
            opts["complement"],
        )

    if packed_result is not None:
        _draw_packed_members(ax, packed_result)

    if region_lines:
        _draw_region_labels(
            ax,
            placements,
            measured,
            cast("dict[str, Any]", placement_config.get("leader", {})),
        )
    if outside_names:
        _draw_exterior_set_labels(ax, outside_names, set_placements)

    for fx, fy, ftext, fstyle in fallback_names:
        ax.text(fx, fy, ftext, ha="center", va="center", **fstyle)

    # Legend: color-keyed swatches matching the region fills (same color and
    # alpha), one per set in shape order.
    if legend:
        swatch_alpha = opts["fills"].get("alpha", 0.5)
        handles = [
            Patch(
                facecolor=set_colors[name],
                edgecolor=set_colors[name],
                alpha=swatch_alpha,
                label=name,
            )
            for name in set_names
        ]
        legend_kwargs: dict[str, Any] = {**opts["legend"]}
        if isinstance(legend, dict):
            legend_kwargs.update(legend)
        ax.legend(handles=handles, **legend_kwargs)

    # Limits were established before label placement and then expanded in place
    # to admit any exterior labels; a fresh ``relim`` here would recompute the
    # data limits from the patches alone and clip those exterior labels, so we
    # only re-assert the aspect ratio and hide the axes.
    ax.set_aspect("equal")
    ax.axis("off")
    return ax


# Each round re-measures text against the (possibly expanded) axis limits and
# re-places; interior-only diagrams settle in one round, exterior labels in a
# few. Capped so a non-converging case can't loop forever.
_PLACE_MAX_ITERS = 4

_Line = tuple[str, dict[str, Any]]
_MeasuredLine = tuple[str, dict[str, Any], float, float]
_Box = tuple[float, float, float, float]


def _measure_renderer(fig: Any) -> Any:
    """A standalone Agg renderer at the figure's size and dpi for text metrics.

    Text extents only need *a* renderer; building a bare Agg one (instead of the
    active canvas's) keeps measurement working under any backend, including
    headless, without reattaching the figure's canvas.
    """
    from matplotlib.backends.backend_agg import RendererAgg

    w_in, h_in = fig.get_size_inches()
    dpi = fig.dpi
    return RendererAgg(int(w_in * dpi), int(h_in * dpi), dpi)  # type: ignore[no-untyped-call]


def _text_data_size(
    ax: Axes, renderer: Any, text: str, style: dict[str, Any]
) -> tuple[float, float]:
    """Measure ``text`` in data-coordinate units under the axes' transform."""
    artist = ax.text(0.0, 0.0, text, **{k: v for k, v in style.items() if k != "ha"})
    bbox = artist.get_window_extent(renderer=renderer)
    artist.remove()
    inv = ax.transData.inverted()
    x0, y0 = inv.transform((0.0, 0.0))
    x1, y1 = inv.transform((bbox.width, bbox.height))
    return abs(float(x1 - x0)), abs(float(y1 - y0))


def _place_region_labels(
    ax: Axes,
    region_lines: dict[str, list[_Line]],
    rings: dict[str, list[list[tuple[float, float]]]],
    container: tuple[float, float, float, float] | None,
    placement: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, list[_MeasuredLine]]]:
    """Measure each region's stacked text and place it with the core.

    Returns the raw placements (region key -> placement dict) and the measured
    lines (region key -> list of ``(text, style, width, height)``) used to draw
    and stack each block. Re-measures and re-places until the axis limits stop
    changing (exterior labels can enlarge the canvas, which changes the
    data-unit size of the text), bounded by :data:`_PLACE_MAX_ITERS`.
    """
    renderer = _measure_renderer(ax.figure)
    placements: dict[str, Any] = {}
    measured: dict[str, list[_MeasuredLine]] = {}

    for _ in range(_PLACE_MAX_ITERS):
        # ``set_aspect("equal")`` only rescales the transform at draw time (via
        # ``apply_aspect``), so measuring text against ``transData`` beforehand
        # uses unequal x/y scales and mismeasures width. Apply it now -- and
        # again each round, since the limits change as exterior labels expand
        # the canvas -- so measured sizes match what is finally rendered.
        ax.apply_aspect()
        sizes: dict[str, tuple[float, float]] = {}
        measured = {}
        for region, lines in region_lines.items():
            dims: list[_MeasuredLine] = []
            for text, style in lines:
                w, h = _text_data_size(ax, renderer, text, style)
                dims.append((text, style, w, h))
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
        placements = _place_labels(rings, sizes, container, **placement_kwargs)

        extra: list[tuple[float, float]] = []
        for region, pl in placements.items():
            if str(pl["kind"]).startswith("exterior"):
                dims = measured[region]
                width = max(d[2] for d in dims)
                height = sum(d[3] for d in dims)
                x, y = pl["anchor"]
                extra.extend(
                    [
                        (x - width / 2.0, y - height / 2.0),
                        (x + width / 2.0, y + height / 2.0),
                    ]
                )
                if pl["leader_end"] is not None:
                    extra.append(pl["leader_end"])
        if not extra:
            break
        before = (*ax.get_xlim(), *ax.get_ylim())
        ax.update_datalim(extra)
        ax.autoscale_view()
        if (*ax.get_xlim(), *ax.get_ylim()) == before:
            break

    return placements, measured


def _draw_region_labels(
    ax: Axes,
    placements: dict[str, Any],
    measured: dict[str, list[_MeasuredLine]],
    leader_style: dict[str, Any] | None = None,
) -> None:
    """Draw each placed block: leader line (if exterior) then stacked lines."""
    for region, dims in measured.items():
        placement = placements.get(region)
        if placement is None:
            # The core could not place this block (degenerate or empty region);
            # skip rather than dropping text on a boundary.
            continue
        ax_x, ax_y = placement["anchor"]

        if (
            str(placement["kind"]).startswith("exterior")
            and placement["tether"] is not None
            and placement["leader_end"] is not None
        ):
            waypoints = placement["leader_waypoints"]
            xs = [
                placement["tether"][0],
                *(p[0] for p in waypoints),
                placement["leader_end"][0],
            ]
            ys = [
                placement["tether"][1],
                *(p[1] for p in waypoints),
                placement["leader_end"][1],
            ]
            line_kwargs: dict[str, Any] = {
                "color": dims[0][1].get("color", "dimgray"),
                "linewidth": 0.8,
                "zorder": 2.5,
                **(leader_style or {}),
            }
            ax.plot(xs, ys, **line_kwargs)

        # Stack the lines centered on the anchor (which is the block's center),
        # top line first, each placed with ``va="top"`` at a descending cursor.
        total_h = sum(d[3] for d in dims)
        y_cursor = ax_y + total_h / 2.0
        for text, style, _, h in dims:
            draw_style = {k: v for k, v in style.items() if k != "ha"}
            ax.text(
                ax_x,
                y_cursor,
                text,
                ha=style.get("ha", "center"),
                va="top",
                **draw_style,
            )
            y_cursor -= h


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


def _place_exterior_set_labels(
    ax: Axes,
    names: dict[str, tuple[str, dict[str, Any]]],
    outlines: dict[str, list[tuple[float, float]]],
    container: tuple[float, float, float, float] | None,
    config: dict[str, Any],
    obstacles: list[_Box],
) -> tuple[dict[str, Any], dict[str, _MeasuredLine]]:
    renderer = _measure_renderer(ax.figure)
    placements: dict[str, Any] = {}
    measured: dict[str, _MeasuredLine] = {}
    for _ in range(_PLACE_MAX_ITERS):
        ax.apply_aspect()
        measured = {}
        sizes: dict[str, tuple[float, float]] = {}
        for name, (text, style) in names.items():
            width, height = _text_data_size(ax, renderer, text, style)
            measured[name] = (text, style, width, height)
            sizes[name] = (width, height)
        placements = _place_set_labels(
            outlines,
            sizes,
            container,
            margin=config.get("margin"),
            angular_steps=config.get("angular_steps"),
            precision=config.get("precision"),
            obstacles=obstacles,
        )
        extra = [
            point
            for x, y, width, height in _set_placement_boxes(placements, measured)
            for point in (
                (x - width / 2.0, y - height / 2.0),
                (x + width / 2.0, y + height / 2.0),
            )
        ]
        before = (*ax.get_xlim(), *ax.get_ylim())
        if extra:
            ax.update_datalim(extra)
            ax.autoscale_view()
        if not extra or (*ax.get_xlim(), *ax.get_ylim()) == before:
            break
    return placements, measured


def _draw_exterior_set_labels(
    ax: Axes,
    names: dict[str, tuple[str, dict[str, Any]]],
    placements: dict[str, Any],
) -> None:
    for name, placement in placements.items():
        spec = names.get(name)
        if spec is None:
            continue
        text, style = spec
        ax.text(
            placement["anchor"][0],
            placement["anchor"][1],
            text,
            ha=style.get("ha", "center"),
            va="center",
            **{k: v for k, v in style.items() if k not in ("ha", "va")},
        )


def _place_packed_members(
    ax: Axes,
    spec: tuple[dict[str, list[str]], dict[str, Any], dict[str, Any]],
    rings: dict[str, list[list[tuple[float, float]]]],
    obstacles: list[_Box],
) -> tuple[dict[str, list[str]], dict[str, Any], dict[str, Any]]:
    content, packing, style = spec
    renderer = _measure_renderer(ax.figure)
    ax.apply_aspect()
    sizes: dict[str, list[tuple[float, float]]] = {}
    for region, names in content.items():
        if region not in rings:
            continue
        sizes[region] = [_text_data_size(ax, renderer, name, style) for name in names]
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


def _font_size_points(style: dict[str, Any]) -> float:
    return float(FontProperties(size=style.get("fontsize", 9)).get_size_in_points())


def _draw_packed_members(
    ax: Axes,
    result: tuple[dict[str, list[str]], dict[str, Any], dict[str, Any]],
) -> None:
    content, placed, style = result
    font_size = _font_size_points(style) * float(placed["scale"])
    draw_style = {k: v for k, v in style.items() if k not in ("fontsize", "ha", "va")}
    for region, boxes in placed["boxes"].items():
        for name, (x, y, _, _) in zip(content.get(region, []), boxes, strict=False):
            ax.text(
                x,
                y,
                name,
                fontsize=font_size,
                ha=style.get("ha", "center"),
                va="center",
                zorder=2.8,
                **draw_style,
            )


def _draw_glyphs(
    ax: Axes,
    fit: EulerFit[Any],
    rings: dict[str, list[list[tuple[float, float]]]],
    set_colors: dict[str, Any],
    resolved: tuple[dict[str, Any], dict[str, Any]],
    obstacles: list[_Box],
    complement_style: dict[str, Any],
) -> None:
    placement, style = resolved
    counts = _requested_glyph_counts(fit)
    placed = _place_glyphs(
        rings,
        counts,
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
    tint = float(style.pop("tint", 0.45))
    edge_tint = float(style.pop("edge_tint", -0.35))
    for region, points in placed["positions"].items():
        base = (
            complement_style.get("facecolor", "#f0f0f0")
            if region == ""
            else _blend_region_color(region, set_colors)
        )
        circle_style: dict[str, Any] = {
            "facecolor": _shift_color(base, tint),
            "edgecolor": _shift_color(base, edge_tint),
            "zorder": 2.0,
            **style,
        }
        for x, y in points:
            ax.add_patch(MplCircle((x, y), placed["radius"], **circle_style))


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
