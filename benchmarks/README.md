# Benchmark harness

Compares **eunoia** against the other area-proportional Euler/Venn *fitters* on
PyPI. Fitters are **grouped by the objective they minimize** and compared only
within a group, on that objective: the only apples-to-apples way to compare
optimizers that minimize different losses. The output drives the
[comparison report](../docs/comparison.md).

This directory is a developer tool. It is **not** part of the published `eunoia`
wheel, and the competitor packages live in an isolated dependency group.

## Run it

```bash
task benchmark          # installs the `benchmark` group, then runs
# or, manually:
uv sync --group benchmark
uv run --group benchmark python -m benchmarks.run
# iterate fast on a coarse grid:
uv run --group benchmark python -m benchmarks.run --quick
```

Outputs:

- `results/results.json`: machine-readable results (source of truth)
- `../docs/_generated/benchmark_table.md`: per-group accuracy tables
- `../docs/_generated/benchmark_timing.md`: wall-clock fit-time table
- `../docs/_static/benchmarks/objective_groups.png`: per-group accuracy charts
- `../docs/_static/benchmarks/timing.png`: wall-clock fit-time chart
- `../docs/_static/benchmarks/gallery.png`: fitted layouts, side by side

## How the comparison works

Each package minimizes a *different* loss, so the harness partitions the
comparison into objective groups (see `GROUPS` in `run.py`):

| Group | Members (configured to that objective) | Scored on |
|---|---|---|
| Sum of squared errors | eunoia `loss="sum_squared"` (circle + ellipse), set-diagrams `"squared"` | `stress` |
| Sum of absolute errors | eunoia `loss="sum_absolute"` (circle + ellipse), set-diagrams `"simple"` | `abs_error` |
| Logarithmic | matplotlib-venn (venn3 default), set-diagrams `"logarithmic"` | `log_error` |

eunoia and set-diagrams are configurable, so they appear in several groups;
matplotlib-venn is fixed (venn3's default is logarithmic L1). eunoia has no
logarithmic loss yet (tracked upstream in jolars/eunoia#96), so it sits out
that group.

- **`cases.py`**: the corpus. A curated subset of the eunoia Rust corpus
  (`crates/eunoia/src/test_utils/corpus.rs`, ported from eulerr's
  `test-reproducibility.R` and the eulerr issue tracker), spanning 2–6 sets with
  real datasets and several layouts that circles provably cannot fit exactly.
  All values are exclusive (per-region).
- **`adapters.py`**: `EunoiaAdapter(shape, loss=)` and
  `MatplotlibSetDiagramsAdapter(objective=)` are parameterized so each group can
  run them under the matching objective; `MatplotlibVennAdapter` is fixed.
- **`metrics.py`**: one **scale-invariant** score per objective family. Each
  *re-measures* the fitted diagram by rasterizing the shapes, then absorbs a
  single multiplicative scale on the fitted areas (every package draws at a
  different size) before computing the loss:
  - `stress`: squared family (venneuler's `Σ(f − β·t)² / Σf²`)
  - `abs_error`: absolute family (`min_b Σ|b·f − t| / Σ|t|`)
  - `log_error`: logarithmic family (`min_b Σ|log(1+b·f) − log(1+t)| / Σlog(1+t)`)

  The runner cross-checks the rasterized `stress` against eunoia's analytic
  `fit.stress` to confirm the estimator is faithful (they agree to grid
  resolution). Wall-clock `fit` time is recorded alongside accuracy.

## License note

`matplotlib-set-diagrams` is GPL-3.0 and `matplotlib-venn` is MIT. We only
*run* these packages here to measure their fit quality; no competitor source is
vendored into or redistributed by eunoia (which is MIT). The GPL dependency is
confined to the `benchmark` dependency group and never enters the published
wheel or the docs build.
