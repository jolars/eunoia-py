# Adapted from
# https://github.com/scikit-learn/scikit-learn/blob/b0b8a39d8bb80611398e4c57895420d5cb1dfe09/doc/sphinxext/github_link.py
# (BSD 3-Clause License, copyright 2007-2023 The scikit-learn developers).

import importlib
import inspect
import os
import subprocess
import sys
from functools import partial

REVISION_CMD = "git rev-parse --short HEAD"


def _get_git_revision():
    try:
        revision = subprocess.check_output(REVISION_CMD.split()).strip()
    except (subprocess.CalledProcessError, OSError):
        print("Failed to execute git to get revision")
        return None
    return revision.decode("utf-8")


def _linkcode_resolve(domain, info, package, url_fmt, revision):
    if revision is None:
        return None
    if domain not in ("py", "pyx"):
        return None
    if not info.get("module") or not info.get("fullname"):
        return None

    class_name = info["fullname"].split(".")[0]
    module = importlib.import_module(info["module"])
    try:
        obj = getattr(module, class_name)
    except AttributeError:
        return None

    obj = inspect.unwrap(obj)

    try:
        fn = inspect.getsourcefile(obj)
    except (TypeError, OSError):
        fn = None
    if not fn:
        try:
            fn = inspect.getsourcefile(sys.modules[obj.__module__])
        except (KeyError, TypeError, OSError):
            fn = None
    if not fn:
        return None

    fn = os.path.relpath(fn, start=os.path.dirname(__import__(package).__file__))
    try:
        lineno = inspect.getsourcelines(obj)[1]
    except (TypeError, OSError):
        lineno = ""
    return url_fmt.format(revision=revision, package=package, path=fn, lineno=lineno)


def make_linkcode_resolve(package, url_fmt):
    """Return a linkcode_resolve function for the given URL format."""
    revision = _get_git_revision()
    return partial(
        _linkcode_resolve, revision=revision, package=package, url_fmt=url_fmt
    )
