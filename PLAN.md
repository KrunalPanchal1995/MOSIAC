# Project plan — full backlog, reorganized 2026-07-17

This file was rewritten on 2026-07-17 to cover the **entire project backlog**, not just a
single session's ask. Source of truth for what's already done: `MarkDownFiles/HISTORY/`
(44 numbered parts, chronological, each tagged DONE/PARTIAL/PENDING — see
`MarkDownFiles/HISTORY/INDEX.md`). Source of truth for defects: `BUG.md` (resolved) and
`bug.md` (unresolved/known limitations). This file is the **plan to close out every
PARTIAL/PENDING history part and every unresolved bug**, in priority order.
`progress.md` is the running log against this plan — update both together.

**Standing constraint (per user instruction, still in force):** the moment session usage
crosses 90%, dump findings into `progress.md`, leave this file updated, and stop — do not
try to finish everything in one pass.

**Not on this priority list, deliberately — read-only for now:** `MarkDownFiles/FEATURE_GAPS_FROM_MONOLITH.md`
(2026-07-17) is a reading list, not a task list, comparing the retired `generate_target_opt.py`
monolith against the 8 split GUI apps and ranking ~10 candidate features that didn't carry
forward (per user request: "plan it for now... I will ask you to read it later and start
implementing it"). Do not start implementing anything from it until the user explicitly asks.

---

## Priority 0 — Data-integrity bugs still open (do these first, small blast radius each)

**DONE, 2026-07-17.** All 5 items fixed and regression-tested this session (472 passed,
1 pre-existing unrelated failure, before and after). See `BUG.md` for full writeups of
each fix.

1. ~~**M12**~~ — re-verified already fixed by B4's Phase 1 fix (never independently
   confirmed until now); added `test_fusion_m12.py` (2 tests) locking it in.
2. ~~**`core/canonicalize.py` self-third-body equivalence**~~ — fixed via a new opt-in
   `cancel_self_third_body` param on `make_reaction_canonical_key`; verified end-to-end
   through the real CHEMKIN parser (not just unit-level). `test_canonicalize_self_third_body.py`
   (4 tests).
3. ~~**M10**~~ — fixed: `_kinetics_are_identical` now also requires matching
   `kinetics_type` and, for pressure-dependent types, a tolerant full comparison of the
   `kinetics_data_json` payload. `test_graph_comparator_m10.py` (5 tests).
4. ~~**M13**~~ — fixed by tracking decision↔band pairs in lockstep (`band_decisions`
   list) instead of re-deriving the OPTIMIZE-decision list after the fact. Confirmed the
   new test actually catches the pre-fix bug (failed against reverted code).
   `test_unified_tree_m13.py` (2 tests).
5. ~~**M14**~~ — fixed 3 stacked bugs in one path: Cantera-2 API shapes
   (`ct.TroeFalloff`/`ct.FalloffReaction` kwargs/`ct.ChebyshevReaction`, none of which
   exist in Cantera 3), a `ct.NasaPoly2` 14-vs-15-element array bug, and the actual
   J/mol-vs-J/kmol unit mixup. Verified against an independently-built Cantera YAML
   ground truth (`rel=1e-6` match). `test_uncertainty_bands_m14.py` (5 tests).

## Priority 1 — Verify the fusion pipeline actually works end-to-end in Zero-RK

**DONE, 2026-07-17.** Ran `constVolumeWSR.x` directly against both `Fused_mean_KLD.inp`
and `Fused_priority_KLD.inp` (Keromnes/Li/Davis) using the same config shape
`make_input_file.py`'s zerork branch already produces (mechFile=thermFile=the fused
`.inp`, H2/O2/N2 IDT run). Both parse cleanly ("Success" in `mech.clog`, 17 species/56
reactions, no rejection, only benign thermo warnings) and the ODE integration completes
(`cvode err=0`). Confirms Zero-RK's own CHEMKIN parser is lenient enough to accept the
generic-M vs. explicit-self-third-body forms as coexisting — full writeup in `BUG.md`'s
"Verification tasks completed" section.

## Priority 2 — Sweep all 8 launcher GUIs against dummy + real fused mechanisms

**DONE, 2026-07-17 (dummy-fixture tier).** Executed per `GUI_STRESS_TEST_PLAN.md`'s
procedure (in-process/subprocess-to-underlying-CLI, per the user's locked "keep going
at this depth" decision — no literal Tk widget driving this pass, the shared-display
hazard was still unconfirmed-safe). All 8 apps run against the checked-in dummy fixture
set (`src/rmip/tests/fixtures/gui_stress/`), output verified by content, 20 permanent
regression tests added (`test_gui_stress_sweep.py` + `test_combustion_target_mono_fuel_
dict.py`). Full writeup: `progress.md`'s "Exit criteria (GUI_STRESS_TEST_PLAN.md §4)"
section. Short version:
- **B12** (brute_force_sa doubled path) and **B14** (nominal_sim no cwd/PYTHONPATH)
  re-verified still fixed, now with real regression coverage for the first time.
- **B13** (forward_uq doubled path) — fixed this session, plus a synthesized minimal
  PRS cache (`bootstrap_forward_uq_cache.py`) gets a FULL real run to complete
  end-to-end (not just past the path bug).
