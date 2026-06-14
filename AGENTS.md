# Agent guide

Notes for AI agents working on this repo. Keep it short --- code is the source
of truth, this file just points at things and flags gotchas.

## What this is

Python wrapper for the [`eunoia`](https://github.com/jolars/eunoia) Rust crate
(area-proportional Euler/Venn diagrams). PyPI name `eunoia`, sister package to
the R package `eulerr`. Built with PyO3 + maturin, abi3-py311.

## Working in the repo

The dev environment is a `devenv` shell, which puts `cargo` (Rust 1.88),
`maturin`, `pytest`, etc. on `PATH`. Assume you are already inside it — run
commands directly (no `direnv` / wrapper prefix needed).

The devenv also auto-runs `uv sync --all-extras --all-groups`, so the venv at
`.devenv/state/venv` already has matplotlib, numpy, mypy, pyright, maturin, and
the docs deps. Build the Rust extension into the venv with
`maturin develop --uv`.

Common loops:

```bash
maturin develop --uv          # build + install editable
pytest                        # run tests (26 currently)
ruff check python tests docs  # lint
ruff format --check python tests docs
mypy                          # strict
pyright                       # strict (matplotlib leniency, see below)
sphinx-build -b html docs docs/_build/html
```

Or via `Taskfile.yml` (`go-task`): `task build`, `task test`, `task lint`,
`task typecheck`, `task docs`, etc.

## Layout

```
src/lib.rs                       PyO3 module: _fit_circles, _fit_ellipses, EunoiaError
python/eunoia/__init__.py        public re-exports
python/eunoia/_models.py         dataclasses: Point, Circle, Ellipse, EulerFit[S]
python/eunoia/_fit.py            public euler() with @overload on shape kwarg
python/eunoia/_parse.py          dict → list[(combo, area)], canonicalize, to_inclusive
python/eunoia/_plot.py           matplotlib renderer (PathPatch + compound Path)
python/eunoia/_options.py        global plotting defaults: options() / get_options() / reset_options()
python/eunoia/_eunoia.pyi        hand-written stubs for the compiled module
python/eunoia/py.typed           PEP 561 marker
docs/conf.py                     Sphinx + MyST + furo (mirrored from sortedl1)
docs/exts/github_link.py         linkcode helper (BSD-3, ported from scikit-learn)
tests/test_*.py                  fit / plot / repr / smoke tests
.github/workflows/ci.yml         lint + typecheck + test matrix + docs build
.github/workflows/publish.yml    multi-platform wheels → PyPI trusted publishing (tag-triggered)
.github/workflows/publish-test.yml  same matrix → TestPyPI (workflow_dispatch only)
.github/workflows/docs.yml       sphinx → GitHub Pages (env `github-pages`)
```

## Key decisions worth remembering

- **One Rust fn per shape**: `_fit_circles`, `_fit_ellipses`, `_fit_squares`,
  `_fit_rectangles`, plus `_venn`. Each returns `shapes`, metrics,
  `region_pieces`, `region_anchors`, `set_anchors`, `set_anchor_regions`,
  `shape_outlines`, and `container` in the same call so `fit.plot()` doesn't
  refit. (`set_anchor_regions` maps each set to the canonical region key its
  label anchor was derived from; `_plot` uses it to stack a set label and its
  region quantity when they coincide, instead of comparing anchor points by
  float equality — the optimizer is only reproducible to fp precision, so the
  two copies of the point differ by ~1e-8.) In `src/lib.rs` the
  shared `build_result` generic + per-shape `ser_*` closures assemble the dict;
  `_fit_*` and `_venn` both call it. All four shapes map to a frozen dataclass
  (`Circle`/`Ellipse`/`Square`/`Rectangle`) and a `shape=` overload in
  `_fit.euler`; `_fit._finish` shares the fitted/residual assembly, and the
  `build_circles`/`build_ellipses`/… + `build_container`/`build_plot_data`
  helpers in `_fit.py` are reused by `_venn.venn`.
- **`complement=`** (euler & venn): threaded through `build_spec` to
  `DiagramSpecBuilder::complement`; the jointly-fitted box comes back as
  `EulerFit.container` (a `Container` dataclass) and `_plot` draws it behind
  everything, skipping the empty-combination region (which serializes to `""`).
  Rejected by the core for multi-cluster specs (surfaces as `EunoiaError`).
- **`venn()`** returns a `VennFit(EulerFit)` (custom repr; topological, so
  `original_values` is empty and `fitted_values` holds geometric region areas).
  Accepts `int` / list-of-names / mapping. Supported set counts: ellipse
  (1–5), circle/square/rectangle (1–3). Circle Venn gained a
  `canonical_venn_layout` impl in core 0.18; an unsupported count surfaces as
  `EunoiaError`.
- **Inclusion-exclusion is handled by the core**, not Python. We pass
  `InputType::Inclusive` to `DiagramSpecBuilder::input_type()` when
  `input="inclusive"`. `_parse.to_inclusive` is only used to express *fitted* values
  in the user's input scale (since `Layout::fitted()` is always per-region
  exclusive).
- **Canonical keys** everywhere in returned dicts: `"B&A"` becomes `"A&B"` via
  `_parse.canonicalize`. Tests rely on this --- see
  `test_canonical_keys_in_output`.
- **Generic `EulerFit[S]`** with `S = TypeVar("S", Circle, Ellipse)`. The public
  `euler()` has two `@overload`s so `eu.euler(..., shape="ellipse")` types as
  `EulerFit[Ellipse]`.
- **`EulerFit.plot_data`is a public attribute** (no leading underscore). pyright
  strict flags cross-module access to single-underscore names as
  `reportPrivateUsage`. If you want it actually private, switch to a
  module-level `WeakValueDictionary` keyed by `id(fit)`.
