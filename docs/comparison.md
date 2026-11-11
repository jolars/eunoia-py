# Comparison with other Python packages

Python packages for set-membership diagrams differ in what they represent and
how they fit layouts. This page compares their approaches and benchmarks the
packages that, like eunoia, fit *area-proportional* Euler diagrams.

## The landscape

"Draw a Venn diagram" can mean several different things. Some packages fit
area-proportional diagrams, others use fixed layouts, and others compute set
sizes without drawing a diagram. The area-proportional fitters are directly
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
* - eunoia
  - yes
  - arbitrary
  - circle, ellipse, square, rectangle
  - numerical optimization (Rust core); reports residuals and goodness of fit
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
  - circles or balls (2D and 3D)
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

The packages fall into four groups:

- *Area-proportional fitters*: matplotlib-set-diagrams, matplotlib-venn,
  BioVenn, and vennplot solve the same problem as eunoia. We benchmark the first
  two below. BioVenn and vennplot are capped at three circles, so they add
  little to the comparison beyond matplotlib-venn.
- *Alternative representations*: supervenn is exactly proportional but
  represents sets as strips of bars or chunks. These are not Euler diagrams, so
  the same geometric metric does not apply.
- *Diagrams without proportional areas*: pyvenn/venn and matplotlib-subsets use
  fixed templates or nested rectangles. Their diagrams do not encode set sizes
  through area.
- *Set algebra*: eule computes disjoint region sizes from membership without
  drawing a diagram. Its output can serve as input to a fitter. eunoia performs
  the same preprocessing internally when you pass it membership lists
  (`eu.euler({"A": [...], "B": [...]})`), a pandas or Polars DataFrame, or a
  NumPy boolean array used as a membership matrix.

## Benchmark

Across the benchmark cases, eunoia's circles achieve lower error than the other
circle fitters within each shared objective. Its ellipses achieve the lowest
error. The figures below compare fit accuracy and fit time, followed by
representative layouts.

### Accuracy, grouped by objective

