"""Public ``venn()`` function for non-proportional Venn diagrams."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import Any, Literal, cast, overload

import numpy.typing as npt
from narwhals.typing import IntoFrame

from eunoia._dataframe import (
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
    build_rotated_rectangles,
    build_squares,
)
from eunoia._models import (
    Circle,
    Ellipse,
    Rectangle,
    RotatedRectangle,
    S,
    Square,
    VennFit,
)
from eunoia._numpy import (
    default_name,
    is_ndarray,
    ndarray_to_members,
    ndarray_to_named_combinations,
)
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
    | npt.NDArray[Any]
)


@overload
def venn(
    sets: VennInput,
    *,
    shape: Literal["ellipse"] = ...,
    complement: float | None = ...,
    input: Literal["exclusive", "inclusive"] = ...,
    names: Sequence[str] | None = ...,
    ids: str | Sequence[object] | None = ...,
) -> VennFit[Ellipse]: ...


@overload
def venn(
    sets: VennInput,
    *,
    shape: Literal["circle"],
    complement: float | None = ...,
    input: Literal["exclusive", "inclusive"] = ...,
    names: Sequence[str] | None = ...,
    ids: str | Sequence[object] | None = ...,
) -> VennFit[Circle]: ...


@overload
def venn(
    sets: VennInput,
    *,
    shape: Literal["square"],
    complement: float | None = ...,
    input: Literal["exclusive", "inclusive"] = ...,
    names: Sequence[str] | None = ...,
    ids: str | Sequence[object] | None = ...,
) -> VennFit[Square]: ...


@overload
def venn(
    sets: VennInput,
    *,
    shape: Literal["rectangle"],
    complement: float | None = ...,
    input: Literal["exclusive", "inclusive"] = ...,
    names: Sequence[str] | None = ...,
    ids: str | Sequence[object] | None = ...,
) -> VennFit[Rectangle]: ...


@overload
def venn(
    sets: VennInput,
    *,
    shape: Literal["rotated_rectangle"],
    complement: float | None = ...,
    input: Literal["exclusive", "inclusive"] = ...,
    names: Sequence[str] | None = ...,
    ids: str | Sequence[object] | None = ...,
) -> VennFit[RotatedRectangle]: ...


def venn(
    sets: VennInput,
    *,
    shape: Literal[
        "circle", "ellipse", "square", "rectangle", "rotated_rectangle"
    ] = "ellipse",
    complement: float | None = None,
    input: Literal["exclusive", "inclusive"] = "exclusive",
    names: Sequence[str] | None = None,
    ids: str | Sequence[object] | None = None,
) -> (
    VennFit[Circle]
    | VennFit[Ellipse]
    | VennFit[Square]
    | VennFit[Rectangle]
    | VennFit[RotatedRectangle]
):
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
          a region;
        * a numpy boolean array used as a membership matrix (2-D, or 1-D for a
          single set); set names come from ``names`` or are generated.

        For ``int`` and plain name-sequence input there are no quantities, so
        ``original_values`` is empty.
    shape:
        ``"ellipse"`` (default), ``"circle"``, ``"square"``, ``"rectangle"``,
        or ``"rotated_rectangle"``. Ellipses support 1--5 sets; circles,
        squares, and rectangles 1--3; rotated rectangles 1--4 (the 4-set
        layout uses rotated rectangles to open all 15 regions). An unsupported
        set count raises :class:`EunoiaError`.
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
    names:
        Set names for numpy-array input, one per column (or a single name for a
        1-D array). Defaults to ``"A"``, ``"B"``, …. Only valid for array input;
        other forms carry their own names and passing ``names`` raises.
    ids:
        Per-observation member identifiers, retained as
        :attr:`~EulerFit.members` and drawable with ``plot(members=True)``. Only
        valid for array and DataFrame input: a sequence with one entry per row,
        or, for a DataFrame, a column name to read identifiers from and exclude
        from the sets. Membership-list input carries its members intrinsically;
        passing ``ids`` with any other form raises.

    Returns
    -------
    VennFit
        A topological fit whose ``plot()`` works like :class:`EulerFit`. When
        quantities were supplied they are kept in ``original_values`` and shown
        by ``plot()`` automatically; otherwise ``fitted_values`` holds the
        geometric area of every region.
    """
    if shape not in (
        "circle",
        "ellipse",
        "square",
        "rectangle",
        "rotated_rectangle",
    ):
        raise EunoiaError(
            "invalid_shape: shape must be 'circle', 'ellipse', 'square', "
            f"'rectangle' or 'rotated_rectangle', got {shape!r}"
        )
    if input not in ("exclusive", "inclusive"):
        raise EunoiaError(
            f"invalid_input: input must be 'exclusive' or 'inclusive', got {input!r}"
        )

    names, original_values, canonical_keys, members_map = _resolve_input(
        sets, input, names, ids
    )
    combinations = list(original_values.items()) if original_values else None
    result: Any = _venn_rust(len(names), shape, names, complement, combinations, input)

    if shape == "circle":
        shapes: Any = build_circles(result["shapes"])
    elif shape == "ellipse":
        shapes = build_ellipses(result["shapes"])
    elif shape == "square":
        shapes = build_squares(result["shapes"])
    elif shape == "rectangle":
        shapes = build_rectangles(result["shapes"])
    else:
        shapes = build_rotated_rectangles(result["shapes"])

    return _make_venn(
        result, shapes, original_values, canonical_keys, input, members_map
    )


