#!/usr/bin/env python3
"""
Repo-root launcher for MSO Studio (the PySide6 GUI integrator).

Must be run with the dedicated GUI virtual environment's interpreter --
PySide6 is deliberately not installed in the shared anaconda environment
(see the env-isolation policy in project memory / CLAUDE.md):

    .venv-gui/bin/python run_mso_studio.py

Mirrors ``rmip_cli.py``'s sys.path pattern: ``src/`` is *appended* (not
prepended, and never via ``cd src``) so ``mso_studio`` resolves without
stdlib shadowing. Named ``run_mso_studio.py`` -- not ``mso_studio.py`` --
because the script's own directory is always sys.path[0]; a same-named
script would shadow the ``mso_studio`` package it needs to import.

``--module <id> [--standalone]`` (2026-08 launcher-integration fix): every
per-module launcher tile now spawns this same script with these flags
instead of the retired legacy Tkinter GUI, so clicking e.g. "Mechanism
Reduction" opens the real PySide6 page. ``--module`` alone deep-links into
the full shell, pre-selected on that page; ``--standalone`` skips the shell
entirely and opens just that page in its own window (``ModuleWindow``) --
see ``mso_studio.launcher.catalog`` for which id maps to which tile.
"""
import argparse
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.append(_SRC)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--module", default=None,
        help="module id to open directly (see mso_studio.gui.modules.PAGE_FACTORIES)",
    )
    parser.add_argument(
        "--standalone", action="store_true",
        help="open --module in its own window, with no sidebar shell",
    )
    args, qt_args = parser.parse_known_args(sys.argv[1:])

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "PySide6 is not installed in this interpreter.\n"
            "Run MSO Studio with the dedicated GUI venv:\n"
            "    ./scripts/setup_gui_venv.sh   (first time only)\n"
            "    .venv-gui/bin/python run_mso_studio.py",
            file=sys.stderr,
        )
        return 1

    from mso_studio.gui.modules import PAGE_FACTORIES

    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName("MSO Studio")
    app.setOrganizationName("mechanism-optimization-suite")

    factories = {mid: factory for mid, _label, factory in PAGE_FACTORIES}
    labels = {mid: label for mid, label, _factory in PAGE_FACTORIES}

    if args.module is not None and args.module not in factories:
        known = ", ".join(sorted(factories))
        print(f"Unknown --module {args.module!r}. Known ids: {known}", file=sys.stderr)
        return 2

    if args.module is not None and args.standalone:
        from mso_studio.gui.module_window import ModuleWindow

        page = factories[args.module]()
        window = ModuleWindow(args.module, labels[args.module], page)
        window.show()
        return app.exec()

    from mso_studio.gui.main_window import MainWindow

    window = MainWindow(PAGE_FACTORIES)
    if args.module is not None:
        for row in range(window.nav_list.count()):
            if window.nav_list.item(row).data(Qt.ItemDataRole.UserRole) == args.module:
                window.nav_list.setCurrentRow(row)
                break
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
