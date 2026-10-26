"""Quantity labels shared by the matplotlib and plotly backends."""

from __future__ import annotations

from collections import Counter
from typing import Any

import matplotlib

matplotlib.use("Agg")

import eunoia as eu
import matplotlib.pyplot as plt
import pytest


def _texts(
    fit: eu.EulerFit[Any], backend: str, quantities: bool | str | dict[str, Any] | None
) -> list[str]:
    if backend == "plotly":
        pytest.importorskip("plotly")
        pytest.importorskip("fontTools")
        fig = fit.plot_plotly(labels=False, quantities=quantities, hover=False)
        return [a.text.replace("<br>", "\n") for a in fig.layout.annotations]
    ax = fit.plot(labels=False, quantities=quantities)
    try:
        return [text.get_text() for text in ax.texts]
    finally:
        plt.close(ax.figure)


@pytest.fixture(scope="module")
def complement_fit() -> eu.EulerFit[eu.Circle]:
    return eu.euler({"A": 10, "B": 8, "A&B": 4}, complement=20, seed=0)


@pytest.mark.parametrize("backend", ["matplotlib", "plotly"])
@pytest.mark.parametrize("quantities", [True, "original", "counts", {}])
def test_requested_complement_quantity(
    complement_fit: eu.EulerFit[eu.Circle],
    backend: str,
    quantities: bool | str | dict[str, Any],
) -> None:
    assert Counter(_texts(complement_fit, backend, quantities)) == Counter(
        ["10", "8", "4", "20"]
    )


@pytest.mark.parametrize("backend", ["matplotlib", "plotly"])
@pytest.mark.parametrize("supplied_values", [False, True])
def test_fitted_complement_quantity(backend: str, supplied_values: bool) -> None:
    fit = eu.venn({"A": 10, "B": 8, "A&B": 4} if supplied_values else 2, complement=20)
    assert fit.plot_data["region_areas"][""] != pytest.approx(20)
    expected = [f"{v:.3g}" for v in fit.fitted_values.values()]
    expected.append(f"{fit.plot_data['region_areas']['']:.3g}")
    assert Counter(_texts(fit, backend, "fitted")) == Counter(expected)


@pytest.mark.parametrize("backend", ["matplotlib", "plotly"])
@pytest.mark.parametrize("display", ["percent", ["counts", "percent"]])
def test_complement_percentages_use_requested_universe(
    complement_fit: eu.EulerFit[eu.Circle], backend: str, display: str | list[str]
) -> None:
    percentages = ["23.8%", "19%", "9.52%", "47.6%"]
    expected = (
        [
            f"{count}\n({pct})"
            for count, pct in zip([10, 8, 4, 20], percentages, strict=True)
        ]
        if isinstance(display, list)
        else percentages
    )
    assert Counter(_texts(complement_fit, backend, {"type": display})) == Counter(
        expected
    )


@pytest.mark.parametrize("backend", ["matplotlib", "plotly"])
@pytest.mark.parametrize("source", ["original", "fitted"])
def test_inclusive_percentages_use_exclusive_universe(
    backend: str, source: str
) -> None:
    fit = eu.euler(
        {"A": 14, "B": 12, "A&B": 4}, input="inclusive", complement=20, seed=0
    )
    assert Counter(
        _texts(fit, backend, {"source": source, "type": "percent"})
    ) == Counter(["33.3%", "28.6%", "9.52%", "47.6%"])


@pytest.mark.parametrize("backend", ["matplotlib", "plotly"])
def test_fitted_percentages_use_geometric_universe(backend: str) -> None:
    fit = eu.venn({"A": 10, "B": 8, "A&B": 4}, complement=20)
    assert fit.container is not None
    total = fit.container.width * fit.container.height
    expected = [f"{v / total * 100:.3g}%" for v in fit.fitted_values.values()]
    expected.append(f"{fit.plot_data['region_areas'][''] / total * 100:.3g}%")
    assert Counter(
        _texts(fit, backend, {"source": "fitted", "type": "percent"})
    ) == Counter(expected)


@pytest.mark.parametrize("backend", ["matplotlib", "plotly"])
def test_complement_quantities_off(
    complement_fit: eu.EulerFit[eu.Circle], backend: str
) -> None:
    assert _texts(complement_fit, backend, False) == []


@pytest.mark.parametrize("backend", ["matplotlib", "plotly"])
def test_venn_complement_quantities_follow_context_default(backend: str) -> None:
    fit = eu.venn({"A": 10, "B": 8, "A&B": 4}, complement=20)
    assert Counter(_texts(fit, backend, None)) == Counter(["10", "8", "4", "20"])
    assert _texts(eu.venn(2, complement=20), backend, None) == []


@pytest.mark.parametrize("backend", ["matplotlib", "plotly"])
def test_complement_quantities_preserve_fit_values(backend: str) -> None:
    fit = eu.euler({"A": 10, "B": 8, "A&B": 4}, complement=20, seed=0)
    original = dict(fit.original_values)
    fitted = dict(fit.fitted_values)
    _texts(fit, backend, "original")
    _texts(fit, backend, "fitted")
    assert fit.original_values == original
    assert fit.fitted_values == fitted
