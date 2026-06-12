"""Run the benchmark and emit the artifacts the docs report consumes.

The comparison is **grouped by objective**: fitters can only be compared fairly
when they minimize the same loss, so each group runs the packages that minimize
one loss family and scores them on that family's scale-invariant metric. eunoia
(configurable via ``loss=``) and matplotlib-set-diagrams (configurable via its
cost objective) appear in several groups; matplotlib-venn appears only in the
logarithmic group (its venn3 default objective).

Usage::

    python -m benchmarks.run            # full run, default resolution
    python -m benchmarks.run --quick    # coarse grid for iteration

Outputs (relative to the repo root):

* ``benchmarks/results/results.json`` -- machine-readable source of truth
* ``docs/_generated/benchmark_table.md`` -- per-group accuracy tables
* ``docs/_generated/benchmark_timing.md`` -- wall-clock fit-time table
* ``docs/_static/benchmarks/objective_groups.png`` -- per-group accuracy charts
* ``docs/_static/benchmarks/timing.png`` -- wall-clock fit-time chart
* ``docs/_static/benchmarks/gallery.png`` -- fitted layouts, side by side

The competitor packages are GPL/MIT and are only *run* here to measure fit
quality; no competitor source is vendored or redistributed by eunoia (MIT).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse as EllipsePatch

from .adapters import (
    EunoiaAdapter,
    MatplotlibSetDiagramsAdapter,
    MatplotlibVennAdapter,
)
from .cases import CASES, CORPUS_SOURCE, Case
from .metrics import METRICS, Shape, score

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "benchmarks" / "results"
GENERATED_DIR = REPO_ROOT / "docs" / "_generated"
FIGURE_DIR = REPO_ROOT / "docs" / "_static" / "benchmarks"

_PLOT_FLOOR = 5e-5  # log-axis floor so true zeros are still drawn

# Each group: the objective its members minimize, the metric to score it on, and
# the configured fitters that minimize that objective. `pending` notes a fitter
# that *would* belong but cannot yet (tracked upstream).
GROUPS = [
    {
        "key": "squared",
        "title": "Sum of squared errors",
        "objective": "minimize Σ (fitted - target)²",
        "metric": "stress",
        "members": [
            EunoiaAdapter("circle", loss="sum_squared"),
            EunoiaAdapter("ellipse", loss="sum_squared"),
            MatplotlibSetDiagramsAdapter("squared"),
        ],
    },
    {
        "key": "absolute",
        "title": "Sum of absolute errors",
        "objective": "minimize Σ |fitted - target|",
        "metric": "abs_error",
        "members": [
            EunoiaAdapter("circle", loss="sum_absolute"),
            EunoiaAdapter("ellipse", loss="sum_absolute"),
            MatplotlibSetDiagramsAdapter("simple"),
        ],
    },
    {
        "key": "logarithmic",
        "title": "Logarithmic error",
        "objective": "minimize Σ |log(1+fitted) - log(1+target)|",
        "metric": "log_error",
        "members": [
            EunoiaAdapter("circle", loss="log_sum_absolute"),
            EunoiaAdapter("ellipse", loss="log_sum_absolute"),
            MatplotlibVennAdapter(),
            MatplotlibSetDiagramsAdapter("logarithmic"),
        ],
    },
]

# Configs rendered in the side-by-side gallery (geometry, not objective).
GALLERY_CASES = [
    "uniform_3_set",
    "eulerape_3_set",
    "issue47_3_set_huge_triple",
    "issue114_4_set_dominant_quad",
    "wilkinson_6_set",
]
GALLERY_MEMBERS = [
    EunoiaAdapter("circle", loss="sum_squared"),
    EunoiaAdapter("ellipse", loss="sum_squared"),
    MatplotlibVennAdapter(),
    MatplotlibSetDiagramsAdapter("squared"),
]


# Representative config per package for the wall-clock timing table/figure
# (group key, member id, display). Timing is end-to-end ``fit`` time from Python.
TIMING_MEMBERS = [
    ("squared", "eunoia-circle-sum_squared", "eunoia (circle)"),
    ("squared", "eunoia-ellipse-sum_squared", "eunoia (ellipse)"),
    ("logarithmic", "matplotlib-venn", "matplotlib-venn"),
    ("squared", "matplotlib-set-diagrams-squared", "matplotlib-set-diagrams"),
]


def _time_fit(adapter, case: Case, repeats: int) -> float:
    samples: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        adapter.fit(case)
        samples.append((time.perf_counter() - start) * 1000.0)
    return median(samples)


def run_grid(resolution: int, repeats: int) -> dict:
    """Run every group; return the full results dict."""
    # Only the configs shown in the timing table get the (expensive) repeated
    # timed re-fits; everything else is fit once for accuracy.
    timed = {(gkey, mid) for gkey, mid, _ in TIMING_MEMBERS}
    groups_out: list[dict] = []
    for group in GROUPS:
        metric = group["metric"]
        members_out = [
            {"id": m.id, "display": m.display, "available": m.available}
            for m in group["members"]
        ]
        rows: list[dict] = []
        for case in CASES:
            cells: dict[str, dict] = {}
            for member in group["members"]:
                cell: dict = {}
                if not member.available:
                    cell["status"] = "not-installed"
                elif not member.supports(case):
                    cell["status"] = "unsupported"
                else:
                    try:
                        shapes = member.fit(case)
                        cell["status"] = "ok"
                        cell["value"] = score(
                            shapes, case.sets, case.regions, metric, resolution
                        )
                        if (group["key"], member.id) in timed:
                            cell["time_ms"] = _time_fit(member, case, repeats)
                    except Exception as exc:  # record, don't crash the run
                        cell["status"] = "error"
                        cell["error"] = f"{type(exc).__name__}: {exc}"
                cells[member.id] = cell
            rows.append({"case": case.name, "n_sets": case.n_sets, "cells": cells})
        groups_out.append(
            {
                "key": group["key"],
                "title": group["title"],
                "objective": group["objective"],
                "metric": metric,
                "metric_label": METRICS[metric][1],
                "pending": group.get("pending"),
                "members": members_out,
                "rows": rows,
            }
        )

    self_check = _self_check(resolution)
    versions = _versions()
    return {
        "meta": {
            "corpus_source": CORPUS_SOURCE,
            "resolution": resolution,
            "timing_repeats": repeats,
            "python": sys.version.split()[0],
            "versions": versions,
            "method": (
                "Fitters grouped by the objective they minimize; each group "
                "scored on that objective's scale-invariant metric (a single "
                "multiplicative scale on fitted areas is absorbed). eunoia's "
                "loss is set via loss=; set-diagrams' via cost_function_objective."
            ),
        },
        "groups": groups_out,
        "self_check": self_check,
    }


def _self_check(resolution: int) -> list[dict]:
    """Rasterized stress vs eunoia's analytic stress (validates the rasterizer)."""
    ref = EunoiaAdapter("circle", loss="sum_squared")
    out: list[dict] = []
    if not ref.available:
        return out
    for case in CASES:
        try:
            rast = score(ref.fit(case), case.sets, case.regions, "stress", resolution)
            out.append(
                {
                    "case": case.name,
                    "rasterized": rast,
                    "native": ref.native_stress(case),
                }
            )
        except Exception:
            continue
    return out


