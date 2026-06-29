# Agent guide

Notes for AI agents working on this repo. Keep it short: code is the source
of truth, and this file just points at things and flags gotchas.

## What this is

Python wrapper for the [`eunoia`](https://github.com/jolars/eunoia) Rust crate
(area-proportional Euler/Venn diagrams). PyPI name `eunoia`, sister package to
the R package `eulerr`. Built with PyO3 + maturin, abi3-py311 (one wheel per
platform covers Python 3.11--3.14).

## Working in the repo

The dev environment is a `devenv` shell (already active) that puts `cargo`
(Rust 1.88), `maturin`, `pytest`, etc. on `PATH`; run commands directly. It also
auto-runs `uv sync --all-extras --all-groups`, so the venv at
`.devenv/state/venv` has matplotlib, numpy, mypy, pyright, and the docs deps.

```bash
maturin develop --uv          # build Rust ext + install editable
pytest                        # run tests
ruff check python tests docs
ruff format --check python tests docs
mypy                          # strict (python/eunoia only)
pyright                       # strict, secondary gate (see gotchas)
sphinx-build -b html docs docs/_build/html
```

Or via `Taskfile.yml` (`go-task`): `task build`, `task test`, `task lint`,
`task typecheck`, `task docs`.

## Layout

The Rust side is `src/lib.rs` (the PyO3 module: `_fit_*` fns, `_venn`,
`_place_labels`, `EunoiaError`). The Python package lives in `python/eunoia/`,
where most filenames are self-describing; `ls` it for the current set. The
non-obvious ones: `_models.py` (the shape dataclasses + `EulerFit[S]`), `_fit.py`
and `_venn.py` (the public `euler`/`venn` plus shared `build_*` helpers),
`_eunoia.pyi` (hand-written stubs for the compiled module). The Architecture
section below explains how these fit together.

## Architecture

**Shapes and fitting.** One Rust fn per shape (`_fit_circles`, `_fit_ellipses`,
`_fit_squares`, `_fit_rectangles`, `_fit_rotated_rectangles`) plus `_venn`. Each
returns everything `fit.plot()` needs in one call (so it never refits): `shapes`,
metrics, `region_pieces`, `region_anchors`, `set_anchors`, `set_anchor_regions`,
`shape_outlines`, and `container`. In `src/lib.rs`, a shared `build_result`
generic + per-shape `ser_*` closures assemble the dict. Each shape maps to a
frozen dataclass and a `shape=` overload in `euler()`; `RotatedRectangle` adds a
`rotation` field (radians). `euler()` is generic `EulerFit[S]` with
`S = TypeVar(..., Circle, Ellipse, Square, Rectangle, RotatedRectangle)` and one
`@overload` per shape; `EulerFit.__repr__` labels the shape via
`_shape_kind_label` (splits CamelCase, so `RotatedRectangle` prints "rotated
rectangles").

**`venn()`** returns `VennFit(EulerFit)` (topological: `original_values` empty,
`fitted_values` holds geometric region areas). Accepts `int`, list-of-names, or
mapping. Supported set counts: ellipse 1--5; circle/square/rectangle 1--3;
rotated_rectangle 1--4 (the 4-set layout rotates rectangles +/-45 deg to open all
15 regions). Unsupported counts surface as `EunoiaError`. Topological, so it
takes none of `euler`'s optimizer knobs.

**Input forms** (both `euler` and `venn`), checked in this order before the
`Mapping` branch:
- *NumPy array* (`_numpy.py`, `is_ndarray` TypeGuard): 2D `(n_rows, n_sets)`
  membership matrix, or 1D single set. Values must be bool or 0/1 numeric;
  `NaN` = non-member. Arrays carry no names, so the **`names=` kwarg** supplies
  them (length+uniqueness validated; default `A`, `B`, ... via `default_name`).
  `names=` is valid *only* for array input.
- *DataFrame* (`_dataframe.py`, `is_dataframe` TypeGuard, via **narwhals**):
  pandas/polars/etc. read as a wide membership matrix. Columns must be bool or
  0/1 numeric (validated by value with `np.isin([0, 1])`, so an object column of
  `bool`/`None` is fine; strings/datetimes/out-of-range raise). Null = non-member;
  all-false rows dropped.

Both array and DataFrame input are always exclusive (reject `input="inclusive"`)
and share `matrix_to_combinations` for identical canonicalization. No Rust
change; the core still gets a pre-aggregated `list[(combo, count)]`.

**Canonical keys** everywhere in returned dicts: `"B&A"` -> `"A&B"` via
`_parse.canonicalize` (see `test_canonical_keys_in_output`).

**Inclusion-exclusion is handled by the core.** We pass `InputType::Inclusive`
when `input="inclusive"`. `_parse.to_inclusive` only re-expresses *fitted* values
in the user's scale (`Layout::fitted()` is always per-region exclusive).

**`complement=`** (euler & venn): threaded via `build_spec` to
`DiagramSpecBuilder::complement`; the jointly-fitted box returns as
`EulerFit.container` (a `Container` dataclass) and `_plot` draws it behind
everything, skipping the empty-combination region (serialized `""`). Rejected by
the core for multi-cluster specs (-> `EunoiaError`).

**Size-aware label placement** (`_plot.py`). Rather than dropping text on bare
anchors, `render` composes a label block per region (set name(s) whose
`set_anchor_regions` point here + that region's quantity, stacked), measures each
block in data units (throwaway `Text` + `get_window_extent` on a standalone
`RendererAgg`, then pixel->data via `ax.transData.inverted()`), and calls the
`_place_labels` FFI (binds `eunoia::plotting::place_labels`). Blocks that fit land
at the largest-inscribed-rect center; blocks that don't are pushed outside with a
straight leader line (`Line2D`). `_place_labels` rebuilds `RegionPolygons`
statelessly from `region_pieces` via `classify_into_pieces` + `from_map` (the
`#[non_exhaustive]` `RegionPiece` can't be constructed directly). The
measure->place loop in `_place_region_labels` re-measures when exterior labels
enlarge the canvas, bounded by `_PLACE_MAX_ITERS`; interior-only diagrams settle
in one pass. `render` does *not* call `relim`/`autoscale_view` (would clip the
expanded limits). Exterior policy is deterministic `raycast`, so seeded fits
render reproducibly. We key labels by region (via `set_anchor_regions`), not by
float-comparing anchor points: the optimizer is reproducible only to fp
precision, so the two copies of a point differ by ~1e-8.

**Global plotting options** (`eunoia.options`, the `eulerr_options` analogue):
one callable that reads (no args -> snapshot) or sets (category kwargs -> merge,
returns a context manager restoring prior state on exit); `reset_options()`
reverts to built-ins. Categories mirror `render`'s kwargs dicts
(`fills`/`edges`/`labels`/`quantities`/`legend`/`complement`, each merged
key-by-key) plus `palette` (cmap name or color sequence, replaced wholesale).
`_DEFAULTS` is the fallback; precedence is explicit kwarg > option > built-in.
State is a `ContextVar` (thread/async-safe).

**`EulerFit.plot_data` is public** (no underscore): pyright strict flags
cross-module access to single-underscore names as `reportPrivateUsage`.

**Errors:** a single `EunoiaError(ValueError)` for all `DiagramError` variants.
The Rust binding prefixes the message with the variant name (`undefined_set: ...`,
`invalid_value: ...`) for string-matching. A subclass hierarchy can be added
non-breakingly later.

## euler() optimizer knobs

`loss=` selects the objective (`_fit.Loss`; `parse_loss` in `src/lib.rs` maps to
core `LossType`). Default `"sum_squared"`; others include `"sum_absolute"`,
`"log_sum_absolute"`, `"stress"`, `"diag_error"`, region-error/max variants.
`None` keeps the core default. Non-smooth losses (`sum_absolute`,
`log_sum_absolute`, `diag_error`) are correct but much slower, especially for
ellipses.

`optimizer=` is a snake_case string (`"levenberg_marquardt"`, `"lbfgs"`,
`"nelder_mead"`, `"cma_es_lm"`, `"trf"`, `"cma_es_trf"`, `"mads"`) mapped by
`parse_optimizer`. `tolerance=`, `n_restarts=`, `max_iterations=`, `n_threads=`
expose the matching `Fitter` builder methods. Python passes scalars through the
FFI unvalidated; Rust applies them with guarded `if let Some(..)` chaining.
`n_threads=None` defers to rayon's global pool (all cores); a positive int is a
private scoped pool (`1` = serial). Threading needs the `parallel` feature, which
we enable in `Cargo.toml`. Parallelism never changes a seeded result, only speed.
All these apply to `euler` only.

## Gotchas

- **NixOS dynamic linker**: matplotlib's NumPy needs `libstdc++.so.6` and
  `libz.so` at runtime. `devenv.nix` adds `pkgs.stdenv.cc.cc.lib` and
  `pkgs.zlib` to `packages` and `LD_LIBRARY_PATH`. Don't remove these.
- **Two `ruff`s on PATH**: the pip-installed one in `.devenv/state/venv/bin` is
  broken on NixOS (dynamic linker). Fix: `ruff` is *not* in
  `[dependency-groups] dev`, so only the nix `pkgs.ruff` is reachable. A
  `Could not start dynamically linked executable: ruff` means that broke.
- **MSRV is 1.88** (`rust-version` in `Cargo.toml`). Don't downgrade below it.
- **pyright is strict but with `reportUnknownMemberType`/`Variable`/`Argument`
  disabled** (matplotlib stubs leave kwargs `Unknown`). mypy strict does the
  heavy lifting; pyright is secondary.
- **Tests are not in mypy/pyright include paths.** Strict typing covers
  `python/eunoia` only; tests are validated by pytest.

## Eunoia core API

We pin `eunoia = "1.6"` in `Cargo.toml`. Key points: the public enums are
`#[non_exhaustive]`, so `map_err`'s `DiagramError` match and the `PlacementKind`
match in `_place_labels` carry a `_` catch-all. The 1.x default optimizer is
reproducible only to fp precision, not bit-exact. (Source paths below cite the
local checkout at `/home/jola/projects/eunoia`, where sources live under
`crates/eunoia/src/...`; the published crate is single-crate, sources under
`src/...`.)

- `DiagramSpecBuilder::new().set(name, val).intersection(&[names], val).input_type(InputType::{Exclusive,Inclusive}).build()`
  (`crates/eunoia/src/spec/spec_builder.rs`)
- `Fitter::<S>::new(&spec).seed(u64).fit() -> Result<Layout<S>, DiagramError>`
  (`crates/eunoia/src/fitter.rs`)
- `Layout<S>`: `.shapes()`, `.requested()`, `.fitted()`, `.residuals()`,
  `.region_error()`, `.diag_error()`, `.stress()`, `.loss()`, `.iterations()`
  (`crates/eunoia/src/fitter/layout.rs`)
- `Layout::plot_data(&spec, PlotOptions) -> PlotData` (no `plotting` feature; the
  only optional feature we enable is `parallel`)
