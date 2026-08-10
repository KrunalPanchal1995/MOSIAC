# Feature gaps: `generate_target_opt.py` (old monolith) vs. the 8 split GUI apps

Compiled 2026-07-17 by a research pass (read-only, no code changes) comparing the retired
12-tab monolith (`generate_target_opt.py`, 6097 lines) against the 8 apps that replaced it
per `MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md`. **This file is a
reading list, not a task list — nothing here should be implemented until the user reads this
and picks specific items.** Ranked candidates are at the bottom.

Methodology: every `_tab_*` handler in the monolith was read in full and cross-referenced
against the corresponding new app (per the split plan's §1.2 mapping table, or by
purpose-matching where the plan doc doesn't name a mapping). `src/gui_common/`'s shared
modules were checked for both completeness of extraction and actual usage by the 8 apps.

Context for why this file exists: the split shrank ~6097 lines to ~2254 lines across 8 apps
(>60%), which is a bigger drop than pure refactoring would explain — this file identifies what
of that drop was a deliberate, documented scope decision (noted inline where applicable) versus
an undocumented capability loss.

---

## Tab-by-tab findings

### Project (`_tab_project`, :1984-2041) → **ORPHANED, no app**
Not assigned to any app in the split plan's table — not a documented decision, just outside
scope. Dropped entirely: project name/output-dir fields, Optimization-type/Algorithm-type
pickers (with `KNOWN_ALGORITHMS` tooltip docs, :667-678), total_reactions/parallel_threads/
targets_count/carbon_number counters, the read-only fuel summary + cross-tab jump button. No new
app can create a `target.opt`'s `project`/`Type`/`Counts` sections at all.

### Files & Paths (`_tab_locations`, :2045-2159) → **ORPHANED, no app**
Dropped entirely: the multi-fuel blend table (species/mole-fraction/global-rxn-coeff/MW/nu_O2
rows, "+ Add fuel", MW-calculator dialog, "Recalc O₂" auto-stoichiometry, :2066-2256, :4746-4875);
all `Locations.*` file fields (mechanism/pre/uncertainty/thermo/trans/targets/addendum) including
the auto-convert-CHEMKIN-to-YAML-on-select hook (`_auto_convert_mechanism`, :2320-2340); all
`Bin.*` executable-path fields (MUQ-SAC bin, solver bin, `.so` paths, SA tool paths); RMIP
database + SMILES-glossary path fields. **Likely-to-be-missed**: this was the only place a fuel
blend (mole fractions, MW, stoichiometric O2) was ever entered — downstream reaction-string
derivation (`derive_global_reaction`) depended on it and now has no GUI feed.

### Mechanisms (`_tab_mechanisms`, :2344-2402) → **ORPHANED, no app**
(RMIP Suite / Fusion apps assume mechanisms are already parsed into `project.db`.) Dropped
entirely: the mechanism-row builder (name/path/format/thermo/trans/glossary/pre, "+ Add
mechanism", per-row and batch CHEMKIN→YAML/.pre convert buttons, :2357-2483); the "one-at-a-time
vs. fuse" workflow radio that downstream Preview logic consumed.

**Update 2026-07-20**: `mechanism_converter_gui.py` now has a "Species glossary CSV" file picker
(row 8, `mechanism_converter_gui.py:344`) wired straight to `rmip_cli.py parse --glossary`
(`src/rmip/cli.py:205`, handler `_cmd_parse` at `:226-241`), so a single mechanism *can* be
converted+parsed into the DB with a glossary attached from the GUI. What's still missing is the
monolith's **batch, multi-mechanism** row-builder workflow (add N mechanism rows, batch-convert
all of them in one pass) — that remains GUI-less; only one mechanism at a time via
`mechanism_converter_gui.py`, or the CLI directly for batch work.

### Experimental Data (`_tab_experimental_data`, :3151-3248) → **ORPHANED, no app**
Dropped entirely: the whole `.target` row-editing grid (dataset_id/type/fuel/oxidizer/bath/T/P/
phi/observed/deviation%/weight, paginated for large datasets); CSV import (`_import_target_csv`,
:3434-3441); the **RKD/ReSpecTh XML dataset importer** bridging to `xml2csv`
(`_import_xml_dataset`, :4957-5102) — a real, working data-ingestion feature (auto-detects skip
reasons, auto-imports the resulting CSV) with no equivalent anywhere; the HTT/LTT
MaxSimulationTime split prompt writing per-dataset `.add` overrides (:3467-3542). No new app can
produce a `.target` file at all.

### Addendum (`_tab_addendum_builder`, :3546-3583) → **ORPHANED, no app**
Dropped entirely: the `.add` YAML row builder (dataset_id/solver/target_type/MaxSimulationTime)
with dynamically-shown per-target-type extra fields (`_rebuild_addendum_extra_fields`, e.g.
`ign_delay_def`, `RCM_type`, `flux_analysis`). No new app can produce a `.add` file.

### Reaction Screening (`_tab_reaction_screening`, :3695-3956) → `brute_force_sa_gui.py` (SA
branch) + `rmip_suite_gui.py` GraphComparisonTab (comparison branch) — **both reduced**
Carried forward: `sens_3_params.py` launch via `PtyTerminal`; RMIP `compare-graph`
classification. Reduced: comparison branch now takes typed comma-separated mechanism IDs instead
of a live mechanism-row checklist (because Mechanisms tab is gone). Dropped entirely: "Quick SA
(Cantera, in-process)" one-click alternative to the terminal SA (`_rs_run_sa_quick`, :3845-3875);
the carbon-number filter UI (`_rs_apply_carbon_filter`, :3926-3946); the "Add selected to
Uncertainty XML" bridge (`_rs_add_selected_to_xml`, :3948-3956) — the whole
screening→carbon-filter→XML pipeline is gone.

