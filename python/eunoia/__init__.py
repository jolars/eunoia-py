"""eunoia: area-proportional Euler and Venn diagrams.

Bindings to the eunoia Rust crate. Sister package to the R package eulerr.
"""

from __future__ import annotations

from eunoia._eunoia import EunoiaError
from eunoia._fit import euler
from eunoia._models import Circle, Ellipse, EulerFit, Point

__version__ = "0.0.1"

__all__ = [
    "Circle",
    "Ellipse",
    "EulerFit",
    "EunoiaError",
    "Point",
    "__version__",
    "euler",
]
