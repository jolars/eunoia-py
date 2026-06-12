"""Package-independent fit-quality metric.

Every fitter returns geometry (circles or ellipses). To score them on equal
footing we ignore whatever error each package reports about itself and instead
*re-measure* the fitted diagram: rasterize the shapes onto a dense grid, label
each pixel with the set-membership signature it falls in, sum pixel areas per
region, and compare those fitted region fractions to the target fractions.

The benchmark compares fitters *grouped by the objective they minimize*, and
scores each group on that objective. So there is one metric per loss family,
each a **scale-invariant** goodness-of-fit (a single multiplicative scale on the
fitted areas is absorbed, since each package draws at an arbitrary size):

* ``stress``    -- sum-of-squared-errors family (venneuler's stress).
* ``abs_error`` -- sum-of-absolute-errors family.
* ``log_error`` -- logarithmic-L1 family (what matplotlib-venn's venn3 and
  matplotlib-set-diagrams("logarithmic") minimize).

Because the same rasterizer + same metric scores every member of a group, the
within-group numbers are directly comparable and independent of diagram scale.
``stress`` mirrors ``Layout::stress`` in the eunoia core, so it can be validated
against ``fit.stress``.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class Shape:
    """A fitted shape, normalized across packages.

    A circle is the special case of an ellipse with ``semi_major == semi_minor``
    and ``rotation == 0``; storing it generally lets the rasterizer treat every
    package uniformly.
    """

    set: str
    cx: float
    cy: float
    semi_major: float
    semi_minor: float
    rotation: float = 0.0

    @classmethod
    def circle(cls, set: str, cx: float, cy: float, r: float) -> Shape:
        return cls(set, cx, cy, r, r, 0.0)


def _region_key(names: tuple[str, ...]) -> str:
    """Canonical region key: set names sorted, joined by ``&`` (eunoia form)."""
    return "&".join(sorted(names))


def all_region_keys(sets: tuple[str, ...]) -> list[str]:
    """Every non-empty region of the powerset, in canonical form."""
    keys: list[str] = []
    for size in range(1, len(sets) + 1):
        for combo in combinations(sorted(sets), size):
            keys.append(_region_key(combo))
    return keys


def _inside_mask(
    shape: Shape, xs: npt.NDArray[np.float64], ys: npt.NDArray[np.float64]
) -> npt.NDArray[np.bool_]:
    """Boolean mask of grid points inside ``shape`` (vectorized)."""
    dx = xs - shape.cx
    dy = ys - shape.cy
    if shape.rotation:
        cos_t = np.cos(-shape.rotation)
        sin_t = np.sin(-shape.rotation)
        rx = cos_t * dx - sin_t * dy
        ry = sin_t * dx + cos_t * dy
    else:
        rx, ry = dx, dy
    return (rx / shape.semi_major) ** 2 + (ry / shape.semi_minor) ** 2 <= 1.0


def rasterize_regions(
    shapes: list[Shape], sets: tuple[str, ...], resolution: int = 1000
) -> dict[str, float]:
    """Estimate the area of every region by counting grid pixels.

    Returns a dict keyed by canonical region string with pixel-area values for
    every region in the powerset of ``sets`` (zero where nothing falls).
    """
    region_keys = all_region_keys(sets)
    areas = dict.fromkeys(region_keys, 0.0)
    if not shapes:
        return areas

    # Bounding box over all shapes (a generous box; ellipses bounded by axes).
    min_x = min(s.cx - max(s.semi_major, s.semi_minor) for s in shapes)
    max_x = max(s.cx + max(s.semi_major, s.semi_minor) for s in shapes)
    min_y = min(s.cy - max(s.semi_major, s.semi_minor) for s in shapes)
    max_y = max(s.cy + max(s.semi_major, s.semi_minor) for s in shapes)
    pad_x = 0.02 * (max_x - min_x or 1.0)
    pad_y = 0.02 * (max_y - min_y or 1.0)

    xs_1d = np.linspace(min_x - pad_x, max_x + pad_x, resolution)
    ys_1d = np.linspace(min_y - pad_y, max_y + pad_y, resolution)
    xs, ys = np.meshgrid(xs_1d, ys_1d)
    pixel_area = ((xs_1d[1] - xs_1d[0]) * (ys_1d[1] - ys_1d[0])).item()

    # Per-set membership: OR together every shape belonging to the same set
    # (each set is one shape here, but this stays correct if that changes).
    membership: dict[str, npt.NDArray[np.bool_]] = {
        name: np.zeros(xs.shape, dtype=bool) for name in sets
    }
    for shape in shapes:
        membership[shape.set] |= _inside_mask(shape, xs, ys)

    # Encode each pixel's signature as an integer over the powerset, then map
    # the populated signatures back to region keys.
    order = sorted(sets)
    signature = np.zeros(xs.shape, dtype=np.int64)
    for bit, name in enumerate(order):
        signature |= membership[name].astype(np.int64) << bit

    codes, counts = np.unique(signature, return_counts=True)
    for code, count in zip(codes, counts, strict=True):
        if code == 0:
            continue  # outside every set
        names = tuple(order[bit] for bit in range(len(order)) if code & (1 << bit))
        areas[_region_key(names)] += float(count) * pixel_area
    return areas


# --------------------------------------------------------------------------- #
# Scale-invariant goodness-of-fit, one per objective family.
#
# Each package draws its diagram at an arbitrary coordinate scale, so before
# scoring we absorb a single multiplicative scale `b` on the fitted areas,
# choosing the `b` that minimizes that family's discrepancy. This isolates
# layout quality from diagram size and lets each fitter be judged on exactly the
# loss family it (and its group-mates) minimized.
# --------------------------------------------------------------------------- #
def _aligned(fitted: dict[str, float], target: dict[str, float]):
    keys = sorted(set(fitted) | set(target))
    f = np.array([fitted.get(k, 0.0) for k in keys], dtype=float)
    t = np.array([target.get(k, 0.0) for k in keys], dtype=float)
    return f, t


def stress(fitted: dict[str, float], target: dict[str, float]) -> float:
    """venneuler / eulerr ``stress``: ``Σ(f - β·t)² / Σf²``, ``β = Σ(f·t)/Σt²``.

    The scale-invariant goodness-of-fit for the **sum-of-squared-errors** family.
    Mirrors ``Layout::stress`` in the eunoia core, so it validates against
    ``fit.stress``.
    """
    f, t = _aligned(fitted, target)
    sum_t2 = float(t @ t)
    sum_f2 = float(f @ f)
    if sum_t2 < 1e-20 or sum_f2 < 1e-20:
        return 0.0
    beta = float(f @ t) / sum_t2
    return float(np.sum((f - beta * t) ** 2) / sum_f2)


def abs_error(fitted: dict[str, float], target: dict[str, float]) -> float:
    """Scale-invariant **sum of absolute errors**: ``min_b Σ|b·f - t| / Σ|t|``.

    The optimal scale ``b`` is the ``f``-weighted median of ``t_i / f_i``; this
    is the absolute-error analogue of ``stress``.
    """
    f, t = _aligned(fitted, target)
    denom = float(np.sum(np.abs(t)))
    if denom < 1e-20:
        return 0.0
    mask = f > 1e-12
    if not mask.any():
        return float(np.sum(np.abs(t)) / denom)
    ratios = t[mask] / f[mask]
    weights = f[mask]
    order = np.argsort(ratios)
    ratios, weights = ratios[order], weights[order]
    cum = np.cumsum(weights)
    b = float(ratios[np.searchsorted(cum, cum[-1] / 2.0)])
    return float(np.sum(np.abs(b * f - t)) / denom)


def log_error(fitted: dict[str, float], target: dict[str, float]) -> float:
    """Scale-invariant **logarithmic L1**:
    ``min_b Σ|log(1+b·f) - log(1+t)| / Σ log(1+t)``.

    This is the objective ``matplotlib-venn``'s ``venn3`` and
    ``matplotlib-set-diagrams("logarithmic")`` minimize. ``b`` is found by a
    1-D search over a wide log-spaced bracket (the curve is well behaved).
    """
    f, t = _aligned(fitted, target)
    denom = float(np.sum(np.log1p(t)))
    if denom < 1e-20 or float(np.sum(f)) < 1e-20:
        return 0.0
    b0 = float(np.sum(t)) / float(np.sum(f))  # total-match starting scale
    betas = (b0 * np.logspace(-3, 3, 2000))[:, None]  # (B, 1)
    logt = np.log1p(t)[None, :]  # (1, R)
    costs = np.sum(np.abs(np.log1p(betas * f[None, :]) - logt), axis=1)  # (B,)
    return float(costs.min() / denom)


# Registry: metric key -> (function, human label).
METRICS = {
    "stress": (stress, "stress (sum of squared errors)"),
    "abs_error": (abs_error, "abs error (sum of absolute errors)"),
    "log_error": (log_error, "log error (logarithmic L1)"),
}


def score(
    shapes: list[Shape],
    sets: tuple[str, ...],
    target: dict[str, float],
    metric: str,
    resolution: int = 1000,
) -> float:
    """Rasterize ``shapes`` and score them with the named ``metric``."""
    fitted = rasterize_regions(shapes, sets, resolution=resolution)
    return METRICS[metric][0](fitted, target)
