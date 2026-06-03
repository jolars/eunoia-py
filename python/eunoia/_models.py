"""Data classes returned by `eunoia.euler`."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar

if TYPE_CHECKING:
    from matplotlib.axes import Axes


@dataclass(frozen=True)
class Point:
    """A 2D point."""

    x: float
    y: float


@dataclass(frozen=True)
class Circle:
    """A fitted circle for one input set."""

    set: str
    center: Point
    radius: float


@dataclass(frozen=True)
class Ellipse:
    """A fitted ellipse for one input set."""

    set: str
    center: Point
    semi_major: float
    semi_minor: float
    rotation: float


@dataclass(frozen=True)
class Square:
    """A fitted axis-aligned square for one input set."""

    set: str
    center: Point
    side: float


@dataclass(frozen=True)
class Rectangle:
    """A fitted axis-aligned rectangle for one input set."""

    set: str
    center: Point
    width: float
    height: float


@dataclass(frozen=True)
class Container:
    """The fitted universe box drawn around a diagram fit with ``complement``.

    The container's area minus the (clipped) union of the shapes equals the
    requested complement area. The leftover region inside the container but
    outside every set is the *complement region*, keyed under the empty
    string in the plot data.
    """

    center: Point
    width: float
    height: float


S = TypeVar("S", Circle, Ellipse, Square, Rectangle)


@dataclass(frozen=True, repr=False)
class EulerFit(Generic[S]):
    """Result of fitting an area-proportional Euler diagram.

    Attributes
    ----------
    shapes:
        Tuple of fitted shapes (one per input set), in the order the sets
        were first encountered in the input.
    original_values:
        The values originally passed in. Keys are canonical (sorted) form.
    fitted_values:
        The fitted areas, expressed in the same scale as ``original_values``
        (exclusive or inclusive, depending on ``input``).
    residuals:
        ``original_values - fitted_values`` per region.
    region_error:
        Per-region error (eunoia core's region_error metric, always in
        per-region exclusive form).
    diag_error:
        Maximum region error (eulerAPE-style worst-case metric).
    stress:
        venneuler-style stress metric.
    loss:
        Final value of the objective the optimizer minimized.
    container:
        The fitted universe box, when the diagram was fit with
        ``complement``; otherwise ``None``.
    """

    shapes: tuple[S, ...]
    original_values: dict[str, float]
    fitted_values: dict[str, float]
    residuals: dict[str, float]
    region_error: dict[str, float]
    diag_error: float
    stress: float
    loss: float
    container: Container | None = None
    plot_data: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __repr__(self) -> str:
        shape_kind = (
            type(self.shapes[0]).__name__.lower() + "s" if self.shapes else "shapes"
        )
        n = len(self.shapes)
        header = (
            f"EulerFit ({n} {shape_kind}, "
            f"diag_error={self.diag_error:.4g}, "
            f"stress={self.stress:.4g}, "
            f"loss={self.loss:.4g})\n"
        )
        region_labels = list(self.original_values)
        if not region_labels:
            return header.rstrip()
        label_w = max(len(k) for k in region_labels)
        col_w = 12
        cols = ("original", "fitted", "residual", "regionError")
        head_row = "  " + " " * label_w + "".join(c.rjust(col_w) for c in cols) + "\n"
        body = ""
        for k in region_labels:
            body += "  " + k.ljust(label_w)
            body += f"{self.original_values[k]:>{col_w}.4g}"
            body += f"{self.fitted_values[k]:>{col_w}.4g}"
            body += f"{self.residuals[k]:>{col_w}.4g}"
            body += f"{self.region_error.get(k, 0.0):>{col_w}.4g}"
            body += "\n"
        return header + head_row + body.rstrip("\n")

    def plot(
        self,
        *,
        ax: Axes | None = None,
        colors: Sequence[Any] | dict[str, Any] | None = None,
        fills: dict[str, dict[str, Any]] | None = None,
        edges: dict[str, Any] | None = None,
        labels: bool = True,
        quantities: bool | Literal["original", "fitted"] = False,
        complement: dict[str, Any] | None = None,
    ) -> Axes:
        """Render the fitted diagram with matplotlib.

        Parameters
        ----------
        ax:
            Existing matplotlib Axes to draw into. If ``None``, a new figure
            and axes are created via ``plt.subplots()``.
        colors:
            Per-set colors. Either a sequence of colors (one per set, in
            shape order) or a dict mapping set name to color. ``None`` uses
            matplotlib's ``tab10`` palette.
        fills:
            Per-region fill style overrides. Maps canonical region key to a
            dict of ``PathPatch`` keyword arguments.
        edges:
            Edge (set boundary) style overrides — a dict of ``PathPatch``
            keyword arguments applied to every set outline.
        labels:
            Whether to draw set name labels at each set's anchor.
        quantities:
            Show fitted/original values per region. ``True`` and
            ``"original"`` show the input values; ``"fitted"`` shows the
            fitted values. ``False`` (default) shows nothing.
        complement:
            Style overrides (``Rectangle`` patch kwargs) for the universe
            container box, drawn only when the fit has a ``container``.
            Ignored otherwise.

        Returns
        -------
        matplotlib.axes.Axes
            The axes the diagram was drawn into.
        """
        from eunoia._plot import render

        return render(
            self,
            ax=ax,
            colors=colors,
            fills=fills,
            edges=edges,
            labels=labels,
            quantities=quantities,
            complement=complement,
        )


class VennFit(EulerFit[S]):
    """Result of laying out a (non-proportional) Venn diagram.

    Shares :class:`EulerFit`'s structure and ``plot()`` method, but the
    diagram is *topological*: every set intersection is drawn regardless of
    its area, so the area-proportional error metrics are not meaningful and
    are left at zero. ``fitted_values`` holds the geometric area of each
    region; ``original_values`` is empty (a Venn layout has no requested
    areas).
    """

    def __repr__(self) -> str:
        names = [s.set for s in self.shapes]
        kind = type(self.shapes[0]).__name__.lower() if self.shapes else "shape"
        return f"VennFit ({len(names)} sets [{kind}]: {', '.join(names)})"
