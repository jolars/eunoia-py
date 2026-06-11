# Eunoia <img src='https://raw.githubusercontent.com/jolars/eunoia-py/refs/heads/main/docs/_static/logo.png' align="right" width="139" />

Python bindings for the [Eunoia](https://github.com/jolars/eunoia) Rust library
for fitting area-proportional Euler and Venn diagrams. Sister package to the R
package [eulerr](https://github.com/jolars/eulerr).

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

### Inclusive input

If your numbers are set sizes that already include their overlaps, pass
`input="inclusive"` and the eunoia core handles the inclusion-exclusion
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

### Plot styling

```python
fit.plot(
    colors=["#e41a1c", "#377eb8", "#4daf4a"],   # per-set
    quantities="fitted",                          # show fitted areas at region anchors
    labels=True,                                  # set names at set anchors
    edges={"linewidth": 1.5},
)
```

## Public API

  | Function / class          | Purpose                                          |
  | ------------------------- | ------------------------------------------------ |
  | `eunoia.euler(values, …)` | Fit a diagram from a `{combination: area}` dict  |
  | `eunoia.EulerFit`         | Result class with shapes, fitted values, metrics |
  | `eunoia.Circle`/`Ellipse` | Per-set fitted shape                             |
  | `eunoia.Point`            | 2D point                                         |
  | `eunoia.EunoiaError`      | Base error type (subclass of `ValueError`)       |

## License

[MIT](LICENSE)
