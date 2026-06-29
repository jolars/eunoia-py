---
file_format: mystnb
kernelspec:
  name: python3
---

# Quickstart

## A two-set fit

The simplest case: two sets with one overlap.

```{code-cell}
import eunoia as eu

fit = eu.euler({"A": 10, "B": 5, "A&B": 3})
print(fit)
```

```{code-cell}
fit.plot();
```

## Inclusive input

By default, values are interpreted as **exclusive** per-region areas. If your
numbers are total set sizes that include overlaps, pass `input="inclusive"` and
the Eunoia core converts internally:

```{code-cell}
fit = eu.euler({"A": 13, "B": 8, "A&B": 3}, input="inclusive")
fit.original_values, fit.fitted_values
```

## Membership lists

Instead of region areas, you can pass each set its members. Every element is
counted into the region of the sets it belongs to, giving **exclusive**
per-region counts:

```{code-cell}
fit = eu.euler(
    {
        "A": ["x", "y", "z"],
        "B": ["y", "z", "w"],
        "C": ["z", "w", "q"],
    }
)
fit.original_values
```

Elements are deduplicated within a set and stringified, so sets, tuples, and
non-string labels all work. `venn()` accepts the same shape (it only needs the
set names):

```{code-cell}
eu.venn({"A": ["x", "y"], "B": ["y", "z"]}).plot();
```

## DataFrames

A pandas or polars DataFrame (anything [narwhals](https://narwhals-dev.github.io/narwhals/)
supports) is read as a **membership matrix**: each column is a set, each row an
observation, and a truthy cell means that observation belongs to the set.
Columns must be boolean or `0`/`1` numeric:

```{code-cell}
import pandas as pd

df = pd.DataFrame(
    {
        "A": [1, 1, 0, 1, 0],
        "B": [0, 1, 1, 1, 0],
        "C": [0, 0, 1, 1, 1],
    }
)
eu.euler(df).original_values
```

Rows that belong to no set are dropped, and `venn(df)` takes the column names as
the set names. The same works for polars frames.

## NumPy arrays

A plain numpy boolean array is read as a membership matrix too (the matrix idiom
from eulerr): a 2D `(n_observations, n_sets)` array, or a 1D array for a single
set. An array carries no column names, so pass them with `names=` (otherwise
sets are named `A`, `B`, …):

```{code-cell}
import numpy as np

rng = np.random.default_rng(0)
arr = rng.random((100, 3)) < 0.4  # 3 boolean columns
eu.euler(arr, names=["A", "B", "C"]).original_values
```

Values may also be `0`/`1` numeric, and `NaN` cells count as non-members. This
scales to many columns: a 13-column boolean matrix is too many sets for a true
Venn diagram, but `eu.euler(arr, shape="circle")` still fits an
area-proportional Euler diagram.

## Three sets with ellipses

Ellipses are more flexible than circles and can fit many three-set arrangements
exactly:

```{code-cell}
fit = eu.euler(
    {"A": 2, "B": 2, "C": 2, "A&B": 1, "A&C": 1, "B&C": 1},
    shape="ellipse",
)
print(f"diag_error = {fit.diag_error:.3g}")
fit.plot(quantities="fitted");
```

## Custom styling

```{code-cell}
fit = eu.euler({"A": 10, "B": 7, "C": 8, "A&B": 3, "A&C": 4, "B&C": 2, "A&B&C": 1})
fit.plot(
    colors=["#e41a1c", "#377eb8", "#4daf4a"],
    quantities=True,
    edges={"linewidth": 1.5},
);
```

## Math text in labels

Set names are drawn as matplotlib text, so anything between `$…$` is rendered
with its [mathtext](https://matplotlib.org/stable/users/explain/text/mathtext.html)
engine. Use Greek letters, subscripts, or full TeX as set names and they carry
through to the labels and legend:

```{code-cell}
fit = eu.euler(
    {
        r"$\alpha$": 10,
        r"$\beta$": 7,
        r"$\gamma$": 8,
        r"$\alpha$&$\beta$": 3,
        r"$\alpha$&$\gamma$": 4,
        r"$\beta$&$\gamma$": 2,
        r"$\alpha$&$\beta$&$\gamma$": 1,
    }
)
fit.plot();
```

## Reproducibility

Pass a `seed` to fix the optimizer's RNG:

```{code-cell}
fit_a = eu.euler({"A": 10, "B": 5, "A&B": 3}, seed=42)
fit_b = eu.euler({"A": 10, "B": 5, "A&B": 3}, seed=42)
fit_a.diag_error == fit_b.diag_error
```
