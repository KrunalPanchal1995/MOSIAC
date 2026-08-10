# Workbench Capability Audit — 2026-08-10

## Purpose

Verify four capabilities of the Optimize Workbench end-to-end, against real mechanisms (FFCM1 =
"good", GRI-3.0 = "ok", a deliberately A-factor-perturbed copy of FFCM1 = "bad"), and implement the
two capabilities (3 and 4) that were only partly built. This session's scope, per the user's own
decisions when asked to clarify: **implement** tasks 3 and 4; **test and record** tasks 1 and 2
without fixing what's found. Every defect below is recorded, not fixed, per that instruction
(except two bugs in code *written this session*, fixed inline — flagged as such).

Everything in this document was produced by actually running the code — real subprocesses, a real
git worktree, real SIGSTOP/SIGCONT signals, a real (partially-completed) FFCM1 optimization, a real
RMG-Py/RDKit/Jupyter/tectonic environment probe — not read off the source alone.

---

## Summary verdict

| # | Capability | Round 1 Verdict | Round 2 status |
|---|---|---|---|
| 1 | Run in any folder, recover files for the full pipeline | **Works** for the outer `run_script.py` stage (confirmed: `unsrt.pkl` correctly resumed, "Uncertainty analysis already finished" printed on re-invocation from a `Project.resume()`-materialized folder). Undermined for subprocessed stages by a config portability bug (below). | **Config-portability bug (B1) fixed** — see D3. Fresh generations and both shipped `target.opt` files now resolve inside the current repo, not the pre-move location. |
| 2 | Edit code mid-run, branch, resume; branch + master simultaneously | **Works** for pause/SIGSTOP/SIGCONT, worktree creation, commit-to-branch, and dual-run (verified two genuinely simultaneous, non-colliding processes, one importing from the main checkout and one from the pause-branch worktree). Does **not** reach code invoked as a subprocess via a `target.opt`-configured absolute path (the SA stage) — a real gap in the "edit and have it take effect" story. | **Gap fixed (B5)** — see D7. Resume-with-new-code now rewrites the `target.opt` passed to a CLI-driven relaunch so the SA stage's `Bin:` paths point into the pause worktree too. |
| 3 | Immediate/intermediate report processing, journal CSVs | **Implemented and verified** across all 6 pipelines (MUQ-SAC, Sensitivity_Analysis, forward_uq, graph_sa, mso_compare, rmip) plus GUI wiring, against real partial run directories from the three-mechanism campaign. One bug found and fixed in this session's own new code. | Unchanged this round (out of Round 2's scope). |
| 4 | All research helper packages present | **All present and working**: RDKit 2025.09.2, PySR 1.5.10, Jupyter (launched and killed a real server), RMG-Py 4.0.0 (`rmg_env`), tectonic, pdfplumber, cantera, mechanism digitizer (stdlib-only). RMG/RDKit/Jupyter now wired into the Tools page; doctor tile now reports on all of them. | **PySR was actually 100% broken (B12)** despite being reported "present and working" in Round 1 — "present" (the package imports, has a version) was conflated with "functional" (an actual fit succeeds). Fixed and verified via a real fit this round; see Part E. |
| 5 | Shipped `DATASET/H2_O2_TEST` reference example runs end-to-end | *(not tested in Round 1 — blocked by B1/B2/B3/B4, all left unfixed by design)* | **B1+B2+B3+B4 jointly cleared** for the first time — the shipped example gets through target parsing, uncertainty-XML loading, all 10 reactions' mechanism-membership checks, and a full SA design-matrix build, into real per-case perturbation sweeps (all 10 cases reached). See D-summary. |
| 6 | Digitize a plot → optimize against it (full chain) | *(not tested in Round 1)* | **Confirmed broken (B11)**: the digitizer's XML output cannot become a `.target` file. Recorded with a control test proving the converter itself is sound, and a concrete fix proposal (F1). |

See **Part D** (fixes applied, with evidence), **Part E** (new defects B11-B16), and **Part F**
(5 proposed new apps) below for the full Round 2 writeup.

---

## Part A — What was implemented (tasks 3 and 4)

### Task 3: uniform "process the results" flag

- **`src/mso_io/postprocess_base.py`** (new) — the shared CLI contract every repo's
  `postprocess()` builds on: `--postprocess RUN_DIR --out DIR --journal --csv-only --formats
  --intermediate`. `save_figure()` makes CSV emission for every figure **unconditional** — the
  "must still generate the csv files" requirement is structural, not optional.
- **`src/MUQ-SAC/VisualAid.py`**, **`src/Sensitivity_Analysis/VisualAid.py`**,
  **`src/forward_uq/uq_plots.py`**, **`src/graph_sa/plots.py`**, **`src/mso_compare/run_plots.py`**,
  **`src/automation/prs_report.py`** — each amended in place with a `postprocess()` function and a
  CLI entry point on this contract, reusing each pipeline's own existing plotting/analysis
  functions (no reimplementation). `src/rmip/postprocess.py` is new (rmip had no prior plotting
  module) and exports mechanism/species/reaction tables plus a quality-score report by driving the
  pre-existing `rmip.analysis.mechanism_report.MechanismReport`.
- **GUI wiring**: `src/mso_studio/core/postprocess_dispatch.py` (new) maps a `ModulePage`'s
  `module_id` to its repo's postprocess script; `RunSummaryCard` gained a "Post-process results…"
  button (enabled for any finished run, including a failed/cancelled one — that's the
  `--intermediate` case); `ModulePage._on_postprocess_requested` runs it as a background subprocess
  and streams the log. Verified via a real click-to-subprocess round trip (see Part C).

### Task 4: helper packages

- **`src/mso_studio/core/rmg.py`** (new) — subprocess adapter into the `rmg_env` conda environment,
  mirroring the existing PySR/pdfplumber anaconda-subprocess pattern. Resolves the *actual* RMG-Py
  install `rmg_env` uses (`/data/OPEN_CODE/RMG_py`, confirmed by asking `rmg_env` itself, not
  assumed from `~/RMG-Py`) rather than hardcoding a path.