def _versions() -> dict[str, str]:
    seen: dict[str, str] = {}
    for group in GROUPS:
        for m in group["members"]:
            if m.version is not None:
                seen[m.display] = m.version
    return seen


# --------------------------------------------------------------------------- #
# Artifact writers
# --------------------------------------------------------------------------- #
def _cell_text(cell: dict) -> str:
    status = cell.get("status")
    if status == "ok":
        return f"{cell['value']:.4f}"
    if status == "unsupported":
        return "—"
    if status == "not-installed":
        return "(not installed)"
    return "error"


def write_table(data: dict) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "<!-- Generated by `python -m benchmarks.run`. Do not edit by hand. -->",
        "",
    ]
    for group in data["groups"]:
        members = group["members"]
        lines.append(f"#### {group['title']}")
        lines.append("")
        lines.append(
            f"*Objective: {group['objective']}; "
            f"scored on `{group['metric']}` (lower is better).*"
        )
        lines.append("")
        header = ["Case", "Sets"] + [m["display"] for m in members]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "|".join(["---"] * len(header)) + "|")
        for row in group["rows"]:
            cells = [_cell_text(row["cells"][m["id"]]) for m in members]
            lines.append(
                f"| `{row['case']}` | {row['n_sets']} | " + " | ".join(cells) + " |"
            )
        lines.append("")
        if group.get("pending"):
            lines.append(f"*Not shown: {group['pending']}.*")
            lines.append("")
    (GENERATED_DIR / "benchmark_table.md").write_text("\n".join(lines).rstrip() + "\n")


