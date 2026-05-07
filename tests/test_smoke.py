from __future__ import annotations

import eunoia
from eunoia._eunoia import _smoke


def test_version() -> None:
    assert eunoia.__version__ == "0.1.0"


def test_extension_loads() -> None:
    assert "scaffolding works" in _smoke()