Each figure compares fitters configured to minimize the same loss. Lower scores
indicate a closer fit. The [methodology](#comparison-methods) explains the
scoring, and the [detailed results](#comparison-results) give the scores for
every case.

#### Squared error

Under the squared loss, eunoia's circles reach a lower `stress` than
matplotlib-set-diagrams on every case, often by an order of magnitude on the
harder specifications. eunoia's ellipses reach essentially zero error.

```{figure} _static/benchmarks/objective_squared.png
:alt: Horizontal grouped bar chart of stress by case for fitters minimizing squared error.
:width: 100%

Scale-invariant squared error (`stress`, log scale; lower is better). eunoia
uses `loss="sum_squared"`, and matplotlib-set-diagrams uses `"squared"`.
```

#### Absolute error

The same advantage appears under the absolute loss: eunoia's circles achieve
lower error than matplotlib-set-diagrams on every case. Its ellipses have the
lowest error by a wide margin.

```{figure} _static/benchmarks/objective_absolute.png
:alt: Horizontal grouped bar chart of absolute error by case for fitters minimizing absolute error.
:width: 100%

Scale-invariant absolute error (log scale; lower is better). eunoia uses
`loss="sum_absolute"`, and matplotlib-set-diagrams uses `"simple"`.
```

#### Logarithmic error

This group matches matplotlib-venn's default objective. eunoia's circles achieve
lower error than both matplotlib-venn and matplotlib-set-diagrams on every case,
while its ellipses achieve the lowest error by a wide margin. The two
competitors produce similar scores. matplotlib-venn supports at most three sets,
so it has no bars for the larger cases.

```{figure} _static/benchmarks/objective_logarithmic.png
:alt: Horizontal grouped bar chart of logarithmic error by case, with matplotlib-venn limited to three sets.
:width: 100%

Scale-invariant logarithmic error (log scale; lower is better). eunoia uses
`loss="log_sum_absolute"`, matplotlib-set-diagrams uses `"logarithmic"`, and
matplotlib-venn uses its default objective. Missing bars mark unsupported set
counts.
```

The core added `"log_sum_absolute"` in version 1.1 (closing
[jolars/eunoia#96](https://github.com/jolars/eunoia/issues/96)), allowing eunoia
to take part in this group. The choice of loss lets users match the objective to
their data.

### Wall-clock fit time

The benchmark also measures end-to-end `fit` time using one representative
configuration per package, matching the gallery below. matplotlib-venn is
fastest but supports at most three sets. eunoia and matplotlib-set-diagrams have
broadly comparable fit times, both taking up to a few seconds on the hardest
specifications with many sets.

eunoia's non-smooth losses, `"sum_absolute"` and `"log_sum_absolute"`, are
markedly slower to optimize than the smooth `"sum_squared"` default shown here.

```{figure} _static/benchmarks/timing.png
:alt: Horizontal grouped bar chart of median fit time per case, log scale.
:width: 100%

Median fit time per case (log scale; lower is faster). Each package uses the
same configuration as in the gallery. Missing bars mark unsupported set counts.
```

### Fitted layouts

The layouts below show how fit errors affect the diagrams. eunoia's ellipses
preserve the target areas where the circle layouts visibly distort them. Each
column shows one fitter, and each row shows one benchmark case.

```{figure} _static/benchmarks/gallery.png
:alt: Grid of fitted layouts, one column per fitter, one row per case.
:width: 100%

Fitted layouts for representative corpus cases, with eunoia using its default
squared loss and matplotlib-set-diagrams using `"squared"`. Shaded panels mark
set counts that matplotlib-venn does not support.
```

(comparison-methods)=
### How the comparison works

Area-proportional fitters *do not all minimize the same loss*. Scoring a fitter
on a loss it was not configured to minimize would make the comparison unfair.
The packages use the following objectives, where $f_i$ and $t_i$ are the fitted
and target areas of region $i$:

  | Package and config                | Minimizes                                                                                                                                         |
  | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
  | matplotlib-venn `venn2`           | closed-form exact                                                                                                                                 |
  | matplotlib-venn `venn3` (default) | $\sum_i \lvert\log(1+f_i) - \log(1+t_i)\rvert$ (logarithmic $L_1$)                                                                                |
  | matplotlib-set-diagrams           | a selectable cost: `"squared"` ($\sum_i (f_i - t_i)^2$), `"simple"` ($\sum_i \lvert f_i - t_i\rvert$), `"logarithmic"`, `"relative"`, `"inverse"` |
  | eunoia                            | a selectable `loss=`: `"sum_squared"`, `"sum_absolute"`, `"log_sum_absolute"`, `"stress"`, `"diag_error"`, …                                      |

The only fair comparison is *within an objective*: choose a loss family,
configure each package that supports it to minimize that loss, and score them on
the same loss. eunoia and matplotlib-set-diagrams are configurable, so they
appear in several groups. matplotlib-venn has a fixed objective, so it appears
only in the logarithmic group, which matches its `venn3` default.

Each group is scored on a *scale-invariant* version of its loss. The score
accounts for a single multiplicative scale factor on the fitted areas because
each package draws its diagram at an arbitrary size. For the squared-error
family, this score is exactly the *`stress`* used by venneuler and eulerr. The
absolute and logarithmic families use the analogous scale-invariant $L_1$ and
logarithmic $L_1$ scores.

Of these packages, only eunoia reports a goodness-of-fit measure itself. The
benchmark harness measures every fitter in the same way by rasterizing the
returned shapes. It also checks that eunoia's rasterized `stress` matches the
value eunoia computes analytically. The two agree to the resolution of the grid.

The benchmark specifications are a curated subset of the eunoia Rust corpus,
which was ported from [eulerr's reproducibility
tests](https://github.com/jolars/eulerr) and real datasets from the eulerr issue
tracker. They span 2 to 6 sets and include layouts that circles provably cannot
fit exactly, as well as real biology and kinase data. The full harness is in
[`benchmarks/`](https://github.com/jolars/eunoia-py/tree/main/benchmarks).

(comparison-results)=
### Detailed results

Expand the tables below to inspect the accuracy scores and fit times for every
benchmark case.

<details>
<summary>View accuracy results</summary>

````{container}
```{include} _generated/benchmark_table.md
```
````

</details>

<details>
<summary>View timing results</summary>

```{include} _generated/benchmark_timing.md
```

</details>

## Reproducing

See the [benchmark
README](https://github.com/jolars/eunoia-py/blob/main/benchmarks/README.md) for
setup instructions and commands to reproduce the results.

```{note}
The numbers and figures on this page are committed to the repository and updated
by running the benchmark. The documentation build itself does *not* install or
execute the competitor packages.
```
