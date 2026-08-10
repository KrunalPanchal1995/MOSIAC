# Progress log

Running log against `PLAN.md`'s full-backlog priority list. Older, session-specific
detail (2026-07-14/15's Task A/B blow-by-blow) has been preserved in
`MarkDownFiles/HISTORY/part41_done.md` through `part44_pending.md` — this file now
tracks status against the reorganized priority list only, to avoid re-duplicating that
detail.

## 2026-07-17 (later same day, continued) — Priority 2 execution: fixture set built

Executing `GUI_STRESS_TEST_PLAN.md` now (was written but not run in the prior section
below). Decisions locked with the user before starting: (1) test mode = **in-process**
only (call worker functions / underlying CLI directly, never drive literal Tk widgets —
the shared X display `:52.0` hazard is still live); (2) forward_uq = fix B13 **and**
synthesize a minimal PRS cache for a full synthetic run, not just a verify-to-guard pass.
Full plan on disk: `/home/krithika/.claude-work/plans/next-up-per-the-serene-island.md`.

### Step 1 (fixture set) — DONE, verified

`src/rmip/tests/fixtures/gui_stress/make_gui_stress_fixtures.py` written and run
successfully. Produces, deterministically:
- `mech_A.inp`/`mech_B.inp`/`mech_C.inp` — 9 species/8 reactions each, zero
  cross-mechanism species-name overlap (real GRI-Mech-3.0 NASA-7 thermo, real
  FFCM-1 Arrhenius params), reaction overlap R1 (all 3) / R2 (A,B) / R3 (B,C) / 17
  mechanism-unique reactions. **Verified** via `rmip_cli.py compare-graph --mechs 1 2 3`:
  9 universal species / 0 partial / 0 unique, 3 identical reaction groups / 0 divergent /
  17 unique — exactly the designed structure.
- `thermo_A.dat`/`thermo_B.dat`/`thermo_C.dat`/`thermo_std.dat` — one THERMO block
  per mechanism, scoped to only that mechanism's own species names.
- `glossary.csv` (27 rows) — parse confirms **100.0% glossary_matched** for all 3.
- `mech_std.inp`/`mech_std.yaml` — canonically-named 9-species/3-reaction mechanism
  (via `ck2yaml`), reaction equations verified to match
  `h2_o2_crosscheck_unsrt.xml`'s `rxn=` strings **exactly** (`"H + O2 <=> O + OH"` etc.)
  — required because `Uncertainty.reaction.__init__` (`MUQ-SAC/Uncertainty.py:1780-1790`)
  hard-asserts each XML reaction string is in `MechanismParser.Parser(mechPath).rxnList`,
  which loads the mechanism as a Cantera YAML dict — a mis-spelled dummy would fail
  that assertion immediately, so `mech_std` is deliberately not interchangeable with
  mech_A/B/C.
- `project.db` — 3 mechanism rows (ids 1/2/3) via the real production parser
  (`rmip_cli.py parse --thermo --glossary`).
- `target.opt` + `targets/gui_stress.target` + `gui_stress.add` — 2-target Tig trio
  adapted from `DATASET/H2_O2_TEST`, repointed at `mech_std.yaml` +
  `h2_o2_crosscheck_unsrt.xml`, `Counts.targets_count: 2`.

**Two real bugs caught and fixed while building this script** (both were in the
fixture-generator itself, not production code — noting here since the fixes are the
kind of mistake worth remembering for future fixture work):
1. Naive token substitution of the single-letter identity `"O"` into a LOW/TROE
   falloff line corrupted the literal CHEMKIN keywords (`"LOW"` → `"LoxoW"`,
   `"TROE"` → `"TRoxoE"`), which the parser then logged as "No reaction arrow found"
   and silently mis-parsed. Fixed by never running substitution over LOW/TROE lines
   (they're pure numbers, no species tokens) — only the third-body efficiency line
   needs it.
2. A single **shared** `thermo.dat` across all 3 dummy mechanisms silently inflated
   every mechanism's stored species count to 36 and dropped glossary-hit to 75%,
   because `_chemkin_parser.py`'s `_parse_nasa7_entry` (:430-431) unions
   SPECIES-block-declared species with *every* THERMO-block entry it finds, not just
   the declared ones. Fixed by giving each mechanism (and `mech_std`) its own
   THERMO block scoped to only its own 9 species. Documented in the fixture script's
   `build_thermo_dat_for()` docstring so it isn't rediscovered.

### Step 2 (app sweep) — 2 of 8 done

**App 1/8 — `mechanism_converter_gui` — DONE, clean, zero bugs.** Golden path
(CHEMKIN→YAML+DB), `.pre` via real ScanMan with a transport file, and the
Fortran-exponent/CRLF auto-fix edge case all verified by content (species/reaction
counts, `ct.Solution` loads, DB rows). 3 tests, `test_gui_stress_sweep.py`.

**App 2/8 — `brute_force_sa_gui` — B12 re-verified fixed; 1 new bug found+fixed
(regression-tested); 1 new bug found, logged not fixed.**
- B12 (doubled relative path): confirmed still fixed by inspection (`_run_sa` resolves
  `out_dir` to absolute before building the command) AND by running
  `sens_3_params.py` end-to-end without ever hitting a doubled-path error.
- **New bug found + fixed**: `combustion_target_class.py`'s "Mono" fuel-type branch
  crashed on the real shipped `DATASET/H2_O2_TEST/targets/H2_IDT.target` (every real
  generated target file writes the fuel spec as a dict even for Mono; the Mono branch
  only handled a bare scalar). Fixed in both `MUQ-SAC/` and `Sensitivity_Analysis/`
  copies (byte-identical bug); `MUQ-SAC_EXTENDED`'s 3rd copy has the same bug but is
  out of scope (standing decision, PLAN.md Priority 6). Full writeup + regression
  tests: `BUG.md`, `test_combustion_target_mono_fuel_dict.py` (4 tests).
- Getting `sens_3_params.py` to run for real also required 3 more fixture additions
  (folded into `make_gui_stress_fixtures.py`): `Bin.samap_executable`/`jpdap_executable`/
  `yaml_writer`/`SA_tool` placeholders, a `StartProfilesData` block (required by the
  module-level load even though no Fls/Flf targets are used), and
  `Locations.Initial_pre_file` (a real `mech_std.pre` built via ScanMan). Also: the
  addendum's `ign_delay_def: OH*` (excited-state chemiluminescence species) doesn't
  exist in a minimal dummy mechanism -- switched the fixture's addendum to
  `ign_delay_def: OH` / `ign_cond: max` (peak ground-state OH, the standard fallback
  definition). Also: `mech_std` originally had only R1/R2/R3 (3 reactions, to match the
  crosscheck XML) which is physically **too incomplete to ignite** (no chain-branching/
  HO2/H2O2 network) -- confirmed via Cantera's own reactor integration ("No ignition!!").
  Expanded `mech_std` to the full 20-reaction network (same chemistry as mech_A/B/C
  combined) while keeping R1/R2/R3's equation strings byte-identical to the XML.
- **New bug found, NOT fixed this session**: with all of the above in place, the run
  gets all the way through target loading, uncertainty selection, design-matrix
  generation, and actual Cantera IDT simulation (nominal IDT = 962 µs, physically
  sane) -- then crashes with `ZeroDivisionError` in the `n`-parameter SA-coefficient
  step for the reaction with nominal `n=0` (`H+O2<=>O+OH`, a real, common Arrhenius
  fit shape). Root cause traced to `DesignMatrix2_0.py`'s fractional/relative `n`
  perturbation (`perturb_fact=0.1 * n0`), which is exactly 0 when `n0=0`. **Logged as
  M30 in `bug.md`, not fixed** -- the correct fix needs a closer read of
  `getClassA_Curves_partial`/`getClassA_Curves_partial_SA` to avoid changing SA
  results for the majority of reactions where `n0!=0`.
- Net: brute_force_sa_gui's own bug (B12) is confirmed fixed and the GUI's own code is
  clean; the crash now happens two layers deeper, inside `sens_3_params.py`'s numerical
  core, on real (not contrived) Arrhenius data. A full successful SA run is not yet
  achieved end-to-end.

**User checkpoint (2026-07-17):** asked whether to continue at this depth, go
shallower, or pause. Answer: **keep going at this depth.** Continuing below.

**App 2 test suite note:** `test_brute_force_sa_b12_and_mono_fuel_fix_no_longer_crash`
initially needed a longer subprocess timeout (120s -> 280s; the full SA run through
pytest's subprocess capture took ~168s here) -- not a product bug, just this
environment's actual runtime for the real Cantera+DesignMatrix pipeline.

**App 3/8 — `nominal_sim_gui` — DONE, B14 re-verified fixed, clean full run.**
`_load_run_labels()` (in-process) and the full `runpy` bootstrap `_run_sim` uses both
verified against a real mso_compare pipeline YAML pointed at `mech_std.yaml` + the 2
dummy Tig targets. Real Cantera IDT computed: 962 µs @ 1450K, 1325 µs @ 1350K (correct
Arrhenius trend: lower T -> longer delay). No doubled-path/cwd crash anywhere -- B14
confirmed still fixed. 2 tests, `test_gui_stress_sweep.py`.

**App 4/8 — `mean_value_fusion_gui` — DONE, 2nd pass, clean, zero new bugs, real gap
documented.**
- Golden path re-verified against the 3-mechanism dummy DB: 17 verbatim + 3 copy (R1
  shared-by-3, R2/R3 shared-by-2, byte-identical kinetics -> COPY not FUSE), 9 species,
  20 total reactions, element-balanced. Matches the graph-comparison structure verified
  when the fixtures were built.
- **New coverage** (Part 43 never exercised this): perturbed one shared reaction's
  A-factor by 1.5x in one mechanism's DB row to force genuine kinetics divergence.
  `_run_fusion` correctly classified it FUSE (not COPY) and computed the geometric mean
  of A to 6 decimal places (`geomean(A, 1.5A, A) = A * 1.5**(1/3)`, verified via direct
  DB query on the fused mechanism row).
- **Real finding, logged not fixed (feature gap, not a bug to "fix" in this pass):**
  the plan asked to test "priority-pick fusion mode" here -- turns out this GUI cannot
  invoke it AT ALL. `mean_value_fusion_gui.py` only ever calls `rmip.stubs.FusionEngine
  .fuse()` (no `fuse_overrides`/`priority_order` UI control exists). Priority-pick
  fusion exists only on the separate, CLI-only `rmip.analysis.fusion.FusionEngine.fuse
  (priority_order=[...])`. Logged in `bug.md`.
- 2 tests, `test_gui_stress_sweep.py`.

**App 5/8 — `uncertainty_generator_gui` — DONE, 2nd pass, 1 new bug found+fixed
(regression-tested).**
- Generate -> Collapse round-trip verified: `generate_uncertainty_xml()`'s output is
  correctly re-read by `compute_symmetric_bounds()`, computed `A_nominal` matches the
  real mechanism's Arrhenius A to 3 sig figs, `A_lb < A_nominal < A_ub` with `factor >
  1`.
- **New bug found + fixed**: `generate_uncertainty_xml()` always emitted a blank
  `<class></class>`. `MechManipulator2_0.py`'s `doPerturbation()` dispatches on that
  value and silently no-ops perturbation when it doesn't match any known classification
  -- the exact defect the crosscheck-fixture docstring already flagged for a *different*
  shipped XML, but present here too, in the generator this GUI's own docstring claims
  already had its 2 known bugs fixed. Fixed: default `<class>` to `"Elementary"`
  (overridable via `rxn["classification"]`). Full writeup: `BUG.md`. 1 test (updated),
  `test_gui_stress_sweep.py`.

**App 6/8 — `forward_uq_gui` — DONE, B13 fixed, full synthetic run succeeds
end-to-end.**
- Fixed B13: `_run_uq` resolves `out_dir` to one absolute path up front and derives both
  `target_opt_path` and `--output_dir` from it, instead of building two relative paths
  from the same string while also launching the child with `cwd=` that same string
  (which `forward_uq.py`'s own `workdir=os.getcwd()` + `os.path.join(workdir,
  args.output_dir)` doubled). Verified in two stages, both passing as permanent tests:
  1. Path-fix-only: reaches the legitimate "Opt/ directory not found" guard cleanly
     (`Loaded 2 target cases`, `n_full = 3`), no `FileNotFoundError`.
  2. **Full run**: built `bootstrap_forward_uq_cache.py` (folded into the fixture dir,
     derives the active-parameter list from the same `Uncertainty.py` code path
     `forward_uq.py` itself uses, rather than hard-coding `1_A`/`2_A`/`3_A`, per the
     plan's design) to synthesize a minimal `Opt/` + `DM_FOR_PARTIAL_PRS/` cache
     (10-coefficient order-2 PRS × 2 cases). With it in place, `forward_uq.py` completes
     all 5 steps for real: `forward_uq_statistics.csv` (2 rows, real physics-shaped
     numbers), `sobol_indices.csv`, and all 5 plot PDFs. No multi-hour MUQ-SAC
     optimization needed, matching the plan's approved design.
- 2 tests, `test_gui_stress_sweep.py`. B13 moved from `bug.md` to `BUG.md`.

**App 7/8 — `mso_compare_gui` — DONE, never tested before, clean, zero bugs found.**
- Ran `run_mso_pipeline.py` with 2 simulation entries (`nominal_htc`+`nominal_ltc`,
  deliberately not dodging concurrency) so Phase 1 dispatches >=2 real concurrent
  `ThreadPoolExecutor` workers -- the exact shape M24 needs to fire. Both completed
  (`status: done`) and each wrote its OWN correct dataset CSV to its OWN output dir; no
  missing/misplaced files, no cross-written content, values matched App 3's
  independently-verified numbers exactly (962.34/1324.88 µs) in this run.
- **M24 status**: confirmed structurally still present by code read (`sim_runner.py`'s
  `os.chdir()` calls are wrapped in try/finally, which guarantees cleanup on exit but
  NOT mutual exclusion during the work -- `os.chdir` is process-global, threads share
  it) but did **not** manifest as observable corruption in this run (fast synthetic
  sims, narrow race window). Structural risk remains open per `bug.md`; a real trigger
  would likely need slower/larger simulations to widen the window. Not fixed this
  session (Priority 4, needs a real design change per `PLAN.md`).
- **Real, non-bug finding**: Phase 2 (merge) warned "Cannot parse φ/P from
  'dataset_001.csv'" and Phases 3-4 gracefully skipped as a result (no crash). Root
  cause: `merge.py` is built specifically for phi-organized LFS/flame-speed-style
  filenames (`Phi_0_5_P_10.csv`, per its own docstring), not Tig/IDT `dataset_NNN.csv`
  output. This is a scope characteristic (Phase 1 works for any target type; Phases
  2-4 assume phi-organized data), not a defect -- documented here, not filed as a bug.
- 1 test, `test_gui_stress_sweep.py` (needed a longer subprocess timeout, 90s->180s,
  after an intermittent timeout when run alongside the full 490+ test suite under
  system load; passes reliably in isolation both before and after the bump).

**App 8/8 — `rmip_suite_gui` — DONE, all 4 tabs, never tested before, clean, zero bugs
found.** GSA and Active-Param-Selection had zero GUI-adjacent coverage ever; both work
correctly on first real test.
- **Tab 1 (compare-graph)**: already the exact command used to verify the fixture set
  itself while building it (9 universal species, 3 identical reaction groups, 17
  unique) -- now locked in as a permanent test.
- **Tab 2 (reduce)**: real DRG reduction on mech_A. Correctly identifies the inert
  third-body-only species (AR, never a true reactant/product) as removable at
  threshold 0 -- confirms the reachability-graph logic is sound, not just "runs
  without crashing."
- **Tab 3 (gsa-run)**: real Zero-RK Sobol GSA (`perturbAFactorGSA_mpi.x`, 20 samples =
  N=2 x (D=8 reactions + 2)), 0 failed/non-ignition samples, real S1 indices for all 8
  reactions, DB row + JSON written. First time this code path has ever been exercised
  end-to-end via anything resembling the GUI's own command.
- **Tab 4 (active-param-selection)**: `src/ActiveParameterScreen.py` against a real
  `ck2yaml`'d mechanism + 2 synthetic SA `.txt` files (a DIFFERENT format from
  `sens_3_params.py`'s own CSV output -- `modules/sensitivity_parser.py`'s expected
  shape, confirmed by reading it). Correctly threshold-screens to 4/8 reactions,
  classifies reaction types (Falloff/Elementary/ThirdBody) correctly, extracts the
  correct 6 active species with correct carbon numbers (all 0, pure H/O/Ar chemistry).
- 4 tests, `test_gui_stress_sweep.py`.

### Exit criteria (GUI_STRESS_TEST_PLAN.md §4) — MET

All 8 apps have a same-session in-process (or, per the locked decision, subprocess-to-
the-underlying-CLI where the app itself only shells out) run recorded here against the
shared dummy fixtures, output verified by content. 16 permanent regression tests in
`test_gui_stress_sweep.py` + 4 in `test_combustion_target_mono_fuel_dict.py` (20 total),
all green in the full suite. Bugs found this session: 3 fixed + regression-tested
(Mono-fuel-dict crash, blank-`<class>` XML generator bug, B13's doubled path), 2 logged
not fixed (M30 ZeroDivisionError on n=0 reactions; the priority-pick-fusion-mode
feature gap), 1 structural risk re-confirmed but not newly triggered (M24). 2 of 4
resolved bugs this session (B12, B14) were re-verifications of already-fixed bugs, now
with real regression coverage for the first time. Full test suite: 491+/493 passing,
1 pre-existing unrelated failure (`test_gsa_prs_crosscheck.py`, missing
`outputs/project.db`, predates this session).

**Final verification (2026-07-17, end of session):** one more real bug found + fixed
while cleaning up: `mechanism_converter_gui.py`'s ScanMan (`.pre`) branch left ScanMan's
own intermediate debris (`<stem>.chmech`/`.chthermo`/`.chtrans`/`.h`) at repo root
instead of the user's chosen output dir (`run_tool()` never passed `cwd=` for that
subprocess). Fixed (`cwd=str(out_p)` on the ScanMan call only; `ck2yaml`/`rmip_cli.py
parse` were unaffected). Full suite re-run clean after: **492/493 passing**, only the
same pre-existing unrelated failure. Repo root confirmed clean (no stray debris) via
`git status`.

### Next (not started this session, per `GUI_STRESS_TEST_PLAN.md` §4/§5)
- Second, larger-scale tier against the real fused mechanisms
  (`outputs/fusion/Fused_Mech.*`, `outputs/fusion_keromnes_li_davis/...`) -- scale/
  real-naming quirks (long species names, unusual third-body syntax) only show up on
  real data, not the minimal dummy fixtures.
- M30 (SA `n=0` ZeroDivisionError) needs a real fix in `DesignMatrix2_0.py`'s
  perturbation-generation formula -- deferred, needs careful scoping to avoid changing
  SA results for reactions where `n0!=0`.
- M24 (mso_compare CWD race) needs the real design-level fix already scoped in
  `PLAN.md` Priority 4 (per-worker subprocess with its own cwd argument, not shared-
  process `chdir`) -- this session only re-confirmed it structurally, did not fix it.
- Then continue down `PLAN.md`'s Priority 3 (Zero-RK flame speed/counterflow, needs a
  user fidelity-vs-cost decision first) and Priority 4 (the rest of the M16-M28 batch).

## 2026-07-17 (later same day) — Priority 0 complete, GUI stress-test plan, feature-gap audit

### Done today

- **Priority 0 fully closed** — all 5 data-integrity bugs fixed and regression-tested
  (472 passed, 1 pre-existing unrelated failure before and after). Full writeups in
  `BUG.md`; the short version:
  - **M12** re-verified (was already fixed by B4's Phase 1 work, just never
    independently confirmed) — added `test_fusion_m12.py`.
  - **Self-third-body equivalence** (`H2+M<=>2H+M` vs. `2H+H2<=>2H2`) fixed via a new
    opt-in `cancel_self_third_body` param on `make_reaction_canonical_key`
    (`core/canonicalize.py`), wired into `core/parser.py`'s production DB-build path.
    Verified end-to-end through the real CHEMKIN parser, not just unit-level — both
    reaction forms now produce the identical `canonical_key`. As a side effect this also
    fixed the separately-tracked MINOR "canonicalize.py ignoring stoichiometric
    coefficients" for that path. `test_canonicalize_self_third_body.py`.
  - **M10** (`graph_comparator.py`) fixed — kinetics-identity check now also requires
    matching `kinetics_type` and, for pressure-dependent types, a tolerant full
    comparison of the falloff/PLOG/Chebyshev `kinetics_data_json` payload, not just the
    single representative A/n/Ea triple. `test_graph_comparator_m10.py`.
  - **M13** (`unified_tree.py`) fixed — decision↔band audit-DB pairing now tracked in
    lockstep (`band_decisions` list) instead of re-derived via a `zip()` that could shift
    after a failed OPTIMIZE build. Confirmed the test actually catches the bug (failed
    against the reverted code, passed after re-applying). `test_unified_tree_m13.py`.
  - **M14** (`uncertainty_bands.py`) fixed — 3 stacked bugs in one path: Cantera-2 API
    shapes that don't exist in Cantera 3 (`ct.TroeFalloff`, `ct.FalloffReaction`'s
    `high_rate`/`low_rate`/`falloff` kwargs, `ct.ChebyshevReaction`), a `ct.NasaPoly2`
    14-vs-15-element coefficient array bug, and the actual Ea unit bug (this codebase's
    J/mol vs. Cantera's Python `ct.Arrhenius` expecting J/kmol). Verified against an
    independently-built Cantera YAML mechanism (`rel=1e-6` match). None of this was
    caught by any exception handling before — every one of these paths would have raised
    uncaught the first time `use_cantera_for_falloff=True` hit a Troe/Lindemann/Chebyshev
    reaction. `test_uncertainty_bands_m14.py`.
- **`GUI_STRESS_TEST_PLAN.md`** written — expands `PLAN.md` Priority 2 into a full
  per-app procedure: a checked-in dummy-fixture set (3 mechanisms with zero string
  overlap + deliberate reaction-overlap structure, matching the shape that already found
  real bugs in Part 43), an apply-to-every-app checklist, all 8 apps in recommended
  order (including `mechanism_converter_gui.py`, never stress-tested, and a second pass
  over the two apps Part 43 partially covered), and exit criteria. Not executed yet —
  this is the plan only, per the user's ask to "make a plan" first.
- **`FEATURE_GAPS_FROM_MONOLITH.md`** written — a research pass (background subagent,
  read-only) comparing the retired `generate_target_opt.py` (12 tabs, 6097 lines)
  against the 8 split GUI apps (~2254 lines total), tab-by-tab and menu-by-menu. Found 5
  entirely orphaned tabs (Project, Files & Paths, Mechanisms, Experimental Data,
  Addendum, Optimization, .so Compiler, Preview — no new app covers them at all) plus
  real reductions in RMIP Analysis (lost multi-condition reduction + 3D diverse-subset
  sampling) and Forward UQ (lost the plot-thumbnail viewer). Also found `gui_common`'s
  `autosave.py`/`fuel_data.py`/`variable_map.py`/`target_types.py` are fully extracted
  but imported by **zero** of the 8 apps — dead infrastructure with nothing plugged in.
  Ranked ~10 candidates at the bottom of the file. **Per user instruction, this is a
  reading list only — nothing from it has been implemented; wait for the user to pick
  specific items.**
- **Priority 1 verified** — ran `constVolumeWSR.x` directly against both
  `Fused_mean_KLD.inp` and `Fused_priority_KLD.inp` (Keromnes/Li/Davis fusion), same
  config shape as `make_input_file.py`'s zerork branch. Both parse cleanly through
  Zero-RK's own CHEMKIN parser (`mech.clog` ends "Success", 17 species/56 reactions, no
  rejection) and the ODE integration completes with no cvode errors. This was the
  #1-listed "immediate next step" carried unfinished across three prior sessions —
  closed out. Full writeup in `BUG.md`.

### Old section (earlier same day)

- Read every `.md`/`.txt` file in the repo (via a research subagent covering
  `MarkDownFiles/`, `.claude-review/`, root-level docs, and the session's own memory
  files) and reconstructed a full chronological history: **44 numbered parts**, each
  tagged DONE/PARTIAL/PENDING, written to `MarkDownFiles/HISTORY/part*.md` +
  `MarkDownFiles/HISTORY/INDEX.md`.
- Compiled the full resolved-bug list into `BUG.md` and the full unresolved-bug/
  known-limitation list into `bug.md`, both at repo root.
- Rewrote `PLAN.md` as a full-backlog priority plan (Priority 0–6) covering every
  PARTIAL/PENDING history part and every unresolved bug, not just this session's
  original two tasks.
- Continued today's own Task A (Zero-RK RCM integration — DONE, verified end-to-end,
  see `MarkDownFiles/HISTORY/part41_done.md`) and Task B (GUI fusion stress test — DONE,
  3 real bugs found and fixed, see `part43_done.md`). Full detail already in those two
  history files plus `BUG.md`; not repeated here.

### Next (per `PLAN.md`'s priority order)

1. ~~**Priority 0**~~ — **DONE** (this session, see above). All 5 items fixed and
   regression-tested.
2. ~~**Priority 1**~~ — **DONE** (this session, see above). Both fused `.inp` files
   confirmed to parse and run cleanly through Zero-RK's own CHEMKIN parser.
3. **Priority 2** (now first up): execute `GUI_STRESS_TEST_PLAN.md` (written this
   session, not yet run) — all 8 apps against the checked-in dummy fixtures, fixing B13
   (`forward_uq_gui.py`) while there.
4. **Priority 3**: Zero-RK flame speed + counterflow/extinction — needs a user decision
   on fidelity vs. cost first (see `PLAN.md`), then a real multi-stage bootstrap-pipeline
   implementation, not a quick bridge.
5. **Priority 4**: review_plan.md Phases 3–5 (M16–M28 batch), grouped by workstream in
   `PLAN.md`.
6. **Priority 5**: re-verify Future.md's 6 restart/checkpoint bugs against current code
   before assuming any are still open.
7. **Not prioritized, reading-list only**: `FEATURE_GAPS_FROM_MONOLITH.md` (written this
   session) — wait for the user to pick specific items before implementing anything.

## Open questions for the user (not blocking, but worth flagging)

- `prompt.txt` (an earlier session) contains a literal `/model opusplan` line — not
  executed (see `PLAN.md`'s Notes section). If this was meant as a live command, please
  re-issue it directly in chat.
- **Check on your other Claude Code session(s) running on this same X display (`:52.0`)**
  — while driving the fusion GUI earlier today, one misdirected click/keystroke sequence
  landed on a different session's terminal window and appears to have toggled its mode
  from "auto" to "manual" (visible in a before/after screenshot, ~2026-07-17 06:08). No
  other damage was visible (its prompt was empty afterward) and no further interaction
  with that window was attempted once this was noticed, but it's worth confirming that
  session is still running the way you expect.
- **Priority-0 item 1 (M12)** and **Priority-5 (Future.md bugs)** both have "ambiguous/
  unconfirmed" status in `bug.md` — worth a quick manual look before anyone spends fix
  time on them, in case they're already resolved and just poorly cross-referenced across
  documents.

## 2026-07-17 (continued) — M24 and M30 fixed, closing out the GUI stress-test session's deferred items

Picked up the two items explicitly deferred at the end of the prior GUI-stress-test
session (see this file's own "Next" list above): M30 and M24, both now fixed with
regression tests, plus dispatched a background pass for the third deferred item (the
real-fused-mechanism GUI sweep tier).

- **M30 fixed** (`src/Sensitivity_Analysis/DesignMatrix2_0.py::DesignMatrix.getSA_3P_samples`)
  — the `ZeroDivisionError` in `sens_3_params.py`'s brute-force SA, previously blamed on
  "nominal n=0" reactions. Actual root cause (found by instrumenting `delta_dict`
  construction against the real GUI-stress fixture): `getSA_3P_samples` reused
  `_get_rxn_param_indices()`, a helper meant for a different caller
  (`partial_PRS_system.py`'s real joint MUQ-SAC PRS/GSA path) whose chunk width
  legitimately varies with `len(activeParameters)`. `getSA_3P_samples` always passes a
  uniform 3-per-reaction `[A,n,Ea]` mask instead, so for any `factor`-type (A-only)
  reaction the chunk read desynced and collapsed to `idx=(0,)` for every param_type —
  "n"/"Ea" were silently never sampled (their ζ came out exactly 0.0 by construction,
  confirmed via log: `L_r_n` was genuinely nonzero, `zr_n` was exactly 0.0). Fixed by
  mapping `param_type` straight to its fixed Arrhenius index instead of going through the
  variable-width helper. Verified end-to-end from a clean directory (no stale
  `pDesignMatrix_*.csv` cache): the full brute-force SA run now completes with distinct
  nonzero SA coefficients for A/n/Ea across all 3 reactions, ending at the script's own
  pre-existing completion sentinel with no exception. `test_gui_stress_sweep.py`'s
  `test_brute_force_sa_b12_and_mono_fuel_fix_no_longer_crash` — previously a deliberate
  trip-wire asserting the crash — now asserts full clean completion.
- **M24 fixed** (`src/mso_compare/pipeline.py::MSO_Pipeline.run_simulations`) — switched
  from `ThreadPoolExecutor` to `ProcessPoolExecutor`. `sim_runner.run_nominal_simulation()`
  changes the process-wide CWD around each run's solve and `utils.setup_logging()` swaps
  the process-wide root logger's `FileHandler` per run; under shared-process threads,
  concurrent runs could corrupt each other's outputs/logs. Verified the race was 100%
  real, not theoretical: a standalone repro with 4 threads each `os.chdir()`-ing into
  their own dir with a staggered sleep showed **all 4** observing the wrong directory —
  and structurally impossible once each run is its own OS process. Required promoting the
  per-run dispatch closure to a module-level `_run_one_sim()` (ProcessPoolExecutor pickles
  the callable even under "fork"). New regression test:
  `src/rmip/tests/test_mso_pipeline_m24.py`.
- Both fixes are both full write-ups moved from `bug.md` to `BUG.md`.
- **Full-suite verification**: `python3 -m pytest` (whole repo) → **584 passed, 1 failed**
  — the 1 failure is `test_gsa_prs_crosscheck.py::TestFullCrossCheckEndToEnd::test_run_crosscheck_completes_on_real_mechanism`,
  a pre-existing, unrelated `project.db`/mechanism-mismatch issue (same class of failure
  documented as pre-existing in the prior session's 492/493 count) — confirmed no overlap
  with anything M24/M30 touched.
- **Dispatched (background agent, in progress as of this writing)**: the third deferred
  item, `GUI_STRESS_TEST_PLAN.md` §4's real-fused-mechanism second tier — re-running all 8
  GUI apps' in-process worker functions against the real Keromnes/Li/Davis fused mechanism
  (`outputs/fusion_keromnes_li_davis/{mean_unsrt,priority}/Fused_*_KLD.*`) instead of the
  small dummy fixtures, to catch scale/real-naming quirks the dummies can't. Results not
  yet in at the time this entry was written — check `BUG.md`/`bug.md` for whatever it
  found by the time you read this.

## 2026-07-17 (later still) — Real-mechanism second-tier GUI stress test (GUI_STRESS_TEST_PLAN.md §4)

Executing the deferred second tier: same 8-app sweep, pointed at real fused mechanisms
instead of dummy fixtures. In progress -- this section updated incrementally as each
app is exercised (flush-to-disk, per project memory's lesson).

### App 1 -- mechanism_converter_gui.py: DONE, 1 real bug found + fixed
- Confirmed `outputs/fusion/Fused_Mech.*` is a stale/empty placeholder (0 species, 0
  reactions in the `.inp`; just an END-only `.dat`) -- NOT usable as a real fixture,
  per the task's own warning. Used `outputs/fusion_keromnes_li_davis/{mean_unsrt,
  priority}` instead.
- Confirmed the documented stale-YAML self-third-body issue is real and reproduces
  exactly as described when converting the ON-DISK `Fused_mean_KLD.inp` fresh through
  `mechanism_converter_gui.convert()` (not just loading the pre-existing `.yaml`) --
  same known issue, not new, since the `.inp` text itself still has the two
  unmerged reaction forms baked in from before the canonicalizer fix.
- Re-parsed the 3 real source mechanisms (Keromnes/Li/Davis) fresh via `rmip_cli.py
  parse` (now with the self-third-body canonicalizer fix active) and re-fused them
  via `mean_value_fusion_gui._run_fusion()` -- produced `Fused_mean_KLD_v2`, whose
  YAML loads CLEANLY in Cantera (17 species/56 reactions, no duplicate-reaction
  error). Confirms the fix's real-world benefit end-to-end, not just at the DB level.
- **New real bug found + fixed**: `convert()` passed the SAME file for both `--input`
  and `--thermo` to ck2yaml whenever a user (or, here, this session's own test setup)
  points the thermo field at a self-contained mechanism's own inline-THERMO file --
  ck2yaml then re-parses the REACTIONS section a second time, silently doubling every
  reaction (112 instead of 56 on the real fused mechanism), or crashing outright if
  two of the doubled reactions collide (as happened here: `HCO + HO2 => CO2 + H + OH`).
  `rmip_cli.py parse`'s own CHEMKIN parser was unaffected. Fixed: drop the redundant
  `--thermo` when it resolves to the same path as `--input`. Full writeup + regression
  test (`test_mechanism_converter_self_contained_thermo_not_doubled`) in `BUG.md`.

### Remaining apps: in progress, see below as completed.

### App 2 (brute_force_sa_gui / sens_3_params.py) -- real target, BLOCKED by a new bug
Built a real target.opt/target/add trio (T=1450/1350K, P=2.2atm, real H2/O2/Ar IDT
values borrowed from `DATASET/H2_O2_TEST`) against the real fused KLD mechanism, with
a real 12-reaction uncertainty XML (mixed `factor`/`arrhenius` perturbation types, per
the M30 real-world-mix request). B12/Mono-fuel-dict/M30 all confirmed still fixed (no
recurrence of any of those 3 crash signatures) -- the run gets cleanly through target
loading, uncertainty selection, and design-matrix generation every time. But every
single simulation (nominal AND perturbed, reproducible at `parallel_threads: 1` too,
ruling out a race) fails because its per-instance working directory never gets the
`mechanism.yaml` file `data_management.py`'s `Design_of_PRS: A-facto` branch requires --
confirmed NOT a mechanism-content or parsing issue (the exact compiled writer the
pipeline uses, called directly/standalone with the exact same real mechanism dict,
writes it fine, twice). New bug logged in `bug.md` (not fixed -- likely a fork-safety
issue in the compiled `yamlwriter.so`/`parallel_yaml_writer.so` extensions that only
manifests for a real-sized (56-reaction) mechanism, unconfirmed without gdb/core-dump
analysis).

**Follow-up 2026-07-20**: further mitigated (see `bug.md`'s entry, "Further mitigated
2026-07-20"). `run_map`'s single `yamlwriter.dump_to_yaml` call site now goes through a
new `_write_mechanism_yaml_verified()` helper (verify → retry ×3 → pure-Python YAML
fallback → clear `RuntimeError` if both fail) so the silent-write failure can no longer
propagate into the confusing downstream `IndexError`. Root-cause read of
`yamlwriter.cpp::dump_to_yaml` CONFIRMED the suspected mechanism: a bare
`std::ofstream` with no `is_open()`/`fail()` check and no exceptions enabled, so a
failed open/write is a silent C++ no-op by default. The exact trigger under real-scale
mechanisms in a forked Pool worker is still not nailed down (would need strace/gdb
under real load) -- only the silent-failure *mechanism* is confirmed and now contained.
Tests: `src/rmip/tests/test_simulation_manager_yaml_write.py` (3 tests, all passing).

### Fusion physics: MAJOR new bug found -- fused mechanisms are silently ~non-reactive
While investigating why real-mechanism ignition kept failing across apps 2/3, did a
clean controlled test: a stoichiometric H2/O2/Ar mix at 1800K ignites in 3 MICROSECONDS
in the real standalone Keromnes-2013 mechanism (cross-checked against Cantera's own
h2o2.yaml reference -- near-identical peak temperatures, confirming the test method is
sound) but shows ZERO temperature rise after 50 MILLISECONDS in a freshly-rebuilt fused
mechanism (mean OR priority mode, same symptom) built from the same 3 real sources via
current code. Root-caused precisely: `FusionEngine`'s priority-pick/verbatim-copy path
writes the fused reaction's `A_orig` DB column equal to `A_si` (the SI-basis value)
instead of the true original-CGS-units value, so `ChemkinWriter`'s default
`use_original_units=True` export writes that wrong value verbatim under a CGS-units
header -- every bimolecular reaction's A-factor ends up ~10^6 too small. This affects
BOTH fusion code paths (`rmip.analysis.fusion.FusionEngine` used by the CLI/priority
mode, and by direct symptom evidence also `rmip.stubs.FusionEngine` used by
`mean_value_fusion_gui.py`'s "write Cantera YAML" option) and means every fused
mechanism this suite has ever exported via CHEMKIN/Cantera-YAML (including the
already-shipped `Fused_mean_KLD.*`/`Fused_priority_KLD.*` files) is likely silently
near-inert for its bimolecular reactions -- far worse than the already-documented
Cantera-duplicate-load failure, since this corruption loads and runs fine, it just
barely reacts. NOT fixed this session (needs a properly-scoped follow-up touching the
shared record-construction path for all 3 fusion treatments). Full repro + diagnostic
detail in `bug.md`. This is very likely the actual, final answer to "why doesn't fusion
work right," superseding earlier partial theories.

Given this finding, apps 3/6/7/8 below were validated for MECHANICS (do they run, do
they produce correctly-shaped output files) using a real, unaffected mechanism (either
Keromnes-2013 standalone, unaffected by the fusion bug since it's not a fusion output,
or the fused mechanism where the specific check doesn't depend on live ignition), not
always through a live ignition physics check on the (currently broken) fused output.

### App 3 (nominal_sim_gui) -- DONE clean, real data
Rebuilt real target/add/mso_config against the real, unaffected (non-fused) Keromnes-
2013 mechanism at fast-igniting real conditions (T=1800/1700K, stoichiometric-ish
H2/O2/Ar, confirmed to ignite in ~5-14us via direct Cantera check first). Full
`mso_compare.run_nominal_sim` run: "Status: done", real physically-sane IDT values
written to `Plot/Dataset/Tig/dataset_001.csv` (14.02us @1800K, 13.51us @1700K -- both
real, nonzero, same order of magnitude as the direct-Cantera check). Also incidentally
found and diagnosed (see bug.md) a secondary `data_management.py::run_sim` "soln2ck_2.py
not found in run script" bug while chasing why the FUSED-mechanism version of this same
test produced NaN -- that NaN turned out to be the fusion A-factor bug above, not this
one, but the soln2ck_2.py issue is real and independent (masks the true error on any
solver=cantera retry).

### App 7 (mso_compare_gui) -- DONE clean, M24 re-confirmed on real data
2 concurrent real-mechanism nominal runs (`run_mso_pipeline.py --regime both`, same
Keromnes-2013 real mechanism/conditions as App 3) via `ProcessPoolExecutor`. Both
completed `[status: done]`, and -- critically -- both landed the IDENTICAL correct
values (14.02/13.51 us) in their OWN separate output directories with zero cross-
contamination, reconfirming M24's fix under real (not just synthetic) concurrent load.

### App 8 (rmip_suite_gui), all 4 tabs -- DONE, real data throughout
- Tab 1 (compare-graph): re-run on the fresh post-canonicalizer-fix Keromnes/Li/Davis
  DB -- 14 universal species, 3 unique, 3 identical/33 divergent/20 unique reactions
  (same topology as the original 2026-07-14 punchlist; confirmed the self-third-body
  pair now shares one canonical_key, see BUG.md).
- Tab 2 (reduce/DRG): ran on the freshly-fused 17-species/56-reaction mechanism,
  correctly identified inert/disconnected species (C2H6, HE) as removable at eps=0 and
  progressively more species (down to 9) at eps=0.5.
- Tab 3 (gsa-run): real Sobol GSA on the FULL real 49-reaction standalone Keromnes
  mechanism (not just a 6-reaction subset), 102 samples, 0 failed/non-ignition,
  correctly ranks `H + O2 <=> O + OH` (the real dominant H2/O2 chain-branching
  reaction) as the top-sensitivity reaction (S1=+0.25) -- a real, physically-sane
  result on real-scale data, never exercised on anything this size before.
- Tab 4 (Active Parameter Selection): ran on the real 56-reaction fused mechanism with
  2 synthetic-but-realistic SA files; correctly screened 4 active reactions at
  threshold 0.10, correctly classified reaction types (Elementary/Duplicate) including
  DUPLICATE-marked reactions the fusion process itself force-marked, and -- notably --
  correctly computed Carbon_Number=1 for real carbon species (CO, CO2), a code path the
  all-H/O/Ar dummy fixture could never exercise at all.

### App 6 (forward_uq_gui) -- PARTIAL
Re-verified B13's doubled-path fix holds on real data: running `forward_uq.py` against
a real target.opt (real Keromnes mechanism, real 12-reaction uncertainty XML, real IDT
targets) correctly loads the config and cleanly reaches the legitimate "Opt/ directory
not found" guard -- no doubled-path `FileNotFoundError`, matching the dummy-fixture
regression test's own first assertion. Did NOT complete a full synthetic-PRS-cache run
against real data this pass: `bootstrap_forward_uq_cache.py`'s dependency,
`Uncertainty.py`'s own mechanism/reaction-matching logic, rejected one of the 12 real
reaction names as "not in the mechanism" even though the exact same equation string is
confirmed present in `gas.reaction_equations()` via Cantera directly -- Uncertainty.py
evidently parses/matches reactions through a different internal path than a plain
Cantera equation-string lookup, and the mismatch wasn't root-caused given time spent
diagnosing the (unrelated, more serious) fusion A-factor bug above. Not logged as a
confirmed new bug (insufficient diagnosis to be sure it's not just missing test-harness
setup on my part, e.g. a required thermo_file/trans_file path) -- flagged here as an
open thread for a future session rather than in `bug.md`'s confirmed-repro list.

### App 4 (mean_value_fusion_gui) -- 2nd pass, real data
Fresh mean-mode fusion of the real Keromnes/Li/Davis mechanisms via `_run_fusion(...,
write_cantera=True)`: 20 verbatim / 3 copy / 33 fuse / 17 species, balanced=True,
matches the original 2026-07-14 topology exactly. This is also how the MAJOR fusion
A-factor bug above was found (both mean and priority modes exhibit it -- confirmed via
direct DB inspection and live ignition-physics testing, not just file content). Priority
mode itself remains untestable through this GUI (pre-existing, already-documented
feature gap, `bug.md`) -- exercised via the separate CLI-only
`rmip.analysis.fusion.FusionEngine.fuse(priority_order=...)` instead, which is where the
bug was cross-confirmed to also affect priority mode.

### App 5 (uncertainty_generator_gui) -- 2nd pass, real data
Generated a real 12-reaction uncertainty XML (mixed `factor`/`arrhenius` perturbation
types, matching the "realistic mix" ask) directly against the real, freshly re-fused
KLD mechanism's own real reactions (H+O2<=>O+OH, H2+O<=>H+OH, CO+O2<=>CO2+O, etc.).
Generate -> Collapse round-trip: all 12 reactions produced sane, error-free bounds
(A_lb < A_nominal < A_ub, factor > 1.0 for every reaction).

### Final test-suite run (2026-07-17, end of real-mechanism second-tier pass)
`pytest src/rmip/tests/ tests/ -q`: **580 passed, 1 failed** (314s). The 1 failure is
the same pre-existing `test_gsa_prs_crosscheck.py::test_run_crosscheck_completes_on_
real_mechanism` noted in earlier sessions -- confirmed NOT caused by anything this
session touched (this session only edited `mechanism_converter_gui.py` and added new
tests). Useful corroboration found while investigating it: its current failure reason
is the EXACT SAME `Uncertainty.py` "Rxn ... not in the mechanism" AssertionError
independently hit during this session's own App 6 (forward_uq) real-data testing --
same reaction (`H2 + O <=> H + OH` / `O + H2 <=> H + OH`, same physical reaction),
same assertion, same module. Not root-caused this session (would need to trace
`Uncertainty.py`'s own internal reaction-matching logic, which evidently doesn't just
do a plain Cantera-equation-string lookup), but now confirmed as a real, currently-
reproducible pattern affecting real mechanisms generally, not just a one-off harness
mistake in my own App 6 test setup. Left as an open thread (not added to `bug.md`'s
confirmed-repro list since the exact trigger condition inside `Uncertainty.py` isn't
pinned down) -- a good lead for whoever next debugs `test_gsa_prs_crosscheck.py`.

### Cleanup
All working-directory side effects from this session's real-mechanism runs (`SIM_RUNS/`,
`SA_3P/`, `Perturbed_Mech_SA_3P_BruteForce/`, stray `DesignMatrix*.csv`/`DM_plots/`/
`Reaction_dict.txt`/etc. that `sens_3_params.py` writes to its CWD by design) were
removed from the repo root; `git status` confirms clean (only this session's intended
file edits/additions remain untracked or modified).

---

# 2026-07-19 — Robustness cluster + RMG/DRG quick wins + restart audit + soln2ck + GUI-sweep confirmation

Batch requested by the user: fix the adjacent RMG/DRG quick wins (B10, M15), the whole
review_plan Phase-3/4/5 robustness cluster (M16–M26), the soln2ck retry-mask defect, do
the restart/checkpoint audit (FUTURE-BUG-1..6), confirm the remaining GUI stress-test
plan, and update all docs. Explicitly out of scope: sens_3_params.py stress-testing.

## Code fixes (all with regression tests where a new test locus made sense)

- **B10** — `rmg_interface.load_rmg_output` called a nonexistent
  `MechanismParser.parse_and_store(mechanism_path=…)` and constructed the parser from a
  bare db-path string. Now `MechanismParser(RMIPConfig(db_path=…)).parse(mech_path=…)`.
  `cli._cmd_complete` was rewritten to the real `RMGInterface` API
  (`generate()` returns an output dir → `load_rmg_output()` for the DB id →
  `find_missing_pathways()` → `append_to_mechanism()`), including the correct
  `MissingPathwaysReport` attributes. Test: `test_rmg_load_b10.py` (separate + embedded thermo).
- **M15** — DRG `_reduce_at_epsilon` kept a reaction on ANY retained participant
  (`retained.intersection(sp_set)`); now Lu-Law-correct (`sp_set and sp_set <= retained`).
  Test: `test_drg_lu_law_m15.py` (incl. the empty-species corner + the M15 invariant).
- **M16** — cli jsr/pfr/flux now `return 0 if converged else 1`; `main()` wraps the
  handler dispatch (clean error → exit 1, 130 on Ctrl-C, None→0).
- **M17** — the two `mechanisms` format-widen DDLs + the `reduction_runs` rebuild now run
  inside `BEGIN…COMMIT` (atomic; FK pragma stays outside the txn). The reduction_runs
  idempotency check now reads `sqlite_master.sql` instead of a `mechanism_id=0` probe
  INSERT that tripped the FK and forced a needless rebuild every startup. Smoke-verified:
  no spurious "Widening…" on a second migration pass.
- **M18b** — new `simulation/subprocess_util.py`: `sanitized_subprocess_env()` strips
  foreign (ANSYS/Fluent/MATLAB) `LD_LIBRARY_PATH` entries; `resolve_timeout()` +
  `DEFAULT_SUBPROCESS_TIMEOUT_S=1800`. Wired into `zerork_bridge` (run_idt/run_jsr),
  `zerork_gsa` (GSA MPI + `_salib_call`), and `muqsac_bridge.run`.
- **M19** — crosscheck PRS-fit gate now requires `ceil((n_coeff+1)/0.9)` converged rows
  (`n_coeff = 1+2p+C(p,2)`, p = design-matrix width) instead of the old blanket `< 4`;
  `_salib_call` deletes stale response JSON first and errors if rc=0 wrote nothing.
- **M20** — Cantera CHEMKIN/CTI→YAML conversions write a temp file + `os.replace` on
  success (no more truncated-YAML-cached-forever); cache key now includes
  `cantera.__version__` and the requested thermo arg. Smoke-verified end-to-end.
- **M21** — jsr/pfr runners delete stale `output/*_full.json` before running and, on
  rc≠0, return an explicit non-converged result rather than parsing disk.
- **M22** — MUQ-SAC `run_script.py`/`data_management.py` use
  `_PY = os.environ.get("MUQSAC_PYTHON","python3.9")`; the two SA-tool subprocesses raise
  on non-zero rc before `pickle.load`; a non-zero cantera exit skips the `tau.out` parse.
- **M23** — the silent order-≥3 truncation. `MUQ-SAC/ResponseSurface.evaluate_prs` (order-2
  only) and `Sensitivity_Analysis/ResponseSurface.evaluate` (buggy `.index()`/enumerate-slice
  for order≥3) rewritten to sum the exact `range(n)`-nested monomials `MatPolyFitTransform`
  builds, up to order 5. Test: `test_response_surface_order3_m23.py` proves
  `evaluate == fit-transform · coeff` for orders 2–5 on both files, incl. repeated-value rows.
- **M25** — `error_metrics.compute_errors_from_df` evaluates every stage on a COMMON valid
  mask, so chi-squared is comparable across stages.
- **M26** — `forward_uq.load_uncertainty_data` fingerprints the uncertainty inputs and
  only reuses `unsrt.pkl` when they match; `forward_uq_gui._poll_results` only accepts a
  results CSV with mtime ≥ run start.
- **soln2ck retry-mask** — `data_management.run_sim` Step 5 now branches on the case's
  solver via `_run_script_needs_soln2ck` (only CHEMKIN_PRO/zerork require the soln2ck_2.py
  line; cantera runs directly). Test: `test_soln2ck_retry_mask.py`.

## Restart/checkpoint audit (FUTURE-BUG-1..6) — CONFIRMED all already fixed

Read every cited location: sentinel at `<case_dir>/.done` from `optDir` (FB1), per-case
`try/finally os.chdir(optDir)` (FB2), restart iterating `p_design_matrix` (FB3), yaml
file-count verify + regen (FB4), `locations` dedupe (FB5), required-absolute
`progress_file` (FB6) — all present ("Bug 1/2/3/4/5 fix" / "Task 4A"). Additionally
hardened the nominal-run `locations` writers in BOTH the `MUQ-SAC` and `Sensitivity_Analysis`
`simulation_manager2_0.py` copies with the same dedupe. Noted (not changed, since it is in
the out-of-scope sens_3_params path): the Sens copy keeps a getcwd-derived `progress_file`
fallback rather than raising.

## GUI stress plan — confirmed already complete

`GUI_STRESS_TEST_PLAN.md` was already fully executed (committed `c88ccb3`):
`test_gui_stress_sweep.py` = 17 tests over all 8 launcher GUIs, all passing (~111 s),
B13 fixed, M24 covered. Docs updated to reflect this (the stale "5 of 7 un-swept" note
in `bug.md` was wrong).

## Verification

- `pytest src/rmip/tests/` minus the slow GUI sweep: **699 passed**.
- GUI sweep subset (brute_force_sa/nominal_sim/mso_compare/mean_value_fusion): 6 passed
  (148 s) — exercises the edited `Sensitivity_Analysis/simulation_manager2_0.py` end-to-end.
- New tests: `test_rmg_load_b10.py`, `test_drg_lu_law_m15.py`, `test_soln2ck_retry_mask.py`,
  `test_response_surface_order3_m23.py` — all green.

Docs updated: `bug.md` (resolved items removed / FUTURE-BUG table flipped to resolved /
soln2ck + GUI-sweep rows marked done), `BUG.md` (new "2026-07-19" resolved section),
`GUI_STRESS_TEST_PLAN.md` (COMPLETED banner).

## 2026-07-20 — Post-deep-review backlog sweep kicked off (5 workstreams, sequential)

Plan on disk: `/home/krithika/.claude-work/plans/bottom-line-the-cantera-chemkin-rmg-replicated-minsky.md`.
Working through, one at a time: (1) glossary GUI, (2) mechanism-check P7-P9 diagnostics,
(3) GUI hardening (pty_terminal.py + brute-force SA), (4) monolith→GUI capability gaps,
(5) GSA→MUQ-SAC prefilter wiring. Explicitly out of scope this round: Zero-RK
flame-speed/counterflow-extinction (needs a from-source SUNDIALS 5 build).

**Workstream 1 (glossary GUI) — DONE, no code needed.** `mechanism_converter_gui.py:344`
already had a "Species glossary CSV" file picker wired to `rmip_cli.py parse --glossary`
(`src/rmip/cli.py:205`) before this session started. `FEATURE_GAPS_FROM_MONOLITH.md`'s
"Mechanisms" tab section updated to reflect this — the narrower gap that remains is the
monolith's *batch* multi-mechanism row-builder workflow, not single-mechanism
glossary-attach (which now works). Populating actual glossary data is the user's own task.

**Workstream 3 (GUI hardening: pty_terminal.py + brute-force SA) — DONE 2026-07-20.**
Two independent fixes, both with regression tests, neither committed:

- `src/gui_common/pty_terminal.py` (M27, `bug.md`): fixed all 4 sub-bugs in the one
  shared widget that all 5 terminal-backed GUI apps import — fd+zombie leak in `stop()`
  (SIGTERM → bounded `waitpid` poll → SIGKILL escalation → final blocking `waitpid`,
  always close `self._fd`), the reader-thread restart race (monotonic `self._gen`
  counter passed explicitly into `_read_loop(gen, fd)`, checked both before `os.read()`
  and before `self._stream.feed()`), no scrollback (`pyte.HistoryScreen(history=2000,
  ratio=0.5)` + Page Up/Down/mouse-wheel bindings calling the newly-factored-out
  `_refresh_once()`), and no close guard (`<Destroy>` bound in `__init__`, guarded by
  `event.widget is self`). Tests: `src/rmip/tests/test_pty_terminal.py`, 4/4 passing.
- `src/Sensitivity_Analysis/simulation_manager2_0.py::run_map`'s silent
  `mechanism.yaml` write failure (the brute-force SA `IndexError`, `bug.md` — see
  "Follow-up 2026-07-20" note above): added `_write_mechanism_yaml_verified()`,
  scoped strictly to `run_map`'s one `yamlwriter.dump_to_yaml` call site
  (verify → retry ×3 → pure-Python `yaml.dump` fallback → clear `RuntimeError` if both
  fail). Confirmed the suspected root cause by reading
  `config_tools/converters_io/YAML_WRITER/yamlwriter.cpp` (untouched, read-only): a
  bare `std::ofstream` with no `is_open()`/`fail()` check and no exceptions enabled —
  a failed open/write silently no-ops by C++ default. Tests:
  `src/rmip/tests/test_simulation_manager_yaml_write.py`, 3/3 passing. Full suite
  (`python -m pytest src/rmip/tests/ -q`) re-run clean after both fixes.

## 2026-07-20 — Phase 3 of monolith-gap closure: target builder, autosave, ReSpecTh
## tab, multi-condition reduction (4 parts, all done, uncommitted)

Closes 4 of the 10 ranked candidates in `FEATURE_GAPS_FROM_MONOLITH.md` (updated inline
there with per-item detail). Read `rmip_suite_gui.py` in full first to match its existing
`_TerminalTab` base-class pattern before adding tabs, per this phase's ground rule.

**Part A — `.target`/`.add` builder (ranked #1), scoped to JSR/PFR only.** New
`rmip build-target` CLI subcommand (`src/rmip/cli.py::_add_build_target_cmd`/
`_cmd_build_target`, registered in `main()` right after `import-respecth`) wraps
`MuqsacBridge.build_target_files()` — its own argparse args were derived from that
method's actual signature (mech_id/db/base-target-opt/target-type/solver/fuel/oxidizer/
T/P/phi/work-dir/dataset-id/species/residence-time/max-sim-time/pfr-*/flux flags), not
copied verbatim from `import-respecth`'s shape (that command's dry-run-only nature meant
`--run-script`/`--timeout`/`--dry-run` weren't relevant here). New GUI tab
`TargetBuilderTab` in `rmip_suite_gui.py`: JSR/PFR-only type dropdown, a fuel-blend
Treeview row editor (species + mole fraction, idiom copied from
`uncertainty_generator_gui.py`'s reaction-row editor), and dynamic extra fields keyed off
`gui_common.target_types.TARGET_TYPE_FIELDS[type]`, each mapped to the real CLI flag it
feeds. Verified end-to-end against the `gui_stress` fixture DB + `target.opt` — produces
a valid pipe-delimited `.target` line and `.add` YAML block.

**Part B — autosave wiring (ranked #3).** `AutoSaveManager` wired into exactly 4 places:
`uncertainty_generator_gui.py` (existing `_add_gen_row`/`_remove_gen_row` callbacks),
`mean_value_fusion_gui.py` (traced persisted StringVars/BooleanVars — no repeatable row
editor exists there), and `rmip_suite_gui.py`'s two new row editors (`TargetBuilderTab`'s
fuel blend, `ReductionTab`'s multi-condition rows), which share ONE
`AutoSaveManager`/checkpoint file at the `RMIPSuiteApp` level since they're one app.
Own checkpoint file per app under `.gui_settings/`, per `autosave.py`'s own docstring.
Every other GUI app deliberately left unwired (already covered by settings.py's
last-path persistence) — not an oversight.

**Part C — ReSpecTh/RKD XML importer GUI tab (ranked #4).** No core/CLI change — `rmip
import-respecth` already existed and was already tested. New `ReSpecThImportTab` in
`rmip_suite_gui.py` is a pure form front-end wrapping it (XML file/dir picker, `--fuel`,
`--solver` dropdown, `--out-dir`, `--dataset-prefix`, `--no-db` checkbox).

**Part D — multi-condition reduction, core+CLI+GUI (ranked #5), orchestration only.**
New `src/rmip/reduction/multi_condition.py::reduce_multi_condition()` dispatches to the
same DRG/DRGEP/PFA/DRGPSA/DRGSA reducer classes `_cmd_reduce` already maps `--method` to,
runs each condition with `save_db=False`, and unions retained species/reactions per
matching ε index (removed = intersection of the per-condition removed sets — valid since
all conditions share one mechanism-wide universe). Persists ONE `reduction_runs` row via
the reducer's own `_insert_run()`, plus a new `reduction_multi_condition_runs` table
(`src/rmip/database/migrations.py::run_multi_condition_migrations`) linking back to the
JSON condition list. CLI: repeatable `--condition T_K,P_atm,phi,fuel` added to `rmip
reduce`; the existing no-`--condition` branch was preserved as-is (only re-indented into
an `else:`, zero statement changes) specifically so its behaviour couldn't drift — locked
in by a CLI test asserting its stdout/JSON shape. GUI: `ReductionTab` gained a repeatable
condition Treeview (same row-editor idiom as Part A) plus the `--mech-path` file picker
it was missing entirely. **Not done, and explicitly out of scope**: the monolith's
separate 3D diverse-subset farthest-point-sampling confirm/redo dialog — that's a
different feature (picking which conditions to run against) and remains open.

**Tests, all green:**
- `src/rmip/tests/test_multi_condition_reduction.py` (new, 4 tests) — built a real
  Cantera-loadable fixture (`h2o2.yaml` parsed into a temp DB) since the union needs
  genuinely condition-dependent DRG rates to exercise real divergence (empirically found:
  T=900K/P=1atm/phi=0.5 vs. T=2000K/P=10atm/phi=2.0 diverge on H2O2 retention for eps in
  [0.5, 0.7] at eps-step 0.05). Confirms exact set equality (not just superset) of the
  union vs. two direct `.reduce()` calls at every eps; confirms the degenerate
  single-condition case is byte-identical to calling `.reduce()` directly; confirms
  `save_db=True` inserts exactly one `reduction_runs` row + one linked
  `reduction_multi_condition_runs` row.
- `src/rmip/tests/test_phase5b.py::TestReduceCLI` (+5 tests) — multi-condition CLI
  invocation, malformed `--condition` returns exit 1, legacy no-`--condition` path
  explicitly asserted unchanged (stdout shape + JSON shape), DB-save inserts both tables.
- `src/rmip/tests/test_gui_stress_sweep.py` (+7 tests) — `ReductionTab`'s multi-condition
  Treeview path in-process (populate `_cond_rows`/StringVars directly, no synthetic Tk
  clicks, matching this file's existing convention) run end-to-end against the mech_A
  fixture; empty-tree case asserted to emit no `--condition` flags at all;
  `TargetBuilderTab`/`ReSpecThImportTab` `_build_command()` argv-shape tests.
- `tests/test_gui_common.py` (+10 tests) — autosave wiring smoke tests for all 4 places:
  mark-dirty via the real row-add callback → force-flush (`_do_save()`, bypassing the
  timer) → checkpoint file written; `on_close()` → final flush. Checkpoint paths
  monkeypatched per-test (mirrors how `gui_common.settings._SETTINGS_DIR` is already
  monkeypatched in this file) so tests never touch the real repo's `.gui_settings/`.

**Full-suite verification:** `src/rmip/tests/` — 931 passed, 0 failed (no regressions).
Repo-root `tests/` — 94 passed, 1 pre-existing failure (`test_launcher_gui.py::
TestAppRegistry::test_eight_apps_listed`, confirmed via `git stash` to already fail
before this phase's changes — `launcher_gui.py` already had 2 more apps registered
from earlier uncommitted work than the test's hardcoded count expects; unrelated to
this phase, not touched).

Docs updated: `FEATURE_GAPS_FROM_MONOLITH.md`'s ranked-candidates #1/#3/#4/#5 each got an
inline "Update 2026-07-20" note naming the concrete new files/classes/functions and what
remains explicitly out of scope. Nothing committed to git — left in the working tree per
this phase's instructions.

## 2026-07-21 — Phase 4 follow-on: GSA reaction-prefilter wired into MUQ-SAC, opt-in

Wired `ZERORK_GSA_PLAN.md` Phase 4's previously-deferred item: use an `rmip gsa-run`
screening result as a pre-filter on which reactions' parameters enter
`src/MUQ-SAC/run_script.py`'s PRS training design, before any expensive simulation runs.
Hard constraint honored throughout: strictly opt-in (default OFF), provably a no-op when
not configured, benchmarked automatically at the `DesignMatrix` level (no licensed
Chemkin-Pro/FlameMaster or compiled `samap`/`jpdap` in this environment — a literal
end-to-end `run_script.py` run stays a documented manual step).

**New module** `src/rmip/simulation/gsa_reaction_prefilter.py`: `ReactionIdMaps` +
`build_reaction_id_maps(db_path=None, mechanism_id=None, mechanism_path=None)`
(generalizes `gsa_prs_crosscheck.py`'s DB-query proof-of-concept; DB mode mirrors its
exact query, file mode loads a Cantera `Solution` directly since production
`run_script.py` has no rmip DB); `select_gsa_important_reactions(gsa_result_path,
metric="ST", threshold=0.01, top_n=None)` (parses an `rmip gsa-run` JSON output, strips
the `R<n>:` label prefix, threshold/top_n mutually exclusive — both given raises);
`apply_gsa_prefilter(unsrt_data, prefilter_cfg)` — the opt-in seam, returns `unsrt_data`
unchanged (same object) whenever `prefilter_cfg` is falsy/empty or `enabled: false`,
raises `ValueError` only on a genuine zero-overlap key-format mismatch (a threshold that
legitimately excludes everything returns an empty dict, not an error).

**`run_script.py`**: new module-scope `_maybe_apply_gsa_prefilter(optInputs, unsrt_data)`,
defined before the argv-parsing block, called right after `unsrt_data` is loaded/
unpickled. Purely additive — zero existing statements touched. This file has no
`if __name__ == "__main__":` guard (pre-existing, zero-test-coverage structure, not
touched); to unit-test the new function without executing the rest of the script,
`test_gsa_reaction_prefilter.py` extracts its exact source via `ast.parse` +
`ast.get_source_segment` and execs it in isolation — avoids any restructuring risk to
1000+ lines of untested production code while still genuinely exercising the shipped
function body. New optional `target.opt` schema block documented in
`ZERORK_GSA_PLAN.md`'s Phase 4 section (`GSA_Prefilter: {enabled, gsa_result_json,
metric, threshold|top_n}`); grepped every `target.opt`/target-shaped file in the repo —
zero existing hits, confirming the wiring is a no-op for every config that exists today.

**`DesignMatrix.py`**: one additive, non-behavior-changing line in `__init__`,
`self.n_reactions_in_design = len(UnsrtData)` — confirmed by reading the whole file that
every reaction-list derivation already flows from `self.unsrt`, so no other change was
needed.

**Tests**: new `src/rmip/tests/test_gsa_reaction_prefilter.py`, 23 tests — module unit
tests (no-op identity incl. `enabled: false`, threshold/top_n filtering incl. the
top_n-alone mutual-exclusion regression guard, key-mismatch `ValueError` vs.
threshold-too-high empty-dict distinction, S1/ST/mu_star metric parsing, `build_
reaction_id_maps` DB-mode vs. file-mode equivalence against the `gui_stress` fixture's
`mech_std.yaml`); the `run_script.py` ast-extraction no-op tests (identity + `rmip`
import never triggered, checked by forcibly clearing `sys.modules` first so an earlier
test's legitimate import can't mask a false pass); and a `DesignMatrix`-level benchmark
using `gsa_prs_crosscheck.py`'s real `build_unsrt_subset()` + the real 3-reaction H2/O2
fixture against a freshly-exported real GRI-3.0 (`mechanism_id=8`, `outputs/project.db`)
mechanism — confirms the disabled path is bit-for-bit identical to never touching the
prefilter, and that enabling it with the REAL S1 values from `ZERORK_GSA_PLAN.md`'s
Phase 4 cross-check (`H+O2<=>O+OH` 0.9992 dominant; `O+H2<=>H+OH` 0.0002; `OH+H2<=>H+H2O`
0.0006, threshold 0.01) retains exactly the dominant reaction. One honest finding written
into that test's docstring rather than glossed over: `qmc_sampling.joint_uniform_block`'s
joint sampling ties every reaction's column to the same shared Sobol draw stream, so the
surviving reaction's own sampled values necessarily differ (not just the dropped columns)
between the filtered and unfiltered design matrices — verified this empirically before
asserting anything, and the test asserts what's actually true (count/identity/shape/
determinism) rather than a false bit-identical-column claim.

**Full-suite verification:** `src/rmip/tests/` — 954 passed, 0 failed (931 pre-existing +
23 new, zero regressions).

Nothing committed to git — left in the working tree per this phase's instructions.
