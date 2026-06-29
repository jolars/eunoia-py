# Comparison with other Python packages

This page positions eunoia among the other Python packages for set-membership
diagrams. It has two halves: a **qualitative map** of the landscape, and a
**quantitative benchmark** of the packages that actually solve the same problem
eunoia does: fitting *area-proportional* Euler diagrams.

We deliberately leave out [eulerr](https://github.com/jolars/eulerr): it is
eunoia's sibling for R, built on the same Rust core, so comparing the two would
measure nothing about the Python ecosystem.

## The landscape

"Draw a Venn diagram" covers several genuinely different problems, and the
Python packages split along those lines. Only the first group is directly
comparable to eunoia.

```{list-table}
:header-rows: 1
:widths: 22 16 10 16 18 18

* - Package
  - Area-proportional
  - Max sets
  - Shapes
  - Method
  - License
* - **eunoia**
  - yes
  - arbitrary
  - circle, ellipse, square, rectangle
  - numerical optimization (Rust core); reports residuals + goodness-of-fit
  - MIT
* - [matplotlib-set-diagrams](https://github.com/paulbrodersen/matplotlib_set_diagrams)
  - yes
  - arbitrary
  - circles
  - optimization-based layout
  - GPL-3
* - [matplotlib-venn](https://github.com/konstantint/matplotlib-venn)
  - yes
  - 3
  - circles
  - closed-form (2 sets); cost-based layout (3 sets)
  - MIT
* - [BioVenn](https://pypi.org/project/BioVenn/)
  - yes
  - 3
  - circles
  - area-proportional, with biological ID mapping
  - MIT
* - [vennplot](https://pypi.org/project/vennplot/)
  - yes
  - 3
  - circles or balls (2D + 3D)
  - area-proportional
  - MIT
* - [supervenn](https://github.com/gecko984/supervenn)
  - yes (exact)
  - many
  - bars or chunks
  - splits sets into parts; not an Euler diagram
  - MIT
* - [pyvenn/venn](https://github.com/tctianchi/pyvenn)
  - no
  - 6
  - fixed templates
  - static shapes; only labels move
  - MIT
* - [matplotlib-subsets](https://pypi.org/project/matplotlib-subsets/)
  - no
  - —
  - nested rectangles
  - set hierarchy, not an Euler layout
  - MIT
* - [eule](https://github.com/quivero/eule)
  - n/a
  - arbitrary
  - none
  - set algebra only; computes region sizes, draws nothing
  - MIT
```

Reading the table:

- **Genuine area-proportional fitters** (`matplotlib-set-diagrams` and
  `matplotlib-venn`) are the only packages that solve eunoia's problem, so
  they are the ones we benchmark below. `BioVenn` and `vennplot` are also
  area-proportional but capped at three circles, so they add little signal
  beyond `matplotlib-venn`.
- **A different representation**: `supervenn` is exactly proportional but draws
  bar/chunk strips rather than overlapping shapes. It is a great tool, just not
  an Euler diagram, so it can't be scored on the same geometry metric.
- **Not area-proportional**: `pyvenn`/`venn` and `matplotlib-subsets` use fixed
  templates or nested rectangles; the picture does not encode the set sizes.
- **Complementary, not a competitor**: `eule` computes the disjoint region
  sizes from membership and draws nothing. It is the kind of preprocessing that
  *feeds* a fitter; eunoia does the same thing internally when you pass it
  membership lists (`eu.euler({"A": [...], "B": [...]})`), a pandas/polars
  DataFrame, or a numpy boolean array used as a membership matrix.

## Benchmark

### Why the comparison is grouped by objective

Comparing area-proportional fitters is subtle because **they do not all minimize
the same thing**, and scoring a fitter on an objective it never targeted is
unfair. Each package minimizes a different loss:

| Package and config | Minimizes |
|---|---|
| `matplotlib-venn` `venn2` | closed-form exact |
| `matplotlib-venn` `venn3` (default) | Σ\|log(1+fitted) − log(1+target)\| (logarithmic L1) |
| `matplotlib-set-diagrams` | a selectable cost: `"squared"` (Σ(f−t)²), `"simple"` (Σ\|f−t\|), `"logarithmic"`, `"relative"`, `"inverse"` |
| **eunoia** | a selectable `loss=`: `"sum_squared"`, `"sum_absolute"`, `"log_sum_absolute"`, `"stress"`, `"diag_error"`, … |

So the only fair comparison is **within an objective**: pick a loss family, run
the packages that can minimize it (configuring each to do so), and score them on
that same loss. eunoia and `matplotlib-set-diagrams` are configurable, so they
appear in several groups; `matplotlib-venn` is fixed, so it appears only in the
logarithmic group its `venn3` default defines.

Each group is scored on a **scale-invariant** version of its loss: a single
multiplicative scale on the fitted areas is absorbed, because each package draws
its diagram at an arbitrary size. For the squared family this scale-invariant
score is exactly venneuler/eulerr **`stress`**; the absolute and logarithmic
families use the analogous scale-invariant L1 and log-L1.

Of these packages, only eunoia reports any goodness-of-fit number itself; the
harness re-measures every fitter identically (rasterizing the returned shapes)
and validates that eunoia's rasterized `stress` matches the value eunoia
computes analytically (they agree to grid resolution).

The specifications are a curated subset of the eunoia Rust corpus
(`crates/eunoia/src/test_utils/corpus.rs`), itself ported from
[eulerr's reproducibility tests](https://github.com/jolars/eulerr) and real
datasets from the eulerr issue tracker. They span 2 to 6 sets and include
layouts circles provably cannot fit exactly, plus real biology and kinase data.
The full harness lives in
[`benchmarks/`](https://github.com/jolars/eunoia-py/tree/main/benchmarks);
reproduce with `task benchmark`.

### Accuracy, grouped by objective

```{include} _generated/benchmark_table.md
```

```{figure} _static/benchmarks/objective_groups.png
:alt: Grouped bar charts, one panel per objective, log scale.
:width: 100%

Each panel is one objective; bars are the scale-invariant score for that
objective (lower is better, log scale). Within a panel every fitter minimized
the same loss, so the comparison is apples-to-apples. Bars are absent where a
package cannot represent that set count.
```

Three things stand out:

1. **Matched on the same objective, eunoia's circles beat the other circle
   fitters, in every group.** In the squared-error group eunoia's circles reach
   a lower `stress` than `matplotlib-set-diagrams("squared")` on every case,
   often by an order of magnitude on the harder specs; the absolute-error group
   tells the same story with `matplotlib-set-diagrams("simple")`. Most tellingly,
   in the **logarithmic** group (`matplotlib-venn`'s *own* default objective),
   eunoia's circles beat both `matplotlib-venn` and
   `matplotlib-set-diagrams("logarithmic")` on every case (the two competitors
   are neck-and-neck with each other, as expected since they minimize the same
   thing). Given the same loss, eunoia's optimizer simply lands closer.

2. **Ellipses then win outright.** eunoia's ellipses are the best fit in every
   group, on every case, reaching essentially zero error under the squared loss,
   and the lowest error by a wide margin under the absolute and logarithmic ones.
   This is geometry no circle-only package can match.

3. **`matplotlib-venn` is fixed and capped.** It offers no choice of objective
   (its `venn3` is a fixed logarithmic layout) and cannot draw four or more sets.
   `matplotlib-set-diagrams` scales to any set count and is configurable, but
   loses to eunoia within every shared objective.

eunoia only joined the logarithmic group because the core gained a
`"log_sum_absolute"` loss in 1.1 (closing
[jolars/eunoia#96](https://github.com/jolars/eunoia/issues/96)); choosing the
objective to match the data is itself part of what eunoia offers here.

### Wall-clock fit time

Accuracy is not the whole story; here is end-to-end `fit` time (one
representative configuration per package).

```{include} _generated/benchmark_timing.md
```

```{figure} _static/benchmarks/timing.png
:alt: Grouped bar chart of median fit time per case, log scale.
:width: 100%

Median fit time per case (log scale), each package under the same configuration
as the gallery. `matplotlib-venn` is fastest but capped at three sets; eunoia
and `matplotlib-set-diagrams` are broadly comparable, both taking up to a few
seconds on the hardest high-set specs. (Separately, eunoia's non-smooth losses,
`"sum_absolute"` and `"log_sum_absolute"`, are markedly slower to optimize than
the smooth `"sum_squared"` default shown here.)
```

### Fitted layouts

```{figure} _static/benchmarks/gallery.png
:alt: Grid of fitted layouts, one column per fitter, one row per case.
:width: 100%

Fitted layouts on representative corpus cases (eunoia under its default squared
loss; set-diagrams under `"squared"`). The four-, five-, and six-set rows show
`matplotlib-venn` dropping out, and eunoia's ellipse column staying faithful
where the circle columns visibly distort.
```

## When to reach for what

- **eunoia** when you want the most faithful diagram, especially with ellipses,
  with four or more sets, when you need to choose the objective (`loss=`) to suit
  your data, or when you need the residuals and goodness-of-fit numbers to judge
  whether the diagram can be trusted at all. MIT-licensed.
- **matplotlib-venn** for a quick, dependency-light two- or three-circle Venn
  where exactness is not critical. Also MIT.
- **matplotlib-set-diagrams** if you specifically want its word-cloud subset
  labels and are comfortable with GPL-3, and be prepared to try its
  `cost_function_objective` options, since the default (`"inverse"`) fits
  area-dominated diagrams poorly.
- **supervenn** when exact proportionality matters more than the Euler-diagram
  shape, e.g. many sets with complex overlaps.

## Reproducing

```bash
task benchmark
# or
uv sync --group benchmark
uv run --group benchmark python -m benchmarks.run
```

The competitor packages are confined to an isolated `benchmark` dependency
group and are never part of the published `eunoia` wheel. We only run them to
measure fit quality; `matplotlib-set-diagrams` is GPL-3, so no competitor source
is vendored into or redistributed by eunoia.
```{note}
The numbers and figures on this page are committed to the repo and refreshed by
running the benchmark; the documentation build itself does **not** install or
execute the competitor packages.
```