### Uncertainty XML (`_tab_xml_builder`, :3960-4030) → `uncertainty_generator_gui.py`
(retrofitted 2026-07-17, partial)
Carried forward: `generate_uncertainty_xml()` was ported "verbatim" per that app's own docstring
— but only as a **late patch** (2026-07-17, this session's Part 43 fix), not part of the
original split; it was missing entirely until then. Dropped entirely: "Fill constant" quick-fill
(T_min/T_max/N-points/σ → linspace array, `_fill_xml_const`, :4061-4083) — rows must now be typed
as full comma-separated arrays by hand; "Load from existing XML…" round-trip import
(`_load_xml`, :4085-4098).

### Optimization (`_tab_optimization`, :2487-2557) → **ORPHANED, no app**
Dropped entirely: PRS/design-matrix fields (Design_of_PRS, Order, Sampling, PRS_type, cutoff,
MRE); objective-function config (`pm_p`, `num_generations`, `softmax_beta`, `pen_alpha`/`pen_K`);
**per-target-type objective weights** (one field per `TARGET_TYPES` entry); adaptive
outlier-retraining settings. None of the `Stats` section is reachable from any of the 8 apps.

### RMIP Analysis (`_tab_rmip_analysis`, :2561-2699) → `rmip_suite_gui.py` (Reduction/GSA/
Active-Param tabs) + `mean_value_fusion_gui.py` (Fusion) — **heavily reduced**
Carried forward: Reduction method/target-species/eps/T/P/phi fields; Fusion tolerances/output
(now via `rmip.stubs.FusionEngine`, a documented deliberate swap from `rmip.analysis.fusion`,
not a silent regression). Reduced: Mechanism Reduction lost the **multi-condition union-reduce
workflow** (`_run_mechanism_reduction_multi_condition`, :3006-3090 — ran the reducer once per
experimental condition and unioned retained species/reactions; new `ReductionTab` is
single-condition only); lost the "Import target species from .target…" dialog (:2701-2806); lost
the **diverse-subset farthest-point-sampling selector with a live 3D T-P-φ scatter confirm/redo
dialog** (`_run_reduction_subset_sampling`/`_show_reduction_subset_confirm`, :2866-3004); Fusion
lost the low-confidence species-translation confirm/edit dialog (`_mm_confirm_dialog`,
:5778-5833). Dropped entirely: 2D graph-image-export settings (:2569-2578); 3D "planetary" graph
viz settings (:2580-2590) — no 3D-viz app exists at all now; persisted SA-run config section
(:2659-2671); "Unified Tree — T-dependent Uncertainty Bands" (:2673-2690) — no equivalent
anywhere; "Export Paths for Final Mechanism" fields (:2692-2697).

