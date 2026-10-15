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

### 1. The error

- With the same code and seed, changing only the font (IBM Plex Mono, Inter,
  DejaVu Sans) changes how many members are left out.
- It happens in tight figures, e.g. `figsize=(15, 3)`, with the static `plot()`.
- Result: which names appear depends on the font, and the missing ones drop
  with only a warning.
- Related, from Item 4: when space runs out, a whole intersection's members
  can vanish together, not just the one that doesn't fit.
- Measured (`seed=1`, 15x3), names left out:
  - DejaVu Sans: 2
  - Inter: 4
  - IBM Plex Mono: 10
  - Every font: `CYP3A4`, `NR1I2` never drawn (zero-area triple region,
    item 5).

### 2. Options

- **Shrink past the floor (no-drop).** Keep shrinking text until all names
  fit, so every font shows every member. Cost: text can get very small.
- **"+N more" marker.** Drop names visibly instead of silently. Reuses the
  existing `max` behaviour. Smallest, safest change.
- **Both, as an opt-in `overflow=` setting** (`"drop"` stays the default, plus
  `"shrink"` and `"more"`). Most complete; needs Johan to agree on the API.
- **Fix only the all-or-nothing drop.** Make a crowded region lose one name at
  a time, not all. Narrow, but it depends on where the dropping happens,
  possibly in Rust.

## Tell Johan (what I fixed)

- Item 7: Plotly title
  - Default top margin is now 50 px, so titles show.
  - New `title=` option on `plot_plotly()`.
  - No `height` given: figure grows by 50 px.
- Plotly hover text
  - Problem: with 1 name per line, small figures cut off the whole tooltip.
  - Now: more than 1 column only when the tooltip is taller than the figure.
  - Max tooltip height = figure height − 50 px (top margin) − 30 px (buffer),
    so there's space above and below and it doesn't get cut off.
  - Columns are aligned and left-aligned.
  - Title and `n =` stay on their own lines.
  - Titles now have spaces around `&` (`A & B`, not `A&B`).

## Before committing

- [ ] `pytest`, `ruff check`, `ruff format --check`, `mypy`, `pyright`.
- [ ] Ask Johan about committing `examples/fonts/` (~470 KB, OFL 1.1).
