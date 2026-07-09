"""Axes-free text metrics for the plotly backend.

The matplotlib renderer measures text through a live ``Axes`` transform and an
``Agg`` renderer (see ``eunoia._plot._text_data_size``). The plotly backend has
no such renderer available synchronously, so it measures text here instead:
directly from the font's glyph-advance table via :mod:`fontTools`, independent
of any figure or transform.

The font file is located with matplotlib's ``font_manager`` (matplotlib is a
required dependency), but no matplotlib *rendering* is involved. The measured
sizes are in typographic points; the caller scales them to data units.

Metrics are necessarily approximate: plotly renders text in the browser with a
different font family than the one measured here, so glyph advances will not
match to the pixel. That is acceptable -- the size-aware placement only needs to
know roughly whether a label block fits its region, and hover tooltips cover the
case where a region is too small for text either way. The measurer is kept
behind :class:`TextMeasurer` so a browser-based or PIL metric could replace it.
"""

from __future__ import annotations

from functools import cache
from typing import Any, Protocol


class TextMeasurer(Protocol):
    """Measures a text string to a ``(width, height)`` size in points."""

    def text_size_points(self, text: str, fontsize: float) -> tuple[float, float]:
        """Return the ``(width, height)`` of ``text`` at ``fontsize`` points."""
        ...


@cache
def _find_font(family: str | None) -> str:
    """Locate a TTF/OTF path for ``family`` (or the default) via matplotlib."""
    from matplotlib.font_manager import FontProperties, findfont

    prop = FontProperties(family=family) if family is not None else FontProperties()
    return findfont(prop)


class FontMetrics:
    """Glyph-advance text metrics for a single font, read with fontTools.

    Width is the sum of horizontal advances of each character (missing glyphs
    fall back to the space advance, then ``.notdef``); height is the font's
    natural line height (ascent minus descent). Multi-line strings (``\\n``)
    take the widest line and the summed line heights.
    """

    def __init__(self, font: Any) -> None:
        # fontTools' table objects are dynamically typed (no stubs), so the
        # font is handled as ``Any`` and the results pinned to concrete types.
        self._cmap: dict[int, str] = font.getBestCmap() or {}
        self._hmtx: dict[str, tuple[int, int]] = font["hmtx"].metrics
        self._units_per_em: int = int(font["head"].unitsPerEm)
        hhea = font["hhea"]
        # ascent is positive, descent negative; their span is the line height.
        self._line_units: int = int(hhea.ascent) - int(hhea.descent)
        # Advance for characters with no glyph in this font.
        space_glyph = self._cmap.get(ord(" "))
        notdef = ".notdef" if ".notdef" in self._hmtx else next(iter(self._hmtx))
        self._fallback_advance: int = self._hmtx[space_glyph or notdef][0]

    @classmethod
    def load(cls, family: str | None = None) -> FontMetrics:
        """Build metrics for ``family`` (matplotlib's default when ``None``)."""
        from fontTools.ttLib import TTFont

        # ``fontNumber=0`` picks the first face of a TrueType collection (.ttc).
        return cls(TTFont(_find_font(family), fontNumber=0, lazy=True))

    def _advance_units(self, char: str) -> int:
        glyph = self._cmap.get(ord(char))
        if glyph is None:
            return self._fallback_advance
        return self._hmtx[glyph][0]

    def text_size_points(self, text: str, fontsize: float) -> tuple[float, float]:
        if not text:
            return 0.0, 0.0
        scale = fontsize / self._units_per_em
        lines = text.split("\n")
        width_units = max(
            (sum(self._advance_units(c) for c in line) for line in lines),
            default=0,
        )
        height_units = self._line_units * len(lines)
        return width_units * scale, height_units * scale


@cache
def default_measurer(family: str | None = None) -> FontMetrics:
    """Return a cached :class:`FontMetrics` for ``family`` (default when ``None``)."""
    return FontMetrics.load(family)
