# Legacy Planning Archive

Consolidated 2026-07-22 from 9 superseded/completed planning + scratch files
into this single file (pure consolidation, no content dropped). Each section is
one original file, verbatim. Current status per section header.

---

## RESUME.md (2026-07-12 handoff — superseded by root PLAN.md/progress.md; detail already distilled into MarkDownFiles/HISTORY.md parts 20-34)

# RESUME — single handoff file

Written: 2026-07-12, updated 2026-07-12 (JSR zerork wiring §2a landed; Zero-RK GSA §2b Phase 3
landed standalone — see item 8 below; `stubs.FusionEngine` (M7) + `stubs.DoEFramework`
`run_screening()`/`prepare_mso_input()` (M9) implemented — see item 9 below; a real
pre-existing `ChemkinWriter` bug found and fixed along the way; the GUI-separation planning
exercise KP tagged for `/model opusplan` is DONE — see item 10 below — **and all 7 apps in that
plan are now built, Phases 1-6 complete**, see §2f and
`MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md`; **Zero-RK GSA §2b's
validation cross-check is now also done — see item 11 below — and it found+fixed a real
previously-undiscovered off-by-one bug in `ZerorkGSARunner._parse_gsa_output` that had silently
corrupted every GSA index this module ever computed until now**). Read this file first in
a new session — it supersedes scattered notes in
`MarkDownFiles/progress.md` / `MarkDownFiles/ZERORK_GSA_PLAN.md` / `MarkDownFiles/PLAN.md` for
"what to do next." Those files still have the full historical detail if you need it; this file is
just the current status + prioritized remaining work in one place.

Original task (still the umbrella goal, from `prompt.txt`): finish Zero-RK integration into the
combustion-target simulation pipeline, keep `src/MUQ-SAC/` in sync with the parallel working copy
at `~/mechanism-optimization-suite`, and plan+build (now both done — see item 10 and §2f) a
GUI-separation refactor of `generate_target_opt.py`.

---

## 0. Sanity check before doing anything

```bash
cd /data/MECHANISM_OPTIMIZATION_SUITE
git log --oneline -10          # should show dd186fd at HEAD (or later)
python3 -m pytest src/rmip/tests/ tests/ -q   # expect 481 passed (398 rmip + 83 top-level tests/)
```

If HEAD isn't `dd186fd` or later, or tests don't pass, something changed outside this handoff —
investigate before trusting anything below.

---

## 1. What's done (commits `92d8f80`..`dd186fd`, all on `master`, all committed)

1. **Zero-RK Phase 0** (`3238fe4`) — Zero-RK built at `/home/krithika/zero-rk/build2/inst_dir`,
   validated against Cantera (0.00004% agreement on GRI-3.0 IDT).
2. **Zero-RK Phase 1** (`10c77d2`) — `src/rmip/simulation/zerork_bridge.py` (`ZerorkBridge` class:
   IDT via `constVolumeWSR`, JSR via `constVolumePSR`). Getting this working end-to-end surfaced
   and fixed **six real bugs** in `src/rmip/io/_chemkin_parser.py` / `chemkin_writer.py` — not
   Zero-RK-specific, silently wrong for any strict consumer:
   - NASA-7 thermo line-1 field widths wrong (26 cols instead of CHEMKIN-standard 24).
   - A Lindemann-only (LOW, no TROE) falloff reaction was never tagged `kinetics_type="lindemann"`
     — silently downgraded to `"third_body"`, losing its pressure-dependence entirely.
   - `chemkin_writer.py` read `kinetics_data_json` with key names that never matched what the
     parser writes (`low_rate` vs `low`, `troe_params` vs top-level, `plog_rates` vs
     `pressures`+`arrhenius`) — every falloff/PLOG/Chebyshev reaction in every mechanism has been
     silently exported without its pressure-dependence data, this whole codebase's lifetime.
   - GRI-3.0-wetCO's `REACTIONS MOLES KELVINS` header was never detected — every Ea was read as
     cal/mol instead of Kelvin (off by a factor of R ≈ 1.987).
   - **`species.formula` was never populated by the parser at all** — every mechanism's ELEMENTS
     block and per-species THERMO elemental columns were silently blank/wrong. This was the
     dominant root cause of a universal NaN-at-t=0 Zero-RK solver failure (Zero-RK computes
     molecular weight from declared elements, not name lookup).
   - Element-symbol case mismatch between the ELEMENTS block (`AR`) and per-species formula field
     (`Ar`) — Zero-RK's parser is case-sensitive.
   Verified: IDT on GRI-3.0 matches Phase 0's reference to 0.05%; IDT on Davis-2005 (different Ea
   units path) converges; JSR on GRI-3.0 converges.
3. **Docs for #2** (`9d1226b`, `dd186fd`).
4. **`outputs/project.db` re-parsed** — mechanisms 8-11 are GRI-3.0/Davis-2005/Keromenes-2013/
   Li-2015 re-parsed with the fixed parser. **1-4 were deliberately left in place, now stale** (see
   §3 table below). Backup of the pre-re-parse DB: `outputs/project.db.bak-pre-zerork-reparse-20260712`.
5. **`src/MUQ-SAC/` reconciled against `~/mechanism-optimization-suite`** (`6f21092`) — per KP's
   explicit instruction, **scoped to `src/MUQ-SAC/` only, everything else in that other repo was
   deliberately ignored** (KP's words: "rest you can ignore" — the merge task is done, don't
   re-open it). Compared all 7 differing files by function/class inventory, not just line diffs.
   Pulled in `AdaptiveResampler.py` (new `resample_hybrid`/`resample_gap_fill`/`_isolation_filter`)
   and `run_script.py` (matching new `outlier_cfg` options + fingerprint-validated sim-cache reuse)
   wholesale from the other copy, but re-applied a "Bug 4 fix" (`Perturbed_Mech` directory-
   completeness check) that the other copy had dropped. `combustion_target_class.py`,
   `make_input_file.py`, `partial_PRS_system.py`, `simulation_manager2_0.py`, `data_management.py`
   were confirmed to have no missing functions relative to the other copy — this repo was already
   ahead there, nothing pulled.
6. **Zero-RK wired into `make_input_file.py` as `solver="zerork"` for Tig (IDT) targets**
   (`6056ec4`, `76dc937`).
   `combustion_target_class.py` now defaults all `zerork_*` params (the only place they're
   defaulted, per KP's explicit requirement — `make_input_file.py` reads `target.add[...]`
   exclusively, never hardcodes). `data_management.py` got an explicit `"zerork"` result-parsing
   branch (without it, zerork's `tau.out` would have silently fallen into a bare `else:` tuned for
   FlameMaster's different file layout and returned a bogus fallback IDT — a correctness bug I
   caught, not a hypothetical). Verified end-to-end: real `create_input_file()` call → generated
   script → real Zero-RK binary run → `output/tau.out` = 8065.80 μs vs. the 8061.9 μs Phase-0
   reference (0.05%, same tolerance as the direct bridge test).
7. **Zero-RK wired into `make_input_file.py` as `solver="zerork"` for JSR targets too**
   (commit `d24fbcf`) — same pattern as #6: an `elif "zerork" in solver:` branch in the JSR
   section of `create_input_file()` driving `constVolumePSR.x` directly (fuel/oxidizer
   stream-ratio reconstruction copied verbatim from the Tig branch, per this file's own earlier
   advice), a matching explicit `"zerork"` branch in `data_management.py`'s JSR result parser, and
   a new `zerork_jsr_preconditioner_threshold` default (`1.0e-6`) in `combustion_target_class.py`
   — deliberately separate from Tig's `zerork_preconditioner_threshold` (`2.048e-3`) because
   Zero-RK's own WSR vs. PSR example decks tune this value differently per reactor type; reusing
   the Tig value would have been wrong, not just untuned. Verified end-to-end against the real
   `constVolumePSR.x` binary on GRI-3.0 (mechanism_id 8): `converged: true`,
   `residence_time_s: 0.5` round-tripped correctly, H2 exit mole fraction `0.0255` parsed
   correctly by both `output/jsr_full.json` and `data_management.py`'s new branch.
   **`src/rmip/tests/` fully passes — nothing there covers this MUQ-SAC-side wiring directly,
   `py_compile` + the manual end-to-end run were the only verification.**
