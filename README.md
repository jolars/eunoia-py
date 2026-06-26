# Eunoia <img src='https://raw.githubusercontent.com/jolars/eunoia-py/refs/heads/main/docs/_static/logo.png' align="right" width="139" />

[![CI](https://github.com/jolars/eunoia-py/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jolars/eunoia-py/actions/workflows/ci.yml)
[![PyPI
version](https://badge.fury.io/py/eunoia.svg)](https://badge.fury.io/py/eunoia)

Python bindings for the [Eunoia](https://eunoia.bz), a Rust library for fitting
area-proportional Euler and Venn diagrams. Sister package to the R package
[eulerr](https://github.com/jolars/eulerr).

![Euler circles, ellipses, and a Venn diagram fitted with
Eunoia](https://raw.githubusercontent.com/jolars/eunoia-py/refs/heads/main/docs/_static/hero.png)

## Install

```bash
pip install eunoia
```

## Quickstart

```python
import eunoia as eu
import matplotlib.pyplot as plt

# Disjoint (per-region) input is the default.
fit = eu.euler({"A": 10, "B": 5, "A&B": 3})
print(fit)
# EulerFit (2 circles, diag_error=2.776e-17, stress=5.887e-33, loss=5.887e-33)
#                  original      fitted    residual regionError
#   A                    10          10           0           0
#   B                     5           5           0           0
#   A&B                   3           3   8.882e-16   2.776e-17

fit.plot()
plt.show()
```

### Inclusive Input

If your numbers are set sizes that already include their overlaps, pass
`input="inclusive"` and the Eunoia core handles the inclusion-exclusion
conversion:

```python
fit = eu.euler({"A": 13, "B": 8, "A&B": 3}, input="inclusive")
```

### Ellipses

Ellipses are more flexible than circles and fit many three-set arrangements
exactly:

```python
fit = eu.euler(
    {"A": 2, "B": 2, "C": 2, "A&B": 1, "A&C": 1, "B&C": 1},
    shape="ellipse",
)
print(fit.diag_error)  # ~1e-14
fit.plot(quantities=True)
```

### Plot Styling

```python
fit.plot(
    colors=["#e41a1c", "#377eb8", "#4daf4a"],  # per-set
    quantities="fitted",  # show fitted areas at region anchors
    labels=True,  # set names at set anchors
    edges={"linewidth": 1.5},
)
```

### Venn Diagrams

`venn()` draws a topological (not area-proportional) diagram in which every
intersection is shown, regardless of its size. It accepts a set count, a list of
names, or a `{combination: area}` mapping:

```python
fit = eu.venn(["A", "B", "C"])
fit.plot(quantities=True)
```

Ellipse Venn diagrams support 1-5 sets; circle, square, and rectangle support
1-3.

### Other Shapes

Besides `"circle"` (default) and `"ellipse"`, `euler()` and `venn()` accept
`shape="square"` and `shape="rectangle"`.

### Global Plotting Options

`eunoia.options(...)` sets defaults for every subsequent plot (colors, edges,
labels, quantities, legend, complement). Called with no arguments it returns a
snapshot; called with category kwargs it returns a context manager that restores
the previous state on exit. `reset_options()` reverts to the built-ins.

## Public API

  | Function/class                                 | Purpose                                            |
  | ---------------------------------------------- | -------------------------------------------------- |
  | `eunoia.euler(values, …)`                      | Fit an area-proportional diagram from a dict       |
  | `eunoia.venn(sets, …)`                         | Fit a topological Venn diagram                     |
  | `eunoia.EulerFit`/`VennFit`                    | Result classes with shapes, fitted values, metrics |
  | `eunoia.Circle`/`Ellipse`                      | Per-set fitted shape (circle or ellipse)           |
  | `eunoia.Square`/`Rectangle`                    | Per-set fitted shape (square or rectangle)         |
  | `eunoia.Container`                             | Universe box drawn behind a `complement=` diagram  |
  | `eunoia.Point`                                 | 2D point                                           |
  | `eunoia.options`/`get_options`/`reset_options` | Global plotting defaults                           |
  | `eunoia.EunoiaError`                           | Base error type (subclass of `ValueError`)         |

## Ecosystem

This package is the Python member of the [Eunoia](https://eunoia.bz) family. The
same Rust core powers bindings in several other languages:

  | Project                                            | Language             | Distribution                                                          |
  | -------------------------------------------------- | -------------------- | --------------------------------------------------------------------- |
  | [eunoia](https://github.com/jolars/eunoia)         | Rust (core)          | [crates.io](https://crates.io/crates/eunoia)                          |
  | [@jolars/eunoia](https://github.com/jolars/eunoia) | JavaScript/TS (WASM) | [npm](https://www.npmjs.com/package/@jolars/eunoia)                   |
  | [Eunoia.jl](https://github.com/jolars/Eunoia.jl)   | Julia                | [Julia Hub](https://platform.juliahub.com/ui/Packages/General/Eunoia) |
  | [eulerr](https://github.com/jolars/eulerr)         | R (original)         | [CRAN](https://cran.r-project.org/package=eulerr)                     |

Narrative documentation for the whole family lives at
[eunoia.bz/docs/](https://eunoia.bz/docs/); the Rust API reference is at
[docs.rs/eunoia](https://docs.rs/eunoia/).

## License

[MIT](LICENSE)
