# TODO

## Rendering report for 0.6.0

Triaged from the supplied `epost-att-lv9vlQ.html` in the sibling Eunoia
checkout. [examples/report_repro.py](examples/report_repro.py) generates
Matplotlib figures, optional Plotly title examples, and diagnostic counts:

```sh
python examples/report_repro.py /tmp/eunoia-report
```

Run in this repository's development environment with the extension installed.
The script includes the original gene membership data from
[issue #133](https://github.com/jolars/eunoia/issues/133), including triple members
`CYP3A4` and `NR1I2`. It uses the issue's seed 0, an explicit budget of
10 restarts, and one fitting thread. Long-name variants append a synthetic
suffix while preserving memberships. These are reproductions of the symptoms,
not exact reconstructions of the report's rendering settings. The results below
used eunoia 0.6.0 and Matplotlib 3.11.1; font metrics can change the counts.

Core changes and a renderer-independent Rust reproduction are tracked in
[Eunoia's TODO](../eunoia/TODO.md). Keep fitting and packing algorithms there.

- [ ] **Default to boundary tethers when displaying members (item 1).**
  Compare `packed-short.png` with `packed-boundary.png`. Core already supports
  `labels={"placement": {"tether": "boundary"}}`, and the binding passes it
  through. Consider this default for member displays while preserving explicit
  overrides. This shortens leaders through their own region; it does not promise
  that leaders avoid every other region's members. If crossings remain, capture
  the fixed geometry and leader segments before requesting a core routing change.

- [ ] **Keep measurements valid at the final viewport (items 1/3).**
  `_plot._place_region_labels` and `_plotly._place_region_labels` stop after
  `_PLACE_MAX_ITERS = 4` and can return placements measured before the last
  bounds expansion. Later exterior set-label placement can also invalidate
  region-label obstacle sizes. Reconcile the final transform, measured blocks,
  placements, and obstacles before packing members and drawing. Include
  multiline text and the actual font/style in this check. `long-list.png`
  reproduces overlapping lists and a shrunken central diagram. Instrumenting
  its four `_place_labels` calls found no overlap between the boxes supplied
  to core, while the final Matplotlib text extents did overlap. This isolates
  a renderer problem for this fixture; it does not prove that every reported
  exterior collision has the same cause. Define a readable fallback when the
  viewport loop cannot converge, instead of merely raising the iteration cap.

- [ ] **Add columns and clearer hierarchy to list mode (items 2/3/4).**
  Both renderers currently turn each region's roster into one newline-joined
  block. Try measured two- and three-column candidates before exterior
  placement, or expose a column/maximum-row option. Keep set headings visually
  distinct from members and account for column gaps in the block measurement.
  Compare `list-roomy.png` and `long-list.png`; changing the box composition
  needs no new core packing algorithm.

- [ ] **Make font scaling and readability choices explicit (items 2/4).**
  Packed members use their reference font size times core's returned scale;
  labels retain their configured size. A larger figure therefore stops growing
  members once scale reaches `1`, and list mode has no member-packing scale at
  all. Compare `packed-short.png`, `packed-roomy.png`, and
  `packed-large-font.png`. Consider an opt-in shared scale/size ratio with a
  readable minimum, respecting explicit font sizes and remeasuring label
  obstacles if the label size changes. The core `max_scale` proposal is
  separate from these renderer defaults; do not present extra rows alone as a
  guarantee that larger text will fit.

- [ ] **Report every omitted member and offer a readable fallback
  (items 4/5/6).** Current warnings cover only core's `unplaced` output.
  `_place_packed_members` filters out regions absent from `region_pieces`
  before calling core; list mode also skips them. Compare requested member
  regions against the fitted geometry and report absent regions separately
  from text overflow. Follow the
  [maintainer's preference](https://github.com/jolars/eunoia/issues/133#issuecomment-5327820844)
  for fit summaries or display diagnostics rather than unconditional warnings
  for approximate fits. The example's circle fit requests two triple members
  but fits zero triple area; even `packed-roomy.png` omits both without an
  overflow warning. `ellipse-control.png` retains them. Do not imply that
  increasing the font budget restores a geometrically absent region.
  For regions that exist but overflow, consider a whole-region exterior
  callout or an explicit count of omitted names, using core placements and
  keeping the measurement loop consistent. The core's prefix contract means
  an oversized early name can also hide later names; do not zip a reordered
  or filtered subset with the original roster.

- [ ] **Validate font measurement and omission reporting (item 6).**
  `packed-short.png` and `packed-monospace.png` differ only in member font
  family. Both omit four names in this fixture, including the two geometrically
  absent triple members; the report's different omission counts are not
  reproduced with these fonts and seed. Different font widths legitimately
  change capacity, so equal omission counts are not an appropriate requirement.
  Check that the resolved font, weight, size, and multiline metrics match the
  renderer, and distinguish expected packing overflow from stale or inaccurate
  measurements. Plotly's fontTools estimates need particular attention when
  the browser resolves a different font. Missing-member warnings must remain
  accurate regardless of font choice.

- [ ] **Reserve space for Plotly titles (item 7).**
  `_plotly._finalize_layout` sets all margins to zero. The script confirms
  `fig.layout.margin.t == 0` and writes `plotly-title-default.html` and
  `plotly-title-margin.html`; the latter adds `margin={"t": 50}`. Choose a
  modest top margin or expose a title option that reserves space. Document
  the current workaround and account for usable plot height when measuring
  labels. No core change is needed. The HTML pair is for browser comparison;
  title visibility was not checked with an automated browser.

Upstream dependencies: strict glyph/member obstacles, balanced packed rows,
an optional alternative to prefix-only overflow, automatic `max_scale`, and
topology-aware fitting are tracked in Eunoia. In particular, the core deliberately
falls back to packing over label boxes, so correcting Python measurements alone
cannot eliminate item 1's label/member overlaps. Expose a strict core option once
available and use the overflow fallback above.

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

- [x] Track stable Eunoia core releases. The wrapper now pins 1.9 and exposes
      matched and exterior set-label placement, unit glyphs, and packed member
      labels.

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
