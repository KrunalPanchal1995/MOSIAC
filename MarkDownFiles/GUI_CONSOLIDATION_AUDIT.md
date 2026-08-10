# GUI consolidation audit — Session B1 of the visual-system plan

Date: 2026-08-05

## Why this exists

The user's ask was "current GUI organization is not so good, there are
repetitive things, make it clean and less repetitive." The visual-system
plan's original B1 sketch (written before this audit) assumed the 13 Qt
module pages each hand-rolled their own file pickers, run/stop controls,
results tables, and settings persistence — a plausible guess from a
high-level scan, but not what's actually in the codebase. This document
records what an actual line-by-line read of `mso_studio/gui/modules/*.py`
and `mso_studio/gui/widgets/*.py` found, so the shared-widget work that
follows targets the real gap instead of re-building things that already
exist.

## What's already centralized (no action needed)

| Concern | Already lives in | Evidence |
|---|---|---|
| Run/Stop button pair, threading, cancellation, log view, status messages, "Generate LaTeX report" | `gui/widgets/module_page.py`'s `ModulePage` base class | Every one of the 12 module pages subclasses it and gets `run_button`/`stop_button`/`log_view`/`run_summary` for free — `_on_run_clicked`/`_on_run_finished`/`_on_run_error`/`_on_run_cancelled`/`_on_report_requested` are implemented exactly once |
| File/directory picker (path field + Browse + live existence validation) | `gui/widgets/file_picker.py`'s `FilePicker` | Used by converter.py, fusion.py, uncertainty.py, nominal.py, and others — a single `FilePicker(mode=..., filter_=..., must_exist=...)` call per field |
| Run status card (spinner while running, result summary, report button) | `gui/widgets/run_summary.py`'s `RunSummaryCard` | One instance per page, owned by `ModulePage`, not rebuilt per subclass |
| Splitter-state / setup-panel layout persistence | `ModulePage._restore_splitter_state`/`_save_splitter_state`, one shared `QSettings("mechanism-optimization-suite", "mso-studio")` namespace | Zero per-page `QSettings(...)` calls found anywhere in `gui/modules/` |
| CSV-backed results preview (capped row count, read-only) | `gui/widgets/mpl_canvas.py`'s `CsvTableView` | Used by compare.py, sensitivity.py, forward_uq.py, optimization.py, nominal.py |
| Plot canvas + theme-aware colors | `gui/widgets/mpl_canvas.py`'s `MplCanvas` (theme wiring added Session A2) | One shared class; `tools.py` is the only module-page consumer today (most others plot via `CsvTableView`'s table view or `mso_io.mpl_plots` helpers) |
| Page header (art thumbnail, title, tagline, description, Learn-more) | `gui/widgets/module_hero.py`'s `ModuleHero`, built once by `ModulePage.__init__` | All 12 pages get one automatically |

This is a materially better starting point than the plan assumed — the
run/stop/log/report/file-picker/settings-persistence "repetition" the user
was reacting to is not in this layer. It's more likely the *visual*
inconsistency Track A already fixes (three palettes, ad-hoc styling), and
the one real structural duplication below.

## What's genuinely duplicated

**A read-only results table is hand-built from scratch in 7 places**, each
repeating the same three-line setup and the same per-cell population loop,
with no CSV export anywhere:

| File | Widget | Columns |
|---|---|---|
| `mechanism_check.py:53-57` | `_findings_table` | Sev / Check / Message / Location |
| `uncertainty.py:68-72` | `_results_table` | 5 columns (reaction, A_nominal, factor, bounds) |
| `automation.py:115-118` | `task_table` | Task / Type / Status |
| `sensitivity.py:89-92` | `bf_targets_table` | 6 columns |
| `rmip_suite.py:359-362` | `fuel_table` | Species / Mole fraction |
| `tools.py:660-661` | `preview` | variable (digitizer CSV preview) |
| `tools.py:860-862` | `table` | Extension / Source found / Installed copies |

Every one of the 7 is the same shape:
```python
table = QTableWidget(self)
table.setColumnCount(N)
table.setHorizontalHeaderLabels([...])
table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
# ... later, row by row:
table.setItem(row, col, QTableWidgetItem(str(value)))
```
All 7 are genuinely read-only display tables (every site sets
`NoEditTriggers`) — none needs in-place editing, so one shared widget can
cover all of them without a variant.

## What was decided against building

- **A `FilePickerRow` rebuild** — `FilePicker` already covers this;
  building a second version would be the opposite of de-duplication.
- **A `RunControls` rebuild** — `ModulePage` already owns this end to end.
- **A `ParamForm` declarative builder** — checked whether pages repeat the
  same 3-line "checkbox + tooltip + add_row" block often enough to justify
  a declarative-spec builder; they don't share enough structure (field
  counts, types, and validation differ per page) for a builder to be
  clearer than the current direct `add_setup_row(label, widget)` calls,
  which are already the single entry point. Revisit only if a future page
  shows the same field pattern verbatim.
- **A `StatusStrip` rebuild** — the launcher already has one
  (`window.py`'s bottom strip); module pages use `ModulePage.statusMessage`
  + `log_view`, which already serves the same purpose without a second
  widget.

## What this session builds

`gui/widgets/results_table.py`'s `ResultsTable(QTableWidget)`:
- `__init__(headers: list[str], parent=None)` — does the 3-line setup once.
- `set_rows(rows: list[list])` — replaces all rows in one call, `str()`-ing
  each cell value (matching every existing call site's behavior).
- `export_csv(path)` / a right-click "Export CSV..." context-menu action —
  genuinely new capability none of the 7 sites have today.

Migrating the 7 existing sites onto `ResultsTable` is Session B2's job
(refactor existing pages onto shared scaffolding) — this session only
builds and tests the widget itself, so B2 has a stable, proven target to
port onto rather than co-developing the abstraction and the migration at
the same time.
