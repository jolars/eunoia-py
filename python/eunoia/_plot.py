"""Matplotlib renderer for ``EulerFit``."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, cast

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, PathPatch
from matplotlib.patches import Rectangle as MplRectangle
from matplotlib.path import Path

from eunoia._models import VennFit
from eunoia._options import get_options

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
    labels: bool | dict[str, Any] | None = None,
    quantities: bool | str | dict[str, Any] | None = None,
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
    label_specs: dict[str, tuple[str, dict[str, Any]] | None]
    if isinstance(labels, dict):
        show_labels = True
        label_specs = _resolve_set_labels(set_names, labels)
    else:
        show_labels = (not bool(legend)) if labels is None else bool(labels)
        label_specs = {name: (name, {}) for name in set_names}

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

    # Resolve the quantity values up front so labels know whether a quantity
    # shares their anchor (and must make room for it).
    quant = _resolve_quantities(fit, quantities)
    values: dict[str, float] = quant[0] if quant is not None else {}

    # A set label and a region quantity can land on the same anchor: the core
    # derives each set anchor from a region (the set's own exclusive region, or
    # -- for a set nested inside another with no exclusive area -- the largest
    # containing region) and reports that source in ``set_anchor_regions``
    # (set name -> canonical region key). When a set's label and the quantity
    # for its anchor region are both shown, we stack the pair (name above,
    # value below) instead of letting them overlap. We rely on this mapping
    # rather than matching anchor points by float equality, since the optimizer
    # is only reproducible to floating-point precision and the two copies of
    # the point differ by ~1e-8.
    #
    # collided[name] is True when set ``name`` shares its anchor with a shown
    # quantity; collided_regions holds the corresponding region keys.
    collided = {
        name: (
            show_labels
            and label_specs.get(name) is not None
            and (region := set_anchor_regions.get(name)) is not None
            and region in values
        )
        for name in set_anchors
    }
    collided_regions = {
        set_anchor_regions[name] for name, hit in collided.items() if hit
    }

    # Set labels
    if show_labels:
        for name, (x, y) in set_anchors.items():
            spec = label_specs.get(name)
            if spec is None:
                continue
            text, style = spec
            va = "bottom" if collided.get(name) else "center"
            text_kwargs: dict[str, Any] = {
                "ha": "center",
                "va": va,
                **opts["labels"],
            }
            text_kwargs.update(style)
            ax.text(x, y, text, **text_kwargs)

    # Region quantities
    if quant is not None:
        _, fmt, q_style = quant
        for combo, (x, y) in region_anchors.items():
            if combo not in values:
                continue
            va = "top" if combo in collided_regions else "center"
            quantity_kwargs: dict[str, Any] = {
                "ha": "center",
                "va": va,
                **opts["quantities"],
            }
            quantity_kwargs.update(q_style)
            ax.text(x, y, fmt(values[combo]), **quantity_kwargs)

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
    palette: Any,
) -> dict[str, RGBA]:
    if colors is None:
        # ``palette`` (eunoia.options) is either a colormap name or a sequence
        # of colors to cycle through, in shape order.
        if isinstance(palette, str):
            cmap = plt.get_cmap(palette)
            return {name: cmap(i % cmap.N) for i, name in enumerate(set_names)}
        seq = list(palette)
        if not seq:
            raise ValueError("palette sequence is empty")
        return {
            name: mcolors.to_rgba(seq[i % len(seq)]) for i, name in enumerate(set_names)
        }
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


def _resolve_set_labels(
    set_names: list[str],
    labels: dict[str, Any],
) -> dict[str, tuple[str, dict[str, Any]] | None]:
    """Normalize a ``labels`` dict to per-set label text and ``ax.text`` kwargs.

    ``labels`` (when a dict) may be one of two shapes:

    * a **per-set** mapping whose keys are all set names. Each value is either

      - a string — replacement label text for that set (default style);
      - a dict — ``ax.text`` keyword arguments for that set; an optional
        ``"text"`` key overrides the label text (e.g. mathtext such as
        ``r"$\\alpha$"``);
      - ``None`` or ``False`` — hide that set's label.

      Sets absent from the mapping keep their name and default style.

    * a **uniform** style dict, when *none* of its keys is a set name. It is
      read as a single set of ``ax.text`` kwargs applied to every label (so
      ``{"fontsize": 14, "color": "crimson"}`` styles all labels at once).

    Mixing the two (some keys set names, some not) is an error, since it almost
    always means a mistyped set name.
    """
    resolved: dict[str, tuple[str, dict[str, Any]] | None] = {
        name: (name, {}) for name in set_names
    }
    known = [k for k in labels if k in set_names]
    if known and len(known) != len(labels):
        unknown = [k for k in labels if k not in set_names]
        raise ValueError(
            f"labels mixes set names {known} with non-set keys {unknown}; "
            f"pass either a per-set dict (keys = set names) or a uniform "
            f"style dict (no key a set name). Known sets: {set_names}"
        )
    if not known:
        # Uniform style applied to every label (empty dict → defaults only).
        uniform = dict(labels)
        return {name: (name, dict(uniform)) for name in set_names}
    for name, spec in labels.items():
        if spec is None or spec is False:
            resolved[name] = None
        elif isinstance(spec, str):
            resolved[name] = (spec, {})
        elif isinstance(spec, dict):
            kwargs = dict(spec)
            text = kwargs.pop("text", name)
            resolved[name] = (str(text), kwargs)
        else:
            raise TypeError(
                f"labels[{name!r}] must be a str, dict, None, or False, "
                f"got {type(spec).__name__}"
            )
    return resolved


_QUANTITY_TYPES = ("counts", "percent")


def _resolve_quantities(
    fit: EulerFit[Any],
    quantities: bool | str | dict[str, Any],
) -> tuple[dict[str, float], Callable[[float], str], dict[str, Any]] | None:
    """Resolve the ``quantities`` kwarg to (values, formatter, text kwargs).

    Returns ``None`` when quantities are off. Otherwise returns the value
    source mapping (canonical region key → value), a formatter turning one
    value into its label string, and any extra ``ax.text`` style kwargs.

    ``quantities`` may be:

    * ``False`` (default) — off; ``True`` — on with the input (original)
      values shown as raw counts.
    * a string — one of ``"original"`` / ``"fitted"`` (value *source*, shown as
      counts) or ``"counts"`` / ``"percent"`` (display *type*, original
      source). ``"percent"`` shows each region's share of the total.
    * a dict — ``{"source": ..., "type": ..., **text_kwargs}``. ``source`` is
      ``"original"`` (default) or ``"fitted"``; ``type`` is ``"counts"``,
      ``"percent"``, or a sequence of both (counts on top, percent in
      parentheses below). Any remaining keys are forwarded to ``ax.text`` as
      style overrides (e.g. ``color``, ``fontsize``, ``fontstyle``).
    """
    if quantities is False:
        return None

    source = "original"
    types: list[str] = ["counts"]
    text_kwargs: dict[str, Any] = {}

    if quantities is True:
        pass
    elif isinstance(quantities, str):
        if quantities in ("original", "fitted"):
            source = quantities
        elif quantities in _QUANTITY_TYPES:
            types = [quantities]
        else:
            raise ValueError(
                f"quantities string must be one of 'original', 'fitted', "
                f"'counts', 'percent'; got {quantities!r}"
            )
    else:
        # A mapping: {"source": ..., "type": ..., **ax.text style kwargs}. An
        # empty dict is "on with defaults" (counts of the original values).
        cfg = dict(quantities)
        source = cfg.pop("source", "original")
        if source not in ("original", "fitted"):
            raise ValueError(
                f"quantities 'source' must be 'original' or 'fitted'; got {source!r}"
            )
        raw_type = cfg.pop("type", "counts")
        types = [raw_type] if isinstance(raw_type, str) else list(raw_type)
        if not types:
            raise ValueError("quantities 'type' must name at least one type")
        unknown = [t for t in types if t not in _QUANTITY_TYPES]
        if unknown:
            raise ValueError(
                f"quantities 'type' entries must be 'counts' or 'percent'; "
                f"got {unknown}"
            )
        text_kwargs = cfg

    values = fit.original_values if source == "original" else fit.fitted_values
    total = sum(values.values())
    show_counts = "counts" in types
    show_percent = "percent" in types

    def fmt(v: float) -> str:
        parts: list[str] = []
        if show_counts:
            parts.append(f"{v:.3g}")
        if show_percent:
            pct = (v / total * 100.0) if total else 0.0
            s = f"{pct:.3g}%"
            parts.append(f"({s})" if show_counts else s)
        return "\n".join(parts)

    return values, fmt, text_kwargs


def _blend_region_color(
    combo: str,
    set_colors: dict[str, RGBA],
) -> RGBA:
    parts = [s.strip() for s in combo.split("&") if s.strip()]
    cs = [set_colors[p] for p in parts if p in set_colors]
    if not cs:
        return (0.5, 0.5, 0.5, 1.0)
    n = len(cs)
    # Blend in OKLab: perceptually uniform, so the mean of the L/a/b
    # coordinates stays vivid instead of darkening, which a plain mean of
    # gamma-encoded sRGB does on mid-saturation pairs. Alpha is unaffected by
    # color space, so it is averaged directly.
    labs = [_srgb_to_oklab(c[:3]) for c in cs]
    mean_lab = (
        sum(lab[0] for lab in labs) / n,
        sum(lab[1] for lab in labs) / n,
        sum(lab[2] for lab in labs) / n,
    )
    r, g, b = _oklab_to_srgb(mean_lab)
    return (r, g, b, sum(c[3] for c in cs) / n)


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    s = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return min(1.0, max(0.0, s))


def _srgb_to_oklab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    """Convert a gamma-encoded sRGB triple to OKLab (Björn Ottosson, 2020)."""
    lr = _srgb_to_linear(rgb[0])
    lg = _srgb_to_linear(rgb[1])
    lb = _srgb_to_linear(rgb[2])

    lc = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb
    mc = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb
    sc = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb

    l_ = lc ** (1 / 3)
    m_ = mc ** (1 / 3)
    s_ = sc ** (1 / 3)

    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _oklab_to_srgb(lab: tuple[float, float, float]) -> tuple[float, float, float]:
    """Inverse of :func:`_srgb_to_oklab`; result is clamped to [0, 1]."""
    big_l, a, b = lab
    l_ = big_l + 0.3963377774 * a + 0.2158037573 * b
    m_ = big_l - 0.1055613458 * a - 0.0638541728 * b
    s_ = big_l - 0.0894841775 * a - 1.2914855480 * b

    lc = l_ * l_ * l_
    mc = m_ * m_ * m_
    sc = s_ * s_ * s_

    lr = 4.0767416621 * lc - 3.3077115913 * mc + 0.2309699292 * sc
    lg = -1.2684380046 * lc + 2.6097574011 * mc - 0.3413193965 * sc
    lb = -0.0041960863 * lc - 0.7034186147 * mc + 1.7076147010 * sc

    return (_linear_to_srgb(lr), _linear_to_srgb(lg), _linear_to_srgb(lb))
