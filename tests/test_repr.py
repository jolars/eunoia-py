from __future__ import annotations

import eunoia as eu


def test_repr_includes_metadata() -> None:
    fit = eu.euler({"A": 10, "B": 5, "A&B": 3})
    text = repr(fit)
    assert "EulerFit" in text
    assert "2 circles" in text
    assert "diag_error=" in text
    assert "stress=" in text


def test_repr_has_table_header() -> None:
    fit = eu.euler({"A": 10, "B": 5, "A&B": 3})
    text = repr(fit)
    assert "original" in text
    assert "fitted" in text
    assert "residual" in text
    assert "regionError" in text


def test_repr_lists_each_region() -> None:
    fit = eu.euler({"A": 10, "B": 5, "A&B": 3})
    text = repr(fit)
    for key in ("A", "B", "A&B"):
        assert key in text


def test_repr_is_str_returnable() -> None:
    fit = eu.euler({"A": 10, "B": 5, "A&B": 3})
    s = str(fit)
    assert isinstance(s, str)
    assert len(s) > 0


def test_repr_for_ellipses_says_ellipses() -> None:
    fit = eu.euler({"A": 10, "B": 5, "A&B": 3}, shape="ellipse")
    text = repr(fit)
    assert "ellipses" in text


def test_repr_for_rotated_rectangles_says_rotated_rectangles() -> None:
    fit = eu.euler({"A": 10, "B": 5, "A&B": 3}, shape="rotated_rectangle", seed=1)
    assert "rotated rectangles" in repr(fit)
    assert "rotatedrectangles" not in repr(fit)
