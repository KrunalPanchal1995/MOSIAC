"""
Root conftest for the consolidated mechanism-optimization suite.

The RMIP package now lives at ``src/rmip`` but still imports itself internally as
``rmip`` (e.g. ``from rmip.core.parser import MechanismParser``). To make those
imports resolve when running ``pytest`` from the repository root, we put ``src``
on ``sys.path``.

IMPORTANT — append, never insert at index 0:
    ``src/io`` is a top-level package literally named ``io``. If ``src`` were
    inserted at the *front* of ``sys.path`` it would shadow the standard-library
    ``io`` module and break unrelated code. Appending keeps stdlib precedence
    while still making ``rmip`` importable (nothing else on the path is named
    ``rmip``).

``src/mso_studio`` is PySide6-only and deliberately lives in a dedicated venv
(``.venv-gui/``), never installed into the shared anaconda env (see
feedback_env_isolation). Its own tests are collected fine under anaconda
(``mso_studio.core.*`` is framework-free), but any page/widget-level test that
needs a real ``QApplication`` fixture ERRORs at setup with
``ModuleNotFoundError: No module named 'PySide6'`` rather than failing to
collect — polluting a bare root ``pytest`` run with spurious errors. Skip the
whole tree under anaconda; run it for real via
``./.venv-gui/bin/python -m pytest src/mso_studio/tests -q`` instead.
"""

import importlib.util
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.append(_SRC)

# The repo root also has a *script* named forward_uq.py (the standalone
# forward-UQ CLI), distinct from the src/forward_uq *package*
# (forward_uq/uq_plots.py etc). Same shadowing hazard class as the stdlib
# `io` case above, just root-vs-src instead of src-vs-stdlib: whenever the
# repo root precedes the appended `src` on sys.path (e.g. `python3 -m
# pytest` invoked from repo root inserts cwd at sys.path[0]), a
# package-style `from forward_uq import X` resolves to the root SCRIPT
# first -- which itself does `from forward_uq.mc_propagator import ...`
# expecting to BE the package, and immediately raises
# `ModuleNotFoundError: No module named 'forward_uq.mc_propagator';
# 'forward_uq' is not a package` (WORKBENCH_AUDIT_2026-08-10.md, defect B7).
# Pre-load the real src/forward_uq package into sys.modules by explicit file
# path -- sys.modules is checked before sys.path, so any later `import
# forward_uq` / `from forward_uq import ...` anywhere in the test run finds
# this already-loaded package instead of re-resolving to the root script.
_FWD_UQ_INIT = os.path.join(_SRC, "forward_uq", "__init__.py")
if "forward_uq" not in sys.modules and os.path.exists(_FWD_UQ_INIT):
    _fwd_uq_spec = importlib.util.spec_from_file_location(
        "forward_uq", _FWD_UQ_INIT,
        submodule_search_locations=[os.path.dirname(_FWD_UQ_INIT)],
    )
    _fwd_uq_mod = importlib.util.module_from_spec(_fwd_uq_spec)
    sys.modules["forward_uq"] = _fwd_uq_mod
    _fwd_uq_spec.loader.exec_module(_fwd_uq_mod)

if importlib.util.find_spec("PySide6") is None:
    collect_ignore = ["src/mso_studio"]
