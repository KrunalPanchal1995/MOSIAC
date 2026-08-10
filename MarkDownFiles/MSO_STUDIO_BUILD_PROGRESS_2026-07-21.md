# MSO Studio (PySide6 integrator) — build progress

Plan: `/home/krithika/.claude-work/plans/here-is-the-template-stateless-badger.md`
(design doc it follows: user-supplied GUI guidelines, uploaded as
`gui_guidelines.md` — core/gui split, RunConfig/RunRecord, one-click LaTeX
report with a 3-rung compile ladder, 8px-grid layout, action registry).

## Environment set up

- `.venv-gui/` — dedicated PySide6 venv (built from anaconda's python3.9,
  since `/usr/bin/python3.9` is missing `ensurepip`/`venv` support on this
  machine). Contains: PySide6 6.9.3, matplotlib, qtawesome, jinja2,
  platformdirs, Pillow, PyYAML, pytest. Rebuild with
  `./scripts/setup_gui_venv.sh`.
- `pdflatex`/`latexmk`/`tectonic` are **not installed** — the report compile
  ladder currently always lands on rung 3 (`.tex` + `report_bundle.zip`).
  Installing `tectonic` (single binary, no system package needed) is the
  cheapest way to get real PDFs; noted as an open follow-up in the plan.
  **Update 2026-08-04**: `tectonic` is now installed
  (`/home/krithika/.local/bin/tectonic`) — the compile ladder lands on rung
  1 and produces real PDFs. `src/run_report.py` and `src/latex_project.py`
  (which independently hard-required `pdflatex`, unrelated to this rung-3
  path) were updated to use the same ladder via the new
  `mso_io.latex_engine` module — see `bug.md`.
- Launch: `.venv-gui/bin/python run_mso_studio.py` (repo-root launcher,
  named to avoid shadowing the `mso_studio` package — see its docstring).
  Also reachable from `launcher_gui.py`'s new "Open MSO Studio (PySide6)"
  button.

## Done (WS-A — foundation, WS-B — core sim modules)

`src/mso_studio/core/` (zero Qt imports, enforced by
`tests/test_no_gui_imports.py`):
- `runrecord.py` — `RunConfig`/`RunRecord` dataclasses, JSON round-trip,
  timestamped run-folder serialization under `platformdirs`.
- `backends.py` — subprocess bridge into anaconda python3.9
  (`SCIENCE_PYTHON`), sanitized env (LD_LIBRARY_PATH foreign-toolchain
  strip, duplicated from `rmip.simulation.subprocess_util` on purpose —
  importing that package would pull in Cantera at import time).
- `nominal.py`, `compare.py`, `sensitivity.py`, `optimization.py` —
  adapters over `mso_compare.run_nominal_sim`, `run_mso_pipeline.py`,
  `Sensitivity_Analysis/sens_3_params.py`, `rmip idt-sens`,
  `MUQ-SAC/run_script.py`. All subprocess-only (run_script.py has no
  `__main__` guard).
- `reporting.py` + `templates/report.tex.j2` — the one-click report:
  Jinja2 with LaTeX-safe delimiters, `tex_escape` filter, 3-rung compile
  ladder (tectonic → latexmk/pdflatex → zip bundle), a template-render
  safety net so a Jinja bug can never dead-end the feature.

`src/mso_studio/gui/`:
- `theme.py` — QSS, ported from `src/gui_common/theme.py`'s dark palette,
  plus a Light palette and System/Light/Dark modes.
- `workers.py` — the one `QThread`/`RunWorker` pattern
  (`progress`/`finished(RunRecord)`/`error`/`cancelled` signals).
- `actions.py` — the action registry (id/label/calls/shortcut/menu),
  feeds the (not yet built) docs traceability table.
- `widgets/` — `LogView`, `FilePicker` (inline validation), `MplCanvas` +
  `CsvTableView`, `RunSummaryCard` (owns the report button), and the big
  one: `ModulePage` — the standard configure-left/results-right/log-below
  layout every capability page subclasses. Handles threading, cancel,
  splitter persistence, and report generation once, generically.
- `main_window.py` — left-nav shell, lazy page construction, menu/toolbar
  skeleton, geometry + theme persistence via `QSettings`, drag-and-drop
  stub, About/log-folder/docs menu items.
- `modules/nominal.py`, `compare.py`, `sensitivity.py`, `optimization.py`
  — fully wired `ModulePage` subclasses (real fields, real core calls,
  real results tabs).
