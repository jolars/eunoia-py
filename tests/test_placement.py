"""Size-aware label placement: the `_place_labels` binding and its use in the
renderer (leaders for blocks that don't fit, none for blocks that do)."""

from __future__ import annotations

from typing import Any

import matplotlib

matplotlib.use("Agg")

import eunoia as eu
import matplotlib.pyplot as plt
import pytest
from eunoia._eunoia import _place_labels


def _rings(fit: eu.EulerFit[Any]) -> dict[str, list[list[tuple[float, float]]]]:
    """Flatten a fit's region pieces to a list of boundary rings per region."""
    out: dict[str, list[list[tuple[float, float]]]] = {}
    pieces = fit.plot_data["region_pieces"]
    for combo, plist in pieces.items():
        if combo == "":
            continue
        rings: list[list[tuple[float, float]]] = []
        for piece in plist:
            rings.append(piece["outer"])
            rings.extend(piece["holes"])
        out[combo] = rings
    return out


def test_place_labels_small_blocks_are_interior() -> None:
    fit = eu.euler({"A": 10, "B": 10, "A&B": 3})
    rings = _rings(fit)
    sizes = {c: (0.2, 0.1) for c in rings}
    placements = _place_labels(rings, sizes)
    assert set(placements) == set(rings)
    for pl in placements.values():
        assert pl["kind"] == "interior"
        assert pl["tether"] is None
        assert pl["leader_end"] is None
        assert pl["leader_waypoints"] == []


def test_place_labels_oversized_block_goes_exterior() -> None:
    fit = eu.euler({"A": 10, "B": 10, "A&B": 3})
    rings = _rings(fit)
    # A block far larger than the thin A&B lens cannot fit inside it.
    sizes = {"A&B": (8.0, 4.0)}
    placements = _place_labels(rings, sizes, exterior="raycast")
    pl = placements["A&B"]
    assert pl["kind"].startswith("exterior")
    assert pl["tether"] is not None
    assert pl["leader_end"] is not None


def test_place_labels_rejects_bad_exterior() -> None:
    fit = eu.euler({"A": 10, "B": 10, "A&B": 3})
    rings = _rings(fit)
    try:
        _place_labels(rings, {"A": (0.1, 0.1)}, exterior="nope")
    except eu.EunoiaError as exc:
        assert "exterior" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected EunoiaError for bad exterior policy")


def test_plot_unfittable_label_gets_leader() -> None:
    # The pathological 4-set case where every region has count 1: some set
    # blocks cannot fit their slivers and must be pushed out with a leader line.
    fit = eu.euler(
        {
            "Ether": ["alice", "bob", "carol", "dave", "erin"],
            "Bitcoin": ["bob", "carol", "frank", "grace"],
            "Doge": ["carol", "dave", "grace", "heidi", "ivan"],
            "Litecoin": ["alice", "frank", "grace", "ivan", "judy"],
        },
        shape="ellipse",
        seed=1,
    )
    ax = fit.plot(quantities=True)
    # Leaders are drawn as Line2D artists; fills/edges are PathPatches.
    assert len(ax.lines) >= 1
    plt.close(ax.figure)


def test_plot_clean_diagram_has_no_leaders() -> None:
    # A diagram where every set has a roomy exclusive region needs no exterior
    # placement, so no leader lines should be drawn.
    fit = eu.euler(
        {
            "Ether": ["alice", "bob", "carol", "dave"],
            "Bitcoin": ["carol", "erin", "frank", "grace"],
            "Doge": ["frank", "heidi", "ivan", "judy"],
            "Litecoin": ["judy", "alice", "mallory", "niaj"],
        },
        shape="ellipse",
        seed=1,
    )
    ax = fit.plot(quantities=True)
    assert len(ax.lines) == 0
    plt.close(ax.figure)


def test_measured_block_size_matches_rendered() -> None:
    """Regression: text is measured against ``transData``, whose x/y scales are
    only equalized once the aspect is applied. Measuring before ``apply_aspect``
    under-measures width, so the core is told a too-narrow box and the drawn
    text overflows its region. The size we feed the core must match what renders.
    """
    from eunoia import _plot

    captured: dict[str, tuple[float, float]] = {}
    orig = _plot._place_labels

    def spy(
        rings: Any,
        sizes: dict[str, tuple[float, float]],
        container: Any = None,
        exterior: str = "raycast",
    ) -> Any:
        captured.update(sizes)  # last round wins, matching the final placement
        return orig(rings, sizes, container, exterior=exterior)

    _plot._place_labels = spy
    try:
        # A horizontal two-circle layout: the data bbox is wider than tall, so a
        # stale (non-equal-aspect) transform mismeasures width by ~34%.
        fit = eu.euler({"Alpha": 10, "B": 10, "Alpha&B": 4})
        ax = fit.plot(labels=True, quantities=False)
    finally:
        _plot._place_labels = orig

    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    text = next(t for t in ax.texts if t.get_text() == "Alpha")
    bb = text.get_window_extent(renderer)
    (x0, y0) = inv.transform((bb.x0, bb.y0))
    (x1, y1) = inv.transform((bb.x1, bb.y1))
    rendered_w, rendered_h = abs(x1 - x0), abs(y1 - y0)

    fed_w, fed_h = captured["Alpha"]
    assert rendered_w == pytest.approx(fed_w, rel=0.05)
    assert rendered_h == pytest.approx(fed_h, rel=0.05)
    plt.close(fig)