- 2 more real bugs found + fixed + regression-tested: `combustion_target_class.py`'s
  Mono-fuel-dict crash (blocked brute_force_sa + forward_uq on the real shipped
  target file) and `uncertainty_generator_gui.py`'s blank-`<class>` XML-generator bug
  (silently no-opped downstream perturbation).
- 2 real findings logged, not fixed: **M30** (new — SA `ZeroDivisionError` on any
  reaction with nominal Arrhenius `n=0`, `bug.md`) and the priority-pick-fusion-mode
  feature gap (`mean_value_fusion_gui` can't invoke it at all — different FusionEngine
  class than the CLI's).
- **M24** (mso_compare CWD race) re-confirmed structurally present by code read; ran
  with real concurrency (2 workers) without triggering observable corruption this pass
  — still open, needs the real design fix already scoped in Priority 4 below.
- `mechanism_converter_gui.py`, `mso_compare_gui.py` swept for the first time ever;
  `rmip_suite_gui.py`'s GSA + Active-Param-Selection tabs had zero prior GUI-adjacent
  coverage and both work correctly on first real test.

**Not yet done: the real-fused-mechanism tier** (`GUI_STRESS_TEST_PLAN.md` §4's 2nd
tier) — scale/real-naming quirks (long species names, unusual third-body syntax) only
show up on real data (`outputs/fusion/Fused_Mech.*`,
`outputs/fusion_keromnes_li_davis/...`), not the minimal dummy fixtures.

## Priority 3 — Zero-RK: flame speed + counterflow/extinction (needs a real bootstrap pipeline)

Scoped in detail this session (`bug.md`, Part 42 in HISTORY) but explicitly NOT
attempted — this is real, multi-day work, not a quick bridge:

1. Confirm with the user: full adaptive-grid/bootstrap fidelity (matching Zero-RK's own
   `flamesolver.py::compute_steady_flame_speeds` — unsteady run → Lewis_file generation →
   steady KINSOL solve → adaptive regrid loop), or would a cheaper approximation (e.g. a
   single long-time `premixedUnsteady` run, reading flame speed off the mass burning rate
   once the solution stabilizes) suffice for their actual downstream use?
2. Implement `Fls` `solver="zerork"` branch in `make_input_file.py` per whichever answer.
   New `zerork_fls_*` defaults go in `combustion_target_class.py`, same pattern as every
   other zerork target.
3. New target-type tag for counterflow/extinction (confirmed `Flw` is unrelated, already
   claimed) — pick something in the existing naming family (`Fcf`/`Fext`), thread through
   `.target`/`.add` parsing the same way every other target type is. Read
   `counterflowflamesolver.py`/`counterflowpremixedflamesolver.py` in full first — not yet
   done, likely mirrors the same bootstrap-pipeline shape as flame speed.
4. Verify each new branch end-to-end against the real binary before calling it done —
   same rigor as the RCM branch this session (generate the script, run it for real,
   check the output file, don't just `ast.parse`-check the generator).

## Priority 4 — review_plan.md Phases 3–5 (never started)

The bulk of `bug.md`'s M16–M28 plus B10/B13 (B13 folded into Priority 2 above since it's
GUI-specific). Recommended order within this batch, grouped by the workstream they touch
so one person/session can stay in one area of the code:

- **Simulation-runner robustness** (M16, M21, M22, M18b, M20): error-handling/returncode
  checks across `cli.py`'s jsr/pfr/flux subcommands, `jsr_runner.py`/`pfr_runner.py`,
  MUQ-SAC's `run_script.py`/`data_management.py`, Zero-RK subprocess env sanitization,
  Cantera-conversion cache atomicity.
- **GSA/UQ correctness** (M19, M23, M25, M26): `gsa_prs_crosscheck.py`'s PRS-fit validity
  gate, the `ResponseSurface.py::evaluate()` order≥3 bug (the OTHER half of the fix
  already ported in 2026-07-11 — see BUG.md Part 19/M23 cross-reference), `error_metrics.py`
  NaN masking, `forward_uq.py`'s unkeyed cache.
- **Pipeline concurrency** (M24): `mso_compare/pipeline.py`'s `ThreadPoolExecutor` +
  per-worker `os.chdir()` CWD races — needs a real design change (per-worker subprocess
  with its own cwd argument, not a shared-process chdir), not a quick patch.
  M17 (migration transactionality) belongs in the same sitting since both are
  database/process-safety issues.
- **GUI hardening** (M27) — **DONE 2026-07-20**: `PtyTerminal` fd/zombie leak
  (`src/gui_common/pty_terminal.py::stop()`, lines 213-253), reader-thread race
  (generation-counter fix in `run()`/`_read_loop()`, lines 92-152), scrollback
  (`pyte.HistoryScreen` + Page Up/Down/mouse-wheel bindings, lines 77-81/107/188-198),
  and the close guard (`<Destroy>` binding, lines 87/207-211) — all fixed once in the
  shared widget, covering all 5 terminal-backed GUI apps at once. Regression tests:
  `src/rmip/tests/test_pty_terminal.py` (4 tests, all passing). See `bug.md`'s M27 entry
  for the full per-bug breakdown.
- **Minors batch** (review.md's MINOR list, `bug.md`): parser leniency warnings,
  `canonicalize.py` stoichiometry-in-key (may be superseded by the Priority-0 item 2 fix
  above — do that first, then re-assess what's left), argparse consistency, the
  `Uncertainty.py` vs. `uncertainty_generator_gui.py` convention mismatch (min-over-T vs.
  max-over-3-anchors — worth resolving now that both code paths are in one app, see
  Part 43), and the rest of the itemized list in `review_plan.md` Phase 5.

## Priority 5 — Future.md restart/checkpoint bug audit (status unconfirmed, re-verify first)

FUTURE-BUG-1 through FUTURE-BUG-6 (`bug.md`) were never explicitly confirmed fixed by any
later document, but two of them may have been incidentally touched by unrelated 2026-07-05
fixes. **Re-verify each one against current code before assuming it's still open** —
don't just re-fix blind. `simulation_manager2_0.py`/`partial_PRS_system.py` restart logic
is the target area.

## Priority 6 — Deferred cleanup (not bugs, standing decisions — only revisit if asked)

Quick win #13 (delete `bkp`/`backup` dirs) and structural improvement #2 (archive
`MUQ-SAC_EXTENDED/`) were explicitly declined by the user once already ("no need to
delete anything"). The repo is now under git (wasn't at the time), which was the original
blocker cited — but **do not unilaterally revisit this**; ask first if it comes up again,
since the user already gave a direct answer once. Structural improvements #3–#7 (God-Object
decomposition, PySide6 migration, etc.) are large, optional, architecture-level asks —
treat as backlog, not urgent.

---

## Ground-truth reference material (kept from the prior version of this file)

### Zero-RK integration conventions (for Priority 3 and any future zerork work)

- Zero-RK is built and installed at `/home/krithika/zero-rk/build2/inst_dir/bin/`. Full
  capability inventory in `MarkDownFiles/ZERORK_GSA_PLAN.md`.
- **Established pattern, follow exactly for any new target/solver**: every zerork
  parameter is a `target.add["zerork_*"]` default set ONLY in
  `combustion_target_class.py.__init__` (guarded `if "key" not in self.add:`), read ONLY
  in `make_input_file.py`'s solver branches, never hardcoded elsewhere. Every new solver
  option is just another string compared via `"zerork" in solver`, matching the existing
  `"CHEMKIN_PRO"`/`"cantera"`/`"FlameMaster"` checks. New target types get: (1) a
  recognizable string in `target.target`, (2) defaults in
  `combustion_target_class.py.__init__`, (3) one `elif` branch per solver inside
  `make_input_file.py`'s `create_input_file()`, (4) NO parallel parameter-plumbing path —
  `.target`/`.add` files are the only place a user-defined run can set a value.
- **Confirmed done**: Tig/JSR/RCM via `constVolumeWSR.x`/`constVolumePSR.x`/
  `variable_volume.x`. **Confirmed permanent gap, do not attempt**: PFR (Zero-RK has no
  such reactor at all).
- **Confirmed NOT a Zero-RK gap**: soot prediction from ChemkinPro is a separate,
  CHEMKIN_PRO-side feature gap, unrelated to Zero-RK. Track separately if it comes up
  again.
- Target-type naming convention: short, Capitalized-first abbreviations (`Tig`, `Fls`,
  `Flf`, `Flw`, `JSR`, `PFR`, RCM-as-Tig-submode). Any new counterflow/extinction tag
  should follow this (e.g. `Fcf`/`Fext`).

### Environment/tooling constraints (already in memory, repeated here for this file's own completeness)

- Always launch via `rmip_cli.py` at the repo root, never `python3 src/rmip/cli.py`
  directly — `src/rmip/io/` shadows the stdlib `io` module and crashes the interpreter if
  `src/rmip/` ends up at `sys.path[0]`. A second `src/io/` package (unrelated) exists too
  — verify any script directly under `src/` (not `src/rmip/`) with `--help` first before
  assuming it's safe by analogy.
- Never `pip install` a new dependency directly into the shared anaconda environment
  without checking numpy/scipy/pandas compatibility first — isolate in a venv, bridge via
  subprocess+JSON (see the SALib/GSA incident, `BUG.md`/memory).
- `rmip_cli.py parse` always creates a NEW mechanism row, never updates in place — old
  mechanism ids in `outputs/project.db` may be permanently stale from before a parser fix;
  check `mechanisms.loaded_at`/description before trusting an old id.

---

## Notes

- The `"/model opusplan"` line that appeared in an earlier session's `prompt.txt` was NOT
  executed — it read as a slash-command the user may have meant to type live, not a file
  instruction. Flagged at the time, not silently ignored or obeyed.
- This file and `progress.md` are the only two places session-continuity state lives.
  `MarkDownFiles/HISTORY/` and `BUG.md`/`bug.md` are the historical/reference record —
  update THEM only when new bugs are found or new history parts are completed, not as a
  running log (that's what `progress.md` is for).