### Forward UQ (`_tab_forwarduq`, :3094-3147) → `forward_uq_gui.py` — **close to 1:1, one real gap**
Carried forward well: sample count/method/output-dir/CI fields, correctly upgraded from an
external-terminal-window launch to the shared `PtyTerminal` (matches the split plan's
standardization goal, an actual improvement). Dropped entirely: "📂 Open output folder" button;
the **PNG/JPG thumbnail plot viewer** with double-click-to-open-full-size (`_view_uq_plots`,
:5264-5331, PIL-based) — `forward_uq_gui.py` only shows a small text summary of the results CSV,
no visual result review at all.

### .so Compiler (`_tab_so_compiler`, :4126-4249) → **ORPHANED, no app**
Dropped entirely: the whole tab — per-`.so` source/dest fields, "Compile & install" (runs
`setup.py build_ext --inplace`), the manual-compilation cheat sheet. No GUI path left to rebuild
`parallel_yaml_writer.so`/`shuffle.so`/`yamlwriter.so`.

### Preview (`_tab_preview`, :4253-4270) → **ORPHANED, no app**
Dropped entirely: the target.opt YAML preview pane; and more significantly, **"Build All
Mechanism Outputs"** (`_build_multi_mechanism_outputs`, :5877-6037) — per-mechanism CHEMKIN→YAML
conversion + fuel-species translation (with the low-confidence confirm dialog) + per-mechanism
`.target`/`target.opt` folder tree, or (fuse mode) a full `GraphComparator`→`FusionEngine`→
`CanteraYAMLWriter` drive writing one `target.opt`. The monolith's closest thing to a one-click
"generate everything for N mechanisms" action; no successor exists.

## App-level / menu-bar features (not tied to one tab — also unmapped by the split plan)

Not mentioned anywhere in the plan doc's scope (neither carried-forward nor deliberately
dropped) — reads as an oversight, not a decision:

- **File menu** (:1624-1637): Load/Save/Save-As `target.opt`, Save/Restore/Save-As Checkpoint,
  Quit. No new app can *save* a full `target.opt`; checkpoint save/restore is entirely unwired
  (see `gui_common/autosave.py` below).
- **Keyboard shortcuts** (Ctrl+O/S/Q, :1708-1710) — none of the 8 apps bind any.
- **Toolbar** (Load/Save/Preview buttons, Quick-Save, CPU-cap indicator, :1712-1738) — gone.
- **Insert menu** (:1640-1649): Add target row/addendum entry/uncertainty reaction, Import CSV,
  Import XML dataset — the XML importer loss is the same one noted under Experimental Data above.
- **Tools menu** (:1651-1668): generic "Launch Backend Job in Terminal…" (:5104-5192);
  **"Mechanism Diagnostics…"** (`_open_diagnostics_dialog`, :5636-5722 — wraps `MechDiagnostics`:
  thermo/Cp continuity, collision-limit, reverse-rate sanity checks); "MW / Stoichiometry
  Calculator…" (:4746-4875); "Generate LaTeX target tables…" (:4877-4955); "Read Chemkin Pro CSV
  (ckcsv)…" (:5618-5634). All gone, no equivalents.
- **Notebook menu** (:1670-1678): PDF Q&A Notebook (Gemini-backed), Plot Digitizer, Extract PDF
  Tables, Symbolic Regression/poly-fit panel (:5335-5417) — an entire research-tooling subsystem,
  completely absent.
- **LaTeX menu** (:1680-1691): report-authoring subsystem (new project/compile/append
  section/import figure/add collaborator/append MSO report section, :5421-5616) — entirely
  absent.
- **Help menu**: guided tour (`_start_tour`, :4704-4744) — gone; reasonably fine, it was tied to
  the now-retired 12-tab structure specifically.
- **Hover/tooltip system** (`_hoverable`, `_show_tip`, used pervasively, :1833-1975) — none of
  the 8 new apps have any inline help/tooltip mechanism, only static label text.

## `src/gui_common/` shared-module parity

- **`theme.py`**, **`pty_terminal.py`**, **`settings.py`** — full parity, actively used by all
  (or most) of the 8 apps. No gap.
- **`autosave.py`** (`AutoSaveManager`) — extracted verbatim but **imported by zero of the 8
  apps**. The monolith's auto-save-every-5s + offer-to-restore-on-startup safety net is
  completely unwired everywhere now — a user filling in a long form (uncertainty rows, fusion
  tolerances) has no crash/close protection.
