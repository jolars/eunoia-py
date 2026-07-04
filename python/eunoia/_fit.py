"""Public ``euler()`` function, dispatching to the Rust binding."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import Any, Literal, cast, overload

import numpy.typing as npt
from narwhals.typing import IntoFrame

from eunoia._dataframe import dataframe_to_combinations, is_dataframe
from eunoia._eunoia import (
    EunoiaError,
    _fit_circles,
    _fit_ellipses,
    _fit_rectangles,
    _fit_rotated_rectangles,
    _fit_squares,
)
from eunoia._models import (
    Circle,
    Container,
    Ellipse,
    EulerFit,
    Point,
    Rectangle,
    RotatedRectangle,
    S,
    Square,
)
from eunoia._numpy import is_ndarray, ndarray_to_combinations, ndarray_to_members
from eunoia._parse import (
    canonicalize,
    is_membership_input,
    parse_dict_input,
    parse_membership_input,
    to_inclusive,
)

EulerInput = (
    Mapping[str, float] | Mapping[str, Collection[str]] | IntoFrame | npt.NDArray[Any]
)
"""Region areas (``{"A&B": 3}``), membership lists (``{"A": ["x", "y"]}``), a
DataFrame (pandas, polars, … via narwhals), or a numpy boolean array used as a
membership matrix."""


Loss = Literal[
    "sum_squared",
    "sum_absolute",
    "sum_squared_region_error",
    "sum_absolute_region_error",
    "max_absolute",
    "max_squared",
    "root_mean_squared",
    "stress",
    "diag_error",
    "log_sum_absolute",
]
"""Objective the optimizer minimizes. ``None`` uses the core default
(``"sum_squared"``)."""


Optimizer = Literal[
    "levenberg_marquardt",
    "lbfgs",
    "nelder_mead",
    "cma_es_lm",
    "trf",
    "cma_es_trf",
    "mads",
]
"""Final-stage optimizer the fitter uses. ``None`` keeps the core default
(``"cma_es_trf"``)."""


@overload
def euler(
    values: EulerInput,
    *,
    input: Literal["exclusive", "inclusive"] = ...,
    names: Sequence[str] | None = ...,
    ids: str | Sequence[object] | None = ...,
    shape: Literal["circle"] = ...,
    seed: int | None = ...,
    complement: float | None = ...,
    loss: Loss | None = ...,
    optimizer: Optimizer | None = ...,
    tolerance: float | None = ...,
    n_restarts: int | None = ...,
    max_iterations: int | None = ...,
    n_threads: int | None = ...,
) -> EulerFit[Circle]: ...


@overload
def euler(
    values: EulerInput,
    *,
    input: Literal["exclusive", "inclusive"] = ...,
    names: Sequence[str] | None = ...,
    ids: str | Sequence[object] | None = ...,
    shape: Literal["ellipse"],
    seed: int | None = ...,
    complement: float | None = ...,
    loss: Loss | None = ...,
    optimizer: Optimizer | None = ...,
    tolerance: float | None = ...,
    n_restarts: int | None = ...,
    max_iterations: int | None = ...,
    n_threads: int | None = ...,
) -> EulerFit[Ellipse]: ...


@overload
def euler(
    values: EulerInput,
    *,
    input: Literal["exclusive", "inclusive"] = ...,
    names: Sequence[str] | None = ...,
    ids: str | Sequence[object] | None = ...,
    shape: Literal["square"],
    seed: int | None = ...,
    complement: float | None = ...,
    loss: Loss | None = ...,
    optimizer: Optimizer | None = ...,
    tolerance: float | None = ...,
    n_restarts: int | None = ...,
    max_iterations: int | None = ...,
    n_threads: int | None = ...,
) -> EulerFit[Square]: ...


@overload
def euler(
    values: EulerInput,
    *,
    input: Literal["exclusive", "inclusive"] = ...,
    names: Sequence[str] | None = ...,
    ids: str | Sequence[object] | None = ...,
    shape: Literal["rectangle"],
    seed: int | None = ...,
    complement: float | None = ...,
    loss: Loss | None = ...,
    optimizer: Optimizer | None = ...,
    tolerance: float | None = ...,
    n_restarts: int | None = ...,
    max_iterations: int | None = ...,
    n_threads: int | None = ...,
) -> EulerFit[Rectangle]: ...


@overload
def euler(
    values: EulerInput,
    *,
    input: Literal["exclusive", "inclusive"] = ...,
    names: Sequence[str] | None = ...,
    ids: str | Sequence[object] | None = ...,
    shape: Literal["rotated_rectangle"],
    seed: int | None = ...,
    complement: float | None = ...,
    loss: Loss | None = ...,
    optimizer: Optimizer | None = ...,
    tolerance: float | None = ...,
    n_restarts: int | None = ...,
    max_iterations: int | None = ...,
    n_threads: int | None = ...,
) -> EulerFit[RotatedRectangle]: ...


def euler(
    values: EulerInput,
    *,
    input: Literal["exclusive", "inclusive"] = "exclusive",
    names: Sequence[str] | None = None,
    ids: str | Sequence[object] | None = None,
    shape: Literal[
        "circle", "ellipse", "square", "rectangle", "rotated_rectangle"
    ] = "circle",
    seed: int | None = None,
    complement: float | None = None,
    loss: Loss | None = None,
    optimizer: Optimizer | None = None,
    tolerance: float | None = None,
    n_restarts: int | None = None,
    max_iterations: int | None = None,
    n_threads: int | None = None,
) -> (
    EulerFit[Circle]
    | EulerFit[Ellipse]
    | EulerFit[Square]
    | EulerFit[Rectangle]
    | EulerFit[RotatedRectangle]
):
    """Fit an area-proportional Euler diagram.

    Parameters
    ----------
    values:
        One of three forms:

        * a mapping from set-combination labels (e.g. ``"A"``, ``"A&B"``) to
          their areas;
        * a mapping from set names to membership collections
          (``{"A": ["x", "y"], "B": ["y", "z"]}``);
        * a DataFrame (pandas, polars, or anything narwhals supports) treated
          as a membership matrix: each column is a set, each row an observation,
          and a truthy cell denotes membership. Columns must be boolean or
          ``0/1`` numeric.
        * a numpy boolean array used as a membership matrix (the matrix idiom
          from eulerr): a 2-D ``(n_observations, n_sets)`` array, or a 1-D array
          read as a single set. Values must be boolean or ``0/1`` numeric;
          ``NaN`` cells count as non-members. Set names come from ``names`` or
          are generated (``"A"``, ``"B"``, …).

        For the membership-list, DataFrame, and array forms, each element/row is
        counted into the canonical region of the sets it belongs to, yielding
        exclusive per-region counts (so ``input`` must stay ``"exclusive"``).
    input:
        ``"exclusive"`` (default): values are per-region areas, with no
        overlap from other sets included.
        ``"inclusive"``: values are total set sizes that include overlaps;
        the eunoia core converts internally.
    names:
        Set names for numpy-array input, one per column (or a single name for a
        1-D array). Defaults to ``"A"``, ``"B"``, …. Only valid for array input;
        other forms carry their own names and passing ``names`` raises.
    ids:
        Per-observation member identifiers, so the fit retains *who* is in each
        region (surfaced as :attr:`~EulerFit.members` and drawable with
        ``plot(members=True)``). Only valid for array and DataFrame input: pass a
        sequence with one entry per row (array or DataFrame), or, for a
        DataFrame, the name of a column to read the identifiers from and exclude
        from the sets. Membership-list input carries its members intrinsically
        (no ``ids`` needed); passing ``ids`` with any other form raises.
    shape:
        ``"circle"`` (default), ``"ellipse"``, ``"square"``,
        ``"rectangle"``, or ``"rotated_rectangle"``.
    seed:
        Optional seed for the optimizer's RNG (for reproducibility).
    complement:
        Area outside every named set (the universe or "complement"). When
        given, the core jointly fits a container box and the result carries
        a ``container``. Requires every set to overlap into one cluster.
    loss:
        The objective the optimizer minimizes. ``None`` (default) uses the
        core default, ``"sum_squared"`` (normalized sum of squared region
        residuals). Other options trade off how error is distributed across
        regions, e.g. ``"sum_absolute"``, ``"stress"`` (venneuler-style),
        ``"diag_error"`` (eulerAPE worst-region), the region-error variants,
        and the max-error variants. See :data:`Loss`.
    optimizer:
        The final-stage optimizer the core uses. ``None`` (default) keeps the
        core default, ``"cma_es_trf"`` (CMA-ES global escape with a bounded
        trust-region-reflective polish). Other options trade robustness for
        speed: ``"levenberg_marquardt"``, ``"lbfgs"``, ``"nelder_mead"``,
        ``"cma_es_lm"``, ``"trf"``, ``"mads"`` (a derivative-free
        mesh-adaptive direct search). See :data:`Optimizer`.
    tolerance:
        Cost-change convergence tolerance for the final-stage optimizer.
        ``None`` keeps the core default (``1e-3``); smaller values fit more
        tightly at the cost of more iterations.
    n_restarts:
        Number of full-pipeline restarts (fresh initialization + optimization),
        keeping the lowest-loss result. ``None`` keeps the core default
        (``10``). Higher values better approach the global optimum but cost
        proportionally more; ``1`` disables restarts.
    max_iterations:
        Maximum optimizer iterations per fit. ``None`` keeps the core default
        (``200``).
    n_threads:
        Number of threads used to run the ``n_restarts`` restarts in parallel.
        ``None`` (default) uses all available logical cores; a positive integer
        caps the thread pool, and ``1`` runs serially. This does not affect the
        result of a seeded fit (the lowest-loss restart is selected regardless
        of completion order), only how fast it is computed. The default pool
        also honors the ``RAYON_NUM_THREADS`` environment variable.

    Returns
    -------
    EulerFit
        A fit result with shapes, original/fitted values, residuals,
        region error, diag_error, stress, and loss.
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

    if names is not None and not is_ndarray(values):
        raise EunoiaError("invalid_input: names= is only valid for numpy array input")

    members_map: dict[str, list[str]] | None = None

    if is_ndarray(values):
        if input != "exclusive":
            raise EunoiaError(
                "invalid_input: array input is always exclusive; "
                "do not pass input='inclusive'"
            )
        combinations = ndarray_to_combinations(values, names)
        canonical_keys = [c for c, _ in combinations]  # already canonical
        original_values = {c: v for c, v in combinations}
        if ids is not None:
            if isinstance(ids, str):
                raise EunoiaError(
                    "invalid_input: ids as a column name is only valid for "
                    "DataFrame input; pass a per-row sequence for array input"
                )
            members_map = ndarray_to_members(values, names, ids)
    elif is_dataframe(values):
        if input != "exclusive":
            raise EunoiaError(
                "invalid_input: DataFrame input is always exclusive; "
                "do not pass input='inclusive'"
            )
        _, combinations, members_map = dataframe_to_combinations(values, ids)
        canonical_keys = [c for c, _ in combinations]  # already canonical
        original_values = {c: v for c, v in combinations}
    else:
        if ids is not None:
            raise EunoiaError(
                "invalid_input: ids= is only valid for array or DataFrame input"
            )
        mapping = cast("Mapping[str, Any]", values)
        try:
            membership = is_membership_input(mapping)
        except ValueError as exc:
            raise EunoiaError(str(exc)) from exc

        if membership:
            if input != "exclusive":
                raise EunoiaError(
                    "invalid_input: membership-list input is always exclusive; "
                    "do not pass input='inclusive'"
                )
            combinations, members_map = parse_membership_input(mapping)
            canonical_keys = [c for c, _ in combinations]  # already canonical
            original_values = {c: v for c, v in combinations}
        else:
            combinations = parse_dict_input(mapping)
            canonical_keys = [canonicalize(k) for k in mapping]
            original_values = {
                ck: v for ck, (_, v) in zip(canonical_keys, combinations, strict=True)
            }

    if shape == "circle":
        result = _fit_circles(
            combinations,
            input,
            complement,
            seed,
            loss,
            optimizer,
            tolerance,
            n_restarts,
            max_iterations,
            n_threads,
        )
        return _finish(
            result,
            build_circles(result["shapes"]),
            original_values,
            canonical_keys,
            input,
            members_map,
        )

    if shape == "ellipse":
        result_e = _fit_ellipses(
            combinations,
            input,
            complement,
            seed,
            loss,
            optimizer,
            tolerance,
            n_restarts,
            max_iterations,
            n_threads,
        )
        return _finish(
            result_e,
            build_ellipses(result_e["shapes"]),
            original_values,
            canonical_keys,
            input,
            members_map,
        )

    if shape == "square":
        result_s = _fit_squares(
            combinations,
            input,
            complement,
            seed,
            loss,
            optimizer,
            tolerance,
            n_restarts,
            max_iterations,
            n_threads,
        )
        return _finish(
            result_s,
            build_squares(result_s["shapes"]),
            original_values,
            canonical_keys,
            input,
            members_map,
        )

    if shape == "rectangle":
        result_r = _fit_rectangles(
            combinations,
            input,
            complement,
            seed,
            loss,
            optimizer,
            tolerance,
            n_restarts,
            max_iterations,
            n_threads,
        )
        return _finish(
            result_r,
            build_rectangles(result_r["shapes"]),
            original_values,
            canonical_keys,
            input,
            members_map,
        )

    result_rr = _fit_rotated_rectangles(
        combinations,
        input,
        complement,
        seed,
        loss,
        optimizer,
        tolerance,
        n_restarts,
        max_iterations,
        n_threads,
    )
    return _finish(
        result_rr,
        build_rotated_rectangles(result_rr["shapes"]),
        original_values,
        canonical_keys,
        input,
        members_map,
    )


def _finish(
    result: Mapping[str, Any],
    shapes: tuple[S, ...],
    original_values: dict[str, float],
    canonical_keys: list[str],
    input: str,
    members: dict[str, list[str]] | None = None,
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
        members=members,
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


def build_rotated_rectangles(raw: Sequence[Any]) -> tuple[RotatedRectangle, ...]:
    """Map raw rotated-rectangle dicts from the Rust binding to
    ``RotatedRectangle``."""
    return tuple(
        RotatedRectangle(
            set=s["set"],
            center=Point(x=s["x"], y=s["y"]),
            width=s["width"],
            height=s["height"],
            rotation=s["rotation"],
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
        "set_anchor_regions": result["set_anchor_regions"],
        "shape_outlines": result["shape_outlines"],
    }
