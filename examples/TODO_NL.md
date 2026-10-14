# TODO (NL)

Items 6 and 7 from *Investigations on eunoia 0.6.0*, plus the Plotly hover
issue found along the way. Reproduce with `examples/viset_repro.ipynb`
(`viset` env, outputs in `repro-out/`).

## Fixing hover texts in Plotly

- [x] **Tooltips cut off in small figures.** Each region's tooltip listed one
  member per line, so big regions (~30 names) were taller than the figure and
  got cut off (e.g. `width=400`).
- [x] Tooltips are built after the final figure height is known
  (`render_plotly` → `_add_hover`).
- [x] Max height = figure height − top margin (50) − 30 px.
  Max gene rows = `(max_height // 17) - 2` (17 px per line at Plotly's 13 px
  hover font; 2 lines for the region name and `n =`).
- [x] Region name and `n =` stay on their own lines; genes wrap into rows,
  space separated, split evenly (`_hover_text`).
- [ ] Check in the browser at several sizes (700x700, 400, 250).
- [ ] Tests in `tests/`.
- [ ] Maybe: "+N more" when rows are still too wide for the figure.
- [ ] Maybe: aligned columns (needs `&nbsp;` padding and/or a monospace hover
  font).

## Item 7: Plotly title hidden with default margins

- [x] Default top margin is now 50 px (was 0), so
  `fig.update_layout(title=...)` shows. `update_layout(margin={"t": 0})`
  still overrides it.
- [x] New `title=` option on `plot_plotly()`.
- [x] Without an explicit `height`, the figure grows by 50 px.
- [ ] Tests in `tests/`.
- Skipped for now: with an explicit `height`, labels are still measured for
  the full height (the diagram really gets `height - 50`).

## Item 6: Different fonts change how many members fit

Same code and seed, switching fonts (DejaVu Sans, IBM Plex Mono, Inter) leaves
a different number of members out in constrained figures, e.g.
`figsize=(15, 3)`.

- [x] Reproduced (`seed=1`, 15x3): DejaVu Sans 2, Inter 4, IBM Plex Mono 10
  did not fit (plus `CYP3A4`, `NR1I2` not drawn: zero-area triple region,
  item 5).
- [x] Each font is really used (checked with `get_fontname()`).
- [x] Static `plot()` looks like expected behaviour: wider font, fewer names
  fit. Names are measured in the same font they are drawn in.
- [ ] Check Plotly: `default_measurer()` is called without a font family and
  the Plotly `font` dict only passes size and colour, so `fontfamily` is
  likely ignored there.
- [ ] Fix Plotly if so, then tests.
- [ ] Report the static result to Johan as expected behaviour.

## Before committing

- [ ] `pytest`, `ruff check`, `ruff format --check`, `mypy`, `pyright`.
- [ ] Ask Johan about committing `examples/fonts/` (~470 KB, OFL 1.1).
