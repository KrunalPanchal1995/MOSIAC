# Project History Archive

Consolidated 2026-07-22 from `MarkDownFiles/HISTORY/` (45 files: `INDEX.md` +
44 numbered parts) into this single file — pure format change (separate files ->
inline sections), no content was summarized away. Original per-part sourcing
notes are preserved verbatim within each section below.

---

# Project history index

Generated 2026-07-17 by reading every .md/.txt file in this repo plus the session's
memory files, and reconstructing a chronological, numbered breakdown of every distinct
phase of work. One file per part, named `partN_<status>.md`. See `../../BUG.md` for
resolved bugs and `../../bug.md` for unresolved bugs/known limitations (kept separate
from this timeline per the user's request).

| Part | Status | Title |
|---|---|---|
| 1 | DONE | [Visualizer bug-fix pass (2026-06-27 to 2026-06-29)](part1_done.md) |
| 2 | DONE | [Phase 5A: SA/Flux edge highlighting (2026-06-29)](part2_done.md) |
| 3 | PARTIAL | [Phase 5D: Species SMILES disambiguation, Tier 1 (2026-06-29)](part3_partial.md) |
| 4 | DONE | [Phase 5C: Carbon-ring 2D layout (2026-06-29)](part4_done.md) |
| 5 | DONE | [Phase 5C: 3D stacked-disc layout + Methyl-Butanoate case load (2026-07-03)](part5_done.md) |
| 6 | DONE | [Phase 5B: Mechanism reduction DRG/DRGEP/PFA (2026-07-04)](part6_done.md) |
| 7 | DONE | [Phase 5B extended: DRGPSA/DRGSA + coefficient/trim Dash visualizers (2026-07-04)](part7_done.md) |
| 8 | PENDING | [Future.md restart-logic bug audit (2026-07-05)](part8_pending.md) |
| 9 | DONE | [GUI Overhaul Batch 1, GUI-1 "Modernization" (2026-07-05)](part9_done.md) |
| 10 | DONE | [GUI-2: multi-fuel blend UI + combustion_target_class chem_data integration (2026-07-05)](part10_done.md) |
| 11 | DONE | [GUI-3: xml2csv.py refactor + LaTeX target tables (2026-07-05)](part11_done.md) |
| 12 | PARTIAL | [GUI-4: backend fixes -- progress-file path, mso_compare bugs, thread cap, pipeline parallelism (2026-07-05)](part12_partial.md) |
| 13 | DONE | [GUI-5: FlameMaster subprocess fix + mech_diagnostics.py (2026-07-05)](part13_done.md) |
| 14 | DONE | [GUI-6: Gemini PDF notebook, plot digitizer, LaTeX project manager, Forward UQ panel (2026-07-05)](part14_done.md) |
| 15 | PARTIAL | [GUI-7: remaining error.md items R1-R7, R9, R10 (2026-07-05)](part15_partial.md) |
| 16 | DONE | [Phase 6: Future.md Part 2 features 1-7 implemented (2026-07-05)](part16_done.md) |
| 17 | DONE | [Deep review #1, static-only (2026-07-11)](part17_done.md) |
| 18 | PARTIAL | [Deep review #1 implementation pass (2026-07-11)](part18_partial.md) |
| 19 | PARTIAL | [ResponseSurface.py bugfix ported + quick-win #7 residual (2026-07-11)](part19_partial.md) |
| 20 | DONE | [git init + unified_tree.py KEEP_ANCHOR blocker fix (2026-07-11)](part20_done.md) |
| 21 | DONE | [Zero-RK integration decision + Phase 0 build & validate (2026-07-11)](part21_done.md) |
| 22 | DONE | [Zero-RK Phase 1: zerork_bridge.py (2026-07-12)](part22_done.md) |
| 23 | DONE | [Zero-RK Phase 2: solver="zerork" wired into make_input_file.py for Tig, JSR (2026-07-12)](part23_done.md) |
| 24 | DONE | [src/MUQ-SAC reconciliation with ~/mechanism-optimization-suite (2026-07-12)](part24_done.md) |
| 25 | DONE | [Zero-RK GSA Phase 3: zerork_gsa.py + SALib environment incident (2026-07-12)](part25_done.md) |
| 26 | DONE | [stubs.FusionEngine (M7) + DoEFramework.run_screening()/prepare_mso_input() (2026-07-12)](part26_done.md) |
| 27 | DONE | [GUI-separation + broader-improvement planning exercise (2026-07-12)](part27_done.md) |
| 28 | DONE | [GUI split Phase 1: src/gui_common/ package + brute_force_sa_gui.py pilot (2026-07-12)](part28_done.md) |
| 29 | DONE | [GUI split Phase 2: forward_uq_gui.py + nominal_sim_gui.py (2026-07-12)](part29_done.md) |
| 30 | DONE | [GUI split Phase 3: mso_compare_gui.py + mean_value_fusion_gui.py (2026-07-12)](part30_done.md) |
| 31 | DONE | [GUI split Phase 4: rmip_suite_gui.py umbrella app (2026-07-12)](part31_done.md) |
| 32 | DONE | [GUI split Phase 6: launcher_gui.py (2026-07-12)](part32_done.md) |
| 33 | DONE | [GUI split Phase 5: uncertainty_generator_gui.py, collapse-only (2026-07-12)](part33_done.md) |
| 34 | DONE | [Zero-RK GSA Phase 4: PRS/direct-Sobol cross-check (2026-07-12)](part34_done.md) |
| 35 | DONE | [Deep review #2 + first-ever dynamic stress test (2026-07-13/14)](part35_done.md) |
| 36 | DONE | [Fusion-engine stress test: Keromnes 2013 / Li 2015 / Davis 2005 (2026-07-14)](part36_done.md) |
| 37 | DONE | [Review-fix Phase 0: dead-simple crashes (2026-07-14, uncommitted)](part37_done.md) |
| 38 | DONE | [Review-fix Phase 1: scientific-integrity core (2026-07-14, uncommitted)](part38_done.md) |
| 39 | PARTIAL | [Review-fix Phase 2: analysis/optimization majors (2026-07-14, uncommitted)](part39_partial.md) |
| 40 | PENDING | [Review-fix Phases 3-5: pipeline robustness, GUI hardening, minors batch](part40_pending.md) |
| 41 | DONE | [Zero-RK: RCM via variable_volume.x integrated + verified end-to-end (2026-07-17)](part41_done.md) |
| 42 | PARTIAL | [Zero-RK: flame speed (Fls) + counterflow/extinction -- scoped, NOT implemented (2026-07-17)](part42_partial.md) |
| 43 | DONE | [Task B: dummy-mechanism GUI fusion stress test -- 3 real bugs found and fixed (2026-07-17)](part43_done.md) |
| 44 | PENDING | [Task B remainder: sweep the other 5 launcher GUIs + literal-GUI verification + canonicalize.py fix](part44_pending.md) |


---

## part1_done.md

# Part 1 [DONE] -- Visualizer bug-fix pass (2026-06-27 to 2026-06-29)

Six specific bugs fixed in the RMIP network visualizer: ghost-node ID collisions,
position-identity key mismatches, formula-string mismatches causing spurious duplicate
nodes, per-panel layout-dropdown desync, unlabeled ghost reaction nodes, and inconsistent
R-IDs for the same reaction across mechanisms.

Status evidence: progress table shows a fix for every row, no open items.

**Source:** MarkDownFiles/progress.md

---

## part2_done.md

# Part 2 [DONE] -- Phase 5A: SA/Flux edge highlighting (2026-06-29)

`CanteraSensitivityRunner.run_idt()` (native Cantera SA) plus 4-band CSS
edge-coloring in the network visualizer; new `sa-run` CLI subcommand.

Status evidence: "Phase 5A -- SA/Flux Edge Highlighting COMPLETE".

**Source:** MarkDownFiles/progress.md, PLAN.md

---

## part3_partial.md

# Part 3 [PARTIAL] -- Phase 5D: Species SMILES disambiguation, Tier 1 (2026-06-29)

`species_variants.csv` glossary override mechanism so e.g. `OHEX` shares `OH`'s
InChIKey.

Status: Tier 1 (manual variant overrides) is DONE. Tier 2 (auto InChIKey-collision
detection) and Tier 3 (RDKit InChI-layer pruning) are explicitly "Deferred, not yet
requested" -- still pending, no later document claims otherwise.

**Source:** MarkDownFiles/progress.md, PLAN.md

---

## part4_done.md

# Part 4 [DONE] -- Phase 5C: Carbon-ring 2D layout (2026-06-29)

`_carbon_ring_positions()` concentric-ring layout by carbon number for the
network visualizer.

**Source:** MarkDownFiles/progress.md

---

## part5_done.md

# Part 5 [DONE] -- Phase 5C: 3D stacked-disc layout + Methyl-Butanoate case load (2026-07-03)

3D Plotly visualizer (`NetworkVisualizer3D`), plus loading MB/MB2D mechanisms
(ids 6/7, 608-623 species). Found and fixed a `scipy.sparse` pre-import bug that
silently crashed `spring_layout` on >500-node graphs.

**Source:** MarkDownFiles/progress.md

---

## part6_done.md

# Part 6 [DONE] -- Phase 5B: Mechanism reduction DRG/DRGEP/PFA (2026-07-04)

Core reducers with BFS/Dijkstra propagation and a new CLI `reduce` subcommand.

**Source:** MarkDownFiles/progress.md, PLAN.md

---

## part7_done.md

# Part 7 [DONE] -- Phase 5B extended: DRGPSA/DRGSA + coefficient/trim Dash visualizers (2026-07-04)

SA-weighted reduction variants plus interactive Dash apps for r_AB heatmaps and
BFS-trim animation.

**Source:** MarkDownFiles/progress.md

---

## part8_pending.md

# Part 8 [PENDING] -- Future.md restart-logic bug audit (2026-07-05)

Documents 6 restart/checkpoint bugs in `simulation_manager2_0.py`/
`partial_PRS_system.py`: sentinel-path fragility, CWD-corruption-on-exception, wrong
design-matrix iterated on restart, partial-YAML-chunk not detected, `locations` file
duplicate-appending, progress-file wrong-directory fallback.

Status: NOT explicitly confirmed fixed anywhere in any later document -- no document
says "Future.md Bug 1/2/3/4/5/6 fixed". Two bugs (sentinel path, progress-file path)
look partially touched by later, differently-scoped fixes (see Part 12) but no document
draws that connection explicitly. Treat all 6 as still open until re-verified.
The 20-feature roadmap in the same document was largely implemented separately (Part 16).

**Source:** MarkDownFiles/Future.md

---

## part9_done.md

# Part 9 [DONE] -- GUI Overhaul Batch 1, GUI-1 "Modernization" (2026-07-05)

Driven by error.md. New `chem_data.py` shared module (atomic weights, `compute_mw`,
`compute_nu_o2`, `thread_cap`); PALETTE/FONTS/theme system; click-based tooltip popover
replacing an aggressive, un-dismissable hover tooltip; menu bar; checkpoint save/restore.

**Source:** MarkDownFiles/progress.md, PLAN.md

---

## part10_done.md

# Part 10 [DONE] -- GUI-2: multi-fuel blend UI + combustion_target_class chem_data integration (2026-07-05)

Both copies (MUQ-SAC and Sensitivity_Analysis) updated to source MW/stoichiometry
tables from `chem_data.py` instead of hardcoded literals; a KeyError bug for unlisted
fuels fixed.

**Source:** MarkDownFiles/progress.md

---

## part11_done.md

# Part 11 [DONE] -- GUI-3: xml2csv.py refactor + LaTeX target tables (2026-07-05)

Full rewrite of a 966-line flat script (functionized, CWD-independent, fixed an
operator-precedence bug, fixed silent-crash AssertionErrors, fixed a molwt KeyError).
New `src/target_tables.py` for LaTeX booktabs tables of target data.

251/956 files parsed in smoke test; the other 705 are a genuinely unsupported target
type, logged as warnings, not silently dropped.

**Source:** MarkDownFiles/progress.md

---

## part12_partial.md

# Part 12 [PARTIAL] -- GUI-4: backend fixes -- progress-file path, mso_compare bugs, thread cap, pipeline parallelism (2026-07-05)

Fixed the progress-file-lands-in-wrong-directory bug (both simulation_manager2_0.py
copies), an mso_compare import-name bug and a Fls double-indexing TypeError, enforced
thread_cap() everywhere, added ThreadPoolExecutor parallelism to mso_compare/pipeline.py,
and a GUI "launch backend job in external terminal" feature.

Status: DONE at the time, but the parallelism approach was LATER FOUND INSUFFICIENT --
the 2026-07-13/14 review found mso_compare/pipeline.py's ThreadPoolExecutor + per-worker
os.chdir() causes CWD races (review.md M24, still unresolved -- see bug.md).

**Source:** MarkDownFiles/progress.md

---

## part13_done.md

# Part 13 [DONE] -- GUI-5: FlameMaster subprocess fix + mech_diagnostics.py (2026-07-05)

os.mkdir -> os.makedirs(exist_ok=True); unbounded retry loop replaced with a bounded
one with atomic file rewrite; new Cantera-based mech_diagnostics.py (NASA-7 continuity,
collision-limit, reverse-rate checks) responding directly to a forum email in error.md
about unphysical reverse rates breaking 1D-flame convergence.

**Source:** MarkDownFiles/progress.md

---

## part14_done.md

# Part 14 [DONE] -- GUI-6: Gemini PDF notebook, plot digitizer, LaTeX project manager, Forward UQ panel (2026-07-05)

New src/notebook_gemini/ package (PDF Q&A via google-genai, plot digitizer with axis
calibration and point-picking), src/latex_project.py (idempotent local-git LaTeX section
management), Forward UQ GUI wiring + 19 smoke tests.

**Source:** MarkDownFiles/progress.md

---

## part15_partial.md

# Part 15 [PARTIAL] -- GUI-7: remaining error.md items R1-R7, R9, R10 (2026-07-05)

PySR/polynomial-fit panel, PDF table extraction, RKD XML+YAML export from the
digitizer, uncertainty-bar picking mode, MSO-report-to-LaTeX append, Forward-UQ inline
plot viewer, PyChemkin ckcsv reader, and .done-sentinel restart robustness.

Status: DONE for R1-R7/R9/R10. R8 (Zero-RK integration) explicitly "Deferred
indefinitely per user decision. No files touched" at this point -- later un-deferred,
see Part 21.

**Source:** MarkDownFiles/progress.md, PLAN.md

---

## part16_done.md

# Part 16 [DONE] -- Phase 6: Future.md Part 2 features 1-7 implemented (2026-07-05)

Reverse Rate Unphysicality Scanner, Mechanism Quality Score + Diff Engine (fixed a
real ComparisonEngine._compare_species() KeyError bug along the way), PLOG Rate Surface
Visualizer, NTC Detection with an HTT/LTT split extension, and Flux/JSR/PFR analysis
wired through the MUQ-SAC pipeline across all 3 solvers via a new
src/rmip/simulation/muqsac_bridge.py. Two real unit-conversion bugs (Pa-vs-atm
double-conversion, PyChemkin's bar-not-Pa convention) caught and fixed.

355/355 tests passing. Known gap flagged: CHEMKIN_PRO/FlameMaster reactor-model
executable names need verification against a real licensed install -- only the cantera
solver path was run end-to-end (still unverified, see bug.md).

**Source:** MarkDownFiles/progress.md

---

## part17_done.md

# Part 17 [DONE] -- Deep review #1, static-only (2026-07-11)

First full codebase review: 15 quick wins, 7 structural improvements, and a proposed
5-phase PySide6 GUI-migration plan (Tkinter -> PySide6, never implemented, see bug.md).

**Source:** .claude-review/report-2026-07-11.md, progress-2026-07-11.md

---

## part18_partial.md

# Part 18 [PARTIAL] -- Deep review #1 implementation pass (2026-07-11)

9 of 15 quick wins implemented; 6 more found already-fixed-on-disk; a newly-found
blocker (duplicate _on_notebook_tab_changed method silently shadowing the reduction-tab
auto-populate handler) found and fixed.

Quick win #13 (delete bkp/backup dirs, ~11,554 LOC) explicitly deferred -- "this repo is
not under git ... no cheap rollback." (Repo now IS under git as of Part 20 -- this
cleanup item was never revisited afterward and remains open, see bug.md.)

**Source:** .claude-review/report-2026-07-11.md, MarkDownFiles/PLAN.md

---

## part19_partial.md

# Part 19 [PARTIAL] -- ResponseSurface.py bugfix ported + quick-win #7 residual (2026-07-11)

Ported the ii/jj/kk/ll/mm range-based loop fix from MUQ-SAC/ResponseSurface.py into
the sibling Sensitivity_Analysis/ResponseSurface.py (fixing a .index()-based
duplicate-monomial bug reachable from the GUI's "Run SA" button). Also fixed a cosmetic
A_units-label inconsistency in the CHEMKIN parser.

Only the fit-half (MatPolyFitTransform) was ported -- the evaluate()-half of
Sensitivity_Analysis/ResponseSurface.py still had the original bug as of the 2026-07-14
review (review.md M23, still unresolved, see bug.md).

**Source:** MarkDownFiles/PLAN.md, progress.md

---

## part20_done.md

# Part 20 [DONE] -- git init + unified_tree.py KEEP_ANCHOR blocker fix (2026-07-11)

Repo placed under version control for the first time (root commit 6379ace).
Separately, fixed a deeper bug: anchor_mech_id was unrecoverable across the real
two-process unify-plan/unify-build CLI workflow because decisions.csv never carried it
-- fixed via a <manifest>.meta.json sidecar.

Re-confirmed fixed in the 2026-07-13 review (findings-d-analysis-sim.md: "FIXED, verify
only").

**Source:** MarkDownFiles/progress.md, .claude-review/report-2026-07-11.md

---

## part21_done.md

# Part 21 [DONE] -- Zero-RK integration decision + Phase 0 build & validate (2026-07-11)

Decision confirmed with KP: wrap Zero-RK via subprocess, don't reimplement its
solvers. Full 6-phase plan written (ZERORK_GSA_PLAN.md). Zero-RK built at
/home/krithika/zero-rk/build2/inst_dir (3 real build-config bugs found and fixed).
Validated: 145/145 ctest, 0.00004% agreement vs Cantera on GRI-3.0-wetCO IDT.

**Source:** MarkDownFiles/ZERORK_GSA_PLAN.md, progress.md

---

## part22_done.md

# Part 22 [DONE] -- Zero-RK Phase 1: zerork_bridge.py (2026-07-12)

Getting one successful Zero-RK IDT/JSR run required finding and fixing 6 real,
previously-undiscovered CHEMKIN parser/writer bugs (none Zero-RK-specific): wrong NASA-7
field widths, an untagged Lindemann falloff reaction, kinetics-data key mismatches, an
undetected KELVINS header modifier, species.formula never populated at all (root cause
of a universal NaN-at-t=0 Zero-RK failure), and an element-symbol case mismatch.

IDT/JSR verified to 0.05% vs. the Phase-0 reference. Deliberately did NOT re-parse the
live outputs/project.db mechanisms 1-4 (left stale; ids 8-11 are current).

**Source:** RESUME.md, ZERORK_GSA_PLAN.md, progress.md

---

## part23_done.md

# Part 23 [DONE] -- Zero-RK Phase 2: solver="zerork" wired into make_input_file.py for Tig, JSR (2026-07-12)

New solver branch in create_input_file() for Tig then JSR targets. A correctness
bug (Zero-RK's tau.out falling into a generic else: branch tuned for FlameMaster) caught
and fixed in data_management.py. Verified end-to-end against real binaries (8065.80 us
vs 8061.9 us reference IDT; JSR converged=true, correct exit composition).

PFR and flame targets are a PERMANENT gap -- Zero-RK has no such reactor at all, not
deferred work (re-confirmed again 2026-07-17, see Part 42).

**Source:** RESUME.md, ZERORK_GSA_PLAN.md

---

## part24_done.md

# Part 24 [DONE] -- src/MUQ-SAC reconciliation with ~/mechanism-optimization-suite (2026-07-12)

Per KP's explicit "rest you can ignore" instruction, scoped only to src/MUQ-SAC/.
Pulled in AdaptiveResampler.py and run_script.py changes wholesale, re-applied a
previously-dropped bugfix ("Bug 4" directory-completeness check) on top.

**Source:** RESUME.md

---

## part25_done.md

# Part 25 [DONE] -- Zero-RK GSA Phase 3: zerork_gsa.py + SALib environment incident (2026-07-12)

Real Sobol/Morris sensitivity indices via SALib sampling + Zero-RK's
perturbAFactorGSA_mpi.x MPI batch execution. Real environment-breaking incident: pip
install SALib upgraded numpy 1.24.4->2.0.2 and broke scikit-learn's import outright --
caught, rolled back, fixed by isolating SALib in a dedicated venv
(/home/krithika/.venvs/salib_gsa), talked to only via subprocess+JSON.

Deliberately not wired into stubs.DoEFramework.run_screening() at this point (needed
FusionEngine first, see Part 26).

**Source:** RESUME.md, ZERORK_GSA_PLAN.md

---

## part26_done.md

# Part 26 [DONE] -- stubs.FusionEngine (M7) + DoEFramework.run_screening()/prepare_mso_input() (2026-07-12)

FusionEngine is a thin adapter over the already-tested rmip.analysis.fusion.FusionEngine,
adding CHEMKIN/.yaml writing and validate_element_balance(). Found and fixed a real
pre-existing ChemkinWriter bug: write() unconditionally appended a duplicate "END\n"
after _write_reactions()'s own terminator -- every CHEMKIN file this writer ever produced
had a double terminator, rejected by ck2yaml.

Still-unimplemented stubs.py modules, explicitly out of scope: PathwayCompleter (needs
RMG-Py), UQFusion (needs a MUQ-SAC covariance adapter, blocked on a missing CLAUDE.md
section that doesn't exist in this repo), AIRecommender, ChangeLog, ReportEngine.

**Source:** RESUME.md, PLAN.md

---

## part27_done.md

# Part 27 [DONE] -- GUI-separation + broader-improvement planning exercise (2026-07-12)

Full plan written: split the 6,080-line, 12-tab generate_target_opt.py monolith into
7 standalone GUI apps sharing a new src/gui_common/ package, plus 8 ranked
broader-improvement findings (#1: the glossary-matching gap silently blocks
FusionEngine/GraphComparator/unify-* on every real mechanism, since every species had
NULL inchi_key at the time).

**Source:** MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md

---

## part28_done.md

# Part 28 [DONE] -- GUI split Phase 1: src/gui_common/ package + brute_force_sa_gui.py pilot (2026-07-12)

Extracted theme, PtyTerminal, autosave, settings, fuel_data, variable_map,
target_types into a shared package. Verified against a real display and a real
target.opt.

**Source:** RESUME.md

---

## part29_done.md

# Part 29 [DONE] -- GUI split Phase 2: forward_uq_gui.py + nominal_sim_gui.py (2026-07-12)

Both wrap existing CLI backends, using the shared PtyTerminal.

**Source:** RESUME.md

---

## part30_done.md

# Part 30 [DONE] -- GUI split Phase 3: mso_compare_gui.py + mean_value_fusion_gui.py (2026-07-12)

The latter is the one app that calls FusionEngine in-process via a background
thread; verified end-to-end with a real fusion run producing VERBATIM=1 COPY=1 FUSE=1.

**Source:** RESUME.md

---

## part31_done.md

# Part 31 [DONE] -- GUI split Phase 4: rmip_suite_gui.py umbrella app (2026-07-12)

One window, 4 internal tabs (Graph Comparison, Mechanism Reduction, GSA, Active
Parameter Selection). A second, previously-undiscovered io-shadowing package (src/io/)
found while wiring the 4th tab -- empirically confirmed safe for this one script. A real
end-to-end DRG reduction was run through the GUI.

**Source:** RESUME.md

---

## part32_done.md

# Part 32 [DONE] -- GUI split Phase 6: launcher_gui.py (2026-07-12)

Built ahead of Phase 5 since Phase 5 was blocked on a KP decision.

**Source:** RESUME.md

---

## part33_done.md

# Part 33 [DONE] -- GUI split Phase 5: uncertainty_generator_gui.py, collapse-only (2026-07-12)

KP confirmed the exact symmetric-bound formula first. Found and fixed a real bug:
generate_target_opt.py's generate_uncertainty_xml() never wrote the no/perturbation_type
attributes Uncertainty.py's reaction.__init__ requires -- every uncertainty XML that GUI
tab ever produced would crash Uncertainty.py on load.

"All 7 apps of the original GUI-separation plan are now built." Note: this app only
COLLAPSED an existing uncertainty XML at this point -- XML GENERATION was not wired into
any of the 7 apps until 2026-07-17, see Part 43.

**Source:** RESUME.md

---

## part34_done.md

# Part 34 [DONE] -- Zero-RK GSA Phase 4: PRS/direct-Sobol cross-check (2026-07-12)

New gsa_prs_crosscheck.py, scoped as validation-only (explicitly not wiring a
prefilter into run_script.py/DesignMatrix.py). Verdict: AGREE at real settings. Found and
fixed a real off-by-one bug in ZerorkGSARunner._parse_gsa_output: perturbAFactorGSA_mpi.x
always writes an unperturbed baseline as task_id=0 before the sample loop; the parser had
silently corrupted every Sobol/Morris index this module had ever computed.

**Source:** RESUME.md, ZERORK_GSA_PLAN.md

---

## part35_done.md

# Part 35 [DONE] -- Deep review #2 + first-ever dynamic stress test (2026-07-13/14)

Fresh review (5 parallel static reviewers + genuine dynamic execution: CLI pipelines
run with real+adversarial inputs, all 9 GUIs button-mashed on a live display). Produced
review.md (B1-B15 blockers, M1-M29 majors, plus a MINOR list) and review_plan.md (phased
fix plan). Mid-review, delivered a new standalone app mechanism_converter_gui.py
(CHEMKIN -> YAML/.pre/DB with Fortran-exponent+CRLF auto-fix).

"NO fixes applied yet" as of the review's own completion -- fixing happened in Parts
37-40.

**Source:** .claude-review/progress.md, report.md, findings-{a..e}-*.md, MarkDownFiles/review.md

---

## part36_done.md

# Part 36 [DONE] -- Fusion-engine stress test: Keromnes 2013 / Li 2015 / Davis 2005 (2026-07-14)

Debugged why GUI mechanism fusion "doesn't work": the repo's only glossary
(species_smiles.csv) had zero entries for CO/CO2/HCO/CH4/C2H6 -- every wet-CO/syngas
mechanism failed to cross-match. Fixed by appending 5 rows to species_smiles.csv.
Completed M9 (canonical-key collisions) and M11 (falloff/PLOG averaging discarding
kinetics data), fixed a bare-third-body writer bug, a specific-collider identity-loss
bug, added forced DUPLICATE re-marking on export.

One explicitly documented, NOT-fixed limitation: both fused .yaml outputs fail
ct.Solution() because Keromnes writes H2 dissociation as a generic-M third-body while
Li/Davis write it as an explicit self-third-body -- Cantera's kinetics engine treats
these as equivalent, this suite's canonicalizer does not (core/canonicalize.py fix
scoped but explicitly not attempted -- "unclear blast radius"). Verifying the fused
CHEMKIN .inp files actually run in Zero-RK was also flagged as not done.

**Source:** outputs/fusion_keromnes_li_davis/stress_test_punchlist.md, pending_night.md

---

## part37_done.md

# Part 37 [DONE] -- Review-fix Phase 0: dead-simple crashes (2026-07-14, uncommitted)

All 7 items complete: B5, B8, B9, B11, B12, B14, M18a (see BUG.md for details).

**Source:** pending_night.md

---

## part38_done.md

# Part 38 [DONE] -- Review-fix Phase 1: scientific-integrity core (2026-07-14, uncommitted)

All Blockers+Majors in this phase complete: B1/B2 (Cantera-3 reader rewrite +
kmol->mol), B3, B4, B6, B7, B15, M1-M8 (see BUG.md for details).

**Source:** pending_night.md

---

## part39_partial.md

# Part 39 [PARTIAL] -- Review-fix Phase 2: analysis/optimization majors (2026-07-14, uncommitted)

M9 and M11 done (completed as part of Part 36's fusion stress test). Explicitly NOT
done: M10, M13, M14, M15, M16, M17, B10/M-rmg. M12 has an ambiguous, unconfirmed note
("already done earlier as part of B4") -- treat as still open (see bug.md).

**Source:** pending_night.md

---

## part40_pending.md

# Part 40 [PENDING] -- Review-fix Phases 3-5: pipeline robustness, GUI hardening, minors batch

"Phases 3/4/5 (review_plan.md) -- not started at all," per pending_night.md. Covers
M13 (again), M18b-M27, B10, B13, and the full MINOR-list batch (parser leniency
warnings, canonicalize.py stoichiometry-in-key, argparse consistency, IDT refinement,
etc.) -- see bug.md for the full itemized list.

**Source:** pending_night.md, MarkDownFiles/review_plan.md

---

## part41_done.md

# Part 41 [DONE] -- Zero-RK: RCM via variable_volume.x integrated + verified end-to-end (2026-07-17)

8 new zerork_rcm_* defaults added to combustion_target_class.py; new elif "zerork"
branch added to the RCM target block in make_input_file.py, mirroring the existing
Tig/JSR pattern (YAML config -> subprocess -> parse "Time at max dP/dt" stdout summary
line as tau -- a real, documented definitional difference from the cantera/CHEMKIN_PRO
branches' two-peak temperature-history heuristic, same class of accepted gap as Tig's
zerork_idt_temp_delta).

A real escaping bug (single \n instead of \\n corrupting the generated child script)
found and fixed during verification. Verified end-to-end against the real binary: built a
combined CHEMKIN mechanism.inp + real volume-profile CSV from Zero-RK's own bundled
example data, ran the generated script for real, output/RCM.out matched Zero-RK's own
"Time at max dP/dt" stdout line exactly (38634.483 us at T=400K).

**Source:** This session's PLAN.md/progress.md (2026-07-17)

---

## part42_partial.md

# Part 42 [PARTIAL] -- Zero-RK: flame speed (Fls) + counterflow/extinction -- scoped, NOT implemented (2026-07-17)

Checked Flw target (already claimed by a JSR/PSR/FlowReactor species-slope-rate
target, unrelated to counterflow -- confirms counterflow needs a genuinely new target
tag). Investigated transport-file requirements: standard CHEMKIN .tran format is
byte-compatible with Zero-RK's own, not a blocker; Lewis_file needs Zero-RK's own
lewisGenerator.x tool, mechanically straightforward.

Real blocker found: premixedSteady.x / counterflowSteady.x are NOT single-subprocess-call
solvers like Tig/JSR/RCM -- they are fixed-inlet-velocity burner-stabilized solvers
needing a whole bootstrap pipeline (unsteady run for an initial profile -> Lewis_file
generation -> steady KINSOL solve -> adaptive regrid-and-retry loop), confirmed by
reading Zero-RK's own bundled Python driver (flamesolver.py::compute_steady_flame_speeds
+ examples/flame_speed/steady/sweep_steady.py). Deliberately did NOT rush a fake
single-call bridge for this -- would be plausible-looking but physically wrong.
Recommend a dedicated follow-up session, ideally after asking the user whether they need
full adaptive-grid fidelity or a cheaper approximation.

**Source:** This session's PLAN.md/progress.md (2026-07-17)

---

## part43_done.md

# Part 43 [DONE] -- Task B: dummy-mechanism GUI fusion stress test -- 3 real bugs found and fixed (2026-07-17)

Built 3 dummy CHEMKIN mechanisms (real H2/O2 chemistry, 8 species/8 reactions) with
every species spelled completely differently per mechanism (SMILES-only identity
resolution, zero string overlap by design) and the exact overlap structure requested
(1 reaction common to all 3, 2 shared between 2 of 3, rest unique). Parsed into a test
DB with 100% glossary hit on every mechanism.

Found and fixed: (1) UnionGraphSpec.save_json() crashed on any real compare-graph run
with tuple-keyed reaction buckets (regression from the prior session's M9 fix never
updating this serializer) -- fixed by stringifying tuple keys. (2) THE BIG ONE:
ChemkinWriter._format_rxn_string() trusted each reaction's cached, now-stale
formula_string (from its ORIGINAL source mechanism's spelling) instead of the
FK-linked, always-correct stoichiometry table -- meaning fused mechanisms could
reference species never declared in their own SPECIES block. Very likely a real root
cause of the user's actual "fusion doesn't work" complaint on real mechanisms with even
slightly different species spellings, not just this synthetic test. Fixed: always
rebuild from stoich, re-apply any (+M)/(+AR) collider annotation via regex extraction
from formula_string so that separately-fixed bug doesn't regress. Verified: ct.Solution()
loads the fixed fused YAML cleanly, all 8 reactions correct. (3) uncertainty_generator_gui.py
could only COLLAPSE an existing uncertainty XML, never GENERATE one -- the
generate_uncertainty_xml() capability existed only in the old monolith and was never
carried into any of the 8 split-out GUIs (this is almost certainly the literal root
cause of the user's "the GUI must be capable of generating xml files" ask). Fixed by
porting the function into uncertainty_generator_gui.py with a new "Generate" UI section.

Added permanent regression tests (test_chemkin_writer_species_staleness.py, 2 tests).
Full suite: 540 passed, 1 pre-existing unrelated failure (missing outputs/project.db).

Safety note: while attempting to drive the literal Tk GUI on the shared X display
(:52.0), a misdirected click/keystroke landed on a DIFFERENT, independently-running
Claude Code session's terminal and appears to have toggled its mode from "auto" to
"manual" -- no other damage observed, but flagged for the user to check. Switched to
calling the GUI's own worker functions in-process instead (same code path, no display
risk) for the remainder of this task.

**Source:** This session's PLAN.md/progress.md (2026-07-17)

---

## part44_pending.md

# Part 44 [PENDING] -- Task B remainder: sweep the other 5 launcher GUIs + literal-GUI verification + canonicalize.py fix

Not yet done, in priority order:
1. Smoke-test the remaining 5 launcher apps (brute_force_sa_gui.py, forward_uq_gui.py,
   nominal_sim_gui.py, mso_compare_gui.py, rmip_suite_gui.py, mechanism_converter_gui.py)
   against the fused dummy mechanism from Part 43 -- the user's explicit "repeat the
   process with all the GUIs available" ask.
2. Re-attempt driving the literal Tk GUI widgets (not just their worker functions) once a
   private/unshared X display is available, so "does the GUI itself work" is answered by
   literally driving it rather than by proxy.
3. core/canonicalize.py fix for the H2-self-third-body-vs-generic-M equivalence (Part 36's
   documented, not-yet-fixed limitation) -- decide whether to implement or explicitly
   accept and move on.
4. Verify the fused CHEMKIN .inp files (both Part 36's real-mechanism fusion and Part 43's
   dummy mechanisms) actually run end-to-end through Zero-RK, not just ck2yaml/Cantera.

**Source:** This session's PLAN.md/progress.md (2026-07-17)

---