- **`fuel_data.py`** (`FuelNormalizer`) — extracted with a genuine improvement (de-duplicated
  onto `chem_data.py`) but **imported by zero of the 8 apps**.
- **`variable_map.py`** (`VariableNameMapper`) — extracted verbatim but **imported by zero of
  the 8 apps** (was low-value even in the monolith).
- **`target_types.py`** (`TARGET_TYPES`/`TARGET_TYPE_FIELDS`/`TARGET_ROW_COLUMNS`) — extracted
  verbatim but **imported by zero of the 8 apps**, directly reflecting that no new app builds
  `.target`/`.add` rows at all.

---

## Ranked candidates for future implementation (read, don't act — user picks)

1. **No GUI path to build a `.target`/`.add` file from scratch** (Experimental Data :3151-3542,
   Addendum :3546-3691, incl. CSV/XML import). Blocks onboarding any brand-new dataset via GUI —
   every existing app assumes these files already exist. Also unlocks the orphaned
   `target_types.py` module.

   **Update 2026-07-20 (Phase-3 follow-on Part A) — DONE, scoped to JSR/PFR only.** New
   `rmip build-target` CLI subcommand (`src/rmip/cli.py::_add_build_target_cmd`/
   `_cmd_build_target`) wraps `MuqsacBridge.build_target_files()` directly — writes
   `rmip.target`/`rmip.add`/`target.opt` for a single JSR or PFR condition. New GUI tab
   `TargetBuilderTab` in `rmip_suite_gui.py` gives this a form front-end: target-type
   dropdown (JSR/PFR only, filtered from `target_types.TARGET_TYPES`), dynamic
   per-type extra fields (`gui_common.target_types.TARGET_TYPE_FIELDS`, mapped onto the
   real `build_target_files()` parameters they feed), and a repeatable fuel-blend row
   editor (species + mole fraction, Treeview idiom copied from
   `uncertainty_generator_gui.py`'s reaction-row editor). Deliberately NOT extended
   beyond JSR/PFR — `build_target_files()` itself only supports those two, and that
   restriction is out of scope per this phase's brief. Other target types (Tig/Fls/
   Flf/Flf_a/RCM/Flw) still have no builder GUI anywhere.

2. **No GUI path to build `Locations`/`Bin`/fuel-blend config** (Files & Paths, :2045-2340) — no
   app can point a fresh project at a mechanism/thermo/executables or define a fuel blend with
   MW/stoichiometry. Unlocks the orphaned `fuel_data.py` module.
