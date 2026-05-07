# TODO

## Before tagging v0.1.0

- [ ] Create GitHub repo `jolars/eunoia-py` and push.
- [ ] Register pending **Trusted Publisher** on pypi.org for `eunoia`
      (workflow `release.yml`, environment `pypi-publish`).
- [ ] Connect the repo on ReadTheDocs.
- [ ] SHA-pin `PyO3/maturin-action` in `.github/workflows/release.yml`
      (currently `@v1`).
- [ ] Verify `release.yml` aarch64 + musl wheels actually build on a dry-run
      (workflow_dispatch trigger is wired up — push a `v0.1.0-rc1` test tag
      to a fork first).
- [ ] `git tag v0.1.0 && git push --tags` → wheels + sdist on PyPI.

## v0.2 — surface expansion

Deferred from v0.1.0; pick whichever is most user-requested first.

- [ ] **`venn(n, names=...)`** — non-proportional 1–5 set Venn diagrams
      (eunoia core has `VennDiagram`).
- [ ] **`error_plot(fit)`** — diagnostic plot of region errors.
- [ ] **`eunoia.options(...)`** — global plotting defaults (eulerr's
      `eulerr_options` analogue).
- [ ] **More shapes**: `shape="square"`, `shape="rectangle"` (eunoia core
      already supports them; plan was to differentiate from eulerr here).
- [ ] **`complement=` kwarg** — universe area outside all sets. Spec builder
      already has `.complement(value)`; just expose.
- [ ] **List-of-sets input**: `eu.euler({"A": ["x", "y"], "B": ["y", "z"]})`
      — count exclusive overlaps per region from membership lists.
- [ ] **DataFrame input** (pandas first, polars cheap follow-up via the
      `__dataframe__` protocol).
- [ ] **numpy bool ndarray input** — the matrix idiom from eulerr.
- [ ] **Optimizer / tolerance knobs** on `euler()`: `optimizer=`,
      `tolerance=`, `n_restarts=`, `max_iterations=`.
- [ ] **`labels=dict` for plot** — per-set custom label text/style (math
      text via mathtext, since that's why we picked matplotlib).
- [ ] **`legend=True` for plot** — eulerr has it; deferred because Euler
      diagrams self-label via region anchors.

## Quality / nice-to-haves

- [ ] Better color blending for overlap regions (eulerr blends in HSL, we
      currently average RGBA — fine but mediocre on mid-saturation pairs).
- [ ] Math-text example in `docs/quickstart.md` (set names like `$\alpha$`,
      `$\beta$`) to showcase the matplotlib choice.
- [ ] Parity test against eulerr README/vignette numbers — record specific
      `diag_error` values and assert match within 1e-6 (circles) / 1e-9
      (ellipses).
- [ ] `examples/quickstart.ipynb` (mentioned in original plan, deferred to
      reduce scope; the executed `docs/quickstart.md` covers most of it).
- [ ] `CHANGELOG.md` (and a release process note: bump version in
      `Cargo.toml`, `pyproject.toml`, `python/eunoia/__init__.py`,
      `tests/test_smoke.py`).
- [ ] Pre-commit hooks: ruff is in devenv git-hooks but not enforced
      cross-platform. Consider a `.pre-commit-config.yaml` with ruff +
      mypy + cargo fmt for non-Nix contributors.
- [ ] Codecov or `coverage` in CI.
- [ ] Subclass `EunoiaError` (e.g. `UndefinedSetError`, `EmptySetsError`)
      *only when a real user reports needing to discriminate*. Adding is
      non-breaking; removing isn't.

## Open questions / decide before v1.0

- [ ] **`EulerFit.plot_data` exposure**: it's a public attribute today
      (pyright strict made the underscore form awkward). For v1.0, decide
      whether to (a) keep public, (b) move to a module-level
      `WeakValueDictionary` keyed by `id(fit)`, or (c) split into a
      separate `EulerFitWithPlotData` subclass. See `AGENTS.md`.
- [ ] **`Generic[S]` in `EulerFit`**: keeps types tight via `@overload` on
      `euler()`, but `EulerFit[Circle]` vs `EulerFit[Ellipse]` adds notation
      noise in error messages and docs. Consider a flat `EulerFit` with a
      `shapes: tuple[Circle, ...] | tuple[Ellipse, ...]` field if users
      complain.
- [ ] **Pyright config**: `reportUnknownMemberType / Variable / Argument`
      are disabled because matplotlib's stubs leak `Unknown`. Re-enable
      when matplotlib stubs improve, or migrate to typed wrappers.
- [ ] **devenv.nix unused packages**: `pkgs.cmake`, `pkgs.ninja`,
      `pkgs.eigen` aren't used by our toolchain. Confirm safe to drop.

## Eunoia core upstream tracking

- [ ] Bump `eunoia = "0.12"` in `Cargo.toml` when 0.13 / 1.0 ships. Pre-1.0
      means minor bumps may break — track tightly. Re-verify the bound API
      surface listed in `AGENTS.md`.
