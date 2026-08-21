"""Features surfaced from eunoia-core 1.8 and 1.9."""

from __future__ import annotations

from typing import Any

import matplotlib

matplotlib.use("Agg")

import eunoia as eu
import matplotlib.pyplot as plt
import pytest
from eunoia._eunoia import (
    _place_glyph_boxes,
    _place_glyphs,
    _place_labels,
    _place_set_labels,
)


def _rings(fit: eu.EulerFit[Any]) -> dict[str, list[list[tuple[float, float]]]]:
    out: dict[str, list[list[tuple[float, float]]]] = {}
    for combo, pieces in fit.plot_data["region_pieces"].items():
        out[combo] = [
            ring for piece in pieces for ring in [piece["outer"], *piece["holes"]]
        ]
    return out


def test_cma_es_optimizer_is_exposed() -> None:
    fit = eu.euler(
        {"A": 5, "B": 4, "A&B": 1},
        optimizer="cma_es",
        n_restarts=1,
        max_iterations=2,
        seed=1,
    )
    assert len(fit.shapes) == 2


def test_matched_label_placement_is_exposed() -> None:
    fit = eu.euler({"A": 10, "B": 10, "A&B": 3})
    placements = _place_labels(_rings(fit), {"A&B": (8.0, 4.0)}, exterior="matched")
    assert placements["A&B"]["kind"] == "exterior_matched"


def test_elbow_label_placement_is_exposed() -> None:
    fit = eu.euler({"A": 10, "B": 10, "A&B": 3})
    placements = _place_labels(_rings(fit), {"A&B": (8.0, 4.0)}, exterior="elbow")
    assert placements["A&B"]["kind"] == "exterior_elbow"
    assert placements["A&B"]["leader_waypoints"]


def test_set_labels_are_exterior_and_leaderless() -> None:
    fit = eu.euler({"A": 10, "B": 10, "A&B": 3})
    placements = _place_set_labels(
        fit.plot_data["shape_outlines"],
        {"A": (0.5, 0.2), "B": (0.5, 0.2)},
    )
    assert set(placements) == {"A", "B"}
    assert {p["kind"] for p in placements.values()} == {"exterior_set"}
    assert all(p["tether"] is None for p in placements.values())


def test_unit_glyph_binding_places_requested_counts() -> None:
    fit = eu.euler({"A": 4, "B": 3, "A&B": 2})
    placed = _place_glyphs(_rings(fit), {"A": 4, "B": 3, "A&B": 2})
    assert placed["radius"] > 0
    assert {k: len(v) for k, v in placed["positions"].items()} == {
        "A": 4,
        "B": 3,
        "A&B": 2,
    }
    assert placed["unplaced"] == {}


def test_member_box_binding_returns_scale_and_boxes() -> None:
    fit = eu.euler({"A": 4, "B": 3, "A&B": 2})
    placed = _place_glyph_boxes(
        _rings(fit),
        {"A": [(0.2, 0.1), (0.3, 0.1)], "A&B": [(0.2, 0.1)]},
    )
    assert 0 < placed["scale"] <= 1
    assert len(placed["boxes"]["A"]) == 2
    assert len(placed["boxes"]["A&B"]) == 1


def test_plot_glyphs_draws_one_circle_per_unit() -> None:
    fit = eu.euler({"A": 4, "B": 3, "A&B": 2})
    ax = fit.plot(glyphs=True, labels=False)
    circles = [p for p in ax.patches if p.__class__.__name__ == "Circle"]
    assert len(circles) == 9
    plt.close(ax.figure)


def test_plot_glyphs_rejects_fractional_quantities() -> None:
    fit = eu.euler({"A": 1.5, "B": 2})
    with pytest.raises(ValueError, match="integer"):
        fit.plot(glyphs=True)


def test_inclusive_glyph_counts_come_from_exclusive_regions() -> None:
    fit = eu.euler({"A": 3, "B": 2, "A&B": 1}, input="inclusive")
    assert fit.plot_data["requested_exclusive"] == {"A": 2, "B": 1, "A&B": 1}
    ax = fit.plot(glyphs=True, labels=False)
    circles = [p for p in ax.patches if p.__class__.__name__ == "Circle"]
    assert len(circles) == 4
    plt.close(ax.figure)


def test_venn_glyph_counts_use_supplied_quantities() -> None:
    fit = eu.venn({"A": 2, "B": 1, "A&B": 1})
    ax = fit.plot(glyphs=True, labels=False, quantities=False)
    circles = [p for p in ax.patches if p.__class__.__name__ == "Circle"]
    assert len(circles) == 4
    plt.close(ax.figure)


def test_glyphs_without_quantities_raise() -> None:
    with pytest.raises(ValueError, match="quantities"):
        eu.venn(2).plot(glyphs=True)


def test_plot_members_packed_draws_names_individually() -> None:
    fit = eu.euler({"A": ["alice", "bob"], "B": ["bob", "carol"]})
    ax = fit.plot(members={"mode": "packed"}, labels=False)
    texts = [text.get_text() for text in ax.texts]
    assert {"alice", "bob", "carol"} <= set(texts)
    assert not any("\n" in text for text in texts)
    plt.close(ax.figure)


def test_plot_exterior_set_labels_have_no_leaders() -> None:
    fit = eu.euler({"Alpha": 5, "Beta": 4, "Alpha&Beta": 1})
    ax = fit.plot(labels={"set_position": "outside"}, quantities=False)
    assert {t.get_text() for t in ax.texts} >= {"Alpha", "Beta"}
    assert len(ax.lines) == 0
    plt.close(ax.figure)
