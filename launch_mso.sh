#!/usr/bin/env bash
# One-command entry point to the whole suite: opens the game-style PySide6
# launcher (launcher_qt.py) if the dedicated GUI venv is set up, otherwise
# falls back to the zero-dependency Tkinter launcher (launcher_gui.py) --
# see the env-isolation policy in project memory / CLAUDE.md.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

if [ -x ".venv-gui/bin/python" ]; then
    exec ".venv-gui/bin/python" launcher_qt.py "$@"
else
    echo "GUI venv (.venv-gui) not found -- falling back to the basic Tkinter launcher." >&2
    echo "For the full game-style launcher, run: ./scripts/setup_gui_venv.sh" >&2
    exec python3 launcher_gui.py "$@"
fi
