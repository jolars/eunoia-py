"""Adapters that drive each fitter from a common :class:`~benchmarks.cases.Case`.

Every adapter exposes the same tiny interface:

* ``available`` / ``version`` -- is the package importable, and which version
* ``supports(case)`` -- can this fitter represent the case at all (set-count cap)
* ``fit(case) -> list[Shape]`` -- run the fitter and return normalized geometry

The benchmark compares fitters *grouped by the objective they minimize*, so the
configurable fitters are parameterized: ``EunoiaAdapter`` takes a ``loss`` and
``MatplotlibSetDiagramsAdapter`` takes a cost ``objective``. ``display`` is the
bare package name (the objective is set by the group it appears in); ``id`` is
unique per configuration so results can be keyed.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from itertools import combinations
from typing import Protocol

from .cases import Case
from .metrics import Shape


class Adapter(Protocol):
    """Structural type implemented by every fitter adapter."""

    id: str
    display: str
    available: bool
    version: str | None

    def supports(self, case: Case) -> bool: ...

    def fit(self, case: Case) -> list[Shape]: ...


def _dist_version(dist: str) -> str | None:
    try:
        return version(dist)
    except PackageNotFoundError:
        return None


# --------------------------------------------------------------------------- #
# eunoia (this package): circles and ellipses, arbitrary set count, any loss.
# --------------------------------------------------------------------------- #
class EunoiaAdapter:
    def __init__(self, shape: str, loss: str | None = None) -> None:
        self.shape = shape
        self.loss = loss
        self.id = f"eunoia-{shape}" + (f"-{loss}" if loss else "")
        self.display = f"eunoia ({shape})"
        try:
            import eunoia  # noqa: F401

            self.available = True
            self.version = _dist_version("eunoia")
        except ImportError:
            self.available = False
            self.version = None

    def supports(self, case: Case) -> bool:
        return case.n_sets >= 2

    def _fit(self, case: Case):
        import eunoia as eu

        return eu.euler(case.regions, shape=self.shape, seed=0, loss=self.loss)

    def fit(self, case: Case) -> list[Shape]:
        shapes: list[Shape] = []
        for s in self._fit(case).shapes:
            if self.shape == "circle":
                shapes.append(Shape.circle(s.set, s.center.x, s.center.y, s.radius))
            else:
                shapes.append(
                    Shape(
                        s.set,
                        s.center.x,
                        s.center.y,
                        s.semi_major,
                        s.semi_minor,
                        s.rotation,
                    )
                )
        return shapes

    def native_stress(self, case: Case) -> float:
        """eunoia's own analytic ``stress`` -- used as a metric self-check."""
        return float(self._fit(case).stress)


# --------------------------------------------------------------------------- #
# matplotlib-venn: circles, 2 or 3 sets. Fixed objective:
#   venn2 closed-form exact; venn3 default = Σ|log(1+t) - log(1+a)| (log L1).
# --------------------------------------------------------------------------- #
class MatplotlibVennAdapter:
    id = "matplotlib-venn"
    display = "matplotlib-venn"

    def __init__(self) -> None:
        try:
            import matplotlib_venn  # noqa: F401

            self.available = True
            self.version = _dist_version("matplotlib-venn")
        except ImportError:
            self.available = False
            self.version = None

    def supports(self, case: Case) -> bool:
        return case.n_sets in (2, 3)

    def fit(self, case: Case) -> list[Shape]:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib_venn import venn2, venn3

        order = sorted(case.sets)
        r = case.regions

        def area(*names: str) -> float:
            return r.get("&".join(sorted(names)), 0.0)

        fig, ax = plt.subplots()
        try:
            if case.n_sets == 2:
                a, b = order
                subsets = (area(a), area(b), area(a, b))
                vd = venn2(subsets=subsets, ax=ax)
            else:
                a, b, c = order
                # venn3 tuple order: Abc, aBc, ABc, abC, AbC, aBC, ABC
                subsets = (
                    area(a),
                    area(b),
                    area(a, b),
                    area(c),
                    area(a, c),
                    area(b, c),
                    area(a, b, c),
                )
                vd = venn3(subsets=subsets, ax=ax)
            shapes = [
                Shape.circle(
                    order[i], vd.centers[i].x, vd.centers[i].y, float(vd.radii[i])
                )
                for i in range(case.n_sets)
            ]
        finally:
            plt.close(fig)
        return shapes


# --------------------------------------------------------------------------- #
# matplotlib-set-diagrams: circles, arbitrary set count, configurable objective
# ("squared", "simple", "logarithmic", "relative", "inverse"; default "inverse").
# --------------------------------------------------------------------------- #
class MatplotlibSetDiagramsAdapter:
    display = "matplotlib-set-diagrams"

    def __init__(self, objective: str = "squared") -> None:
        self.objective = objective
        self.id = f"matplotlib-set-diagrams-{objective}"
        try:
            import matplotlib_set_diagrams  # noqa: F401

            self.available = True
            self.version = _dist_version("matplotlib-set-diagrams")
        except ImportError:
            self.available = False
            self.version = None

    def supports(self, case: Case) -> bool:
        return case.n_sets >= 2

    def fit(self, case: Case) -> list[Shape]:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib_set_diagrams import EulerDiagram

        order = sorted(case.sets)
        index = {name: i for i, name in enumerate(order)}

        # Build the membership-tuple -> size dict the package expects, covering
        # every populated region of the powerset.
        subset_sizes: dict[tuple[int, ...], float] = {}
        for size in range(1, case.n_sets + 1):
            for combo in combinations(order, size):
                value = case.regions.get("&".join(sorted(combo)), 0.0)
                key = tuple(1 if name in combo else 0 for name in order)
                subset_sizes[key] = value

        fig, ax = plt.subplots()
        try:
            d = EulerDiagram(
                subset_sizes,
                cost_function_objective=self.objective,
                ax=ax,
            )
            origins = d.origins  # (N, 2)
            radii = d.radii  # (N,)
            shapes = [
                Shape.circle(
                    name,
                    float(origins[index[name]][0]),
                    float(origins[index[name]][1]),
                    float(radii[index[name]]),
                )
                for name in order
            ]
        finally:
            plt.close(fig)
        return shapes
