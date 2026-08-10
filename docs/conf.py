"""Sphinx configuration for MSO Studio's documentation site.

Builds with the GUI venv's interpreter (.venv-gui) because autodoc must
import mso_studio.gui.* modules, which need PySide6 -- not installed in the
shared anaconda environment by design (see the env-isolation policy):

    .venv-gui/bin/sphinx-build -b html docs docs/_build/html
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent
REPO_ROOT = DOCS_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

# Importing gui/* modules for autodoc doesn't require a running event loop
# (they only define classes), but PySide6 warns/errors without a platform
# plugin in some headless CI environments -- force offscreen so `sphinx-build`
# never depends on a real display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

project = "MSO Studio"
copyright = "Mechanism Optimization Suite"
author = "Mechanism Optimization Suite"
try:
    from mso_studio import __version__ as release
except ImportError:
    release = "0.dev"
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # NumPy-style docstrings
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

autodoc_mock_imports = [
    # Heavy science deps that live in the anaconda env, not the docs venv --
    # core/*.py adapters reference them only inside function bodies (lazy
    # imports for the subprocess bridge), so mocking is safe for autodoc.
    "cantera",
]

napoleon_google_docstring = False
napoleon_numpy_docstring = True

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

try:
    import furo  # noqa: F401
    html_theme = "furo"
except ImportError:
    html_theme = "alabaster"

html_static_path = []


def setup(app):
    """Regenerate traceability.rst from the live action registry before
    every build (guidelines doc, Part 3.2) -- see generate_action_table.py."""
    sys.path.insert(0, str(DOCS_DIR))
    from generate_action_table import main as regenerate_traceability

    def _on_builder_inited(app):
        regenerate_traceability()

    app.connect("builder-inited", _on_builder_inited)