def _time_lookup(data: dict, group_key: str, member_id: str, case: str):
    for g in data["groups"]:
        if g["key"] == group_key:
            for r in g["rows"]:
                if r["case"] == case:
                    return r["cells"].get(member_id, {}).get("time_ms")
    return None


def write_timing_table(data: dict) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "<!-- Generated by `python -m benchmarks.run`. Do not edit by hand. -->",
        "",
        "Median end-to-end `fit` wall-clock time in **milliseconds** "
        f"(median of {data['meta']['timing_repeats']} runs; lower is faster). "
        "Indicative only — timings are machine- and load-dependent.",
        "",
    ]
    header = ["Case", "Sets"] + [disp for _, _, disp in TIMING_MEMBERS]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for case in CASES:
        cells = []
        for gkey, mid, _ in TIMING_MEMBERS:
            ms = _time_lookup(data, gkey, mid, case.name)
            cells.append(f"{ms:.0f}" if ms is not None else "—")
        lines.append(f"| `{case.name}` | {case.n_sets} | " + " | ".join(cells) + " |")
    (GENERATED_DIR / "benchmark_timing.md").write_text("\n".join(lines) + "\n")


def make_timing_chart(data: dict) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    cmap = plt.get_cmap("tab10")
    x = np.arange(len(CASES))
    width = 0.8 / len(TIMING_MEMBERS)
    fig, ax = plt.subplots(figsize=(max(8, 1.1 * len(CASES)), 4.5))
    for i, (gkey, mid, disp) in enumerate(TIMING_MEMBERS):
        heights, positions = [], []
        for j, case in enumerate(CASES):
            ms = _time_lookup(data, gkey, mid, case.name)
            if ms is None:
                continue
            heights.append(ms)
            positions.append(x[j] + (i - (len(TIMING_MEMBERS) - 1) / 2) * width)
        ax.bar(positions, heights, width=width, label=disp, color=cmap(i))
    ax.set_yscale("log")
    ax.set_ylabel("median fit time (ms, log scale)")
    ax.set_xticks(x)
    ax.set_xticklabels(
        [f"{c.name}\n({c.n_sets}-set)" for c in CASES],
        rotation=45,
        ha="right",
        fontsize=7,
    )
    ax.legend(fontsize=8, ncol=2)
    ax.set_title("Wall-clock fit time by case (bars absent = unsupported)")
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "timing.png", dpi=130)
    plt.close(fig)


def make_group_charts(data: dict) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    groups = data["groups"]
    cmap = plt.get_cmap("tab10")
    fig, axes = plt.subplots(
        len(groups), 1, figsize=(max(8, 1.1 * len(CASES)), 4 * len(groups))
    )
    if len(groups) == 1:
        axes = [axes]
    x = np.arange(len(CASES))
    case_index = {c.name: i for i, c in enumerate(CASES)}
    for ax, group in zip(axes, groups, strict=True):
        members = group["members"]
        width = 0.8 / max(len(members), 1)
        rows = {r["case"]: r for r in group["rows"]}
        for i, m in enumerate(members):
            heights, positions = [], []
            for cname, j in case_index.items():
                cell = rows[cname]["cells"][m["id"]]
                if cell.get("status") != "ok":
                    continue
                heights.append(max(cell["value"], _PLOT_FLOOR))
                positions.append(x[j] + (i - (len(members) - 1) / 2) * width)
            ax.bar(positions, heights, width=width, label=m["display"], color=cmap(i))
        ax.set_yscale("log")
        ax.set_ylabel(f"{group['metric']}\n(lower is better)")
        ax.set_title(f"{group['title']} — {group['objective']}", fontsize=10)
        ax.set_xticks(x)
        ax.set_xticklabels(
            [f"{c.name}\n({c.n_sets}-set)" for c in CASES],
            rotation=45,
            ha="right",
            fontsize=7,
        )
        ax.axhline(_PLOT_FLOOR, color="0.85", lw=0.6)
        ax.legend(fontsize=7, ncol=2)
    fig.suptitle(
        "Within-objective comparison (each group scored on its own loss)",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.99))
    fig.savefig(FIGURE_DIR / "objective_groups.png", dpi=130)
    plt.close(fig)


