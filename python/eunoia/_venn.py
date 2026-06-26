"""Public ``venn()`` function for non-proportional Venn diagrams."""

from __future__ import annotations

import string
from collections.abc import Collection, Mapping, Sequence
from typing import Any, Literal, cast, overload

from narwhals.typing import IntoFrame

from eunoia._dataframe import (
    dataframe_column_names,
    dataframe_to_combinations,
    is_dataframe,
)
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
from eunoia._parse import (
    canonicalize,
    is_membership_input,
    parse_membership_input,
    to_inclusive,
)

VennInput = (
    int
    | Sequence[str]
    | Mapping[str, float]
    | Mapping[str, Collection[str]]
    | IntoFrame
)


@overload
def venn(
    sets: VennInput,
    *,
    shape: Literal["ellipse"] = ...,
    complement: float | None = ...,
    input: Literal["exclusive", "inclusive"] = ...,
) -> VennFit[Ellipse]: ...


@overload
def venn(
    sets: VennInput,
    *,
    shape: Literal["circle"],
    complement: float | None = ...,
    input: Literal["exclusive", "inclusive"] = ...,
) -> VennFit[Circle]: ...


@overload
def venn(
    sets: VennInput,
    *,
    shape: Literal["square"],
    complement: float | None = ...,
    input: Literal["exclusive", "inclusive"] = ...,
) -> VennFit[Square]: ...


@overload
def venn(
    sets: VennInput,
    *,
    shape: Literal["rectangle"],
    complement: float | None = ...,
    input: Literal["exclusive", "inclusive"] = ...,
) -> VennFit[Rectangle]: ...


def venn(
    sets: VennInput,
    *,
    shape: Literal["circle", "ellipse", "square", "rectangle"] = "ellipse",
    complement: float | None = None,
    input: Literal["exclusive", "inclusive"] = "exclusive",
) -> VennFit[Circle] | VennFit[Ellipse] | VennFit[Square] | VennFit[Rectangle]:
    """Lay out a (non-proportional) Venn diagram.

    Unlike :func:`euler`, every set intersection is always drawn, regardless
    of area. The arrangement is *topological*: the shapes come from the
    eunoia core's canonical Venn layouts, not from numerical optimization.

    Parameters
    ----------
    sets:
        The sets to show. One of:

        * an ``int`` *n*: *n* sets with default names ``"A"``, ``"B"``, …;
        * a sequence of set names, e.g. ``["cat", "dog", "fish"]``;
        * a mapping from set-combination labels (e.g. ``"A"``, ``"A&B"``) to
          per-region quantities, where the layout stays topological but the
          values are kept as :attr:`~EulerFit.original_values` so ``plot()`` can label
          each region (this is the common "Venn diagram with subset sizes"
          case);
        * a mapping from set names to membership collections
          (``{"A": ["x", "y"], "B": ["y", "z"]}``), counted into per-region
          quantities;
        * a DataFrame (pandas, polars, … via narwhals) treated as a membership
          matrix; its column names are the sets and each row is counted into
          a region.

        For ``int`` and plain name-sequence input there are no quantities, so
        ``original_values`` is empty.
    shape:
        ``"ellipse"`` (default), ``"circle"``, ``"square"``, or
        ``"rectangle"``. Ellipses support 1--5 sets; circles, squares, and
        rectangles 1--3. An unsupported set count raises :class:`EunoiaError`.
    complement:
        Optional universe area outside every set. For a Venn diagram this only
        adds a visual container box (the padded bounding box); it does not
        drive optimization.
    input:
        How to read the supplied quantities. ``"exclusive"`` (default): each
        value is a per-region count with no overlap included. ``"inclusive"``:
        values are total set sizes that include overlaps. Only meaningful for
        the region-area mapping form; membership-list and DataFrame input are
        always exclusive (passing ``"inclusive"`` raises :class:`EunoiaError`).

    Returns
    -------
    VennFit
        A topological fit whose ``plot()`` works like :class:`EulerFit`. When
        quantities were supplied they are kept in ``original_values`` and shown
        by ``plot()`` automatically; otherwise ``fitted_values`` holds the
        geometric area of every region.
    """
    if shape not in ("circle", "ellipse", "square", "rectangle"):
        raise EunoiaError(
            "invalid_shape: shape must be 'circle', 'ellipse', 'square' or "
            f"'rectangle', got {shape!r}"
        )
    if input not in ("exclusive", "inclusive"):
        raise EunoiaError(
            f"invalid_input: input must be 'exclusive' or 'inclusive', got {input!r}"
        )

    names, original_values, canonical_keys = _resolve_input(sets, input)
    result: Any = _venn_rust(len(names), shape, names, complement)

    if shape == "circle":
        shapes: Any = build_circles(result["shapes"])
    elif shape == "ellipse":
        shapes = build_ellipses(result["shapes"])
    elif shape == "square":
        shapes = build_squares(result["shapes"])
    else:
        shapes = build_rectangles(result["shapes"])

    return _make_venn(result, shapes, original_values, canonical_keys, input)