3. **Autosave/checkpoint safety net unwired** (`gui_common/autosave.py` exists, tested, unused)
   — cheapest fix in this list since the module is already built; just needs wiring into the
   longer-running apps (uncertainty_generator_gui.py, mean_value_fusion_gui.py first).

   **Update 2026-07-20 (Phase-3 follow-on Part B) — DONE for 4 places, deliberately not
   more.** `AutoSaveManager` is now wired into exactly: (1) `uncertainty_generator_gui.py`
   — `mark_dirty()` called from the EXISTING `_add_gen_row`/`_remove_gen_row` row
   callbacks, own checkpoint `.gui_settings/uncertainty_generator_checkpoint.json`; (2)
   `mean_value_fusion_gui.py` — no repeatable row editor exists there, so the persisted
   form fields (`mech_ids`, tolerances, output name/dir, priority order) are traced
   directly via `trace_add("write", ...)`, own checkpoint
   `.gui_settings/mean_value_fusion_checkpoint.json`; (3)+(4) `rmip_suite_gui.py`'s new
   `TargetBuilderTab` fuel-blend row editor and `ReductionTab`'s new multi-condition row
   editor (see #1 and #5 below) — these share ONE `AutoSaveManager`/checkpoint file at
   the `RMIPSuiteApp` level (`.gui_settings/rmip_suite_checkpoint.json`), since they're
   two row editors inside one app, not two apps. Every other GUI app (brute_force_sa,
   forward_uq, nominal_sim, mso_compare, mechanism_converter, launcher) remains
   deliberately unwired, per this phase's explicit scope decision — their state is
   already covered by existing save/load-last-path settings persistence.
4. **XML/RKD-ReSpecTh dataset importer gone** (`_import_xml_dataset`, :4957-5102) — a real,
   working bridge to `xml2csv`; currently the only way to bulk-import experimental datasets.

   **Update 2026-07-20 (Phase-3 follow-on Part C) — GUI front-end DONE; the core/CLI
   side was already there.** `rmip import-respecth` (`src/rmip/cli.py`, wrapping
   `rmip.io.respecth_reader`) already existed and was already tested — no core/CLI
   change was needed. New GUI tab `ReSpecThImportTab` in `rmip_suite_gui.py` gives it a
   form front-end: XML file/directory picker, `--fuel`, `--solver` dropdown
   (cantera/CHEMKIN_PRO/FlameMaster), `--out-dir` picker, `--dataset-prefix`, and a
   `--no-db` checkbox.
5. **Multi-condition union-reduce + diverse-subset 3D-confirm dialog gone**
   (`_run_mechanism_reduction_multi_condition` :3006-3090, `_run_reduction_subset_sampling`
   :2866-3004) — `ReductionTab` today is single-condition only, a real capability regression for
   anyone reducing against real experimental coverage.

   **Update 2026-07-20 (Phase-3 follow-on Part D) — the union-reduce ORCHESTRATION is
   DONE (core+CLI+GUI); the diverse-subset 3D-confirm dialog is NOT part of this and
   remains a distinct, still-open gap.** New `src/rmip/reduction/multi_condition.py::
   reduce_multi_condition()` runs the same DRG/DRGEP/PFA/DRGPSA/DRGSA reducer once per
   given `SimCondition`, then unions the retained species/reactions at each matching ε
   threshold (removed = intersection of the per-condition removed sets, since all
   conditions share the same mechanism-wide universe); persists exactly ONE
   `reduction_runs` row for the whole union via the reducer's own `_insert_run()`, plus a
   new `reduction_multi_condition_runs` table (`src/rmip/database/migrations.py::
   run_multi_condition_migrations`) linking that run back to the JSON-serialised
   condition list. CLI: `rmip reduce` gained a repeatable `--condition T_K,P_atm,phi,fuel`
   flag (`_add_reduce_cmd`/`_cmd_reduce` in `src/rmip/cli.py`) — when given, dispatches to
   `reduce_multi_condition()` instead of the reducer's own `.reduce()`; the pre-existing
   no-`--condition` single-condition code path is untouched (same statements, only
   re-indented into an `else:` branch — verified via CLI tests asserting its output shape
   is unchanged). GUI: `rmip_suite_gui.py`'s `ReductionTab` gained a repeatable condition
   Treeview (T_K/P_atm/phi/fuel, same add/remove-row idiom as `TargetBuilderTab`'s fuel
   blend) plus the `--mech-path` file picker the tab was missing entirely (needed for
   real Cantera rate evaluation — without it, every condition degrades to the same
   unweighted/flux_score fallback and a union becomes a no-op). **Explicitly NOT done:**
   the monolith's separate 3D diverse-subset farthest-point-sampling confirm/redo dialog
   (`_run_reduction_subset_sampling`/`_show_reduction_subset_confirm`, :2866-3004) — that
   picks WHICH conditions to run against in the first place and is unrelated math; it
   remains a distinct, still-open gap.
6. **Mechanism Diagnostics panel gone** (`_open_diagnostics_dialog`, :5636-5722) — a working
   correctness tool (thermo continuity, collision limits, reverse-rate sanity) with no home now.
7. **"Build All Mechanism Outputs" batch fan-out gone** (`_build_multi_mechanism_outputs`,
   :5877-6037) — the monolith's closest thing to "generate everything for N mechanisms," no
   successor.
8. **Compile tab gone** (`_tab_so_compiler`, :4126-4249) — low usage frequency but a real
   capability cliff when a `.so` needs rebuilding.
9. **Uncertainty XML "Fill constant" quick-fill + "Load from existing XML" gone** (:4061-4098) —
   cheap to restore, code still exists in the monolith to copy from.
10. **Forward UQ's thumbnail plot viewer gone** (`_view_uq_plots`, :5264-5331) — nice-to-have,
    forward_uq_gui.py currently only dumps CSV text.

All line numbers above refer to `generate_target_opt.py` as of 2026-07-17. Re-verify line numbers
before implementing anything — they will drift if the monolith file is touched again.
