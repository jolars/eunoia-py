"""The common benchmark corpus.

Every fitter under test is driven from the *same* set specifications so the
comparison is apples-to-apples. The specs are a curated subset of the eunoia
Rust corpus at ``crates/eunoia/src/test_utils/corpus.rs`` (itself ported from
eulerr's ``tests/testthat/test-reproducibility.R`` plus real datasets from the
eulerr issue tracker). We keep the upstream names, difficulty classes, and
exclusive region values verbatim so results trace back to a known source.

All values are **exclusive** (per-region / "disjoint" in eulerr terms): the
value for ``"A&B"`` is the area in A and B but not in any other set. This is the
input form ``matplotlib-venn`` and ``matplotlib-set-diagrams`` both expect, so no
inclusion-exclusion conversion happens anywhere in the harness. (The single
inclusive corpus entry, ``issue44_4_set_inclusive``, is deliberately omitted to
keep every case in one scale.)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    """One benchmark specification.

    Attributes:
        name: Stable identifier (matches the eunoia corpus entry where ported).
        sets: Set names in canonical order. Geometry index ``i`` returned by a
            fitter corresponds to ``sets[i]``.
        regions: Exclusive area per region, keyed by canonical ``"A&B"`` strings
            (set names sorted, joined by ``"&"``). Regions absent from the dict
            are implicitly zero.
        n_sets: Number of base sets.
        category: Difficulty class from the corpus (``easy``/``medium``/``hard``).
        note: One-line description, including why the case is interesting.
    """

    name: str
    sets: tuple[str, ...]
    regions: dict[str, float]
    n_sets: int
    category: str
    note: str = ""

    @property
    def label(self) -> str:
        """Human-friendly label for tables and figure titles."""
        return f"{self.name} ({self.n_sets}-set, {self.category})"


def _case(
    name: str,
    sets: tuple[str, ...],
    regions: dict[str, float],
    category: str,
    note: str = "",
) -> Case:
    return Case(
        name=name,
        sets=sets,
        regions=regions,
        n_sets=len(sets),
        category=category,
        note=note,
    )


# Ordered roughly by set count so tables read 2 -> 6 sets.
CASES: list[Case] = [
    # -- 2 sets: exact for every fitter (two circles represent any 2-Venn) --
    _case(
        "two_disjoint",
        ("A", "B"),
        {"A": 10.0, "B": 9.0},
        "easy",
        "Two non-overlapping sets; baseline that everything fits exactly.",
    ),
    _case(
        "two_overlap",
        ("A", "B"),
        {"A": 3.0, "B": 2.0, "A&B": 2.0},
        "easy",
        "Plain 2-set overlap; closed-form-exact for circles.",
    ),
    # -- 3 sets --
    _case(
        "three_set_small_overlaps",
        ("A", "B", "C"),
        {
            "A": 10.0,
            "B": 10.0,
            "C": 10.0,
            "A&B": 2.0,
            "A&C": 2.0,
            "B&C": 2.0,
            "A&B&C": 0.5,
        },
        "easy",
        "Mild symmetric 3-set; circles handle it well.",
    ),
    _case(
        "uniform_3_set",
        ("A", "B", "C"),
        {
            "A": 10.0,
            "B": 10.0,
            "C": 10.0,
            "A&B": 4.0,
            "A&C": 4.0,
            "B&C": 4.0,
            "A&B&C": 2.0,
        },
        "medium",
        "Symmetric 3-Venn; circles cannot fit exactly (~2-3%), ellipses ~0.",
    ),
    _case(
        "eulerape_3_set",
        ("a", "b", "c"),
        {
            "a": 3491.0,
            "b": 3409.0,
            "c": 3503.0,
            "a&b": 120.0,
            "a&c": 114.0,
            "b&c": 132.0,
            "a&b&c": 126.0,
        },
        "medium",
        "Asymmetric 3-set from the eulerAPE article; circles miss the triple, "
        "ellipses fit near machine zero.",
    ),
    _case(
        "issue47_3_set_huge_triple",
        ("A", "B", "C"),
        {
            "A": 500.0,
            "B": 400.0,
            "C": 400.0,
            "A&B": 30.0,
            "A&C": 40.0,
            "B&C": 15.0,
            "A&B&C": 120.0,
        },
        "hard",
        "Tiny pairwise overlaps but a huge triple; geometrically impossible "
        "for circles, fittable by ellipses.",
    ),
    _case(
        "issue111_3_set_asymmetric",
        ("A", "B", "C"),
        {
            "A": 10000.0,
            "B": 1000.0,
            "C": 100.0,
            "A&B": 50.0,
            "A&C": 30.0,
            "B&C": 260.0,
            "A&B&C": 15.0,
        },
        "medium",
        "Two orders of magnitude scale variation across the three sets.",
    ),
    # -- 4 sets: beyond matplotlib-venn's cap --
    _case(
        "issue114_4_set_dominant_quad",
        ("A", "B", "C", "D"),
        {
            "A": 7516.0,
            "B": 7621.0,
            "C": 3152.0,
            "D": 26642.0,
            "A&B": 781.0,
            "A&C": 817.0,
            "A&D": 6418.0,
            "B&C": 369.0,
            "B&D": 1465.0,
            "C&D": 4118.0,
            "A&B&C": 324.0,
            "A&B&D": 2525.0,
            "A&C&D": 8847.0,
            "B&C&D": 1149.0,
            "A&B&C&D": 10336.0,
        },
        "hard",
        "Real biology-style 4-set; the 4-way intersection dominates.",
    ),
    _case(
        "issue103_4_set",
        ("A", "B", "C", "D"),
        {
            "A": 26.0,
            "B": 455.0,
            "C": 86.0,
            "D": 26.0,
            "A&B": 10.0,
            "A&C": 6.0,
            "A&D": 4.0,
            "B&C": 34.0,
            "B&D": 56.0,
            "C&D": 21.0,
            "A&B&C": 2.0,
            "A&B&D": 8.0,
            "A&C&D": 13.0,
            "B&C&D": 79.0,
            "A&B&C&D": 51.0,
        },
        "medium",
        "Fully populated 4-set (all 15 regions) from a real dataset.",
    ),
    # -- 5 sets --
    _case(
        "issue93_5_set_kinases",
        ("agc", "camk", "cmgc", "tk", "tkl"),
        {
            "agc": 9.0,
            "camk": 17.0,
            "cmgc": 16.0,
            "tk": 16.0,
            "tkl": 23.0,
            "agc&camk": 1.0,
            "camk&tk": 1.0,
            "tk&tkl": 1.0,
            "camk&cmgc&tkl": 1.0,
            "camk&tk&tkl": 2.0,
            "agc&camk&tk&tkl": 1.0,
            "camk&cmgc&tk&tkl": 3.0,
            "agc&camk&cmgc&tk&tkl": 1.0,
        },
        "hard",
        "Five protein-kinase families with sparse high-order overlaps "
        "(eulerr issue #93).",
    ),
    # -- 6 sets --
    _case(
        "wilkinson_6_set",
        ("A", "B", "C", "D", "E", "F"),
        {
            "A": 4.0,
            "B": 6.0,
            "C": 3.0,
            "D": 2.0,
            "E": 7.0,
            "F": 3.0,
            "A&B": 2.0,
            "A&F": 2.0,
            "B&C": 2.0,
            "B&D": 1.0,
            "B&F": 2.0,
            "C&D": 1.0,
            "D&E": 1.0,
            "E&F": 1.0,
            "A&B&F": 1.0,
            "B&C&D": 1.0,
        },
        "hard",
        "Classic Wilkinson 6-set layout; faithful only with ellipses.",
    ),
]


CASES_BY_NAME: dict[str, Case] = {c.name: c for c in CASES}


# Provenance string surfaced in results metadata and the docs report.
CORPUS_SOURCE = (
    "Ported from the eunoia Rust corpus "
    "(crates/eunoia/src/test_utils/corpus.rs), itself derived from eulerr's "
    "test-reproducibility.R and the eulerr issue tracker."
)
