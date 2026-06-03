"""Public ``euler()`` function — dispatches to the Rust binding."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal, overload

from eunoia._eunoia import (
    EunoiaError,
    _fit_circles,
    _fit_ellipses,
    _fit_rectangles,
    _fit_squares,
)
from eunoia._models import (
    Circle,
    Container,
    Ellipse,
    EulerFit,
    Point,
    Rectangle,
    S,
    Square,
)
from eunoia._parse import canonicalize, parse_dict_input, to_inclusive


@overload
def euler(
    values: Mapping[str, float],
    *,
    input: Literal["exclusive", "inclusive"] = ...,
    shape: Literal["circle"] = ...,
    seed: int | None = ...,
    complement: float | None = ...,
) -> EulerFit[Circle]: ...


@overload
def euler(
    values: Mapping[str, float],
    *,
    input: Literal["exclusive", "inclusive"] = ...,
    shape: Literal["ellipse"],
    seed: int | None = ...,
    complement: float | None = ...,
) -> EulerFit[Ellipse]: ...


@overload
def euler(
    values: Mapping[str, float],
    *,
    input: Literal["exclusive", "inclusive"] = ...,
    shape: Literal["square"],
    seed: int | None = ...,
    complement: float | None = ...,
) -> EulerFit[Square]: ...


@overload
def euler(
    values: Mapping[str, float],
    *,
    input: Literal["exclusive", "inclusive"] = ...,
    shape: Literal["rectangle"],
    seed: int | None = ...,
    complement: float | None = ...,
) -> EulerFit[Rectangle]: ...


def euler(
    values: Mapping[str, float],
    *,
    input: Literal["exclusive", "inclusive"] = "exclusive",
    shape: Literal["circle", "ellipse", "square", "rectangle"] = "circle",
    seed: int | None = None,
    complement: float | None = None,
) -> EulerFit[Circle] | EulerFit[Ellipse] | EulerFit[Square] | EulerFit[Rectangle]:
    """Fit an area-proportional Euler diagram.

    Parameters
    ----------
    values:
        Mapping from set-combination labels (e.g. ``"A"``, ``"A&B"``) to
        their areas.
    input:
        ``"exclusive"`` (default): values are per-region areas, with no
        overlap from other sets included.
        ``"inclusive"``: values are total set sizes that include overlaps;
        the eunoia core converts internally.
    shape:
        ``"circle"`` (default), ``"ellipse"``, ``"square"`` or
        ``"rectangle"``.
    seed:
        Optional seed for the optimizer's RNG (for reproducibility).
    complement:
        Area outside every named set (the universe / "complement"). When
        given, the core jointly fits a container box and the result carries
        a ``container``. Requires every set to overlap into one cluster.

    Returns
    -------
    EulerFit
        A fit result with shapes, original/fitted values, residuals,
        region error, diag_error, stress, and loss.
    """
    if shape not in ("circle", "ellipse", "square", "rectangle"):
        raise EunoiaError(
            "invalid_shape: shape must be 'circle', 'ellipse', 'square' or "
            f"'rectangle', got {shape!r}"
        )

    combinations = parse_dict_input(values)
    canonical_keys = [canonicalize(k) for k in values]
    original_values = {
        ck: float(v) for ck, v in zip(canonical_keys, values.values(), strict=True)
    }

    if shape == "circle":
        result = _fit_circles(combinations, input, complement, seed)
        return _finish(
            result,
            build_circles(result["shapes"]),
            original_values,
            canonical_keys,
            input,
        )

    if shape == "ellipse":
        result_e = _fit_ellipses(combinations, input, complement, seed)
        return _finish(
            result_e,
            build_ellipses(result_e["shapes"]),
            original_values,
            canonical_keys,
            input,
        )

    if shape == "square":
        result_s = _fit_squares(combinations, input, complement, seed)
        return _finish(
            result_s,
            build_squares(result_s["shapes"]),
            original_values,
            canonical_keys,
            input,
        )

    result_r = _fit_rectangles(combinations, input, complement, seed)
    return _finish(
        result_r,
        build_rectangles(result_r["shapes"]),
        original_values,
        canonical_keys,
        input,
    )


def _finish(
    result: Mapping[str, Any],
    shapes: tuple[S, ...],
    original_values: dict[str, float],
    canonical_keys: list[str],
    input: str,
) -> EulerFit[S]:
    """Assemble an ``EulerFit`` from a raw Rust result and built shapes."""
    fitted_exclusive = result["fitted_exclusive"]
    if input == "exclusive":
        fitted_values = {
            ck: float(fitted_exclusive.get(ck, 0.0)) for ck in canonical_keys
        }
    else:
        fitted_values = to_inclusive(fitted_exclusive, canonical_keys)
    residuals = {ck: original_values[ck] - fitted_values[ck] for ck in canonical_keys}
    return EulerFit(
        shapes=shapes,
        original_values=original_values,
        fitted_values=fitted_values,
        residuals=residuals,
        region_error={k: float(v) for k, v in result["region_error"].items()},
        diag_error=float(result["diag_error"]),
        stress=float(result["stress"]),
        loss=float(result["loss"]),
        container=build_container(result.get("container")),
        plot_data=build_plot_data(result),
    )


def build_circles(raw: Sequence[Any]) -> tuple[Circle, ...]:
    """Map raw circle dicts from the Rust binding to ``Circle`` instances."""
    return tuple(
        Circle(set=s["set"], center=Point(x=s["x"], y=s["y"]), radius=s["radius"])
        for s in raw
    )


def build_ellipses(raw: Sequence[Any]) -> tuple[Ellipse, ...]:
    """Map raw ellipse dicts from the Rust binding to ``Ellipse`` instances."""
    return tuple(
        Ellipse(
            set=s["set"],
            center=Point(x=s["x"], y=s["y"]),
            semi_major=s["semi_major"],
            semi_minor=s["semi_minor"],
            rotation=s["rotation"],
        )
        for s in raw
    )


def build_squares(raw: Sequence[Any]) -> tuple[Square, ...]:
    """Map raw square dicts from the Rust binding to ``Square`` instances."""
    return tuple(
        Square(set=s["set"], center=Point(x=s["x"], y=s["y"]), side=s["side"])
        for s in raw
    )


def build_rectangles(raw: Sequence[Any]) -> tuple[Rectangle, ...]:
    """Map raw rectangle dicts from the Rust binding to ``Rectangle``."""
    return tuple(
        Rectangle(
            set=s["set"],
            center=Point(x=s["x"], y=s["y"]),
            width=s["width"],
            height=s["height"],
        )
        for s in raw
    )


def build_container(container_data: Mapping[str, float] | None) -> Container | None:
    """Map the raw container dict (or ``None``) to a ``Container``."""
    if container_data is None:
        return None
    return Container(
        center=Point(x=container_data["x"], y=container_data["y"]),
        width=container_data["width"],
        height=container_data["height"],
    )


def build_plot_data(result: Mapping[str, Any]) -> dict[str, Any]:
    """Extract the matplotlib rendering bundle from a raw Rust result."""
    return {
        "region_pieces": result["region_pieces"],
        "region_anchors": result["region_anchors"],
        "region_areas": result["region_areas"],
        "set_anchors": result["set_anchors"],
        "shape_outlines": result["shape_outlines"],
    }
