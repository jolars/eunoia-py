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
      (`gh workflow run publish.yml --ref main`; the `publish` job is gated on
      `refs/tags/v*` so PyPI is not touched).
- [x] Register pending **Trusted Publisher** on test.pypi.org for `eunoia`
      (workflow `publish-test.yml`, environment `testpypi`). Separate
      registration from prod pypi.org.
- [x] Run `publish-test.yml` (`gh workflow run publish-test.yml --ref main`) and
      verify the wheels install from TestPyPI:
      `pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ eunoia`.

## v0.2: surface expansion

Deferred from v0.1.0; pick whichever is most user-requested first.

- [x] **`venn(n, names=...)`**: non-proportional Venn diagrams (eunoia core
      `VennDiagram`). Done: `venn()` takes int, list-of-names, or mapping,
      returns `VennFit`. Ellipse 1--5, square/rectangle 1--3; **circle Venn
      unsupported in core 0.15** (re-enable after the 0.18 bump).
- [x] **`eunoia.options(...)`**: global plotting defaults (eulerr's
      `eulerr_options` analogue). Done: single callable that reads (no args) or
      sets (category kwargs) and doubles as a context manager for scoped
      overrides; `reset_options()` restores defaults. Categories mirror
      `_plot.render`'s kwargs dicts (`fills`/`edges`/`labels`/`quantities`/
      `legend`/`complement` + `palette`). State in a `ContextVar`. See
      `_options.py`.
- [x] **More shapes**: `shape="square"`, `shape="rectangle"`. Done.
- [x] **`complement=`kwarg**: universe area outside all sets. Done for both
      `euler()` and `venn()`; container surfaces as `EulerFit.container` and is
      drawn by `.plot()`.
- [x] **List-of-sets input**: `eu.euler({"A": ["x", "y"], "B": ["y", "z"]})`,
      counting exclusive overlaps per region from membership lists.
- [x] **DataFrame input**: pandas, polars, etc. as a wide membership matrix
      (each column a set, each row an observation). Routed through `narwhals`
      rather than the deprecated `__dataframe__` interchange protocol.
- [x] **numpy bool ndarray input**: the matrix idiom from eulerr. Done: a 2D
      `(n_observations, n_sets)` boolean/`0`/`1` array (or 1D single set) is read
      as a membership matrix by `euler()`/`venn()`, with set names from a new
      `names=` kwarg (default `A`, `B`, …). See `_numpy.py`.
- [x] **Optimizer and tolerance knobs** on `euler()`: `optimizer=`, `tolerance=`,
      `n_restarts=`, `max_iterations=`.
- [x] **`labels=dict`for plot**: per-set custom label text and style (math text
      via mathtext, since that's why we picked matplotlib). Done: `labels`
      accepts `bool | dict | None`. A per-set dict (keys = set names) maps each
      to a replacement string, an `ax.text` kwargs dict (optional `"text"` key),
      or `None`/`False` to hide; a dict with no set-name keys is a uniform style
      applied to all labels. See `_resolve_set_labels` in `_plot.py`.
- [x] **`legend=True`for plot**: color-keyed swatches via `ax.legend`;
      accepts `bool | dict` and defaults inline `labels` off when shown.
- [x] **`quantities` display types**: widened to `bool | str | dict` to
      mirror eulerr's `quantities = list(type = ...)`. Strings select either the
      value *source* (`"original"` or `"fitted"`) or the display *type*
      (`"counts"` or `"percent"`); a dict combines `source`, `type` (one or both
      of `counts`/`percent`, stacked count-over-percent), and any extra
      `ax.text` style kwargs (`color`, `fontsize`, or `fontstyle`). Percent is
      each region's share of the total. See `_resolve_quantities` in `_plot.py`.
- [x] **Per-set edge styling**: `edges` now also accepts a per-set dict
      (keyed by set name, values are `PathPatch` kwargs dicts) or a sequence of
      kwargs dicts (one per set, in shape order), in addition to the flat dict
      applied uniformly. See `_resolve_set_edges` in `_plot.py`.

## Quality and nice-to-haves

- [x] Better color blending for overlap regions (now blend in OKLab via
      linear-light sRGB instead of averaging gamma-encoded RGBA, which
      darkened mid-saturation pairs).
- [x] Math-text example in `docs/quickstart.md` (set names like `$\alpha$`,
      `$\beta$`) to showcase the matplotlib choice.
- [ ] Parity test against eulerr README and vignette numbers; record specific
      `diag_error` values and assert match within 1e-6 (circles) or 1e-9
      (ellipses).
- [ ] Codecov or `coverage` in CI.
- [ ] Subclass `EunoiaError` (e.g. `UndefinedSetError`, `EmptySetsError`) *only
      when a real user reports needing to discriminate*. Adding is non-breaking;
      removing isn't.

## Open questions to decide before v1.0

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
- [ ] **Pyright config**: `reportUnknownMemberType`, `Variable`, and `Argument` are
      disabled because matplotlib's stubs leak `Unknown`. Re-enable when
      matplotlib stubs improve, or migrate to typed wrappers.

## Eunoia core upstream tracking

- [x] Bump `eunoia` pin (currently `"0.15"` in `Cargo.toml`) toward upstream
      (local checkout is already at 0.18.0). Pre-1.0 means minor bumps may break,
      so track tightly. Re-verify the bound API surface listed in `AGENTS.md`.

## Defer until later

- [ ] **`error_plot(fit)`**: diagnostic plot of region errors.
- [x] **Plotly backend**: an interactive renderer alongside matplotlib, behind
      a `eunoia[plotly]` extra (lazily imported). Motivated by hover tooltips
      (discussion #34), which matplotlib can't serve cleanly in static HTML or
      notebooks; member-on-hover falls out as per-region `hovertext`. Shipped as
      `EulerFit.plot_plotly()`: backend-neutral content helpers factored into
      `_render_common.py` (shared with the matplotlib emitter), text measured
      Axes-free via fontTools (`_metrics.py`), and the plotly emitter
      (`_plotly.py`) added as a purely additive step. `eunoia.options` categories
      are read and translated to plotly properties (colors, `alpha`,
      `linewidth`, `fontsize`); a fuller backend-neutral/tagged options split can
      follow if a second interactive backend is added.
