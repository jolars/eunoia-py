"""Type stubs for the compiled ``eunoia._eunoia`` Rust extension."""

from typing import TypedDict

__all__ = [
    "EunoiaError",
    "_fit_circles",
    "_fit_ellipses",
    "_smoke",
]

class EunoiaError(ValueError): ...

class _CircleDict(TypedDict):
    set: str
    x: float
    y: float
    radius: float

class _EllipseDict(TypedDict):
    set: str
    x: float
    y: float
    semi_major: float
    semi_minor: float
    rotation: float

class _RegionPiece(TypedDict):
    outer: list[tuple[float, float]]
    holes: list[list[tuple[float, float]]]

class _CircleResult(TypedDict):
    shapes: list[_CircleDict]
    fitted_exclusive: dict[str, float]
    region_error: dict[str, float]
    diag_error: float
    stress: float
    loss: float
    iterations: int
    region_pieces: dict[str, list[_RegionPiece]]
    region_anchors: dict[str, tuple[float, float]]
    region_areas: dict[str, float]
    set_anchors: dict[str, tuple[float, float]]
    shape_outlines: dict[str, list[tuple[float, float]]]

class _EllipseResult(TypedDict):
    shapes: list[_EllipseDict]
    fitted_exclusive: dict[str, float]
    region_error: dict[str, float]
    diag_error: float
    stress: float
    loss: float
    iterations: int
    region_pieces: dict[str, list[_RegionPiece]]
    region_anchors: dict[str, tuple[float, float]]
    region_areas: dict[str, float]
    set_anchors: dict[str, tuple[float, float]]
    shape_outlines: dict[str, list[tuple[float, float]]]

def _smoke() -> str: ...
def _fit_circles(
    combinations: list[tuple[str, float]],
    input_kind: str,
    seed: int | None = None,
) -> _CircleResult: ...
def _fit_ellipses(
    combinations: list[tuple[str, float]],
    input_kind: str,
    seed: int | None = None,
) -> _EllipseResult: ...
