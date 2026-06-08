# TODO

## Before tagging v0.1.0

- [x] Create GitHub repo `jolars/eunoia-py` and push.
- [x] Register pending **Trusted Publisher** on pypi.org for `eunoia` (workflow
      `release.yml`, environment `pypi-publish`).
- [x] Add `.github/workflows/docs.yml` that builds Sphinx and deploys to GitHub
      Pages (env `github-pages`, `actions/deploy-pages`). Triggers on version
      tags (`v*`) and `workflow_dispatch`.
- [x] In repo settings → Pages, set Source = "GitHub Actions" so the
      `github-pages` environment is created (one-time manual step).
- [x] Verify `publish.yml` aarch64 + musl wheels actually build on a dry-run
      (`gh workflow run publish.yml --ref main` --- `publish` job is gated on
      `refs/tags/v*` so PyPI is not touched).
- [x] Register pending **Trusted Publisher** on test.pypi.org for `eunoia`
      (workflow `publish-test.yml`, environment `testpypi`). Separate
      registration from prod pypi.org.
- [x] Run `publish-test.yml` (`gh workflow run publish-test.yml --ref main`) and
      verify the wheels install from TestPyPI:
      `pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ eunoia`.

## v0.2 --- surface expansion

Deferred from v0.1.0; pick whichever is most user-requested first.

- [x] **`venn(n, names=...)`** --- non-proportional Venn diagrams (eunoia core
      `VennDiagram`). Done: `venn()` takes int / list-of-names / mapping,
      returns `VennFit`. Ellipse 1--5, square/rectangle 1--3; **circle Venn
      unsupported in core 0.15** (re-enable after the 0.18 bump).
- [ ] **`eunoia.options(...)`** --- global plotting defaults (eulerr's
      `eulerr_options` analogue).
- [x] **More shapes**: `shape="square"`, `shape="rectangle"`. Done.
- [x] **`complement=`kwarg** --- universe area outside all sets. Done for both
      `euler()` and `venn()`; container surfaces as `EulerFit.container` and is
      drawn by `.plot()`.
- [x] **List-of-sets input**: `eu.euler({"A": ["x", "y"], "B": ["y", "z"]})` ---
      count exclusive overlaps per region from membership lists.
- [ ] **DataFrame input** (pandas first, polars cheap follow-up via the
      `__dataframe__` protocol).
- [ ] **numpy bool ndarray input** --- the matrix idiom from eulerr.
- [ ] **Optimizer / tolerance knobs** on `euler()`: `optimizer=`, `tolerance=`,
      `n_restarts=`, `max_iterations=`.
- [ ] **`labels=dict`for plot** --- per-set custom label text/style (math text
      via mathtext, since that's why we picked matplotlib).
- [ ] **`legend=True`for plot** --- eulerr has it; deferred because Euler
      diagrams self-label via region anchors.
- [ ] **`quantities` display types** --- widen the kwarg to mirror eulerr's
      `quantities = list(type = ...)`: support `"percent"` (share of total) and
      a count+percent combination in addition to the current raw value, plus
      text styling (`color` / `fontsize` / `fontstyle`). Natural shape is
      `quantities: bool | str | dict`. Used in several eulerr gallery plots
      (one_contained, wilkinson, gene_set).
- [ ] **Per-set edge styling** --- `edges` currently applies one dict uniformly
      to every outline (`_plot.py`); eulerr allows per-set vectors
      (`edges = list(lty = 1:3)`). Let `edges` also accept a per-set dict (keyed
      by set name) or sequence, mirroring how `colors=` already works.

## Quality / nice-to-haves

- [ ] Better color blending for overlap regions (eulerr blends in HSL, we
      currently average RGBA --- fine but mediocre on mid-saturation pairs).
- [ ] Math-text example in `docs/quickstart.md` (set names like `$\alpha$`,
      `$\beta$`) to showcase the matplotlib choice.
- [ ] Parity test against eulerr README/vignette numbers --- record specific
      `diag_error` values and assert match within 1e-6 (circles) / 1e-9
      (ellipses).
- [ ] Codecov or `coverage` in CI.
- [ ] Subclass `EunoiaError` (e.g. `UndefinedSetError`, `EmptySetsError`) *only
      when a real user reports needing to discriminate*. Adding is non-breaking;
      removing isn't.

## Open questions / decide before v1.0

- [ ] **`EulerFit.plot_data`exposure**: it's a public attribute today (pyright
      strict made the underscore form awkward). For v1.0, decide whether to (a)
      keep public, (b) move to a module-level `WeakValueDictionary` keyed by
      `id(fit)`, or (c) split into a separate `EulerFitWithPlotData` subclass.
      See `AGENTS.md`.
- [ ] **`Generic[S]`in `EulerFit`**: keeps types tight via `@overload` on
      `euler()`, but `EulerFit[Circle]` vs `EulerFit[Ellipse]` adds notation
      noise in error messages and docs. Consider a flat `EulerFit` with a
      `shapes: tuple[Circle, ...] | tuple[Ellipse, ...]` field if users
      complain.
- [ ] **Pyright config**: `reportUnknownMemberType / Variable / Argument` are
      disabled because matplotlib's stubs leak `Unknown`. Re-enable when
      matplotlib stubs improve, or migrate to typed wrappers.

## Eunoia core upstream tracking

- [x] Bump `eunoia` pin (currently `"0.15"` in `Cargo.toml`) toward upstream
      (local checkout is already at 0.18.0). Pre-1.0 means minor bumps may break
      --- track tightly. Re-verify the bound API surface listed in `AGENTS.md`.

## Defer until later

- [ ] **`error_plot(fit)`** --- diagnostic plot of region errors.
