"""Reproduce rendering symptoms from the eunoia 0.6.0 HTML report.

Run from this repository's environment:
    python examples/report_repro.py /tmp/eunoia-report

The membership data and seed 0 come from https://github.com/jolars/eunoia/issues/133.
Long-name variants append a synthetic suffix without changing membership.
Images are diagnostic examples, not pixel-for-pixel reconstructions of the
report's unspecified rendering settings. See TODO.md for ownership.
"""

from __future__ import annotations

import argparse
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import eunoia as eu
import matplotlib.pyplot as plt

# Preserve the original memberships so missing names can be checked directly.
DATA = {
    "Atorvastatin": [
        "ABCA1",
        "ABCB1",
        "ACE",
        "AGTR1",
        "APOA5",
        "APOB",
        "BDKRB2",
        "BGLAP",
        "CACNA1S",
        "CD40LG",
        "CLMN",
        "CXCL10",
        "CYP3A4",
        "CYP3A7",
        "DRD3",
        "FAS",
        "FGF2",
        "HLA-DRB1",
        "HMGCR",
        "HSPD1",
        "IFNL3",
        "IFNL4",
        "IL2RA",
        "ITGAM",
        "LEPR",
        "LIPC",
        "MAPK10",
        "MTHFR",
        "MYLIP",
        "NOS1",
        "NOS3",
        "NR1I2",
        "PIK3CG",
        "POR",
        "PPARD",
        "PRDM16",
        "RYR1",
        "SLCO1B1",
        "SOAT1",
        "TFPI",
        "TGM2",
        "TNF",
        "UGT1A1",
        "UGT1A10",
        "UGT1A3",
        "UGT1A4",
        "UGT1A5",
        "UGT1A6",
        "UGT1A7",
        "UGT1A8",
        "UGT1A9",
    ],
    "Simvastatin": [
        "ABCA1",
        "ABCB1",
        "ABCC2",
        "ABCG8",
        "APOA5",
        "AR",
        "BDNF",
        "CACNA1S",
        "CCR2",
        "CEL",
        "CYBA",
        "CYP1A2",
        "CYP2C19",
        "CYP2C8",
        "CYP2C9",
        "CYP2D6",
        "CYP3A4",
        "CYP3A5",
        "F3",
        "HLA-DRB1",
        "HLA-G",
        "HMGCR",
        "ICMT",
        "IDH1",
        "IL17A",
        "LEPR",
        "LIF",
        "LIPC",
        "MMP2",
        "NFE2L2",
        "NR1I2",
        "NR2E3",
        "PIK3CG",
        "PLK1",
        "PLTP",
        "PON1",
        "PRDM16",
        "RHOA",
        "RYR1",
        "SCAP",
        "SLCO2B1",
        "THBD",
        "THBS1",
        "TPM3",
        "UGT1A9",
        "ZNF542P",
    ],
    "Sunitinib": [
        "BAP1",
        "CA9",
        "CSF1R",
        "CXCL8",
        "CYP3A4",
        "EWSR1",
        "FGFR1",
        "FGFR2",
        "FLT1",
        "FLT3",
        "FLT4",
        "HIF1A",
        "HMOX1",
        "IL4R",
        "KDM5C",
        "KDR",
        "KIT",
        "MKI67",
        "NOS3",
        "NR1I2",
        "NR1I3",
        "PBRM1",
        "PDGFA",
        "PDGFB",
        "PDGFC",
        "PDGFD",
        "PDGFRA",
        "PDGFRB",
        "POR",
        "PTEN",
        "PTPN12",
        "PTPRB",
        "RET",
        "SLC22A5",
        "TP53",
        "VEGFA",
        "VEGFC",
        "VHL",
        "YES1",
    ],
}


def membership(*, long_names: bool = False) -> dict[str, list[str]]:
    return {
        name: [f"{gene}_long_member_name" if long_names else gene for gene in genes]
        for name, genes in DATA.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    eu.reset_options()
    print(f"eunoia={version('eunoia')}, matplotlib={matplotlib.__version__}")

    fit = eu.euler(membership(), seed=0, n_restarts=10, n_threads=1)
    triple = "Atorvastatin&Simvastatin&Sunitinib"
    print(
        f"triple: requested={fit.original_values[triple]}, "
        f"fitted={fit.fitted_values.get(triple, 0):.6g}, "
        f"polygon_present={triple in fit.plot_data['region_pieces']}"
    )

    cases = [
        ("packed-short", (15, 3), "packed", {}, {}),
        (
            "packed-boundary",
            (15, 3),
            "packed",
            {"placement": {"tether": "boundary"}},
            {},
        ),
        ("packed-roomy", (15, 15), "packed", {}, {}),
        ("packed-large-font", (10, 10), "packed", {"fontsize": 28}, {"fontsize": 20}),
        ("list-roomy", (15, 15), "list", {}, {}),
        ("packed-monospace", (15, 3), "packed", {}, {"fontfamily": "DejaVu Sans Mono"}),
    ]
    for filename, figsize, mode, labels, members in cases:
        fig, ax = plt.subplots(figsize=figsize, dpi=100)
        fit.plot(ax=ax, labels=labels, members={"mode": mode, **members})
        fig.canvas.draw()
        member_names = {name for names in membership().values() for name in names}
        drawn_names = {text.get_text() for text in ax.texts}
        if mode == "packed":
            missing = len(member_names - drawn_names)
            print(f"{filename}: members missing from artists={missing}")
        fig.savefig(args.output / f"{filename}.png")
        plt.close(fig)

    long_fit = eu.euler(membership(long_names=True), seed=0, n_restarts=10, n_threads=1)
    for mode in ["packed", "list"]:
        fig, ax = plt.subplots(figsize=(15, 15), dpi=100)
        long_fit.plot(ax=ax, members={"mode": mode})
        fig.savefig(args.output / f"long-{mode}.png")
        plt.close(fig)

    ellipse = eu.euler(
        membership(), shape="ellipse", seed=0, n_restarts=10, n_threads=1
    )
    print(f"ellipse triple fitted={ellipse.fitted_values.get(triple, 0):.6g}")
    fig, ax = plt.subplots(figsize=(15, 15), dpi=100)
    ellipse.plot(ax=ax, members={"mode": "packed"})
    fig.savefig(args.output / "ellipse-control.png")
    plt.close(fig)

    try:
        import plotly  # noqa: F401
    except ImportError:
        print("Plotly extra is not installed; skipping title examples.")
    else:
        fig = fit.plot_plotly()
        fig.update_layout(title="Title with default margins")
        print(f"Plotly default top margin={fig.layout.margin.t}")
        fig.write_html(args.output / "plotly-title-default.html")
        fig.update_layout(title="Title with top margin", margin={"t": 50})
        fig.write_html(args.output / "plotly-title-margin.html")


if __name__ == "__main__":
    main()
