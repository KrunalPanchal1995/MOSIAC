#!/usr/bin/env python3
"""
Repo-root launcher for the game-style PySide6 MSO Launcher.

Must be run with the dedicated GUI virtual environment's interpreter --
PySide6 is deliberately not installed in the shared anaconda environment
(see the env-isolation policy in project memory / CLAUDE.md):

    .venv-gui/bin/python launcher_qt.py

Mirrors ``run_mso_studio.py``'s sys.path pattern exactly: ``src/`` is
*appended* (not prepended, and never via ``cd src``) so ``mso_studio``
resolves without stdlib shadowing, and this script is named
``launcher_qt.py`` -- not ``launcher.py`` -- so it can never shadow the
``mso_studio.launcher`` package it imports.

Prefer ``./launch_mso.sh`` for everyday use -- it falls back to the
Tkinter ``launcher_gui.py`` automatically if ``.venv-gui`` doesn't exist yet.
This script assumes the GUI venv is already active/selected.
"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.append(_SRC)


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "PySide6 is not installed in this interpreter.\n"
            "Run the launcher with the dedicated GUI venv:\n"
            "    ./scripts/setup_gui_venv.sh   (first time only)\n"
            "    .venv-gui/bin/python launcher_qt.py\n"
            "or just: ./launch_mso.sh",
            file=sys.stderr,
        )
        return 1

    from PySide6.QtCore import QSettings

    from mso_studio.launcher.boot import BootSplash
    from mso_studio.launcher.process import LaunchManager
    from mso_studio.launcher.window import ORG_NAME, APP_NAME, LauncherWindow

    app = QApplication(sys.argv)
    app.setApplicationName("MSO Launcher")
    app.setOrganizationName("mechanism-optimization-suite")

    launch_manager = LaunchManager()
    state = {}

    def _on_splash_finished(boot_results) -> None:
        window = LauncherWindow(launch_manager, boot_results)
        window.show()
        state["window"] = window  # keep alive
        splash.close()

    # Honor the user's saved theme preference (LauncherWindow._set_theme
    # persists it under the same QSettings key) instead of always booting
    # into dark mode regardless of what was chosen last session.
    saved_mode = QSettings(ORG_NAME, APP_NAME).value("theme_mode", "system")
    splash = BootSplash(saved_mode)
    splash.finished.connect(_on_splash_finished)
    splash.start()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
