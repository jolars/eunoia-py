"""Benchmark harness comparing eunoia against other Python Euler/Venn packages.

This package is *not* part of the installable ``eunoia`` distribution. It lives
in the repo as a developer tool: it runs the area-proportional fitters in the
Python ecosystem on a common corpus of set specifications, scores every fitter
with one package-independent fit-quality metric, and emits the tables and
figures consumed by ``docs/comparison.md``.

The competitor packages (``matplotlib-venn``, ``matplotlib-set-diagrams``) are
declared in the isolated ``benchmark`` dependency group so they never leak into
the runtime, ``dev``, or ``docs`` environments. See ``benchmarks/README.md``.
"""
