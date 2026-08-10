User Guide
==========

Installation
------------

MSO Studio's GUI runs in a dedicated virtual environment, kept separate
from the shared anaconda environment that hosts the suite's science stack
(Cantera, MUQ-SAC, RMIP) -- see the env-isolation policy in the project's
memory notes.

.. code-block:: bash

   ./scripts/setup_gui_venv.sh
   .venv-gui/bin/python run_mso_studio.py

If you see ``PySide6 is not installed in this interpreter``, you launched
with the wrong Python -- use ``.venv-gui/bin/python``, not the system or
anaconda one.

A five-minute worked example: nominal simulation
--------------------------------------------------

1. Open **Nominal Simulation** in the left sidebar.
2. Fill in **Mechanism**, **Targets**, **Thermo file**, **Transport file**,
   and **Base .opt template** -- every field is a file picker with inline
   validation (a red outline means the path doesn't exist).
3. Press **Run** (or ``F5``). The window stays responsive; progress streams
   into the collapsible log strip below the results tabs.
4. When the run finishes, the run-summary card enables
   **Generate LaTeX report** -- click it for a ``.tex`` (and, if a LaTeX
   toolchain is installed, a compiled PDF) capturing the exact
   configuration, software versions, and results of that run.

Each module page (Mechanism Comparison, Sensitivity Analysis, Optimization,
Mechanism-Comparison Automation, Tools) follows the same
configure-left / results-right / log-below layout.

One-click LaTeX reports
------------------------

Every run-based module gets the generic report for free
(:func:`mso_studio.core.reporting.build_report`). If no LaTeX toolchain
(``tectonic``, ``latexmk``, or ``pdflatex``) is installed, the button still
succeeds -- it writes a ``report_bundle.zip`` containing the ``.tex`` and
figures, ready to compile locally or upload to Overleaf, rather than
failing outright.

Nominal Simulation and Mechanism Comparison additionally offer
**Generate LaTeX target tables...**, a richer, module-specific export
(:func:`mso_studio.core.mso_reports.generate_target_tables`) that produces
publication-quality per-target-type tables straight from the ``.target``
file.

Troubleshooting
----------------

**"Missing or invalid: Mechanism, Targets."**
    One or more required file pickers are empty or point at a path that
    doesn't exist. Browse to the actual file -- the Run button's handler
    checks this before starting anything, so nothing was launched.

**"Backend command exited with code 1"**
    The underlying science script failed. The error includes the last
    output lines and the full log path -- open "Details..." (the log
    strip) for the complete trace before reporting a bug.

**"No LaTeX engine found — wrote a compile-ready bundle"**
    Not an error -- this is the expected message when no LaTeX toolchain is
    installed. Compile the bundle locally with ``tectonic`` (recommended,
    single binary, no system package needed) or upload it to Overleaf.

**A new automation study seems to oversubscribe threads**
    Run **Preflight check** before **Launch** -- it scans thread commitments
    across this repo's automation directory *and* any other live one
    (``MSO_STUDIO_EXTRA_AUTOMATION_DIRS``). If it reports headroom lower
    than expected, another study is already running.

Help menu
---------

Inside the app: **Help > Documentation** opens this site (once built),
**Help > Open log folder** opens the directory every run's ``RunRecord``
is saved under, and **Help > About** shows exact version numbers -- include
those when reporting an issue.
