"""Generate the README hero figure.

Run from the repo root with the dev env active:

    python docs/_static/make_hero.py

Writes ``docs/_static/hero.png`` --- a three-panel showcase (Euler circles,
ellipse fit, and a Venn diagram) used at the top of the README.
"""

from __future__ import annotations

import eunoia as eu
import matplotlib.pyplot as plt

PALETTE = ["#e41a1c", "#377eb8", "#4daf4a"]

fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.6))

# 1. Area-proportional Euler diagram from per-region counts.
euler = eu.euler({"A": 10, "B": 7, "C": 6, "A&B": 3, "A&C": 2, "B&C": 2, "A&B&C": 1})
euler.plot(ax=axes[0], colors=PALETTE, quantities=True, labels=False)
axes[0].set_title("euler() — circles")

# 2. Ellipses fit three-set arrangements circles cannot.
ellipse = eu.euler(
    {"A": 2, "B": 2, "C": 2, "A&B": 1, "A&C": 1, "B&C": 1, "A&B&C": 0.5},
    shape="ellipse",
)
ellipse.plot(ax=axes[1], colors=PALETTE, labels=True)
axes[1].set_title("euler(shape='ellipse')")

# 3. Topological Venn diagram (all regions shown).
venn = eu.venn(["A", "B", "C"])
venn.plot(ax=axes[2], colors=PALETTE, labels=True)
axes[2].set_title("venn()")

fig.tight_layout()
fig.savefig("docs/_static/hero.png", dpi=150, bbox_inches="tight")
print("wrote docs/_static/hero.png")
