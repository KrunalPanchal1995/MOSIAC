#!/usr/bin/env python3
"""
Repo-root launcher for the Optimize Workbench -- Phase 2 of the 2026-08 GUI
integration overhaul: a dedicated window bundling the four pages that make
up the actual tuning workflow (Sensitivity Analysis, Target Workbench,
Optimization, Forward UQ), for working the optimization loop without every
other MSO Studio module in the sidebar. Same pages as MSO Studio -- this is
a curated subset of the same ``mso_studio.gui.modules.PAGE_FACTORIES``, not
a fork of them, so there is nothing to keep in sync by hand.

Must be run with the dedicated GUI virtual environment's interpreter, same
as ``run_mso_studio.py``:

    .venv-gui/bin/python run_mso_optimize.py
"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.append(_SRC)

#: module ids, in display order, that make up the Optimize Workbench.
OPTIMIZE_WORKBENCH_MODULES = ("sensitivity", "target_workbench", "optimization", "forward_uq")


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "PySide6 is not installed in this interpreter.\n"
            "Run the Optimize Workbench with the dedicated GUI venv:\n"
            "    ./scripts/setup_gui_venv.sh   (first time only)\n"
            "    .venv-gui/bin/python run_mso_optimize.py",
            file=sys.stderr,
        )
        return 1

    from mso_studio.gui.main_window import MainWindow
    from mso_studio.gui.modules import PAGE_FACTORIES

    app = QApplication(sys.argv)
    app.setApplicationName("MSO Optimize Workbench")
    app.setOrganizationName("mechanism-optimization-suite")

    by_id = {mid: (mid, label, factory) for mid, label, factory in PAGE_FACTORIES}
    missing = [mid for mid in OPTIMIZE_WORKBENCH_MODULES if mid not in by_id]
    if missing:
        print(f"Optimize Workbench: unknown module id(s) {missing}", file=sys.stderr)
        return 2
    curated = [by_id[mid] for mid in OPTIMIZE_WORKBENCH_MODULES]

    window = MainWindow(curated)
    window.setWindowTitle(window.windowTitle().replace("MSO Studio", "MSO Optimize Workbench"))
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