def _make_venn(
    result: Mapping[str, Any],
    shapes: tuple[S, ...],
    original_values: dict[str, float],
    canonical_keys: list[str],
    input: str,
    members: dict[str, list[str]] | None = None,
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
        members=members,
        plot_data=build_plot_data(result),
    )


def _resolve_input(
    sets: VennInput,
    input: str,
    names: Sequence[str] | None,
    ids: str | Sequence[object] | None,
) -> tuple[list[str], dict[str, float], list[str], dict[str, list[str]] | None]:
    """Resolve ``sets`` into set names, ``original_values``, canonical keys, and
    an optional ``members`` map.

    Mirrors :func:`euler`'s input handling for the value-carrying forms
    (region-area mapping, membership lists, DataFrame, numpy array). ``int`` and
    plain name-sequence input carry no quantities, so ``original_values`` is
    empty and the canonical-key list is too. ``names`` is only honored for array
    input; supplying it with any other form raises. ``ids`` supplies member
    identifiers for array/DataFrame input; passing it with any other form raises.
    """
    if is_ndarray(sets):
        if input != "exclusive":
            raise EunoiaError(
                "invalid_input: array input is always exclusive; "
                "do not pass input='inclusive'"
            )
        set_names, combinations = ndarray_to_named_combinations(sets, names)
        original_values = {c: v for c, v in combinations}
        members_map: dict[str, list[str]] | None = None
        if ids is not None:
            if isinstance(ids, str):
                raise EunoiaError(
                    "invalid_input: ids as a column name is only valid for "
                    "DataFrame input; pass a per-row sequence for array input"
                )
            members_map = ndarray_to_members(sets, names, ids)
        return set_names, original_values, list(original_values), members_map

    if names is not None:
        raise EunoiaError("invalid_input: names= is only valid for numpy array input")

    if is_dataframe(sets):
        if input != "exclusive":
            raise EunoiaError(
                "invalid_input: DataFrame input is always exclusive; "
                "do not pass input='inclusive'"
            )
        set_names, combinations, members_map = dataframe_to_combinations(sets, ids)
        original_values = {c: v for c, v in combinations}
        return set_names, original_values, list(original_values), members_map

    if ids is not None:
        raise EunoiaError(
            "invalid_input: ids= is only valid for array or DataFrame input"
        )

    # bool is an int subclass; reject it explicitly to avoid venn(True).
    if isinstance(sets, bool):
        raise TypeError("venn: 'sets' must be an int, a list of names, or a mapping")
    if isinstance(sets, int):
        if sets < 1:
            raise ValueError("venn: number of sets must be >= 1")
        return [default_name(i) for i in range(sets)], {}, [], None
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
            combinations, members_map = parse_membership_input(members)
            original_values = {c: v for c, v in combinations}
            return names, original_values, list(original_values), members_map
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
        return names, original_values, canonical_keys, None
    if isinstance(sets, str):
        raise TypeError("venn: pass a list of set names, not a single string")
    names = [str(s) for s in cast("Sequence[str]", sets)]
    if not names:
        raise ValueError("venn: need at least one set name")
    if len(set(names)) != len(names):
        raise ValueError("venn: set names must be unique")
    return names, {}, [], None