8. **Zero-RK GSA (Phase 3 of `ZERORK_GSA_PLAN.md`) implemented, standalone** — new
   `rmip/simulation/zerork_gsa.py` (`ZerorkGSARunner`): real Sobol/Morris sensitivity indices over
   a mechanism's reaction A-factors, via SALib sampling + Zero-RK's `perturbAFactorGSA_mpi.x` MPI
   batch execution + SALib index computation. New CLI: `rmip gsa-run` (use via the repo-root
   `rmip_cli.py` launcher, not `python3 src/rmip/cli.py` directly — see §4's `io`-shadowing note).
   New DB tables (`sensitivity_runs`/`sobol_indices`/`design_matrices`, mirroring `reduction_runs`)
   and `types.py` dataclasses (`GSARunConfig`, `SobolResult`). New tests:
   `src/rmip/tests/test_zerork_gsa.py` (16 tests, all passing, folded into the 371-test suite).
   **Scope decision** (confirmed with KP): standalone on a single `mechanism_id`, not wired into
   `stubs.py`'s `DoEFramework.run_screening()` — that interface needs a merged mechanism from
   `FusionEngine` (M7), which is itself an unimplemented stub. `SobolResult.to_screening_dict()`
   already matches `run_screening()`'s documented return shape for that future hookup. Full
   details, including a real environment-breaking incident (installing SALib into the shared
   anaconda env upgraded numpy 1.24→2.0 and broke scikit-learn — reverted, then fixed properly by
   isolating SALib in a dedicated venv, `/home/krithika/.venvs/salib_gsa`, talked to only via
   subprocess+JSON) are in `ZERORK_GSA_PLAN.md`'s Phase 3 section — read it before touching SALib
   or the GSA engine again.
9. **`rmip.stubs.FusionEngine` (M7) and `rmip.stubs.DoEFramework.run_screening()`/
   `prepare_mso_input()` (M9) implemented** (uncommitted as of this RESUME.md edit — check
   `git status`). `FusionEngine` is a thin adapter over the already-implemented, already-tested
   `rmip.analysis.fusion.FusionEngine` (different class, same name, different module — it
   reconstructs a `GraphComparisonResult` from `UnionGraphSpec`'s 3 bucket dicts, losslessly,
   delegates the actual DB-row fusion to the core engine, applies `fuse_overrides` as a post-insert
   UPDATE, then adds CHEMKIN `.inp`/`.dat` writing via `ChemkinWriter` and optional Cantera YAML via
   `ck2yaml` — neither of which the core engine did). Also implements
   `validate_element_balance()` (parses `species.formula`, weights by `stoichiometry`, no prior
   implementation existed anywhere in the repo). `DoEFramework.run_screening()`/
   `prepare_mso_input()` now for real: build a fused mechanism via `FusionEngine`, screen its
   FUSE-bucket reactions via `ZerorkGSARunner` (item 8), remap "label:formula"-keyed results back
   to `canonical_key` (positional zip against the `reaction_ids` list passed to
   `GSARunConfig` — the one place a subtle bug could hide, tested explicitly), apply the
   documented `|S1|`/`|mu_star| < 0.01` MSO cutoff. New tests: `test_stubs_fusion.py` (9 tests),
   `test_stubs_doe.py` (10 tests) — 390 total now passing.
   - **Found and fixed a real, pre-existing `ChemkinWriter` bug along the way**: `write()`
     unconditionally appended a second `"END\n"` after `_write_reactions()`'s own terminating
     `["END", ""]` — a duplicate terminator every CHEMKIN file this writer ever produced had.
     Cantera's own `ck2yaml` rejects it outright (`"Section starts with unrecognized keyword"`);
     Zero-RK's parser and this repo's own prior tests silently tolerated the extra trailing
     content, so it was never caught until `FusionEngine.fuse(write_cantera=True)` actually piped
     writer output through `ck2yaml` for the first time. Fixed by deleting the redundant
     top-level `lines.append("END\n")` in `chemkin_writer.py`'s `write()`. Verified this doesn't
     regress Zero-RK (`IDTResult.idt_s` unchanged, matches Phase 1's reference exactly).
   - **Scope note, unrelated to this fix**: every mechanism currently in `outputs/project.db`
     (both `chemkin`- and `cantera_yaml`-parsed) has `species.inchi_key`/`reactions.canonical_key`
     entirely NULL (`glossary_matched=0` everywhere) — `GraphComparator.compare()` matches by
     inchi_key/canonical_key (D1/D2), so it produces an *empty* comparison on any real mechanism
     in this DB today. This is a pre-existing, separate data-pipeline gap (the name→SMILES→InChI
     glossary-matching step in `core/parser.py` was never exercised with a glossary covering these
     species names at parse time) — not a defect in `FusionEngine`/`GraphComparator` themselves.
     `test_stubs_fusion.py`/`test_stubs_doe.py` build glossary-resolved fixture data by hand
     instead (same pattern `test_phase3.py::TestFusionEngine` already uses, for the same reason).
     If real-mechanism fusion is ever needed, populating a real glossary file for common species
     (H2/O2/H2O/etc.) and re-parsing with `--glossary` is the prerequisite — separate task, not
     attempted here.
10. **GUI-separation + broader-improvement planning exercise done** — KP's original `prompt.txt`
    line 5 explicitly invoked `/model opusplan` for this; done properly via Plan Mode (2 Explore
    passes over the live `generate_target_opt.py` + backend modules, 4 clarifying `AskUserQuestion`
    rounds with KP, not assumed from memory). Full plan:
    `MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md`. Summary: split the
    6080-line, 12-tab `generate_target_opt.py` monolith into **7 standalone GUI apps** (Forward UQ,
    Brute-Force SA, Nominal Simulation, MSO Compare, RMIP Suite [umbrella: graph/comparison,
    Mechanism Reduction, Global Sens Analysis, Active Parameter Selection], Mean Value/Fusion
    Generator, Uncertainty Generator), each a thin Tk form over an already-existing, already-working
    CLI/library backend, sharing a new `src/gui_common/` package (theme/PtyTerminal/autosave/
    fuel-data/target-types) extracted from the monolith. Phased build order: pilot on Brute-Force SA
    first (Phase 1), then Forward UQ + Nominal Sim (Phase 2), then MSO Compare + Fusion Generator
    (Phase 3), then RMIP Suite (Phase 4, biggest lift), then Uncertainty Generator (Phase 5, needs a
    new symmetric-max-bound formula confirmed with KP first), then an optional launcher (Phase 6).
    Also produced 8 ranked "what else can be improved" findings (glossary-matching gap is the
    highest-leverage one — it silently blocks `FusionEngine`/`GraphComparator`/`unify-*` on every
    real mechanism in the DB today). **Nothing in Part 1's 7 apps has been built yet** — this item
    is the planning deliverable only; §2f below is the prioritized next-build-step list.
11. **Zero-RK GSA Phase 4 validation cross-check implemented** (2026-07-12) — new
    `src/rmip/simulation/gsa_prs_crosscheck.py` (7 tests, `test_gsa_prs_crosscheck.py`): compares
    `ZerorkGSARunner`'s direct-simulation Sobol indices against `AnalyticalSobolPRS`'s
    PRS-surrogate Sobol indices for the same 3 real H2/O2 reactions on GRI-3.0 (`mechanism_id=8`),
    per `ZERORK_GSA_PLAN.md` Phase 4's open question #4 ("worth doing first" before trusting Phase
    3's indices as a training-set prefilter). **Scope, confirmed with KP: validation only** — does
    NOT wire a prefilter into `src/MUQ-SAC/run_script.py`/`DesignMatrix.py` (real production code
    with zero automated test coverage); that remains explicitly not-started, a separate follow-up
    — see §2b. New fixture `src/rmip/tests/fixtures/h2_o2_crosscheck_unsrt.xml` (the shipped
    `DATASET/H2_O2_TEST/uncertainty/H2_uncertainty.xml` is missing `no=`/`<perturbation_type>`/has
    blank `<class>`, which crashes or silently no-ops `Uncertainty.py`/`MechManipulator2_0.py` —
    same family of bug as the uncertainty-XML-writer bug found in item 9/Phase 5 above, just in a
    different fixture this time). At real settings (40 PRS-training points, 512 direct-Sobol base
    samples): **verdict AGREE**, all 3 reactions' `S1_prs`/`S1_direct` within 0.0001-0.0002.
    **Found and fixed a real, previously-undiscovered off-by-one bug in
    `ZerorkGSARunner._parse_gsa_output`** along the way (see `ZERORK_GSA_PLAN.md` open question #4
    for the full root-cause writeup) — `perturbAFactorGSA_mpi.x` always writes an unperturbed
    baseline as `task_id=0` before the sample loop, then writes matrix row `j` as `task_id=j+1`;
    the parser read `task_id` directly as the row index, silently misaligning every sample's
    simulated IDT with the wrong row of the SALib sample matrix for **every Sobol/Morris GSA run
    this module has ever performed** — the `rmip gsa-run` CLI, `DoEFramework.run_screening()`/
    `prepare_mso_input()`, and the RMIP Suite GUI's GSA tab were all silently computing
    statistically-corrupted indices until this fix. Existing `test_parse_gsa_output_*` unit tests
    updated to the real baseline+offset output format, plus a new regression test. Combined suite
    (`tests/` + `src/rmip/tests/`) is now 481 passing.

---

## 2. What's NOT done — prioritized

### 2a. ~~JSR → `make_input_file.py`~~ — ✅ DONE (2026-07-12, commit `d24fbcf`)
See item 7 in §1 above.

### 2a'. ~~Zero-RK GSA core engine~~ — ✅ DONE standalone (2026-07-12, commit `6bc0ddb`)
See item 8 in §1 above.

### 2a''. ~~FusionEngine (M7) + DoEFramework (M9) wiring~~ — ✅ DONE (2026-07-12, commit `a1afd99`)
See item 9 in §1 above. **Remaining, not done in `stubs.py`:** `PathwayCompleter` (M5, needs RMG-Py),
`UQFusion` (M13, needs KP's MUQ-SAC covariance adapter — CLAUDE.md §11), `AIRecommender` (M10),
`ChangeLog` (M11), `ReportEngine` (M12) — none of these were on the path toward the GUI plan, so
none were attempted this session; see `stubs.py` itself for their still-accurate docstrings/stubs.

### 2b. Zero-RK GSA Phases 4-5 (`MarkDownFiles/ZERORK_GSA_PLAN.md`) — remaining piece
Phase 3 (the core SALib+Zero-RK engine) is done — see item 8/§2a' above. **The validation
sub-step is now done too** — see item 11 in §1 above: `src/rmip/simulation/gsa_prs_crosscheck.py`,
verdict AGREE on real GRI-3.0 data, and it surfaced+fixed a real off-by-one bug in
`ZerorkGSARunner._parse_gsa_output` that had been silently corrupting every GSA run's indices.
**Still NOT started: the actual prefilter wiring itself** — use `ZerorkGSARunner`'s (now-validated)
screening indices, or TLA's cheap per-reaction local sensitivities, as a pre-filter on which
reactions' parameters go into `DesignMatrix.py`'s design before `MUQ-SAC/run_script.py`'s PRS
training runs. **Confirmed with KP how this should be scoped when it's eventually built:** hook
into the existing `PRS_type == "Partial"` brute-force-SA plumbing (the only place a "restrict to N
reactions" concept already exists end-to-end in `run_script.py` — see the correlation_analysis/
`SA_tool` step around its PRS_type=="Partial" branch), as an opt-in alternative selection method,
**not** a replacement — the existing brute-force local-SA behavior must remain the default when
GSA screening isn't requested. Also still not done: **Phase 5**'s GUI polish item (a `solver`
dropdown offering "Zero-RK" on the Brute-Force SA app's Run-SA panel) — note the other half of
Phase 5 (a GSA panel via the embedded `PtyTerminal` pattern) is already satisfied by
`rmip_suite_gui.py`'s existing Global Sensitivity Analysis tab (§2f Phase 4), built before this
GSA-Phase-4/5 item was revisited — don't re-build that.

Real reaction-ID-mapping gap to solve when the prefilter is eventually built: `ZerorkGSARunner`
(rmip DB id / `canonical_key` / `"label:formula"`) and `MUQ-SAC`'s `Uncertainty`/`DesignMatrix`
(Chemkin-file-order `"R1093"`-style keys from the uncertainty XML's `no=` attribute) use completely
separate ID schemes with no existing bridge — `gsa_prs_crosscheck.py` sidesteps this by building
its own small mapping by hand (matching on `formula_string`/equation text) for its 3-reaction case;
a real prefilter over a whole mechanism's reactions will need a proper, tested mapping layer, not
just a similar one-off.

### 2c. "All kinds of targets" — re-scope with KP before attempting
KP's original ask (`prompt.txt`) mentioned soot predictions, counterflow burner, extinction strain
rate, etc. **Zero-RK has no flame/PFR reactor at all** (confirmed in Phase 0/1 research, permanent
gap) — those targets must stay on cantera/CHEMKIN_PRO/FlameMaster regardless of `solver=`. Don't
attempt to add zerork branches for `Flf`/`Flf_a`/`PFR`/`Flw`/`RCM` targets; there's no Zero-RK
capability behind them. If KP still wants those simulation *types* to gain some other capability
(e.g. soot in CHEMKIN_PRO), that's a separate, non-Zero-RK task — ask before scoping.

### 2d. ~~GUI-separation planning exercise~~ — ✅ DONE (2026-07-12)
See item 10 in §1 above. The plan itself is complete and approved by KP; **building it is a
separate, not-yet-started piece of work** — see 2f.

### 2f. Build the GUI split (per the approved plan) — Phase 1 ✅ DONE (2026-07-12)
`MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md`'s §1.7 Phase 1: shared
`src/gui_common/` package + the Brute-Force SA pilot app, both built and tested this session.
- **`src/gui_common/`**: `theme.py` (`PALETTE`/`FONTS`/`apply_theme()`), `pty_terminal.py`
  (`PtyTerminal`), `autosave.py` (`AutoSaveManager`), `settings.py` (NEW, not a lift-and-shift —
  replaces the monolith's single global `.rmip_gui_settings.json` with one JSON file per app under
  `.gui_settings/<app_name>.json`, avoiding a key collision once multiple apps import it),
  `variable_map.py` (`VariableNameMapper`), `target_types.py` (`TARGET_TYPES`/`TARGET_TYPE_FIELDS`/
  `TARGET_ROW_COLUMNS`), `fuel_data.py` (`FuelNormalizer` — **deduplicated during extraction, not
  just relocated**: `get_mw()`/`get_nu_o2()` now delegate to `chem_data.compute_mw()`/
  `compute_nu_o2()` instead of carrying a second, verbatim-duplicated MW table — confirmed the two
  tables held identical numbers, e.g. both had `NC7H16: 100.205`, before deleting one; kept
  `FuelNormalizer`'s own alias-resolution/SMILES data, which `chem_data.py` has neither of).
- **`brute_force_sa_gui.py`** (repo root, matching `forward_uq.py`'s convention): standalone Tk app
  wrapping `src/Sensitivity_Analysis/sens_3_params.py`. Scope note worth knowing before touching
  this again: `sens_3_params.py` needs a **full** `target.opt`-shaped YAML (Locations.mechanism/
  targets/addendum, Stats fields) — its own conditions come from the `.target`/`.add` files already
  referenced inside that YAML, not from separate T/P/phi fields (confirmed by reading the
  monolith's own `_rs_run_sa_terminal()`, which only ever overrode `Locations.mechanism` before
  launching). So this app **loads an existing target.opt** (built by other means) rather than
  reconstructing the whole config tree from scratch in a second GUI — it only lets the user
  override the mechanism path, then launches `sens_3_params.py` via the shared `PtyTerminal`. This
  is the correct scope, not a shortcut — rebuilding all of `target.opt`'s schema in every new app
  would defeat the point of the split.
- **Verified**: real Tk window built and ran without exception (display was available in this
  session, `DISPLAY` was set) — loaded a real `target.opt`
  (`DATASET/H2_O2_TEST/target.opt`) correctly, `xdotool` confirmed the window exists with the
  correct title. **Could not get a photographic screenshot** — this sandbox's virtual display shows
  a screensaver/test-pattern to screen-capture tools (`scrot`) regardless of what's actually
  rendered; a future session with a normal display should still eyeball it once, this is a
  tooling gap in this environment, not a claim that visual polish was verified.
- **Tests**: `tests/test_gui_common.py` (19 tests — `fuel_data`/`variable_map`/`target_types`/
  `settings`/`autosave`; `theme.py`/`pty_terminal.py` need a real display, not unit-tested),
  `tests/test_brute_force_sa_gui.py` (5 tests — headless `--no-gui` config-loading path).

**Phase 2 ✅ DONE (2026-07-12, same session)** — Forward UQ + Nominal Simulation apps.
- **`forward_uq_gui.py`** (repo root): wraps `forward_uq.py` exactly as it already works
  standalone (`<target.opt> --n_samples N --method M --seed S --output_dir D`) — same
  "load an existing target.opt, don't rebuild the schema" scoping as Brute-Force SA, since
  `forward_uq.py` also needs the mechanism/uncertainty-XML `Locations` already populated plus
  `run_script.py`'s cached PRS coefficients to already exist. Uses the shared `PtyTerminal`
  (the monolith's own Forward UQ tab instead shelled out to an **external OS terminal window**
  via `_run_job()` — this app replaces that with the standardized embedded terminal per the
  plan's §1.4 decision). Polls for `forward_uq_statistics.csv` after launch and displays a
  summary, same behavior as the monolith's tab.
- **`nominal_sim_gui.py`** (repo root): wraps `src/mso_compare/run_nominal_sim.py`. **Confirmed
  with KP during planning which of two same-named "nominal sim" things this is** — the
  `mso_compare` pipeline's nominal-only runner (`template_nominal_only.yaml`'s named run labels:
  `nominal_htc`/`nominal_ltc`/custom), NOT `src/MUQ-SAC/nominal_sim_v3.py` (a different, unrelated
  driver that also exists in this codebase — don't confuse the two if touching this again). Loads
  an mso_compare pipeline YAML, lists its run labels via `mso_compare.config.load_config()`
  in-process (cheap, no subprocess needed just to populate a dropdown), lets the user pick a
  label + dry-run toggle, launches `run_nominal_sim.py --config ... --run ...` via `PtyTerminal`.
- **Verified**: both apps built real Tk windows without exception against this session's live
  display; `forward_uq_gui.py` loaded a real `target.opt`; `nominal_sim_gui.py` loaded the real
  `template_nominal_only.yaml` and correctly populated its run-label dropdown
  (`['nominal_htc', 'nominal_ltc']`). Same screenshot-tooling limitation as Phase 1 — no
  photographic capture possible in this sandbox, structural/functional verification only.
- **Tests**: `tests/test_forward_uq_gui.py` (3), `tests/test_nominal_sim_gui.py` (5).

**Phase 3 ✅ DONE (2026-07-12, same session)** — MSO Compare + Mean Value/Fusion Generator apps.
- **`mso_compare_gui.py`** (repo root): wraps `src/run_mso_pipeline.py`'s full 4-phase pipeline
  (simulate→merge→error-metrics→plots), each phase independently skippable, `--regime htc|ltc|both`,
  `--dry-run`/`--verbose` — a straightforward `PtyTerminal`-launched subprocess wrapper, same shape
  as Phase 1/2's apps. Distinct from `nominal_sim_gui.py` (Phase 2): that one runs a single named
  run label; this one runs the full comparison pipeline `src/mso_compare/` was actually built for.
- **`mean_value_fusion_gui.py`** (repo root): **the one app this phase that does NOT shell out to
  a subprocess** — calls `rmip.analysis.graph_comparator.GraphComparator` →
  `build_union_spec()` → `rmip.stubs.FusionEngine.fuse()` (this session's earlier work) directly
  in-process via a background `threading.Thread` + `root.after(0, ...)` callback, matching the
  monolith's own RMIP Analysis tab pattern for in-process library calls (there's no existing
  standalone CLI for `stubs.FusionEngine` specifically — only `rmip.analysis.fusion.FusionEngine`
  has one, `rmip fuse`, which lacks `fuse_overrides`/file-writing/element-balance-validation).
  Lets the user list a DB's mechanisms, pick ≥2 IDs to fuse, set kinetics-identity tolerances,
  and optionally write Cantera YAML too. Displays VERBATIM/COPY/FUSE counts and the element-balance
  report after a run.
- **Verified**: both apps built real Tk windows without exception; `mean_value_fusion_gui.py` was
  exercised end-to-end with a REAL fusion run (reusing `test_stubs_fusion.py`'s H2-combustion
  fixture) inside a real `root.mainloop()` (not just `root.update()` — the background-thread
  `root.after()` call needs an actual running mainloop, confirmed the hard way when an
  `update()`-loop test harness raised `RuntimeError: main thread is not in main loop` — a
  test-harness bug, not an app bug, fixed by driving the test through `mainloop()` properly).
  Fusion produced the expected `VERBATIM=1 COPY=1 FUSE=1`, balanced element check, and real
  `.inp`/`.dat` files on disk.
- **Tests**: `tests/test_mso_compare_gui.py` (3), `tests/test_mean_value_fusion_gui.py` (4 — the
  `TestRunFusion` case runs a real fusion end-to-end, mirroring
  `test_stubs_fusion.py`'s own expectations exactly, since this app's `_run_fusion()` is a thin
  wrapper over the same call sequence). Combined suite (`tests/` + `src/rmip/tests/`) is now 448
  passing.

**Phase 4 ✅ DONE (2026-07-12, same session)** — RMIP Suite (umbrella app).
- **`rmip_suite_gui.py`** (repo root): one window, one shared "RMIP database" field, an internal
  `ttk.Notebook` with 4 tabs — Graph Comparison (`rmip compare-graph`), Mechanism Reduction
  (`rmip reduce`), Global Sensitivity Analysis (`rmip gsa-run`, this session's earlier work),
  Active Parameter Selection (`src/ActiveParameterScreen.py`). Mechanism Fusion, which used to
  live in this same tab in the monolith, does **not** appear here — it moved to its own app in
  Phase 3 (`mean_value_fusion_gui.py`) per the plan's §1.3 scope decision; don't re-add it here.
  All 4 tabs share one `_TerminalTab` base class (assemble a CLI argv list, launch via the shared
  `PtyTerminal`) — the first 3 launch via the repo-root `rmip_cli.py` launcher (never
  `python3 src/rmip/cli.py` directly, see the `io`-shadowing note elsewhere in this file); the 4th
  launches `src/ActiveParameterScreen.py` directly.
- **New finding while wiring the Active Parameter Selection tab**: `src/io/` is **also** a real
  Python package (has its own `__init__.py`, contains `mso_analysis.py`/`mso_io.py`/
  `mso_latex.py`/`mso_plots.py`) — a second, previously-undiscovered `io`-shadowing directory,
  completely unrelated to `src/rmip/io/`. **Empirically confirmed this specific case is safe** —
  `python3 src/ActiveParameterScreen.py --help` runs cleanly (verified this session; something
  about interpreter/module load order means the crash that hits `src/rmip/cli.py` didn't reproduce
  here) — but if a future session adds a GUI wrapper for any OTHER script that lives directly
  under `src/` (not `src/rmip/`), verify with `--help` first rather than assuming it's fine by
  analogy; this wasn't fully root-caused, just empirically checked for this one script.
- **Verified**: real Tk window built with all 4 tabs, each tab's `_build_command()` checked
  against known-good CLI argv shapes; **ran a real end-to-end DRG reduction** through the GUI's
  `PtyTerminal` on mechanism 8 (GRI-3.0) — actual `rmip_cli.py reduce` subprocess executed,
  produced `"DRG reduction complete: ... 6 species / 44 reactions ... DB reduction_runs id = 3"`
  in the embedded terminal, confirming the whole GUI→PtyTerminal→subprocess→real-RMIP-library
  chain works, not just command assembly.
- **Tests**: `tests/test_rmip_suite_gui.py` (12 — command-assembly + validation-error tests for
  all 4 tabs). Combined suite (`tests/` + `src/rmip/tests/`) is now 460 passing.

**Phase 6 ✅ DONE (2026-07-12, same session)** — optional launcher, built ahead of Phase 5 since
Phase 5 is genuinely blocked (see below) and Phase 6 has no dependency on it.
- **`launcher_gui.py`** (repo root): small window listing all 6 built apps as buttons, each
  spawning the corresponding script via `subprocess.Popen` (a real separate process, not an
  in-process import — a crash in one app can't take the launcher or any other running app down).
  Deliberately does **not** list an Uncertainty Generator entry yet (Phase 5 isn't built) —
  `tests/test_launcher_gui.py` has an explicit test asserting this stays true until that app
  actually exists, so it doesn't get forgotten and left off later by accident either.
- **Tests**: `tests/test_launcher_gui.py` (4, including a real subprocess spawn of
  `brute_force_sa_gui.py --no-gui`). Combined suite (`tests/` + `src/rmip/tests/`) is now 464
  passing.

**Phase 5 ✅ DONE (2026-07-12, same session)** — Uncertainty Generator. KP confirmed the exact
formula (asked via `AskUserQuestion`): for each reaction, `max(|kappa_max(T)-kappa_nom(T)|,
|kappa_nom(T)-kappa_min(T)|)` across all 3 anchor temperatures — since `kappa = ln(k)`, this delta
IS already `ln(uncertainty factor)`, no separate division needed — applied symmetrically to
`ln(A)` at the nominal (T-independent) A-factor: `A_lb = A_nominal/exp(max_delta)`,
`A_ub = A_nominal*exp(max_delta)`.
- **`uncertainty_generator_gui.py`** (repo root): wraps `src/MUQ-SAC/Uncertainty.py`'s existing
  `reaction` class (`getKappaMax`/`getKappaMin`/`getNominal`, all evaluated at 3 fixed anchor
  temperatures — low/mid/high of whatever `<temp>` list the XML gives) — in-process via a
  background thread (same pattern as `mean_value_fusion_gui.py`, no subprocess). Per-reaction
  errors (e.g. a reaction string not present in the given mechanism) are caught and reported in
  the results table rather than aborting the whole batch.
- **Found and fixed TWO more real, previously-undiscovered bugs while building this** — same
  family as the `ChemkinWriter` double-`END` bug from earlier this session (a writer whose output
  was never actually round-tripped through its real consumer until now): `generate_target_opt.py`'s
  `generate_uncertainty_xml()` (the existing "Uncertainty XML" tab's writer, in production use)
  never wrote the `no` or `perturbation_type` attributes that `Uncertainty.py`'s own
  `reaction.__init__` requires — **every uncertainty XML that tab has ever produced would crash
  `Uncertainty.py` on load** (`KeyError: 'no'`, then `AttributeError: 'reaction' object has no
  attribute 'perturbation_type'`), only ever silently unexercised because nothing had piped the
  GUI's own XML output back through `Uncertainty.py` before. Fixed in `generate_target_opt.py`
  directly: `no` = stable 1-based sequence number (only ever used downstream as a display/tag
  label, confirmed by reading every usage — safe default); `perturbation_type` defaults to
  `"arrhenius"` (the standard 3-parameter A/n/Ea case, matching `sens_3_params.py`'s scope — not
  `"factor"`, the reduced 1-parameter mode).
- **Real minimum-data constraint discovered, not a bug**: `Uncertainty.py`'s internal Class-B/C
  curve fit (`getConstrainedUnsrtZeta`) needs enough `<temp>`/`<unsrt>` points to determine its
  3-parameter basis — a 2-point XML input causes `ValueError: min() arg is an empty sequence`
  inside existing, untouched legacy code. Real uncertainty XML always has many points (the shipped
  example has 11) — this only bit a first draft of the test fixtures, fixed there, not in
  `Uncertainty.py` itself.
- **Verified**: real end-to-end run against a real mechanism already in this repo
  (`MECHANISM/FFCM1/FFCM1.yaml`) with a freshly-generated (bug-fixed) uncertainty XML — computed
  correct symmetric bounds for 2 real reactions, correctly caught and reported 1 deliberately-fake
  reaction as an error without crashing the batch, wrote a correct CSV.
- **Tests**: `tests/test_uncertainty_generator_gui.py` (9 — includes explicit regression tests for
  the `no`/`perturbation_type` XML-writer bugs, and a real end-to-end bound computation against
  `MECHANISM/FFCM1/FFCM1.yaml`, skipped automatically if that mechanism file isn't present). Also
  updated `launcher_gui.py` to add the now-built Uncertainty Generator button (was deliberately
  absent before). Combined suite (`tests/` + `src/rmip/tests/`) is now 473 passing.
- **All 7 apps of the original GUI-separation plan are now built.** Nothing from Part 1 of
  `MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md` remains — see that
  file's Part 2 (8 ranked broader-improvement findings, several already acted on this session:
  items 1-2 partially addressed via the glossary gap being *documented* — not fixed, still open —
  and the `ChemkinWriter`/uncertainty-XML writer bugs *are* fixed) for what's left beyond the GUI
  split itself.

### 2e. Stale `project.db` mechanism IDs (low priority, just a decision to make eventually)
Mechanisms 1-4 in `outputs/project.db` are stale (pre-parser-fix). 8-11 are current. Nothing
forces a decision now — flagged so a future session doesn't get confused seeing both. If any new
SA/reduction run needs the corrected data, point it at 8-11, not 1-4.

---

## 3. Reference: `outputs/project.db` mechanism table

| ID | Name | Species | Rxns | Format | Status |
|----|------|---------|------|--------|--------|
| 1  | GRI-3.0 | 15 | 48 | chemkin | STALE — use 8 |
| 2  | Davis-2005 | 14 | 38 | chemkin | STALE — use 9 |
| 3  | Keromenes-2013 | 17 | 49 | chemkin | STALE — use 10 |
| 4  | Li-2015 | 14 | 37 | chemkin | STALE — use 11 |
| 5  | FFCM1 | 38 | 291 | cantera_yaml | unaffected (different reader) |
| 6  | MB-MB2D (base) | 608 | 3984 | cantera_yaml | unaffected |
| 7  | MB-MB2D Lalit-2024 | 623 | 4050 | cantera_yaml | unaffected |
| 8  | GRI-3.0 | 15 | 48 | chemkin | current |
| 9  | Davis-2005 | 14 | 38 | chemkin | current |
| 10 | Keromenes-2013 | 17 | 49 | chemkin | current |
| 11 | Li-2015 | 14 | 37 | chemkin | current |

Zero-RK install: `/home/krithika/zero-rk/build2/inst_dir` (50 binaries, `ctest` 145/145 passing).

---

## 4. Things that will bite you if you forget them

- **Always invoke the CLI via the repo-root `rmip_cli.py` launcher** (`python3 rmip_cli.py ...`),
  never `python3 src/rmip/cli.py ...` or `cd src && python -m rmip.cli`. `src/rmip/io/` is a
  package literally named `io`, and if `src/rmip/` ends up as `sys.path[0]` (which running
  `cli.py` directly as a script does), it shadows the stdlib `io` module and crashes the
  interpreter at startup (`AttributeError: module 'io' has no attribute 'open'`) before any of
  your code even runs. This is pre-existing and already documented in `rmip_cli.py`'s own
  docstring — re-discovered the hard way while testing the `gsa-run` CLI subcommand, not new.
- **Don't `pip install` anything into the shared anaconda environment without checking what it
  drags in first.** `pip install SALib` alone silently upgraded `numpy` 1.24.4→2.0.2 (plus
  scipy/pandas), which broke `scikit-learn`'s import outright — a real incident, not a
  hypothetical, during the Zero-RK GSA work. `SALib` now lives in its own venv
  (`/home/krithika/.venvs/salib_gsa`), talked to only via subprocess+JSON
  (`rmip/simulation/_salib_backend.py`) — same D7 "subprocess boundary" principle already used
  for every other external tool in this codebase. If you need a new Python dependency and aren't
  certain it's compatible with the pinned `numpy==1.24.4`/`scipy==1.8.0`/`pandas==1.4.1`, check
  first (`pip download --no-deps` + inspect metadata, or just try it in a throwaway venv) rather
  than installing directly and finding out via a broken test suite.
- **`rmip_cli.py parse` always creates a NEW mechanism row** — it never updates in place. Don't
  re-parse expecting IDs 1-4 to change; use a fresh ID (already done, see §3) or write a targeted
  SQL patch if you need in-place semantics.
- **`ChemkinWriter`'s `use_original_units=True` is the default and the one Zero-RK/GSA plan
  depends on** — the `not self._use_orig` (true-SI) path for LOW/TROE/PLOG data was left
  correctly-scoped-out (no `_si_to_cgs_factor` re-scaling) rather than fixed properly, because the
  underlying stored values were never true SI to begin with. If you ever need `use_original_units=
  False` to work correctly for falloff/PLOG reactions, that's unfinished — check
  `chemkin_writer.py`'s `_format_reaction` comments before trusting that path.
- **`make_input_file.py`'s solver dispatch is deeply nested and mostly duplicated per target type**
  (Tig alone has 2 ignition-mode branches × up to 5 solver/BoundaryLayer combinations, each a full
  copy-pasted Python-script-as-string). Use `ast.walk()` to find the real control-flow structure
  before editing — grepping for `if`/`elif` by line number is unreliable because the file is full
  of triple-quoted string literals containing *other* Python code that looks identical to real
  control flow. (This cost real time this session — don't repeat it.)
- **`target.species_dict` / `target.fuel_dict` in the `make_input_file.py`/`combustion_target_class.py`
  pipeline are already-resolved ABSOLUTE mixture mole fractions**, not stream-relative ratios like
  Zero-RK's own `fuel_mole_fracs`/`oxidizer_mole_fracs` want. Don't feed them to Zero-RK directly —
  reconstruct normalized stream ratios first (see the Tig branch in `make_input_file.py` for the
  working pattern: normalize `fuel_dict` to sum 1, normalize `species_dict` minus fuel species to
  sum 1, pass `initial_phis: [target.phi]`).
- **`soln2ck_2.py`/`soln2ck_FM.py` in `src/MUQ-SAC/` are Cantera's own vendored yaml2ck converter**
  — already correct, already used by CHEMKIN_PRO. The zerork Tig branch reuses this for
  Cantera-YAML → CHEMKIN-ASCII conversion instead of `rmip`'s own `ChemkinWriter` (which is
  DB-driven and not applicable to this per-run-perturbed-mechanism pipeline anyway).
- **`mech_diagnostics.py` in `src/MUQ-SAC/` exists only in this repo**, not in
  `~/mechanism-optimization-suite`. Don't delete it thinking it's cruft.

---

## 5. Quick verification commands

```bash
cd /data/MECHANISM_OPTIMIZATION_SUITE

# rmip test suite
python3 -m pytest src/rmip/tests/ -q                          # expect 390 passed

# MUQ-SAC files still parse
python3 -m py_compile src/MUQ-SAC/make_input_file.py src/MUQ-SAC/combustion_target_class.py \
    src/MUQ-SAC/data_management.py src/MUQ-SAC/run_script.py src/MUQ-SAC/AdaptiveResampler.py

# Zero-RK IDT smoke test (direct bridge, mechanism_id=8 = current GRI-3.0)
python3 -c "
import sys; sys.path.insert(0, 'src')
from rmip.simulation.zerork_bridge import ZerorkBridge
from rmip.types import SimCondition
b = ZerorkBridge('outputs/project.db', '/home/krithika/zero-rk/build2/inst_dir')
m = b.export_mechanism(8, '/tmp/zerork_smoke')
c = SimCondition(T_K=1000.0, P_atm=10.0, phi=1.0, fuel='H2:1.0', oxidizer='O2:1.0, N2:3.76')
i = b.build_idt_input(m, 8, c, '/tmp/zerork_smoke/idt')
p = b.run_idt(i, timeout=60)
print(b.parse_idt_output('/tmp/zerork_smoke/idt', 8, c) if p.returncode == 0 else p.stdout[-500:])
"
# expect IDTResult(..., idt_s≈0.00806..., converged=True, ...)

# Zero-RK JSR smoke test (direct bridge, mechanism_id=8 = current GRI-3.0)
python3 -c "
import sys; sys.path.insert(0, 'src')
from rmip.simulation.zerork_bridge import ZerorkBridge
from rmip.types import SimCondition
b = ZerorkBridge('outputs/project.db', '/home/krithika/zero-rk/build2/inst_dir')
m = b.export_mechanism(8, '/tmp/zerork_smoke_jsr')
c = SimCondition(T_K=1000.0, P_atm=10.0, phi=1.0, fuel='H2:1.0', oxidizer='O2:1.0, N2:3.76')
i = b.build_jsr_input(m, 8, c, residence_time_s=0.5, work_dir='/tmp/zerork_smoke_jsr/jsr')
p = b.run_jsr(i, timeout=60)
print(b.parse_jsr_output('/tmp/zerork_smoke_jsr/jsr', 8, c) if p.returncode == 0 else p.stdout[-500:])
"
# expect JSRResult(..., converged=True, residence_time_s≈0.5, ...) -- this exercises
# zerork_bridge.py directly (Phase 1), not make_input_file.py's new zerork JSR branch (Phase 2,
# §1 item 7 above) -- that one needs a full combustion_target_class round-trip to exercise, see
# this session's scratchpad verify_jsr_zerork.py for the pattern if it needs re-checking.

# Zero-RK GSA smoke test (CLI, mechanism_id=8, tiny sample count for speed --
# MUST use the repo-root launcher, see §4's io-shadowing note)
python3 rmip_cli.py gsa-run 8 --db /tmp/gsa_smoke.db --method sobol --n-samples 4 \
    --reactions <id1>,<id2>,<id3> --zerork-install-prefix /home/krithika/zero-rk/build2/inst_dir \
    --T 1000 --P 10 --phi 1.0 --fuel "H2:1.0" --work-dir /tmp/gsa_smoke_work --seed 1
# (copy outputs/project.db to /tmp/gsa_smoke.db first; get real reaction ids via
#  `SELECT id FROM reactions WHERE mechanism_id=8 ORDER BY id LIMIT 3` -- expect
#  "sobol GSA complete" + a DB sensitivity_runs id printed at the end)
```

---

## pending_night.md (2026-07-14 handoff — its load-bearing caveat is already quoted in BUG.md's header)

# Session handoff — 2026-07-14

Long session executing `MarkDownFiles/review_plan.md` (the fix plan for `MarkDownFiles/review.md`'s deep-review findings), plus an ad-hoc fusion-engine stress test + deliverable requested mid-session. **Nothing in this session has been committed to git** — everything described below is uncommitted working-tree changes. Test suite is green at every checkpoint mentioned (run `python3 -m pytest src/rmip/tests/ tests/ -q` to confirm; last known count: **539 passed**, up from the 481 baseline at session start).

## What's done

### Phase 0 (review_plan.md) — complete
All 7 items: B5 (fuse-CLI crash), B8 (sensitivity_runner typo), B9 (optimize-CLI crash), B11 (GSA inf-handling + failure-rate guard), B12 (brute_force_sa path bug), B14 (nominal_sim_gui subprocess spawn — note: the literal `cwd=src` fix suggested by the plan is WRONG for this repo, `src/io/` shadows stdlib `io` and crashes the interpreter; the actual fix defers `sys.path.insert` via `-c`+runpy, see `nominal_sim_gui.py`), M18a (mpi-ranks clamp).

### Phase 1 (review_plan.md) — complete, all Blockers + Majors
B1/B2 (Cantera-3 reader rewrite + kmol→mol conversion), B3 (compare no longer silently drops unresolved species/reactions), B4 (fusion identity violation — root cause was in `graph_comparator.py`, same class as B3), B6 (Fortran-exponent corruption), B7 (DUPLICATE keyword semantics inverted, parser+writer), B15 (CHEMKIN writer Ea unit bug), M1 (ion species `+` truncation + referential-integrity check + `allow_pseudo_species`), M2 (LOW/TROE/PLOG no-space-after-slash bug, 2 separate bugs found), M3 (KJOULES matched as JOULES), M4 (bare `+M` third-body handling), M5 (kinetics_data mol-SI standardization), M6 (cantera_writer element case), M7 (chemkin_writer hard-error on NULL A_si), M8 (thermo-skip warning + **found and fixed** a real NASA-7 data-block ordering bug in cantera_writer.py that was the actual cause of all the "discontinuity in cp/R" warnings seen throughout the session).

### Phase 2 (review_plan.md) — partially done
- **M9 done** (canonical_key collisions for CHEMKIN DUPLICATE reactions) in `graph_comparator.py`, `fusion.py` (3 internal lookups), `stubs.py` (DoEFramework), `types.py` (`ReactionClassification.occurrence_index`, `FusionRecord.occurrence_index`, `UnionGraphSpec` bucket dicts now tuple-keyed). **NOT done**: `comparison.py`, `unified_tree.py`, `gsa_prs_crosscheck.py`, and `graph_builder.py`'s R-label collision — these were surveyed (see the Explore-agent findings, still fresh in this conversation's history) but not fixed. Lower priority than the M9 sites already fixed since those aren't on the fusion critical path.
- **M11 done** (falloff/PLOG FUSE-bucket averaging discarding kinetics_data_json) in `fusion.py`.
- **M10, M12 (already done earlier as part of B4), M13, M14, M15, M16, M17, B10/M-rmg — NOT started.**

### Phases 3/4/5 (review_plan.md) — not started at all.

### Ad-hoc fusion deliverable (user request mid-session)
User asked (after Phase 2 was started) to: debug why GUI mechanism fusion wasn't working, stress-test the fusion engine, and produce two fused mechanisms from Keromnes 2013 / Li 2015 / Davis 2005 (all in `MECHANISM/`) — one priority-pick (Keromnes > Li > Davis for shared reactions, new fusion mode, not previously existing) and one consensus-mean with temperature-dependent uncertainty bands (methodology confirmed with user via AskUserQuestion before implementing — see below). Used Fable 5 (via `Agent` tool, `model: "fable"`, `subagent_type: "Plan"`) to draft the execution plan for this per explicit user instruction ("Fable 5 to make a plan"); I (Sonnet 5) executed it.

**Confirmed uncertainty methodology** (do not re-litigate, user already approved all three points):
1. A-factor UF = worst-case over a T-grid of `max_i(k_i(T)) / mean_i(k_i(T))` (arithmetic mean), applied symmetrically `[A_mean/UF, A_mean*UF]`.
2. 3-param band symmetric in ln(k): `f(T) = exp(max_i|ln k_i(T) - mean_i ln k_i(T)|)`, band = `[k_geo_mean(T)/f(T), k_geo_mean(T)*f(T)]`.
3. Fit upper/lower envelopes to their own effective 2-param Arrhenius (A, Ea at fixed n=n_mean) via OLS, inflated to guarantee containment of the discrete band.

**Delivered** (all in `outputs/fusion_keromnes_li_davis/`):
- `db/fusion_stress.db` — Keromnes(id 1)/Li(id 2)/Davis(id 3) parsed with an extended glossary.
- `glossary/added_entries.csv` — the 5 species (CO, CO2, HCO, CH4, C2H6) that were missing from the repo's only glossary (`species_smiles.csv`, now also updated at repo root) — this was the actual root cause of "fusion doesn't work in the GUI" (nothing carbon-chemistry-related could cross-match).
- `priority/Fused_priority_KLD.{inp,dat,yaml}` + `_priority_provenance.json` (per-reaction chosen-source audit).
- `mean_unsrt/Fused_mean_KLD.{inp,dat,yaml}` + `uncertainty_bands.{json,csv}` + `mso_bounds_3param.json`.
- `stress_test_punchlist.md` — full bug list found+fixed during this work, plus one **documented but not fixed** limitation (see below).
- New code: `src/rmip/analysis/fusion_uncertainty.py` (new module, 10 passing tests in `test_fusion_uncertainty.py`, zero containment violations verified against real data), `FusionTreatment.PRIORITY` + `FusionEngine.fuse(..., priority_order=...)` in `fusion.py`, `--allow-pseudo-species` plumbed through `chemkin_reader.load_chemkin`/`MechanismParser.parse`/CLI `parse` subcommand, driver script `fuse_kld.py` at repo root.

**Known unresolved limitation** (documented in the punchlist, real remaining work): both fused `.yaml` files fail to load in `ct.Solution()` — not just `ck2yaml`, Cantera's own kinetics engine — because Keromnes writes H2 dissociation as `H2+M<=>2H+M` while Li/Davis write the same physical reaction as `2H+H2<=>2H2` (H2 as its own explicit third body), and Cantera's internal duplicate-detection recognizes these as the same reaction while this suite's canonicalizer does not (different canonical_key). The `.inp`/`.dat` CHEMKIN files are correct and unaffected — Zero-RK and other CHEMKIN-family tools are expected to be more lenient here (not verified this session — would be a good next step: try loading `Fused_mean_KLD.inp` directly through Zero-RK's own parser to confirm the CHEMKIN files really are usable as-is). A real fix requires teaching `core/canonicalize.py` to recognize the "species appears as both reactant and product with equal stoichiometry" pattern as equivalent to a generic-M third body — not attempted, unclear blast radius on other mechanisms.

## Immediate next steps (priority order)

1. **Verify the CHEMKIN `.inp` files actually work end-to-end** in a real solver (Zero-RK ideally, since that's what this suite's simulation runners use) — this was not done and is the one unverified claim in the punchlist.
2. **Decide on the H2-self-third-body canonicalization fix** — either implement it (`core/canonicalize.py`, `make_reaction_canonical_key`) or explicitly accept the limitation and move on. Ask the user if it matters for their downstream use of these two mechanisms.
3. **Continue Phase 2**: M10 (falloff SHARED_IDENTICAL misclassification — compares only A/n/Ea, ignores LOW/TROE tables), M13 (unified_tree.py band/record zip bug), M14 (uncertainty_bands.py Cantera-2 class names — note `fusion_uncertainty.py` from this session sidesteps this by NOT depending on `uncertainty_bands.py`'s Cantera integration at all, computing k(T) directly from stored A/n/Ea instead), M15 (drg.py Lu-Law reduction), M16 (cli.py error handling), M17 (migrations.py transactional wrapping), B10/M-rmg (RMG interface API mismatch). Also finish M9's remaining sites (`comparison.py`, `unified_tree.py`, `gsa_prs_crosscheck.py`, `graph_builder.py` R-labels) if time allows — lower priority since they're off the fusion critical path.
4. **Phases 3–5** of `review_plan.md` (MUQ-SAC/mso_compare robustness, GUI hardening, minors batch) — not started.

## Notes for continuity

- `MarkDownFiles/review.md` and `review_plan.md` are the source of truth for the ID scheme (B1-B15, M1-M17) — re-read them, don't rely on memory of what's fixed.
- The `.rmip_cantera_cache/` directory and `outputs/project.db` predate this session; `outputs/fusion_keromnes_li_davis/` is entirely new this session.
- `species_smiles.csv` at repo root was edited (5 rows appended) — this affects ALL future parses of carbon-chemistry mechanisms in this repo, not just this session's task. Good change to keep.
- Multiple fused-mechanism DB rows accumulated in `outputs/fusion_keromnes_li_davis/db/fusion_stress.db` from iterative re-runs while debugging (ids 4, 5, 6... — only the LAST one per mode, written by the final `fuse_kld.py` runs, is reflected in the output files). Harmless but could be cleaned up.
- Git status: nothing committed. `git status`/`git diff --stat` will show a large uncommitted diff across `src/rmip/`, plus several new files (`fuse_kld.py`, `src/rmip/analysis/fusion_uncertainty.py`, `src/rmip/tests/test_fusion_*.py`, `outputs/fusion_keromnes_li_davis/`). User has not asked for a commit yet — do not commit without asking.

---

## MarkDownFiles/Future.md (restart/checkpoint bugs + feature roadmap — bugs confirmed fixed in BUG.md's FUTURE-BUG-1..6 entry; features shipped separately per HISTORY part 16)

# Future.md — Restart Logic Audit + Feature Roadmap
> Generated: 2026-07-05

---

## Part 1: Restart Logic Bugs

### Bug 1 — Sentinel write path is coincidentally correct but fundamentally fragile
**`simulation_manager2_0.py:804`**

The sentinel **check** (line 730):
```python
_sentinel = os.path.join(os.getcwd(), "case-"+str(case_index), ".done")
#  → <optDir>/case-N/.done
```
The sentinel **write** (line 804):
```python
with open(os.path.join(os.getcwd(), ".done"), "w") as _sf:
#  → os.getcwd()/.done
```
These happen to produce the same path only because `getDirectoryList()` calls `os.chdir("case-N")` as a side effect and never restores CWD. If that side effect ever disappears (refactor, exception, early return), the sentinel is written one directory too high (`<optDir>/.done` instead of `<optDir>/case-N/.done`) and the check for case-N never finds it — the case re-runs every restart.

**Fix:** Use the captured `optDir` (line 711) explicitly:
```python
with open(os.path.join(optDir, "case-"+str(case_index), ".done"), "w") as _sf:
```

---

### Bug 2 — CWD corruption on exception poisons all subsequent case iterations
**`simulation_manager2_0.py:737–822`**

`getDirectoryList()` calls `os.chdir("case-N")` but never chdir's back. The balancing `os.chdir('..')` is at line 822, AFTER all simulation code runs. If anything throws between line 737 and 822 (simulation crash, `do_job_async_` failure, OS error), the function exits with CWD stuck inside `case-N/`.

On the next iteration, the sentinel check uses `os.getcwd()` which is now `<optDir>/case-N/`, so it looks for `<optDir>/case-N/case-(N+1)/.done` — a path that will never exist. Every subsequent case re-runs from scratch even if it was already complete.

**Fix:** Use `try/finally` to guarantee `os.chdir('..')`, or — better — build all paths from `optDir` (captured at line 711) instead of relying on `os.getcwd()`:
```python
case_dir_path = os.path.join(optDir, "case-"+str(case_index))
_sentinel = os.path.join(case_dir_path, ".done")
# Pass case_dir_path explicitly to getDirectoryList instead of using os.chdir side effect
```

---

### Bug 3 — YAML restart path iterates wrong design matrix
**`partial_PRS_system.py:626`** — the main YAML-folder restart bug

On a fresh run, YAML files are generated using `p_design_matrix` (partial), so
`mechanism_0.yaml … mechanism_{len(p_design_matrix)-1}.yaml` exist on disk.

On **restart** (line 621–629), when the YAML directory already exists:
```python
for i, sample in enumerate(design_matrix):   # BUG: should be p_design_matrix
    yaml_loc.append(...+f"/mechanism_{i}.yaml")
```
`design_matrix` is the **full** matrix (all columns, potentially more rows than `p_design_matrix`).
If `len(design_matrix) > len(p_design_matrix)`, you build `yaml_loc` entries for files
`mechanism_{k}.yaml` that don't exist on disk. When `getDirectoryList()` later accesses
`yaml_loc[i]` and passes it to `create_input_file`, it references a non-existent mechanism
file — crash or silently wrong simulation input.

**Fix:** Replace `design_matrix` with `p_design_matrix` at line 626:
```python
for i, sample in enumerate(p_design_matrix):
```

---

### Bug 4 — YAML file existence not verified on restart (partial chunk write)
Both `partial_PRS_system.py` and `run_script.py` check only whether the **directory** exists,
not whether all files exist inside it. YAML files are written in chunks of 500 (lines 598–619).
If the run is interrupted after chunk 0 is written but before chunk 1 completes, the directory
exists but only `mechanism_0.yaml … mechanism_499.yaml` are on disk. The restart path
silently builds `yaml_loc` for all N files and passes missing paths to simulations.

**Fix:** Add a guard before accepting the restart path:
```python
import glob
existing = len(glob.glob(os.path.join(yaml_dir, "mechanism_*.yaml")))
if existing == len(p_design_matrix):
    # all files present — use restart path
else:
    # partial write — regenerate missing files from the last complete chunk
```

---

### Bug 5 — `locations` file is appended, accumulating stale entries across restarts
**`simulation_manager2_0.py:815`**
```python
simulation_locations = open(optDir+"/locations", '+a')
```
On restart, previously completed case locations are appended again. `data_management` later
reads this file and processes every listed simulation output. Duplicate entries cause the
same simulation to be counted twice in the response surface fit, corrupting the PRS.

**Fix:** Build the complete `sim_location` list in memory across all cases, then write the
`locations` file once at the end of `make_dir_in_parallel` (overwrite, not append), or
check before appending whether this case's entries are already present.

---

### Bug 6 — `progress` file ends up in the wrong directory (nominal simulations)
**`simulation_manager2_0.py:195`**
```python
progress_path = self.progress_file if self.progress_file else \
    os.path.join(os.path.dirname(os.getcwd()), "progress")
```
The fallback uses `os.path.dirname(os.getcwd())` at **callback time**. Pool worker callbacks
fire with unpredictable CWD (each worker calls `os.chdir(simulation_dir)`), so the fallback
parent is a random simulation subdirectory, not `nominalDir`. This is why the progress file
is never found in the nominal simulation folder on restart.

The caller sets `X.progress_file = os.path.join(nominalDir, "progress")` at line 671, which
is correct. The fix is to raise an error if `progress_file` is `None` in `callback_run`
(instead of silently using the broken fallback) and audit all Worker creation sites to ensure
they always set `progress_file` explicitly before calling `do_job_async_`.

---

## Part 2: 20 New Feature Ideas for RMIP

### Core Mechanism Analysis

**1. Reverse Rate Unphysicality Scanner**
Check every reaction where only the forward rate is given; compute the reverse via Keq at a
grid of T values and flag reactions where `k_rev` exceeds the collision limit by >3 orders
of magnitude. Directly addresses the convergence failures described in `solved_error.md` —
one of the most common mechanism quality killers in 1D flame simulations.

**2. Mechanism Quality Score**
Composite numeric score per mechanism: SMILES resolution %, thermo self-consistency,
enthalpy of formation agreement with ATcT/JANAF reference, NTC coverage, and rate constant
physical bounds (collision limit check). Single-number "trust index" for each mechanism in
the DB, surfaced in `rmip summary` and comparison reports.

**3. Reaction Pathway Flux Analysis (Rate of Production)**
At any user-specified T/P/φ/t condition, compute integrated rates of production (RoP) for
each element (C, H, O) and render a Sankey diagram showing how atoms flow through the
mechanism. Identifies dominant pathways without requiring external SA data from Chemkin-Pro.

**4. Mechanism Diff Report**
Given any two mechanism IDs in the DB, produce a human-readable diff: reactions added/removed,
log-ratio of A for shared reactions, species added/removed, thermo coefficient changes.
Exportable as HTML table or LaTeX. Essential for tracking changes between mechanism versions
during development.

**5. PLOG Rate Surface Visualizer**
For reactions with PLOG kinetics, render interactive `log k(T,P)` surface plots and contour
maps. Highlight regions where log-linear interpolation breaks down (non-monotonic pressure
dependence) or where the high-P limit is ill-defined. CLI: `rmip plog-surface <rxn_id>`.

---

### Simulation & Benchmarking

**6. JSR / Plug-Flow Reactor (PFR) Simulator**
Add Cantera jet-stirred reactor (constant-T, constant-P, fixed residence time) and plug-flow
reactor modes to `simulation/`. JSR gives speciation profiles at fixed T/P/φ/τ — the most
common validation target for intermediate species. Fits into the existing `SimCondition` /
`IDTResult` type contract.

**7. Ignition Delay NTC Detection**
From a φ=1.0 IDT sweep at multiple T values, auto-detect whether the mechanism reproduces
the negative temperature coefficient (NTC) region typical of n-alkanes. Report
`T_NTC_onset`, `T_NTC_end`, and `IDT_ratio_NTC` vs experimental correlations. Flags
mechanisms that miss NTC — a critical quality check for gasoline surrogate mechanisms.

**8. Adaptive Experiment-Guided Parameter Selection**
Given an IDT or LFS experimental dataset and the current mechanism's MRE, run sensitivity
analysis, rank reactions by their improvement potential, and propose which 5–10 reactions
should be targeted in the next optimization round. Bridges M8 (sensitivity) and M7 (fusion/
optimization) into a closed loop.

**9. Multi-Objective Optimization**
Extend `MSOInterface` to support multiple experimental targets simultaneously with
user-specified weights (e.g., IDT weight=0.7, LFS weight=0.3). Expose Pareto front
visualization showing the IDT-LFS trade-off surface. Allows KP to make explicit decisions
about which observables to prioritize rather than implicitly collapsing them.

---

### Data Integration

**10. NIST / ReSpecTh Rate Database Connector**
Given a reaction's `canonical_key`, query NIST Webbook or a local ReSpecTh XML archive for
published rate expressions. Return a structured list of literature `(A, n, Ea)` measurements
with citations. Auto-populate as alternative sources in `ParameterEstimator` — the input
to the fusion uncertainty band calculation.

**11. ATcT Thermo Cross-Checker**
For each species with a known `inchi_key`, query Active Thermochemical Tables (cached local
JSON) and compare `Hf_298K` against the NASA-7 polynomial value. Flag species where the
deviation exceeds 5 kJ/mol — a common sign of mismatched thermo source between mechanisms.

**12. Experimental Data Digitizer**
Given an image of a scatter plot (IDT or LFS from a paper), accept user-defined axis
calibration points and extract data coordinates via click. Export as `exp_data_points`-
compatible CSV. Addresses a manual step done repeatedly when loading experimental targets.

---

### Intelligence & Machine Learning

**13. Reaction Family Clustering**
Cluster all reactions in the DB by their functional form (H-abstraction, beta-scission,
addition, recombination, etc.) using SMARTS pattern matching on canonical SMILES. Display
as a colour-coded family map on the network graph. Useful for identifying under-represented
families and for applying class-specific uncertainty priors in UQ.

**14. Missing Reaction Predictor (ML)**
Beyond topological gap detection (current Phase 4), train a graph neural network on known
combustion mechanisms to predict which reactions are likely missing based on the presence
of their precursor species. Returns `(species_pair, reaction_type, confidence)` ranked list
as an `RMGSeedSpec`-compatible output.

**15. Mechanism Similarity Fingerprinting**
Compute a compact numerical fingerprint for a mechanism (reaction-type distribution vector +
rate constant quantiles + species formula distribution) and display pairwise mechanism
similarity as a dendrogram/heatmap. Immediately reveals whether two mechanisms are
"fundamentally the same" or truly different — useful before deciding whether to fuse.

---

### Reporting & Workflow

**16. LaTeX Report Generator**
From a completed RMIP workflow (parse → compare → fuse → optimize), auto-generate a
structured LaTeX document: mechanism summary tables, kinetics comparison figures (Arrhenius
plots), ranking tables, uncertainty band figures, and bibliography. Plugs directly into
the paper writing workflow and extends KP's existing `run_report.py` infrastructure.

**17. Workflow Checkpoint System**
Save the complete state of an RMIP session (all mechanism IDs, comparison results, fusion
decisions, optimization outputs) to a versioned JSON snapshot. Load the snapshot to resume
from any intermediate step without re-running previous stages. Complements the existing
SQLite DB by capturing the high-level workflow state.

**18. Batch Workflow Runner**
Accept a YAML config specifying a full pipeline (mechanisms to parse, comparison mode,
fusion settings, optimization targets, export format) and execute it end-to-end via a
single `rmip batch run config.yaml` command. Enables automated nightly mechanism
benchmarking or CI-style quality gates on mechanism updates.

---

### Visualization

**19. Interactive Arrhenius Plot Builder**
For any set of reactions selected by the user (or all FUSE-class reactions), generate
interactive Arrhenius plots showing `k(T)` curves for each contributing mechanism, the
fused curve, and the `±3σ` uncertainty band. Pan/zoom, exportable as PDF-ready SVG.
Fills the gap between the current numerical comparison (M6) and communicating results.

**20. 3D Time-Evolving Mechanism Animation**
Using Cantera IDT simulation output, animate how species concentrations change over time
during ignition and overlay them on the 3D network graph (node size ∝ mole fraction at
each timestep). Creates an intuitive visual of what reactions "light up" during combustion
and at what timescale each pathway becomes dominant.

---

## FEATURE_ROADMAP_FROM_LITERATURE.md (all 8 phases shipped/committed/merged per project memory)

# Feature Roadmap — Literature Gap Analysis (2026-07-18)

A survey of what the combustion-kinetics community does across the full mechanism
lifecycle (development → validation → optimization/UQ → reduction → deployment),
cross-referenced against what this codebase actually implements, to identify major,
genuinely-missing, multi-session features.

**Scope note:** this is a *research + gap report*, not an implementation. Nothing here
is built. Each item lists: what it is, why it matters, its literature anchor, the
current state in this repo, and a rough effort band (S = 1 session, M = 2–4, L = 5+).

---

## What the codebase already does (baseline, so gaps are honest)

- **I/O**: CHEMKIN + Cantera-YAML read/write; thermo (NASA-7) + transport *reading*;
  SMILES glossary; experimental data via a **custom CSV/YAML** format.
- **Structure/analysis**: reaction-graph build, canonicalization, N-way comparison,
  mechanism **fusion** (consensus-mean + priority-pick), uncertainty bands, PLOG
  surface viz, NTC detector, reverse-rate unphysicality scanner, 2D/3D network viz.
- **Simulation**: IDT, JSR, PFR, LFS, RCM via Cantera / Zero-RK / FlameMaster bridges.
- **Sensitivity/UQ**: local sensitivity + integrated-flux scoring (graph attributes),
  Zero-RK **global SA** (Sobol/Morris via SALib), GSA↔PRS cross-check, forward UQ.
- **Reduction**: DRG, DRGEP, DRGPSA/DRGSA, PFA — i.e. the full **skeletal / directed-
  relation-graph family** (species+reaction elimination).
- **Optimization**: MUQ-SAC **PRS (polynomial response surface) + SLSQP gradient**
  single-objective optimization; MSO bounds.
- **Generation**: RMG interface **stub** (raises `NotImplementedError`), missing-species
  predictor.

Everything below is *absent or only stubbed*.

---

## The gaps (12 major features)

### A. Development & Data Foundation

**1. ReSpecTh / PrIMe standardized experimental-data ingestion (RKD XML) — effort M**
- *What*: an importer for the ReSpecTh Kinetics Data (RKD) XML format (spec v2.5, Apr
  2024) and the PrIMe XML it descends from, mapping `<experiment>` elements
  (shock-tube IDT, RCM, flame speed, JSR/flow-reactor speciation, with metadata,
  bibliography, and per-point uncertainties) onto this repo's target/`.opt` model.
- *Why*: the repo reads a **bespoke CSV/YAML** exp format, which locks it out of the
  field's shared validation corpus. ReSpecTh alone is ~111k data points across ~2,400
  XML files (H2, syngas, CH3OH, C2H5OH, CH4, …). One importer unlocks all of it as
  optimization/validation targets — this is the single highest-leverage data feature.
- *Lit*: Turányi & coworkers, ReSpecTh RKD format v2.5 (2024); descends from PrIMe.
- *Now*: `io/exp_data_reader.py` handles custom CSV/YAML only. No XML, no per-point
  uncertainty ontology, no bibliographic provenance.

**2. Automatic mechanism generation with group-additivity thermo + rate rules — effort L**
- *What*: RMG-style construction from reactant seed + reaction families: iterative
  species enumeration, **Benson group-additivity thermochemistry**, rate-rule/template
  database for k(T), and automatic pressure-dependence (chemically-activated paths).
- *Why*: the whole "development" half of the lifecycle is currently outsourced to a
  stub. Even a *thin* in-house generator (a few families + a small rate-rule library)
  would let the suite extend/patch mechanisms rather than only consume them.
- *Lit*: Gao/Green et al., *Reaction Mechanism Generator* (RMG v3.0); Benson group
  additivity; recent biofuel/halocarbon extensions (2022–2024).
- *Now*: `generation/rmg_interface.py` + `stubs.py::PathwayCompleter` both stubbed;
  no rate-rule DB, no group-additivity engine.

**3. Thermochemistry estimation + NASA-7/9 fitting + thermodynamic-consistency repair — effort M**
- *What*: (a) estimate Cp/H/S for a new/under-specified species (group additivity or a
  data-driven surrogate), (b) **fit NASA-7/9 polynomials** from tabulated Cp/H/S with
  Tmid-continuity constraints, (c) a *repair* pass that enforces detailed balance so
  solver-derived reverse rates stay physical.
- *Why*: fusion/generation routinely introduce species lacking clean thermo; the repo
  can currently only *flag* the resulting bad reverse rates (`reverse_rate_scanner.py`),
  not *fix* them, and can't fit thermo at all.
- *Lit*: Benson additivity; NASA polynomial conventions; detailed-balance consistency
  is a standard mechanism-QA step.
- *Now*: `parameter_estimator.py` averages Arrhenius params and checks thermo
  *continuity*; no group-additivity estimation, no NASA fitting, no consistency *repair*.

**4. Transport-property estimation from molecular structure — effort S/M**
- *What*: estimate Lennard-Jones σ, ε (and dipole/polarizability) for species missing a
  transport entry, from structure/critical-property correlations, so a fused or
  generated mechanism is flame-speed-ready.
- *Why*: LFS and any diffusive simulation silently fail or fall back to bad defaults
  when a species has no `.tran` data — a common post-fusion state.
- *Lit*: RMG's transport-estimation module; standard LJ correlations.
- *Now*: transport is *parsed* but never *estimated* (grep: only reader + fixtures).

### B. Optimization & Uncertainty Quantification

**5. Bound-to-Bound Data Collaboration (B2BDC) feasible-set optimization — effort L**
- *What*: the Frenklach/Packard/Wang framework — build quadratic/rational surrogates per
  target, define the **feasible parameter set** consistent with *all* experimental
  uncertainty bounds, run **dataset consistency analysis** (is the collective data even
  self-consistent?), and do prediction on the feasible set.
- *Why*: this is *the* alternative paradigm to the repo's single-objective gradient
  optimization — it yields guaranteed-consistent bounds and can *detect* mutually
  contradictory experiments, which weighted-least-squares silently averages away.
- *Lit*: Frenklach et al., "Optimization of combustion kinetic models on a feasible
  set"; "Consistency Analysis for Massively Inconsistent Datasets in B2BDC" (2017).
- *Now*: absent. Optimization is PRS + SLSQP single weighted objective only.

**6. Bayesian / MCMC calibration + MUM-PCE uncertainty minimization — effort L**
- *What*: full posterior inference over rate parameters (MCMC or the **Method of
  Uncertainty Minimization using Polynomial Chaos Expansions**, MUM-PCE), producing not
  just an optimum but a *calibrated covariance* — accuracy **and** precision.
- *Why*: the repo produces a point estimate + forward UQ, but never a **posterior**;
  it can't answer "how much did these data actually constrain each parameter, and how
  are the constrained parameters correlated?"
- *Lit*: Sheen & Wang (MUM-PCE); recent NN-MUM-PCE surrogate scaling (2024); Bayesian
  combustion-kinetics inference is now standard.
- *Now*: absent. PRS surrogate exists but is used for deterministic optimization, not
  posterior sampling or covariance minimization.

**7. Polynomial-Chaos surrogates with analytic Sobol + active-subspace reduction — effort M**
- *What*: build generalized-PCE surrogates whose coefficients give **analytic** Sobol
  indices and variance decomposition for free; add **active-subspace** discovery to
  find the low-dimensional combination of rate parameters that actually drives a target.
- *Why*: the repo computes Sobol indices by *sampling* (Zero-RK GSA / SALib) — expensive
  and per-target. gPC gives them analytically from one fit; active subspaces then cut a
  50-parameter problem to the ~3 directions that matter (huge for optimization + DoE).
- *Lit*: active-subspace dimension reduction for chemical kinetics (Constantine
  lineage); gPC → analytic Sobol; multi-fidelity PCE (2024).
- *Now*: PRS surrogate + sampled Sobol only; no gPC basis, no active subspaces.

**8. Optimal experimental design (which experiment to run next) — effort M**
- *What*: given the current model + uncertainty, rank *candidate* experiments (T, P, φ,
  diluent, target type) by expected information gain / uncertainty reduction (D-optimal
  or active-subspace-similarity design), to guide data collection.
- *Why*: closes the loop — the suite can already *use* data and *quantify* uncertainty;
  it can't yet say *"the LFS point at 20 atm / φ=1.3 would shrink your posterior most."*
- *Lit*: "Using active subspace-based similarity analysis for design of combustion
  experiments" (2022); classical D-/A-optimal design.
- *Now*: absent.

**9. Multi-objective / Pareto optimization across target classes — effort M**
- *What*: replace (or augment) the single weighted objective with a Pareto front over
  competing target families (IDT vs LFS vs speciation vs RCM), exposing trade-offs
  instead of hiding them in one weight vector.
- *Why*: real mechanisms can't fit every target class at once; a weighted sum forces a
  hidden compromise. A Pareto front makes the trade-off explicit and choosable.
- *Lit*: multi-objective evolutionary optimization is common in surrogate-fuel model
  building; complements B2BDC's consistency view.
- *Now*: MUQ-SAC uses a single SLSQP objective.

### C. Reduction (beyond skeletal)

**10. Chemical/isomer lumping + QSSA analytic reduction + CSP timescale analysis — effort L**
- *What*: the "second stage" of reduction the repo is missing entirely: **chemical
  lumping** (merge isomers/similar species into pseudo-species with fitted lumped
  rates), **QSSA** (algebraically eliminate short-timescale species → analytic reduced
  mechanism), and **CSP** (computational singular perturbation) to *identify* QSS species
  and exhausted modes automatically.
- *Why*: DRG/DRGEP/PFA (all present) produce *skeletal* mechanisms (fewer species, same
  form). Lumping + QSSA get the *order-of-magnitude* further reduction needed for CFD,
  and CSP is the principled way to choose what to lump/eliminate.
- *Lit*: Lu & Law (QSSA-via-lumping, DRG family); Matrisciano et al. thermodynamic
  chemical lumping (2022); Valorani/Goussis CSP; recent ML-based lumping (2023).
- *Now*: `reduction/` is DRG/DRGEP/DRGPSA/PFA only — no lumping, no QSSA, no CSP.

**11. Skeletal-vs-detailed error mapping + adaptive chemistry (TDAC) — effort M/L**
- *What*: (a) systematically map a reduced mechanism's error against the detailed one
  across the whole (T, P, φ) design space with a worst-case guarantee, and (b) **tabulated
  dynamic adaptive chemistry** — on-the-fly per-cell reduction for CFD deployment.
- *Why*: reduction today is one-shot at a threshold; there's no coverage map telling you
  *where* the skeletal model breaks, and no runtime path to actually deploy it in a solver.
- *Lit*: DRGEP+PCA with error control (HCCI); TDAC / on-the-fly reduction literature.
- *Now*: reducers report a threshold-based reduction but no space-filling error atlas,
  no adaptive-chemistry runtime.

### D. Diagnostics & Validation

**12. First-class Rate-of-Production / reaction-path-flux diagnostics — effort S/M**
- *What*: for a chosen condition and time (or integrated over ignition), rank reactions
  by their contribution to a target species' production/consumption, trace dominant
  **reaction pathways**, and render an element-flux pathway diagram — the standard
  "why does this mechanism do X" tool.
- *Why*: the repo has `flux_score` as a *graph node attribute* fed from an external
  wrapper, but no first-class ROP tool a user can point at a condition. Cantera exposes
  the raw rates already, so this is mostly orchestration + a good diagram — high value,
  modest cost.
- *Lit*: ROP analysis + element-flux/path-flux pathway analysis are the universal
  mechanism-diagnostic toolset (also the physical basis of PFA/DRG).
- *Now*: only the normalized `flux_score` attribute in `analysis/sensitivity.py`; no
  condition-specific ROP/pathway tool.

---

## Suggested priority (impact ÷ effort)

1. **#12 ROP / path-flux diagnostics** (S/M) — high value, cheap, unblocks everything else.
2. **#1 ReSpecTh/PrIMe ingestion** (M) — unlocks the field's whole validation corpus.
3. **#4 Transport estimation** (S/M) — small, removes a real post-fusion failure mode.
4. **#3 Thermo fitting + consistency repair** (M) — pairs with the existing reverse-rate scanner.
5. **#7 gPC + active subspaces** (M) — cheaper, exact Sobol; foundation for #6 and #8.
6. **#6 Bayesian/MUM-PCE** (L) and **#5 B2BDC** (L) — the two flagship optimization paradigms.
7. **#10 lumping/QSSA/CSP** (L) — the missing half of reduction.
8. Remainder (#2 generation, #8 DoE, #9 Pareto, #11 error-map/TDAC) as follow-ons.

---

## Sources

- Frenklach et al., *Optimization of combustion kinetic models on a feasible set* (B2BDC feasible-set optimization).
- *Consistency Analysis for Massively Inconsistent Datasets in Bound-to-Bound Data Collaboration*, arXiv:1701.04695.
- Sheen & Wang, MUM-PCE; *Facilitating Bayesian analysis of combustion kinetic models with artificial neural network* (NN-MUM-PCE), Combustion & Flame.
- *Active subspace-based dimension reduction for chemical kinetics applications with epistemic uncertainty*.
- *Using active subspace-based similarity analysis for design of combustion experiments*, Proc. Combust. Inst. (2022).
- Gao et al., *Reaction Mechanism Generator: Automatic construction of chemical kinetic mechanisms*; *RMG v3.0*.
- *Automatic mechanism generation for the combustion of advanced biofuels: diethyl ether*, Int. J. Chem. Kinet. (2024).
- ReSpecTh Kinetics Data Format Specification v2.5 (2024), ELTE (respecth.elte.hu/rkdformat); *ReSpecTh: Reaction kinetics, spectroscopy, and thermochemical datasets*, PMC12174324.
- Matrisciano et al., *An a priori thermodynamic-data chemical lumping method for reduction of large kinetic mechanisms*, Int. J. Chem. Kinet. (2022).
- *An automatic procedure for the simplification of chemical kinetic mechanisms based on CSP* (Valorani/Goussis lineage).
- Lu & Law, *The application of the QSSA via reaction lumping for the reduction of complex hydrocarbon oxidation mechanisms*, Proc. Combust. Inst.
- *A path flux analysis method for the reduction of detailed chemical kinetic mechanisms* (PFA / ROP basis).

---

## GUI_STRESS_TEST_PLAN.md (self-declared STATUS: COMPLETED, confirmed 2026-07-19; superseded by tests/test_gui_stress_sweep.py)

# GUI stress-test plan — every app, one at a time, dummy files only

> **STATUS: COMPLETED (confirmed 2026-07-19).** This plan has been fully executed. The
> shared fixture set exists at `src/rmip/tests/fixtures/gui_stress/` (built by
> `make_gui_stress_fixtures.py`), and `src/rmip/tests/test_gui_stress_sweep.py` runs an
> in-process worker-function sweep for **all 8** launcher GUIs — 17 tests, all passing
> (~111 s), committed in `c88ccb3`. Coverage highlights matching §3/§4 below:
> mechanism_converter (golden + Fortran-exponent/CRLF auto-fix + self-contained-thermo),
> brute_force_sa (B12 re-verified + full SA run), nominal_sim (B14 + full run),
> mean_value_fusion (golden + divergent-kinetics), uncertainty_generator (Generate→Collapse
> round-trip), forward_uq (**B13 doubled-path fixed** + full run with a synthesized PRS
> cache), mso_compare (**M24** CWD race exercised with ≥2 concurrent workers), rmip_suite
> (all 4 tabs incl. previously-zero-coverage GSA + Active-Param). The soln2ck retry-mask
> defect flagged in `bug.md` during this plan's real-mechanism tier is also fixed
> (`test_soln2ck_retry_mask.py`). The original per-app procedure is retained below as the
> reference for any future re-sweep.

Written 2026-07-17. Scope: the 8 standalone GUI apps produced by the 2026-07-11→17 split of
`generate_target_opt.py` (see `MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md`).
This plan supersedes `PLAN.md` Priority 2 (folds it in) and replaces the "sweep the other 5 GUIs"
one-liner with a real per-app procedure, since two apps (`mean_value_fusion_gui.py`,
`uncertainty_generator_gui.py`) already went through one round of this and it found 3 real bugs
(`MarkDownFiles/HISTORY/part43_done.md`) — the same rigor should apply to the rest, and those two
should get a second pass rather than being marked "done forever."

**Ground rule carried over from the last stress test:** never drive the literal Tk display unless
you have first confirmed, this session, that display `:52.0` is not shared with another live agent
session. A misdirected click during the 2026-07-17 fusion-GUI test landed on a different session's
terminal window (see `progress.md`'s open questions). Default to calling each GUI's own worker
functions in-process (`_run_*`, `_on_*`, etc.) — same code path a button click would trigger, just
invoked directly — and say explicitly in the writeup that this was done in-process, not via literal
widget clicks. Only fall back to real widget-driving if the user confirms the display is safe to use.

---

## 1. Dummy fixtures — build once, reuse across every app

Rather than hand-crafting a new dummy mechanism per app test (as Part 43 did, ad hoc, and didn't
persist), build a small, checked-in fixture set once, under `src/rmip/tests/fixtures/gui_stress/`,
so every app test in this plan reads from the same known-good dummy data and results are comparable
run to run:

1. **Three dummy CHEMKIN mechanisms**, same shape as Part 43's (real H2/O2 chemistry, ~8 species /
   ~8 reactions each), each with every species spelled completely differently (zero string overlap,
   forcing SMILES/InChI-only identity resolution) and a deliberate overlap structure: 1 reaction
   common to all 3, 2 reactions shared between exactly 2 of 3, the rest unique per mechanism. This is
   the structure that already found the `ChemkinWriter` species-staleness bug — keep it, don't
   simplify it away.
2. A **matching glossary** giving 100% `glossary_matched` hit rate on all three (Part 43 built one
   ad hoc; persist it this time).
3. A **dummy `target.opt`/.target/.add trio** with a handful of `Tig`/`JSR`/`RCM` targets pointed at
   one of the three dummy mechanisms, small enough to run in seconds through Zero-RK/Cantera — needed
   for the apps that consume `.target`/`.opt` files directly (Brute-Force SA, Forward UQ, Nominal
   Sim, MSO Compare, RMIP Suite's GSA/Active-Param tabs).
4. A **dummy uncertainty XML** (already exists: `src/rmip/tests/fixtures/h2_o2_crosscheck_unsrt.xml`
   — reuse, don't recreate) for Uncertainty Generator's "collapse" path.
5. Reuse the already-produced fused outputs (`outputs/fusion/Fused_Mech.{inp,yaml,dat}`,
   `outputs/fusion_keromnes_li_davis/{mean_unsrt,priority}/*.inp`) as a second, larger/more-realistic
   fixture tier once the dummy-fixture pass is clean — real mechanisms exercise scale and naming
   quirks the minimal dummies won't.

Write a single `make_gui_stress_fixtures.py` (or extend the existing dummy-generation code already
proven in `test_chemkin_writer_species_staleness.py`) that regenerates all of the above
deterministically, so the fixture set can be rebuilt if it ever needs to change shape.

## 2. Per-app procedure (apply identically to every app below)

For each app:
1. Read the app's `argparse` entry point and worker function(s) that a "Run"/"Generate"/"Compare"
   button ultimately calls.
2. Point it at the dummy fixtures from §1 (or a `--target-opt`/`--db` dummy set, per the app).
3. Invoke the worker function(s) in-process, covering: the golden path, at least one deliberately
   malformed/missing-input edge case (per the app's own known failure modes below), and — if the app
   has one — the "Run" button's subprocess/PTY path specifically, since M27 (`bug.md`) already flags
   PTY fd/zombie leaks and a reader-thread race across all 5 terminal-backed apps as a known risk
   class to watch for while here, not just re-read about. (M27 itself — fd/zombie leak,
   reader-thread race, no scrollback, no close guard — is now fixed in
   `src/gui_common/pty_terminal.py` as of 2026-07-20; see `bug.md`'s M27 entry.)
4. Confirm output files/DB rows are actually produced and correct (open and check content, don't
   just check exit code / no-exception).
5. Log any real bug found immediately into `bug.md` (if not fixed same-session) or `BUG.md` +
   `progress.md` (if fixed same-session) — don't accumulate findings only in memory across a long
   session, per the flush-to-disk lesson already in project memory.

## 3. Apps, in recommended order (cheapest verification / highest known risk first)

1. **`mechanism_converter_gui.py`** — never stress-tested at all (built same session as the 2026-07-12
   plan, after the plan was written, no monolith equivalent to compare against). Test CHEMKIN→YAML,
   CHEMKIN→`.pre`, CHEMKIN→DB against all 3 dummy mechanisms, plus the Fortran-exponent/CRLF
   auto-fix paths it specifically claims to handle — construct a dummy `.inp` with a deliberately
   broken exponent (`1.7+13`) and CRLF line endings to actually exercise the auto-fix, not just the
   clean-input path.
2. **`brute_force_sa_gui.py`** — B12 (doubled relative path crash) is marked resolved in `BUG.md`;
   re-verify it's still fixed and hasn't regressed, then exercise a full SA run against the dummy
   `.opt` trio from §1.3.
3. **`nominal_sim_gui.py`** — same: B14 marked resolved, re-verify, then a full run.
4. **`mean_value_fusion_gui.py`** — second pass. Part 43 already found and fixed real bugs here;
   re-run the same dummy-mechanism fusion end-to-end to confirm no regression, then extend coverage
   to whatever wasn't exercised the first time (check `part43_done.md` for exactly what was and
   wasn't covered — it does not mention testing the priority-pick fusion mode specifically, only
   mean/uncertainty mode, so add that).
5. **`uncertainty_generator_gui.py`** — second pass, same reasoning. Part 43 ported
   `generate_uncertainty_xml()` in; confirm the "Generate" path produces a well-formed XML the
   "Collapse" path can then correctly re-read (round-trip test), not just that each half works in
   isolation.
6. **`forward_uq_gui.py`** — **B13 is still open** (`bug.md`): "Run" can essentially never succeed
   (doubled path + hard-required `Opt/`/`DM_FOR_PARTIAL_PRS/` dirs). Fix this while sweeping the app,
   don't just re-document the same crash a third time. Once fixed, exercise a real forward-UQ run
   against the dummy fixtures.
7. **`mso_compare_gui.py`** — never tested. Watch for M24 (`pipeline.py`'s `ThreadPoolExecutor` +
   per-worker `os.chdir()` CWD race) while here — a multi-mechanism dummy run with ≥2 concurrent
   workers is the natural way to actually trigger this, so don't dodge concurrency in the test setup.
8. **`rmip_suite_gui.py`** — never tested, biggest surface (4 internal tabs: graph viz/comparison,
   mechanism reduction, Global Sensitivity Analysis, Active Parameter Selection). Test each internal
   tab separately against the dummy fixtures; GSA and Active-Param-Selection specifically had **zero
   GUI coverage ever**, per the original split plan (section 1.2), so budget the most time here.

## 4. Exit criteria

All 8 apps have a same-session (or explicitly-superseding) in-process worker-function run recorded
in `progress.md`, against the shared dummy fixtures from §1, with actual output verified (not just
"didn't crash"). Any bug found is either fixed with a regression test (preferred, matching Part 43's
pattern) or logged in `bug.md` with a clear repro if fixing is out of scope for the pass. Once all 8
are clean, do one larger-scale pass against the real fused mechanisms (§1.5) as a second tier —
dummy fixtures catch logic bugs cheaply, but scale/real-naming quirks (long species names, unusual
third-body syntax, etc.) only show up on real data.

## 5. Relationship to other open plan items

This plan is Priority 2 of `PLAN.md`, expanded. Priority 0 (data-integrity bugs) should still be
done first where feasible since some of them (M10, M14) affect the same fusion/comparison code paths
these GUI tests exercise — a GUI test built on top of a still-buggy backend will just rediscover
already-known bugs instead of finding new GUI-layer ones. Not a hard blocker, but worth sequencing
Priority 0 before or alongside this plan rather than strictly after.

---

## MarkDownFiles/ZERORK_GSA_PLAN.md (2026-07-11 PLANNING ONLY doc — fully shipped, see HISTORY.md parts 22-34)

# Zero-RK Integration + Global Sensitivity Analysis — Implementation Plan

Written: 2026-07-11. Status: **PLANNING ONLY — nothing in this document has been implemented.**

---

## 0. The decision this plan is built on

**Question asked:** build fast in-house solvers + GSA (Julia/C++, reimplementing what Zero-RK does),
or wrap Zero-RK and build GSA on top?

**Decision (confirmed with KP):** wrap Zero-RK. Do not reimplement its solvers.

**Why:** Zero-RK's value is ~15 years of LLNL engineering on analytical sparse Jacobians, PSR/PFR/
batch-reactor formulations, and combustion-specific CVODE/KINSOL tuning for large mechanisms —
not the ODE-solver algorithm itself, which Julia's `Sundials.jl`/`DifferentialEquations.jl` could
provide in an afternoon. The hard, slow-to-build part (accurate sparse Jacobians generated directly
from a reaction mechanism, validated reactor physics) is exactly what already exists, is open
source, BSD-3-Clause licensed, and is sitting on disk. Rebuilding it would be a multi-month-to-
multi-year detour to re-derive something already correct.

**GSA scope (confirmed with KP):** extend the existing brute-force `src/Sensitivity_Analysis/`
codebase and the existing `src/forward_uq/` codebase, **and** bring in Zero-RK's own GSA-related
capability. This plan does all three, and is explicit about where they meet.

---

## 1. Ground truth — what's actually here today

Gathered by direct inspection this session (not from memory of Zero-RK's public docs). File paths,
class names, and algorithms below are all verified against the live source, not assumed.

### 1.1 Zero-RK itself (`/home/krithika/zero-rk/`)

- **Source is present, NOT built.** A prior `cmake` configure was started (`build/CMakeCache.txt`
  exists, `ENABLE_MPI=ON`, `MPI_CXX_COMPILER=/home/krithika/anaconda3/bin/mpicxx`,
  `CMAKE_INSTALL_PREFIX=/home/krithika/zero-rk/build/inst_dir` — a local, non-system path, no
  sudo needed) but got no further than partially building `superlu` (`libsuperlu.a` exists).
  `superlu_dist`, SUNDIALS, and the actual zerork library/applications were never built — **zero
  `.x` binaries exist anywhere in the tree.** This confirms KP's note: Zero-RK is not installed.
- **Toolchain check (this machine):** `cmake` 3.x, `gfortran`, `g++` 10.5, MPI (`mpicxx`/`mpicc`/
  `mpirun` via anaconda) — all present and sufficient. `julia` 1.10.11 also present but irrelevant
  now that the reimplementation path is declined. 520 GB free disk, 160 CPUs, 251 GB RAM — no
  resource constraint for building or for running large MPI sample batches later.
- **What Zero-RK's applications actually are** (confirmed by reading source, not assumed):

  | App | Physical config | Sensitivity/GSA behavior |
  |---|---|---|
  | `constVolumeWSR` | 0-D constant-volume ignition delay (IDT), the core "shock-tube-like" solver | none |
  | `constVolumeWSR_TLA` | same, **plus a bespoke Tangent-Linear-Approximation (TLA) local-sensitivity pass** | see 1.1.1 below — this is the one genuinely cheap sensitivity mechanism in Zero-RK |
  | `constVolumePSR` | 0-D perfectly-stirred reactor (JSR), prescribed residence time | none |
  | `variable_volume` / `variable_volume_gsa` / `variable_volume_batch` | 0-D reactor with prescribed volume-vs-time history (RCM) | GSA variant = brute-force MC batch, see 1.1.2 |
  | `premixedSteady` / `premixedUnsteady` | 1-D laminar premixed flame (flame speed) | `premixedSteady` has an optional brute-force OAT flame-speed sensitivity block |
  | `counterflowSteady`/`Unsteady`, `diffusionSteady`/`Unsteady` | 1-D counterflow premixed/diffusion flames, extinction strain-rate sweeps | none |
  | `perturbAFactor` | **not a reactor** — OAT local-sensitivity driver, wraps `constVolumeWSR`'s IDT solve | true brute-force OAT (see 1.1.3) |
  | `perturbAFactorGSA` | **not a reactor** — MC batch driver, wraps `constVolumeWSR`'s IDT solve | brute-force MC batch (see 1.1.2) |

  **No PFR (plug-flow reactor) application exists in Zero-RK.** RMIP's PFR targets (via
  `MuqsacBridge`/`create_input_file`'s cantera/CHEMKIN_PRO/FlameMaster branches) have **no Zero-RK
  acceleration path** — this is a real, permanent gap, not a to-do. PFR stays on existing solvers.

- **1.1.1 — TLA (`constVolumeWSR_TLA`), the one cheap sensitivity mechanism.** After the forward
  IDT integration, it checkpoints states, re-evaluates the already-computed analytical sparse
  Jacobian at each checkpoint, and solves **one additional linear tangent-sensitivity ODE for ALL
  reactions simultaneously** (trapezoidal stepping using the already-factored Jacobian) — i.e. one
  extra *linear* pass, not N extra *nonlinear* solves. Outputs relative IDT sensitivity
  `S_k = -1/tau · (dT/dξ_k)/(dT/dt)` per reaction to `sensAnalysis_IDT_run###.txt`. Limitations:
  constant-volume IDT only, and only for the largest `idtTemps` threshold (code prints a warning
  otherwise). This is architecturally the same idea as `rmip/simulation/sensitivity_runner.py`'s
  `CanteraSensitivityRunner.run_idt()` (Cantera's native CVODES forward-sensitivity, also cheap,
  also single-condition) — Zero-RK's TLA is a hand-rolled analog for a solver that doesn't use
  CVODES' sensitivity API. **No CVODES `CVodeSensInit`-based forward sensitivity analysis (FSA)
  exists anywhere in Zero-RK** (confirmed by grep — `cvodes` headers are linked in a couple of apps
  but only for quadrature integration, not the sensitivity-equation API).

- **1.1.2 — `perturbAFactorGSA` / `variable_volume_gsa`, the "GSA" apps.** These are **MPI
  master/worker Monte Carlo batch runners, not index-computing GSA tools.** You supply a plain-text
  `gsaMatrixFile` (rows = samples, columns = reactions, each entry an A-factor multiplier — you
  generate this matrix yourself, e.g. via the shipped `create_lognormal_mtx.py`/
  `create_bruteforce_mtx.py` examples); the app runs one full nonlinear IDT (or RCM) solve per row,
  in parallel across MPI ranks, and dumps a raw table (`task_id, cpu_time, idt[1..nRoots]`) plus an
  input-distribution-only diagnostic file (min/max/log-mean/log-stdev of the sampled multipliers —
  **no correlation with the output, no Sobol/Morris index, computed in-code**). Cost scales as
  O(num_samples) full nonlinear solves — this is brute-force Monte Carlo, just parallelized and
  fast per-solve thanks to Zero-RK's sparse Jacobian. **The actual GSA statistics (Sobol/Morris/
  regression indices) must be computed by us, in Python, from the raw output** — this is the
  concrete gap Phase 3 below fills.

- **1.1.3 — `perturbAFactor`, true OAT.** Perturbs exactly one reaction's A-factor at a time (fixed
  multiplier, default 2×, optional `doBothDir` for two-sided central difference), `nRxn` (or
  `2×nRxn`) + 1 total solves. Has both serial and MPI binaries. **A-factor only** — no n/Ea
  perturbation support in Zero-RK's own apps (unlike `sens_3_params.py`'s 3-parameter approach —
  see Phase 2's design choice on this).

- **No Python bindings exist** (no pybind11/ctypes/SWIG). `python/zerork/` is 100% subprocess +
  YAML, wrapping compiled `.x` binaries (`rate_opt/cv_opt.py` is the cleanest reference example —
  writes YAML from a template, calls the binary via `subprocess`, parses text output). This is
  **the same interaction pattern already used everywhere else in this codebase**
  (`MuqsacBridge`, CHEMKIN_PRO/FlameMaster dispatch in `make_input_file.py`) — no new integration
  paradigm needed, just another subprocess-and-file-contract backend.

### 1.2 RMIP-suite side — what already exists to extend

- **`src/Sensitivity_Analysis/sens_3_params.py`** — the actively-maintained, GUI-wired ("Run SA"
  button → embedded PtyTerminal) brute-force local SA tool. Perturbs **each reaction's A, n, Ea
  independently** (forward- or central-difference), ~3N+1 or ~6N+1 full simulations per target
  case. Solver is chosen **per target** via `target.add["solver"]` (`cantera`/`CHEMKIN_PRO`/
  FlameMaster today), dispatched through `simulation_manager2_0.py`'s parallel worker pool
  (thread-capped via `chem_data.thread_cap()`). This per-target solver dispatch is the exact seam
  Zero-RK plugs into (Phase 2).
  - `sens.py` (older, single-global-A-factor OAT) is legacy/superseded — not touched by this plan.
  - `src/Sensitivity_Analysis/ResponseSurface.py` — PRS fit + closed-form uncertainty propagation
    (order-3/4/5 bug already fixed this session, unrelated to this plan).
- **`src/forward_uq/` + root `forward_uq.py`** — a *separate*, already-cheap GSA pipeline:
  `MCPropagator` samples the uncertain-parameter prior via `MUQ-SAC/qmc_sampling.py`
  (`joint_uniform_block`, Sobol/LHS/numpy methods) and evaluates a **pre-trained PRS surrogate**
  (milliseconds, no solver re-runs), then `AnalyticalSobolPRS` computes first-order/total-order
  Sobol indices analytically from the order-2 PRS coefficients (closed-form ANOVA decomposition,
  no extra sampling needed for the indices themselves). This is genuinely cheap **because it never
  touches the real solver after PRS training** — the cost is all paid up front when
  `src/MUQ-SAC/run_script.py`'s optimization pipeline generates the training simulations that
  `sens_3_params.py`/`DesignMatrix.py`-style workflows produce. **Making those training-simulation
  runs faster (Zero-RK) directly speeds up this whole pipeline**, even though this pipeline itself
  needs no Zero-RK integration to function.
  - ⚠️ Divergence flagged: `src/MUQ-SAC/ResponseSurface.py` (consumed by `forward_uq.py`'s
    `load_prs_from_cache`) and `src/Sensitivity_Analysis/ResponseSurface.py` (consumed by
    `sens_3_params.py`) have diverged in constructor signature. This plan treats
    `MUQ-SAC/ResponseSurface.py` as canonical for anything touching the `forward_uq.py` pipeline.
- **`src/rmip/simulation/sensitivity_runner.py`** — `CanteraSensitivityRunner.run_idt()`, Cantera's
  **native** CVODES-based forward sensitivity (`add_sensitivity_reaction` + `ReactorNet.sensitivity()`)
  — already cheap, already correct, single-condition, all reactions in one integration pass. No
  `run_lfs()` exists (confirmed absent, not just misnamed — flagged as a pre-existing gap, out of
  scope here unless you want it added). Feeds `DRGPSAReducer`/`DRGSAReducer` (both actually live in
  `reduction/drgpsa.py`, not two separate files as sometimes assumed).
- **`src/rmip/stubs.py` — `DoEFramework` (M9), already-designed, unimplemented.** This is the
  **correct landing spot for the new GSA implementation** — its docstring already specifies:
  Sobol/LHS screening design, **SALib** for Morris/Sobol indices (`run_screening()` return contract
  is literally `{canonical_key: {"S1": float, "S1_conf": float, ...}}` — a SALib-shaped result),
  and a `prepare_mso_input()` hand-off to MSO with SA-based parameter screening
  (`|SA coefficient| < 0.01` cutoff, already specified). We don't need to invent an API — we need
  to implement the one already designed.
- **No DB schema exists** for SA runs, Sobol indices, or design matrices (`sensitivity_runs`,
  `sobol_indices`, `design_matrices` tables all absent from `migrations.py`/`schema*.py`;
  `forward_uq.py` only writes flat CSVs today, nothing to the SQLite DB). Needs new migrations +
  `types.py` dataclasses, following the `reduction_runs`/`ReductionResult` pattern already
  established in Phase 5B.
- **No `gsa`/`sobol`/`doe` CLI subcommand exists.** Closest neighbors: `sa-run` (Cantera local SA),
  `reduce` (DRG family, already consumes SA JSON).
- **Dependencies not yet installed:** `SALib` (needed — this is what `DoEFramework.run_screening()`
  is designed around) and `mpi4py` (needed only if we want fine-grained Python-side control over
  Zero-RK's MPI batch jobs beyond plain `subprocess.run(["mpirun", ...])`, which may not be
  necessary — see Phase 3's open question). `ruamel.yaml`, `pyDOE`, `dill` are already installed.

---

## 2. Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │  rmip/simulation/zerork_bridge.py  (NEW)      │
                    │  subprocess + YAML contract, same shape as    │
                    │  muqsac_bridge.py (D7 principle: never import │
                    │  Zero-RK internals, only call its .x binaries)│
                    └───────────────┬───────────────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │                            │                            │
┌───────▼────────┐         ┌─────────▼─────────┐        ┌─────────▼──────────┐
│ Phase 2:         │         │ Phase 3:            │        │ Phase 4:             │
│ Zero-RK as a new │         │ DoEFramework.        │        │ forward_uq.py PRS    │
│ solver= option   │         │ run_screening()       │        │ pipeline speedup     │
│ in sens_3_params/│         │ implemented via       │        │ (indirect — faster   │
│ simulation_       │         │ SALib sampling +      │        │ training sims feed   │
│ manager2_0.py     │         │ perturbAFactorGSA's    │        │ existing PRS/Sobol)  │
│ (brute-force OAT, │         │ MPI batch machinery    │        │                      │
│ existing codebase)│         │ (new GSA, new codebase)│        │                      │
└───────────────────┘         └────────────────────────┘        └──────────────────────┘
```

Key principle carried over from the rest of this codebase (D7, `MuqsacBridge`'s own docstring):
**never import Zero-RK internals. Subprocess + file contract only.** Zero-RK is C++/MPI; there is
no Python binding to import even if we wanted to.

---

## 3. Phased plan

### Phase 0 — Build & install Zero-RK — ✅ DONE (2026-07-11)

**Install prefix: `/home/krithika/zero-rk/build2/inst_dir/bin/`** — this is the path Phase 1's
`zerork_bridge.py` should reference. The original stale `build/` dir was left untouched (not
deleted, per the earlier confirm-before-delete note); all real work happened in a fresh `build2/`.

**What actually happened, differs from the plan's assumptions in two important ways — both found
and fixed this session:**

1. **`-DSYSTEM_SUNDIALS_ROOT=/usr` doesn't work here — use it anyway, but only after checking a
   capability requirement, not just build speed.** System SUNDIALS is 3.1.2 (`libsundials-*3`
   packages) and its libraries weren't even found via `find_library` (all `-NOTFOUND` in
   `CMakeCache.txt`) — moot anyway, because **`constVolumeWSR_TLA` (the TLA sensitivity solver this
   whole plan leans on) and the counterflow flame solvers are silently `disabled for
   SUNDIALS_VERSION!=5`** at configure time (confirmed in the configure log: `constVolumeWSR_TSA
   solver disabled...`, `unsteadyCounterFlow Flame solver disabled...`,
   `steadyCounterFlow Flame solver disabled...`). Used `-DSUNDIALS_VERSION=5` (default, builds from
   source) instead — ~10 min build, not the slow multi-tens-of-minutes worst case, on this box's
   160 cores.
2. **Anaconda's `mpicc`/`mpicxx` are broken for this build** — they invoke a conda-specific
   compiler shim (`x86_64-conda_cos6-linux-gnu-cc`) that isn't installed/on PATH, causing the nested
   SUNDIALS `ExternalProject` sub-build to fail with `command not found`. Worse: passing
   `-DMPI_C_COMPILER=/usr/bin/mpicc` at the top level does **not** propagate into that sub-build
   (`cmake/sundials.cmake`'s `ExternalProject_Add` only forwards `CMAKE_INSTALL_PREFIX`, nothing
   else) — the sub-build does its own `find_program`, which resolves `mpicc` via `PATH`, and
   anaconda's bin dir sits before `/usr/bin` in this shell's `PATH`. Fix: prepend `/usr/bin:/bin` to
   `PATH` for the `cmake` configure invocation itself, not just pass compiler flags.
3. **`-DSYSTEM_SUPERLU_ROOT=/usr` fails to compile anything that includes SuperLU headers** —
   Zero-RK's `cmake/superlu.cmake` sets `INTERFACE_INCLUDE_DIRECTORIES` to
   `${SYSTEM_SUPERLU_ROOT}/include` (i.e. flat `/usr/include`), but Ubuntu's `libsuperlu-dev`
   package installs headers under `/usr/include/superlu/` — every application including
   `cv_param_sparse.h` (which does `#include <slu_ddefs.h>`) fails with `slu_ddefs.h: No such file
   or directory`. This is a real packaging-layout mismatch in Zero-RK's own CMake code, not
   something to route around with a flag. Fix: don't use `SYSTEM_SUPERLU_ROOT`/
   `SYSTEM_SUPERLU_DIST_ROOT` at all — let Zero-RK build both from source (fast, small libraries,
   ~1-2 min combined).

**Working configure command** (system SuperLU/SUNDIALS are both bypassed for the reasons above):
```bash
cd /home/krithika/zero-rk/build2
PATH="/usr/bin:/bin:$PATH" cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo \
         -DENABLE_MPI=ON \
         -DMPI_C_COMPILER=/usr/bin/mpicc \
         -DMPI_CXX_COMPILER=/usr/bin/mpicxx \
         -DCMAKE_INSTALL_PREFIX=$PWD/inst_dir \
         -DSUNDIALS_VERSION=5
PATH="/usr/bin:/bin:$PATH" make -j155  &&  make install
```

**Validation results (all passed):**
- `ctest`: **145/145 tests passed**, 0.82s total.
- **50 binaries built**, including every application this plan depends on:
  `constVolumeWSR[_mpi].x`, `constVolumeWSR_TLA[_mpi].x`, `constVolumePSR[_mpi].x`,
  `perturbAFactor_serial.x`/`perturbAFactor_mpi.x`, `perturbAFactorGSA_mpi.x`,
  `variable_volume[_batch][_gsa].x`, all premixed/counterflow/diffusion flame solvers,
  `idt_diagnostic.x`, `thermo_check.x`.
- **Acceptance-gate smoke test** (`examples/perturbAFactorGSA/`, shipped H2 mechanism, 1000-sample
  MC batch, 80 MPI ranks): ran successfully in well under 1 second wall-clock. Compared against the
  shipped `h2_T875_gsa_mpi.dat.ref` — all 5 IDT-threshold columns matched to 5-6 significant figures
  for the first several sample rows (the one differing column, `cpu_time`, is expected to vary by
  machine). Note: had to regenerate `hydrogen_1000.mtx` via `create_lognormal_mtx.py` using
  anaconda's Python instead of the documented `/usr/bin/python3.9` — the system Python's numpy
  install is broken (`ImportError: numpy.core._multiarray_umath`), unrelated to Zero-RK itself.
- **Cross-validation against this repo's existing Cantera-based solver**, on a real mechanism
  already in `project.db` (GRI-3.0-wetCO, `/home/krithika/MUQ-SAC/MECHANISMS/GRI3/
  chem_gri30_wetCO.inp`, 14 species / 48 reactions — confirmed this is a reduced H2/CO "wetCO"
  variant, not full 53-species GRI-3.0, so H2 was used as fuel not CH4): ran `constVolumeWSR.x` at
  T₀=1000K, P₀=10atm, φ=1.0, H2/air, IDT defined as ΔT=400K rise. Result: **Zero-RK
  8.0618713571932385e-03 s vs. Cantera's `IdealGasReactor` 8.0618681668e-03 s — 0.00004% relative
  difference.** This is the real correctness gate for everything downstream, and it passed cleanly.
- One usage note for Phase 1: `constVolumeWSR.x`'s YAML schema is NOT the same shape as
  `perturbAFactorGSA`'s — it takes **vectors** (`initial_temperatures`, `initial_pressures`,
  `initial_phis`, `initial_egrs`, `preconditioner_thresholds` — all as lists, even for a
  single-condition run) plus `eps_lin`/`nonlinear_convergence_coefficient`/`long_output` with no
  documented defaults (omitting any of these aborts immediately with "didn't find required input
  value" — no partial-default behavior). `zerork_bridge.py` needs to hardcode sensible defaults for
  all of these, not just the physically-meaningful fields. Also: species names in
  `fuel_mole_fracs`/`oxidizer_mole_fracs`/`trace_mole_fracs` must match the **exact casing** used in
  the mechanism file's `SPECIES` block (case-sensitive lookup) — can't assume lowercase.

Original plan text below, retained for the reasoning/tradeoffs (SUNDIALS version choice, disk
cleanliness) that led to the above — the concrete commands above supersede it where they conflict.

---

**Effort: 0.5–1 day (mostly unattended build time, SUNDIALS-from-source is slow).**

1. The existing `build/` dir is stale/partial (only `superlu` got built, config is 7 days old
   relative to this session). Recommend a **clean re-configure** rather than resuming it, to avoid
   fighting a half-finished `ExternalProject` state:
   ```bash
   cd /home/krithika/zero-rk
   rm -rf build   # confirm with KP first — see note below
   mkdir build && cd build
   cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo \
            -DENABLE_MPI=ON \
            -DMPI_C_COMPILER=/home/krithika/anaconda3/bin/mpicc \
            -DMPI_CXX_COMPILER=/home/krithika/anaconda3/bin/mpicxx \
            -DCMAKE_INSTALL_PREFIX=$PWD/inst_dir
   make -j$(nproc)
   ```
   ⚠️ **This deletes ~38 MB of partial build state before rebuilding it from scratch — reversible
   in the sense that it's all regenerable from source, but it's still a delete. Confirm with KP
   before running `rm -rf build`, per this session's standing rule about destructive operations.**
   Alternative if KP prefers not to delete anything: build in a fresh directory (`build2/`) and
   leave `build/` untouched, at the cost of ~40 MB extra disk (irrelevant given 520 GB free).
2. **SUNDIALS**: default config builds SUNDIALS 5 from source (slow, ~15-30 min). System has
   `libsundials-cvode3` etc. via apt (version 3.x) and Zero-RK supports system SUNDIALS 3.2.1 via
   `-DSYSTEM_SUNDIALS_ROOT=/usr`. **Try system SUNDIALS first** (faster) — if version mismatch
   causes a CMake error, fall back to the from-source default. Either way this is a build-config
   detail, not a design decision — try both, keep whichever configures cleanly.
3. `make -j$(nproc)` (160 cores available — should be fast once dependencies are resolved).
4. `ctest` — run Zero-RK's own test suite, confirm pass before trusting any output.
5. `make install` → binaries land in `build/inst_dir/bin/`.
6. **Smoke test**: run the shipped `examples/perturbAFactorGSA/` H2 example exactly as documented
   (`run.sh.in` → substitute install prefix, run via `mpirun`), diff the output against the shipped
   `.dat.ref` reference file. This is the acceptance gate for "Zero-RK is correctly installed" —
   don't proceed to Phase 1 until this matches.
7. **Cross-validate against the existing solver stack**: pick one small mechanism already in
   `project.db` (e.g. GRI-3.0 or Davis-2005 — both tiny, already loaded), run the same IDT
   condition through both Zero-RK's `constVolumeWSR` and the existing Cantera-based IDT path
   (`CanteraSensitivityRunner`'s underlying `IdealGasReactor`/`ReactorNet` setup, or MUQ-SAC's
   cantera Tig branch), confirm IDT values agree within solver tolerance. This is the real
   correctness gate for everything downstream — a fast-but-wrong solver is worse than a slow-but-
   right one.

### Phase 1 — `rmip/simulation/zerork_bridge.py` — ✅ DONE (2026-07-12)

**Verified working: `constVolumeWSR` (IDT) and `constVolumePSR` (JSR), both reactor types this
phase scoped.** IDT on GRI-3.0 matches the Phase 0 Cantera cross-validation reference to 0.05%
(8.06579668920622e-3 s here vs 8.0618713571932385e-3 s in Phase 0 — small residual difference is
expected floating-point/round-trip noise, not a correctness gap). IDT on Davis-2005 (a mechanism
with no `KELVINS` header, exercising the other Ea-units code path) converges cleanly. JSR on
GRI-3.0 converges. Full test suite 355/355 throughout.

Getting a single successful Zero-RK run required finding and fixing **six real, previously-
undiscovered bugs** in the CHEMKIN parse/write round-trip — none Zero-RK-specific, all silently
wrong for any consumer, just never exercised by a parser strict enough to surface them before now
(Cantera's `ck2yaml` and this repo's own downstream tooling apparently tolerate all of them).
Commit `10c77d2` has full details; summary:

1. `chemkin_writer.py` NASA-7 line-1 field widths were wrong (species-name+date block 26 cols
   instead of the CHEMKIN-standard 24; Tmid 8-wide with no guaranteed separator from Thigh) —
   shifted every fixed-column field and could concatenate Thigh/Tmid with zero separator.
2. `_chemkin_parser.py`: a LOW-only (Lindemann, no TROE) falloff reaction was never tagged
   `kinetics_type="lindemann"` — fell through to `"third_body"` and silently dropped the
   LOW-pressure rate. Affects 1 reaction in each of GRI-3.0/Davis-2005/Keromenes-2013/Li-2015.
3. `chemkin_writer.py` read `kinetics_data_json` using key names that never matched what the
   parser actually writes (`low_rate` vs `low`, `troe_params` vs top-level, `plog_rates` vs
   `pressures`+`arrhenius`, `T_limits`/`n_T`/`n_P` vs `Tmin`/`Tmax`/`coeffs`) — every falloff/PLOG/
   Chebyshev reaction in every mechanism has silently lost its pressure-dependence data on export
   since this writer existed, not just for this plan.
4. `_chemkin_parser.py` never detected the `KELVINS` REACTIONS-header modifier (Ea given as
   activation temperature Ea/R) — silently defaulted to cal/mol. GRI-3.0-wetCO's header is
   `REACTIONS MOLES KELVINS`; every one of its reactions' Ea was mislabeled by a factor of R until
   this fix (verified against GRI-Mech 3.0's published values, e.g. O+H2<=>H+OH: file value
   3150.48 × 1.98720 = 6260 cal/mol, the documented value).
5. `species.formula` was never populated by the CHEMKIN parser at all (`"formula": None` was
   dead code) — `ChemkinWriter`'s ELEMENTS block silently fell back to a hardcoded `{C,H,O,N}`
   (missing e.g. `AR`), and every THERMO entry's own elemental-composition columns came out blank.
   **This was the dominant root cause of the universal NaN-at-t=0 CVode failure** — Zero-RK
   computes species molecular weights from the declared elements, not from name lookup, so every
   species (not just AR) got a degenerate molecular weight.
6. `zerork_bridge.py`'s own composition resolution double-applied the equivalence-ratio mixing —
   it called Cantera's `set_equivalence_ratio`+`mole_fraction_dict` to pre-resolve the full
   mixture, then *also* passed Zero-RK's `initial_phis`. Zero-RK's `fuel_mole_fracs`/
   `oxidizer_mole_fracs` are stream-relative ratios (same convention as Cantera's own
   `set_equivalence_ratio` *input* strings, e.g. `"O2:1.0, N2:3.76"` need not sum to 1) and it
   applies phi internally — fixed by parsing `condition.fuel`/`.oxidizer` directly instead.

⚠️ **Not yet done: the live `outputs/project.db` (mechanisms 1-4) was parsed with the old, buggy
parser and was deliberately NOT re-parsed as part of this fix** — its `species.formula`/ELEMENTS
data is stale for all 4 CHEMKIN mechanisms, and GRI-3.0's (mechanism_id=1) Ea values specifically
are stale (were being read as cal/mol instead of Kelvin). Needs explicit user confirmation before
re-parsing, since other analysis results (SA runs, reductions, comparisons) already reference these
mechanism_ids and a re-parse via `rmip_cli.py parse` creates new IDs rather than updating in place.

Mirror `muqsac_bridge.py`'s existing shape (already-established pattern in this codebase):
- `ZerorkBridge.build_input_files(condition: SimCondition, reactor_type, ...)` — write the YAML
  input (`mechFile`, `thermFile`, `initTemp`, `initPres`, `initPhi`/`fuelComp`/`oxidizerComp`,
  tolerances) from a `SimCondition`, reusing the mole-fraction resolution logic already in
  `MuqsacBridge.build_target_files()` rather than re-deriving it.
- `ZerorkBridge.run(reactor_type, input_yaml, n_mpi_ranks=1)` — `subprocess.run(["mpirun", "-n",
  str(n_mpi_ranks), exe_path, input_yaml])` for MPI-only apps (GSA family, flame solvers);
  `subprocess.run([exe_path, input_yaml])` for `constVolumeWSR`/`constVolumePSR` (which — verify in
  Phase 0 — may have serial builds; `perturbAFactor` confirmed has both).
- `ZerorkBridge.parse_idt_output(...)`, `.parse_gsa_output(...)`, `.parse_rcm_output(...)` — read
  the `.dat`-style tables Zero-RK writes (format confirmed in section 1.1.2's example) into
  `IDTResult`/new `GSASampleResult` dataclasses.
- **Mechanism format note**: Zero-RK's `mechFile`/`thermFile` expect CHEMKIN-ASCII, not Cantera
  YAML. Some mechanisms in `project.db` are stored as `cantera_yaml` format (e.g. FFCM1, MB-MB2D).
  Need a YAML→CHEMKIN-ASCII export path for those — check whether `rmip/io/chemkin_writer.py`
  (already exists, used for the `export --format` CLI path per Phase 4's `ChemkinWriter`) already
  covers this before writing a new converter.
- Reactor coverage this phase: `constVolumeWSR` (IDT — highest value, maps to existing Tig
  targets), `constVolumePSR` (JSR). Defer `variable_volume` (RCM) and flame solvers
  (`premixedSteady`/counterflow) to a later pass unless KP has near-term need — IDT is what both
  `sens_3_params.py` and the GSA apps center on, so it's the highest-leverage first target.
- CLI: `rmip zerork-idt <mech_id> --db DB --T ... --P ... --phi ... --fuel ... [--n-ranks N]`,
  mirroring `sa-run`'s argument shape.

### Phase 2 — Zero-RK as a `solver=` option in the existing brute-force SA codebase — ✅ DONE for Tig + JSR (2026-07-12)

**Implemented directly in `make_input_file.py`'s `create_input_file()`** — the single function
every solver dispatch (SA, forward-UQ, nominal runs, everything) already routes through via
`simulation_manager2_0.py` — rather than adding a separate seam in `sens_3_params.py`. Same net
effect the plan describes (Zero-RK becomes a `target.add["solver"]` option alongside cantera/
CHEMKIN_PRO/FlameMaster, reusing 100% of the existing perturbation/orchestration code) but at the
more foundational layer, so it's automatically available to every caller, not just brute-force SA.
Commit `6056ec4` has full details for Tig. Verified end-to-end (real `create_input_file()` call →
generated script → real Zero-RK run → `output/tau.out`) against a freshly re-parsed GRI-3.0
mechanism, matching the Phase 0 Cantera cross-validation reference to 0.05%.

JSR wiring followed the same pattern: a `constVolumePSR.x`-driving `elif "zerork" in solver:`
branch in the JSR section of `create_input_file()`, an explicit `"zerork"` branch in
`data_management.py`'s JSR result parser, and a new `zerork_jsr_preconditioner_threshold` default
(`1.0e-6`, matching Zero-RK's own PSR example — the existing `zerork_preconditioner_threshold`
default of `2.048e-3` is WSR/Tig-tuned and would be wrong for PSR/JSR) in
`combustion_target_class.py`. Verified end-to-end the same way as Tig: a real generated script run
against `constVolumePSR.x` on GRI-3.0 (mechanism_id 8), `converged: true`,
`residence_time_s: 0.5` round-tripped correctly, H2 exit mole fraction `0.0255` parsed correctly by
both `output/jsr_full.json` and `data_management.py`'s new branch.

**Scope done: Tig (IDT) and JSR.** PFR/flame targets remain a **permanent** gap (Zero-RK has no
such reactor), not deferred work.

**Effort: 2-3 days, small once Phase 1 lands.** (Original estimate; actual Tig implementation
took about half a day once Phase 1's zerork_bridge.py existed, including the composition-handling
subtlety below.)

Design choice (recommended): **do not** try to use Zero-RK's own `perturbAFactor`/
`perturbAFactorGSA` apps for the 3-parameter (A, n, Ea) OAT sweep `sens_3_params.py` already does —
those apps only support A-factor perturbation. Instead, keep `sens_3_params.py`'s existing
mechanism-perturbation-file generation logic exactly as-is (it already writes a full perturbed
mechanism YAML/CHEMKIN file per A/n/Ea case — solver-agnostic by construction) and add
`"zerork"` as a new accepted value for `target.add["solver"]` in `make_input_file.py`, dispatching
to `ZerorkBridge.run("constVolumeWSR", ...)` from Phase 1 alongside the existing
`cantera`/`CHEMKIN_PRO`/FlameMaster branches in `simulation_manager2_0.py`. This gets **full
3-parameter OAT generality at Zero-RK's solver speed**, reusing 100% of the existing perturbation/
orchestration/parallelization code — the only new code is one new solver branch, matching the
shape of the CHEMKIN_PRO/FlameMaster branches already there.

- Scope this phase to Tig (IDT) targets only, since that's Phase 1's reactor coverage.
- Thread/process-pool sizing: reuse `chem_data.thread_cap()` as today — but note Zero-RK's MPI
  ranks are a *second* level of parallelism (each `zerork-idt` subprocess call can itself use
  `n_mpi_ranks` MPI workers for its own GSA-matrix batch, see Phase 3) — need a combined budget so
  total (Python worker processes) × (MPI ranks per Zero-RK call) doesn't exceed `thread_cap()`.
  This is a real design detail to get right, not just a footnote — oversubscription will silently
  slow everything down on a 160-core box, not crash.

### Phase 3 — True GSA via SALib + Zero-RK's MPI batch machinery — ✅ DONE, standalone (2026-07-12)

**Scope decision (confirmed with KP before starting):** implemented as a standalone engine
(`rmip/simulation/zerork_gsa.py`'s `ZerorkGSARunner`) operating directly on a single
`mechanism_id` + selected reaction A-factors — **not** wired into `DoEFramework.run_screening()`'s
documented `UnionGraphSpec.fuse_params` interface as originally planned below. Reason found during
implementation: that interface screens `fuse_params`, which only exist for a *merged* mechanism
produced by `FusionEngine` (M7) — and M7 is itself still an unimplemented stub in this codebase
(raises `NotImplementedError`). Wiring `run_screening()` to a mechanism that doesn't exist yet
wasn't possible; building the real, working GSA capability against mechanisms that already exist
in `project.db` was. `SobolResult.to_screening_dict()` already returns exactly
`run_screening()`'s documented `{canonical_key: {"S1": ..., "S1_conf": ..., ...}}` shape, so
wiring `DoEFramework` to delegate to `ZerorkGSARunner` once M7 lands is a small follow-up, not a
redesign.

**⚠️ Environment incident, now resolved — read before touching `SALib` again:** SALib 1.5.2
requires `numpy>=2.0`/`scipy>=1.9.3`/`pandas>=2.0`. This repo's shared anaconda environment is
pinned to `numpy 1.24.4` (scikit-learn 1.0.2, numba 0.54.1, and other already-installed packages
depend on the numpy-1.x ABI). Running `pip install SALib` directly in that environment upgraded
numpy to 2.0.2 and **broke scikit-learn's import outright** (confirmed via
`src/rmip/tests/test_phase6.py`'s `pytest.importorskip("sklearn")` silently starting to skip).
Immediately rolled back (`pip install numpy==1.24.4 scipy==1.8.0 pandas==1.4.1`), restoring
355/355 passing with `sklearn` importable again. **Fix: SALib now lives in a dedicated venv,
`/home/krithika/.venvs/salib_gsa`, never imported directly** — `zerork_gsa.py` talks to it only
via `_salib_backend.py`, invoked as a subprocess exchanging JSON request/response files. This is
the same D7 "subprocess + file contract, never import" principle already used for Zero-RK/
CHEMKIN_PRO/FlameMaster, just extended to a Python dependency instead of an external binary. If a
future session considers installing SALib into the main environment "for convenience," don't —
this incident is why the venv exists, not an arbitrary choice.

**MPI note:** `perturbAFactorGSA_mpi.x` must be invoked via `/usr/bin/mpiexec` (system OpenMPI
4.1.4, the same MPI Zero-RK was built against in Phase 0), **not** anaconda's `mpirun` (MPICH/
Hydra 3.3.2 — a different, incompatible MPI implementation that would silently produce wrong or
crashing runs). `zerork_gsa.py` hardcodes `/usr/bin/mpiexec` as the default for this reason.

**What was built:**
- `rmip/simulation/zerork_gsa.py` — `ZerorkGSARunner.run_screening(config, work_dir)`: samples
  via SALib (Sobol via `SALib.sample.sobol`/`analyze.sobol`, Morris via
  `SALib.sample.morris`/`analyze.morris`), writes Zero-RK's `gsaMatrixFile` (confirmed format:
  header `"{n_samples:6d} {n_reactions:6d}"`, then **one value per line**, row-major — not one
  row per line as the "rows/columns" framing might suggest), expands the caller's selected-reaction
  subset to the mechanism's **full** reaction-column count (Zero-RK cross-checks
  `gsaMatrixFile`'s column count against the parsed `mechFile` and errors on mismatch —
  unselected reactions are held at multiplier 1.0 for every sample, not omitted), runs
  `perturbAFactorGSA_mpi.x` once over the whole batch, parses its output table (mean-imputing any
  non-ignition/failed sample before handing `Y` to SALib's analyzer, which can't accept NaN), and
  returns a `SobolResult`.
- A-factor sampling is log-uniform: each selected reaction's multiplier is sampled in
  `[1/factor_bound, factor_bound]` (default `factor_bound=2.0`, matching Zero-RK's own
  `perturbAFactor` 2x default convention) by sampling the log-multiplier uniformly in
  `[-ln(factor_bound), +ln(factor_bound)]` and exponentiating.
- `rmip/simulation/_salib_backend.py` — the venv-side `sample`/`analyze` subprocess entry point.
- DB: `run_gsa_migrations()` in `migrations.py` adds `sensitivity_runs`/`sobol_indices`/
  `design_matrices` tables, mirroring the `reduction_runs` (Phase 5B) pattern exactly (same
  `_table_exists`-guarded lazy-migration shape, same FK-cascade style).
- `types.py`: `GSARunConfig`, `SobolResult` dataclasses (`to_dict`/`from_dict`/`save`/`load`,
  mirroring `ReductionResult`'s exact conventions).
- CLI: `rmip gsa-run <mech_id> --db DB --method sobol|morris --n-samples N --reactions ...
  --zerork-install-prefix PATH --T ... --P ... --phi ... --fuel ... [--seed N] [--out FILE]`
  (`rmip/cli.py`'s `_add_gsa_run_cmd`/`_cmd_gsa_run`, mirroring `reduce`'s structure).
  ⚠️ Must be invoked via the repo-root `rmip_cli.py` launcher, not `python3 src/rmip/cli.py`
  directly or `cd src && python -m rmip.cli` — `src/rmip/io/` is a package named `io` that shadows
  the stdlib `io` module and crashes the interpreter at startup if `src/rmip/` ends up as
  `sys.path[0]` (pre-existing landmine, already documented in `rmip_cli.py`'s own docstring, not
  something this phase introduced — just re-discovered it the hard way).
- Tests: `src/rmip/tests/test_zerork_gsa.py` (16 tests, all passing) — dataclass round-trips,
  migration idempotency, pure-logic matrix/output-parsing helpers (no external dependency needed),
  DB persistence, and one real end-to-end test that actually runs
  `perturbAFactorGSA_mpi.x`/SALib (skipped automatically if the venv/binary aren't present on the
  running machine).

**Verified end-to-end** against real GRI-3.0 (`mechanism_id=8` in `outputs/project.db`), both
methods: Sobol (`perturbAFactorGSA_mpi.x` output cross-confirmed "number of reactions: 48" matching
the exported mechanism exactly) and Morris, both via the actual CLI (`rmip gsa-run`) and the
Python API. Small sample counts were used for the verification runs (to keep them fast, seconds
not minutes) — the resulting indices are not statistically converged at that N (expected and fine
for a mechanics check; real usage needs the sample counts Saltelli/Morris theory recommends,
typically hundreds to thousands).

Original plan text below, retained for the reasoning/tradeoffs (SALib/Zero-RK matrix-format
semantics, DB schema shape) that led to the above — the concrete implementation above supersedes
it where they conflict.

---

This is where "Zero-RK's own GSA functionality" actually gets used, and where real Sobol/Morris
indices get computed (something neither Zero-RK nor this codebase currently does).

1. **Install `SALib`** (`pip install SALib`) — already the documented dependency choice in
   `stubs.py`'s docstring, don't second-guess it.
2. **Sampling**: use SALib's `saltelli.sample()` (for Sobol) or `morris.sample()` (for Morris
   screening) to generate the parameter-perturbation matrix, instead of Zero-RK's own
   `create_lognormal_mtx.py`/`create_bruteforce_mtx.py` examples (those are simplistic reference
   scripts, not real DoE — SALib's samplers are the actual state of the art here and are what
   `stubs.py` already commits to).
3. **Execution — reuse Zero-RK's own MPI batch machinery rather than re-parallelizing in Python**:
   write SALib's generated sample matrix out in Zero-RK's `gsaMatrixFile` format (plain text,
   `rows cols` header + row-major multiplier values — format confirmed in section 1.1.2), then
   invoke `perturbAFactorGSA_mpi.x` **once** via `mpirun -n <ranks>` over the whole batch. This
   reuses Zero-RK's already-implemented, already-tested MPI master/worker dispatch instead of us
   building a parallel-dispatch layer over many individual Zero-RK subprocess calls — less new
   code, and Zero-RK's MPI batching is presumably more efficient than N independent process
   spawns for large sample counts (thousands, typical for Sobol/Saltelli with many parameters).
   - Open question to resolve during implementation: does `perturbAFactorGSA`'s "perturb all
     reactions simultaneously per row" model match what SALib's Saltelli sampler produces (which
     also perturbs multiple parameters per sample row, by design, for variance decomposition)?
     Need to confirm the semantics line up before trusting the indices — this is exactly the kind
     of thing Phase 0's cross-validation step should also probe.
4. **Index computation (the actual gap)**: read `perturbAFactorGSA`'s raw output table (IDT per
   sample) back into Python, feed the corresponding SALib sampler's matching analyzer
   (`sobol.analyze()` or `morris.analyze()`) — this is where `{canonical_key: {"S1": ..., "S1_conf":
   ..., "ST": ...}}` actually gets computed, filling in exactly what Zero-RK's C++ code omits
   (confirmed in 1.1.2 — it only writes input-distribution diagnostics, never output-correlated
   indices).
5. **Implement `DoEFramework.prepare_mso_input()`** per its existing docstring: run screening,
   apply the documented `|SA coefficient| < 0.01` cutoff, build bounds/x0 from
   `spec.fuse_params`, hand off to `MSOParameters`.
6. **DB persistence** (new, since nothing currently exists): migrations for `sensitivity_runs`
   (mode: brute_force_oat | cantera_local | zerork_gsa_sobol | zerork_gsa_morris),
   `sobol_indices` (per-reaction S1/ST/confidence), `design_matrices` (sample count, method,
   seed, parameter list) — mirror the `reduction_runs` table pattern (Phase 5B) for consistency.
   New dataclasses in `types.py`: `SobolResult`, `GSARunConfig`.
7. **CLI**: `rmip gsa-run <mech_id> --db DB --method sobol|morris --n-samples N --reactions ...
   --zerork-install-prefix PATH [--dry-run]`, matching the argument-naming conventions of
   `reduce`/`sa-run`.

### Phase 4 — Connect back to the existing PRS/Forward-UQ pipeline
**Effort: 2-3 days.**

- Use Phase 3's screening indices (or TLA's cheap per-reaction local sensitivities from section
  1.1.1, whichever is cheaper to obtain for a given case) as a **pre-filter** on which reactions'
  parameters go into `DesignMatrix.py`'s design before `MUQ-SAC/run_script.py`'s PRS training runs
  — directly implements the cutoff already specified in `DoEFramework.prepare_mso_input()`'s
  docstring, and reduces the number of expensive training simulations needed.
- No change needed to `AnalyticalSobolPRS`/`MCPropagator` themselves — they stay solver-agnostic
  surrogate consumers. The benefit here is indirect: fewer, better-chosen training simulations,
  and (once Phase 2 lands) those training simulations can themselves run through
  `solver="zerork"` for a direct speedup.
- **Validation step**: on at least one case, compare Phase 3's direct-simulation Sobol indices
  against `AnalyticalSobolPRS`'s PRS-surrogate indices for the same reactions. Large disagreement
  flags either a bad PRS fit (nonlinear regime the order-2 surrogate can't capture — e.g. near NTC
  onset or extinction) or a GSA-sampling bug — this cross-check is valuable in both directions and
  should become a standing diagnostic, not a one-off check.

### Phase 5 — CLI polish + GUI integration
**Effort: 3-4 days.**

- GUI: add a `solver` dropdown option "Zero-RK" to the Run-SA panel (wherever `target.add["solver"]`
  is currently chosen in `generate_target_opt.py`); add a new GSA panel/button following the
  **embedded PtyTerminal pattern** already used for "Run SA" (`_rs_terminal.run(...)`) rather than
  Forward UQ's external-terminal-plus-file-polling pattern — this matches PLAN.md's already-
  recorded structural-improvement recommendation (#5: route long jobs through `PtyTerminal`, not
  external OS terminal windows) instead of adding a third launch mechanism.
- Progress/results display: reuse the Forward UQ tab's polling-for-output-file pattern (simpler
  than building new IPC) but point it at the embedded terminal's completion signal instead of an
  external process exit.

---

## 4. Effort summary

| Phase | What | Estimate |
|---|---|---|
| 0 | Build + validate Zero-RK | ✅ DONE (2026-07-11) — ~1 hour incl. debugging 3 build-config issues |
| 1 | `zerork_bridge.py` (IDT + JSR reactors) | 3-5 days |
| 2 | `solver="zerork"` in existing brute-force SA | 2-3 days |
| 3 | Real Sobol/Morris via SALib + Zero-RK's MPI batch apps | ✅ DONE (2026-07-12), standalone — ~1 day, not 1-2 weeks (scoped to a single mechanism rather than the not-yet-built M7 fusion pipeline; see Phase 3 section for why) |
| 4 | Wire screening into PRS/Forward-UQ pipeline + cross-validation | ✅ DONE (validation step 2026-07-12, prefilter wiring 2026-07-21) — cross-validation ~1 day; prefilter wiring (`gsa_reaction_prefilter.py` + `run_script.py`/`DesignMatrix.py` opt-in hooks + 23 tests) ~1 day; full E2E run is a documented manual step (no licensed toolchain in this environment) |
| 5 | CLI + GUI | 3-4 days |
| **Total** | | **~3-4 weeks** of focused work, plus whatever wall-clock the unattended Zero-RK build takes |

This is a rough, single-pass estimate (not padded for review cycles/rework) — treat as ordering
information ("Phase 3 is the big one") more than a committed schedule.

---

## 5. Open questions / risks to resolve during implementation, not now

1. ~~`SYSTEM_SUNDIALS_ROOT` vs from-source SUNDIALS 5~~ — **RESOLVED (Phase 0): must use
   `-DSUNDIALS_VERSION=5` from source.** System SUNDIALS (3.1.2) isn't just slower to skip building
   from source, it actually disables `constVolumeWSR_TLA` and the counterflow flame solvers at
   configure time. Not a speed tradeoff — a hard capability requirement. See Phase 0 for the full
   finding and the two other build-config bugs (broken anaconda MPI compiler wrapper,
   `SYSTEM_SUPERLU_ROOT` include-path mismatch) discovered alongside it.
2. ~~Mechanism format conversion~~ — **RESOLVED: yes, `rmip/io/chemkin_writer.py`'s
   `ChemkinWriter.write(mechanism_id, output_path)` already covers this.** It's DB-driven (reads
   `species`/`reactions`/`stoichiometry` tables), not format-of-origin-driven — works identically
   for a mechanism originally loaded from CHEMKIN or from Cantera YAML. No new converter needed.
3. **MPI-rank budget vs. Python worker-pool budget** — need one combined `thread_cap()`-respecting
   allocation, not two independent ones that can oversubscribe the box (Phase 2 note).
4. ~~Does SALib's Saltelli sampling semantics match `perturbAFactorGSA`'s "perturb all reactions
   per row" execution model~~ — **RESOLVED (Phase 3): yes, cleanly, with one adaptation.**
   `perturbAFactorGSA` requires the `gsaMatrixFile`'s column count to equal the mechanism's full
   reaction count exactly (cross-checked against the parsed `mechFile`, confirmed via its own
   stdout: `number of reactions : 48`). SALib's Saltelli/Morris samplers only produce columns for
   the parameters actually being screened. Reconciled by expanding the selected-reaction subset to
   the mechanism's full column width, holding every non-selected reaction's multiplier at 1.0 for
   every sample row (see `ZerorkGSARunner._build_full_matrix`) — no reshaping/padding of the
   semantics themselves needed, just a width expansion. Did not do the known-answer
   linear-response cross-check against `AnalyticalSobolPRS` this pass (small-N verification runs
   only checked mechanics, not statistical convergence) — worth doing before trusting indices from
   a real, larger production run.

   **Follow-up (validation step, done 2026-07-12): implemented as
   `src/rmip/simulation/gsa_prs_crosscheck.py`** — standalone, does not touch `run_script.py`.
   Ran the cross-check on GRI-3.0 (`mechanism_id=8`)'s `H+O2<=>O+OH` / `O+H2<=>H+OH` /
   `OH+H2<=>H+H2O` (real uncertainty data, new fixture
   `src/rmip/tests/fixtures/h2_o2_crosscheck_unsrt.xml`, built from the same real `<temp>`/`<unsrt>`
   arrays as `DATASET/H2_O2_TEST/uncertainty/H2_uncertainty.xml` but with `no=`/
   `<perturbation_type>`/non-blank `<class>` added — the shipped fixture is missing all three,
   which crashes `Uncertainty.py`'s `reaction.__init__` or silently no-ops the perturbation
   dispatch). At real, converged settings (`n_design=40` PRS-training points, `n_direct_base=512`
   Sobol base samples), **result: AGREE** — `S1_prs`/`S1_direct` per reaction: `0.9992`/`0.9991`
   (H+O2<=>O+OH, correctly dominant), `0.0002`/`0.0002` (O+H2<=>H+OH), `0.0006`/`0.0008`
   (OH+H2<=>H+H2O) — all within 0.0001-0.0002 of each other.

   **This cross-check found a real, previously-undiscovered off-by-one bug in
   `ZerorkGSARunner._parse_gsa_output`, now fixed.** At smaller sample counts the two near-zero
   reactions initially disagreed by nearly 1.0 (PRS said ~0, direct-sim said ~1.0, i.e. as
   "dominant" as the real dominant reaction) — increasing the sample count to 512 made this
   *worse*, not better, which ruled out ordinary statistical noise and pointed at a systematic bug.
   Root cause, confirmed by reading `applications/perturbAFactorGSA/perturbAFactor_mpi.cpp`
   directly: `perturbAFactorGSA_mpi.x` always writes `task_id=0` as its own unperturbed-baseline
   run *before* the sample loop ("report the unperturbed IDT calculation as task 0"), then writes
   matrix row `j` (0-indexed) as `task_id=j+1` — a row-index-to-task-id offset of exactly one.
   `_parse_gsa_output` read `task_id` directly as the row index, so every sample's simulated IDT
   was silently paired with the *wrong* row of the SALib sample matrix (off by one, with row 0
   getting the baseline's value and the true last row silently dropped) — corrupting the Saltelli
   pick-freeze pairing for **every Sobol/Morris index this module has ever computed**, not just
   this cross-check's 3-reaction case. Fixed in `zerork_gsa.py`'s `_parse_gsa_output` (now returns
   `rows.get(i + 1, nan)` for `i in range(n_samples)`, ignoring `task_id=0` entirely); the existing
   `test_parse_gsa_output_*` unit tests were updated to reflect the real baseline+offset output
   format, plus a new regression test pinning the fix. This silently affects (until this fix)
   every caller of `ZerorkGSARunner.run_screening()` to date: the `rmip gsa-run` CLI,
   `DoEFramework.run_screening()`/`prepare_mso_input()`, and the RMIP Suite GUI's GSA tab — all
   were computing statistically-corrupted indices, though the earlier `test_run_screening_sobol_real_binary`
   end-to-end test never caught it because it only asserts structural shape (sample count, key
   sets), never actual index values against an independent ground truth. This is exactly the
   failure mode this validation step was built to catch.

   Separately (not a bug, a real modeling gap this cross-check had to work around): `Manipulator`'s
   A-factor-only perturbation bound is `sigma_A = min(reaction.uncertainties)` (~0.13-0.16 for this
   trio) — much narrower than `ZerorkGSARunner.run_screening()`'s own default `factor_bound=2.0`
   (`ln(2)~=0.69`). An apples-to-apples comparison needed the direct-sim side to sample the *same*
   per-reaction bound the PRS was trained on, not `run_screening()`'s single shared bound — see
   `run_direct_sobol_per_reaction_bounds()`, which composes `ZerorkGSARunner`'s private
   sampling/matrix/parsing helpers with a per-reaction bounds list. A regression test
   (`TestPerReactionBoundsMatchesRunScreening`) pins this composition against `run_screening()`
   itself for the equal-bounds case, so a future change to `zerork_gsa.py`'s internals that breaks
   the composition is caught immediately.

   **Prefilter wiring into `run_script.py`/`DesignMatrix.py` — DONE (2026-07-21).** New module
   `src/rmip/simulation/gsa_reaction_prefilter.py`:
   - `ReactionIdMaps` (dataclass: `id_of_formula`, `formula_of_id`) +
     `build_reaction_id_maps(db_path=None, mechanism_id=None, mechanism_path=None)` — generalizes
     this file's own `id_of_formula`/DB-query proof-of-concept. DB mode mirrors
     `run_crosscheck`'s exact `SELECT id, formula_string FROM reactions WHERE mechanism_id=?`
     query; file mode loads a Cantera `Solution` directly (no DB) and assigns 1-based ids in
     `Solution.reactions()` order, since production `run_script.py` has no rmip DB, only a
     `Locations.mechanism` file path.
   - `select_gsa_important_reactions(gsa_result_path, metric="ST", threshold=0.01, top_n=None)` —
     reads an `rmip gsa-run` JSON output (`SobolResult.save()`'s shape), strips the
     `ZerorkGSARunner`-style `R<n>:` label prefix, and returns the reaction-formula set clearing
     `threshold` (default 0.01) or the top `top_n`. Passing both raises `ValueError` (mutually
     exclusive, loud failure over silent precedence).
   - `apply_gsa_prefilter(unsrt_data, prefilter_cfg)` — THE opt-in seam. Returns `unsrt_data`
     **completely unchanged** (same object) whenever `prefilter_cfg` is falsy/empty or has
     `enabled: false`; raises `ValueError` (not a silent empty dict) if the GSA result's reaction
     keys have zero overlap with `unsrt_data`'s keys (format-mismatch guard) — but returns an empty
     dict, not an error, if overlap exists and the threshold legitimately excludes everything (a
     valid user choice, not a bug signature).

   **`run_script.py` wiring**: `_maybe_apply_gsa_prefilter(optInputs, unsrt_data)` (defined at
   module scope, before the argv-parsing block) is called right after `unsrt_data` is
   loaded/unpickled (~line 220 in the pre-change file), before it drives `manipulationDict`/
   `DesignMatrix`. Purely additive — zero existing statements touched, no restructuring of the
   file's (pre-existing, zero-coverage) lack of an `if __name__ == "__main__":` guard. New
   optional `target.opt` schema block (absent = today's exact behavior, confirmed by grepping
   every `target.opt`/target-shaped file in this repo for zero `GSA_Prefilter` hits):
   ```yaml
   GSA_Prefilter:
     enabled: true
     gsa_result_json: /path/to/sobol_1_gsa.json   # an `rmip gsa-run` output file
     metric: ST        # or S1 / mu_star
     threshold: 0.01   # or top_n: 20 (mutually exclusive with threshold)
   ```

   **`DesignMatrix.py`**: one additive, non-behavior-changing line in `__init__`,
   `self.n_reactions_in_design = len(UnsrtData)` — every reaction-list derivation in the class
   already flows from `self.unsrt` (`list(self.unsrt.keys())` throughout), confirmed by reading the
   whole file; nothing else needed changing.

   **Tests**: `src/rmip/tests/test_gsa_reaction_prefilter.py` (23 tests) — unit tests for the new
   module (no-op identity, threshold/top_n filtering, key-mismatch `ValueError`, DB-mode vs.
   file-mode `build_reaction_id_maps` equivalence, S1/ST/mu_star metric parsing); a
   `run_script.py`-level test that extracts `_maybe_apply_gsa_prefilter`'s exact source via `ast`
   (that file has no `__main__` guard, so it can't be `import`ed directly without executing its
   whole side-effecting body — extracting just this one function avoids needing to restructure
   1000+ lines of untested production code) and proves both identity-on-no-op AND that the `rmip`
   import is never triggered in that path; and a DesignMatrix-level benchmark using
   `gsa_prs_crosscheck.py`'s real `build_unsrt_subset()` + the real 3-reaction H2/O2 fixture against
   a freshly-exported real GRI-3.0 (`mechanism_id=8`) mechanism — confirms the disabled path is
   numerically identical (bit-for-bit) to never touching the prefilter at all, and that enabling it
   with the real S1 values from this section (0.9992/0.0002/0.0006) retains exactly the dominant
   reaction with a well-formed, deterministic (but numerically distinct, since
   `qmc_sampling.joint_uniform_block`'s joint sampling ties every reaction's column to the same
   shared draw stream — see that test's docstring) design matrix. **Full end-to-end validation
   (a literal `run_script.py` run) remains a documented MANUAL step** — this environment has no
   licensed Chemkin-Pro/FlameMaster install or compiled `samap`/`jpdap` binaries; see
   `test_gsa_reaction_prefilter.py`'s module docstring for the exact manual checklist left for
   whoever has that toolchain.
5. **No PFR support in Zero-RK** — permanent gap, not a task. PFR targets stay on
   cantera/CHEMKIN_PRO/FlameMaster as today.
6. ~~`mpi4py` — install or not?~~ — **RESOLVED (Phase 3): not installed, not needed.**
   `ZerorkGSARunner` invokes `perturbAFactorGSA_mpi.x` via plain
   `subprocess.run([mpiexec, "-n", str(n_ranks), ...])` — no fine-grained Python-side MPI control
   was needed. (Separately, installing `SALib` directly into the shared anaconda environment while
   implementing this phase caused a real, since-reverted incident — see the Phase 3 section above
   — which is why SALib itself now lives in a dedicated venv rather than the main environment.)
7. **`pyDOE` in Zero-RK's own `pyproject.toml` appears unused** by any code found in `python/` —
   noted as an unresolved oddity during the survey, not something this plan depends on either way.

---

## 6. What this plan deliberately does NOT do

- Does not reimplement any Zero-RK solver logic in Julia, C++, or Python. Zero-RK's binaries are
  called as opaque, validated tools via subprocess — same D7 principle as every other external
  solver in this codebase.
- Does not replace `sens_3_params.py`'s 3-parameter brute-force OAT approach — extends it with a
  faster solver backend.
- Does not replace `AnalyticalSobolPRS`/`MCPropagator` — adds a complementary, more expensive but
  surrogate-free GSA path alongside them, with a cross-validation step connecting the two.
- Does not add PFR support to Zero-RK usage (not possible — Zero-RK has no PFR reactor).

---

## MarkDownFiles/PLAN.md — OLD (2026-07-11 vintage 'RMIP Feature Roadmap' doc — superseded by root PLAN.md, rewritten 2026-07-17 to cover the full backlog)

# RMIP — Feature Roadmap
Last updated: 2026-07-11

---

## Deep-review implementation backlog (from `.claude-review/report.md`, 2026-07-11)

A full codebase review (skill: deep-codebase-review) was run 2026-07-11 and is finalized at
`/data/MECHANISM_OPTIMIZATION_SUITE/.claude-review/report.md`. A follow-up implementation
session (same day) worked through the "Quick wins" list; session ended at ~90% usage budget
before the "Structural improvements" list or the Phase 1 should-fix/nice-to-have backlog
could be started. This section is the prioritized plan for continuing that work in a future
session. Read `.claude-review/report.md` in full before resuming — it has exact line numbers,
severity, and reasoning for every item below.

### Done this session (2026-07-11 implementation pass)
- Quick wins 1, 4, 5, 6 (prior pass) + 10, 11, 12, 14 (this session) — see report.md checkboxes.
- Verified already-fixed on disk (stale checklist, not actually done this session): quick wins
  2, 3, 7 (numeric-conversion half), 8, 9, 15 (bind half).
- New blocker found + fixed: duplicate `_on_notebook_tab_changed` method in `generate_target_opt.py`
  (`class App`) silently shadowed the reduction-tab auto-populate handler — renamed and chained.
- Full test suite verified green (355/355) after all changes; `ast.parse` clean on `generate_target_opt.py`.

### Done in follow-up session (2026-07-11, later same day)
- **Structural improvement #1 — ResponseSurface.py bugfix ported.** `src/Sensitivity_Analysis/ResponseSurface.py::MatPolyFitTransform()`
  now uses the same `ii/jj/kk/ll/mm` range-based loops as the already-fixed `src/MUQ-SAC/ResponseSurface.py:315-379`,
  replacing the buggy `row.index(value)`-based loops. Verified against the review's own documented
  example (`[0.5, 0.3, 0.5]` → 10 order-3 terms, not the buggy 21). This was the highest-priority
  live correctness bug (reachable from the GUI's "Run SA" button) — done.
- **Quick win #7 residual — `_chemkin_parser.py` lines 684, 728, 759** (`_parse_arrhenius_triple`/
  `_parse_low_line`/`_parse_plog_line`): `A_units` display label now derived from
  `sum(coeff for _, coeff in rxn.reactants)` (stoichiometric order), matching the formula already
  used by `_extract_representative_kinetics` for the numeric SI conversion. Was cosmetic-only but
  now consistent.
- Full test suite still 355/355 after both changes; `ast.parse` clean on both files.
- `.claude-review/report.md` checkboxes updated for both items.

### Done in second follow-up session (2026-07-11, later same day)
- **`git init` done.** Repo now has version control (root commit `6379ace`, 754 files). Large
  reference/vendored data (`DATASET/`, `PyChemkin-master/`, `MECHANISM/`, `outputs/`, `xml_output/`)
  excluded via `.gitignore` — repo tracks source + small project files only, not the ~780M of data.
  This unblocks quick win #13 and structural improvement #2 below whenever the user wants them done.
- **User explicitly declined the actual deletion/archival** ("no need to delete anything, move to
  another task") — quick win #13 and structural improvement #2 remain **not started, and not
  currently planned**. Don't re-propose deleting `bkp`/`MUQ-SAC_EXTENDED` unless the user brings it
  up again.
- **Phase 1 blocker fixed** (moved up from the backlog per this doc's own priority note — "should be
  prioritized above the structural items once the ResponseSurface fix lands"): the
  `analysis/unified_tree.py:504-512` `KEEP_ANCHOR` anchor-resolution bug. See report.md for full
  detail — short version: `plan()`/`build()` run as separate CLI processes in production
  (`unify-plan` then `unify-build`), and `decisions.csv` never carried `anchor_mech_id` across that
  boundary, so `KEEP_ANCHOR` decisions always silently fell back to `min(source_mech_ids)` and the
  `unified_tree_runs.mode`/`anchor_mech_id` DB columns were always `"unknown"`/`None`. Fixed via a
  `<manifest>.meta.json` sidecar written by `plan()` and read by `build()`. Verified with a manual
  two-process repro (not added as a permanent test this session — see report.md's "good follow-up"
  note). Full suite 355/355.

### Remaining open items (not started, not currently planned)
- Quick win #13 — delete `src/MUQ-SAC/bkp/` + `src/Sensitivity_Analysis/backup/make_input_file.py`
  (~11,554 LOC). Git-safe now, but user declined for now.
- Structural improvement #2 — archive `src/MUQ-SAC_EXTENDED/` (~16,070 LOC). Same as above.
- **New, smaller follow-up surfaced this session (not urgent, not triaged into the numbered lists
  above)**: `analysis/unified_tree.py`'s `_build_rxn_record`/`_pick_verbatim_source` fix has no
  dedicated regression test (existing fixtures always make the anchor the lowest-id mechanism, so
  they can't distinguish old buggy behavior from fixed behavior). Also surfaced but NOT fixed:
  `CanteraYAMLWriter` writes the full reaction formula string (e.g. `"H2+O2<=>H2O"`) as part of the
  YAML equation field instead of a clean Cantera-parseable equation, causing Cantera YAML validation
  to fail (caught internally, logged as a warning, doesn't crash the build) — seen while manually
  verifying the anchor fix above, pre-existing and unrelated to it.

### Remaining backlog, in report.md's priority order (not started)
- Structural improvement #3: consolidate duplicated `Input_file_reader.py`/`getRxnData*` O(N) `.index()`
  lookups across `src/MUQ-SAC/`, `src/Sensitivity_Analysis/` into one shared O(1) dict-based module.
- Structural improvement #4: decompose `generate_target_opt.py`'s `class App` (~4,460 lines / ~150
  methods) into per-tab controller modules — large effort, but this God Object is the direct cause
  of both duplicate-method bugs found across the review + this session.
- Structural improvement #5: numeric-field validation in `_collect()`/`_validate_tab` (currently 4 of
  12 tabs validated); route MSO/MUQ-SAC + Forward UQ runs through the existing `PtyTerminal` widget
  instead of external OS terminal windows.
- Structural improvement #6: GUI framework migration to PySide6 — full phased plan already written
  in report.md's "GUI Framework Migration Plan" section (5 phases, multi-month effort). Sequenced
  last; items 3-5 above de-risk or are prerequisite work for it regardless of whether it's pursued.
- Structural improvement #7: split `config_tools/` into live `build_tools/`-style subset vs. archived
  `legacy/config_tools_oneoffs/` (~3,500 LOC unreferenced scripts).
- Phase 1 should-fix items not yet triaged into quick wins (see report.md Phase 1 section in full):
  `migrations.py` FK-probe idempotency (565-575, 664-689), `analysis/unified_tree.py:377` `zip()`
  truncation (OPTIMIZE decisions silently drop from the Phase-4 audit-trail DB tables if a shorter
  `bands` list truncates the pairing — separate from the already-fixed KEEP_ANCHOR bug at 504-512),
  `analysis/parameter_estimator.py` log(A) filtering (188), `analysis/uncertainty_bands.py`
  ZeroDivisionError (351), `analysis/fusion.py` non-deterministic tie-break,
  `simulation/muqsac_bridge.py` StopIteration on empty fuel_dict (122), and the broader "cli.py has
  zero try/except blocks" UX gap. (`analysis/unified_tree.py:504-512` KEEP_ANCHOR blocker — DONE,
  see above.)
- Test-coverage gaps flagged repeatedly in the review: `generate_target_opt.py` (6,052 lines) has
  zero tests; most `cli.py` subcommands have zero CLI-invocation tests — both directly explain why
  several bugs found in this review shipped unnoticed.

### Process note for whoever resumes
This session discovered that 6 of 15 "quick win" checkboxes in report.md were stale — already
fixed on disk but not marked. Before implementing anything from the lists above, **re-verify the
current line numbers/content against the live file first** (grep the exact snippet from report.md);
don't trust an unchecked box to mean "not done yet."

---


All Phase 5A–5D work is COMPLETE (298/298 tests passing).
All GUI Overhaul phases (GUI-1 through GUI-7) are COMPLETE.
**zerork integration is DEFERRED** (user decision; not scheduled).
This document is retained as a design reference. See `progress.md` for
session-by-session implementation details and `CLAUDE.md §4` for the
compact phase status table.

---

## GUI Overhaul + Toolchain Integration (error.md — Batch 1)  ✅ ALL COMPLETE

Driven by `error.md` (33-line feedback brief). Seven phases, ~38 features.
Master plan: `/home/krithika/.claude/plans/read-the-error-md-and-elegant-micali.md`

| Phase | Scope | Status |
|-------|-------|--------|
| **GUI-1** | Theme (PALETTE/FONTS/HELP), click-ⓘ tooltips, menu bar, checkpoint/restore | ✅ COMPLETE |
| **GUI-2** | Multi-fuel blend UI + MW dialog + `combustion_target_class.py` fixes (both copies) | ✅ COMPLETE |
| **GUI-3** | `xml2csv.py` refactor + GUI XML import panel + `target_tables.py` LaTeX target tables | ✅ COMPLETE |
| **GUI-4** | Progress-file fix, `mso_compare` imports+Fls, thread cap, pipeline parallelism, GUI job launcher | ✅ COMPLETE |
| **GUI-5** | FlameMaster subprocess fix + bounded retry loop + `mech_diagnostics.py` + GUI panel | ✅ COMPLETE |
| **GUI-6** | Gemini PDF notebook, plot digitizer, local-git LaTeX manager, Forward UQ panel + 19 smoke tests | ✅ COMPLETE |
| **GUI-7** | R1 PySR/poly-fit panel, R2 PDF table extraction, R3 RKD XML+YAML export, R4 uncertainty bar mode, R5 MSO report→LaTeX append, R6 UQ plots viewer, R9 PyChemkin ckcsv reader, R10 `.done` sentinel | ✅ COMPLETE |

### New shared modules created
| Module | Location | Purpose |
|--------|----------|---------|
| `chem_data.py` | `/data/OPEN_CODE/PHASE-3/` | Atomic weights, `compute_mw()`, `compute_nu_o2()`, `thread_cap()` |
| `target_tables.py` | `src/` | LaTeX booktabs target-data tables from .target CSV |
| `latex_project.py` | `src/` | Local-git LaTeX project with idempotent section append |
| `mech_diagnostics.py` | `src/MUQ-SAC/` | Cantera-based NASA-7 / collision-limit / reverse-rate checks |
| `pychemkin_reader.py` | `src/` | Thin CKCSVReader wrapper over PyChemkin ckcsv readers |
| `src/notebook_gemini/` | — | `gemini_client`, `pdf_panel`, `digitizer`, `pdf_table_panel`, `pysr_panel` |

### Deferred
- **R8 — zerork integration**: Deferred indefinitely per user decision. No files touched.

---

## Phase 5A — SA/Flux Edge Highlighting  ✅ COMPLETE (2026-06-29)

### What was built
- `rmip/simulation/sensitivity_runner.py` — `CanteraSensitivityRunner.run_idt()`:
  wraps Cantera built-in SA to emit `{"coefficients": {formula: coeff, ...}}`
- `rmip/analysis/visualization.py` — `to_cytoscape_elements()` embeds `importance`
  in edge data; `_default_stylesheet(threshold)` applies 4 CSS bands:
  - `< threshold` → grey, width 1, opacity 0.25
  - `>= 0.1` → green (#4CAF50), width 1.5
  - `>= 0.5` → orange (#FF9800), width 2.5
  - `>= 0.8` → red (#F44336), width 4.0
- `rmip/cli.py` — `visualize` extended: `--sa-json`, `--flux-json`, `--threshold`,
  `--score`; new `sa-run` subcommand

### Design decisions recorded
- SA/flux highlighting is view-layer only — no DB writes
- `--sa-json` accepts comma-separated pair for union mode (one file per mechanism)
- Ghost-node edges always get importance = 0 (always grey)

---

## Phase 5B — Mechanism Reduction  ✅ COMPLETE (2026-07-04)

### Core reducers (DRG / DRGEP / PFA)
- `rmip/reduction/drg.py` — `DRGReducer`: per-reaction rate x stoichiometry
  interaction coefficients r_AB, BFS propagation from seed species, multi-eps sweep.
  Rate sources: Cantera (if mech_path + condition) → flux_score from graph → w=1 fallback.
- `rmip/reduction/drgep.py` — `DRGEPReducer`: max-path coefficient EP_AB via log-space
  Dijkstra. More conservative than DRG at same eps.
- `rmip/reduction/pfa.py` — `PFAReducer`: signed production + consumption path fluxes;
  separates forward/reverse contributions.

### Phase 5B-extended: DRGPSA + DRGSA + visualization (2026-07-04)
- `rmip/reduction/drgpsa.py`:
  - `DRGPSAReducer` — SA-weighted DRG. Each reaction's contribution amplified by
    `(1 + |s_i|)` where `s_i` is its normalized SA coefficient. SA from pre-computed
    JSON (`--sa-json`) or Cantera on-the-fly (`CanteraSensitivityRunner`).
    **Selectivity**: More selective than DRG for species coupled only through non-SA
    reactions — when heavy SA is on reaction R, denom[A] grows while numer[(A,C)]
    stays fixed for species C not in R → r(A,C) shrinks → C may be removed at lower eps.
    This is correct intended behavior.
  - `DRGSAReducer` — Pure SA importance ranking. Per-species importance =
    `max(|s_i|)` over all reactions involving that species. No BFS, no r_AB.
- `rmip/reduction/coefficient_viz.py` — `CoefficientVisualizer`:
  Dash app with 3 tabs: r_AB heatmap (Viridis, seeds starred), 2D network (spring-layout
  species subgraph, edges coloured/weighted by r_AB strength with threshold slider),
  3D network (Plotly Scatter3d using carbon-ring coords). `export_html()` for static snapshots.
- `rmip/reduction/trim_viz.py` — `TrimVisualizer`:
  Dash app with eps slider + 3 tabs: BFS propagation coloring (0=green/seed, deeper waves
  → red), 2D trim (full bipartite graph, retained blue/seed green vs removed red/faded),
  3D trim (same in Scatter3d). `export_html()` for static snapshots.

### Data model additions (types.py)
- `ReductionStep.bfs_levels: Dict[str, int]` — BFS wave-front level per retained species
  (seeds=0, first neighbours=1, etc.)
- `ReductionResult.r_AB: Dict[str, Dict[str, float]]` — full interaction matrix (JSON-serialisable)
- `ReductionResult.sa_coefficients: Dict[str, float]` — SA coefficients used for DRGPSA/DRGSA

### DB changes
- `reduction_runs` table CHECK constraint widened from `('DRG','DRGEP','PFA')` to
  include `'DRGPSA'` and `'DRGSA'`. Handled by `_ensure_wide_reduction_method_constraint()`
  in `migrations.py` using the same savepoint-probe + table-recreation pattern as the
  `mechanisms.format` constraint widening.

### CLI additions
- `reduce`: `--method` now accepts `DRG|DRGEP|PFA|DRGPSA|DRGSA`; `--sa-json FILE` added
- `reduce-viz`: new command — `--mode coeff|trim|both`, `--port`, `--export-html`, `--threshold`

---

## Phase 5C — 3D / Concentric-Carbon-Ring Layout  ✅ COMPLETE (2026-07-03)

### 2D carbon-ring layout
- `core/graph_builder.py` — `_carbon_ring_positions()`: species on concentric rings
  by carbon number (C0 center at R0, Cn at radius n*delta_r), uniform angular spacing
  alphabetically within each ring. Reaction nodes at centroid of participating species.
- Exposed as "Preset — Carbon rings (by Cn, fixed)" in visualizer layout dropdown.

### 3D stacked-disc layout
- **Geometry:** flat rings (not spheres) stacked in z by carbon number.
  Ring radius = `(0.5 + shell_gap*n)*delta_r`. Ring plane at z = `layer_gap*delta_r*n`.
  Spheres were abandoned: they project as filled discs from any camera angle regardless
  of radial gap — flat rings in separate z-planes keep every orbit visible.
- Two angular orderings stored per node: alphabetical (`pos_x/y/z_3d`) and
  chemical-family arcs (`pos_x/y/z_3d_fam`: hydrocarbons → oxygenates by O count →
  N-containing). Live "Ring order" radio in Dash app to flip without rebuilding.
- Same-ring reactions lifted +0.4 layers; radial-collapse push in xy-plane.
- `analysis/visualization3d.py` — `NetworkVisualizer3D`: Plotly Scatter3d Dash app
  (Turbo colorscale by Cn, orbit wireframes, label/ring-order radios,
  edges/orbits/ghosts toggles, dual-panel union mode, `export_html()`).
- CLI: `visualize3d <id> [id2] --db DB [--union] [--shell-gap F] [--layer-gap F]
  [--order alpha|family] [--export-html PATH] [--port N]`

### Bug fixed en route
- `scipy.sparse` never imported by networkx 3.2.1 on scipy 1.8 → `AttributeError`
  on `spring_layout` for graphs with >500 nodes. Pre-import added to `graph_builder.py`.
  This bug previously crashed ALL large-mechanism visualization silently.

---

## Phase 5D — Identical-SMILES Species Disambiguation  ✅ COMPLETE (2026-06-29)

### Tier 1 implementation
- `rmip/io/glossary_reader.py` — `load_variants(path)` reads `species_variants.csv`
- `rmip/core/parser.py` — `parse()` accepts `variants_path`; applies variant overrides
  so (e.g.) OHEX shares OH's InChIKey → recognized as same species in union graph
- `rmip/database/migrations.py` — `run_phase5d_migrations(conn)` adds
  `species.variant_tag` and `species.canonical_name` columns (idempotent ALTER TABLE)
- `rmip/cli.py` — `parse` command: `--variants FILE`
- `rmip/analysis/visualization.py` — `node[variant_tag]` selector: double orange border

`species_variants.csv` format:
```csv
variant_name,canonical_name,reason
OHEX,OH,excited_state
HNO2,HONO,tautomer
```

### Tier 2 / Tier 3 (deferred, not yet requested)
- Tier 2: Automatic InChIKey collision detection during glossary → log WARNING + suggest
  adding to `species_variants.csv`
- Tier 3: RDKit InChI layer pruning (`-SNon`) for tautomer detection in `canonicalize.py`

---

## Phase 5+ stubs (future work)

These modules have full docstring + signature stubs in `rmip/stubs.py` with
`raise NotImplementedError`. Designs are deliberately not recorded here yet —
wait until KP decides to implement them.

| Module | Class | Description |
|--------|-------|-------------|
| M9 | `DoEFramework` | Sobol/LHS DoE for FUSE reaction parameters — **design now exists, see below** |
| M10 | `AIRecommender` | Graph + kinetics-based recommendation engine |
| M11 | `ChangeLog` | DB modification tracker + diff reports between mechanism versions |
| M12 | `ReportEngine` | LaTeX/HTML report generation |
| M13 | `UQFusion` | UQ-aware fusion using MUQ-SAC Cholesky covariance decomposition |

### M9 `DoEFramework` — full plan now written (2026-07-11)

KP asked whether to build fast in-house solvers + global sensitivity analysis (GSA) in Julia/C++
(reimplementing what Zero-RK does) or wrap Zero-RK — decided: **wrap Zero-RK, don't reimplement.**
GSA scope: extend `src/Sensitivity_Analysis/` (brute-force OAT) and `src/forward_uq/` (PRS-based
Sobol), and bring in Zero-RK's own GSA-related applications.

Full extensive plan, including a verified inventory of Zero-RK's actual capabilities and this
repo's existing SA/UQ code, is written at **`MarkDownFiles/ZERORK_GSA_PLAN.md`**. Six phases: build
Zero-RK → `zerork_bridge.py` subprocess wrapper → `solver="zerork"` option in the existing
brute-force SA → implement `DoEFramework.run_screening()` for real (SALib Sobol/Morris driven by
Zero-RK's `perturbAFactorGSA` MPI batch machinery — Zero-RK's own "GSA" apps only dump raw Monte
Carlo samples, they don't compute indices themselves, that gap is what Phase 3 fills) → wire back
into the PRS/Forward-UQ pipeline → CLI/GUI. ~3-4 weeks estimated.

**Phase 0 (build + validate Zero-RK) is DONE (2026-07-11)** — installed at
`/home/krithika/zero-rk/build2/inst_dir/bin/`, 145/145 internal tests passing, output
cross-validated against this repo's Cantera solver to 0.00004% agreement on a real `project.db`
mechanism. Found and fixed 3 build-config issues along the way (SUNDIALS version silently disables
the TLA sensitivity solver if not built from source; anaconda's MPI compiler wrapper is broken for
this build; Zero-RK's system-SuperLU CMake option has an include-path bug on Ubuntu) — full detail
in `ZERORK_GSA_PLAN.md`'s Phase 0 section, including the exact working configure command. Phases
1-5 (the actual `zerork_bridge.py`, SA/GSA integration, CLI/GUI) not started — resume there.

---

## Completion history

| Priority | Phase | Completed |
|----------|-------|-----------|
| 1 | 5A — SA/flux edge highlighting | 2026-06-29 |
| 2 | 5D — SMILES disambiguation Tier 1 | 2026-06-29 |
| 3 | 5C — Carbon-ring 2D + 3D stacked-disc | 2026-07-03 |
| 4 | 5B — Mechanism reduction (DRG/DRGEP/PFA) | 2026-07-04 |
| 5 | 5B-ext — DRGPSA/DRGSA + coeff/trim viz | 2026-07-04 |

---

## MarkDownFiles/progress.md — OLD (superseded by root progress.md; its detail already covered by MarkDownFiles/HISTORY.md, esp. parts 41-44)

# RMIP — Implementation Progress Log
Last updated: 2026-07-12

---

## Current status: RMIP Phases 1–6 COMPLETE + GUI Overhaul GUI-1 through GUI-7 ✅ ALL COMPLETE. Deep-review implementation IN PROGRESS (see below + `PLAN.md`). Zero-RK integration + GSA plan IN PROGRESS (Phase 0 + Phase 1 done — see `ZERORK_GSA_PLAN.md`; Phase 2-5 not started).

---

## Session 2026-07-12 — Zero-RK Phase 1 (`zerork_bridge.py`) — done, 6 real parser/writer bugs found+fixed

Resumed from a session that got cut off mid-debug (API connection error) partway through getting a
first end-to-end Zero-RK IDT run working — `zerork_bridge.py` existed as an uncommitted draft,
`chemkin_writer.py` had one partial fix in flight (NASA-7 Tmid field width), and the test run was
failing with `could not parse mech`. Picked up from there and pushed the debug through to a fully
working, cross-validated IDT + JSR round-trip. Full six-bug list and verification details are in
`ZERORK_GSA_PLAN.md`'s Phase 1 section (not duplicated here) — headline: none of the six bugs were
Zero-RK-specific, all were silently-wrong CHEMKIN parse/write round-trip behavior that no consumer
had been strict enough to surface before (Cantera's own `ck2yaml` tolerates all of them). The
dominant one: `species.formula` was never populated by `_chemkin_parser.py` at all, so every
CHEMKIN-sourced mechanism's ELEMENTS block and every species' THERMO elemental-composition columns
have been silently wrong/blank since this codebase's CHEMKIN parser existed — Zero-RK derives
molecular weight from those declared elements (not name lookup), so this produced a universal
NaN-at-t=0 solver failure until fixed.

Committed as `10c77d2` (code only — `_chemkin_parser.py`, `chemkin_writer.py`,
`simulation/base.py`'s ck2yaml-entry-point-detection robustness fix, new `zerork_bridge.py`).
**Deliberately did not re-parse the live `outputs/project.db`** — mechanisms 1-4 (all
CHEMKIN-sourced) were parsed with the old buggy parser, so their `species.formula`/ELEMENTS data is
stale, and GRI-3.0 (mechanism_id=1) specifically has stale Ea values (was being read as cal/mol
instead of the file's actual Kelvin/`Ea/R` convention). Left for explicit user confirmation before
touching, since existing SA runs/reductions/comparisons already reference these mechanism_ids and
`rmip_cli.py parse` creates new IDs rather than updating in place.

Not started this session: Phase 2 (`solver="zerork"` in `sens_3_params.py`/`simulation_manager2_0.py`),
Phase 3 (real Sobol/Morris GSA via SALib + `perturbAFactorGSA`), Phase 4 (PRS pipeline wiring),
Phase 5 (CLI/GUI). Also not started: the `make_input_files.py`/`combustion_target_class.py`
Zero-RK integration KP asked for (adding it as a `solver=` option alongside FlameMaster/Cantera/
CHEMKIN_PRO, plus surfacing whatever Zero-RK-only capabilities aren't in `make_input_files.py`
today), the `~/mechanism-optimization-suite` version-control merge, and the GUI-separation planning
task — all still open, see conversation for current prioritization discussion.

Full test suite 355/355 throughout, no regressions.

---

## Session 2026-07-11 (third follow-up) — Zero-RK integration plan + Phase 0 (build & validate)

KP asked whether to build fast in-house combustion solvers + global sensitivity analysis (GSA) in
Julia/C++ (reimplementing what LLNL's Zero-RK does), or wrap Zero-RK instead. Recommended and KP
confirmed: **wrap Zero-RK, don't reimplement** — its value is ~15 years of validated analytical
sparse-Jacobian and reactor-physics engineering, not the ODE-solver algorithm itself. GSA scope per
KP: extend the existing brute-force `src/Sensitivity_Analysis/` and `src/forward_uq/` codebases,
and bring in Zero-RK's own GSA-related applications.

**Grounding research** (two parallel Explore-agent surveys, one on Zero-RK's actual source at
`/home/krithika/zero-rk/`, one on this repo's existing SA/UQ code) found: Zero-RK's own "GSA" apps
(`perturbAFactorGSA`, `variable_volume_gsa`) are MPI-parallel Monte Carlo batch runners that dump
raw per-sample IDT results — they do NOT compute Sobol/Morris indices themselves, that's a real gap
to fill in Python. `rmip/stubs.py`'s unimplemented `DoEFramework` (M9) stub already specifies
exactly this design (SALib-based screening) — implementing an existing spec, not inventing one.
Full six-phase plan written to `MarkDownFiles/ZERORK_GSA_PLAN.md`.

**Phase 0 (build & validate Zero-RK) executed and DONE this session.** Zero-RK source was on disk
but not built (confirmed: a stale partial `cmake` configure existed, zero compiled binaries
anywhere — matched KP's own note that it "is not yet installed"). Built fresh in
`/home/krithika/zero-rk/build2/` (original stale `build/` left untouched, not deleted). Found and
fixed three real build-configuration bugs along the way (not anticipated in the original plan):

1. System SUNDIALS (3.1.2, via apt) not only wasn't found by Zero-RK's `find_library` calls, but
   **using anything other than SUNDIALS 5 silently disables `constVolumeWSR_TLA`** (the
   Tangent-Linear-Approximation sensitivity solver this whole plan leans on) **and the counterflow
   flame solvers** at configure time — confirmed via the configure log's own
   `"... disabled for SUNDIALS_VERSION!=5"` messages. Not a speed tradeoff, a hard capability
   requirement. Used `-DSUNDIALS_VERSION=5` (from source, ~10 min build on 160 cores).
2. Anaconda's `mpicc`/`mpicxx` invoke a conda-specific compiler (`x86_64-conda_cos6-linux-gnu-cc`)
   not installed in this environment — broke the nested SUNDIALS `ExternalProject` sub-build.
   Top-level `-DMPI_C_COMPILER=...` flags don't propagate into that sub-build (Zero-RK's own
   `ExternalProject_Add` only forwards `CMAKE_INSTALL_PREFIX`) — fixed by prepending `/usr/bin` to
   `PATH` for the whole configure invocation so the sub-build's own compiler auto-detection finds
   the working system OpenMPI instead.
3. `-DSYSTEM_SUPERLU_ROOT=/usr` fails to compile anything using SuperLU headers — Zero-RK's
   `cmake/superlu.cmake` assumes a flat `${root}/include/slu_ddefs.h` layout, but Ubuntu's
   `libsuperlu-dev` package installs under `/usr/include/superlu/` — a real packaging mismatch in
   Zero-RK's own CMake code. Fixed by not using system SuperLU/SuperLU_DIST at all — let Zero-RK
   build both from source (fast, ~1-2 min).

**Full validation, all passed:** `ctest` 145/145. 50 binaries built including every application the
plan depends on. Acceptance-gate smoke test (`examples/perturbAFactorGSA/`, shipped H2 mechanism,
1000-sample MC batch via MPI) matched the shipped `.dat.ref` reference to 5-6 significant figures
(had to regenerate the sample matrix using anaconda's Python — the documented `/usr/bin/python3.9`
has a broken numpy install, unrelated to Zero-RK). **Cross-validation against this repo's own
Cantera-based solver**, on GRI-3.0-wetCO (already in `project.db`, confirmed to actually be a
reduced 14-species H2/CO syngas mechanism, not full 53-species GRI-3.0) at T=1000K/P=10atm/φ=1,
H2/air: Zero-RK 8.0618713571932385e-03 s vs. Cantera 8.0618681668e-03 s — **0.00004% relative
difference.** This was the real correctness gate for the whole plan and it passed cleanly.

Install prefix for Phase 1 to reference: `/home/krithika/zero-rk/build2/inst_dir/bin/`.

**Not started:** Phases 1-5 (`zerork_bridge.py`, `solver="zerork"` SA integration, real GSA via
SALib, PRS-pipeline wiring, CLI/GUI). Also did some Phase-1 groundwork while Phase 0's build ran in
the background: confirmed `rmip/io/chemkin_writer.py`'s `ChemkinWriter.write()` is DB-driven (not
format-of-origin-driven), so it already covers the Cantera-YAML→CHEMKIN-ASCII conversion Zero-RK
needs — no new converter required, one of the plan's open questions resolved for free.

All docs updated: `ZERORK_GSA_PLAN.md`'s Phase 0 section rewritten with full findings and the exact
working configure command; `PLAN.md`'s pointer updated; this entry. Stopped here (not proceeding
into Phase 1 code) per usage-budget awareness — this is a clean, fully-validated checkpoint.

---

## Session 2026-07-11 (second follow-up) — git init + unified_tree.py anchor-resolution blocker

Continuation of the same day's work. Two things happened in this session:

**1. `git init`.** User approved initializing version control for this repo (previously no git,
no rollback safety). Wrote a `.gitignore` excluding the large reference/vendored data directories
(`DATASET/` 300M, `PyChemkin-master/` 296M vendored third-party code, `MECHANISM/` 184M, plus
`outputs/`, `xml_output/`, caches, transient runtime files) so the tracked repo stays focused on
source code (~100M) rather than the full 896M working directory. Checked for secrets before
committing (`.claude/settings.local.json` is just a Claude Code permission allowlist, nothing
sensitive). Root commit `6379ace`, 754 files. This unblocks quick win #13 (delete `bkp`/`backup`
dirs) and structural improvement #2 (archive `MUQ-SAC_EXTENDED/`) whenever wanted — **user then
explicitly said not to do the actual deletion/archival ("no need to delete anything, move to
another task")**, so those remain not started and not currently planned. Don't re-propose them
unless asked again.

**2. Fixed the `analysis/unified_tree.py:504-512` blocker** — the next-highest-priority item per
`PLAN.md`'s own note ("should be prioritized above the structural items once the ResponseSurface
fix lands"). The bug: `_pick_verbatim_source()` resolved `KEEP_ANCHOR` decisions via
`min(d.source_mech_ids)` instead of the actual anchor mechanism id. Investigation found the root
cause was deeper than the one-line description: `plan()` and `build()` run as **separate CLI
processes** in the real `rmip unify-plan` / `rmip unify-build` workflow, and the only thing passed
between them (`decisions.csv`) never carried `anchor_mech_id` at all — so in every real
CLI-driven build, `anchor_mech_id` was `None`, not just wrong in the "non-anchor mech has a lower
id" edge case. This also meant `unified_tree_runs.mode`/`anchor_mech_id` DB columns were always
`"unknown"`/`None` for every production run — a second, previously-unreported symptom of the same
gap.

**Fix:** `plan()` now writes a `<manifest_path>.meta.json` sidecar (`{mode, anchor_mech_id}`)
alongside `decisions.csv`. `build()` reads it when called with `manifest_path` only (the real CLI
path, `plan=None`), falling back to `("unknown", None)` with a logged warning if the sidecar is
missing (e.g. an old manifest from before this fix — backward compatible). `anchor_mech_id` is now
threaded through `_build_rxn_record()` → `_pick_verbatim_source()`, which resolves `KEEP_ANCHOR` to
the real anchor id, falling back to `min(source_mech_ids)` with a logged warning only if the anchor
is genuinely unresolvable.

**Verification:** existing test fixtures always make the anchor the lowest-id mechanism, so they
can't distinguish old buggy behavior from fixed behavior (355/355 pass either way — this was true
before and after). Wrote a manual two-process repro instead (not committed as a permanent test —
flagged in `PLAN.md` as a good follow-up): two separate `UnifiedTreeBuilder` instances, one calling
`plan()` with `anchor_mech_id` set to the *higher*-id mechanism (which has divergent kinetics from
the lower-id one on a shared reaction), the other calling `build()` with only `manifest_path`.
Confirmed the unified reaction correctly carries the anchor's kinetics, not the lower-id
mechanism's. `ast.parse` clean; full suite 355/355.

**Surfaced but not fixed** (pre-existing, unrelated, seen only because the repro above ran
`CanteraYAMLWriter`): the YAML writer emits the full reaction formula string as part of the
Cantera equation field, causing YAML validation to fail (caught internally as a warning, doesn't
crash the build). Not triaged into `PLAN.md`'s numbered lists — noted there as a loose end.

Updated `.claude-review/report.md`'s finding for this blocker to FIXED with full detail; updated
`PLAN.md`'s "Immediate next steps" accordingly.

---

## Session 2026-07-11 (follow-up) — Structural improvement #1 + quick-win #7 residual

Resumed from `PLAN.md`'s "Immediate next steps" list (written at the end of the earlier
2026-07-11 session below). Picked the two safe, non-destructive items first — both are edits,
neither touches the `bkp`/`MUQ-SAC_EXTENDED` legacy-dir questions that need a git-safety decision.

- **Ported the `ResponseSurface.py` bugfix** (Structural improvement #1, report.md's top-priority
  item): `src/Sensitivity_Analysis/ResponseSurface.py::MatPolyFitTransform()` lines 271-313 used
  `row.index(value)`-based loops for order-3/4/5 polynomial terms, which silently produced
  duplicate monomials (and the wrong column count) whenever two row values were equal — common
  when zeta samples cluster near the same value. Replaced with the `ii/jj/kk/ll/mm` range-based
  loops already fixed in the sibling `src/MUQ-SAC/ResponseSurface.py:315-379`, ported verbatim and
  matched to this file's tab-indentation style. Verified numerically against the review's own
  documented example: `row = [0.5, 0.3, 0.5]` now yields 10 order-3 terms (`C(5,3)`), not the
  buggy 21. This was a live, reachable correctness bug wired to the GUI's "Run SA
  (sens_3_params.py)" button.
- **Quick win #7 residual**: `src/rmip/io/_chemkin_parser.py` lines 684, 728, 759
  (`_parse_arrhenius_triple`/`_parse_low_line`/`_parse_plog_line`) derived the `A_units` display
  label from `len(rxn.reactants)` (species count) instead of stoichiometric order — cosmetic/
  metadata-only (the real numeric SI conversion in `_extract_representative_kinetics` was already
  correct), but inconsistent. Changed all three sites to
  `sum(coeff for _, coeff in rxn.reactants)`, matching the already-fixed numeric-conversion path.
- **Verification:** `python -m pytest src/rmip/tests/ -q` → 355/355 passing (unchanged — neither
  fix touches existing test-covered behavior differently than before). `ast.parse` clean on both
  modified files.
- Updated `.claude-review/report.md` checkboxes for quick-win #7 and structural improvement #1 to
  IMPLEMENTED; updated `PLAN.md`'s "Immediate next steps" to drop these two and keep only the two
  git-safety-gated items (quick win #13 deletion, structural improvement #2 archival).
- **Not done, still needs the user**: quick win #13 (delete `bkp`/`backup` dirs, ~11,554 LOC) and
  structural improvement #2 (archive `MUQ-SAC_EXTENDED/`, ~16,070 LOC) — both recommended to wait
  on an explicit `git init` decision since this repo still has no version control.

---

## Session 2026-07-11 — Deep-review quick-wins implementation pass

Followed up on the deep-codebase-review finalized earlier the same day
(`.claude-review/report.md`). Instructed to start implementing the review's "Quick wins" list
and finish what's possible; session was cut short by usage budget (~90%) before the
"Structural improvements" list could be started. Full detail, exact line numbers, and the
prioritized continuation plan are in `PLAN.md`'s new "Deep-review implementation backlog"
section — this entry is a summary.

**Verification-first approach:** before editing anything, re-checked all 15 quick-win line
references against the live file. Found 6 already fixed on disk but not reflected in
report.md's checkboxes (`self.after`→`self.root.after`, hardcoded anaconda path removed,
chemkin parser/writer reaction-order SI conversion, Dash `0.0.0.0`→`127.0.0.1` binding,
`shlex.quote()` on shell interpolation, duplicate `<<NotebookTabChanged>>` bind) — likely from
an earlier untracked edit pass. Updated report.md's checkboxes to reflect reality rather than
re-doing already-correct work.

**Implemented this session:**
- `generate_target_opt.py::_clear_trows` — added `askyesno` confirmation guard (skipped when
  the row list is already empty; internal checkpoint-restore call site passes `confirm=False`
  so restoring a checkpoint doesn't pop a spurious dialog).
- `generate_target_opt.py` — all 10 literal `foreground="gray"` → `foreground=PALETTE["text_dim"]`.
- Deleted `generate_target_opt_PHASE4_FIX.py` (confirmed zero references repo-wide first).
- `generate_target_opt.py::_scrolled` — added mouse-wheel binding (`<MouseWheel>` +
  `<Button-4>`/`<Button-5>`, bound/unbound on canvas `<Enter>`/`<Leave>`) — applies to all 12
  tabs since they all route through this helper.
- **New blocker found + fixed** (not in the original quick-wins list, surfaced during
  re-verification): two methods in `class App` were both named `_on_notebook_tab_changed`
  (~line 2772: reduction-tab auto-populate handler; ~line 4519: tab-locking handler). Python
  silently keeps only the later definition, so the auto-populate-reduction-target feature was
  dead code even though the earlier *duplicate bind* bug (separate finding) had already been
  fixed. Renamed the first to `_on_notebook_tab_changed_for_reduction`; the surviving
  `_on_notebook_tab_changed` now calls it at the end, so both behaviors run on every tab change.

**Deliberately not done:** quick win #13 (delete `src/MUQ-SAC/bkp/` +
`src/Sensitivity_Analysis/backup/make_input_file.py`, ~11,554 LOC) — this repo has no git, so
there's no cheap rollback if the review's "already duplicated under `version_history/`" claim
turns out to be stale. Left for explicit user confirmation (recommend `git init` first). See
`PLAN.md` for the full remaining backlog (ResponseSurface.py bugfix port, MUQ-SAC_EXTENDED
archival, App God-Object decomposition, GUI migration plan, etc.) in priority order.

**Verification:** `python -m pytest src/rmip/tests/ -q` → 355/355 passing (unchanged — none of
this session's edits touch `src/rmip/`). `ast.parse` clean on `generate_target_opt.py` after
all edits.

---

## Session 2026-07-05 (Phase 6) — Future.md Part 2, features 1–7

Implemented all seven feature ideas from `Future.md`'s Part 2 (features 2 and 4 merged per
KP's instruction). Points 3 (flux analysis) and 6 (JSR/PFR) route through the live
`src/MUQ-SAC/` pipeline across all three solvers (cantera/CHEMKIN_PRO/FlameMaster), per KP's
explicit direction, rather than new native RMIP simulation code. Point 7 (NTC detection) was
extended per KP to also produce an HTT/LTT split that **replaces** the fixed 850/1000 K
LTC/NTC/HTC regime thresholds wherever a mechanism has a detected NTC onset.

**Test status: 355/355 passing** (298 prior + 57 new `test_phase6.py`).

### Feature 1 — Reverse Rate Unphysicality Scanner (`analysis/reverse_rate_scanner.py`, new)
- `ReverseRateScanner.scan(mechanism_id)`: for every `reversible=1` reaction with full NASA-7
  thermo on all participants, computes `k_rev(T) = k_fwd(T) / Kc(T)` via ΔH°(T)/ΔS°(T) from
  NASA-7 polynomials and flags `k_rev` exceeding a T-scaled collision limit
  (`1e8·sqrt(T/298.15) m³/mol/s`) by > 3 orders of magnitude (configurable).
- Only bimolecular-reverse reactions (forward product-side stoich sum = 2) are flagged —
  collision theory gives a clean bound only there; others are evaluated but skipped.
- CHEMKIN parser discards `REV /` blocks entirely (never in the DB), so explicit reverse
  Arrhenius fits can't be excluded — documented limitation, all `reversible=1` scanned.
- New `reverse_rate_flags` table; CLI `reverse-scan`.

### Features 2+4 — Mechanism Report, merged (`analysis/mechanism_report.py`, new)
- `QualityScorer`: composite 0–100 "trust index" — SMILES resolution %, thermo Tmid
  continuity, `ReverseRateScanner`-based rate-bounds score, optional Hf-vs-ATcT agreement,
  optional NTC coverage. Weights renormalise over whichever components are supplied.
- `MechanismDiffEngine`: two-mechanism diff (species/reactions added/removed, shared-reaction
  log10(A) ratios, thermo Cp/R deltas) — reuses `ComparisonEngine.compare()` rather than
  reimplementing species/reaction cross-referencing.
- **Fixed a pre-existing bug** in `analysis/comparison.py::ComparisonEngine._compare_species()`
  discovered by this work: `sp_sets[mid][mid]` (indexed by mechanism id) should have been
  `sp_sets[mid][key]` (indexed by inchi_key) — always raised `KeyError` whenever any species
  was actually shared across mechanisms. This is the first code path to exercise that branch
  with real overlapping-species test data.
- `MechanismReport.report([id])` → quality only; `.report([id_a, id_b])` → quality-each +
  diff. HTML export via plotly (bar chart of composite scores + log-A-ratio chart), matching
  the `reduction/coefficient_viz.py` export pattern. New `mechanism_quality_scores` table;
  CLI `report`.

### Feature 5 — PLOG Rate Surface Visualizer (`analysis/plog_surface.py`, new)
- `PlogSurfaceBuilder.build()`: log10 k(T,P) grid over a T/P grid, reusing the log-linear PLOG
  interpolation already in `analysis/uncertainty_bands.py` rather than reimplementing it.
- Flags non-monotonic k(P) at the mechanism's own explicit PLOG pressure levels (not the
  display grid — a real PLOG-fitting pathology) and an ill-defined high-P limit when fewer
  than 2 pressure levels are given.
- Interactive plotly Surface + Contour two-panel figure; CLI `plog-surface`.

### Feature 7 (extended) — NTC Detection + HTT/LTT split (`analysis/ntc_detector.py`, new)
- `NTCDetector.detect()`: runs a φ-fixed `IDTRunner` sweep, finds the NTC onset (first local
  **minimum** of IDT(T) sweeping low→high T) and end (following local **maximum**) via
  sign-change detection on `d(ln IDT)/dT` with a 1% dead-zone against noise.
- `NTCReport.classify(T)` / module-level `split_targets_by_ntc()`: T > onset → HTT
  (High-Temperature Target), T < onset → LTT — on the 1/T (Arrhenius) scale, per KP's
  extension of the base feature idea.
- `tag_exp_dataset()` writes the new `exp_data_points.temp_target_class` column for MSO
  target selection.
- **`analysis/benchmarking.py` and `simulation/performance_ranker.py` updated**: regime
  classification is now computed **per mechanism** (was: once, shared across all mechanisms
  in a comparison) — prefers the mechanism's own detected `ntc_runs.T_NTC_onset` (HTT/LTT
  regimes) and falls back to the fixed 850/1000 K LTC/NTC/HTC split only when no NTC run has
  been stored for that mechanism. `Regime` enum (`types.py`) gained `HTT`/`LTT` members.
- New `ntc_runs` table; CLI `ntc` (with `--tag-dataset`).

### Points 3 + 6 — Flux analysis / JSR / PFR via the MUQ-SAC pipeline, all 3 solvers
**`src/MUQ-SAC/make_input_file.py::create_input_file()`** (the canonical, actively-edited
pipeline — NOT the stale `MUQ-SAC_EXTENDED/`):
- JSR branch (previously cantera-only, unconditional) now dispatches on `solver` like every
  other branch: `cantera` (existing script, extended with a `jsr_full.json` full-composition
  dump alongside the pre-existing single-species `jsr.out` — additive, doesn't change what
  `data_management.py` reads), `CHEMKIN_PRO` (PyChemkin's `writeinputJSR()` +
  `CKReactorGenericPSR` model — **KP to verify** exact executable name), `FlameMaster`
  (`Flame is PSR` deck — **KP to verify** keyword set against your build).
- New PFR branch, same three-solver structure: `cantera` uses a Lagrangian-marching
  `IdealGasConstPressureReactor` (dt = dz/u recomputed from local density each step —
  textbook idealized-PFR integration, no axial diffusion); `CHEMKIN_PRO` uses PyChemkin's
  `writeInputPlugFlow()` + `CKReactorPlugFlow` (**KP to verify**); `FlameMaster` approximates
  a PFR via a fixed-mass-flux `BurnerStabilizedFlame` (closest available mode in this
  toolchain — unlike an idealized PFR it still includes axial diffusion; **KP to verify**).
- Flux analysis: `target.add["flux_analysis"]` (new, applies to the JSR/PFR branches above)
  toggles `ReactionFluxAnal is TRUE` for FlameMaster, `job.postprocess(rop=True)` for
  CHEMKIN_PRO, and an appended `gas.net_rates_of_progress` dump to `output/flux.json` for
  cantera.
- `combustion_target_class.py`: new default addendum keys for PFR geometry
  (`pfr_length`/`pfr_diameter`/`pfr_mdot`/`pfr_n_points`) and flux analysis
  (`flux_analysis`/`flux_element`), plus previously-undefaulted JSR keys
  (`maxSimulationTime`, `species`).
- **Two real unit-conversion bugs caught and fixed during development** (see CLAUDE.md §11
  "MUQ-SAC Bridge" for detail): (1) `target.pressure` is already in Pa by the time
  `create_input_file()` sees it (unconditional unit conversion in
  `combustion_target_class.__init__`) — the new JSR/PFR `CHEMKIN_PRO` branches were
  initially re-multiplying by 101325, and the new `jsr_full.json`/`pfr_full.json` outputs
  were initially mislabelling the raw Pa value as `P_atm`; (2) PyChemkin's
  `writeinputJSR()`/`writeInputPlugFlow()` expect pressure in **bar**, not Pa (they divide
  by 1.01325 internally to get atm) — fixed to convert Pa → bar before calling them. Caught
  by tracing the actual unit-conversion code path and confirmed by round-tripping a
  bridge-generated `.target`/`.add` pair through the real `combustion_target_class` parser.

**New `src/rmip/simulation/muqsac_bridge.py`** (`MuqsacBridge`) — the RMIP↔MUQ-SAC seam
(subprocess-only, D7-style — never imports MUQ-SAC modules):
- `build_target_files()`: resolves `SimCondition.fuel`/`.oxidizer` to exact mole fractions via
  a real `ct.Solution.set_equivalence_ratio()` call, splits them the way `.target` files
  expect (fuel species → `Fuel`, `O2` → `Oxidizer`, rest → `Bath_gas`), and writes a
  single-target `.target` + `.add` + a derived `target.opt` (patched from a KP-supplied base
  config, not mutated in place).
- `run()`: `subprocess.run(["python3", run_script_path, target_opt])`.
- `parse_jsr_output()`/`parse_pfr_output()`/`parse_flux_output()`: read the additive
  `output/*_full.json`/`flux.json` files into `JSRResult`/`PFRResult`/`FluxResult`.
- `store_reactor_result()`/`store_flux_result()`: persist to `simulation_runs`
  (`extra_json` column carries full composition / axial profile) / `flux_runs`.
- Validated end-to-end (not just unit-tested): a bridge-generated `.target`/`.add` pair was
  round-tripped through the real `combustion_target_class`, fed into the real
  `create_input_file()`, and the resulting cantera JSR/PFR scripts were actually executed
  against a real Cantera mechanism — correct physical output confirmed (species profiles,
  flux ROP values). CHEMKIN_PRO/FlameMaster paths are structurally validated (deck content,
  valid-Python-syntax for generated scripts) but not run against a licensed solver install.
- `JSRRunner`/`PFRRunner` (`simulation/jsr_runner.py`/`pfr_runner.py`, new): thin
  `run_single()`/`run_batch()` orchestration mirroring `IDTRunner`'s API shape.
- New `simulation_runs.extra_json` column (idempotent migration); `simulation_runs.sim_type`
  CHECK widened to add `'JSR'`/`'PFR'`/`'FLUX'` — this widen migration is wrapped in an
  explicit `BEGIN`/`COMMIT` with a leftover-table recovery check, added after
  `executescript()`'s non-atomicity (a pre-existing pattern also used by the Phase-3/5B
  format-widening migrations) left a live test DB with an empty `simulation_runs` table and
  the real data stranded in `_simulation_runs_old` after a column-count mismatch during dev.
- CLI: `flux`, `jsr`, `pfr` (all take `--solver cantera|chemkin|flamemaster`,
  `--base-target-opt`, `--work-dir`, `--dry-run` to inspect generated files without invoking
  `run_script.py`).

### Schema / types (`database/schema_phase6.py`, `database/migrations.py::run_phase6_migrations`, `types.py`)
- New tables: `ntc_runs`, `reverse_rate_flags`, `mechanism_quality_scores`, `flux_runs`.
- New dataclasses: `JSRResult`, `PFRResult`, `FluxResult`, `ReverseRateFlag`, `QualityScore`,
  `MechanismDiffResult`, `PlogSurface`, `NTCReport`, plus `SolverName`/`TempTargetClass` enums.
- All migrations idempotent (verified: called 3× in a row, no error, no duplicate rows).

### Known gaps / follow-ups for KP
- CHEMKIN_PRO reactor model executable names (`CKReactorGenericPSR`, `CKReactorPlugFlow`) and
  the FlameMaster PSR/BurnerStabilizedFlame-based JSR/PFR decks need verification against a
  real licensed install — only the `cantera` solver path was executed end-to-end.
- ~~4 pre-existing test failures discovered (unrelated to Phase-6, not fixed):
  `test_phase5b.py`/`test_phase5b_extended.py` reference `ReductionResult.from_dict()`/
  `.load()`, neither of which is implemented in `types.py` (only `.to_dict()`/`.save()` are).~~
  **RESOLVED** (2026-07-11, deep-review implementation session, quick win #4): both classmethods
  had been misplaced under `class NTCReport` instead of `class ReductionResult` — moved back.
  Verified still correct as of the 2026-07-11 follow-up sessions: `types.py` has
  `ReductionResult.from_dict`/`.load` at lines 882/894; `test_phase5b.py` +
  `test_phase5b_extended.py` → 91/91 passing; full suite 355/355, 0 failures.
- Flux-analysis toggling was added only to the new JSR/PFR branches, not retrofitted onto the
  pre-existing Tig/Fls/RCM branches' own (already-present but always-commented)
  `#ReactionFluxAnal is TRUE` lines — extending it there would follow the same
  `target.add["flux_analysis"]` pattern if wanted.

---

## Session 2026-07-05 (final) — GUI-7: Remaining error.md items R1–R7, R9, R10

All items from the post-GUI-6 error.md audit implemented. zerork (R8) remains deferred per user request.

### R1 — PySR / polynomial-fit panel (`src/notebook_gemini/pysr_panel.py` — new)
- `PySRPanel(ttk.Frame)`: loads CSV, selects X/Y columns via Combobox
- **Polynomial fit** (numpy): any degree 1–10; RMSE + coefficient list + LaTeX equation string displayed
- **PySR symbolic regression** (threaded): configurable niterations; binary/unary operators; gracefully disabled if `pysr`/Julia absent; displays full equation table + best expression
- Embedded matplotlib `FigureCanvasTkAgg` with `NavigationToolbar2Tk`; scatter data + fit overlay
- "Export LaTeX eq." saves equation text to .tex file
- Wired to **Notebook → Symbolic Regression…**

### R2 — PDF table extraction (`src/notebook_gemini/pdf_table_panel.py` — new)
- `PDFTablePanel(ttk.Frame)`: threaded pdfplumber `.extract_tables()` across all pages
- Listbox of detected tables (page number, row×col dimensions); box-drawing preview in Text widget
- CSV export; **Gemini: clean table** — renders table as CSV, sends to Gemini for OCR correction, re-parses reply
- Wired to **Notebook → Extract PDF Tables…**

### R3 — RKD XML + YAML export from digitizer (`src/notebook_gemini/digitizer.py`)
- Two new toolbar buttons: **Export XML (RKD)…** and **Export YAML…**
- XML uses `xml.etree.ElementTree` in minimal ReSpecTh/RKD format with `<experiment>/<dataGroup>/<property>/<dataPoint>` hierarchy; asks for property names + units; includes `dy_plus/dy_minus` uncertainty if present
- YAML export: flat YAML with header metadata and `data:` list; uncertainty columns included when present
- `ET.indent()` for readable output; `xml_declaration=True`

### R4 — Uncertainty bar picking mode (`src/notebook_gemini/digitizer.py`)
- New `"err_bar"` radio mode added to `_MODES`; orange markers
- Two-click state machine: first click stores `_err_upper` (upper bound y value); second click computes `dy_plus = |y_upper − dp.y|`, `dy_minus = |dp.y − y_lower|` and assigns to the most recently picked data point
- `DataPoint` dataclass extended with `dy_plus: float = 0.0` and `dy_minus: float = 0.0`
- CSV export auto-adds `_plus`/`_minus` columns when any point has non-zero error bars

### R5 — MSO report → LaTeX project integration (`generate_target_opt.py`)
- New **LaTeX → Append MSO report section…** menu item
- `_append_mso_report_section()`: picks LaTeX project folder + MSO metadata YAML + artefacts output dir; invokes `run_report.py` as subprocess; reads generated `.tex`; calls `LaTeXProject.append_section()` to idempotently insert as a new section

### R6 — Forward UQ plots inline viewer (`generate_target_opt.py`)
- New **🖼 View output plots** button in ⑥ Forward UQ run row
- `_view_uq_plots()`: scans UQ output dir for `*.png`/`*.jpg` (recursive); renders 3-column Pillow thumbnail grid (290×220 px) in a scrollable Toplevel; double-click opens at full size via `xdg-open`/`eog`
- Graceful error if Pillow not installed

### R7 — Multi-fuel blend → target.opt YAML round-trip
- Already complete from previous session: `_collect()` at lines 2047–2072 emits `fuel: {a:..., b:...}` (dict), `fuelClass: "Multi"`, `fuel_coeffs`, `fuel_mw`, `fuel_nu_o2` per key. Verified against `data_management.py` which handles `isinstance(fuel, dict)` at line 510.

### R9 — PyChemkin integration (`src/pychemkin_reader.py` — new)
- `CKCSVReader`: wraps `chemkin.getVariable / getMoleFraction / getIgnitionDelay / getTotalMoles` from `PyChemkin-master/`; stdlib-only fallback CSV parser for when PyChemkin import fails
- Methods: `list_variables()`, `get_variable(var)` → `(t, v)` arrays, `get_mole_fractions([sp])`, `get_ignition_delay()`, `get_total_moles()`, `to_dataframe()`
- `CKCSVViewerPanel(ttk.Frame)`: variable listbox + data preview (50-row table) + IDT popup + matplotlib plot + CSV export
- Wired to **Tools → Read Chemkin Pro CSV (ckcsv) …**
- Does NOT require Chemkin Pro license — reads existing output files only

### R10 — `.done` sentinel restart robustness (`src/MUQ-SAC/simulation_manager2_0.py`)
- Skip check at line ~730 changed from `if "case-N" in os.listdir()` (directory-exists, unreliable for partial runs) to `if os.path.exists("case-N/.done")` (sentinel-only, written after validated completion)
- After `del X` (simulations complete), writes `case-N/.done` sentinel atomically
- Restarts skip cases with sentinel; cases without sentinel re-run fully — no spurious partial-skip

**Verification:** 298/298 RMIP tests still passing. `ast.parse` clean on all 5 modified/created files. ✅

---

## Session 2026-07-05 (continued) — Remaining items (error.md audit)

### Forward UQ GUI integration + smoke test
- Added "▶ Run Forward UQ" + "📂 Open output folder" buttons to ⑥ Forward UQ tab
- Launches `forward_uq.py <temp_target.opt>` in terminal via `_run_job()`
- Background thread polls for `forward_uq_statistics.csv` and displays first 10 rows in scrollable result panel
- **Smoke tests** (`tests/test_forward_uq.py`): 19/19 passing
  - `TestBuildFeatureMatrix` (6 tests) — pure math, order-1 and order-2 shapes + column values
  - `TestAnalyticalSobolPRS` (7 tests) — variance formula, S_i ≥ 0, ST ≥ S1, DataFrame shape, pure linear S_i sum = 1
  - `TestMCPropagatorPropagation` (4 tests) — shape, identity-PRS η = Σζ, variance = n/3 for symmetric prior
  - `TestFeatureMatrixConsistency` (1 test) — B@coeff matches manual polynomial evaluation

### GUI-3: XML import panel (replaced stub)
- `_import_xml_dataset()`: browse XML folder, set fuel species, run `xml2csv.main()` in background thread, reports row count and output dir in status bar

### GUI-3: Customizable LaTeX target tables (replaced stub)
- `_open_latex_tables_dialog()`: pick .target CSV + .bib, select target types + columns, choose output dir, compile PDF
- New `src/target_tables.py`: `generate_target_tables()` — parse pipe- or CSV-delimited .target, group by type, build booktabs LaTeX tables, combined document, pdflatex compile; CLI available

**Verification:** ast.parse clean on 3 files; 19/19 smoke tests pass. ✅

---

## Session 2026-07-05 (continued) — Phase 6: Gemini Notebook + LaTeX

### Task 6A — `src/notebook_gemini/` package (Gemini PDF Q&A)
New files:
- `__init__.py`
- `gemini_client.py` — wraps `google.genai` v1.47.0; reads `GOOGLE_API_KEY`; model `gemini-2.0-flash`; graceful degrade if key absent. Methods: `chat()`, `chat_with_pdf_bytes()`, `chat_with_image_bytes()`, `summarise_pdf_bytes()`
- `pdf_panel.py` — `PDFNotebookPanel(ttk.Frame)`: load PDF via pdfplumber, extract text, Gemini summary + threaded Q&A chat; colour-coded user/Gemini/error tags; spinner indicator. Also runs standalone.
- GUI: **Notebook → PDF Q&A Notebook…** opens in Toplevel

### Task 6B — `src/notebook_gemini/digitizer.py` (Plot Digitizer)
- `DigitizerPanel(ttk.Frame)`: load image/PDF page (via pdfplumber+PIL); X/Y axis calibration (click 2 reference points each); data-point picking; zoom scroll; CSV export with axis labels; Undo; log-scale toggle; Gemini "read axes" (sends image PNG to Gemini, gets axis labels/ranges back)
- GUI: **Notebook → Plot Digitizer…** opens in Toplevel

### Task 6C — `src/latex_project.py` (Local-git LaTeX)
- `LaTeXProject` class: `create()` (scaffold main.tex + .gitignore + git init + initial commit), `append_section(key, title, body)` (idempotent — duplicate guard comment `% section-key: X`, inserts before END SECTIONS marker, auto-commits), `import_figure()` (copy to figures/, return includegraphics snippet), `add_collaborator()` (registers in collaborators.json, prints git remote instructions), `compile()` (two-pass pdflatex, opens PDF via xdg-open)
- CLI: `python latex_project.py new|compile|append|figure|collab`
- GUI: **LaTeX** menu with 5 items (New, Compile, Append section, Import figure, Add collaborator)
- Smoke-tested: append_section idempotency, guard comment, section content ✓

**Deps installed:** `google-genai` 1.47.0, `gitpython` 3.1.50, `pdfplumber` 0.11.8
**Verification:** ast.parse clean on 6 files. ✅

---

## Session 2026-07-05 (continued) — Phase 5: FlameMaster + mech_diagnostics

### Task 5A — subprocess.call / os.mkdir fix (`src/MUQ-SAC/make_input_file.py`)
Both Fls call sites:
- `os.mkdir("output")` → `os.makedirs("output", exist_ok=True)` (no crash on restart)
- `subprocess.call("./run_profile")` → `subprocess.run(["bash", "./run_profile"], check=False)`

### Task 5B — Bounded FlameMaster retry loop (`src/MUQ-SAC/data_management.py`)
Replaced unbounded `while outfile == "":` with:
- `try/finally: os.chdir(saved_cwd)` — CWD always restored
- First pass: restart-safe (skip if converged output already exists)
- Second pass: bounded `for count, start_profile in enumerate(start_profiles, 1):`
- Atomic `FlameMaster.input` rewrite via `os.replace()`
- On exhaustion: logs WARNING, sets `eta = float("nan")`, exits cleanly

### Task 5C — Mechanism diagnostics (`src/MUQ-SAC/mech_diagnostics.py` — new file)
Three Cantera checks:
1. NASA-7 Tmid continuity (|ΔCp/R| > thermo_tol = 0.01)
2. Collision-limit: bimolecular A > 1e14 cm³/(mol·s) CGS
3. Reverse-rate: k_rev/k_fwd > 0.1 at T_ref = 1500 K
- CLI + Python API; smoke-tested on gri30.yaml (53 sp, 325 rxn, 0 thermo, 46 coll-limit)
- GUI panel: Tools → Mechanism Diagnostics… in generate_target_opt.py

**Verification:** ast.parse clean on all 4 files. ✅

---

**RMIP test suite:** 298/298 passing (`python -m pytest src/rmip/tests/ -v`)

---

## Session 2026-07-05 (continued) — Phase 4 backend fixes

### Task 4A — Progress file path bug (all copies of simulation_manager2_0.py)
**Root cause:** `callback_run` wrote `open('../progress','+a')` relative to whatever CWD the
multiprocessing pool callback ran in — typically a case sub-directory, so the progress file
landed in the wrong parent rather than inside `NOMINAL/`.

**Fix applied to:**
- `src/MUQ-SAC/simulation_manager2_0.py`
- `src/Sensitivity_Analysis/simulation_manager2_0.py`

Changes:
- Added `self.progress_file = None` to `Worker.__init__`
- `callback_run` uses `self.progress_file` if set; falls back to `os.path.dirname(os.getcwd())/progress`
- `make_nominal_dir_in_parallel`: sets `X.progress_file = os.path.join(nominalDir, "progress")`
- `make_dir_in_parallel`: sets `X.progress_file = os.path.join(optDir, "progress")`

### Task 4B — mso_compare bug fixes (`src/mso_compare/sim_runner.py`)
1. **`data_management_nominal` import**: `data_management_nominal` does not exist; file is
   `data_management.py`. Import corrected to `import data_management`.
2. **Fls double-index**: `vals = temp_sim_opt.get(..., [None])[0]` followed by `vals[0]`
   was subscripting a float twice → TypeError. Fixed to `vals = temp_sim_opt.get(..., [])`
   and `sim_val = vals[0] if vals else float("nan")`.

### Task 4C — Thread cap enforcement
- Added `_thread_cap()` import from chem_data to both `simulation_manager2_0.py` copies
- `self.parallel_threads` clamped: `min(int(target_data["Counts"]["parallel_threads"]), _thread_cap())`
- Fallback inline `_thread_cap()` if chem_data not available

### Task 4D — Pipeline parallelism (`src/mso_compare/pipeline.py`)
- Added `concurrent.futures.ThreadPoolExecutor` to `run_simulations`
- All configured simulation runs now launch in parallel (up to `_thread_cap()` threads)
- Each `run_nominal_simulation` is independent (different mechanisms, different output dirs)
- Sequential for-loop replaced with `pool.map(_run_one, sim_items)`

### Task 4E — GUI job launcher (`generate_target_opt.py`)
- `_run_job(cmd, label)`: launches `cmd` in external terminal
  (gnome-terminal → xterm → konsole fallback chain); tracks PID; updates status bar
  when terminal exits via background thread
- `_open_run_dialog()`: dialog with command entry, working-directory picker, label field
- Wired to **Tools → Launch Backend Job in Terminal…**

**Verification:** `ast.parse` clean on all 5 modified files. ✅

---

## Session 2026-07-05 (continued) — GUI-2 (Tasks 2D/2E) + GUI-3 xml2csv

### Task 2D — `src/MUQ-SAC/combustion_target_class.py`
- Added `sys`, chem_data import block at top (with sys.path insert to repo root;
  graceful fallback if chem_data not found: `_HAS_CHEM_DATA = False`)
- Replaced hard-coded `self.molecularWt` (26 literals) + `self.stoichiometry` (27 literals)
  with `dict(_DEFAULT_MW)` / `dict(_DEFAULT_NU)` from chem_data; hard-coded tables remain
  as fallback inside `else` branch
- φ computation: `nu_o2` fallback via `_compute_nu_o2(fuel)` for fuels not in the table

### Task 2E — `src/Sensitivity_Analysis/combustion_target_class.py`
- Same chem_data import + table replacement as Task 2D
- **KeyError bug fixed**: line was `st_ox.append(self.stoichiometry[i])` →
  now uses `.get(i, 0.0)` + `_compute_nu_o2(i)` fallback for unlisted fuels
- Both files pass `ast.parse` clean (verified)

### Task 2F (GUI-3) — `config_tools/converters_io/XML2CSV/xml2csv.py` refactored
Full rewrite of the 966-line flat script. All fixes from error.md applied:
- **Functionized**: `main(xml_dir, out_dir, fuel_list, input_fuel)` entry point;
  importable as `from xml2csv import main`
- **CWD-independence**: `xml_dir` / `out_dir` parameters; no implicit `os.listdir()`
- **Append duplication**: `open("target.opt","a+")` → file opened once with "w" before
  the loop; per-file rows appended with `target_fh.write(rows)` (no re-open)
- **bibliographyLink**: `_extract_bib(root, citekey)` emits BibTeX @article{...};
  `_make_citekey()` generates `Author+Year` stable keys; all parsed → `references.bib`
- **molwt KeyError**: `molwt[each]` for JSR species → `_mol_wt(each)` via `chem_data.compute_mw`
- **and/or precedence bug** (line 762): `Target_mode == "premixed" or ... or Target_mode == "X"`
  → `Target_mode in _FLS_MODES` frozenset (parenthesised correctly)
- **AssertionError stops**: all `raise AssertionError(...)` → `log.warning(...); return None,None,None`
  (caller continues to next file, partial output preserved)
- **TabErrors**: entire file rewritten in pure 4-space indentation
- **Stoichiometry**: sourced from `chem_data._BASE_STOICH` + `_nu_o2()` fallback
- **np.repeat on dicts** bug fixed: list comprehension `[dict] * ndpt` used for all
  dict-valued per-row arrays (fuel, bathgas, ox); avoids numpy object-array newline printing
- **Smoke test**: 251/956 NH3 files parsed (705 are unrecognised `stirred reactor (quartz)`
  type → logged warning, skipped); 431,778 rows output; references.bib generated ✅

---

## Session 2026-07-05 — GUI Overhaul Batch 1, Phase GUI-1 (Modernization)

Driven by `error.md`. Rewrote `generate_target_opt.py` GUI layer in 6 micro-tasks.
New shared module `chem_data.py` created as foundation for all chemistry calculations.

### New file: `chem_data.py`
- `ATOMIC_WEIGHTS` dict (IUPAC 2021, 34 elements)
- `DEFAULT_FUEL_MW` / `DEFAULT_STOICH_O2` fallback tables (replaces hard-coded values
  scattered across both `combustion_target_class.py` copies)
- `parse_formula(formula)` — regex-based parser, supports fractional counts (biomass)
- `compute_mw(formula)` — molecular weight from formula string or species name
- `compute_nu_o2(formula)` — stoichiometric O2 by atom balance: CₓHᵧOᵤNᵥSᵥ balance
- `compute_nu_o2_blend(fuels)` — mole-fraction-weighted blend stoichiometry
- `compute_phi_from_blend(fuel_dict, x_o2)` — unified φ formula (replaces two divergent versions)
- `thread_cap()` — `os.cpu_count() - 5`, floor 1

### Task 1A — PALETTE, FONTS, _HELP constants (`generate_target_opt.py`)
- `PALETTE` dict: 13 named colours (dark navy theme)
- `TAB_COLORS` list: per-tab accent colours for notebook chips
- `FONTS` dict: 10 named font tuples using `DejaVu Sans` / `DejaVu Sans Mono`
- `_HELP` dict: ~50 entries covering every `target.opt` variable with full semantics
  (drawn from `run_script.py` optInputs key analysis)

### Task 1B — `_apply_theme(root)`
- 130-line `clam`-based dark theme applied via `ttk.Style`
- Covers: TFrame, TLabel (+ Header/SubHeader/Section/Dim/Status variants), TButton
  (+ Small/Danger variants), TEntry, TCombobox, TNotebook (+ Tab), TScrollbar,
  TSeparator, Canvas/Text option_add
- Called in `main()` before `App()` is constructed

### Task 1C — Font literal replacement
- Replaced all 15× `font=("", 12, "bold")` → `FONTS["header"]`
- Replaced all 4× `font=("", 10, "bold")` → `FONTS["section"]`
- Replaced all 4× `font=("Courier", 9)` → `FONTS["mono_small"]`
- Zero bare font literals remain (verified by grep)

### Task 1D — Click-ⓘ tooltip popover (replaces broken hover tooltip)
**Root cause fixed:** `_show_tip` (old lines 465–472) created a new `tk.Toplevel` on
every `<Enter>` event with no `<Leave>` binding, causing stacking floating windows that
never dismissed. Each call also had a 2.5 s timer that destroyed only its own window.

**New system:**
- `_show_tip(anchor_widget, text)` — single reusable `tk.Toplevel`; toggle on click;
  destroys old tip before opening new one
- `_close_tip()` — explicit close
- `_on_root_click(event)` — bound to `<Button-1>` on root; closes if click is outside tip
- `_field()` is now an **instance method** (was `@staticmethod`); places a `" ⓘ "` label
  badge (blue, `cursor="hand2"`) bound to `<Button-1>` instead of `<Enter>`
- Only one popover can be open at a time; Esc also dismisses it

### Task 1E — Menu bar
Four menus added to `_build_ui`:
- **File**: Load / Save / Save As / Save Checkpoint / Restore Checkpoint / Quit
- **Insert**: Add target row / Add addendum entry / Add uncertainty reaction /
  Import CSV / Import XML dataset
- **Tools**: Generate & Preview / Generate .target / .add / .xml /
  MW Calculator (Phase 2 stub) / LaTeX tables (Phase 3 stub)
- **Help**: Guided tour / About dialog
- Keyboard shortcuts: `Ctrl+O` (load), `Ctrl+S` (save), `Ctrl+Q` (quit)
- Thread-cap indicator in toolbar: `"CPU cap: N threads"` using `chem_data.thread_cap()`
- Scrolled canvas background updated to `PALETTE["surface"]`

### Task 1F — Checkpoint save / restore
- `_save_checkpoint()` — `filedialog.asksaveasfilename` → JSON with `cfg` dict +
  `target_rows` / `add_rows` / `xml_rows` / `quick_path`
- `_restore_checkpoint()` — reopens JSON; repopulates all row-based builders by calling
  `_add_trow`, `_add_arow`, `_add_xrow`; shows info dialog explaining flat-field refresh

### Stub methods added (will be implemented in later phases)
- `_start_tour()` — 11-step guided notebook tour via `messagebox.askyesno`
- `_open_mw_dialog()` — Phase 2 placeholder
- `_open_latex_tables_dialog()` — Phase 3 placeholder
- `_import_xml_dataset()` — Phase 3 placeholder

### Smoke test
```
python -c "import generate_target_opt; print('OK')"  # → OK
```

---

## Current status: Phases 1–5 COMPLETE (all planned phases done)

**Test suite:** 298/298 passing (`python -m pytest src/rmip/tests/ -v` from repo root)
- 62 parser tests (`test_chemkin_parser.py`)
- 50 Phase-3 tests (`test_phase3.py`)
- 48 Phase-4 tests (`test_phase4.py`)
- 29 Phase-5 tests (`test_phase5.py`)
- 18 Phase-5C 3D tests (`test_phase5c_3d.py`)
- 41 Phase-5B tests (`test_phase5b.py`)
- 50 Phase-5B extended tests (`test_phase5b_extended.py`)

**CLI launcher:** always `python rmip_cli.py <cmd>` from `/data/OPEN_CODE/PHASE-3/`.
Never `python -m src.rmip.cli` (causes `ModuleNotFoundError`; see `error.md`).

---

## Session 2026-07-04 — Phase 5B extended: DRGPSA, DRGSA, coefficient/trim visualization

### New reducers (`src/rmip/reduction/drgpsa.py`)

**`DRGPSAReducer(DRGReducer)`** — DRG with Preliminary Sensitivity Analysis:
- Inherits all DRG infrastructure; overrides `_compute_drg_coefficients()` only
- Each reaction's contribution amplified: `weighted_omega = omega * (1 + |s_i|)`
  where `s_i` is the normalized SA coefficient
- Both numerator AND denominator amplified — SA-unimportant pathways get lower
  effective r_AB than in plain DRG (correct: DRGPSA focuses on SA-critical pathways)
- SA data: pre-computed JSON via `--sa-json` or Cantera on-the-fly via `CanteraSensitivityRunner`
- Stores `sa_coefficients` dict in `ReductionResult`

**`DRGSAReducer(DRGReducer)`** — Direct SA importance ranking:
- Per-species importance = `max(|s_i|)` over all reactions involving that species
- No BFS graph traversal, no r_AB matrix computation
- Seeds always retained; other species retained if importance > eps

### BFS levels + r_AB in all reducers
All reducers (DRG, DRGEP, PFA, DRGPSA) now populate:
- `ReductionStep.bfs_levels: Dict[str, int]` — BFS wave-front level per retained species
  (seeds=0, first-wave=1, second-wave=2, etc.)
- `ReductionResult.r_AB: Dict[str, Dict[str, float]]` — full interaction matrix as
  nested dict (JSON-serialisable)

### Coefficient visualization (`src/rmip/reduction/coefficient_viz.py`)
`CoefficientVisualizer(result, G=None, threshold_default=0.05)`:
- Dash app (dark theme #1e1e1e) with threshold slider + 3 tabs:
  - **Heatmap** — Viridis go.Heatmap of r_AB matrix; seeds starred; hover shows value
  - **2D Network** — species subgraph, edges coloured by 4 strength bands; threshold slider
  - **3D Network** — Plotly Scatter3d using carbon-ring positions from G
- `export_html(path)` — 3 static Plotly HTML files

### Trim visualization (`src/rmip/reduction/trim_viz.py`)
`TrimVisualizer(result, G)`:
- Dash app with eps slider + stats subtitle + 3 tabs:
  - **BFS Propagation** — species coloured by bfs_level (green=seed → cyan/blue → purple/red)
  - **2D Trim** — full bipartite graph: seeds green, retained blue, removed red/faded
  - **3D Trim** — same in Plotly Scatter3d
- `export_html(path, eps_index=0)` — static HTML at given eps

### DB constraint widening
`reduction_runs.method` CHECK widened to include `'DRGPSA'` and `'DRGSA'`.
`_ensure_wide_reduction_method_constraint(conn)` in `migrations.py` uses
savepoint-probe + table-recreation (same pattern as `_WIDEN_MECHANISMS_FORMAT`).

### CLI additions
- `reduce`: `--method` now accepts `DRG|DRGEP|PFA|DRGPSA|DRGSA`; `--sa-json FILE` added
- `reduce-viz <mech_id> --db DB --reduction-json FILE --mode coeff|trim|both
  [--port 8055] [--threshold 0.05] [--export-html PATH]`
  - `mode=both`: CoefficientVisualizer in daemonised multiprocessing.Process (port 8055) +
    TrimVisualizer in foreground (port 8056)

### Tests (`src/rmip/tests/test_phase5b_extended.py` — 50 tests)
- `_build_h2_fixture()` — 7 species, 4 reactions H2 combustion; uses correct
  schema column name `stoich_coeff`
- DRGPSA: coefficient computation, SA amplification, r_AB matrix shape
- DRGSA: importance ranking, threshold sweep, seeds always retained
- CoefficientVisualizer: empty r_AB, figure generation, threshold filtering
- TrimVisualizer: step rendering, BFS level coloring, retained/removed partitioning
- CLI dispatch for DRGPSA/DRGSA and reduce-viz
- ReductionResult JSON round-trip with r_AB, bfs_levels, sa_coefficients

### Key algorithmic insight (DRGPSA selectivity)
DRGPSA is MORE selective than plain DRG for species not in SA-important reactions.
When heavy SA is on reaction R (involving A and B): `denom[A]` grows with SA weight,
`numer[(A,C)]` stays same for species C not in R → `r(A,C) = numer/denom` shrinks.
At same eps, C may be dropped by DRGPSA but retained by DRG. This is intended behavior.

### Error fixed (error.md)
`python3.9 -m src.rmip.cli` → `ModuleNotFoundError: No module named 'rmip'`
Root cause: treating `src` as a package; internal imports use `rmip` not `src.rmip`.
Fix: always use `python rmip_cli.py` from repo root. `error.md` updated with full explanation.

**Usage:**
```bash
python rmip_cli.py reduce 1 --db project.db \
    --method DRGPSA --target "H2,O2,H2O" \
    --sa-json outputs/sa_ffcm1.json --eps-max 0.5 --out drgpsa_steps.json

python rmip_cli.py reduce-viz 1 --db project.db \
    --reduction-json drgpsa_steps.json --mode both
```

---

## Session 2026-07-04 — Phase 5B: Mechanism Reduction (DRG / DRGEP / PFA)

- **`rmip/types.py`** — new `ReductionStep` and `ReductionResult` dataclasses with
  JSON round-trip serialization and `save()`/`load()` helpers
- **`rmip/reduction/drg.py`** — `DRGReducer`: r_AB coefficients + BFS from seeds.
  Rate sources: Cantera → flux_score from graph → omega=1 fallback.
- **`rmip/reduction/drgep.py`** — `DRGEPReducer`: max-path EP_AB via log-space
  Dijkstra; more conservative than DRG at same eps.
- **`rmip/reduction/pfa.py`** — `PFAReducer`: signed production + consumption fluxes.
- **`rmip/reduction/__init__.py`** — package exporting all reducers
- **`rmip/database/migrations.py`** — `run_phase5b_migrations()` adds `reduction_runs`
  table; idempotent
- **`rmip/cli.py`** — `reduce` subcommand; `visualize` extended with `--reduction-json`
  and `--eps` for Dash reduction slider (dims removed nodes to 8% opacity, red dashed border)
- **`rmip/tests/test_phase5b.py`** — 41-test suite

**Usage:**
```bash
python rmip_cli.py reduce 1 --db project.db \
    --method DRG --target "H2,O2,H2O" --eps-max 0.5 --out drg_steps.json
python rmip_cli.py visualize 1 --db project.db --reduction-json drg_steps.json
```

---

## Session 2026-07-03 — Phase 5C 3D planetary layout + MB case

- **3D stacked-disc layout** (`core/graph_builder.py`): flat rings per carbon shell,
  stacked in z. Spheres abandoned (project as filled discs, bury inner shells).
  Two orderings per node: alphabetical and chemical-family arcs.
- **`analysis/visualization3d.py`** — `NetworkVisualizer3D`: Plotly Scatter3d Dash app.
- **CLI `visualize3d`** — `--shell-gap`, `--layer-gap`, `--order alpha|family`,
  `--export-html`, `--union`, `--label id|formula`
- **Bug fixed:** `scipy.sparse` pre-import in `graph_builder.py` — networkx
  spring_layout crashed for >500-node graphs on scipy 1.8.
- **MB case loaded:** id=6 (608 sp / 3984 rxn), id=7 (623 sp / 4050 rxn).
- **Carbon-ring 2D fix:** shell assignment prefers DB `formula` over name.

```bash
python rmip_cli.py visualize3d 6 7 --union --db project.db --label id
```

---

## Phase 5A — SA/Flux Edge Highlighting (COMPLETE — 2026-06-29)

- `rmip/simulation/sensitivity_runner.py` — `CanteraSensitivityRunner.run_idt()`
- `rmip/analysis/visualization.py` — importance bands in stylesheet; `sa-json`/`threshold`
- `rmip/cli.py` — `--sa-json`, `--flux-json`, `--threshold`, `--score` on `visualize`;
  new `sa-run` subcommand

---

## Phase 5C — Carbon-Ring 2D Layout (COMPLETE — 2026-06-29)

- `rmip/core/graph_builder.py` — `_carbon_ring_positions()`, `preset_carbon_ring` layout

---

## Phase 5D — Species SMILES Disambiguation, Tier 1 (COMPLETE — 2026-06-29)

- `glossary_reader.py` — `load_variants()`; `parser.py` — `variants_path`;
  `migrations.py` — `run_phase5d_migrations()`; `cli.py` — `parse --variants FILE`;
  `visualization.py` — double-orange border for variant nodes

---

## Completed phases (summary)

### Phase 1 — Core parsing & graph (COMPLETE)
CHEMKIN reader (dual-path: RMG-Py or built-in `_chemkin_parser.py`), Cantera YAML
reader, glossary reader, `MechanismParser`, RDKit canonicalization, bipartite graph
builder, core SQLite schema. CLI: `parse`, `graph`, `list`, `summary`.

### Phase 2 — Analysis & visualization (COMPLETE)
Interactive Dash network visualizer (single + dual-panel union, ghost nodes, shared
layout dropdown, global R-IDs, diff stats bar, PNG/PDF/SVG export). Kinetics/thermo
comparison, sparsity detection, SA/flux score attachment. Phase-3 DB tables.
CLI: `compare`, `visualize`, `sparsity`, `sensitivity`, `reaction-matrix`, `reactions`.

### Phase 3 — Fusion, optimization, simulation (COMPLETE)
`FusionEngine` (VERBATIM/COPY/FUSE), `GraphComparator`, `ParameterEstimator`,
`BenchmarkSuite`, `IDTRunner`, `LFSRunner`, `PerformanceRanker`, `MSOInterface`
(JSON contract, subprocess), `RMGInterface`, `ChemkinWriter`. Phase-3 migrations.
CLI: `fuse`, `optimize`, `rank`, `complete`, `export`, `compare-graph`, `exp-load`, `bench`.

### Phase 4 — Unified mechanism & uncertainty (COMPLETE)
`UncertaintyBandEstimator` (3-sigma per-T bands), `UnifiedTreeBuilder` (plan + build),
`CanteraYAMLWriter` (SI YAML + uncertainty embedding), `MissingSpeciesPredictor`.
Phase-4 DB tables. CLI: `unify-plan`, `unify-build`, `predict-missing`, `export --format yaml`.

---

## Visualizer bug fixes (sessions 2026-06-27 to 2026-06-29)

| Date | Fix | File(s) | Description |
|------|-----|---------|-------------|
| 2026-06-27 | Ghost node ID collision | `graph_builder.py` | `ghost_S_{id}` / `ghost_R_{id}` — avoids collision between same-integer species and reaction DB ids |
| 2026-06-27 | Position identity key mismatch | `graph_builder.py` | True union graph keyed by `ik:`/`nm:`/`ck:`/`cf:`. Ghost nodes copy `**src_data` → same position guaranteed |
| 2026-06-27 | Formula string mismatch | `graph_builder.py` | `_canon_formula()` normalizes arrows + sorts species. GRI+Davis union: ~85 → ~66 nodes |
| 2026-06-28 | Per-panel layout dropdown desync | `visualization.py` | Single shared dropdown, one callback writes both panels simultaneously |
| 2026-06-28 | Ghost reactions had no labels | `visualization.py` | Ghost reaction label = `formula_string`; shows global R-ID in R-ID mode |
| 2026-06-28 | Same reaction had different R-IDs per mechanism | `graph_builder.py` | `_assign_global_reaction_labels()` in `build_union_graphs()` — first-appearance order from mech-1 |

---

## Known limitations / deferred items

| Item | Status | Target phase |
|------|--------|-------------|
| `CanteraSensitivityRunner.run_lfs()` for LFS SA | Not built | 5A follow-up |
| DRGSA has no r_AB (not applicable) | By design | N/A |
| Tier 2/3 SMILES disambiguation (auto-collision, RDKit InChI pruning) | Deferred | Future |
| RMG-Py not installed | Expected (source at `/data/OPEN_CODE/RMG_py/`) | N/A |
| Transport data | Out of scope (D6) | N/A |
| NASA-9 polynomials | Not supported | N/A |

---

## Live project database (`project.db`, actually `outputs/project.db`)

| ID | Name | Species | Reactions | Format | Notes |
|----|------|---------|-----------|--------|-------|
| 1  | GRI-3.0 | 15 | 48 | chemkin | **STALE** — pre-Zero-RK-Phase-1 parser bugs (blank ELEMENTS/formula, Ea mislabeled cal/mol instead of Kelvin). Kept for continuity with existing SA/reduction results keyed to this id. Use id=8 for new work. |
| 2  | Davis-2005 | 14 | 38 | chemkin | **STALE** (blank ELEMENTS/formula, misclassified Lindemann reaction). Use id=9. |
| 3  | Keromenes-2013 | 17 | 49 | chemkin | **STALE** (same as above). Use id=10. |
| 4  | Li-2015 | 14 | 37 | chemkin | **STALE** (same as above). Use id=11. |
| 5  | FFCM1 | 38 | 291 | cantera_yaml | Unaffected — different reader (`cantera_reader.py`), not `_chemkin_parser.py`. |
| 6  | MB-MB2D (base) | 608 | 3984 | cantera_yaml | Unaffected, same reason. |
| 7  | MB-MB2D Lalit-2024 | 623 | 4050 | cantera_yaml | Unaffected, same reason. |
| 8  | GRI-3.0 | 15 | 48 | chemkin | **Current** — re-parsed 2026-07-12 with the fixed parser (commit `10c77d2`). |
| 9  | Davis-2005 | 14 | 38 | chemkin | **Current** — re-parsed 2026-07-12. |
| 10 | Keromenes-2013 | 17 | 49 | chemkin | **Current** — re-parsed 2026-07-12. |
| 11 | Li-2015 | 14 | 37 | chemkin | **Current** — re-parsed 2026-07-12. |

Backup of the pre-re-parse DB: `outputs/project.db.bak-pre-zerork-reparse-20260712`. IDs 1-4 were
deliberately left in place rather than deleted/overwritten — re-parsing via `rmip_cli.py parse`
always creates new rows, and any existing SA runs/reductions/comparisons already keyed to 1-4 stay
valid (just not reflecting the fix) until explicitly re-run against 8-11.

---

## Mechanism file paths

| Mechanism | Path |
|-----------|------|
| GRI-3.0 | `/home/krithika/MUQ-SAC/MECHANISMS/GRI3/chem_gri30_wetCO.inp` |
| Davis-2005 | `/home/krithika/MUQ-SAC/MECHANISMS/Davis_2005/chem_Davis2005_mech_wetCO.inp` |
| Keromenes-2013 | `/home/krithika/MUQ-SAC/MECHANISMS/Keromens/chem_Keromnes2013_orig_mech_wetCO.inp` |
| Li-2015 | `/home/krithika/MUQ-SAC/MECHANISMS/Li_2015/chem_Li2015_wetCO_mech.inp` |
| NUIG-2010 | `/home/krithika/MUQ-SAC/MECHANISMS/NUIG-NGM_2010/chem_NUIG2010_wetCO_nc5_49.inp` |
| CRECK-2012 | `/home/krithika/MUQ-SAC/MECHANISMS/CRECK/chem_CRECK2012_mech_wetCO_v1212.inp` |
| FFCM1 | `/home/krithika/MUQ-SAC/MECHANISMS/FFCM1/FFCM1.yaml` |
| AramcoMech 1.3 | `/home/krithika/MUQ-SAC/MECHANISMS/Keromens/aramcomech_1.3_syngas_chem/aramcomech_1.3_syngas_chem.yaml` |
| nHeptane | `/home/krithika/MUQ-SAC/MECHANISMS/nHeptane/heptane.inp` |
| MB-MB2D (base) | `/home/krithika/MUQ-SAC/Database/BUTANOATE/MB_MB2D.yaml` |
| MB-MB2D Lalit-2024 | `/data/OPEN_CODE/PHASE-3/DATASET/METHYL_BUTANOATE_2026/MB_MB2D_LALIT_2024.yaml` |

---

## How to resume work in a new session

```bash
cd /data/OPEN_CODE/PHASE-3/

# Verify all tests pass
python -m pytest src/rmip/tests/ -v   # expect 298/298

# Check project DB
python rmip_cli.py list --db project.db

# Launch visualizer (union GRI vs Davis)
python rmip_cli.py visualize 1 2 --union --db project.db

# Visualize large MB mechs in 3D
python rmip_cli.py visualize3d 6 7 --union --db project.db --label id

# Run DRG reduction + visualize
python rmip_cli.py reduce 1 --db project.db \
    --method DRG --target "H2,O2,H2O" --eps-max 0.5 --out drg_steps.json
python rmip_cli.py reduce-viz 1 --db project.db \
    --reduction-json drg_steps.json --mode both
```

---

## Key design decisions (immutable, from CLAUDE.md §2)

| ID | Decision |
|----|----------|
| D1 | Species identity = `inchi_key` (RDKit InChIKey) |
| D2 | Reaction identity = `canonical_key` (sorted-SMILES frozenset, directional) |
| D3 | SQLite only — no ORM, stdlib `sqlite3`, SI units in DB |
| D4 | IO readers return plain `dict` — no DB writes inside readers |
| D5 | Inter-module transfer uses dataclasses from `rmip/types.py` |
| D6 | Transport data out of scope |
| D7 | MSO interface = JSON file contract only (subprocess, no import) |
| D8 | Ghost node IDs: `ghost_S_{db_id}_{src_mech}` / `ghost_R_{db_id}_{src_mech}` |
| D9 | Global union R-IDs: assigned by `_assign_global_reaction_labels()` in union mode |
| D10 | 3-sigma uncertainty convention: `sigma_lnk = ln(f)/3`, `f = sqrt(k_max/k_min)` |

---

## MarkDownFiles/error.md (raw pre-2026-07-05 GUI complaint notes — superseded by later target-builder/algorithm-expansion work; kept verbatim in case any single item wasn't fully addressed)

What is \u27f3, \u2715, etc in the options? Make the optiuons more intelligent and clear in GUI.
Experimental dataset addition must get a saperate tab, we can import from XML format or CSV format with header files etc. Now, currently sim type is only Tig an dFls, but it can be any thing from counter flow burner, heat stablized burner, JSR, Plug flow etc. See what kind of targets are encoded in make_input_file.py
Very bad format for fuel species blend information gathering. It too clustered. There are repeated tasks in different tabs. Kindly make it unified and unique (for eg, you can import the xml files from inset, there is a tab for sam in the GUI and there is a saperate window in Mechanism to load into RMIP
In meta data still you are asking for fuel species and it formula, you are doing the same in MUQ-SAC input file location. I would liek you to bring the tabs in progression, use next to switch from one tab to another. See the Aspen Plus design and follow that way, every task must be saved automatically so once it accedently gets closed it can be reloaded without doing th esame task again from memory
Algorithm type is outdated, I am using may kinds of optimization algorithms like GA alone, some other evolutionary, the GA plus a loca refinement gradient based algorithm and a local gradient based algorithm. Basically every algo available in the pyGAD, Scipy optimize and other packages can be used here so expand the list accordingly. See optimizationTool.py for more info. You can still list the algorithms but can not activate those that are not implemented. Provide those options in the list 
Allow the user to create new folder in choose directory options that opens up when you want to choose a file
You must allow the user to give more option in mech reduction, like allow the user to create .target file and use the same or a subset of that to do SA or reduction
You must lock the tabs that are not yet reached by the user. You must allow to unk the nect tab after clicking next option. You must chang the position of the tabs as the file locations are only created after those files exists. You must first ask the user to create those files first then you must ask for fiel location details


---

## MarkDownFiles/CLT.md (orphan CLI snippet — NOTE: demonstrates `python3.9 -m rmip.cli parse ...` directly, which is the anti-pattern this repo's own conventions warn against; always use `python3 rmip_cli.py` instead — kept only as a historical curiosity, not a usage example to follow)

python3.9 -m rmip.cli parse mech_B.inp --db project.db \
    --glossary species_smiles.csv \
    --thermo thermo.dat \
    --dict species_dict.txt \
    --name "My Mechanism v2" \
    --check-duplicates

---

