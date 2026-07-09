"""Backend-neutral rendering helpers shared by the matplotlib and plotly emitters.

These resolve the user-facing ``plot`` keyword arguments (colors, edges, labels,
quantities, members) and blend region colors into plain data -- no drawing and
no dependence on a live figure. Both ``eunoia._plot`` (matplotlib) and
``eunoia._plotly`` build on them, so their names are public (no leading
underscore) to avoid pyright's ``reportPrivateUsage`` on cross-module use, the
same reason ``EulerFit.plot_data`` is public.

Color resolution uses matplotlib's color and colormap utilities; matplotlib is a
required dependency, so this is available regardless of backend.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt

if TYPE_CHECKING:
    from eunoia._models import EulerFit

RGBA = tuple[float, float, float, float]

_QUANTITY_TYPES = ("counts", "percent")


def region_rings(
    region_pieces: dict[str, list[dict[str, Any]]],
) -> dict[str, list[list[tuple[float, float]]]]:
    """Flatten each region's pieces to a list of boundary rings.

    The core classifies rings back into outer/hole pieces by containment, so we
    can hand it every piece's outer ring plus its hole rings as one flat list
    per region, ignoring the outer/hole distinction and winding order.
    """
    rings: dict[str, list[list[tuple[float, float]]]] = {}
    for combo, pieces in region_pieces.items():
        if combo == "":
            continue
        region: list[list[tuple[float, float]]] = []
        for piece in pieces:
            region.append(piece["outer"])
            region.extend(piece["holes"])
        if region:
            rings[combo] = region
    return rings


def resolve_set_colors(
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


def resolve_set_edges(
    set_names: list[str],
    edges: dict[str, Any] | Sequence[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Normalize ``edges`` to a per-set mapping of style kwargs.

    ``edges`` may be:

    * ``None``: no overrides (every set gets ``{}``).
    * a flat dict of style kwargs: applied uniformly to every set.
    * a per-set dict keyed by set name, whose values are kwargs dicts: each
      set styled independently; sets absent from the dict get ``{}``.
    * a sequence of kwargs dicts: one per set, in shape order.

    A dict is read as per-set when *all* its values are themselves dicts;
    otherwise it is a single uniform style (no style kwarg takes a dict, so the
    two cases never collide).
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


def resolve_set_labels(
    set_names: list[str],
    labels: dict[str, Any],
) -> dict[str, tuple[str, dict[str, Any]] | None]:
    """Normalize a ``labels`` dict to per-set label text and text kwargs.

    ``labels`` (when a dict) may be one of two shapes:

    * a **per-set** mapping whose keys are all set names. Each value is either

      - a string: replacement label text for that set (default style);
      - a dict: text keyword arguments for that set; an optional ``"text"``
        key overrides the label text (e.g. mathtext such as ``r"$\\alpha$"``);
      - ``None`` or ``False``: hide that set's label.

      Sets absent from the mapping keep their name and default style.

    * a **uniform** style dict, when *none* of its keys is a set name. It is
      read as a single set of text kwargs applied to every label (so
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


def resolve_members(
    fit: EulerFit[Any],
    members: bool | dict[str, Any] | None,
) -> tuple[dict[str, str], dict[str, Any]] | None:
    """Resolve the ``members`` kwarg to per-region member text and text kwargs.

    Returns ``None`` when members are off. Otherwise returns
    ``({region: text}, text_kwargs)`` where each ``text`` newline-joins that
    region's (already sorted) member names, capped by an optional ``max``.

    ``members`` may be:

    * ``None`` or ``False`` (default): off.
    * ``True`` (or an empty dict): on, listing every member name.
    * a dict: ``{"max": int, **text_kwargs}``. ``max`` caps how many names are
      listed per region, replacing the remainder with a ``"+N more"`` line; any
      other keys are forwarded to the text call (e.g. ``color``, ``fontsize``).
    """
    if members is None or members is False:
        return None
    if fit.members is None:
        raise ValueError(
            "members display requested but this fit carries no member "
            "identities; member names are available for membership-list input, "
            "or array/DataFrame input with ids="
        )
    max_n: int | None = None
    text_kwargs: dict[str, Any] = {}
    if isinstance(members, dict):
        cfg = dict(members)
        raw_max = cfg.pop("max", None)
        if raw_max is not None:
            if isinstance(raw_max, bool) or not isinstance(raw_max, int) or raw_max < 1:
                raise ValueError("members 'max' must be a positive integer")
            max_n = raw_max
        text_kwargs = cfg

    out: dict[str, str] = {}
    for region, names in fit.members.items():
        if not names:
            continue
        if max_n is not None and len(names) > max_n:
            lines = [*names[:max_n], f"+{len(names) - max_n} more"]
        else:
            lines = list(names)
        out[region] = "\n".join(lines)
    return out, text_kwargs


def resolve_quantities(
    fit: EulerFit[Any],
    quantities: bool | str | dict[str, Any],
) -> tuple[dict[str, float], Callable[[float], str], dict[str, Any]] | None:
    """Resolve the ``quantities`` kwarg to (values, formatter, text kwargs).

    Returns ``None`` when quantities are off. Otherwise returns the value
    source mapping (canonical region key → value), a formatter turning one
    value into its label string, and any extra text style kwargs.

    ``quantities`` may be:

    * ``False`` (default) is off; ``True`` is on with the input (original)
      values shown as raw counts.
    * a string: one of ``"original"`` or ``"fitted"`` (value *source*, shown as
      counts), or ``"counts"`` or ``"percent"`` (display *type*, original
      source). ``"percent"`` shows each region's share of the total.
    * a dict: ``{"source": ..., "type": ..., **text_kwargs}``. ``source`` is
      ``"original"`` (default) or ``"fitted"``; ``type`` is ``"counts"``,
      ``"percent"``, or a sequence of both (counts on top, percent in
      parentheses below). Any remaining keys are forwarded as style overrides
      (e.g. ``color``, ``fontsize``, ``fontstyle``).
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
        # A mapping: {"source": ..., "type": ..., **text style kwargs}. An
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


def blend_region_color(
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
