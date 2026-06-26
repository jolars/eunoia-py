---
file_format: mystnb
kernelspec:
  name: python3
---

# Eunoia

Python bindings for the [Eunoia](https://github.com/jolars/eunoia) Rust
library for area-proportional Euler and Venn diagrams. Sister package to the
R package [eulerr](https://github.com/jolars/eulerr).

```{toctree}
:maxdepth: 2
:hidden:
:caption: Contents

Home<self>
quickstart
gallery
comparison
api
```

An Euler diagram lays out one shape per set and sizes and positions them so
that every region's area is proportional to the quantity it represents. Eunoia
fits that layout with a fast Rust optimizer and draws it with matplotlib:

```{code-cell}
import eunoia as eu

fit = eu.euler(
    {"A": 10, "B": 7, "C": 8, "A&B": 3, "A&C": 4, "B&C": 2, "A&B&C": 1}
)
fit.plot(quantities=True);
```

## Why Eunoia

- **Area-proportional.** Region areas track your numbers, so the picture is
  quantitative, not just topological.
- **Several shapes.** Fit with circles, ellipses, squares, or rectangles.
  Ellipses handle relationships that circles cannot draw exactly.
- **Flexible input.** Pass per-region areas, inclusive set sizes, membership
  lists, or a pandas/polars DataFrame read as a membership matrix.
- **Venn diagrams too.** {func}`~eunoia.venn` draws topological Venn diagrams
  for one to five sets.
- **Matplotlib native.** Plots are ordinary `Axes`, so they slot into figures,
  subplots, and your usual styling.
- **Fast and typed.** The optimizer is Rust; the API is fully type-annotated
  and ships a `py.typed` marker.

## Install

```bash
pip install eunoia
```

Wheels are published for Linux, macOS, and Windows; no Rust toolchain is needed
to install.

## At a glance

The fit object holds the requested and fitted values and can plot itself:

```{code-cell}
fit = eu.euler({"A": 10, "B": 5, "A&B": 3})
print(fit)
fit.plot();
```

Swap in ellipses (or `"square"`, `"rectangle"`) for arrangements circles cannot
capture, and label regions with their fitted values:

```{code-cell}
fit = eu.euler(
    {"A": 2, "B": 2, "C": 2, "A&B": 1, "A&C": 1, "B&C": 1},
    shape="ellipse",
)
fit.plot(quantities="fitted");
```

## Next steps

- {doc}`quickstart` walks through the input formats and common options.
- {doc}`gallery` showcases shapes, styling, and Venn diagrams.
- {doc}`comparison` benchmarks Eunoia against related tools.
- {doc}`api` is the full reference.
