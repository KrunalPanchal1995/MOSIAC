"""
generate_action_table.py -- regenerates docs/traceability.rst from the live
``mso_studio.gui.actions.ACTIONS`` registry (guidelines doc, Part 3.2: "Don't
maintain this table by hand -- generate it.").

Importing every ``gui.modules.*`` page module is what populates ``ACTIONS``
(each module calls ``register(Action(...))`` at import time) -- done
explicitly here rather than relying on autodoc's import order, so this
script produces the same table whether run standalone or from conf.py's
``builder-inited`` hook.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent
REPO_ROOT = DOCS_DIR.parent
SRC_DIR = REPO_ROOT / "src"

_MODULE_PAGES = (
    "mso_studio.gui.modules.nominal",
    "mso_studio.gui.modules.compare",
    "mso_studio.gui.modules.sensitivity",
    "mso_studio.gui.modules.optimization",
    "mso_studio.gui.modules.automation",
    "mso_studio.gui.modules.tools",
)


def _ensure_sys_path() -> None:
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def build_traceability_rst() -> str:
    _ensure_sys_path()
    for module_name in _MODULE_PAGES:
        importlib.import_module(module_name)

    from mso_studio.gui.actions import traceability_rows

    rows = traceability_rows()
    lines = [
        "Action -> function traceability",
        "==================================",
        "",
        "Generated from the live ``mso_studio.gui.actions.ACTIONS`` registry "
        "(``docs/generate_action_table.py``) -- every user-visible action, "
        "the ``core`` function it calls, and its shortcut, if any. Always "
        "correct by construction: this table cannot drift from the code, "
        "because it *is* the code.",
        "",
        ".. list-table::",
        "   :header-rows: 1",
        "   :widths: 15 30 15 40",
        "",
        "   * - Menu",
        "     - Action",
        "     - Shortcut",
        "     - Calls",
    ]
    for menu, label, shortcut, calls in rows:
        lines.append(f"   * - {menu or '—'}")
        lines.append(f"     - {label}")
        lines.append(f"     - {shortcut or '—'}")
        lines.append(f"     - ``{calls}``")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    text = build_traceability_rst()
    (DOCS_DIR / "traceability.rst").write_text(text)
    print(f"Wrote {DOCS_DIR / 'traceability.rst'}")


if __name__ == "__main__":
    main()
