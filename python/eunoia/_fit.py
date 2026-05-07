"""Public ``euler()`` function — dispatches to the Rust binding."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, overload

from eunoia._eunoia import EunoiaError, _fit_circles, _fit_ellipses
from eunoia._models import Circle, Ellipse, EulerFit, Point
from eunoia._parse import canonicalize, parse_dict_input, to_inclusive


@overload
def euler(
    values: Mapping[str, float],
    *,
    input: Literal["exclusive", "inclusive"] = ...,
    shape: Literal["circle"] = ...,
    seed: int | None = ...,
) -> EulerFit[Circle]: ...


@overload
def euler(
    values: Mapping[str, float],
    *,
    input: Literal["exclusive", "inclusive"] = ...,
    shape: Literal["ellipse"],
    seed: int | None = ...,
) -> EulerFit[Ellipse]: ...


def euler(
    values: Mapping[str, float],
    *,
    input: Literal["exclusive", "inclusive"] = "exclusive",
    shape: Literal["circle", "ellipse"] = "circle",
    seed: int | None = None,
) -> EulerFit[Circle] | EulerFit[Ellipse]:
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
        ``"circle"`` (default) or ``"ellipse"``.
    seed:
        Optional seed for the optimizer's RNG (for reproducibility).

    Returns
    -------
    EulerFit
        A fit result with shapes, original/fitted values, residuals,
        region error, diag_error, stress, and loss.
    """
    if shape not in ("circle", "ellipse"):
        raise EunoiaError(
            f"invalid_shape: shape must be 'circle' or 'ellipse', got {shape!r}"
        )

    combinations = parse_dict_input(values)
    canonical_keys = [canonicalize(k) for k in values]
    original_values = {
        ck: float(v) for ck, v in zip(canonical_keys, values.values(), strict=True)
    }

    if shape == "circle":
        result = _fit_circles(combinations, input, seed)
        circle_shapes: tuple[Circle, ...] = tuple(
            Circle(
                set=s["set"],
                center=Point(x=s["x"], y=s["y"]),
                radius=s["radius"],
            )
            for s in result["shapes"]
        )
        fitted_exclusive = result["fitted_exclusive"]
        if input == "exclusive":
            fitted_values = {
                ck: float(fitted_exclusive.get(ck, 0.0)) for ck in canonical_keys
            }
        else:
            fitted_values = to_inclusive(fitted_exclusive, canonical_keys)
        residuals = {
            ck: original_values[ck] - fitted_values[ck] for ck in canonical_keys
        }
        return EulerFit[Circle](
            shapes=circle_shapes,
            original_values=original_values,
            fitted_values=fitted_values,
            residuals=residuals,
            region_error={k: float(v) for k, v in result["region_error"].items()},
            diag_error=float(result["diag_error"]),
            stress=float(result["stress"]),
            loss=float(result["loss"]),
            plot_data={
                "region_pieces": result["region_pieces"],
                "region_anchors": result["region_anchors"],
                "region_areas": result["region_areas"],
                "set_anchors": result["set_anchors"],
                "shape_outlines": result["shape_outlines"],
            },
        )

    result_e = _fit_ellipses(combinations, input, seed)
    ellipse_shapes: tuple[Ellipse, ...] = tuple(
        Ellipse(
            set=s["set"],
            center=Point(x=s["x"], y=s["y"]),
            semi_major=s["semi_major"],
            semi_minor=s["semi_minor"],
            rotation=s["rotation"],
        )
        for s in result_e["shapes"]
    )
    fitted_exclusive_e = result_e["fitted_exclusive"]
    if input == "exclusive":
        fitted_values_e = {
            ck: float(fitted_exclusive_e.get(ck, 0.0)) for ck in canonical_keys
        }
    else:
        fitted_values_e = to_inclusive(fitted_exclusive_e, canonical_keys)
    residuals_e = {
        ck: original_values[ck] - fitted_values_e[ck] for ck in canonical_keys
    }
    return EulerFit[Ellipse](
        shapes=ellipse_shapes,
        original_values=original_values,
        fitted_values=fitted_values_e,
        residuals=residuals_e,
        region_error={k: float(v) for k, v in result_e["region_error"].items()},
        diag_error=float(result_e["diag_error"]),
        stress=float(result_e["stress"]),
        loss=float(result_e["loss"]),
        plot_data={
            "region_pieces": result_e["region_pieces"],
            "region_anchors": result_e["region_anchors"],
            "region_areas": result_e["region_areas"],
            "set_anchors": result_e["set_anchors"],
            "shape_outlines": result_e["shape_outlines"],
        },
    )
