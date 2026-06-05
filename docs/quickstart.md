---
file_format: mystnb
kernelspec:
  name: python3
---

# Quickstart

```{code-cell} ipython3
:tags: [remove-cell]

import matplotlib
matplotlib.use("Agg")
```

## A two-set fit

The simplest case: two sets with one overlap.

```{code-cell} ipython3
import eunoia as eu

fit = eu.euler({"A": 10, "B": 5, "A&B": 3})
print(fit)
```

```{code-cell} ipython3
fit.plot();
```

## Inclusive input

By default, values are interpreted as **exclusive** per-region areas. If
your numbers are total set sizes that include overlaps, pass
`input="inclusive"` and the eunoia core converts internally:

```{code-cell} ipython3
fit = eu.euler({"A": 13, "B": 8, "A&B": 3}, input="inclusive")
fit.original_values, fit.fitted_values
```

## Membership lists

Instead of region areas, you can pass each set its members. Every element is
counted into the region of the sets it belongs to, giving **exclusive**
per-region counts:

```{code-cell} ipython3
fit = eu.euler(
    {
        "A": ["x", "y", "z"],
        "B": ["y", "z", "w"],
        "C": ["z", "w", "q"],
    }
)
fit.original_values
```

Elements are deduplicated within a set and stringified, so sets, tuples and
non-string labels all work. `venn()` accepts the same shape (it only needs the
set names):

```{code-cell} ipython3
eu.venn({"A": ["x", "y"], "B": ["y", "z"]});
```

## Three sets with ellipses

Ellipses are more flexible than circles and can fit many three-set
arrangements exactly:

```{code-cell} ipython3
fit = eu.euler(
    {"A": 2, "B": 2, "C": 2, "A&B": 1, "A&C": 1, "B&C": 1},
    shape="ellipse",
)
print(f"diag_error = {fit.diag_error:.3g}")
fit.plot(quantities="fitted");
```

## Custom styling

```{code-cell} ipython3
fit = eu.euler({"A": 10, "B": 7, "C": 8, "A&B": 3, "A&C": 4, "B&C": 2, "A&B&C": 1})
fit.plot(
    colors=["#e41a1c", "#377eb8", "#4daf4a"],
    quantities=True,
    edges={"linewidth": 1.5},
);
```

## Reproducibility

Pass a `seed` to fix the optimizer's RNG:

```{code-cell} ipython3
fit_a = eu.euler({"A": 10, "B": 5, "A&B": 3}, seed=42)
fit_b = eu.euler({"A": 10, "B": 5, "A&B": 3}, seed=42)
fit_a.diag_error == fit_b.diag_error
```
