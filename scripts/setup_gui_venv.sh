#!/usr/bin/env bash
# Create the dedicated PySide6 GUI virtual environment (.venv-gui) at the
# repo root. Never installed into the shared anaconda environment -- see the
# env-isolation policy in project memory / CLAUDE.md.
#
# The heavy science stack (Cantera, MUQ-SAC, RMIP) stays in anaconda
# python3.9 and is reached from the GUI only via subprocess
# (mso_studio.core.backends.SCIENCE_PYTHON).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv-gui"

# The system python3.9 (/usr/bin/python3.9) is missing ensurepip/venv support
# on this machine; anaconda's python3.9 has a working venv module and is
# ABI-compatible with the anaconda science stack's Python version, so use it
# purely as the venv *builder* -- the resulting venv is still isolated site-packages.
PYTHON_FOR_VENV="${MSO_STUDIO_VENV_PYTHON:-$HOME/anaconda3/bin/python3.9}"

if [ ! -d "${VENV_DIR}" ]; then
    echo "Creating GUI venv at ${VENV_DIR} ..."
    "${PYTHON_FOR_VENV}" -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip -q
"${VENV_DIR}/bin/python" -m pip install -q \
    PySide6 \
    matplotlib \
    qtawesome \
    jinja2 \
    platformdirs \
    Pillow \
    pyyaml \
    numpy \
    scipy \
    pytest \
    sphinx \
    furo

echo "Done. Launch with: ${VENV_DIR}/bin/python ${REPO_ROOT}/run_mso_studio.py"
