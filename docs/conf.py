import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "exts"))

from eunoia import __version__
from github_link import make_linkcode_resolve

# Project information
project = "eunoia"
copyright = "2026, Johan Larsson"
author = "Johan Larsson"
release = __version__

# General configuration
extensions = [
    "sphinx.ext.autosummary",
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.mathjax",
    "sphinx_copybutton",
    "myst_nb",
    "sphinx.ext.linkcode",
]
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
master_doc = "index"

pygments_style = "tango"

# Autosummary
autosummary_generate = True
autosummary_imported_members = True

# HTML output
html_theme = "furo"
html_static_path = ["_static"]
html_css_files = ["css/custom.css"]
html_title = f"eunoia {release}"
html_logo = "_static/logo.svg"
html_favicon = "_static/logo.svg"

# Intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "matplotlib": ("https://matplotlib.org/stable/", None),
}

# MyST
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "dollarmath",
    "amsmath",
]

# MyST-NB
nb_execution_mode = "auto"
nb_execution_timeout = 60

# Linkcode — wrap in a plain function so Sphinx doesn't warn about `partial`.
_linkcode_resolve = make_linkcode_resolve(
    "eunoia",
    "https://github.com/jolars/eunoia-py/blob/{revision}/python/{package}/{path}#L{lineno}",
)


def linkcode_resolve(domain, info):
    return _linkcode_resolve(domain, info)


# Napoleon
napoleon_google_docstring = False
napoleon_use_ivar = True