- **Global plotting options** (`eunoia.options`, the `eulerr_options` analogue):
  one callable that reads (no args → snapshot) or sets (category kwargs → merge,
  returns a context manager that restores prior state on exit); `reset_options()`
  reverts to built-ins. Categories mirror `_plot.render`'s kwargs dicts —
  `fills`/`edges`/`labels`/`quantities`/`legend`/`complement` (each a dict,
  merged key-by-key) and `palette` (a cmap name or color sequence, replaced
  wholesale). `_DEFAULTS` in `_options.py` is the fallback layer; `render`
  reads `get_options()` and layers per-call kwargs on top (explicit kwarg >
  option > built-in). State is a `ContextVar`, so scoping is thread/async-safe.
- **abi3-py311** → one wheel per platform covers Python 3.11--3.14. Don't add
  per-Python-version wheel rows to `publish.yml`.
- **Single `EunoiaError(ValueError)`** for all `DiagramError` variants. The Rust
  binding prefixes the message with the variant name (`undefined_set: ...`,
  `invalid_value: ...`) so users can string-match. Subclass hierarchy can be
  added later non-breakingly.
- **`euler(..., loss=)`** selects the optimizer objective. `_fit.Loss` lists the
  strings (`"sum_squared"` default, `"sum_absolute"`, `"log_sum_absolute"`,
  `"stress"`, `"diag_error"`, region-error/max variants); `parse_loss` in
  `src/lib.rs` maps them to the core `LossType`. `None` keeps the core default
  (`sum_squared`). Non-smooth losses (`sum_absolute`, `log_sum_absolute`,
  `diag_error`) optimize correctly but are much slower, especially for ellipses.

## Gotchas (things that bit us once)

- **NixOS dynamic linker**: matplotlib's NumPy needs `libstdc++.so.6` and
  `libz.so` at runtime. `devenv.nix` adds `pkgs.stdenv.cc.cc.lib` and
  `pkgs.zlib` to `packages` and to `LD_LIBRARY_PATH`. Don't remove these.
- **Two `ruff`s on PATH**: a pip-installed one in `.devenv/state/venv/bin` and
  the nix-provided one. The pip one is broken on NixOS (dynamic linker again).
  We solved this by *not* listing `ruff` in `[dependency-groups]   dev`, so only
  the nix one (`pkgs.ruff`) is reachable. If you ever see
  `Could not start dynamically linked executable: ruff`, that's why.
- **`eunoia` 1.x MSRV is 1.88**, matched by `rust-version` in `Cargo.toml`. Don't
  downgrade the toolchain below that.
- **pyright is strict but with `reportUnknownMemberType` / `Variable` /
  `Argument` disabled** in `pyproject.toml`. matplotlib's stubs leave many
  kwargs as `Unknown`, which spams those rules without anything actionable. mypy
  strict does the heavy lifting; pyright is the secondary gate.
- **Tests are not in mypy/pyright include paths.** Strict typing applies to
  `python/eunoia` only. Tests are validated by pytest.

## Eunoia core API we bind against

(We pin `eunoia = "1.1"` in `Cargo.toml`; the binding is verified against the
published 1.1.0 crate. 1.0 made the public enums `#[non_exhaustive]`, so
`map_err`'s `DiagramError` match carries a `_` catch-all; 1.0 also fixed the
`SumAbsoute`→`SumAbsolute` typo and 1.1 added `LossType::LogSumAbsolute`. The
new 1.x default optimizer is reproducible only to floating-point precision, not
bit-exact. Note: the published crate is a single crate — its sources live under
`src/…`, not the workspace `crates/eunoia/src/…` paths cited below, which point
at the local checkout at `/home/jola/projects/eunoia`.)

- `DiagramSpecBuilder::new().set(name, val).intersection(&[names], val).input_type(InputType::{Exclusive,Inclusive}).build()`
  (`crates/eunoia/src/spec/spec_builder.rs`)
- `Fitter::<S>::new(&spec).seed(u64).fit() -> Result<Layout<S>, DiagramError>`
  (`crates/eunoia/src/fitter.rs:137`)
- `Layout<S>`: `.shapes()`, `.requested()`, `.fitted()`, `.residuals()`,
  `.region_error()`, `.diag_error()`, `.stress()`, `.loss()`, `.iterations()`
  (`crates/eunoia/src/fitter/layout.rs`)
- `Layout::plot_data(&spec, PlotOptions) -> PlotData` (gated on `plotting`
  feature; we enable it in `Cargo.toml`)
- `DiagramError` variants → `EunoiaError` with prefix tags

## Manual one-time setup (before first PyPI release)

1. Create GitHub repo `jolars/eunoia-py`, push.
2. On pypi.org, register a **pending Trusted Publisher** for `eunoia` (workflow
   `publish.yml`, environment `pypi`).
3. On test.pypi.org, register a separate pending Trusted Publisher for
   `eunoia` (workflow `publish-test.yml`, environment `testpypi`). Used by
   the `publish-test.yml` dispatch workflow for pre-release verification.
4. In the GitHub repo settings, under **Pages**, set Source = "GitHub Actions".
   This auto-creates the `github-pages` environment that `docs.yml` deploys to.
   (We host docs on GitHub Pages via Actions, not on ReadTheDocs.)

## Out of scope for v0.1.0 (do not add without asking)

`venn()`, `error_plot()`, `options()`, list-of-sets / DataFrame / numpy input,
`complement=` kwarg, `square` / `rectangle` shapes, exposed
optimizer/tolerance/n_restarts knobs, plot legend.
