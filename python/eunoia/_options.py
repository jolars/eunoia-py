"""Global plotting defaults for eunoia (eulerr's ``eulerr_options`` analogue).

A single callable, :func:`options`, both reads and sets the defaults that
:func:`eunoia._plot.render` falls back to, and doubles as a context manager for
scoped overrides::

    eu.options(fills={"alpha": 0.6})        # set globally, returns prior values
    eu.options()                            # read a snapshot of the current options
    with eu.options(labels={"fontsize": 14}):
        fit.plot()                          # restored to prior on exit

Options are grouped into categories that mirror the keyword dictionaries in
``_plot.render``: ``fills``, ``edges``, ``labels``, ``quantities``, ``members``,
``legend``, ``glyphs``, and ``complement`` are each a dict of plotting options,
while ``palette`` is the default color source (a colormap name or a sequence of
colors) used when ``plot(colors=...)`` is not given.

Precedence inside ``render`` is: an explicit ``plot(...)`` keyword argument >
the active option (a context override or the global value) > the built-in
fallback baked into these defaults.

State lives in a :class:`contextvars.ContextVar`, so ``with`` blocks are
exception-safe and isolated across threads and async tasks (the same reason
matplotlib's ``rc_context`` and pandas' ``option_context`` do it this way).
"""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar
from copy import deepcopy
from typing import Any

__all__ = ["get_options", "options", "reset_options"]

# Built-in fallbacks. Each mapping category holds matplotlib kwargs; ``palette``
# is a colormap name (or a sequence of colors). These are the literals that used
# to live inline in ``_plot.render``.
_DEFAULTS: dict[str, Any] = {
    "palette": "tab10",
    "fills": {"alpha": 0.5},
    "edges": {"linewidth": 1.0, "edgecolor": "black"},
    "labels": {"fontsize": 11},
    "quantities": {"fontsize": 9, "color": "dimgray"},
    "members": {"fontsize": 9},
    "glyphs": {"tint": 0.45, "alpha": 1.0, "linewidth": 0.5},
    "legend": {},
    "complement": {"facecolor": "#f0f0f0", "edgecolor": "0.4", "linewidth": 1.0},
}

# Categories whose value is a dict of matplotlib kwargs (merged key-by-key on
# update). Everything else (just ``palette``) is replaced wholesale.
_MAPPING_CATEGORIES = frozenset(
    {
        "fills",
        "edges",
        "labels",
        "quantities",
        "members",
        "glyphs",
        "legend",
        "complement",
    }
)

_state: ContextVar[dict[str, Any]] = ContextVar("eunoia_options")


def _current() -> dict[str, Any]:
    """The effective options for the current context (never mutated in place)."""
    return _state.get(_DEFAULTS)


def get_options() -> dict[str, Any]:
    """Return a deep copy of the currently effective plotting options.

    The copy is safe to mutate; it does not affect the live options.
    """
    return deepcopy(_current())


def _apply(changes: dict[str, Any]) -> dict[str, Any]:
    """Validate and merge ``changes`` into a new state; return the prior state."""
    unknown = [k for k in changes if k not in _DEFAULTS]
    if unknown:
        raise ValueError(
            f"unknown option category {unknown}; "
            f"valid categories are {sorted(_DEFAULTS)}"
        )
    prev = deepcopy(_current())
    merged = deepcopy(prev)
    for category, value in changes.items():
        if category in _MAPPING_CATEGORIES:
            if not isinstance(value, Mapping):
                raise TypeError(
                    f"option {category!r} must be a mapping of matplotlib "
                    f"kwargs, got {type(value).__name__}"
                )
            merged[category] = {**merged[category], **value}
        else:
            merged[category] = value
    _state.set(merged)
    return prev


class _OptionsContext:
    """Returned by :func:`options` when setting; restores prior state on exit.

    The change is already applied by the time this is constructed (so using
    :func:`options` as a plain statement persists it). As a context manager,
    ``__exit__`` rolls the options back to what they were before the call.
    """

    __slots__ = ("_prev",)

    def __init__(self, prev: dict[str, Any]) -> None:
        self._prev = prev

    def __enter__(self) -> dict[str, Any]:
        return get_options()

    def __exit__(self, *exc: object) -> None:
        _state.set(self._prev)


def options(**changes: Any) -> dict[str, Any] | _OptionsContext:
    """Get or set global plotting defaults.

    Called with no arguments, returns a deep-copied snapshot of the currently
    effective options (see :func:`get_options`). Called with one or more
    category keyword arguments, merges them into the global options *and*
    returns a context manager that restores the previous values on exit::

        eu.options(fills={"alpha": 0.6})          # persistent global change
        with eu.options(labels={"fontsize": 14}):  # scoped change
            fit.plot()

    Mapping categories (``fills``, ``edges``, ``labels``, ``quantities``,
    ``members``, ``glyphs``, ``legend``, ``complement``) are merged key-by-key with the
    current values; ``palette`` is replaced wholesale. Unknown categories raise
    ``ValueError``.
    """
    if not changes:
        return get_options()
    prev = _apply(changes)
    return _OptionsContext(prev)


def reset_options() -> None:
    """Restore all plotting options to their built-in defaults."""
    _state.set(deepcopy(_DEFAULTS))