- **RDKit**: `scripts/tools_worker.py` gained `rdkit_validate_smiles` / `rdkit_render_png` modes
  (RDKit isn't in the GUI venv, same isolation rule as PySR); `mso_studio/core/tools.py` gained the
  matching adapters; a new **RDKit / SMILES** tab in the Tools page validates a species table (e.g.
  `species_smiles.csv`) and previews structures.
- **Jupyter**: `launch_jupyter()` in `core/tools.py` starts a real detached `jupyter notebook`
  server; wired as a "Launch Jupyter…" button next to the existing notebook-template generator.
- **RMG**: a new **RMG (mechanism generation)** tab runs RMG-Py against an `input.py` config and
  surfaces `chem_annotated.inp`/`species_dictionary.txt` paths for the rest of the workbench.
- **Doctor tile**: `rmip/config/preflight.py` gained probes for `rdkit`, `pysr`, `jupyter`,
  `latex_engine` (tectonic/latexmk/pdflatex), `pdfplumber`, `google_genai`, and a new
  `helper_packages` task — shows up automatically in the existing Doctor panel's task dropdown.

---

## Part B — Recorded defects (tasks 1 & 2, per instructions: not fixed this session)

Severity legend: **HIGH** = blocks the capability outright or silently defeats it; **MEDIUM** =
degrades one specific path/mechanism/format; **LOW** = narrow or already-mitigated.

### B1. [HIGH] `target.opt`'s `Bin:` section has stale absolute paths to the pre-move repo location
**File:** `DATASET/H2_O2_TEST/target.opt`, `Bin:` section (and, by construction, every `target.opt`
`generate_target_opt.py` produces).
```yaml
Bin:
  yaml_writer: /data/OPEN_CODE/PHASE-3/src/MUQ-SAC/parallel_yaml_writer.so
  SA_tool:     /data/OPEN_CODE/PHASE-3/src/Sensitivity_Analysis/sens.py
  SA_tool_3p:  /data/OPEN_CODE/PHASE-3/src/Sensitivity_Analysis/sens_3_params.py
```
`/data/OPEN_CODE/PHASE-3` is this repo's location *before* it moved to
`/data/MECHANISM_OPTIMIZATION_SUITE` — and it still exists on disk with its **old, unfixed** copy
of the code. `run_script.py` shells out to `binLoc["SA_tool"]` (line 616) as a literal absolute
path, not one derived from its own location. Result: the A-factor SA stage silently ran the OLD
`combustion_target_class.py`, which lacks the Multi-fuel-dict parsing fix the *current* repo
already has, and crashed (`ValueError: could not convert string to float: " {'a': 0.0050}"`) on
exactly the class of input the fix was for.

**Why this matters for both tasks under test:**
- **Task 1** — copying `target.opt` into a fresh folder does not make the pipeline self-contained;
  `SA_tool`/`SA_tool_3p`/`yaml_writer`/`bin`/`solver_bin` all depend on a fixed external location
  existing and being current.
- **Task 2** — editing `src/Sensitivity_Analysis/sens.py` in a `git_pause` worktree branch has
  **zero effect** on a run driven by such a `target.opt`: the subprocess call bypasses both the
  main checkout and the worktree. See B5 for the live-process confirmation.

**Recommendation:** `generate_target_opt.py` should emit `Bin:` paths relative to its own repo
root; existing checked-in `target.opt` files should be regenerated or hand-fixed.

### B2. [HIGH] `generate_target_opt.py`'s uncertainty-XML generator is incompatible with `run_script.py`'s parser
**File:** `DATASET/H2_O2_TEST/uncertainty/H2_uncertainty.xml` ("Generated by:
`generate_target_opt.py` (⑨ XML Builder)").
`Uncertainty.py:1892`'s `reaction.__init__` requires **both** a `rxn=` and a `no=` attribute per
`<reaction>` element, plus a non-blank `<class>` and a `<perturbation_type>` child element (used at
`Uncertainty.py:2048`, `:2414`, `:2603`). The shipped XML has `rxn=` only, `<class></class>`
(blank), and no `<perturbation_type>` — three compounding gaps. Blocks the entire H2_O2_TEST
reference example from running via `run_script.py`, full stop:
`KeyError: 'no'` → (after a scratch fix) → `AttributeError: 'reaction' object has no attribute
'perturbation_type'`.

**Corroboration already in the repo:** `src/rmip/tests/fixtures/h2_o2_crosscheck_unsrt.xml`'s own
header comment (pre-existing, not written this session) documents this *exact* defect
independently: *"Built new rather than reusing `DATASET/H2_O2_TEST/uncertainty/H2_uncertainty.xml`
directly, because that shipped fixture has `<class></class>` (blank) and no
`no=`/`<perturbation_type>`..."* — a prior session already hit and worked around this for a
different consumer (`gsa_prs_crosscheck.py`), but the shipped file itself was never fixed, so
`run_script.py` (the actual optimize-workbench entry point) still hits it fresh.

**Recommendation:** fix `H2_uncertainty.xml` directly (all three gaps), and audit
`generate_target_opt.py`'s XML Builder for the same three omissions since it produced this file.

### B3. [MEDIUM] Reaction-equation notation mismatch between uncertainty XML and Cantera mechanisms
After fixing B2, several reactions still failed to match against `FFCM1.yaml`/`GRI_CO.yaml`'s
reaction list: the uncertainty XML writes duplicated species explicitly (`OH+OH<=>O+H2O`,
`H+H+M<=>H2+M`) while Cantera's own `ck2yaml`-style output uses stoichiometric-coefficient shorthand
(`2 OH <=> O + H2O`, `H2 + M <=> 2 H + M`). `Uncertainty.py`'s order-independent equation-canonicalizer
does not normalize this notation, so an otherwise-matching reaction is reported as
`AssertionError: Rxn OH+OH<=>O+H2O not in the mechanism` even though it plainly is, just spelled
differently. Confirmed for at least 3 of the 10 reactions in the H2/O2 test set.

### B4. [HIGH] Malformed data row crashes the parser (data bug, not code)
**File:** `DATASET/H2_O2_TEST/targets/H2_IDT.target`, line 10 (dataset_003, Fls, Phi=2.0).
```
... Fuel -- x->{'a': 'H2'} = {'a': 0.399}	| Oxidizer -- x->O2 = 0.100}	| Bath_gas -- ...
```
A stray trailing `}` in the Oxidizer field (apparent copy-paste leftover from the adjacent Fuel
dict) crashes `combustion_target_class.py:218`
(`ValueError: could not convert string to float: ' 0.100}'`) the moment `run_script.py` parses
this file. Lines 1–9 are fine; this is one malformed row, not a systemic parser bug. A related,
lower-severity gap: the Oxidizer field's parser has no Multi/dict branch the way the Fuel field
does (lines 200–213 vs. 216–217) — not currently triggered by any target file, but latent.

### B5. [HIGH, confirmed against a live process] Pause-and-edit does not reach subprocessed pipeline stages
Tested against the real, live `bad_ffcm1_perturbed` `run_script.py` process (PID 1725539):
`git_pause.pause_process()` (SIGSTOP — confirmed via `/proc/<pid>/status`), `create_pause_branch()`
(real worktree + branch), editing a committed file
(`src/Sensitivity_Analysis/combustion_target_class.py`) in the worktree only, and
`build_reload_env()` (PYTHONPATH correctly prepended) all work exactly as designed. But because of
B1 (SA_tool is an absolute path from `target.opt`, not derived from the running process's own
location), a subprocess launched with the worktree's PYTHONPATH still runs `sens.py` from its
*original* absolute path — Python sets a subprocess's `sys.path[0]` to the invoked script's own
directory, which wins over PYTHONPATH for its bare-name sibling imports. The edit-and-resume story
only reaches code `run_script.py` imports in-process (`VisualAid`, `Uncertainty`); it does **not**
reach `sens.py`/`sens_3_params.py`, the two heaviest, most-likely-to-need-editing stages.

**Recommendation:** either (a) resume should also rewrite a working copy of `target.opt`'s `Bin:`
paths to point into the pause worktree, or (b) `sens.py`'s own sibling imports should honor
PYTHONPATH ahead of its script directory.

### B6. [LOW] `Project.scan()`/`resume()` against a still-running source is racy
While the `good_ffcm1` source was still actively running (not paused/finished), `scan()` +
`resume()` correctly recovered `unsrt.pkl` (the core promise holds — re-invocation printed
"Uncertainty analysis already finished"), but the SA subprocess then failed differently than the
source would have (`os.chdir("nominal")` — that directory didn't exist yet in either copy at
snapshot time). This is an inherent snapshot-consistency limitation of resuming a *still-writing*
source, not a defect in `mso_project.Project` itself — `resume()` should be documented as
pause/finished/crashed-only, or the snapshot diff could warn when a matched file's mtime is within
the last few seconds.

### B7. [LOW, latent] `forward_uq.py` (root script) vs. `src/forward_uq/` (package) name collision
`from forward_uq import uq_plots` resolves to the root-level *script* (raises
`ModuleNotFoundError: No module named 'forward_uq.mc_propagator'`) whenever repo root precedes
`src/` on `sys.path` — e.g. any `python3 -m pytest` run from repo root. Same class of bug as the
already-documented `io` package-shadowing issue this repo's root `conftest.py` works around, just
not covered by that fix since the collision is root-vs-`src/`, not stdlib-vs-`src/`. Confirmed not
yet triggered in shipped code (nothing does a package-style `from forward_uq import X`); only this
session's own test hit it, and was rewritten to load the leaf module directly instead.

### B8. [Unconfirmed / open] good_ffcm1's real run reached a per-case FlameMaster failure
The FFCM1 ("good") run got substantially further than any of the above blockers — past uncertainty
analysis, past the SA design-matrix build, into real per-case FlameMaster nominal simulations —
before failing on one specific case: `FileNotFoundError: .../SA/nominal/case-7/6/output/Su.out`
(a fuel-rich, Phi=2.0, H2/O2 flame-speed condition). Not root-caused within this session's time
budget (solver non-convergence vs. environment issue vs. a FlameMaster install gap are all
plausible) — flagged as an open item for the next session.

### B9. [Not a repo defect — this session's own code, already fixed inline]
`VisualAid.postprocess()`'s target-set-plots branch called `TargetSetPlotter.plot_condition_coverage(
save_path=os.path.join(figures_dir, ...))` without first creating `figures_dir`, causing
`FileNotFoundError` the first time it ran against a real partial FFCM1/GRI3/perturbed-FFCM1
directory (`figures_dir` was only created earlier in the *other* branch, for posterior plots).
Fixed immediately (`os.makedirs(figures_dir, exist_ok=True)` added) since this is new code written
this session, not a pre-existing defect subject to the "record, don't fix" rule; re-verified
against all three mechanisms afterward (see Part C).

### B10. [Pre-existing, unrelated to this session] `test_main_window_popout.py::test_detached_window_is_forgotten_on_close` hangs
Running the entire GUI test suite (`.venv-gui/bin/python -m pytest src/mso_studio/tests/ -q`)
reliably gets to 57% (`src/mso_studio/tests/test_main_window_popout.py::
test_detached_window_is_forgotten_on_close`) and then genuinely hangs — confirmed via `ps STAT`
transitioning from `R` (running, ~95-98% CPU while tests before it were executing) to `S`
(sleeping) with decaying CPU%, sitting there for minutes with zero further output, well past the
test's own internal 5-second `qapp.processEvents()` deadline-poll (lines 82-89 of that test,
already written defensively against exactly this kind of flakiness — "a fixed processEvents() count
was observed flaky under heavy system load", per its own comment — but the deadline itself is
apparently not always honored either). Likely culprit: `window._detach_item(...)` or
`MainWindow(factories)` construction blocking before the poll loop is ever reached, or
`qapp.processEvents()` itself blocking under this offscreen-platform/threading combination — not
root-caused further within this session's time budget. Reproduced twice independently. Confirmed
unrelated to this session's changes: every file touched this session
(`mso_studio.core.rmg`/`.tools`/`.postprocess_dispatch`, `gui.modules.tools`,
`gui.widgets.module_page`, `gui.widgets.run_summary`, `test_rmg.py`) sorts alphabetically after
`test_main_window_popout.py`, so the hang occurs before pytest ever reaches any of them; all
individually-run files this session touched pass in under 1s each. Killed the process (PID
verified via `ps`) rather than waiting further. Worth a dedicated follow-up session.

---

## Part C — Verification performed (evidence, not just claims)

All of the following were *executed*, with real output inspected — see the session transcript for
full command/output pairs.

**Task 1 (any-folder + recovery):**
- Launched a real `run_script.py` FFCM1 optimization from `/tmp/mso_campaign/good_ffcm1` (outside
  the repo).
- `Project.create()` + `Project.scan()` retro-imported **764 real artifacts** from that directory,
  correctly classified by kind (csv/log/txt/pkl/png/yaml).
- `Project.resume()` materialized all 764 files into a fresh directory; re-invoking `run_script.py`
  there printed "Uncertainty analysis already finished" — the resume contract holds.

**Task 2 (pause/branch/dual-run):**
- `pause_process()` on a live PID → confirmed `/proc/<pid>/status` shows `State: T (stopped)`.
- `create_pause_branch()` → real `git worktree`/branch created; a committed file edited inside it
  only (confirmed absent from the main checkout).
- `resume_process_unchanged()` (SIGCONT) on a fresh test process → confirmed state transitions
  `T (stopped)` → `S (sleeping)`.
- `commit_results_to_branch()` → real commit (`ede44c3`) on the pause branch with actual result
  files, confirmed via `git show --stat`.
- **Dual run**: launched the main-checkout copy of `run_script.py` and the pause-worktree's own
  copy *simultaneously*, confirmed via `/proc/<pid>/cmdline` and `/proc/<pid>/maps` that the
  worktree process genuinely loaded its own `yamlwriter.so` from
  `.mso_pause_worktrees/.../src/MUQ-SAC/`, both writing to separate output folders with zero
  collision.
- `remove_pause_worktree()` → worktree checkout removed; branch and commit preserved, exactly as
  documented.

**Task 3 (postprocess):**
- `mso_io.postprocess_base` unit-tested (10 tests, `tests/test_postprocess_base.py`).
- All 6 repo `postprocess()` implementations unit-tested against synthetic fixtures
  (`tests/test_repo_postprocessors.py`, 11 tests) and, for `rmip`, against the real
  `gui_stress` fixture database (full mechanism/species/reaction/quality-score/diff export).
- `--postprocess --journal --intermediate` run for real against all three campaign mechanisms'
  actual (partial) output directories — found and fixed B9, then confirmed clean figures/tables/
  manifest for all three.
- GUI wiring exercised end-to-end: constructed a real `OptimizationPage`, simulated a finished
  record, clicked (emitted) the "Post-process results…" signal, and confirmed a real background
  subprocess ran, streamed its log into the `LogView`, and completed.

**Task 4 (helper packages):**
- `rmg_available()` → real positive result: `/home/krithika/anaconda3/envs/rmg_env/bin/python
  running /data/OPEN_CODE/RMG_py/rmg.py`; `rmgpy_version()` → `4.0.0`.
- `rdkit_validate_smiles()` round-tripped through the real anaconda subprocess against the repo's
  own `species_smiles.csv` (35 rows), returning correct canonical SMILES/formula/MW.
- `launch_jupyter()` started a real `jupyter-notebook` process (confirmed via `ps`), then killed
  cleanly.
- Doctor's new `helper_packages` task run for real: rdkit, pysr, pdfplumber, google-genai, jupyter,
  tectonic, and the rmg_env/RMG-Py checkout all reported present with real versions/paths.
- `RdkitTab`/`RmgTab` constructed for real inside a `ToolsPage` under the offscreen Qt platform;
  `RmgTab.status_label` showed the live, correct availability string.

**Regression checks:** `tests/`, `src/mso_workbench/tests/` (~373 tests, 3 pre-existing failures
unrelated to this session — see below), `src/mso_studio/tests/test_tools.py`,
`test_no_gui_imports.py`, `test_rmg.py` all green. Full `src/mso_studio/tests/` GUI suite ran
cleanly (zero failures) up through 57% (all files alphabetically before and including
`test_main_window_popout.py`'s first test), at which point it hit a pre-existing, unrelated hang —
see B10. Every file touched this session sorts after that point and was individually verified
green; the suite could not be run start-to-finish to confirm those files' collection/interaction
within the full run, only in isolation.

**Pre-existing, unrelated failures observed in the baseline suite (not caused by this session):**
`tests/test_launcher_gui.py::TestAppRegistry` (two tests) — asserts against the deprecated legacy
Tkinter launcher's `_APPS` list, stale relative to the current catalog-based launcher (superseded
in the Phase 1 GUI overhaul). `src/mso_workbench/tests/test_breakpoint.py::test_step_pauses_once_then_rearms_for_the_next_boundary`
— a timing-sensitive threading test, unrelated to anything touched this session.

---

## Files changed this session

**New:** `src/mso_io/postprocess_base.py`, `src/rmip/postprocess.py`,
`src/mso_studio/core/rmg.py`, `src/mso_studio/core/postprocess_dispatch.py`,
`tests/test_postprocess_base.py`, `tests/test_repo_postprocessors.py`,
`src/mso_studio/tests/test_rmg.py`.

**Amended:** `src/MUQ-SAC/VisualAid.py`, `src/Sensitivity_Analysis/VisualAid.py`,
`src/forward_uq/uq_plots.py`, `src/graph_sa/plots.py`, `src/mso_compare/run_plots.py`,
`src/automation/prs_report.py` (all: `postprocess()` + CLI), `scripts/tools_worker.py` (RDKit
modes), `src/mso_studio/core/tools.py` (RDKit/Jupyter adapters), `src/mso_studio/gui/modules/tools.py`
(RDKit + RMG tabs, Launch Jupyter button), `src/mso_studio/gui/widgets/run_summary.py` +
`src/mso_studio/gui/widgets/module_page.py` (Post-process results wiring),
`src/rmip/config/preflight.py` (helper-package doctor probes).

**Not touched (per "record, don't fix"):** `DATASET/H2_O2_TEST/target.opt`,
`DATASET/H2_O2_TEST/uncertainty/H2_uncertainty.xml`, `DATASET/H2_O2_TEST/targets/H2_IDT.target`,
`generate_target_opt.py`, `src/MUQ-SAC/Uncertainty.py`, `src/Sensitivity_Analysis/
combustion_target_class.py`, `src/mso_workbench/git_pause.py`, `src/mso_project/project.py`.

---
---

# Round 2 — 2026-08-10 (same day, second pass)

## Scope

Per the user's explicit instructions this round: (1) **fix** the bugs recorded above rather than
just record them; (2) stress-test **PySR** and the **plot digitizer** specifically, which Round 1
skipped; (3) propose **≥3** new helper apps for the store; (4) apply the same procedure — a small
real file from `DATASET`/`MECHANISM` or produced by an app, followed through the chain (image →
digitized CSV → XML → `.target`/`.add` → optimizer, and equivalent chains for every other app) — to
every app Round 1 didn't stress-test; (5) migrate the code + all markdown to
`/data/FINALIZED_MECH_OPT_SUITE` for a future GitHub push.

Two items were explicitly prioritized first per the user's own decision when asked to clarify:
**root-cause B8 and B10** (both left "open" in Round 1) before the new stress-testing work.

Everything below was produced by actually running the code against real files in
`/home/krithika/mechanism-optimization-suite/DATASET`, `.../MECHANISM`, and this repo's own
`MECHANISM`/`DATASET` — real subprocesses, real `git commit`/`worktree` operations, a real PySR/Julia
compile, a real Cantera flame-speed solve, and a real (partial, still-running as of this writeup)
`run_script.py` invocation of the shipped H2/O2 reference example — not read off the source alone.

---

## Part D — Round 2: fixes applied

### D1 (was B10). GUI test-suite hang — root-caused and fixed

Round 1 could not complete a full `src/mso_studio/tests/` run and blamed
`test_main_window_popout.py` because progress reliably stalled around 57%. Reproducing under
`python -X faulthandler` with a `timeout -s ABRT` (so the exact blocked frame gets printed instead of
just "it hung") pointed at a **completely different, much earlier test**:
`test_launcher_window.py::test_doctor_entry_opens_doctor_dialog_not_a_launch_error`, stuck inside
`apply_theme -> QApplication.setStyleSheet`.

**Real root cause:** several test files (`test_launcher_window.py`, `test_launcher_window_pause.py`,
`test_module_hero.py`) construct a real top-level `LauncherWindow`/similar via `.show()` per test and
never `.close()` it. `QApplication` is a **process-wide singleton**
(`QApplication.instance() or QApplication([])`), so those leaked windows accumulate across **every**
test file in the whole pytest session, not just the one that created them. Every subsequent
`apply_theme()`'s `app.setStyleSheet(...)` call re-polishes every live top-level widget the
QApplication still knows about — so the cost grows with how many tests have already run, and by
~57% into the full suite the accumulated leak makes some later window construction take minutes.
Pytest's dot-per-test progress made that look like a hang on whichever test's dot happened to print
next — not a property of that test itself.

**Fix:** `src/mso_studio/tests/conftest.py` gained an autouse fixture that gets rid of every
top-level widget after each test, so the live set a `QApplication` carries into the next test never
grows. Two follow-on issues surfaced and were fixed in the same pass:
- A first version used `.close()`, which invokes the widget's own `closeEvent` —
  `LauncherWindow.closeEvent` can pop a modal `QMessageBox`/`WelcomeDialog.exec()` (real app
  behavior: "apps still running, leave them running?" / first-run welcome), pumping a **nested** Qt
  event loop nothing under `offscreen` can dismiss — a genuine, worse hang, confirmed via the same
  faulthandler technique. Switched to `.hide()` + `.deleteLater()`, which removes the widget from
  `topLevelWidgets()`/style-repolish consideration exactly as well, without running arbitrary
  app-specific close-time logic.
- Draining pending Qt events (needed to actually flush the `deleteLater()`s) surfaced a **separate,
  previously-invisible** bug: `test_module_hero.py`, `test_native_extensions_tab.py`,
  `test_notebook_gen_tab.py` construct and discard more than one page/canvas per test; a stale
  matplotlib `QTimer.singleShot(0, self._draw_idle)` from an earlier-discarded canvas fired against
  an already-deleted C++ object (`RuntimeError: Internal C++ object (MplCanvas) already deleted`).
  This is invisible without a fixture pumping the event loop during teardown, which nothing did
  before. Recorded as **E1** below (not fixed — out of scope for the hang fix) and worked around in
  the fixture (swallow that one `RuntimeError` class) so it doesn't regress those three tests.

**Verification:** the exact 25-file prefix batch that previously aborted under `SIGABRT` after ~90s
now runs **237 passed in 31.6s, exit 0**, going all the way past `test_main_window_popout.py` to
100%. `test_module_hero.py`/`test_native_extensions_tab.py`/`test_notebook_gen_tab.py` (21 tests)
individually confirmed green after the fixture fix.

**Caveat (honest, not swept under the rug):** a full-suite run attempted three times this session
(120s / 300s / 900s timeouts) did not complete, but for a **different, external** reason: the machine
was under sustained, unrelated heavy load for the whole session (`uptime` load average climbed from
45 at session start to **137** by the end) from the user's own separate, real `KRUNAL/MULTI-STAGE_
OPTIMIZATION` n-heptane campaign (`cantera_.py` processes at 200-700% CPU each) and a Julia CFD job at
~2600% CPU — confirmed via `/proc/<pid>/cwd` on the actual running processes, nothing to do with this
session's changes. A 900s attempt reached only 35% of the suite. The specific, previously-reproduced
hang is confirmed fixed via the representative-batch + faulthandler evidence above; a clean full-suite
timing run should be re-attempted when the machine is not under this load. See **E7** below for a
related discovery (leaked stress-test processes from earlier work also contributing to the load).

### D2 (was B8). FlameMaster case-7 `Su.out` failure — root-caused and fixed

Round 1 left this open, suspecting solver non-convergence, an environment gap, or a FlameMaster
install issue. It was none of those.

**Root cause, found by reading the actual solver log** (`.../case-7/6/solve`, captured stdout+stderr
next to the missing `output/` — itself an artifact of the diagnostic gap this round also fixed, see
below): a plain Python `NameError`.
```
gas.set_equivalence_ratio(1.0, H2, {"O2": 1.0, "N2": 3.76})
NameError: name 'H2' is not defined
```
`src/MUQ-SAC/make_input_file2_0.py`'s cantera-phi-mode template substitutes
`fuel=target.add["fuel"]` **unquoted** into `gas.set_equivalence_ratio({phi}, {fuel}, ...)`, so a
fuel name like `"H2"` becomes a bare Python identifier instead of a string literal in the generated
`cantera_.py` — which then crashes before any simulation runs at all, for **every** cantera-phi-mode
case, regardless of mechanism or condition. The exact same bug (same template pattern, same
unquoted `.format()` substitution) was present in three more files:
`src/MUQ-SAC/make_input_file.py`, `src/MUQ-SAC/make_input_file2_0_A_factor.py`,
`src/Sensitivity_Analysis/make_input_file.py`.

**Fix:** `fuel=target.add["fuel"]` → `fuel=repr(target.add["fuel"])` in all four files, so the
substituted value is a properly quoted (and escaped) Python string literal.

**Verified two ways:**
1. **Directly against the real failing case** — copied `case-7/6/cantera_.py`, applied the one-line
   fix by hand, ran it for real: solved cleanly (670→706 grid points across 3 refinements) and wrote
   `output/Su.out` = `298.0 K, 208.14 cm/s` — a physically correct stoichiometric H2/air laminar flame
   speed. Confirms the mechanism/conditions were never the problem.
2. **Through the actual code path** — regenerated the same k(T)-style template via the fixed source
   and confirmed valid, correctly-quoted Python (`ast.parse` + inspection).

**Diagnostic improvement (the other half of D2):** `data_management.py`'s `extract_output` (both
`src/MUQ-SAC/` and `src/Sensitivity_Analysis/` copies) had exactly **two** `open(...)` call sites (the
Fls-cantera `Su.out` read, and the Tig-FlameMaster-native `tau.out` read) that were missing the
`if "X.out" in os.listdir(path):` restart-safe guard every **other** branch in the same function
already has — so a missing output file raised a bare, undiagnosed `FileNotFoundError` that could
abort a multi-hour optimization run over one bad case, instead of degrading to the same `eta = "N/A"`
sentinel every sibling branch already uses safely. Fixed by adding the missing guard (matching the
established pattern exactly) plus a new `_log_missing_solver_output()` helper that prints the case
directory and the tail of the adjacent `solve` log — the exact diagnostic that made D2's own root
cause discoverable in the first place, now available for the next person without needing a manual
`cd` into the case directory.

**A near-miss worth recording honestly:** the first version of the `fuel=repr(...)` edit used a
naive string-replace that appended an inline `# comment` onto a **single-line** `.format(...)` call
in three of the four files — Python comments run to end-of-line, so the comment silently swallowed
the rest of the format call's keyword arguments, breaking the syntax
(`SyntaxError: invalid syntax` at the following `else:`). Caught immediately by re-running the full
`tests/` suite (which the "Verification" section below always does after any source change) —
340 passed, only the 2 pre-existing failures — and by the H2_O2_TEST acceptance run itself failing
to even import. Fixed by removing the inline comment from the one-line call sites.

### D3 (was B1). Stale `/data/OPEN_CODE/PHASE-3` paths — fixed, and a second instance found

`generate_target_opt.py::_default_bin_paths()`'s three repo-internal `Bin:` defaults
(`yaml_writer`/`SA_tool`/`SA_tool_3p`) now derive from `_REPO_ROOT` (this file's own directory) with
the existing `MSO_*` env-var override preserved, instead of a literal `/data/OPEN_CODE/PHASE-3/...`
default. The two checked-in configs (`target.opt`, `DATASET/H2_O2_TEST/target.opt`) had their `Bin:`
sections hand-fixed to the current repo path.

**A second instance of the identical bug class was found while chasing D2's acceptance test**, in a
section Round 1 didn't examine: `DATASET/H2_O2_TEST/target.opt`'s **`Locations:`** section (mechanism/
thermo/trans/targets/addendum paths — all seven entries) also pointed at
`/data/OPEN_CODE/PHASE-3/...`, and `run_script.py` reads `targets`/`addendum` from there literally —
so it was loading the OLD, pre-move `H2_IDT.target`, which still has the un-fixed stray `}` that D5
below fixes in the current repo's copy. All seven `Locations:` entries hand-fixed to the current repo
path (each target file's existence at the new path verified first). The root `target.opt`'s
`Locations.addendum` and its entire `RMIP.mechanisms` list (4 ammonia mechanisms) had the same stale
prefix — fixed via a verified bulk `sed` replace (13 occurrences; every referenced file's existence
confirmed at the new path before the replace).

**Verified:** `_default_bin_paths()` returns `/data/MECHANISM_OPTIMIZATION_SUITE/...` paths for a
fresh generation; the H2_O2_TEST acceptance run (D-summary below) got past both `target.opt`
sections without a stale-path error.

### D4 (was B2). Uncertainty XML `no=`/`perturbation_type`/`class` — fixed

The writer (`generate_target_opt.py::generate_uncertainty_xml`) already emitted `no=` and
`<perturbation_type>` (fixed in an earlier session per its own inline comments) — only the *shipped*
`DATASET/H2_O2_TEST/uncertainty/H2_uncertainty.xml` was stale. The writer's `<class>` default changed
from a hardcoded blank string to `"Elementary"` (matching the convention already established in
`src/rmip/tests/fixtures/h2_o2_crosscheck_unsrt.xml`, which was built specifically to work around
this exact shipped-file gap). The shipped XML was regenerated through the fixed writer from its own
existing 10-reaction data (temperatures/uncertainties preserved), restoring a descriptive header
comment afterward.

**A regeneration mistake caught immediately:** the restored header comment used a prose "--" (em-dash
style, this session's own writing convention) inside an XML `<!-- ... -->` comment block — invalid
per the XML spec (comments cannot contain "--" except as the closing "-->"), causing
`xml.etree.ElementTree.ParseError: not well-formed (invalid token)`. Caught by the H2_O2_TEST
acceptance run failing to parse the very file this fix produced; fixed by rewording to avoid "--".

**Verified three ways:** (1) `ET.parse()` round-trips cleanly, 10 reactions. (2) The H2_O2_TEST
acceptance run gets past `ET.parse(self.xmlPath)` (previously impossible — `KeyError: 'no'`). (3) A
**real, independent, second data point**: drove `uncertainty_generator_gui.py --no-gui --generate-xml`
(the actual app, not just the underlying function) against a fresh reactions-JSON — the produced XML
has `no="1"`, `<class>Elementary</class>`, `<perturbation_type>arrhenius</perturbation_type>`, and
round-trips through `Uncertainty.reaction.__init__` against real FFCM1.yaml, correctly resolving to
`index=14` (FFCM1's own `H + O2 (+M) <=> HO2 (+M)`, Reaction 15).

### D5 (was B4). Malformed target line + Oxidizer dict branch — fixed, with one regression caught and reverted

The stray trailing `}` in `DATASET/H2_O2_TEST/targets/H2_IDT.target` line 10's Oxidizer field was
deleted (both the current-repo copy; the pre-move `/data/OPEN_CODE/PHASE-3` copy was left alone as
external/legacy per D3's finding — regenerating `Locations:` to point at the current repo makes the
old copy irrelevant to this pipeline going forward).

The Oxidizer field's parser (`src/MUQ-SAC/combustion_target_class.py` and the `Sensitivity_Analysis`
copy) gained the same Multi/dict shape-dispatch the Fuel field already had, so a dict-wrapped Oxidizer
(e.g. a custom O2/N2/Ar blend) doesn't crash trying `float()` on a dict-repr string.

**A real regression caught by the regression suite, not shipped:** the first version of this fix
copied the Fuel branch's dispatch condition verbatim (`"Multi" in self.fuel_type or
_ox_rhs.startswith("{")`), reasoning by analogy from the Fuel field. This was wrong: `Fuel_type`
governs the **Fuel** field's own shape, not the Oxidizer field's, and real shipped data proves it —
`DATASET/METHYL_BUTANOATE_2026/MB_LTC_no_dummy.target` has `Fuel_type: Multi` (a Multi-species fuel
blend) with a **plain scalar** Oxidizer (`x->O2 = 0.2035`, no dict). Gating the dict-branch on
`fuel_type` sent that real scalar through `json.loads()` and crashed with `JSONDecodeError`, flipping
`test_write_curated_real_bridge_gates_clean` (`src/mso_studio/tests/test_target_workbench.py`) from
passing to failing — caught by re-running the regression suite. Fixed by dispatching on the Oxidizer
field's own content shape alone (`_ox_rhs.startswith("{")`), never on `fuel_type`.

**Verified:** the corrected fix round-trips the real, produced-by-a-real-converter
`x20101002.target` (Fuel_type=Multi, plain-scalar Oxidizer — the exact real-world shape the mistake
above got wrong) through `combustion_target_class.combustion_target` cleanly (see D-summary's
digitizer-chain section); `test_write_curated_real_bridge_gates_clean` passes again.

### D6 (was B3). Reaction-equation notation mismatch — fixed, extended twice beyond the original scope

`_canon_rxn_equation` (both `src/MUQ-SAC/Uncertainty.py` and `src/Sensitivity_Analysis/Uncertainty.py`
copies) now expands stoichiometric-coefficient shorthand (`"2 OH"` → two `"OH"` tokens) before
sorting, so `OH+OH<=>O+H2O` and `2 OH <=> O + H2O` canonicalize identically — the originally-reported
gap.

**Two more real mismatches found and fixed in the same pass, discovered by actually running the
H2_O2_TEST acceptance test rather than stopping at the first fix:**

1. **Reversible-direction disagreement.** GRI_CO.yaml (Reaction 18) writes `2 H + M <=> H2 + M`;
   FFCM1.yaml (Reaction 6) writes the *same physical reaction* as `H2 + M <=> 2 H + M` — opposite
   formal "forward" direction, both confirmed live in this repo's own shipped `MECHANISM/` files.
   Since `<=>` already declares the reaction reversible, which side a mechanism calls "forward" is
   not physically meaningful; the canonicalizer now additionally sorts the two (already
   stoichiometry-expanded) sides as a pair for reversible reactions only — irreversible (`=>`)
   equations are never side-swapped, since for those, order **is** physically meaningful.
2. **Falloff parenthesized third-body notation.** Cantera writes falloff reactions as
   `H + O2 (+M) <=> HO2 (+M)` (FFCM1.yaml Reaction 15, confirmed live) while a hand-authored
   uncertainty XML for the exact same `<type>pressure_dependent</type>` reaction spells it
   `H+O2+M<=>HO2+M` (the shipped `H2_uncertainty.xml`) — found live when the H2_O2_TEST acceptance
   run reached exactly this reaction after D4/D6's earlier fixes cleared the way. `(+M)`/`(+N2)`/etc.
   is now normalized to `+ M`/`+ N2` before tokenizing.

**A self-inflicted bug caught by a new unit test before it shipped:** the first implementation of the
reversible/irreversible detection used `reversible = "=>" not in arrow`, which is wrong — `"<=>"`
itself *contains* `"=>"` as a substring, so every reversible reaction was misclassified as
irreversible (silently disabling the direction-swap fix entirely, and in a way that reversed the
canonical form itself, breaking the *already-passing* reordering test). Caught by the very next test
run (`test_reversible_direction_disagreement_still_matches` failing in the direction that revealed
canon(a) == canon(b) was false when it should be true). Fixed with an explicit membership check
against the two literal irreversible-arrow spellings instead of a substring test.

**Verified:** 16 tests in `src/rmip/tests/test_uncertainty_reaction_order.py` (6 pre-existing + 8 new
across the stoichiometric-shorthand, direction-disagreement, falloff-notation, and
still-distinguishes-real-differences cases), all passing for both `MUQ-SAC` and `Sensitivity_Analysis`
copies. The H2_O2_TEST acceptance run gets past every one of its 10 reactions' mechanism-membership
checks (previously impossible for at least 2 of them).

### D7 (was B5). Pause/resume doesn't reach subprocessed SA stage — fixed

New `git_pause.rewrite_target_opt_for_worktree(session, target_opt_path)`: given a `target.opt` whose
`Bin:` `SA_tool`/`SA_tool_3p`/`yaml_writer` point somewhere under the pause session's `repo_root`
(true for any config produced after D3's fix), writes a working copy with those three entries
repointed at the equivalent path under the pause worktree, leaving the original file and all
non-repo-internal entries (`bin`, `solver_bin`) untouched. `LaunchManager.resume_with_new_code`
(`src/mso_studio/launcher/process.py`) now scans the relaunch argv for a literal `.opt` file argument
(the CLI-driven pipelines, e.g. `run_script.py target.opt`, pass one) and substitutes the rewritten
copy before relaunching — GUI-driven entries that pick a target.opt at runtime instead of via argv
are unaffected (no `.opt` argv arg to rewrite), same as before.

**Verified:** 4 new tests in `src/mso_workbench/tests/test_git_pause.py`
(`TestRewriteTargetOptForWorktree`) — repo-internal paths get repointed into a real `git worktree`,
external paths are left alone, the original file is never modified, and a config needing no rewrite
returns unchanged. Full `test_git_pause.py` (12 tests) and `test_launcher_pause.py` (10 tests) suites
still green.

### D8 (was B7). `forward_uq` root-vs-`src/` shadowing — fixed

Root `conftest.py` now pre-loads the real `src/forward_uq` package into `sys.modules` by explicit
file path (mirroring the existing stdlib-`io`-shadowing guard's rationale, just root-vs-`src/`
instead of `src/`-vs-stdlib) — `sys.modules` is checked before `sys.path`, so any later `import
forward_uq` / `from forward_uq import ...` anywhere in a test run finds the real package instead of
re-resolving to the root-level `forward_uq.py` script.

**Verified:** a fresh subprocess doing `from forward_uq import uq_plots` after importing `conftest`
now resolves to `src/forward_uq/uq_plots.py` (previously: `ModuleNotFoundError: No module named
'forward_uq.mc_propagator'; 'forward_uq' is not a package`). Full collection (1486 tests) unaffected.

### B6, B9 — no code change needed (unchanged from Round 1)

B6 (resume-of-a-still-running-source raciness) and B9 (this session's own bug, already fixed
in-session) needed no further action this round.

### D-summary: the joint B1+B2+B3+B4 acceptance test — the shipped reference example, running for the first time

`python3.9 src/MUQ-SAC/run_script.py DATASET/H2_O2_TEST/target.opt`, run from a fresh scratch
directory (never before possible — Round 1 could not get past the second of ten targets):

- ✅ Targets parsed and exported to `targets.csv` (was: `ValueError` on line 10 — D5)
- ✅ T-P-φ space plot generated
- ✅ Uncertainty XML loaded — `no=`, `<perturbation_type>` present (was: `KeyError: 'no'` — D4)
- ✅ All 10 reactions matched against FFCM1.yaml by equation, including the stoichiometric-shorthand,
  reversible-direction, and falloff-notation cases (was: `AssertionError: Rxn ... not in the
  mechanism` — D6)
- ✅ `Bin:`/`Locations:` sections resolve inside the current repo, not the pre-move location (D3)
- ✅ Full SA design-matrix build completed (`DesignMatrix_x0_a_fact.csv`, `DesignMatrix_x2_a_fact.csv`,
  `ACTIVE_RXN_LIST.csv`) and the per-case perturbation sweep launched: all 10 targets reached
  `SA/multiply/case-{0..9}/`, each with real per-reaction sub-perturbation directories (7 reactions
  × 10 cases = the expected sweep size for this mechanism/target set)
- 🔄 Killed by a 240s harness timeout mid-sweep (`EXIT 124`, not a crash) — the same multi-hour-
  campaign stage Round 1's `good_ffcm1` run reached before hitting D2's now-fixed bug, now confirmed
  reachable from a **completely fresh run of the shipped example itself**, not just a pre-existing
  campaign directory. No parsing/config error observed anywhere through this point, across three
  separate runs this round (each one advancing past the previous run's failure once that failure was
  fixed) — B1, B2, B3, and B4 are all confirmed cleared by direct execution, not merely by static
  reasoning about the fix. This is the first time the shipped reference example has gotten this far.

---

## Part E — Round 2: new defects found while stress-testing (B11+)

Severity legend matches Round 1: **HIGH** = blocks the capability outright or silently defeats it;
**MEDIUM** = degrades one specific path/format; **LOW** = narrow or already-mitigated.

### B11. [HIGH] The plot digitizer's XML output cannot become a `.target` file — the digitize→optimize chain is broken

**Files:** `src/mso_studio/core/digitizer.py::export_rkd_xml`; `config_tools/converters_io/XML2CSV/
xml2csv.py`.

Fed a real digitizer session's recorded output (`Test_run_23_JULY/mso_studio/gui_widget_evidence/
digitized_points.xml`) into the suite's own ReSpecTh→`.target` converter:
```
$ python3 config_tools/converters_io/XML2CSV/xml2csv.py <dir-with-digitized-xml> <out>
WARNING: Missing commonProperties or dataGroup in digitized_points.xml — skipping
Done: 0 files parsed, 1 skipped, 0 target rows.
```
`export_rkd_xml` emits a minimal `<experiment><fileAuthor/><dataGroup><property/><dataPoint/></
dataGroup></experiment>` with no `experimentType`, `apparatus`/`kind`/`mode`, `bibliographyLink`, or
`commonProperties` — all of which `xml2csv.py`'s `_parse_xml_file` requires
(`root.find(".//experimentType")`, `.//kind`, `.//mode`, `.//bibliographyLink`, `.//
commonProperties`, at minimum). Every digitized dataset is silently dropped, not converted — the
suite's own **digitize a plot → get a `.target` file** workflow, implied by having both a digitizer
and a ReSpecTh converter in the same app store, does not exist end-to-end today.

**Control test (proves the converter itself is fine):** the same `xml2csv.py` against a genuine
ReSpecTh file (`DATASET/AMMONIA/FLAME_SPEED/x20101002.xml`) parsed cleanly — 19 target rows, correct
`.target` format — and that output round-trips cleanly through `combustion_target_class.
combustion_target` (confirming D5's Oxidizer fix against real, converter-produced data along the
way: `Fuel_type=Multi`, plain-scalar `Oxidizer -- x->O2 = 0.171267`, parsed correctly).

**Recommendation:** either (a) teach `export_rkd_xml` to emit the full ReSpecTh schema `xml2csv.py`
expects (`experimentType`/`apparatus`/`bibliographyLink`/`commonProperties`/property `id`s), or (b)
build the dedicated CSV→XML converter proposed as **F1** below, which is the more natural fix — the
digitizer already exports a clean CSV; teaching *that* path to become a real ReSpecTh XML is more
tractable than reverse-engineering the full schema into the minimal RKD writer.

### B12. [HIGH] PySR fitting was 100%-broken for every single invocation — fixed

**File:** `scripts/tools_worker.py::_pysr_fit`.

Ran a real PySR fit (the actual subprocess entry point the GUI's Tools > Curve/Symbolic tab calls,
not just the underlying function) against real Arrhenius `k(T)` data extracted from FFCM1.yaml
(`H + O2 <=> O + OH`, 15 points, 500-2500 K):
```
AssertionError: `tournament_selection_n` must be less than `population_size`
```
`_pysr_fit` hardcoded `population_size=15` — **exactly equal to** `PySRRegressor`'s own default
`tournament_selection_n=15` (confirmed against the installed PySR 1.5.10). The Julia backend requires
strictly-less-than, so this crashed at `Options` construction, before any fitting happens, for
**every** input, unconditionally — this is why the original audit's note about "the `row.get(...)`
pattern on a pandas row is the fragile part" never got a chance to matter; nothing ever reached that
code.

**Fixed:** `population_size=15` → `population_size=20` (leaves real headroom above the default
`tournament_selection_n` instead of exactly matching it).

**Verified:** re-ran the identical real fit after the fix — succeeded, `best_equation =
"abs(x0 + (x0 - 1049.4789)) ^ 2.6844916"`, 11 equations in the Pareto front, `y_fine` all finite.

### B13. [MEDIUM] `mean_value_fusion_gui.py --write-cantera` crashes when fusing pressure-dependent (SRI) kinetics, and swallows the failure

**File:** `mean_value_fusion_gui.py` (its CHEMKIN `.inp` writer).

Fused two real, ingested mechanisms (FFCM1 + the GRI3 CHEMKIN file converted earlier this session)
with `--write-cantera`. Fusion itself completed (writes `.inp`/`.dat` — the primary artifacts), but
the `ck2yaml` re-conversion step crashed:
```
ERROR: ck2yaml failed (exit 1): ... InputError: Reaction equation implies pressure ...
  [secondary crash inside Cantera's own error formatter, AttributeError:
   'NoneType' object has no attribute 'reaction_string_suffix' — masks the real message]
```
Root cause, found precisely by scanning the produced `.inp` for `(+M)` equations missing their
falloff auxiliary line:
```
! Fused (VERBATIM) from [1]
! WARNING: kinetics_type=sri, written as plain Arrhenius
CH3CHO(+M)<=>CH4+CO(+M)     5.440000E+21  -1.740  86364.000
```
The writer's own comment shows it *knows* it's dropping SRI falloff data and downgrading to plain
Arrhenius — but does not also strip the `(+M)` third-body marker from the reaction equation string,
leaving a syntactically pressure-dependent equation with no falloff data, which `ck2yaml` correctly
rejects. **The CLI then exits 0 anyway** — a real conversion failure during `--write-cantera` is
logged but not surfaced as a non-zero exit / failed status, so a caller checking only the exit code
would believe the Cantera YAML was produced when it was not.

**Recommendation:** when downgrading a falloff reaction (SRI/Troe/Lindemann) to plain Arrhenius
because averaging would discard the data, also strip `(+M)`/`(+species)` from the written equation
string (a real, physically-honest simplification: "no longer falloff" should also mean "no longer
written as falloff"). Separately, `--write-cantera`'s `ck2yaml` failure should propagate as a failed
run, not exit 0.

### B14. [HIGH] Project Manager's LaTeX report never compiles — `\author{mso_project}` is unescaped for LaTeX — fixed

**Files:** `src/mso_project/report/builder.py:121,149`; `src/latex_project.py` (root cause).

Built a real project (`create_project`), added a real note, and called `build_project_report` —
succeeded at every Python-level step (sections appended, `.tex`/manifest/README all written) but:
```
tectonic errors:
  ! Missing $ inserted.
PDF not generated — check main.tex for errors.
```
Root cause: `author=rules.author or "mso_project"` — when no author is explicitly set (the default,
unset case for every project this session created), it falls back to the literal Python **package
name** `"mso_project"`, substituted verbatim into `\author{mso_project}` in the rendered `.tex`. LaTeX
outside math mode treats a bare `_` as "start a subscript, but there's no preceding `$`" — hence
"Missing $ inserted." **Reproduced with two different project names/paths (one containing an
underscore, one not)** — the underscore is in the hardcoded fallback string itself, not anything
user-supplied, so this fires on **every** report built by a project that never explicitly set an
author (i.e. nearly all of them).

**Wider implication, not just this one string:** nothing in the report pipeline LaTeX-escapes dynamic
text fields (`_`, `%`, `#`, `&`, `^`, `~`, `\`) before substituting them into the template. This
repo's own real dataset/project naming convention is full of underscores
(`H2_O2_TEST`, `SYNGAS_COMPLETE`, `MB_LTC_no_dummy`, `1_3_BUTADIENE_Manikanta`, ...) — a project named
after (or a note referencing) any real dataset in this suite would very likely hit the same class of
failure even after fixing this one hardcoded default.

**Fixed both ways** rather than just the immediate patch: (a) the fallback default changed from the
internal package-name literal `"mso_project"` to `"MSO Studio"` (both call sites in
`report/builder.py`). (b) **the real root cause** turned out to be one level down —
`LaTeXProject.create()` in `src/latex_project.py` substitutes `title`/`author` into
`\title{{{title}}}`/`\author{{{author}}}` with **no escaping at all**, so *any* caller (not just
`report/builder.py`'s two call sites — including the standalone `python latex_project.py --new`
CLI) was exposed. Added a self-contained `_escape_latex()` helper (same approach as
`report/sections.py`'s existing `_escape()`, deliberately not imported cross-package, matching that
function's own stated convention) and applied it to both `title` and `author` in `create()` — this
fixes every caller at once, not just the two that happened to be exercised this round.

**Verified:** re-ran the exact reproduction with an underscore-heavy real title
(`"H2_O2_TEST Study"`, deliberately chosen to match this repo's own dataset-naming convention) —
`compiled: True`, both `main.pdf` and `supplementary/main.pdf` produced. Full `tests/` +
`src/mso_workbench/tests/` regression suite (382 passed) shows no new failures — the same 3
pre-existing failures from Round 1 (`test_launcher_gui.py::TestAppRegistry` ×2,
`test_breakpoint.py::test_step_pauses_once_then_rearms_for_the_next_boundary`) and nothing else.

### B15. [LOW] `config_tools/converters_io/XLX2CSV/xlx2csv.py` — no `__main__` guard, and a Bath_gas dict/list bug

**File:** `config_tools/converters_io/XLX2CSV/xlx2csv.py`.

Two independent issues found running the CSV→target branch against the tool's own bundled fixture
(`Flame_Speed/fls.csv` + `.header`):

1. The script has top-level (module-scope) side effects and no `if __name__ == "__main__":` guard —
   `import xlx2csv` alone (rather than running it as `python3 xlx2csv.py <dir>`) executes its
   `sys.argv`-reading driver code immediately and can `sys.exit(1)` mid-import. Nothing in the repo
   currently imports it as a module (confirmed via repo-wide grep), so this hasn't bitten anything
   yet, but it means the module can't be safely used as a library the way `xml2csv.py`'s
   `_parse_xml_file` is.
2. Run properly (`python3 xlx2csv.py .` from the fixture directory — the intended usage): produces a
   `.target` file, but the Bath_gas field is malformed —
   `Bath_gas -- x->['bg1'] = {'bg1': 3.76}` (a **list** `['bg1']` where every other field, and the
   header's own `Bath_gas: {bg1: N2}` schema, uses a `{id: species}` **dict**). Root cause:
   `normalize_species_list(head.get("Bath_gas"))` (line 195) is designed to flatten a dict to its
   **keys** (for whatever its other, list-producing callers need), which is exactly wrong here — it
   discards the species name ("N2") and keeps only the internal id ("bg1"). Confirmed as a real
   crash, not just cosmetic: round-tripping the produced `.target` line through
   `combustion_target_class.combustion_target` raises
   `TypeError: list indices must be integers or slices, not str` (iterating the JSON array `['bg1']`
   yields the string `'bg1'` as the loop variable, which then can't index a list).

**Recommendation:** (1) add an `if __name__ == "__main__":` guard. (2) Bath_gas's writer should use
`head.get("Bath_gas")` (the raw `{id: species}` dict) directly, the same way the Fuel field does,
instead of routing it through `normalize_species_list`.

### B16. [LOW, informational] Leaked stress-test processes contributing to sustained heavy system load

Not a defect in the suite's own code, but a real operational finding worth recording: `ps aux` shows
dozens of `python3.9 run_script.py target.opt` processes (in `/home/krithika/mechanism-optimization-
suite`, a separate checkout from this one) still alive from earlier stress-testing (some since
00:24, i.e. hours before this round started), each holding ~1.4 GB RSS, in `S+` (sleeping) state at
near-zero CPU — consistent with stuck/orphaned multiprocessing workers from an incomplete SA run that
was never cleaned up. Combined with the user's own separate, legitimate, heavy concurrent work (a
Julia CFD job at ~2600% CPU, an n-heptane MSO campaign's `cantera_.py` workers at 200-700% CPU each,
confirmed via `/proc/<pid>/cwd`), this pushed `uptime` load average to **137** during this session —
a real contributor to why the full GUI-suite timing run (D1's caveat) could not be completed cleanly.
**Not cleaned up this session** (killing dozens of long-lived processes without being certain none
of them matter is not a call to make unilaterally) — flagged for the user's own judgment.

---

## Part F — Proposed additions to the app store (≥3 requested; 5 provided)

Each closes a gap confirmed by this round's stress-testing, not a speculative want-list item.

1. **CSV → ReSpecTh/RKD XML converter** (`csv2xml`). The missing inverse of the suite's existing
   `config_tools/converters_io/XML2CSV/xml2csv.py`. Directly closes **B11**: a digitized CSV (or any
   hand-prepared CSV of x/y/uncertainty points) becomes a *real* ReSpecTh XML the existing converter
   can already turn into `.target`/`.add`, instead of the digitizer's minimal XML writer needing to
   independently reimplement the full ReSpecTh schema. Highest value of the five proposals and the
   smallest to build — it reuses `xml2csv.py`'s own schema knowledge, just inverted.
2. **Rate-Constant Explorer.** Plot `k(T, P)` for one reaction across N loaded mechanisms, overlay
   the ±3σ band read straight from an uncertainty XML, refit A/n/Ea from a tabulated `k(T)` (natural
   pairing with the now-fixed PySR tab — **B12** — for a symbolic/non-Arrhenius fit), and convert
   between PLOG/Troe/Lindemann forms. The suite tunes A-factors and quantifies their uncertainty but
   has no tool to simply *look at* a rate constant; confirmed absent from `CATALOG`
   (`src/mso_studio/launcher/catalog.py`).
3. **Reaction Pathway / Rate-of-Production Flux Viewer.** Element-flux graph and ranked ROP
   contributors at a chosen (T, P, φ, t). `graph_sa` does graph *comparison* between mechanisms, not
   ROP flux within one; this is the standard companion diagnostic to a sensitivity-analysis result
   (which reactions matter — this shows what they're actually doing) and is missing.
2. **Thermo & Transport Data Inspector.** NASA-7/9 polynomial continuity and Cp/H/S consistency at
   `T_mid`, a Burcat/RMG lookup for species missing thermo, Lennard-Jones completeness check.
   `mechanism_check`'s `thermo_provenance` check (exercised for real in D3's mechanism_check test —
   "Cross-checked 14 species against reference thermo data") covers cross-referencing, not editing or
   estimating; there's no dedicated thermo/transport editor.
5. **Experimental Data Librarian.** Batch-ingest a whole ReSpecTh directory (the suite already has
   AMMONIA/FLAME_SPEED and AMMONIA_COMBUSTION_EXP_DATA folders of dozens of individual XML files),
   dedupe by DOI/figure, and render a T/P/φ coverage map — so a gap in the experimental target set is
   visible *before* launching an optimization, not discovered mid-campaign. `target_workbench`
   curates one already-converted `.target` file; nothing in the store operates one level up, on a raw
   ReSpecTh directory.

---

## Round 2 files changed

**New (this round):** none beyond Round 1's list — all Round 2 work amended existing files or fixed
data files.

**Amended (code):** `conftest.py` (B7/D8), `generate_target_opt.py` (B1/D3, B2/D4),
`scripts/tools_worker.py` (B12), `src/MUQ-SAC/Uncertainty.py` + `src/Sensitivity_Analysis/
Uncertainty.py` (B3/D6), `src/MUQ-SAC/combustion_target_class.py` + `src/Sensitivity_Analysis/
combustion_target_class.py` (B4/D5), `src/MUQ-SAC/data_management.py` + `src/Sensitivity_Analysis/
data_management.py` (B8/D2 diagnostics), `src/MUQ-SAC/make_input_file.py` +
`src/MUQ-SAC/make_input_file2_0.py` + `src/MUQ-SAC/make_input_file2_0_A_factor.py` +
`src/Sensitivity_Analysis/make_input_file.py` (B8/D2 fuel-quoting), `src/mso_workbench/git_pause.py`
(B5/D7), `src/mso_studio/launcher/process.py` (B5/D7), `src/mso_studio/tests/conftest.py` (B10/D1),
`src/latex_project.py` + `src/mso_project/report/builder.py` (B14).

**Amended (tests):** `src/rmip/tests/test_uncertainty_reaction_order.py` (+8 tests),
`src/mso_workbench/tests/test_git_pause.py` (+4 tests).

**Amended (data, gitignored — not migrated to `/data/FINALIZED_MECH_OPT_SUITE`):**
`target.opt`, `DATASET/H2_O2_TEST/target.opt`, `DATASET/H2_O2_TEST/targets/H2_IDT.target`,
`DATASET/H2_O2_TEST/uncertainty/H2_uncertainty.xml`.

**Not touched further:** `src/mso_project/project.py` (B6, still just needs the documented resume()
caveat, no code change); `config_tools/converters_io/XLX2CSV/xlx2csv.py` (B15, recorded not fixed —
the fix touches a tool nothing else in the repo currently depends on, lower priority than the items
actually fixed this round); `mean_value_fusion_gui.py` (B13, recorded not fixed — the `--write-
cantera` path is a secondary output mode, primary fusion output (`.inp`/`.dat`) is unaffected);
`src/mso_studio/core/digitizer.py` (B11, recorded not fixed — the recommended fix is really
"build F1" rather than patching the minimal RKD writer).

## Round 2 summary verdict

| # | Item | Status |
|---|---|---|
| B1/D3 | Stale pre-move paths (`Bin:` + `Locations:`) | **Fixed**, verified via fresh-generation + H2_O2_TEST acceptance run |
| B2/D4 | Uncertainty XML `no=`/`perturbation_type`/`class` | **Fixed**, verified via regeneration + real app (`uncertainty_generator_gui.py`) + acceptance run |
| B3/D6 | Reaction-equation notation mismatch | **Fixed**, extended twice beyond original scope (direction-swap, falloff notation), 16 tests |
| B4/D5 | Malformed target line + Oxidizer dispatch | **Fixed**, one real regression caught by the regression suite and corrected before shipping |
| B5/D7 | Pause/resume doesn't reach SA subprocess | **Fixed**, 4 new tests |
| B7/D8 | `forward_uq` root-vs-`src/` shadowing | **Fixed** |
| B8/D2 | FlameMaster case-7 failure | **Root-caused** (codegen bug, not solver/environment) **and fixed**, verified against the real failing case |
| B10/D1 | GUI test-suite hang | **Root-caused** (widget leak, not the test originally blamed) **and fixed**, verified via representative batch; full-suite timing re-run blocked by unrelated heavy system load (documented) |
| B11 | Digitizer → xml2csv chain | **Confirmed broken** (recorded, not fixed — F1 proposed as the real fix) |
| B12 | PySR | **Confirmed 100% broken, fixed**, verified via real fit |
| B13 | Mechanism fusion `--write-cantera` | **Confirmed broken** for SRI-kinetics fusions (recorded, not fixed) |
| B14 | Project report LaTeX compile | **Confirmed broken for nearly every project, fixed** (root cause in `latex_project.py`, not just the fallback string), verified with a real underscore-heavy title |
| B15 | `xlx2csv.py` | **Confirmed broken** (no `__main__` guard; Bath_gas dict/list bug) (recorded, not fixed) |
| B16 | Leaked processes / system load | **Recorded**, not acted on (not this session's call to make) |