- `modules/automation.py` — fully wired (WS-C, see below). `modules/tools.py`
  — still a **placeholder** (`PlaceholderPage`), clearly labeled "not built
  yet".

Tests: `src/mso_studio/tests/` — 23 tests, all green
(`./.venv-gui/bin/python -m pytest src/mso_studio/tests -q`). Covers
RunRecord round-trip/latest-lookup, backend env sanitization + subprocess
streaming/failure/log-file behavior, the core/gui import-layering rule,
`build_report`'s rung-3 fallback (verified end-to-end since no LaTeX
toolchain exists on this machine), and (WS-C) validate/preflight/meta-PRS-fit
against the real integrated automation code + real external factorial
report data.

Smoke test: app launches clean both under `QT_QPA_PLATFORM=offscreen` and
against the real X display (confirmed via `xwininfo` — window registers
with correct title/geometry; this display's screenshot tooling returns a
static test-card image regardless of region, a capture quirk of this VM/
remote-display setup, not an app issue — could not get a true visual
screenshot this session).

`launcher_gui.py` (Tkinter) got a new button, "Open MSO Studio (PySide6)",
that shells out to `.venv-gui/bin/python run_mso_studio.py` — separate
interpreter than every other button (those use `sys.executable`, i.e.
anaconda, which doesn't have PySide6 by design).

## Done (WS-C — mechanism-comparison automation + p_PRS integration)

**Copied** (code only — never the live state/log/lock files, see below)
from `/data2/KRUNAL/FINALIZED_STAGE_OPTIMIZATION_2026/MSO_A_FACTOR/p_PRS/_automation/`
into `src/automation/`: `run_tasks.py`, `prs_extract_doe.py`, `prs_fit.py`,
`prs_optimize.py`, `prs_plan_runs.py`, `prs_preflight.py`, `prs_report.py`,
`prs_driver.py`, `TASK_SCHEMA.md`, `examples/*.yaml`. Deliberately NOT
copied: `cleanup_space.py`, `edit_target_opt.py`, `phase_a_driver.py`,
`factorial_dispatch.py`, `factorial_relaunch_corrupted*.py` — all legacy/
superseded (per `run_tasks.py`'s own docstring) or only used by those
legacy scripts, not by `run_tasks.py`/`prs_*.py`.

**Important: there is a live, independent campaign still running** in the
external `_automation/` directory (state files timestamped as recent as
2026-07-21 12:45 at last check) — it was NOT touched, only read from. Two
real correctness/safety fixes were needed, not just path hygiene:

1. **De-hardcoded** `run_tasks.py`'s `DEFAULT_PYTHON`/`DEFAULT_OPTIMIZE_CMD`/
   `DEFAULT_COMPARE_CMD` (were `/home/krithika/anaconda3/...`,
   `/home/krithika/MUQ-SAC/V3.0/run_script.py`,
   `/home/krithika/mechanism-optimization-suite/src/run_mso_pipeline.py`) to
   resolve against `MSO_STUDIO_SCIENCE_PYTHON` / this repo's own
   `src/MUQ-SAC/run_script.py` / `src/run_mso_pipeline.py`. Still fully
   overridable per-study (YAML `settings.python`, per-task `command:`).
2. **`prs_extract_doe.py`/`prs_report.py`/`prs_plan_runs.py`** assumed
   `MECHANISM_COMPARISON/` and the fuel folders were siblings of the script
   (`AUTOMATION_DIR.parent`) — true only when run in place. That external,
   multi-GB data will never live in this git repo, so these now resolve
   against `MSO_PPRS_DATA_ROOT` (env var, defaults to the real external
   p_PRS root so behavior is unchanged out of the box).
3. **The actually-important safety fix**: `prs_preflight.py`'s thread-
   headroom check only ever scanned `state_*.json` in its *own* directory.
   Left as-is, a study launched from this repo's copy would be blind to the
   live external campaign's committed threads and could oversubscribe the
   machine on top of it. `automation_dirs()` now scans this repo's
   `src/automation/` **and** the known external `_automation/` dir (or
   `MSO_STUDIO_EXTRA_AUTOMATION_DIRS`, `:`-separated, if set) — verified
   working: it correctly found and parsed all 4 live external state files
   (campaign was idle — all tasks `done`/`skipped_existing` — at check
   time, confirmed by reading the state JSON directly, not a scan bug).

`core/automation.py` — adapter, NOT a single blocking `run_*` call like
every other module (a study runs for days after `--daemon` detaches it):
`validate_yaml`/`get_status`/`run_preflight` (subprocess, read-only),
`launch_daemon` (subprocess `--daemon`, returns almost immediately once
detached, returns a `RunRecord`), and `fit_meta_prs`/`available_fuels`
(pure numpy/scipy, **in-process**, no subprocess — imports
`prs_extract_doe`/`prs_fit`/`prs_optimize` directly by putting
`src/automation/` on `sys.path`, matching those scripts' own sibling-import
convention rather than forcing a package structure onto them).

`gui/modules/automation.py` — NOT a `ModulePage` subclass (doesn't fit the
one-shot run/RunRecord model); two tabs: **Task Runner** (YAML picker,
Validate/Preflight/Launch/Refresh-status buttons, a structured per-task
status table read from the state file, an output log) and **Meta-PRS Fit**
(fuel dropdown, read-only LOOCV-trust + predicted-optimum display). Every
operation runs on its own thread via the new `gui/workers.py::CallWorker`/
`call_in_thread` (added alongside the existing `RunWorker` — these
operations return plain values, not `RunRecord`s, so didn't fit that
signal shape).

Verified: `run_tasks.py examples/compare_only_minimal.yaml --validate`
passes from the new location; `prs_preflight.py` correctly reports "2
automation dir(s)" scanned and finds the live external state files;
`fit_meta_prs` tested against the **real** external factorial reports for
all 3 fuels (not mocked) — all pass. All 6 nav pages (including Automation)
build cleanly offscreen. Confirmed via `ls -la --time-style=full-iso` that
none of the live external state/lock files changed timestamp during this
work.

## Done (WS-D — Tools module + LaTeX everywhere + Sphinx docs)

**Dependency routing decision**: PySR (needs Julia), `pdfplumber`, and
`google-genai` all already live in the shared anaconda environment
(installed there for the original Tkinter panels, before this session) —
never added to the light `.venv-gui`. New `scripts/tools_worker.py` runs in
anaconda and handles every operation needing them (`pysr_fit`,
`gemini_chat*`, `pdf_extract_*`, `pdf_render_page`); `core/tools.py` shells
out to it via the existing `run_backend` bridge, same pattern as every
other adapter. Polynomial fitting and the digitizer's coordinate math
(`core/digitizer.py`) are pure numpy/stdlib and run in-process.

**Ported into `gui/modules/tools.py`** (replaces the placeholder), four
sub-tabs, none `ModulePage` subclasses (interactive tools, not
run-and-report jobs): **Curve / Symbolic Fit** (CSV load, poly fit
in-process, PySR fit via the worker with an honest note that Julia's
`.fit()` can't be cooperatively cancelled — killing the subprocess is
actually a strict improvement over the original Tkinter panel's "may still
be finishing" limitation), **Plot Digitizer** (new `QGraphicsView`-based
`DigitizerView` widget for interactive click-to-calibrate/digitize — the
one genuinely GUI-specific piece; PDF-page loading renders via the worker's
`pdf_render_page` rather than Qt's `QtPdf` module, which fails to import on
this machine — a `libgssapi_krb5` version conflict, confirmed unrelated to
this project and not worth chasing), **PDF Q&A** and **PDF Tables**
(Gemini-backed, both degrade gracefully via `tools_core.gemini_available()`
when `GOOGLE_API_KEY` is unset, matching the original panels' behavior).

**Richer per-module LaTeX ("Export options...", guidelines doc Part 4)** —
partially wired, with an important discovery along the way:
- `src/target_tables.py` (self-contained, stdlib only) is now wired as
  **"Generate LaTeX target tables..."** on both Nominal Simulation and
  Mechanism Comparison pages (`core/mso_reports.py` +
  `gui/widgets/target_tables_button.py`, a small shared button so the
  wiring isn't duplicated) — tested end-to-end against a real `.target`
  file in the repo.
- `src/run_report.py` (the "read a full MSO run's results, write a
  comprehensive LaTeX report" generator the user specifically asked to
  extend to all GUIs) turned out to have a **genuine, pre-existing bug**:
  it imports sibling modules as `from io.mso_io import ...` /
  `io.mso_analysis` / `io.mso_plots` / `io.mso_latex`. Because `src/io/` is
  a real package literally named `io`, this cannot resolve under ANY normal
  CPython invocation — confirmed both failure modes directly: (a) if
  `src/` isn't on `sys.path` at interpreter start, stdlib `io` wins and
  `io.mso_io` fails to import; (b) if `src/` *is* on `sys.path` at start
  (cwd=`src/`, as the script's own docstring instructs), the interpreter's
  own bootstrap `import io` resolves to the local empty package and CPython
  crashes before any user code runs (`Fatal Python error:
  init_sys_streams`). The existing caller in `generate_target_opt.py`
  (`_append_mso_report_section`) also passes CLI args that don't match
  `run_report.py`'s actual `argparse`-free interface and doesn't set `cwd`
  — this feature path looks like it's been broken since before this
  integration, not something this session broke. Added a small, purely
  additive `--config <yaml>` non-interactive entry point to `run_report.py`
  (unblocks the moment the `io` collision is fixed) but did **not**
  attempt the actual fix — most likely renaming `src/io/` — since that's a
  broader, riskier change (other files may import from that package) than
  this workstream's scope. Full details in `core/mso_reports.py`'s module
  docstring. **This is the one explicit gap in "extend LaTeX reporting to
  all GUIs" — flagging clearly rather than claiming it's done.**
- `src/modules/latex_tables.py` (needs `pandas`, not in `.venv-gui`) and
  `src/io/mso_latex.py`'s `generate_latex_document` (self-contained, but
  only useful as part of the full `run_report.py` pipeline that's blocked
  above) were not wired this session.

**Sphinx docs site** (`docs/`): `autodoc` + `napoleon` (NumPy docstrings —
already written that way throughout `core/`/`gui/` as each module was
built), `furo` theme installed (with a graceful `alabaster` fallback in
`conf.py` if unavailable). Built with `.venv-gui`'s interpreter, not
anaconda's — autodoc must import `gui.*` modules, which need PySide6;
`QT_QPA_PLATFORM=offscreen` is forced in `conf.py` so the build never needs
a real display. `docs/generate_action_table.py` regenerates
`docs/traceability.rst` from the live `gui.actions.ACTIONS` registry on
every build (hooked via `conf.py`'s `setup()` / `builder-inited`) — always
correct by construction, verified it correctly lists all 7 currently
registered actions including both `target_tables` buttons. `.readthedocs.yaml`
+ `docs/requirements.txt` added. **Verified: `sphinx-build -b html docs
docs/_build/html` succeeds with zero warnings**, all 28 `core`/`gui`
submodules render, spot-checked real docstring content in the output HTML.

Full test suite: 34/34 passing after WS-D (`test_digitizer.py`,
`test_tools.py` — including a real end-to-end anaconda-subprocess PDF-text
extraction test against a reference PDF already in the repo, not mocked —
and `test_mso_reports.py`, also tested against a real `.target` file).

## Known gaps / honesty notes

- **`src/run_report.py`'s LaTeX pipeline is blocked by a pre-existing `io`
  package-name collision bug**, not fixed this session — see the WS-D
  section above and `core/mso_reports.py`'s docstring for full details and
  the exact fix needed (likely renaming `src/io/`).
- `gui/modules/sensitivity.py`'s IDT-sensitivity results only get a JSON
  path logged, not rendered as a sortable table.
- PySR fitting's "Cancel" semantics changed from the original (which could
  only "stop watching," Julia kept computing regardless) to actually
  killing the subprocess — a behavior change, arguably a strict
  improvement, flagged in case it matters to existing muscle memory.
- Qt's `QtPdf` module fails to import on this machine (system
  `libgssapi_krb5` version conflict) — PDF-page rendering for the
  digitizer routes through the anaconda `pdfplumber` worker instead;
  harmless, but means that specific operation has a subprocess round-trip
  a native Qt path wouldn't need.
- No frozen/installer build (PyInstaller etc., guidelines doc Part 5) —
  explicitly out of scope per the plan.
- Did not visually screenshot-verify the QSS styling in this session (see
  earlier smoke-test note); layout logic was verified by code review + the
  offscreen-platform clean run, not by eye.

## All four workstreams (WS-A/B/C/D) are now done

Everything in the original plan has been built and tested (34 tests green)
except the one explicitly-flagged gap above (`run_report.py`'s blocked
pipeline). Nothing has been committed to git this session (per instruction:
only commit when asked).
