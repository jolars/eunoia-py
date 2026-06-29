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

`euler()` also accepts inclusive counts, DataFrames, and NumPy arrays;
`shape=` switches between circles, ellipses, squares, and rectangles;
`venn()` draws topological diagrams; and `eunoia.options(...)` sets global
plotting defaults. See the documentation for the full API.

## Documentation

Full documentation, including narrative guides and the API reference, lives at
[jolars.github.io/eunoia-py](https://jolars.github.io/eunoia-py).

## Ecosystem

This package is the Python member of the [Eunoia](https://eunoia.bz) family. The
same Rust core powers bindings in several other languages:

  | Language   | Package                                                                                                               | Install                      |
  | ---------- | --------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
  | Rust       | [`eunoia`](https://crates.io/crates/eunoia) ([repo](https://github.com/jolars/eunoia))                                | `cargo add eunoia`           |
  | JavaScript | [`@jolars/eunoia`](https://www.npmjs.com/package/@jolars/eunoia) ([repo](https://github.com/jolars/eunoia))           | `npm install @jolars/eunoia` |
  | Julia      | [`Eunoia.jl`](https://platform.juliahub.com/ui/Packages/General/Eunoia) ([repo](https://github.com/jolars/Eunoia.jl)) | `] add Eunoia`               |
  | R          | [`eulerr`](https://cran.r-project.org/package=eulerr) ([repo](https://github.com/jolars/eulerr))                      | `install.packages("eulerr")` |

Documentation for the whole family lives at
[eunoia.bz/docs/](https://eunoia.bz/docs/); the Rust API reference is at
[docs.rs/eunoia](https://docs.rs/eunoia/).

## License

[MIT](LICENSE)