def _draw_shapes(ax, shapes: list[Shape], sets: tuple[str, ...]) -> None:
    cmap = plt.get_cmap("tab10")
    color = {name: cmap(i % 10) for i, name in enumerate(sorted(sets))}
    for s in shapes:
        ax.add_patch(
            EllipsePatch(
                (s.cx, s.cy),
                width=2 * s.semi_major,
                height=2 * s.semi_minor,
                angle=np.degrees(s.rotation),
                facecolor=color[s.set],
                edgecolor="black",
                alpha=0.45,
                linewidth=0.8,
            )
        )
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.autoscale_view()


def make_gallery() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    cases = [c for c in CASES if c.name in GALLERY_CASES]
    members = GALLERY_MEMBERS
    fig, axes = plt.subplots(
        len(cases),
        len(members),
        figsize=(2.5 * len(members), 2.5 * len(cases)),
        squeeze=False,
    )
    for c, member in enumerate(members):
        axes[0][c].set_title(member.display, fontsize=10)
    for r, case in enumerate(cases):
        axes[r][0].set_ylabel(case.name, fontsize=9, rotation=90, labelpad=10)
        for c, member in enumerate(members):
            ax = axes[r][c]
            ax.set_xticks([])
            ax.set_yticks([])
            if not member.available or not member.supports(case):
                ax.text(
                    0.5,
                    0.5,
                    "—" if member.available else "n/a",
                    ha="center",
                    va="center",
                    fontsize=14,
                    color="0.6",
                )
                continue
            try:
                _draw_shapes(ax, member.fit(case), case.sets)
            except Exception:
                ax.text(0.5, 0.5, "error", ha="center", va="center", color="red")
    fig.suptitle("Fitted layouts on representative corpus cases", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    fig.savefig(FIGURE_DIR / "gallery.png", dpi=130)
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolution", type=int, default=None)
    parser.add_argument("--repeats", type=int, default=None)
    parser.add_argument("--quick", action="store_true", help="coarse, fast run")
    args = parser.parse_args(argv)

    resolution = args.resolution or (400 if args.quick else 1000)
    repeats = args.repeats or (2 if args.quick else 5)

    print(f"Running benchmark (resolution={resolution}, repeats={repeats})...")
    data = run_grid(resolution=resolution, repeats=repeats)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "results.json").write_text(json.dumps(data, indent=2) + "\n")
    write_table(data)
    write_timing_table(data)
    make_group_charts(data)
    make_timing_chart(data)
    make_gallery()

    worst = max(
        (abs(c["rasterized"] - c["native"]) for c in data["self_check"]),
        default=0.0,
    )
    print(f"  groups: {len(data['groups'])}  cases: {len(CASES)}")
    print(f"  stress self-check: max|rasterized - native| = {worst:.4f}")
    print(f"  wrote {RESULTS_DIR / 'results.json'}")
    print(f"  wrote {GENERATED_DIR / 'benchmark_table.md'}")
    print(f"  wrote {GENERATED_DIR / 'benchmark_timing.md'}")
    print(f"  wrote {FIGURE_DIR / 'objective_groups.png'}")
    print(f"  wrote {FIGURE_DIR / 'timing.png'}")
    print(f"  wrote {FIGURE_DIR / 'gallery.png'}")


if __name__ == "__main__":
    main()
