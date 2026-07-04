"""Member-name retention and rendering (``ids=`` / ``plot(members=...)``)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import eunoia as eu
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pytest
from eunoia._parse import parse_membership_input

# --- parse layer -----------------------------------------------------------


def test_parse_membership_returns_sorted_member_map() -> None:
    combos, members = parse_membership_input(
        {"A": ["bob", "alice"], "B": ["alice", "carol"]}
    )
    assert dict(combos) == {"A": 1.0, "B": 1.0, "A&B": 1.0}
    # alice is in both sets -> the intersection; names sorted within each region.
    assert members == {"A": ["bob"], "B": ["carol"], "A&B": ["alice"]}


def test_parse_membership_canonical_keys_and_dedup() -> None:
    # "B&A" must land under canonical "A&B"; duplicates within a set collapse.
    _, members = parse_membership_input({"B": ["y", "y"], "A": ["y"]})
    assert members == {"A&B": ["y"]}


# --- euler membership-list input -------------------------------------------


def test_euler_membership_populates_members() -> None:
    fit = eu.euler(
        {
            "A": ["alice", "bob", "carol"],
            "B": ["bob", "carol", "dave"],
            "C": ["carol", "dave", "erin"],
        }
    )
    assert fit.members == {
        "A": ["alice"],
        "A&B": ["bob"],
        "A&B&C": ["carol"],
        "B&C": ["dave"],
        "C": ["erin"],
    }


def test_euler_area_input_has_no_members() -> None:
    assert eu.euler({"A": 10, "B": 5, "A&B": 3}).members is None


def test_euler_membership_rejects_ids() -> None:
    with pytest.raises(eu.EunoiaError):
        eu.euler({"A": ["x", "y"]}, ids=["x", "y"])


def test_euler_area_rejects_ids() -> None:
    with pytest.raises(eu.EunoiaError):
        eu.euler({"A": 10, "B": 5, "A&B": 3}, ids=["x"])


# --- numpy array input with ids= -------------------------------------------


def test_euler_array_ids_populates_members() -> None:
    arr = np.array([[1, 0], [1, 1], [0, 1], [1, 1]])
    fit = eu.euler(arr, names=["X", "Y"], ids=["r1", "r2", "r3", "r4"])
    assert fit.members == {"X": ["r1"], "Y": ["r3"], "X&Y": ["r2", "r4"]}


def test_euler_array_without_ids_has_no_members() -> None:
    arr = np.array([[1, 0], [0, 1]])
    assert eu.euler(arr, names=["X", "Y"]).members is None


def test_euler_array_ids_wrong_length_raises() -> None:
    arr = np.array([[1, 0], [1, 1], [0, 1]])
    with pytest.raises(eu.EunoiaError):
        eu.euler(arr, names=["X", "Y"], ids=["only", "two"])


def test_euler_array_ids_as_str_raises() -> None:
    arr = np.array([[1, 0], [0, 1]])
    with pytest.raises(eu.EunoiaError):
        eu.euler(arr, names=["X", "Y"], ids="a_column")


# --- DataFrame input with ids= ---------------------------------------------

pd = pytest.importorskip("pandas")
pl = pytest.importorskip("polars")

Builder = Callable[[dict[str, list[Any]]], Any]
BACKENDS: list[tuple[str, Builder]] = [
    ("pandas", lambda cols: pd.DataFrame(cols)),
    ("polars", lambda cols: pl.DataFrame(cols)),
]


@pytest.fixture(params=BACKENDS, ids=[name for name, _ in BACKENDS])
def frame(request: pytest.FixtureRequest) -> Builder:
    return request.param[1]


def test_euler_dataframe_ids_column_excluded_and_members(frame: Builder) -> None:
    df = frame(
        {
            "A": [1, 1, 0, 1],
            "B": [0, 1, 1, 1],
            "who": ["r1", "r2", "r3", "r4"],
        }
    )
    fit = eu.euler(df, ids="who")
    # The id column is not a set.
    assert {s.set for s in fit.shapes} == {"A", "B"}
    assert fit.members == {"A": ["r1"], "B": ["r3"], "A&B": ["r2", "r4"]}


def test_euler_dataframe_ids_sequence(frame: Builder) -> None:
    df = frame({"A": [1, 0], "B": [1, 1]})
    fit = eu.euler(df, ids=["m1", "m2"])
    assert fit.members == {"A&B": ["m1"], "B": ["m2"]}


def test_euler_dataframe_without_ids_has_no_members(frame: Builder) -> None:
    df = frame({"A": [1, 0], "B": [1, 1]})
    assert eu.euler(df).members is None


def test_euler_dataframe_unknown_ids_column_raises(frame: Builder) -> None:
    df = frame({"A": [1, 0], "B": [1, 1]})
    with pytest.raises(eu.EunoiaError):
        eu.euler(df, ids="missing")


# --- venn ------------------------------------------------------------------


def test_venn_membership_populates_members() -> None:
    v = eu.venn({"A": ["x", "y"], "B": ["y", "z"]})
    assert v.members == {"A": ["x"], "B": ["z"], "A&B": ["y"]}


def test_venn_int_has_no_members() -> None:
    assert eu.venn(3).members is None


def test_venn_array_ids_populates_members() -> None:
    arr = np.array([[1, 0], [1, 1]])
    v = eu.venn(arr, names=["X", "Y"], ids=["a", "b"])
    assert v.members == {"X": ["a"], "X&Y": ["b"]}


def test_venn_int_rejects_ids() -> None:
    with pytest.raises(eu.EunoiaError):
        eu.venn(3, ids=["x"])  # type: ignore[call-overload]


# --- rendering -------------------------------------------------------------


@pytest.fixture
def member_fit() -> eu.EulerFit[eu.Circle]:
    return eu.euler(
        {
            "A": ["alice", "bob", "carol", "dave"],
            "B": ["carol", "dave", "erin"],
        },
        shape="circle",
    )


def test_plot_members_draws_names(member_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = member_fit.plot(members=True)
    joined = "\n".join(t.get_text() for t in ax.texts)
    for name in ("alice", "bob", "carol", "dave", "erin"):
        assert name in joined
    plt.close(ax.figure)


def test_plot_members_off_by_default(member_fit: eu.EulerFit[eu.Circle]) -> None:
    ax = member_fit.plot()
    joined = "\n".join(t.get_text() for t in ax.texts)
    assert "alice" not in joined
    plt.close(ax.figure)


def test_plot_members_max_truncates(member_fit: eu.EulerFit[eu.Circle]) -> None:
    # A&B = {carol, dave}; with max=1 the second becomes a "+1 more" line.
    ax = member_fit.plot(members={"max": 1})
    assert any("more" in t.get_text() for t in ax.texts)
    plt.close(ax.figure)


def test_plot_members_bad_max_raises(member_fit: eu.EulerFit[eu.Circle]) -> None:
    with pytest.raises(ValueError):
        member_fit.plot(members={"max": 0})


def test_plot_members_on_area_fit_raises() -> None:
    fit = eu.euler({"A": 10, "B": 5, "A&B": 3})
    with pytest.raises(ValueError):
        fit.plot(members=True)


def test_plot_members_style_option_applied(member_fit: eu.EulerFit[eu.Circle]) -> None:
    with eu.options(members={"color": "navy"}):
        ax = member_fit.plot(members=True)
        # Each region's members render as one newline-joined text block.
        member_texts = [t for t in ax.texts if "alice" in t.get_text()]
        assert member_texts
        assert all(t.get_color() == "navy" for t in member_texts)
    plt.close(ax.figure)