def _make_venn(
    result: Mapping[str, Any],
    shapes: tuple[S, ...],
    original_values: dict[str, float],
    canonical_keys: list[str],
    input: str,
) -> VennFit[S]:
    """Assemble a ``VennFit`` from a raw ``_venn`` result and built shapes.

    When quantities were supplied, ``fitted_values`` mirrors :func:`euler` —
    the geometric area of each requested region, expressed in the input scale.
    With no quantities it falls back to the geometric area of *every* region.
    """
    fitted_exclusive = result["fitted_exclusive"]
    if original_values:
        if input == "exclusive":
            fitted_values = {
                ck: float(fitted_exclusive.get(ck, 0.0)) for ck in canonical_keys
            }
        else:
            fitted_values = to_inclusive(fitted_exclusive, canonical_keys)
    else:
        fitted_values = {k: float(v) for k, v in fitted_exclusive.items()}
    return VennFit(
        shapes=shapes,
        original_values=original_values,
        fitted_values=fitted_values,
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


def _resolve_input(
    sets: VennInput, input: str
) -> tuple[list[str], dict[str, float], list[str]]:
    """Resolve ``sets`` into set names, ``original_values`` and canonical keys.

    Mirrors :func:`euler`'s input handling for the value-carrying forms
    (region-area mapping, membership lists, DataFrame). ``int`` and plain
    name-sequence input carry no quantities, so ``original_values`` is empty
    and the canonical-key list is too.
    """
    if is_dataframe(sets):
        if input != "exclusive":
            raise EunoiaError(
                "invalid_input: DataFrame input is always exclusive; "
                "do not pass input='inclusive'"
            )
        names = dataframe_column_names(sets)
        original_values = {c: v for c, v in dataframe_to_combinations(sets)}
        return names, original_values, list(original_values)

    # bool is an int subclass; reject it explicitly to avoid venn(True).
    if isinstance(sets, bool):
        raise TypeError("venn: 'sets' must be an int, a list of names, or a mapping")
    if isinstance(sets, int):
        if sets < 1:
            raise ValueError("venn: number of sets must be >= 1")
        return [_default_name(i) for i in range(sets)], {}, []
    if isinstance(sets, Mapping):
        try:
            membership = is_membership_input(sets)
        except ValueError as exc:
            raise EunoiaError(str(exc)) from exc
        if membership:
            if input != "exclusive":
                raise EunoiaError(
                    "invalid_input: membership-list input is always exclusive; "
                    "do not pass input='inclusive'"
                )
            members = cast("Mapping[str, Collection[object]]", sets)
            # Membership keys are the set names (preserve their order); a set
            # with no exclusive members still gets a shape.
            names = list(members)
            original_values = {c: v for c, v in parse_membership_input(members)}
            return names, original_values, list(original_values)
        area_map = cast("Mapping[str, float]", sets)
        names = []
        for key in area_map:
            for part in canonicalize(key).split("&"):
                if part and part not in names:
                    names.append(part)
        if not names:
            raise ValueError("venn: no sets found in mapping")
        canonical_keys = [canonicalize(k) for k in area_map]
        original_values = {
            ck: float(v)
            for ck, v in zip(canonical_keys, area_map.values(), strict=True)
        }
        return names, original_values, canonical_keys
    if isinstance(sets, str):
        raise TypeError("venn: pass a list of set names, not a single string")
    names = [str(s) for s in cast("Sequence[str]", sets)]
    if not names:
        raise ValueError("venn: need at least one set name")
    if len(set(names)) != len(names):
        raise ValueError("venn: set names must be unique")
    return names, {}, []
