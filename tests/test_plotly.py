"""Tests for the optional interactive plotly backend (EulerFit.plot_plotly)."""

from __future__ import annotations

import pytest

pytest.importorskip("plotly")
pytest.importorskip("fontTools")

import eunoia as eu
import plotly.graph_objects as go


@pytest.fixture
def simple_fit() -> eu.EulerFit[eu.Circle]:
    return eu.euler({"A": 10, "B": 5, "A&B": 3})


@pytest.fixture
def member_fit() -> eu.EulerFit[eu.Circle]:
    return eu.euler(
        {"A": ["g1", "g2", "g3"], "B": ["g2", "g3", "g4"], "A&B": ["g2", "g3"]}
    )


def _fill_shapes(fig: go.Figure) -> list:
    """Region fill shapes: filled paths with no border (vs outlines/leaders)."""
    return [
        s
        for s in fig.layout.shapes
        if s.type == "path" and s.line.width == 0 and s.fillcolor != "rgba(0,0,0,0)"
    ]


def _n_pieces(fit: eu.EulerFit) -> int:
    pieces = fit.plot_data["region_pieces"]
    return sum(len(v) for combo, v in pieces.items() if combo)


def test_returns_figure(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    assert isinstance(simple_fit.plot_plotly(), go.Figure)


def test_region_fills_one_per_piece(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    fig = simple_fit.plot_plotly()
    assert len(_fill_shapes(fig)) == _n_pieces(simple_fit)


def test_empty_region_skipped(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    # The complement ("") region is never drawn as a fill.
    fig = simple_fit.plot_plotly()
    assert "" not in simple_fit.plot_data["region_pieces"] or len(
        _fill_shapes(fig)
    ) == _n_pieces(simple_fit)


def test_container_shape_when_complement() -> None:
    fit = eu.euler({"A": 10, "B": 5, "A&B": 3}, complement=30)
    assert fit.container is not None
    fig = fit.plot_plotly()
    rects = [s for s in fig.layout.shapes if s.type == "rect"]
    assert len(rects) == 1


def test_no_container_without_complement(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    fig = simple_fit.plot_plotly()
    assert not [s for s in fig.layout.shapes if s.type == "rect"]


def test_hover_trace_per_region(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    fig = simple_fit.plot_plotly()
    hover_traces = [t for t in fig.data if t.hoveron == "fills"]
    assert len(hover_traces) == _n_pieces(simple_fit)


def test_hover_members_in_text(member_fit: eu.EulerFit[eu.Circle]) -> None:
    fig = member_fit.plot_plotly(hover="members")
    texts = "\n".join(t.text for t in fig.data if t.hoveron == "fills")
    assert "g1" in texts and "g4" in texts


def test_hover_disabled(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    fig = simple_fit.plot_plotly(hover=False)
    assert not [t for t in fig.data if getattr(t, "hoveron", None) == "fills"]


def test_members_without_identities_raises(
    simple_fit: eu.EulerFit[eu.Circle],
) -> None:
    with pytest.raises(ValueError, match="member identities"):
        simple_fit.plot_plotly(members=True)


def test_quantities_render_annotations(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    plain = simple_fit.plot_plotly(quantities=False)
    with_q = simple_fit.plot_plotly(quantities=True)
    assert len(with_q.layout.annotations) > len(plain.layout.annotations)


def test_members_render_annotations(member_fit: eu.EulerFit[eu.Circle]) -> None:
    fig = member_fit.plot_plotly(members=True)
    joined = " ".join(a.text for a in fig.layout.annotations)
    assert "g1" in joined


def test_legend_traces(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    fig = simple_fit.plot_plotly(legend=True)
    assert fig.layout.showlegend
    legend_traces = [t for t in fig.data if t.showlegend]
    assert len(legend_traces) == len(simple_fit.shapes)


def test_colors_accepted(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    fig = simple_fit.plot_plotly(colors={"A": "red", "B": "blue"})
    assert _fill_shapes(fig)


def test_equal_aspect_layout(simple_fit: eu.EulerFit[eu.Circle]) -> None:
    fig = simple_fit.plot_plotly(width=500)
    assert fig.layout.yaxis.scaleanchor == "x"
    assert fig.layout.width == 500


def test_venn_plot_plotly() -> None:
    fig = eu.venn(3).plot_plotly()
    assert isinstance(fig, go.Figure)
    assert _fill_shapes(fig)


def test_exterior_leader_emitted() -> None:
    # Drive the leader path directly with a synthetic exterior placement so the
    # test is deterministic (the optimizer decides when a block goes outside).
    from eunoia._plotly import _draw_labels

    fig = go.Figure()
    placements = {
        "A": {
            "anchor": (5.0, 5.0),
            "kind": "exterior_raycast",
            "tether": (1.0, 1.0),
            "leader_end": (4.5, 4.5),
            "leader_waypoints": [(2.0, 2.0)],
        }
    }
    measured = {"A": [("A", {"color": "black", "fontsize": 11}, 0.5, 0.3)]}
    _draw_labels(fig, placements, measured)
    leaders = [s for s in fig.layout.shapes if s.type == "path" and s.line.width == 0.8]
    assert leaders
    assert len(fig.layout.annotations) == 1
