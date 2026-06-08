"""eunoia: area-proportional Euler and Venn diagrams.

Bindings to the eunoia Rust crate. Sister package to the R package eulerr.
"""

from __future__ import annotations

from eunoia._eunoia import EunoiaError
from eunoia._fit import euler
from eunoia._models import (
    Circle,
    Container,
    Ellipse,
    EulerFit,
    Point,
    Rectangle,
    Square,
    VennFit,
)
from eunoia._options import get_options, options, reset_options
from eunoia._venn import venn

__version__ = "0.1.0"

__all__ = [
    "Circle",
    "Container",
    "Ellipse",
    "EulerFit",
    "EunoiaError",
    "Point",
    "Rectangle",
    "Square",
    "VennFit",
    "__version__",
    "euler",
    "get_options",
    "options",
    "reset_options",
    "venn",
]
