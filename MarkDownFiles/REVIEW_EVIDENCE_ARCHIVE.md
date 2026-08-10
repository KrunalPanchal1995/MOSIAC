# Deep-Review Evidence Archive

Consolidated 2026-07-22 from `.claude-review/` (9 working files from the
2026-07-11/13/14 deep-codebase-review runs) into this single file. This is the
detail layer behind `MarkDownFiles/review.md` / `review_plan.md` — those two
remain the synthesized, primary reference; this archive is the raw dynamic/static
evidence they were built from (exact repro commands, file:line detail, the
per-area findings that got merged into report.md). Pure consolidation, no content
dropped.

---

## .claude-review/report-2026-07-11.md

# Deep Codebase Review — Findings Report

Last updated: 2026-07-11

## Quick wins
Small, low-risk, high-value fixes — mostly single-line or few-line changes. Listed roughly in priority order (data-corruption/silently-broken-feature risks first).

Implementation status as of 2026-07-11 (this session): items 1, 4, 5, 6 were implemented in an earlier pass. Items 2, 3, 7, 8, 9, 15 were found **already fixed on disk** when this session re-checked them (fixed in an untracked prior pass not reflected in this checklist — see note at the end of this list). Items 10, 11, 12, 14 were implemented this session. Item 13 was deliberately **not** executed (see note). A new blocker found during re-verification (duplicate `_on_notebook_tab_changed` method silently shadowing itself) was also fixed this session.

1. [x] IMPLEMENTED — **`schema.py:250` / `schema_phase3.py:292` — fix `lastrowid == 0`/truthiness checks to `cur.rowcount == 0`.** Currently silently attaches data to the wrong DB row on any non-adjacent duplicate insert. Blocker, one-line fix each. Changed `schema.py:250` to `cur.rowcount == 0`; changed `schema_phase3.py:292` to `if cur.rowcount != 0: return cur.lastrowid`. `src/rmip/tests/test_phase3.py` (50 tests) still passes.
2. [x] ALREADY FIXED (verified) — **`generate_target_opt.py:5195,5197` — `self.after(` → `self.root.after(`.** Re-checked this session: both call sites already read `self.root.after(...)`.
3. [x] ALREADY FIXED (verified) — **`generate_target_opt.py:5536` — hardcoded `/home/krithika/anaconda3/bin/python`.** Re-checked this session: no remaining occurrence of that literal path in the file (repo-wide grep clean).
4. [x] IMPLEMENTED — **`types.py:1162-1177` — move `ReductionResult.load`/`.from_dict` back under `class ReductionResult`, out of `class NTCReport`.** `AttributeError` on every call today; used in production `cli.py` paths and tests. Moved both classmethods to after `ReductionResult.save()` (~line 874); removed the misplaced copy from `NTCReport`. `src/rmip/tests/` went from 351 passed/4 failed to 355 passed/0 failed.
5. [x] IMPLEMENTED — **`cli.py:1184-1187` — `mech_id = score.mechanism_id if score else None`.** `rmip rank` prints a dataclass repr instead of the id on every invocation. Loop var renamed to `score`; `mech_id` now derived from `score.mechanism_id`. No test coverage exists for this CLI path (per report's own note); full test suite (355 tests) still passes.
6. [x] IMPLEMENTED — **`cli.py` flux dry-run exit code (~1964-1967/2143-2147) — return 0 on the successful dry-run path**, matching `_cmd_jsr`/`_cmd_pfr`. Breaks CI/scripts checking exit codes today. `_cmd_flux` now returns 0 when `result is None` and `args.dry_run` is set (the only way `_run_muqsac_bridge_case` returns `None`), 1 otherwise. No existing test coverage; full test suite still passes.
7. [x] ALREADY FIXED (verified) + residual IMPLEMENTED (2026-07-11, follow-up session) — **`_chemkin_parser.py`/`chemkin_writer.py` reaction-order-based unit conversion.** `_chemkin_parser.py::_extract_representative_kinetics` (the function that drives actual SI conversion, ~line 969) uses `sum(coeff for _, coeff in rxn.reactants)` with an explanatory comment referencing the exact `2CH3(+M)<=>C2H6(+M)` case from the review. `chemkin_writer.py` derives `rxn_order` from stoichiometry per-reaction (~line 452) and uses `_si_to_cgs_factor(rxn_order)`; `SI_TO_CGS_BIMOL` is kept only "for reference/back-compat", not applied unconditionally. **Residual now fixed**: `_chemkin_parser.py` lines 684, 728, 759 (`_parse_arrhenius_triple`/`_parse_low_line`/`_parse_plog_line`) previously computed `A_units` (a descriptive string label only, not the numeric SI value) from `len(rxn.reactants)`; changed to the same `sum(coeff for _, coeff in rxn.reactants)` stoichiometric-order formula used by `_extract_representative_kinetics`, so the display label now agrees with the numeric conversion for repeated-reactant reactions.
8. [x] ALREADY FIXED (verified) — **Dash viz host binding.** Re-checked this session: `reduction/trim_viz.py:108` and `reduction/coefficient_viz.py:79` both bind `host="127.0.0.1"`; `cli.py` has no direct `host=` binding of its own (it calls into these). No `0.0.0.0` binding remains anywhere in the repo.
9. [x] ALREADY FIXED (verified) — **`generate_target_opt.py` shell-command quoting.** Re-checked this session: both call sites (~5139-5142, ~5173-5177) now wrap every interpolated value in `shlex.quote(...)` before building the `bash -c` string.
10. [x] IMPLEMENTED (this session) — **`generate_target_opt.py::_clear_trows` — added `askyesno` confirmation.** Guard skipped when the row list is already empty, and an explicit `confirm=False` parameter added for the one internal call site (`_restore_checkpoint`) so restoring a checkpoint doesn't pop a spurious dialog on its own programmatic clear.
11. [x] IMPLEMENTED (this session) — **`generate_target_opt.py` — all 10 literal `foreground="gray"` → `foreground=PALETTE["text_dim"]`.** Verified identical literal at all 10 sites; blanket replace applied; `ast.parse` clean.
12. [x] IMPLEMENTED (this session) — **`generate_target_opt_PHASE4_FIX.py` — deleted.** Repo-wide grep confirmed zero references before deletion.
13. [ ] **NOT executed — `src/MUQ-SAC/bkp/` and `src/Sensitivity_Analysis/backup/make_input_file.py` — recommended deletion (~11,554 LOC), deliberately deferred to the user.** This repo is not under git (confirmed via environment metadata), so there is no cheap rollback if the "already duplicated under `version_history/`" claim from the original review turns out to be stale. Recommend the user either confirms deletion explicitly or runs `git init` first so the removal is reversible. Left in place this session out of caution — see PLAN.md.
14. [x] IMPLEMENTED (this session) — **`generate_target_opt.py::_scrolled` — mouse-wheel binding added.** `<MouseWheel>` (Windows/macOS, `event.delta`) and `<Button-4>`/`<Button-5>` (Linux) bound/unbound on canvas `<Enter>`/`<Leave>` so wheel scrolling doesn't leak to other widgets. Applies app-wide since all 12 tabs route through this helper.
15. [x] ALREADY FIXED (verified) — **Duplicate `<<NotebookTabChanged>>` bind.** Re-checked this session: only one `nb.bind("<<NotebookTabChanged>>", ...)` call exists (line ~1754). **However**, a related but distinct blocker was found and fixed this session: two separate *methods* were both named `_on_notebook_tab_changed` (~line 2772, the reduction-tab auto-populate handler, and ~line 4519, the tab-locking handler) — Python silently keeps only the last definition, so the auto-populate-reduction-target feature was unreachable dead code even though the duplicate *bind* itself had already been cleaned up. Fixed by renaming the first to `_on_notebook_tab_changed_for_reduction` and calling it from the end of the surviving `_on_notebook_tab_changed` (tab-locking) method, so both behaviors now run on every tab change.

**Note on items found "already fixed":** this session opened by re-verifying every quick-win line reference against the current file before implementing, since report.md's checkboxes hadn't been updated to match. Six items (2, 3, 7, 8, 9, 15's bind-half) turned out to already be fixed in the working tree — likely from a prior editing pass in this same repo that was never reflected back into this checklist. Lesson for future sessions: update report.md checkboxes immediately after each fix lands, don't batch it to the end.

**Verification this session:** `python -m pytest src/rmip/tests/ -q` → 355 passed, 0 failed (same as before this session's changes — none of the fixes above touch `src/rmip/`). `ast.parse` clean on `generate_target_opt.py` after all edits.

## Structural improvements
Bigger changes, roughly ordered by impact. Effort estimates are rough.

1. [x] IMPLEMENTED (2026-07-11, follow-up session) — **Port the `src/Sensitivity_Analysis/ResponseSurface.py` bugfix from `src/MUQ-SAC/ResponseSurface.py`.** `MatPolyFitTransform()` lines 271-313 (buggy `row.index(value)`-based loops) replaced with the same `ii/jj/kk/ll/mm` range-based loops already used in `src/MUQ-SAC/ResponseSurface.py:315-379`, ported verbatim (tab-indentation matched to this file's style). Verified the fix numerically against the review's own documented example: row `[0.5, 0.3, 0.5]` now produces 10 order-3 terms (`C(5,3)`), not the buggy 21. `ast.parse` clean; full test suite still 355/355 (this module has no direct test coverage, unchanged by this fix).
2. **Archive `src/MUQ-SAC_EXTENDED/` (~16,070 LOC) plus the `bkp`/`backup` dirs above.** Zero live callers confirmed by repo-wide grep; it's a strictly worse (unfixed, thinner) fork of the still-used `src/MUQ-SAC/`. Small effort (move + README), removes ~a third of the "which copy is real" confusion in the legacy layer. Do this alongside item 1 — reading `MUQ-SAC_EXTENDED`'s still-broken `ResponseSurface.py` is what surfaces the fix that needs porting.
3. **Consolidate the duplicated `Input_file_reader.py`/`getRxnData*` O(N) `.index()` lookups across `src/MUQ-SAC/`, `src/Sensitivity_Analysis/` into one shared module with an O(1) dict-based lookup.** Medium effort — this is the deeper fix behind quick-win-adjacent performance issue; requires deciding where "shared kinetics-tool code" should live now that three lineages (`MUQ-SAC`, `Sensitivity_Analysis`, `rmip`) exist independently. Natural first step toward reducing the copy-paste-drift pattern that let the ResponseSurface bug diverge in the first place.
4. **Decompose `generate_target_opt.py`'s `class App` (~4,460 lines / ~150 methods) into per-tab controller modules.** Large effort, but this single God Object is the direct cause of at least two shipped bugs (duplicate `_on_notebook_tab_changed` definition, `self.after` vs `self.root.after` typo) — nothing today prevents two methods in different "concerns" from silently colliding on a name. This is also exactly the prerequisite work described as "Phase 1" in the GUI Framework Migration Plan below, so it's not wasted effort even if the org doesn't pursue the full PySide6 migration — extracting pure business logic out of `_collect()` and friends pays off either way.
5. **Add validation coverage: numeric-field validation in `_collect()`/`_validate_tab` (currently 4 of 12 tabs) and route the two most consequential long-running jobs (MSO/MUQ-SAC, Forward UQ) through the existing `PtyTerminal` widget instead of external OS terminal windows.** Medium effort, directly fixes the two biggest "the app looks broken to a scientist" UX gaps found in Phase 2 (crash-on-typo, job-finished status that only updates if the user manually returns to an external terminal window).
6. **GUI framework migration to PySide6 — see the dedicated "GUI Framework Migration Plan" section below for the full phased plan.** Large, multi-month effort; recommended but sequenced last since items 1-5 either de-risk it (item 4) or are worth doing regardless of whether the migration happens.
7. **Split `config_tools/` into a live `build_tools/`-style subset (XML2CSV, parallel_native, Shared_Objects) and an archived `legacy/config_tools_oneoffs/` subset (~3,500 LOC of unreferenced scripts).** Small-medium effort, mostly directory moves + a README; removes ambiguity about which scripts in that directory are actually part of the pipeline.

## Phase 1: Code review

### Scope note
This is a Python scientific/CLI suite for combustion reaction-mechanism optimization, with one large Tkinter desktop GUI (`generate_target_opt.py`'s `class App`) as its primary user-facing product — see Phase 2/3 below for the GUI/UX and aesthetics audit of that app, and the GUI Framework Migration Plan for a proposed PySide6 rewrite. Findings below (Phase 1) cover `src/rmip/` (primary package), root orchestration scripts, and tests. Legacy/duplicate dirs (`src/MUQ-SAC/`, `src/MUQ-SAC_EXTENDED/`, `src/Sensitivity_Analysis/`), vendored `PyChemkin-master/`, and `config_tools/` one-off scripts are covered separately in Phase 4/5 (performance + architecture), not here. All findings below were spot-checked against the actual source (line numbers and code content verified) before inclusion.

---

### src/rmip/types.py

- **types.py:1162-1177 (`ReductionResult.load`/`.from_dict` defined inside `class NTCReport` instead of `class ReductionResult`)** — **blocker** — VERIFIED (class boundaries: `ReductionResult` at line 842, `NTCReport` at line 1115, `from_dict`/`load` at 1162/1174 fall after the `NTCReport` header with no intervening class statement). `ReductionResult.load(...)` does not exist at runtime → `AttributeError`. Called in production code at `src/rmip/cli.py:608`, `src/rmip/cli.py:1668`, `src/rmip/reduction/trim_viz.py:24`, `src/rmip/reduction/coefficient_viz.py:17`, and by tests `test_phase5b.py:402`, `test_phase5b_extended.py:437`. `NTCReport.from_dict`/`.load` are also broken since they reference `ReductionResult` fields (`d["method"]`, `d["steps"]`) that don't exist on an NTC report dict.
  Fix: move `from_dict`/`load` back under `ReductionResult` (after its `save()` at line ~879); remove from `NTCReport`.

---

### src/rmip/database/schema.py

- **schema.py:250 (`insert_species` fallback-id check: `if cur.lastrowid == 0:`)** — **blocker** — VERIFIED. `sqlite3.Cursor.lastrowid` after a no-op `INSERT OR IGNORE` reflects the connection-wide `sqlite3_last_insert_rowid()` (the most recently inserted row on the whole connection), not `0`. Since some other row is almost always inserted earlier on the connection, this check essentially never fires, so the function silently returns the **stale id of an unrelated row** instead of doing the documented existing-row lookup. `test_phase3.py:991` only tests two *consecutive* inserts of the same name, which coincidentally makes `lastrowid` correct — masking the bug. Any non-adjacent duplicate species name corrupts stoichiometry linkage silently.
  Fix: check `cur.rowcount == 0` instead of `lastrowid == 0`.
- **schema.py:243-248, 289-293, and `BatchInserter._flush` 480-487 (dynamic column names from `kwargs.keys()` interpolated into raw SQL)** — **nice-to-have**. Not exploitable today (all call sites pass static kwargs), but `insert_species`/`insert_reaction` are exported public API; a future caller building kwargs from config/user input would have a SQL-injection vector.
  Fix: validate column names against an allow-list before interpolating.

### src/rmip/database/schema_phase3.py

- **schema_phase3.py:292 (`insert_exp_dataset`: `if cur.lastrowid:`)** — **blocker** — VERIFIED same pattern as above, more damaging in practice: load dataset A (id=1), load dataset B (id=2), reload dataset A (name conflict, no-op insert) → `lastrowid` is B's stale id `2` (truthy) → function returns `2`, and `ExpDataReader.load_csv` (`src/rmip/io/exp_data_reader.py:128-141`) attaches A's new points to dataset B's id.
  Fix: check `cur.rowcount == 0`.

### src/rmip/database/migrations.py

- **migrations.py:565-575 and 664-689 (idempotency probes for `reduction_runs`/`simulation_runs` use `mechanism_id=0`, which always fails the FK check)** — **should-fix**. Both tables have `mechanism_id INTEGER NOT NULL REFERENCES mechanisms(id)` with `PRAGMA foreign_keys = ON`; id `0` never exists, so the probe insert always raises `IntegrityError` regardless of whether the CHECK constraint already permits the value. The "already migrated — skip" fast path can never be taken; every startup on an already-migrated DB unnecessarily rebuilds these tables (rename → recreate → copy → drop). Self-heals transactionally, not destructive, but defeats the documented idempotency and wastes I/O on every run.
  Fix: probe with a `mechanism_id` that references a real row, or catch the FK-specific error message distinctly from the CHECK-constraint error.
- **migrations.py:572 (`except Exception:` in `_ensure_wide_reduction_method_constraint`, inconsistent with sibling functions that catch `sqlite3.IntegrityError` specifically)** — **should-fix**. Combined with the item above, this masks the FK-probe issue instead of surfacing it.
  Fix: narrow to `except sqlite3.IntegrityError:`.

### src/rmip/io/_chemkin_parser.py

- **_chemkin_parser.py:957-1012 + 1339-1388 (reaction order for A-factor unit conversion computed as `len(rxn.reactants)` — unique species count — instead of stoichiometric order)** — **blocker**. `_parse_species_side` aggregates repeated species via `Counter`, so `2CH3(+M)<=>C2H6(+M)` (a real, common combustion reaction) yields `reactants=[("CH3",2.0)]`, `len()==1` → treated as unimolecular (order 1, no conversion) when the true order is 2 (should divide A by 1e6). Produces an A-factor wrong by a factor of 1e6 with no warning. This parser is the fallback path used specifically when RMG-Py is unavailable (`chemkin_reader.py:104-137`) — i.e. exactly the scenario where it matters most. `test_chemkin_parser.py` unit-tests `_convert_to_si` with a manually-supplied order and never exercises a duplicated-reactant reaction, so the bug is invisible to the suite.
  Fix: compute order as `sum(coeff for _, coeff in rxn.reactants)`.

### src/rmip/io/chemkin_writer.py

- **chemkin_writer.py:449, 492, 521 (`SI_TO_CGS_BIMOL` (1e6) applied unconditionally regardless of actual reaction molecularity)** — **blocker**. Should be `1` for unimolecular, `1e6` for bimolecular, `1e12` for termolecular — comment at line 72-77 claims this is a documented fallback ("default to bimolecular... when order is unknown") but it's applied unconditionally, not just when unknown. Mostly hidden behind `use_original_units=True` (the default) using `A_orig`, but any mechanism lacking `A_orig` — including mechanisms produced by this suite's own fusion/optimization pipeline (`fused`/`optimized`/`unified`) — gets systematically wrong rate constants (off by up to 1e6) with no warning when written back out to CHEMKIN format. `test_phase3.py:1220-1228` only asserts the constructor flag is stored, not actual conversion output.
  Fix: derive reaction order from stoichiometry per-reaction (mirrors the `_chemkin_parser.py` fix) and select `1`/`1e6`/`1e12` accordingly.

### src/rmip/core/graph_builder.py

- **graph_builder.py:481-490 (`_carbon_number()` regex `r'C(\d*)'` matches any `C` character, misclassifying `Cl`, `Ca`, `Co`, `Cr`, `Cs`, `Cd`, `Ce`, `Cf`)** — **nice-to-have**, cosmetic (affects only graph-layout carbon-shell grouping, not chemistry data). `chemkin_writer.py`'s `_ALL_ELEMENTS` set shows the codebase does anticipate halogen/metal mechanisms (e.g. `CL`, `FE`, `NA`, `CA`).
  Fix: reuse `_ELEMENT_RE` (`r'([A-Z][a-z]?)(\d*)'`, already defined at line 582) instead of a bare substring search.

### src/rmip/core/parser.py

- **parser.py:348-374 (`_build_canonical_key()` silently returns `None` with no logging when a species lacks a glossary SMILES)** — **nice-to-have**. Degrades cross-mechanism reaction matching silently; no diagnostic trail.
  Fix: log which species lacked SMILES when returning `None`.
- **parser.py:33,57 (imports `RMIPConfig` and takes it as a constructor arg, contradicting `config.py:6-9`'s documented rule "Never import config from within io/ or core/ readers")** — **nice-to-have**, architectural rule violated in the exact module the rule calls out. No functional bug today (no circular import), but couples `MechanismParser` to `RMIPConfig` unnecessarily.

### src/rmip/config.py

- **config.py:34-72 (`regime_thresholds`/`LTC_MAX_K`/`NTC_MAX_K` are dead configuration — nothing reads them)** — **nice-to-have**. `SimCondition.regime()` (`types.py:93-100`) hardcodes `850.0`/`1000.0` directly instead of consulting `RMIPConfig`; the `Regime` enum docstring even calls this a "fixed-threshold fallback," so the config surface is pure dead weight with a misleading docstring promising it's configurable.
  Fix: wire `RMIPConfig.regime_thresholds` through to `SimCondition.regime()`, or delete the unused config knob.

**Checked, found solid (core/database/io):** SQL elsewhere uses parameterized `?` placeholders correctly; no `eval`/`exec`/`pickle` in this cluster; `yaml.safe_load` used consistently; RDKit-unavailable fallback in `canonicalize.py` is a reasonable, clearly-logged degradation; `stubs.py` methods all either implement a real contract or raise `NotImplementedError` (nothing misleadingly half-working).

---

### src/rmip/analysis/, optimization/, generation/ (~9,800 LOC across 19 modules, all read)

- **analysis/unified_tree.py:504-512 (`_pick_verbatim_source()` resolves a `KEEP_ANCHOR` decision's source via `min(d.source_mech_ids)` rather than the actual anchor mechanism id, which isn't even passed into the function)** — **blocker — FIXED (2026-07-11, follow-up session)**. Root cause was worse than the one-line description suggests: `anchor_mech_id` isn't just unused in `_pick_verbatim_source`, it's genuinely unrecoverable in the real `rmip unify-build` CLI path, because `plan()` and `build()` run as **separate CLI invocations** (`unify-plan` then `unify-build`), and `decisions.csv` (the only thing passed between them) never carried `anchor_mech_id` — so `plan.anchor_mech_id if plan else None` was always `None` in production, not just in the "non-anchor mech happens to have a lower id" edge case. Fix: `plan()` now writes a `<manifest_path>.meta.json` sidecar with `{mode, anchor_mech_id}`; `build()` reads it when invoked with `manifest_path` only (no in-memory `plan` object) and threads `anchor_mech_id` through `_build_rxn_record()` into `_pick_verbatim_source()`, which now resolves `KEEP_ANCHOR` to the actual anchor id (falling back to `min(source_mech_ids)` with a logged warning only if the sidecar is missing/stale — e.g. a manifest from before this fix). Also fixes a related, previously-unreported bug this uncovered: `meta["mode"]` and the `unified_tree_runs.mode`/`anchor_mech_id` DB columns were **always** `"unknown"`/`None` for every real CLI-driven build, for the same reason. Verified with a manual two-process repro (separate `UnifiedTreeBuilder` instances for `plan()` and `build()`, anchor set to the *higher*-id mechanism with divergent kinetics from the lower-id one) — unified R3 correctly carries the anchor's `A_si=2e15/Ea_si=490000`, not the lower-id mechanism's `1e15/494000`. Existing test fixtures still don't exercise this (anchor is always mech 1, the lowest id), so no existing test caught this either way — a targeted regression test is a good follow-up but wasn't added this session. Full suite still 355/355; `ast.parse` clean.
  Fix: thread the actual `anchor_mech_id` into `_pick_verbatim_source` and prefer it directly when present in `source_mech_ids`.
- **analysis/unified_tree.py:377 (`zip()` pairs all `OPTIMIZE` decisions against a potentially-shorter `bands` list)** — **should-fix**. When an `OPTIMIZE` reaction fails to build (a path the module explicitly anticipates and logs), later decision/band pairs silently drop out of the Phase-4 audit-trail DB tables via `zip`'s silent truncation.
- **analysis/parameter_estimator.py:188 (`estimate_arrhenius()` takes `np.log(A_arr)` without filtering non-positive `A`)** — **should-fix**. Parallel logic in `graph_comparator._aggregate_kinetics` does filter; here a non-positive `A` produces `-inf`/`NaN` that silently propagates into MSO optimization bounds.
- **analysis/uncertainty_bands.py:351 (uncaught `ZeroDivisionError` on duplicate PLOG pressure entries)** — **should-fix**.
- **generation/rmg_interface.py:241 (redundant multiply-then-divide by `fuel_mole_frac` crashes instead of validating `fuel_mole_frac == 0`)** — **should-fix**.
- **optimization/mso_interface.py vs generation/rmg_interface.py (inconsistent subprocess error handling between the two)** — **nice-to-have**.
- **analysis/fusion.py (`_modal_value()` has a non-deterministic tie-break)** — **should-fix**, reproducibility risk for fused mechanisms (same input could yield different output across runs/machines).
- **analysis/fusion.py (module docstring doesn't match implementation)** — **nice-to-have**.
- **analysis/mechanism_report.py (NASA-7 coefficient-array length not validated before use)** — **should-fix**.
- **generation/missing_species_predictor.py (overly broad silent `except Exception`)** — **should-fix**.

---

### src/rmip/simulation/, reduction/, intelligence/, reporting/, cli.py

- **cli.py:1184-1187 (`_cmd_rank` prints the full `RegimeScore` dataclass repr as "mech_id" instead of `score.mechanism_id`)** — **should-fix**. `report.best_per_regime()` returns `Dict[str, Optional[RegimeScore]]`; the loop treats the value as if it were already an id. Confusing/incorrect output on every `rmip rank` call.
  Fix: `mech_id = score.mechanism_id if score else None` before printing.
- **cli.py:1964-1967 vs 2143-2147 (`rmip flux --dry-run` returns exit code 1 on success)** — **should-fix**. `_run_muqsac_bridge_case` returns `None` for the successful dry-run path; `_cmd_flux` treats `None` as an error and returns 1 — inconsistent with `_cmd_jsr`/`_cmd_pfr`, which explicitly `return 0` on dry-run. Breaks CI/scripts checking exit codes.
- **cli.py (whole file, 2168 lines, zero `try/except` blocks)** — **nice-to-have** (systemic UX gap). Every subcommand hits DB/file/Cantera/subprocess calls directly; any usage error surfaces as a raw traceback instead of an actionable CLI message.
  Fix: wrap `args.func(args)` in `main()` with a top-level `try/except Exception as exc: log.error(...); return 1`.
- **cli.py:1702-1703, 1719-1720 vs reduction/trim_viz.py:108 and reduction/coefficient_viz.py:79 (`app.run(host="0.0.0.0", ...)` while the CLI prints "Launching ... at http://localhost:{port}")** — **should-fix, security-relevant** — VERIFIED both viz files bind `0.0.0.0`. The Dash visualizer servers are reachable from any network interface (unauthenticated, interactive), not just localhost as the printed message implies — real risk of accidental exposure on a shared/cloud host.
  Fix: default `host="127.0.0.1"` (or add a `--host` flag defaulting to localhost) so behavior matches the message.
- **reduction/drg.py:227-230, 290-292 (and shared by `DRGPSAReducer`/`DRGSAReducer`/`PFAReducer`/`DRGEPReducer` via inheritance) — reaction-lookup tables stored as side-effect instance attributes (`self._rxn_formula_to_species` etc.)** — **should-fix**. Correct only because `reduce()` always calls `_load_stoichiometry` immediately before use; a reducer instance reused concurrently across mechanisms (e.g. from multiple threads) would silently corrupt results for one caller. Shared mutable state / latent race condition.
- **reduction/drg.py:217-225, drgep.py:157-170, pfa.py:99-110 (O(N²) BFS/Dijkstra/matrix-assembly scanning *all* species per step instead of each species' sparse neighbors)** — **nice-to-have** (correctness fine, scalability concern). Runs ~51 times (once per ε step) × O(N²) — can get slow on large detailed mechanisms (hundreds-thousands of species).
  Fix: build an adjacency structure once, iterate only over actual neighbors.
- **simulation/muqsac_bridge.py:122 (unhandled `StopIteration` if resolved `fuel_dict` is empty)** — **should-fix**. `next(iter(fuel_dict))` crashes with a cryptic error if no fuel species has nonzero mole fraction; worse, `rmip.target` is already written to disk (line 118) before this point, leaving a partial/garbage file on failure.
  Fix: validate `fuel_dict` is non-empty right after `_resolve_composition()`, raise a clear `ValueError`.
- **simulation/idt_runner.py:217 (`ZeroDivisionError` for `n_steps < 4`: `t_end*0.001/(n_steps//4)`)** — **nice-to-have** (not reachable via current CLI, but a public Python-API parameter with no validation).
- **simulation/sensitivity_runner.py:190-198 (`_estimate_T_ad` silently swallows all exceptions with no logging, falling back to `gas.T + 1500.0`)** — **should-fix**. Any real Cantera/thermo failure is masked, potentially producing a wrong ignition threshold with no diagnostic trail.
  Fix: `except Exception as exc: log.debug(...)` before the fallback return.
- **simulation/performance_ranker.py — no direct unit tests** — **should-fix** (test-coverage gap). Only exercised indirectly via 2 tests in `test_phase6.py`; core scoring/ranking/matching logic untested, which is how the `cli.py:1184` bug above went uncaught.
- **cli.py subcommands almost entirely untested** — **should-fix** (test-coverage gap). Only `reduce`/`reduce-viz` have CLI-level tests; `rank`, `bench`, `jsr`, `pfr`, `flux`, `export`, `fuse`, `optimize`, `complete`, `predict-missing`, `report`, `ntc`, `plog-surface`, `reverse-scan`, `compare`, `compare-graph`, `visualize`, `visualize3d`, `parse`, `graph`, `list`, `summary`, `reactions`, `reaction-matrix`, `sparsity`, `sensitivity`, `sa-run`, `exp-load`, `unify-plan`, `unify-build` have zero CLI-invocation tests — directly explains why the `rank`/`flux` bugs above shipped unnoticed.
- **intelligence/ and reporting/ packages are empty stubs** — informational, not a bug. Named in review scope but contain only a one-line docstring each ("Phase 5+ (M10 AI Recommender)" / "Phase 6+ (M12 ReportEngine)"), no implementation or tests.

---

### Root orchestration scripts

**`generate_target_opt.py` (6,052 lines — largest and riskiest file in the repo) — structural breakdown:**
| Lines | Content |
|---|---|
| 1-476 | Imports, optional-dependency guards, helper classes (`FuelNormalizer`, `TabLockingManager`, `VariableNameMapper`, GUI-settings load/save, `PtyTerminal`, `AutoSaveManager`) |
| 483-869 | Theme/fonts, help text, algorithm tables, `DEFAULT_CONFIG` (entire target.opt schema) |
| 890-1373 | Pure file-generator functions (`config_to_yaml`, `generate_target_file`, `generate_addendum_file`, `derive_global_reaction`, `translate_species_for_mechanism`, `convert_mechanism_files`, `generate_uncertainty_xml`) — best-factored part of the file, small/documented/single-purpose |
| 1375-1552 | Theme application, `run_cli` |
| 1553-6015 | **Single `class App`, ~4,460 lines / ~150 methods** — all 12 GUI tabs, dialogs, subprocess launchers, config serialization, checkpoint/autosave, and domain logic (species translation, mechanism fusion, HTT/LTT splitting) in one God Object |
| 6015-6052 | `main()`/argparse entry |

- **generate_target_opt.py:2773 and :4520 (`_on_notebook_tab_changed` defined twice in `class App`)** — **blocker** — VERIFIED both definitions exist (line 2773: auto-populates reduction target species on first RMIP Analysis tab open; line 4520: tab-locking click handler). Python keeps only the last definition; the line-2773 handler (and its `_auto_populate_reduction_target()` call) is unreachable dead code — the documented "auto-load target species" feature never runs.
  Fix: rename one method (e.g. keep tab-locking as `_on_notebook_tab_changed`, rename the other to `_on_notebook_tab_changed_for_reduction`) and call both from the bind.
- **generate_target_opt.py:5195, 5197 (`self.after(...)` called on `self` instead of `self.root.after(...)` in the Forward-UQ result-polling thread)** — **should-fix**. Every other background-thread callback correctly uses `self.root.after(...)`. `App` has no `after()` method, so both the main call and its own exception handler raise `AttributeError`, silently killing the daemon thread — the "append forward UQ results" feature never works.
  Fix: `self.after(` → `self.root.after(` at both lines.
- **generate_target_opt.py:5536 (hardcoded `/home/krithika/anaconda3/bin/python` in a `subprocess.run` call)** — **blocker** — VERIFIED. Not a placeholder — a live path baked into `_append_mso_report_section`. Fails with `FileNotFoundError` on any machine other than the original dev machine.
  Fix: use `sys.executable`.
- **generate_target_opt.py:755-761 (`DEFAULT_CONFIG["Bin"]` has 4 hardcoded developer-machine absolute paths, breaking the file's own `PLACEHOLDER_*` convention used everywhere else in the same dict)** — **should-fix**. `"bin": "/home/krithika/MUQ-SAC/V3.0"`, `"solver_bin": "/home/krithika/FlameMaster/Bin/bin"`, plus two `/data/OPEN_CODE/PHASE-3/...` paths — silently point at nonexistent paths on any other checkout, unlike e.g. `Locations.mechanism = "PLACEHOLDER_MECHANISM.yaml"` which is obviously a placeholder.
  Fix: rename to `PLACEHOLDER_BIN_MUQSAC`, `PLACEHOLDER_SOLVER_BIN`, etc.
- **generate_target_opt.py:5139-5142, 5173-5176 (unquoted GUI free-text fields interpolated into a shell command string later run via `bash -c`)** — **should-fix, security-relevant**. `cmd = f"cd {wd!r} && {cmd_var.get().strip()}"` and the forward-UQ launch command interpolate `opt_path`/`out_dir` from free-text GUI fields with no shell quoting (`!r`/`repr()` is not shell-safe). A path/value containing a space or shell metacharacter breaks the command or executes unintended shell content.
  Fix: `shlex.quote()` each interpolated value before building the shell string.
- **generate_target_opt.py:4020-4038 (`_fill_xml_const` uses a broad `except Exception` to recompute the same value manually — but the fallback path re-raises the identical `ValueError` for bad numeric input)** — **nice-to-have**. Conflates "numpy unavailable" (import-time) with "bad user input" (should be validated separately).
- **generate_target_opt.py:4233-4399 (`_collect`) / 4567-4598 (`_validate_tab`) (no numeric validation before parsing ~30 numeric fields)** — **should-fix**. Any non-numeric text typed into a numeric Entry widget raises an uncaught `ValueError` on Preview/Save/Generate.
- **generate_target_opt.py:65-89 vs chem_data.py:63-127 (duplicated fuel property table — `FuelNormalizer.CANONICAL_FUELS` re-declares ~19 fuels' MW/nu_O2 already in `chem_data.DEFAULT_FUEL_MW`/`DEFAULT_STOICH_O2`)** — **nice-to-have**, DRY violation; currently in sync but two hand-maintained copies will drift. `chem_data.py`'s own docstring says it's meant to be the shared source.
- **generate_target_opt.py:5108 (`_run_job`'s watcher thread calls `self._status.set(...)` — a `tk.StringVar` — directly from a background thread instead of via `self.root.after(...)`)** — **nice-to-have**. Tkinter/Tcl isn't thread-safe; can intermittently corrupt UI state depending on platform/Tcl build.
- **`class App` is ~4,460 lines / ~150 methods** — **should-fix (readability/architecture)**. UI layout, validation, subprocess orchestration, serialization, and domain logic all live as methods on one object with no separation of concerns — directly enabled the two duplicate-method/wrong-`self` bugs above, since nothing prevents two methods in different "concerns" from colliding on a name. Existing `_tab_*`/`_rs_*`/`_mm_*`/`_latex_*` naming prefixes suggest a natural split into per-tab controller classes/modules.
- **~50 `except Exception` blocks throughout `generate_target_opt.py`** — **nice-to-have**, mostly benign (UI teardown/optional-file loads) but broad enough to mask unrelated bugs; several are silent (no logging) in file I/O paths specifically.

**`generate_target_opt_PHASE4_FIX.py` (129 lines)** — **should-fix**. Confirmed via repo-wide search: not imported anywhere. A standalone dev/scratch prototype of the tab-locking concept later implemented properly as `TabLockingManager` in `generate_target_opt.py:160-243` ("PROPER IMPLEMENTATION TEST" docstring confirms it was a design scratchpad, never merged, never deleted).
  Fix: delete, or move to a `dev/scratch/` directory — currently looks like production code sitting in repo root.

**`forward_uq.py`:**
- **Lines 154-156 (`min(T_vals)`/`max(T_vals)` on a possibly-empty `target_list`)** — **should-fix**. Raises uncaught `ValueError: min() arg is an empty sequence` instead of a clear "no targets loaded" message when the targets file is empty.
- **Line 45 (`warnings.filterwarnings("ignore")` blanket-suppresses all warnings at import time)** — **nice-to-have**. Can hide real deprecation/precision issues from numpy/pandas/sklearn during long Monte Carlo runs.
- **Lines 122, 128 (`pickle.load`/`pickle.dump` for a local `unsrt.pkl` cache)** — **nice-to-have**. Not attacker-controlled today, but unsafe if the cache file is ever shared/copied between environments.
- **Lines 143-144 (files opened without context managers: `open(...).read()`/`.readlines()`)** — **nice-to-have**, inconsistent with `with open(...)` used elsewhere in the same file.
- **Lines 462-471 (broad `except Exception as exc:` per-case in the Sobol-index loop, printed without traceback)** — **nice-to-have**; acceptable for continuing a batch job, but harder to diagnose without a rerun.

**`chem_data.py`, `graph_sa_run.py`, `rmip_cli.py`, `conftest.py`, `run_forward_uq.sh`, `run_graph_sa.sh`** — no correctness/security issues found. `chem_data.py`'s formula/MW/nu_O2 math was hand-verified against combustion stoichiometry for H2/CH4/NC7H16/NH3/N2H4. Shell scripts use `set -euo pipefail` and quote variables correctly. Minor nice-to-have: the `sys.path`-shadow-avoidance snippet is duplicated near-identically across `rmip_cli.py`, `conftest.py`, `graph_sa_run.py`, `forward_uq.py` — small enough not to be risky, but could be factored into one helper.

**Test coverage gaps (root level):**
- `generate_target_opt.py` (6,052 lines, largest/riskiest file in repo) has **zero** test coverage — none of the pure, easily-testable generator functions (lines 890-1373) or `App` methods are tested. Directly consistent with the duplicate-method and `self.after` bugs shipping unnoticed.
- `chem_data.py` has only an ad-hoc `__main__` self-test block, not wired into pytest.
- `tests/test_forward_uq.py` (305 lines) is solid, focused coverage of `forward_uq`'s pure-math internals with good synthetic/analytical expected values — this is the one bright spot in root-level test coverage.

## Phase 2: GUI & UX

### Scope correction (2026-07-11 resume)
The initial pass of this review incorrectly marked Phase 2/3 as N/A. Correction: `/data/Open_CODE/Phase-3` referenced in checkpoint paths is confirmed by the user to be **the same codebase as this repo**, not an external app. `generate_target_opt.py`'s `class App` (lines 1553-6015, ~150 methods) **is the primary product GUI** — a Tkinter desktop application with a `ttk.Notebook` of 12 tabs (`_tab_project`, `_tab_mechanisms`, `_tab_experimental_data`, `_tab_addendum_builder`, `_tab_reaction_screening`, `_tab_xml_builder`, `_tab_locations`, `_tab_optimization`, `_tab_rmip_analysis`, `_tab_forwarduq`, `_tab_so_compiler`, `_tab_preview`) plus roughly 10 additional standalone dialogs reachable from the menu bar (LaTeX project builder, Gemini-backed PDF Q&A notebook, plot digitizer, PDF table extractor, symbolic-regression panel, CKCSV viewer, mechanism-diagnostics dialog, MW/stoichiometry calculator, guided tour). Findings below are from a full pass over this GUI.

- **generate_target_opt.py:5195,5197 (Forward UQ result callback calls `self.after(...)`, a method that doesn't exist on `App`)** — **blocker** — `_run_forward_uq`'s background poller (`_poll_results`, lines 5152-5200) does `self.after(0, lambda txt=...: self._uq_append_result(txt))`. `class App` (line 1553) has no base class and defines no `after()` — only `PtyTerminal` (a `ttk.Frame` subclass) legitimately has `self.after(...)`. When the polling thread finds `forward_uq_statistics.csv`, this raises `AttributeError` inside a daemon thread, uncaught by Tkinter's callback machinery — dies silently to stderr. Net effect: Forward UQ results never populate the "Results summary" box even on a fully successful run. (Same root bug already flagged in Phase 1 from a code-correctness angle; repeated here because it's also a user-facing "the feature silently doesn't work" UX failure, the worst kind.)
  Fix: `self.after(` → `self.root.after(`.
- **generate_target_opt.py:5181-5200 (`_poll_results` gives up silently after 60s with zero UI feedback)** — **should-fix**. Loops `for _ in range(30): time.sleep(2)` looking for the QMC results CSV, then falls off the end with no indication if the job (help text at line 652 says it can run 50k-200k samples) isn't done yet. User is left with a stale "Launching: …" status and no sign the GUI stopped watching.
  Fix: on timeout, update status to "Still running — check the terminal window; click 'Open output folder' when done."
- **generate_target_opt.py:4233-4399, 5681-5711 (~30 unvalidated `int()`/`float()` calls feed directly into Preview/Save with no error handling, no `validatecommand` anywhere in the file)** — **blocker**. `_collect()` does e.g. `int(self._n_rxn.get() or 10)`, `float(self._cutoff.get() or 1)` for ~30 fields with no try/except in the call chain; `_preview()`, `_save_opt()`, `_quick_save()` call `_collect()` unwrapped. No `root.report_callback_exception` override either. A stray letter in any numeric field + clicking Preview/Save prints a traceback to console and the click visibly does nothing — no dialog, no highlighted field. Looks like a broken button to the user.
  Fix: wrap `_collect()` in try/except with `messagebox.showerror` naming the offending field, or add `validatecommand` to numeric entries in `_field()` (line 1891).
- **generate_target_opt.py:4567-4598 (`_validate_tab` only covers 4 of 12 tabs — Project, Experimental Data, Addendum, Files & Paths)** — **should-fix**. Optimization, RMIP Analysis, Forward UQ, Reaction Screening, Uncertainty XML, Compile, Preview never get validated, even though they hold the ~30 numeric fields above. `TabLockingManager`'s "✓ complete" badge gives false confidence — a tab can show "done" while containing garbage that only fails later, silently, at Preview/Save time.
  Fix: extend validation to attempt-parse numeric fields per tab before marking visited.
- **generate_target_opt.py:3172, 3385-3391 ("Clear all" wipes every experimental-data row with zero confirmation)** — **should-fix**. Unlike the app's own pattern for lower-stakes actions (HTT/LTT split confirm at 3434, subset-confirm at 2831, "Create subfolder?" at 1881), `_clear_trows()` has no `askyesno` guard. Since `AutoSaveManager` fires every 5s and marks dirty on any `StringVar` trace, an accidental click can get autosaved into `.rmip_gui_autosave.json` before the user notices — defeating the checkpoint system's own purpose.
  Fix: add `askyesno` confirmation before `_clear_trows()`.
- **generate_target_opt.py:462-469, 4444-4452 (autosave/checkpoint failures swallowed to console only)** — **should-fix**. `AutoSaveManager._do_save` and `App._save_checkpoint_silent` both catch all exceptions and only `print(...)`; neither updates status nor shows a dialog. This is the app's designated data-loss safety net — a disk-full/permission error means it silently stops protecting the user's work with no on-screen sign.
  Fix: on repeated autosave failure, set a persistent status-bar warning (e.g. red "⚠ autosave failing") instead of console-only logging.
- **generate_target_opt.py:2969-3053, 3772-3802, 3804-3834 (background job launches have no busy state, no re-entrancy guard, no progress bar anywhere in 6,000 lines)** — **should-fix**. Every `threading.Thread(target=_worker, daemon=True).start()` pattern (mechanism reduction, RMIP comparison, quick SA, others) just sets one status-bar line. No button gets disabled, no busy cursor, zero `ttk.Progressbar` in the file. A user can click "Run" repeatedly and start overlapping jobs against the same SQLite DB/output dir with no visual indication of progress.
  Fix: disable the trigger button and show an indeterminate `ttk.Progressbar` for the worker's duration.
- **generate_target_opt.py:5064-5148, 5152-5178 vs 3723-3851 (the two most important long-running jobs get worse feedback than a minor one)** — **should-fix**. The app has a real embedded terminal, `PtyTerminal` (328-439, `pty.fork()` + `pyte`), wired up for Reaction Screening's SA button (3723, 3851). But the main MSO/MUQ-SAC optimization run (`_run_job`, 5064-5148) and Forward UQ (`_run_forward_uq`, 5152-5178) instead shell out to an *external* OS terminal (gnome-terminal/xterm/konsole, 5088-5100) Tk has no control over — status bar shows only a PID and "finished" (which only fires once the user manually presses Enter in that external terminal, since the command is wrapped with `; read`). Alt-tab away and the status bar says "launched" indefinitely.
  Fix: route MSO/MUQ-SAC and Forward UQ through the same `PtyTerminal` used for Reaction Screening, for one consistent, in-GUI, observable job-monitoring experience. (Also ties into the GUI-migration plan below — `QProcess` fixes this architecturally.)
- **generate_target_opt.py:1781-1794 (`_scrolled()` canvas has no mouse-wheel binding anywhere in the file)** — **should-fix**. The only way to scroll any tab is dragging the thin `ttk.Scrollbar`. Matters most on the Optimization tab, which stacks ~25 `_field()` rows under 4 section headers (2452-2520) with no columns — reaching "Adaptive Outlier Retraining" at the bottom requires repeated scrollbar drags on a laptop screen.
  Fix: bind `<MouseWheel>`/`<Button-4>`/`<Button-5>` on the canvas in `_scrolled()`.
- **generate_target_opt.py:1729 and 1755 (duplicate `<<NotebookTabChanged>>` binding)** — **nice-to-have**. Bound twice (once after `nb` creation, again after `TabLockingManager` setup), so `_on_notebook_tab_changed` (itself wrapped in a bare `except Exception: pass`) runs twice per tab click. Harmless but a maintenance trap that double-swallows errors.
  Fix: remove the earlier duplicate bind at line 1729.
- **generate_target_opt.py:1611-1619, 1691-1693 (only 3 keyboard accelerators — Ctrl+O/S/Q — across ~150 actions)** — **nice-to-have**. A real accessibility positive that goes only partway. Preview and Next/Previous tab (core to the 12-tab wizard flow) have none.
  Fix: add accelerators at least for Preview and Next/Previous tab.
- **generate_target_opt.py:1799-1850, 539-658 (help system: good pattern, narrow trigger target)** — **nice-to-have**. A genuinely good discoverability pattern — a comprehensive `_HELP` dictionary surfaced through a shared "ⓘ" popover (`_show_tip`), dismissible via outside-click/Escape. Gap: click-only on a tiny 3-character glyph, no hover preview, so first-time users have no cue a field has extra help.
  Fix: add a hover-triggered tooltip in addition to the click popover.
- **generate_target_opt.py:4660-4702 (guided Tour is 12 sequential blocking `askyesno` dialogs)** — **nice-to-have**. Functionally fine but a clunky 12-click onboarding flow rather than a lightweight coach-mark/banner.
  Fix: consider a single non-blocking overlay/status-bar walkthrough instead.
- **generate_target_opt.py:2463-2518 (field labels inconsistently mix plain English and raw backend variable names)** — **nice-to-have**. Some Optimization-tab labels are translated ("Order of PRS (polynomial)"), others expose the raw config key verbatim ("pm_p (power-mean exponent)", "softmax_beta (minimax pressure)", "pen_alpha (floor fraction)").
  Fix: normalize all labels to plain English, keep the backend key in the tooltip only (`VariableNameMapper`, 246-306, already half-supports this).
- **generate_target_opt.py:1731-1746 (positive — deliberate tab ordering, not accidental)** — for context. A comment at 1731-1734 explains file-producing tabs were intentionally placed before "Files & Paths" so that tab becomes a pre-filled confirmation step. Real, deliberate IA work — undercut only by the validation-coverage gap above, which doesn't back up the wizard metaphor it creates.

## Phase 3: Aesthetics & visual design

- **generate_target_opt.py:483-533, 1375-1519 (positive — a real, centralized design-token system exists)** — for context. `PALETTE` (14 named colors) and `FONTS` (11 named font roles), consumed via a proper `ttk.Style` pass on the `"clam"` base theme (`_apply_theme`, 1375-1519) covering TFrame/TLabel/TButton/TEntry/TCombobox/TNotebook/TScrollbar/TSeparator uniformly. This is a legitimately "designed on purpose" dark theme, not default-Tkinter grey. Findings below are about where the app doesn't honor its own system.
- **generate_target_opt.py:338-341 vs 483-498 (a second, unrelated color palette bleeds into the themed UI)** — **should-fix**. `PtyTerminal._FG_COLORS` (338-341) hardcodes a Catppuccin-Mocha-style ANSI palette intended for terminal text (`"green": "#a6e3a1"`, `"red": "#f38ba8"`, bg `"#1e1e2e"`, text `"#cdd6f4"`). That palette then leaks into unrelated App UI instead of `PALETTE`: success labels at 3092, 4892, 4974 use literal `foreground="#a6e3a1"` where `PALETTE["success"]` (`#22c55e`) exists; a warning label at 2907 uses `"#f38ba8"` where `PALETTE["warning"]`/`["error"]` exist; the matplotlib 3D scatter figure (2918-2930) is fully styled with this second palette rather than `PALETTE["bg"]`/`["surface"]`. Two different "success green"s and two different dark backgrounds are visible in the same app depending on which dialog is open.
  Fix: reference `PALETTE[...]` everywhere instead of re-typing the terminal-emulator's hex values.
- **generate_target_opt.py: 10 instances of literal `foreground="gray"` instead of the `text_dim` token (lines 2316, 3065, 3166, 3515, 3932, 3952, 3957, 4095, 4124, 4217)** — **should-fix**. Ten labels across ≥8 tabs use the raw Tk color name `"gray"` (X11 `#BEBEBE`) for secondary text, while the rest of the app correctly uses `PALETTE["text_dim"]` (`#94a3b8`) or the `"Dim.TLabel"` style. Visibly different shade depending on which tab you're viewing.
  Fix: replace all ten with `foreground=PALETTE["text_dim"]`.
- **generate_target_opt.py: font tuples hardcoded outside the `FONTS` token table (lines 344, 3103, 5274, 5436, 5478, 5632)** — **nice-to-have**. `PtyTerminal` defaults to `font=("Courier", 10)` (344) — a family used nowhere else (app standardizes on DejaVu Sans/DejaVu Sans Mono). `font=("DejaVu Sans Mono", 8)` (3103) and `("DejaVu Sans", 7)` (5274) go below the smallest defined token (`FONTS["small"]` = 9pt). `("DejaVu Sans Mono", 9)` is re-typed literally 3 separate times (5436, 5478, 5632) instead of using `FONTS["mono_small"]`.
  Fix: route all through `FONTS[...]`; drop the 7pt/Courier outliers.
- **generate_target_opt.py:500-515 (`TAB_COLORS` is a fully-built, unused second accent palette with a stale ordering comment)** — **nice-to-have**. Explicitly commented "currently unused elsewhere in the file" — a whole per-tab color-coding design decision made and never implemented. Its own ordering comment is stale too: lists a "Targets" tab that doesn't exist under that name and doesn't match the actual `nb.add(...)` order at 1735-1746.
  Fix: wire it into tab labels/icons as intended, or delete it.
- **generate_target_opt.py: iconography is 100% emoji/unicode glyphs, no image assets, no window icon (e.g. lines 1682, 3086, 3088)** — **nice-to-have**. Buttons use Unicode glyphs (💾 ▶ ✕ ✓ 🔒 ⓘ 📂 🖼) throughout — `PhotoImage` is used exactly once in the whole file (5262), only for user-generated plot thumbnails, not UI chrome. No `root.iconphoto()`/`iconbitmap()` anywhere — window/taskbar shows Tk's default feather icon. Coherent low-effort strategy but font-dependent — renders as tofu boxes on a minimal Linux box without a color-emoji font.
  Fix: at minimum set a `root.iconphoto()` app icon; consider a small SVG/PNG icon set for the highest-traffic actions longer-term.
- **generate_target_opt.py:2452-2520 (Optimization tab is one long flat single-column form, ~25 stacked fields)** — **should-fix**. `_tab_optimization` stacks PRS/Design settings → Objective Function → one weight field per `TARGET_TYPES` entry (8 of them) → Adaptive Outlier Retraining in a single vertical column separated only by `_section()` dividers. No side-by-side columns/cards/sub-notebook. This is the clearest instance of the "flat/overwhelming" IA concern in the whole app.
  Fix: split into a sub-notebook (PRS / Objective / Weights / Outlier Retraining) or a 2-column grid.
- **generate_target_opt.py:1384-1519, 1891-1943, 1781-1794 (positive — shared style + widget-builder pattern used consistently)** — for context. Nearly every tab is built through the same three helpers — `_field()` (label+entry/combobox+optional browse+optional ⓘ), `_section()` (separator+header), `_scrolled()` (canvas+scrollbar wrapper). Genuinely disciplined for a 4,460-line single-class GUI — modulo the color/font/gray inconsistencies above, the 12 tabs mostly do look like one application.

## GUI Framework Migration Plan (assessment + proposal, NOT implemented)

**Recommendation: migrate to PySide6**, keeping the existing Dash usage (`src/rmip/reduction/trim_viz.py`, `coefficient_viz.py`) scoped to what it already does well (on-demand visualization pop-outs), not expanded into the app shell.

### Why
This is a desktop-only tool for a small number of expert combustion-kinetics researchers who need: (a) validated, dense numeric forms across 12 tabs, (b) reliable long-running-subprocess progress/error surfacing with real terminal semantics, (c) long-term maintainability past the current God Object ceiling. PySide6 is the only evaluated option that structurally addresses all three simultaneously — native validated widgets (`QDoubleSpinBox`/`QSpinBox`) fix the ~30-field unvalidated-numeric-entry problem as a byproduct of porting; `QProcess` signal/slot subprocess handling replaces the current manual `os.read()`-polling + `Tk.after()`-refresh-loop architecture; and the native desktop model matches actual usage (local files/paths, no remote-access need). Options considered and rejected:

- **Dash as the app shell** — already a dependency in this repo, but its usage here is "spin up a throwaway server for one chart," not a stateful 12-tab wizard with tab-locking/autosave/PTY streaming. No native local directory picker; live ANSI/PTY streaming fights Dash's reactive-callback model built for charts, not forms.
- **NiceGUI / Streamlit** — Streamlit's full-script-rerun-per-interaction model is a poor fit for a stateful wizard with tab-locking and background jobs (effectively ruled out). NiceGUI is purpose-built for "desktop app as local web UI" but is a much smaller/less mature ecosystem, adopted for a tool with no actual multi-user/remote-access requirement to justify going web at all.
- **Stay in Tkinter, modernize via ttkbootstrap/CustomTkinter** — smallest-effort option, viable if there's no bandwidth for a large migration, but doesn't fix the structural ceiling: no real validated-numeric widgets, `Tk.after()` polling stays weaker than Qt signals for subprocess progress, and the God Object decomposition becomes extra unbundled work rather than falling out of the widget-API rewrite.

**Main risk:** ~150 entangled methods mixing UI and domain logic (worst offender: `_collect()` at line ~4233, which walks ~150 `tk.Variable` fields across every tab to assemble the config dict) — a multi-month effort for 1-2 developers. The biggest danger isn't the widget rewrite, it's silently changing numeric/scientific behavior while manually extracting logic that's currently entangled with `tk.Variable` reads (`_collect()`, `_mm_translate_and_derive_rxn`, `_write_httltt_addendum_overrides`, `_run_mechanism_reduction_multi_condition`). Mitigation is built into Phase 1 below (extract + golden-file test before any Qt code is written).

### What's already portable as-is
- Lines 890-1373: `config_to_yaml`, `generate_target_file`, `parse_target_file_species`, `generate_addendum_file`, `derive_global_reaction`, `translate_species_for_mechanism`, `convert_mechanism_files`, `generate_uncertainty_xml` — already pure, zero Tk imports.
- `FuelNormalizer`, `VariableNameMapper` (lines 56-306) — pure logic/data.
- `DEFAULT_CONFIG`, `_HELP`, `TARGET_TYPES`, `TARGET_TYPE_FIELDS`, `KNOWN_ALGORITHMS`, `ALGORITHM_TYPE_GROUPS`, `_SECTION_COMMENTS` — plain dicts.
- `TabLockingManager`, `AutoSaveManager`, `PtyTerminal` (lines 160-476, 328-439) — reusable *algorithms* (visited-set/validator-callback, dirty-flag/debounce, `pty.fork()`+`pyte` VT100 emulation) but wired to Tk APIs; port the algorithm, rewrite the glue.

Two distinct subprocess-launch patterns exist today and both need a home in the new design: (1) `_run_job`/`_open_run_dialog` (~line 5064) shells out to an *external* terminal emulator (hardcoded `gnome-terminal`/`xterm`/`konsole` fallback chain — itself a latent reliability bug, since job launch fails outright if none are installed) and polls a results CSV on a timer; (2) `PtyTerminal` is a real embedded `pty.fork()` + `pyte` terminal used in exactly one place, `_rs_run_sa_terminal` (line 3836).

### Phased plan
1. **Extract framework-agnostic core** (do regardless of final GUI choice) — move the pure functions/classes/dicts above into a new `src/rmip/gui_core/` package (no Tk imports, enforced by lint); extract embedded business logic out of `_collect()`/checkpoint read-write/`_mm_translate_and_derive_rxn`/`_run_mechanism_reduction_multi_condition` into pure functions over plain dicts/dataclasses; add golden-file regression tests (using real datasets under `DATASET/`/`MECHANISM/`) asserting the extracted functions byte-for-byte reproduce the current Tk app's `target.opt`/`.target`/`.add`/`.xml` output. This is the required safety net before any tab is ported — Large effort, but shippable incrementally without touching the running GUI.
2. **New shell/navigation skeleton** — `QMainWindow` + `QTabWidget`, 12 placeholder tabs, QSS/`qt-material` stylesheet instead of porting `PALETTE`/`FONTS` literally, port `TabLockingManager`/`AutoSaveManager` algorithms onto Qt's timer/signal primitives. Validate navigation+locking+autosave against empty stubs first. Medium effort.
3. **Port tabs in risk order**: (i) Project + Files & Paths (establishes the validated-numeric-field pattern); (ii) Mechanisms/Uncertainty XML/Addendum/Experimental Data (establishes one `QTableView`+`QAbstractTableModel` dynamic-row pattern replacing ~6 hand-rolled add/remove-row implementations); (iii) Reaction Screening (smallest PTY consumer — establishes the QProcess/pty pattern); (iv) Optimization/Run Jobs/Forward UQ (replaces the external-terminal-spawn hack and CSV-polling loop — a genuine reliability upgrade, not just parity); (v) RMIP Analysis/Reduction (thin Qt form wrapper; keep launching existing Dash viz servers via `QWebEngineView` or `webbrowser.open` rather than reimplementing them in Qt); (vi) Preview/Compile/checkpoint tabs + standalone dialogs last (mechanical `QDialog` ports; explicitly triage which are must-have parity vs. deprioritized — e.g. the Gemini-backed PDF notebook pulls in an unrelated external API dependency). Large overall, Medium-sized chunks per group.
4. **Subprocess/progress/streaming consolidation** — one framework-agnostic job-runner interface in the Phase 1 core (`start(cmd, cwd, env) -> handle` with stdout/stderr/exit callbacks) with a thin `QProcess`-signal adapter; two render modes (plain scrolling log vs. `pyte`-driven ANSI panel). Explicit design spike required (not assumed free): confirm whether any downstream tool (MSO/Cantera/MUQ-SAC) branches on `isatty()` for correctness, not just cosmetics — if so, `QProcess`'s pipe-based I/O isn't sufficient and `pty.fork()`+`QSocketNotifier` is still needed underneath. Medium effort.
5. **Cutover / parallel-run** — Tk app stays the shipped tool, unmodified, through phases 1-4; PySide6 app is a separate entry point. Because Phase 1 reuses the same generator functions, checkpoint/`target.opt`/`.target`/`.add`/`.xml` formats should be identical by construction — add a round-trip test loading a real checkpoint in both apps and diffing output. Dual-ship; have users try the new app on non-critical work first; explicitly preserve tab-locking badges/guided-tour/Next-Back placement semantics (these are functional safeguards against skipping required fields, not cosmetic). Only retire the Tk UI once all tabs have parity, round-trip tests pass, and one full real optimization run has been driven end-to-end by an actual researcher.

### Migration-specific risks
- Checkpoint/autosave format drift breaking users' in-flight `target.opt` studies — mitigated by Phase 5's round-trip diff tests.
- Silent numeric/scientific bugs introduced while manually extracting logic out of `tk.Variable`-entangled methods — mitigated by Phase 1's golden-file tests, required before Phase 3 touches any tab.
- Hardcoded developer-machine paths in `DEFAULT_CONFIG["Bin"]` (see Phase 1 code-review finding below) should be fixed as a separate, sequenced change — not bundled into the port, or output diffing becomes much harder to trust.
- `QProcess` is pipe-based, not a real pty by default — regression risk for any tool that behaves differently under `isatty()==False`; needs the Phase 4 design spike, not an assumption.
- Tab-locking/guided-tour/button-placement are functional workflow safeguards (prevent skipping required-field validation) and must be ported with equivalent *behavior*, not just equivalent appearance.
- Scope creep: ~10 standalone dialogs beyond the 12 tabs are real surface area to triage (must-port vs. deprioritize) before effort is estimated — at least one depends on an external Gemini API client unrelated to the core combustion workflow.
- Timeline realism: multi-month effort for ~150 entangled methods; the phased/parallel-run structure exists specifically so the current Tk tool remains usable throughout rather than betting the only working tool on a big-bang rewrite.

## Phase 4: Performance & effectiveness

### Legacy directories (src/MUQ-SAC, src/MUQ-SAC_EXTENDED, src/Sensitivity_Analysis, config_tools) — not covered in Phase 1

Live-wiring was checked by grepping all real entry points (`generate_target_opt.py`, `forward_uq.py`, `graph_sa_run.py`, `rmip_cli.py`, `src/rmip/**`) for references into each legacy dir — this determines which findings below are "fix it, it's live" vs. "archive it, it's dead."

- **`src/Sensitivity_Analysis/ResponseSurface.py::MatPolyFitTransform()` lines 289-311 — blocker (correctness + performance)**. Order-3/4/5 polynomial interaction-term construction uses `for j in row[row.index(i):]: for k in row[row.index(j):]: ...`, nested 3-5 levels deep, with `list.index()` (O(N) scan) as every inner loop bound — already O(N³)-O(N⁵), made worse by the scan, and **wrong** whenever two row values are equal (common when zeta samples cluster near 0), since `.index()` always returns the first match, producing duplicate monomials and an incorrect column count. This exact bug was found and fixed in the sibling file `src/MUQ-SAC/ResponseSurface.py:315-379` (explicit `range(ii, n)`-based loops, with a code comment documenting the fix: "BUG FIX (order 3, 4, 5): Original loops used row.index(value)..."). The fix was never ported to `src/Sensitivity_Analysis/ResponseSurface.py`, which is still live — wired to the GUI's "Run SA (sens_3_params.py)" button (`generate_target_opt.py` ~3850-3851) — so this bug is reachable in production for any order-3+ response-surface fit. `src/MUQ-SAC_EXTENDED/` (dead, see below) also still has the unfixed version, confirming it predates the fix and was never kept in sync.
  Fix: port the `ii/jj/kk/ll/mm` range-based loops from `src/MUQ-SAC/ResponseSurface.py` into `src/Sensitivity_Analysis/ResponseSurface.py`.
- **`Input_file_reader.py::getRxnData*/getKappa/getFocData` (near-identical duplicate at the same line numbers in `src/MUQ-SAC/`, `src/MUQ-SAC_EXTENDED/`, `src/Sensitivity_Analysis/`), ~lines 413-459 — should-fix**. `if rxn in self.rxn_index: k = self.rxn_index.index(rxn)` — a linear membership test plus a linear index lookup (2×O(N)) per call, called per-reaction inside the DesignMatrix-construction loops in `data_management.py`/`DesignMatrix.py`. Building one design-matrix row costs O(N_reactions²); the full matrix costs O(N_samples × N_reactions²) — same class of issue Phase 1 already flagged in `src/rmip/reduction/{drg,drgep,pfa}.py`.
  Fix: build `dict(zip(self.rxn_index, range(len(self.rxn_index))))` once at parse time; replace `.index()` calls with O(1) dict lookups.
- **`src/MUQ-SAC/data_management.py` lines 470/554/590 — nice-to-have**. `open("./eta_file_location.txt", "+a")` without a context manager, called per-case; relies on GC to close. Low severity, worth fixing while already touching this file for the two items above.
- **Compiled `.so` binaries (`parallel_yaml_writer.so`, `shuffle.so`, `yamlwriter.so`) duplicated 3× across `src/MUQ-SAC/`, `src/MUQ-SAC_EXTENDED/`, `src/Sensitivity_Analysis/`** — nice-to-have. Not a runtime issue, but adds build-provenance confusion; consolidating to one build location once `MUQ-SAC_EXTENDED` is archived removes two of the three copies.

## Phase 5: Architecture & maintainability

### Legacy directory duplication — ~31,000 LOC of dead/archivable code identified

| Directory | Live? (referenced by a real entry point) | LOC | Verdict |
|---|---|---|---|
| `src/MUQ-SAC/` | **Yes** — `src/rmip/simulation/muqsac_bridge.py` shells out to `run_script.py` as the official JSR/PFR/flux backend; `forward_uq.py` imports it directly; `generate_target_opt.py` hardcodes its paths/`.so` files throughout. Received a 3-way merge as recently as 2026-07-03 (8 days before this review) per `version_history/2026-07-03_muqsac_merge/MERGE_LOG.md` — actively maintained. | ~43,800 (incl. 7,509 in `bkp/`) | **Keep.** Architecturally messy (flat namespace, `.so`/`.txt` mixed with source, a stale `bkp/` subdir) but not dead. |
| `src/MUQ-SAC/bkp/` | No — pre-merge snapshots, already duplicated out-of-band under `version_history/2026-07-03_muqsac_merge/current_before_merge/` | 7,509 | **Delete** — duplicate-of-a-duplicate sitting inside the live package. |
| `src/MUQ-SAC_EXTENDED/` | **No** — zero references anywhere in the repo outside its own directory (not one of the sources folded into the 2026-07-03 merge either). File-by-file comparison shows it's an earlier/thinner fork (e.g. `data_management.py` 564 vs. MUQ-SAC's 988 lines, `make_input_file.py` 2,707 vs. 4,535), not a superset — and it still has the unfixed `ResponseSurface.py` bug described above, proving it was never kept in sync. | ~16,070 | **Archive/delete**, with a README noting "superseded by src/MUQ-SAC/, unused fork." |
| `src/Sensitivity_Analysis/` | **Yes** — `generate_target_opt.py` directly subprocess-launches `sens_3_params.py` from the GUI's SA button; `bin_sa`/`bin_sa3` config fields point at it. Confirmed a deliberate sibling fork of MUQ-SAC (merge log: "a separate, self-contained copy — deliberately untouched" during the 2026-07-03 merge), not an accidental duplicate — but it did not receive MUQ-SAC's bugfixes (see Phase 4). Independent from `src/rmip/analysis/sensitivity.py` (different purpose: mechanism-reduction sensitivity vs. Arrhenius/PRS optimization sensitivity — parallel tools, not duplicates). | ~21,900 (incl. 4,045 in `backup/`) | **Keep**, but flag for a consolidation follow-up — port MUQ-SAC's bugfixes in, or factor the shared parser/response-surface code into one location both tools import. |
| `src/Sensitivity_Analysis/backup/make_input_file.py` | No — unreferenced duplicate | 4,045 | **Delete.** |
| `config_tools/converters_io/XML2CSV/`, `config_tools/parallel_native/`, `config_tools/shared_libs/Shared_Objects/` | **Yes** — GUI's XML→target converter and Compile tab reference these directly. | ~2,800 | **Keep**, ideally renamed under a clearer `build_tools/` grouping. |
| `config_tools/converters_io/XLX2CSV/`, `data_generators/`, `examples_notebooks/`, `research/`, `shared_libs/lib_v_0.1/`, `test/` (stray `~` scratch files) | No references from any live entry point | ~3,500 | **Archive** to `legacy/config_tools_oneoffs/` with a note they were exploratory/one-off scripts. |
| `PyChemkin-master/` | Vendored — used only via `src/pychemkin_reader.py` | ~2,400 | **No action** — genuinely vendored third-party, confirmed untouched. |

**Total unambiguous dead/archivable code: ≈31,100 LOC** (`MUQ-SAC_EXTENDED` 16,070 + `MUQ-SAC/bkp` 7,509 + `Sensitivity_Analysis/backup` 4,045 + config_tools one-offs ~3,500) — roughly a third of everything scoped in this legacy-dirs pass. This is the single highest-leverage architecture cleanup in the repo: it removes an entire duplicate implementation (`MUQ-SAC_EXTENDED`) that carries a *worse*, already-fixed-elsewhere bug, with zero live callers to break.

**Broader architecture note (ties Phase 1 + Phase 4/5 together):** the repo has three independent lineages solving overlapping problems — `src/MUQ-SAC/` (legacy PRS/Arrhenius optimization engine, flat namespace, subprocess-driven), `src/Sensitivity_Analysis/` (deliberate fork of MUQ-SAC for a narrower SA use case, drifting out of sync), and `src/rmip/` (the modern, well-structured package with its own `analysis/sensitivity.py`). None of the three import each other; `generate_target_opt.py`'s `class App` is the only place that wires all three together via subprocess/path config. This explains why the `ResponseSurface.py` bugfix didn't propagate — there is no shared module for the two copies to both depend on, only copy-paste lineage.

---

## .claude-review/progress-2026-07-11.md

# Deep Codebase Review — Progress

Started: 2026-07-11
Last checkpoint: 2026-07-11 (all in-scope phases complete, synthesis written; implementation session run to ~90% usage budget, then wrapped up)
Status: REVIEW DONE, IMPLEMENTATION PARTIAL. report.md finalized (Phase 1-5 + Synthesis + GUI Migration Plan). Implementation session completed: 9 of 15 quick wins now [x] IMPLEMENTED, 6 more verified ALREADY FIXED (stale checklist), 1 (legacy dir deletion) deliberately deferred to user, plus one newly-found blocker (duplicate `_on_notebook_tab_changed` method) fixed. Full remaining backlog (structural improvements 1-7, Phase 1 should-fix/nice-to-have items, GUI migration plan) NOT started — see `/data/MECHANISM_OPTIMIZATION_SUITE/MarkDownFiles/PLAN.md` for the prioritized future plan and `/data/MECHANISM_OPTIMIZATION_SUITE/MarkDownFiles/progress.md` for the session log entry.

## Scope
- Stack: Python 3 scientific/computational suite for chemical reaction mechanism optimization (combustion kinetics). No web/desktop GUI framework found in-repo (streamlit/tkinter/PyQt/flask/dash/gradio all absent). `.rmip_gui_*.json` files and "gui_name" references in `generate_target_opt.py` refer to an *external* GUI app living outside this repo (checkpoint path points to `/data/OPEN_CODE/PHASE-3`), not code we can review here.
- Has GUI: **no** — headless CLI/library suite. Phases 2 (GUI/UX) and 3 (Aesthetics) are out of scope; noted explicitly rather than producing empty sections.
- Phases in scope: [x] code-review [ ] ~~GUI/UX~~ (N/A — no GUI in this repo) [ ] ~~aesthetics~~ (N/A) [x] performance (if turns allow) [x] architecture (if turns allow) [ ] synthesis
- Repo size: ~280 Python files tracked via Glob (not counting `__pycache__`). Primary active package `src/rmip/` alone is ~32,000 LOC across ~40+ modules. Large legacy/parallel-implementation directories also exist: `src/MUQ-SAC/`, `src/MUQ-SAC_EXTENDED/`, `src/Sensitivity_Analysis/`, vendored `PyChemkin-master/`, and `config_tools/` (many standalone utility scripts). Root also has very large orchestration scripts, notably `generate_target_opt.py` (6,052 lines) and `forward_uq.py`, `graph_sa_run.py`, `chem_data.py`, `rmip_cli.py` (thin launcher).
- No CLAUDE.md / CONTRIBUTING.md found. Some READMEs under src/modules, src/io, src/mso_compare, MarkDownFiles/README.md.
- Not a git repository (per environment info) — no git history/blame available; findings are based on static reading only.

## Prioritization decision (given huge scope + limited turns)
Given the codebase is enormous (280+ files, tens of thousands of LOC, several apparently-duplicated legacy implementations of the same subsystem), full exhaustive coverage of every file is not achievable in one pass. Priority order chosen:
1. **`src/rmip/`** — the primary, actively-structured package (has its own tests/, database/, io/, analysis/, etc.) — HIGHEST PRIORITY.
2. **Root orchestration scripts** (`rmip_cli.py`, `chem_data.py`, `forward_uq.py`, `graph_sa_run.py`, `generate_target_opt.py`, `generate_target_opt_PHASE4_FIX.py`) — these appear to be the actual entry points driving real runs.
3. **`tests/` and `conftest.py`** at repo root.
4. Lower priority / flagged but not deep-dived: `src/MUQ-SAC/`, `src/MUQ-SAC_EXTENDED/`, `src/Sensitivity_Analysis/` (look like superseded/legacy predecessors of `src/rmip/` — heavy duplication between MUQ-SAC and MUQ-SAC_EXTENDED), `PyChemkin-master/` (vendored third-party code, not reviewed), `config_tools/` (standalone one-off utility scripts).

## Phase checklist
- [x] Phase 1: Code review — DONE. Covered (every file read in full): `src/rmip/core/*`, `src/rmip/database/*`, `src/rmip/io/*`, `src/rmip/types.py`, `src/rmip/config.py`, `src/rmip/stubs.py`, `src/rmip/analysis/*` (19 modules, ~9800 LOC), `src/rmip/optimization/*`, `src/rmip/generation/*`, `src/rmip/simulation/*`, `src/rmip/reduction/*`, `src/rmip/intelligence/__init__.py` (empty stub), `src/rmip/reporting/__init__.py` (empty stub), `src/rmip/cli.py` (2168 lines), `src/rmip/__init__.py`, `generate_target_opt.py` (6052 lines, full structural read), `generate_target_opt_PHASE4_FIX.py`, `chem_data.py`, `forward_uq.py`, `graph_sa_run.py`, `rmip_cli.py`, `conftest.py`, `tests/test_forward_uq.py`, `run_forward_uq.sh`, `run_graph_sa.sh`. All blocker-severity findings spot-verified against actual source before inclusion in report.md.
- [x] Phase 2: GUI/UX — DONE (resume). Full audit of `generate_target_opt.py`'s `class App` (Tkinter, 12 tabs + ~10 dialogs) via dedicated subagent. Findings in report.md.
- [x] Phase 3: Aesthetics — DONE (resume). Same subagent pass, covering PALETTE/FONTS design-token system and where it's/isn't honored. Findings in report.md.
- [x] Phase 4: Performance & effectiveness — DONE. Covers O(N²) algorithms already found in src/rmip/reduction/{drg,drgep,pfa}.py (Phase 1), plus a dedicated legacy-dir pass (src/MUQ-SAC, MUQ-SAC_EXTENDED, Sensitivity_Analysis, config_tools) via subagent — found a live, unfixed correctness+perf bug in Sensitivity_Analysis/ResponseSurface.py that was already fixed in the sibling MUQ-SAC copy.
- [x] Phase 5: Architecture — DONE. Legacy-dir duplication quantified (~31,100 LOC dead/archivable), live-vs-dead status confirmed via grep against all real entry points. Findings in report.md.
- [x] Phase 6: Synthesis — DONE. Quick wins (15 items) and Structural improvements (7 items) written to report.md, pulling from all phases.
- [x] GUI Framework Migration Plan — DONE (user-requested addition, not a standard skill phase). Recommends PySide6, 5-phase migration plan, written to report.md. NOT implemented, per instructions.

## Currently in progress
Nothing — review is complete. report.md is finalized (Phase 1-5 + Synthesis + GUI Migration Plan). No implementation has been done, per instructions ("stop after writing report.md").

## Next step
Review is done. Remaining open item, NOT part of the skill: user asked for a version-control merge from ~/mechanism-optimization-suit (the real git repo for this package) into this folder, keeping changes made here. This is BLOCKED — that path is outside the sandboxed working directory (/data/MECHANISM_OPTIMIZATION_SUITE only, confirmed via a blocked `ls ~/mechanism-optimization-suit` even with dangerouslyDisableSandbox). Needs the user to either: grant this session access to that path, copy/rsync the git repo's contents into this folder, or run the diff/merge themselves with guidance. If resuming this review in a future session, this is the only unresolved thread — the review itself needs no further work unless the user requests changes or an implementation pass (skill §8).

## Log of resumes
- 2026-07-11: fresh run started, orientation + scoping done.
- 2026-07-11: Phase 1 completed via 4 parallel review subagents + spot-verification; findings written to report.md. Starting Phase 4/5 light pass.
- 2026-07-11 (resume, same day): User explicitly reframed scope. "The App" = `generate_target_opt.py`'s `class App` (4,460-line Tkinter GUI, 12 tabs) — this IS the primary product GUI, not out of scope. Reactivating Phase 2 (GUI/UX) and Phase 3 (Aesthetics) as full passes on this Tkinter app (previous run incorrectly marked these N/A — it only checked for web/desktop *frameworks* like streamlit/PyQt/dash and missed that generate_target_opt.py itself contains a large hand-rolled Tkinter GUI). Also added: assess whether a better GUI framework/approach exists than Tkinter, and if so produce a migration plan (in report.md, NOT implemented) to port all features from generate_target_opt.py to a new GUI. Also noted: `/data/Open_CODE/Phase-3` referenced in checkpoint paths is confirmed to be the SAME codebase as this folder (per user), not an external app — so those "external GUI" notes in old Phase 2 section are corrected/superseded.
- Separate post-review task (not part of skill, tracked here for continuity): user wants ~/mechanism-optimization-suit (the actual git repo for this package) diffed/merged into this folder afterward — keep changes made here, pull in changes from there, but do NOT push anything back into that git repo. To be done after report.md is finalized.
- Plan for this session: (a) finish Phase 4/5 light pass (legacy dir duplication + perf, was already in progress), (b) run full Phase 2/3 GUI+aesthetics audit on generate_target_opt.py's App class via subagent, (c) research GUI framework alternatives + write migration plan via subagent, (d) synthesize report.md, (e) handle git merge task separately.
- 2026-07-11 (new session, implementation pass): User asked to start implementing the quick wins listed in report.md and finish what's possible this session. Re-verified each of the 15 quick wins against the live file before touching anything — found 6 already fixed on disk (not reflected in checkboxes, presumably from an earlier untracked edit pass). Implemented the remaining 4 safe, low-risk ones this session (askyesno guard on `_clear_trows`, `foreground="gray"` → `PALETTE["text_dim"]` ×10, deleted `generate_target_opt_PHASE4_FIX.py`, mouse-wheel binding on `_scrolled`), plus fixed a newly-surfaced blocker (duplicate `_on_notebook_tab_changed` method silently shadowing the reduction-tab auto-populate handler). Deliberately did NOT delete the `src/MUQ-SAC/bkp/`/`src/Sensitivity_Analysis/backup/` legacy dirs (~11,554 LOC, quick win #13) — repo has no git, so no cheap rollback if the review's "already duplicated elsewhere" claim is stale; left for explicit user confirmation. Ran full test suite (355/355 passing, unchanged) and `ast.parse` after edits. Session hit ~90% usage budget partway through the Structural-improvements backlog (never started) — stopped per user instruction, wrote the prioritized remaining work to `MarkDownFiles/PLAN.md`, logged the session to `MarkDownFiles/progress.md`, and updated report.md's checkboxes/this file before ending.
- 2026-07-11 (follow-up session, same day): Resumed from `PLAN.md`. Implemented structural improvement #1 (ported the `ResponseSurface.py` `ii/jj/kk/ll/mm`-loop bugfix from `src/MUQ-SAC/` into `src/Sensitivity_Analysis/`, verified numerically against the review's own documented example) and the quick-win #7 residual (`_chemkin_parser.py` A_units label now uses stoichiometric-sum order, matching the already-fixed numeric-conversion path). 355/355 tests, `ast.parse` clean. User then approved `git init` (previously asked, deferred) — repo now under version control (commit `6379ace`, 754 files, large data dirs gitignored) — but explicitly declined the actual quick-win #13 deletion / structural-improvement #2 archival that git init was meant to unblock ("no need to delete anything, move to another task"). Redirected to the next-highest-priority item per `PLAN.md`'s own ordering: fixed the `analysis/unified_tree.py:504-512` KEEP_ANCHOR blocker — root cause turned out deeper than reported (anchor_mech_id was unrecoverable across the real two-process `unify-plan`/`unify-build` CLI workflow, not just wrong in an edge case), fixed via a `<manifest>.meta.json` sidecar, verified with a manual two-process repro since existing fixtures can't distinguish old/new behavior. All three changes' report.md/PLAN.md/progress.md entries updated. Remaining open items: quick win #13 and structural improvement #2 (git-safe now, but not wanted currently — don't re-propose), plus two small newly-surfaced loose ends (no regression test for the anchor fix; a pre-existing, unrelated `CanteraYAMLWriter` equation-string bug noticed during verification).

---

## .claude-review/findings-a-wip-gsa.md

# Findings A: WIP GSA code (zerork_gsa.py, gsa_prs_crosscheck.py, tests, fixtures)

Reviewer scope: src/rmip/simulation/zerork_gsa.py (incl. uncommitted off-by-one fix),
src/rmip/simulation/gsa_prs_crosscheck.py (untracked), their tests, fixture XML,
zerork_bridge.py / _salib_backend.py. Cross-checked against Zero-RK C++ sources at
/home/krithika/zero-rk. KNOWN/NEW tags vs .claude-review/report-2026-07-11.md — confirmed: the Jul 11 report never covered these untracked/uncommitted files, so ALL findings here are NEW.

## Verification of the uncommitted off-by-one fix

The fix in `_parse_gsa_output` (`rows.get(i + 1, ...)`) is **CORRECT**. Verified directly against
/home/krithika/zero-rk/applications/perturbAFactorGSA/perturbAFactor_mpi.cpp:
- line 281: `fprintf(outFilePtr,"%8d %16.7e",0,cpuTimeOrig);` — "report the unperturbed IDT calculation as task 0" (line 280 comment), written before the sample rows.
- line 289: `fprintf(outFilePtr,"%8d %16.7e",j+1,cpuTimeWorker[j]);` inside `for(j=0; j<nTask; j++)` — gsaMatrixFile row j is written as task_id j+1.
- Column layout task_id, cpu_time, idt[0..nSoln-1] confirmed (lines 281-294); `nSoln = idtTemps().size()` (idtControlParams.cpp:167), so `fields[2]` is right for the single-idtTemps request.
- Matrix format also confirmed: SequentialFileMatrixRead uses `fscanf("%d%d")` header + whitespace-separated `%lf` row-major values (src/utilities/sequential_file_matrix.cpp), so `_write_gsa_matrix`'s one-value-per-line format is fine; the app cross-checks num_columns == nRxn.
The pre-fix code did corrupt every previously computed index (Y shifted by one row vs X, last sample silently dropped); the fix and its regression tests are sound.

## Findings

- [BLOCKER][NEW] src/rmip/simulation/zerork_gsa.py:229 — Failed/non-ignition samples are NOT written as "non-positive" values as the docstring and `idt_s > 0` filter assume: perturbAFactorGSA's solver initializes `idt[j]=INFINITY` and leaves it there when no temperature root is crossed before maxTime or CVode fails (applications/perturbAFactorGSA/idtSolvers.cpp:39), and glibc `%16.7e` prints `inf`, which Python parses as `float('inf') > 0` == True. Failure scenario: any GSA batch with one non-igniting sample (low T / lean phi / maxTime=1.0 s exceeded) → `inf` enters Y as "valid", `n_failed` undercounts, `y_mean` becomes `inf`, all imputed values become `inf`, SALib returns NaN/garbage Sobol indices with no error raised. Fix: `rows[task_id] = idt_s if (idt_s > 0 and math.isfinite(idt_s)) else float("nan")` (gsa_prs_crosscheck.py inherits the fix automatically via `runner._parse_gsa_output`).

- [MAJOR][NEW] src/rmip/simulation/zerork_gsa.py:318 — `n_ranks = max(1, min(config.n_mpi_ranks, n_rows))` can legally produce 1, but perturbAFactorGSA_mpi.x is master/worker and hard-exits when `nWorker = nThread-1 < 1` ("current version does not support MPI with 0 worker threads", perturbAFactor_mpi.cpp:113-119). Failure scenario: `GSARunConfig(n_mpi_ranks=1)` → app exit(-1) → RuntimeError on every run. Also a capacity off-by-one: rank 0 does no IDT work, so useful max is n_rows+1, not n_rows. Fix: `n_ranks = max(2, min(config.n_mpi_ranks, n_rows + 1))`. Same bug duplicated at gsa_prs_crosscheck.py:432.

- [MAJOR][NEW] src/rmip/simulation/gsa_prs_crosscheck.py:587-588 — `id_of_formula = {formula: rid ...}` silently collapses duplicate `formula_string` entries (DUPLICATE-tagged reactions; GRI-3.0 mech_id=8 contains such pairs) to the last id. zerork_gsa.py:116-119 explicitly documents formula_string is non-unique and reaction_label must be used. Failure scenario: fixture XML targeting a duplicated reaction → wrong DB reaction id → wrong gsaMatrix column perturbed on the direct side while the PRS side perturbs the right one → spurious DISAGREE/AGREE with no error. Latent with the current 3-reaction H2/O2 fixture. Fix: assert uniqueness for the selected keys or key by reaction_label.

- [MAJOR][NEW] src/rmip/simulation/gsa_prs_crosscheck.py:255-259,284-286 — PRS fit can proceed with far too few training rows: `collect_training_data` requires only >= 4 converged rows, but a 3-variable order-2 "Full" PRS has 10 coefficients; `train_test_split(test_size=0.1)` on 5-15 surviving rows yields an underdetermined fit validated on 1-2 test points, which can pass the 5% MRE gate by luck. Failure scenario: n_design=16 with dropped rows → meaningless PRS marked `prs_valid=True` → AGREE/DISAGREE verdict reported as a scientific conclusion. Fix: require `len(zeta_rows) >= comb(n+2,2) + n_test + margin` before fitting.

- [MINOR][NEW] src/rmip/simulation/gsa_prs_crosscheck.py:118 — `prepare_nominal_cantera_yaml` hardcodes `ZerorkBridge(db_path, "/home/krithika/zero-rk/build2/inst_dir")`, and `run_crosscheck` (line 576-578) never forwards its own `zerork_install_dir` parameter to it. Failure scenario: caller passes a different valid install prefix → FileNotFoundError despite a correct argument. Fix: thread the parameter through.

- [MINOR][NEW] src/rmip/simulation/gsa_prs_crosscheck.py:207-211 — the `soln2ck_2.py` subprocess call has `timeout=timeout` but `subprocess.TimeoutExpired` is only caught around the later `build_idt_input/run_idt` block (216-223). Failure scenario: one hung converter row → TimeoutExpired propagates → whole cross-check aborts instead of dropping the row as designed. Fix: include the converter call in the try/except (return None).

- [MINOR][NEW] src/rmip/simulation/zerork_gsa.py:140-149 — `_salib_call` has no subprocess timeout, and reads `resp_path` blindly after rc==0: a stale `salib_<cmd>_response.json` left in the same work_dir by a previous run would be silently reused if the backend ever exits 0 without writing (and a hung venv python blocks forever). Fix: unlink resp_path before invoking; add a timeout.

- [MINOR][NEW] src/rmip/simulation/gsa_prs_crosscheck.py:589-591 — `sigma_A = cholskyDeCorrelateMat.ravel()[0]` is, for perturbation_type "factor", `min(reaction.uncertainties)` (Uncertainty.py:1940) — the minimum over the 500-2500 K grid (the 2500 K value, 0.13-0.16), not the uncertainty at the studied condition (1000 K, where the fixture says 0.27-0.35). Both sides use the same value so the comparison stays apples-to-apples, but the sampled domain understates the fixture's stated uncertainty at the simulated condition by ~2x. Fix: document, or interpolate unsrt at condition.T_K.

- [MINOR][NEW] unit ambiguity inherited by the cross-check (MechManipulator2_0.py:325-328,379) — Manipulator applies `ln A += sigma_A * zeta` (multiplier `exp(sigma*zeta)`), treating XML `<unsrt>` values (0.13-0.40, conventionally log10-based uncertainty factors) as natural-log units. If the fixture values are log10 f, the physical perturbation is understated by ln(10)≈2.3 on BOTH sides (consistent — verdict unaffected; this is why the plan's sigma_A≈0.13-0.16 vs ln2≈0.69 note matters for run_screening's factor_bound=2.0 default but not for the cross-check itself). Fix: pin the unsrt unit convention in the fixture header; if log10, convert with *ln(10) in one documented place.

- [NIT][NEW] src/rmip/simulation/zerork_gsa.py:385-447 — `with sqlite3.connect(...)` commits but never closes the connection (relies on GC); repeated calls in a long-lived process accumulate handles. Same pattern in zerork_bridge.py. Fix: contextlib.closing.

- [NIT][NEW] src/rmip/simulation/gsa_prs_crosscheck.py:157-175,288-299 — `build_design_matrix`/`fit_prs` use process-global `os.chdir` (restored in finally); unsafe if ever driven from threads. Acceptable for the standalone harness; noting for future pipeline wiring.

- [MAJOR][NEW] src/rmip/tests/test_zerork_gsa.py:209-223 (`test_parse_gsa_output_failed_sample_becomes_nan`) — the test encodes the failure value as `0.0`, but the real binary writes `inf` for non-ignition (idtSolvers.cpp:39). The test passes while the production failure path (BLOCKER above) is broken — assertion green on wrong code. Fix: add rows with `inf` / `nan` and assert they map to NaN.

- [MINOR][NEW] src/rmip/simulation/zerork_gsa.py:331-343 — mean-imputation policy for failed samples (orchestrator confirmed it triggers in real runs): substituting the batch mean into Saltelli pick-freeze rows shrinks the variance attributable to whichever reactions cause non-ignition, biasing S1/ST toward zero exactly for the influential parameters; there is no threshold guard (e.g. warn/refuse at n_failed/n_rows > ~5-10%) and `n_failed` is persisted but never checked downstream. Combined with the inf BLOCKER, today the imputed value itself is `inf`, so the policy currently never works as designed. Fix: after the inf fix, add a failure-fraction guard and consider imputing per-pick-freeze-block or reporting indices with/without imputation.

- [MINOR][NEW] src/rmip/simulation/zerork_gsa.py:307 (and gsa_prs_crosscheck.py:422) — `maxTime: 1.0` hardcoded while the equivalent IDT path (`ZerorkBridge.build_idt_input`) exposes `stop_time_s`. Low-T conditions with IDT > 1 s make every sample "fail" with no config knob. Fix: add `max_time_s` to `GSARunConfig`/crosscheck signature.

- [NIT][NEW] src/rmip/tests/test_gsa_prs_crosscheck.py:252-297 (`TestPerReactionBoundsMatchesRunScreening`) — pin compares the two implementations against each other, so any shared bug (inf handling, n_ranks floor) passes silently; guards divergence, not correctness.

(HV pseudo-species rc=134 crash and un-sanitized subprocess env / LD_LIBRARY_PATH leak: observed and logged by the orchestrator — not duplicated here.)

## Notes (verified-correct items worth recording)

- The uncommitted off-by-one fix is genuinely correct (see verification section above); its regression tests pin the right behavior.
- Manipulator A-factor math vs direct-sim domain is consistent: `MechManipulator2_0._compute_perturbed_params` does `p[lnA] += sigma_A * zeta`, writes `A = exp(p[lnA])`; the crosscheck's direct side samples ln-multipliers uniformly in `[-sigma_A, +sigma_A]` and `_build_full_matrix` exponentiates. zeta~U(-1,1) scaled by sigma == U(-sigma, sigma): identical input distributions both sides, and Sobol indices are invariant under per-variable linear rescaling — the comparison design is sound.
- `AnalyticalSobolPRS` (src/forward_uq/sobol_prs.py) assumes zeta_i ~ U(-1,1); DesignMatrix "A-facto" samples are in [-1,1] — consistent.
- `ResponseSurface.ytestMaxError` is percent; `criteria`=5.0 is percent — `compare()`'s gate is unit-consistent.
- `_all_reactions` ORDER BY id matches ChemkinWriter export order; the app validates matrix width == mechanism nRxn, so column-count mismatches fail loudly.
- SALib serialization boundary (_salib_backend.py) is clean: plain JSON lists, no dtype/endianness assumptions; sobol sample uses calc_second_order=False consistently with the analyzer.

## Suggested dynamic stress tests

1. **Confirm the inf-parsing BLOCKER (pure Python, no solver):**
   ```bash
   python3 -c "
   import sys, tempfile, pathlib; sys.path.insert(0, 'src')
   from rmip.simulation.zerork_gsa import ZerorkGSARunner
   p = pathlib.Path(tempfile.mkdtemp())/'o.dat'
   p.write_text('# hdr\n 0 1.1e-02 9.9e-03\n 1 1.2e-02 inf\n 2 1.3e-02 6.1e-03\n')
   Y = ZerorkGSARunner._parse_gsa_output(p, 2)
   print('Y =', Y)
   assert Y[0] != Y[0], 'FAIL: inf treated as valid ignition -> y_mean=inf -> Sobol garbage'"
   ```
2. **Confirm the binary emits `inf` for non-ignition** (fast, ~seconds): copy an existing GSA work dir's `gsa_input.yml`, set `maxTime: 1.0e-9`, rerun `mpiexec -n 2 .../perturbAFactorGSA_mpi.x gsa_input.yml`, then `grep -c inf gsa_output.dat` (expect > 0).
3. **Confirm the n_ranks=1 crash** (exits at MPI setup, no solve): `cd <existing work dir> && /usr/bin/mpiexec -n 1 /home/krithika/zero-rk/build2/inst_dir/bin/perturbAFactorGSA_mpi.x gsa_input.yml; echo rc=$?` — expect "does not support MPI with 0 worker threads" + nonzero rc, proving `GSARunConfig(n_mpi_ranks=1)` can never work.
4. **Duplicate-formula collision probe (read-only SQL):** `python3 -c "import sqlite3; c=sqlite3.connect('outputs/project.db'); print(c.execute('SELECT formula_string, COUNT(*) FROM reactions WHERE mechanism_id=8 GROUP BY formula_string HAVING COUNT(*)>1').fetchall())"` — any rows demonstrate gsa_prs_crosscheck.py:587's `id_of_formula` silently maps those formulas to one arbitrary id.
5. **Underdetermined-PRS false-valid probe (no solver):** loop seeds: `Z = rng.uniform(-1,1,(5,3)); Y = rng.normal(size=5)`, call `gsa_prs_crosscheck.fit_prs(list(Z), list(Y), tmpdir, criteria=5.0)` and count how often `prs.ytestMaxError <= 5.0` — any nonzero rate shows a meaningless 10-coefficient fit on ~4 training points can be marked `prs_valid=True`.

## Orchestrator confirmations (2026-07-13, executed)
- Stress test 1 EXECUTED → CONFIRMED: `_parse_gsa_output` returned `Y=[inf, 0.0061]` for an output containing a non-ignition `inf` row. BLOCKER stands.
- Stress test 3 EXECUTED → CONFIRMED: `mpiexec -n 1 perturbAFactorGSA_mpi.x` exits 255 ("Exit code: 255") — n_mpi_ranks=1 can never work; the `max(1, ...)` clamp is wrong.

---

## .claude-review/findings-b-guis.md

# Findings B — 7 standalone tkinter GUI apps + launcher + src/gui_common/ (built 2026-07-12, never reviewed)

(Persisted by orchestrator from subagent output, 2026-07-13.)

Verified-NOT-bugs (checked, do not re-flag): nominal_sim_gui.py:71 `_, cfg = load_config(...)` is a correct unpack (mso_compare/config.py:249 returns `raw, PipelineConfig(...)`; its docstring is wrong, GUI is right); uncertainty_generator_gui.py:93-100 T args align (Uncertainty.py getKappaMax/getNominal lines 1980, 2146 ignore the T argument and recompute the 3 anchors internally); all CLI flags assembled by every tab match the real argparse definitions; pyte ByteStream handles split multibyte UTF-8.

## Findings

- [BLOCKER][NEW] brute_force_sa_gui.py:236-240 — with the default relative output dir, "Run SA" always crashes FileNotFoundError at child startup: `_run_sa` writes `outputs/sa/target.opt` (relative to GUI cwd), then runs `sens_3_params.py outputs/sa/target.opt` with cwd=`outputs/sa`; sens_3_params.py:126 opens argv[1] relative to its own cwd → resolves `<gui_cwd>/outputs/sa/outputs/sa/target.opt` (doubled path). Only works with an absolute output dir. Fix: pass `str(Path(out_dir).resolve() / "target.opt")` and `cwd=str(Path(out_dir).resolve())`.
- [BLOCKER][NEW] forward_uq_gui.py:236-250 — identical doubled-relative-path crash: default out dir "outputs/forward_uq" → cmd carries relative target.opt while cwd is the same relative dir; forward_uq.py:108 open() resolves against child cwd → FileNotFoundError on every default run. Fix: resolve to absolute before building cmd.
- [MAJOR][NEW] forward_uq_gui.py:250 + forward_uq.py:339,374 — even with an absolute out dir the run can never succeed from a fresh dir: forward_uq.py hard-requires `<cwd>/Opt/` and `<cwd>/DM_FOR_PARTIAL_PRS/`; the GUI sets cwd to the freshly-mkdir'ed empty output dir → guaranteed "ERROR: Opt/ directory not found". Only workaround (out dir = project workdir) makes line 240 silently overwrite the project's own target.opt with a comment-stripped yaml.safe_dump. Fix: explicit workdir field for cwd; write GUI temp copy under a distinct name; askyesno before overwrite.
- [MAJOR][NEW] brute_force_sa_gui.py:231-234 — `cfg = dict(self._cfg)` shallow copy + `cfg.setdefault("Locations", {})["mechanism"] = override` mutates the shared nested dict: cleared override stays sticky until Reload. Fix: copy.deepcopy.
- [MAJOR][NEW] src/gui_common/pty_terminal.py:134-145 — `stop()` leaks pty master fd (`self._fd = None` without os.close) and never waitpid()s → one zombie + one fd per job across all 5 terminal-backed apps; eventually EMFILE on pty.fork(). Fix: close fd + waitpid in stop(), final reap on EOF in _read_loop.
- [MAJOR][NEW] src/gui_common/pty_terminal.py:96-105 — reader-thread restart race: old thread blocked in os.read(old fd) can wake after run() reassigns self._fd → two threads consuming one pty (interleaved/lost output); also os.read(None) → TypeError not caught by `except OSError`. Fix: capture fd/stream as locals, per-run generation token, catch (OSError, TypeError).
- [MAJOR][NEW] src/gui_common/pty_terminal.py:79 + all 5 consumer apps (rmip_suite_gui.py:124 rows=14, forward_uq_gui.py:169, brute_force_sa_gui.py:162, nominal_sim_gui.py:152, mso_compare_gui.py:145) — pyte.Screen has zero scrollback; only last 14-18 lines ever exist; a long job's traceback scrolls away irretrievably and this widget is the ONE launch mechanism (plan §1.4). Fix: pyte.HistoryScreen(history=5000) or tee raw bytes to a logfile + "Open full log".
- [MAJOR][NEW] forward_uq_gui.py:255-269 — `_poll_results` globs `out_dir/**/forward_uq_statistics.csv` from 2s after launch; stale CSV from a previous run is displayed as this run's results and the poller exits (real results never shown). Fix: only accept files with mtime > launch time.
- [MAJOR][KNOWN(Jul11 monolith generate_target_opt.py:5181-5200)] forward_uq_gui.py:256 — poll gives up silently after 60s (30×2s); real UQ runs take far longer → results box never fills, no message. Copy-pasted defect. Fix: poll until child exits (PtyTerminal knows pid) + status on give-up.
- [MAJOR][NEW] all 5 terminal apps (rmip_suite_gui.py:396-410, brute_force_sa_gui.py:258-262, …) — no WM_DELETE_WINDOW handler: closing the window SIGHUPs and silently kills a running multi-hour job, zero confirmation. Fix: root.protocol handler checking terminal._alive.
- [MINOR][NEW] src/gui_common/settings.py:34 — write_text truncate-in-place, not atomic; kill mid-write → corrupted JSON silently reset to {}. Fix: tmp + os.replace.
- [MINOR][NEW] src/gui_common/fuel_data.py:51 — alias "butene" → C4H6 (butadiene); butene is C4H8 (MW 56.108, nu_O2 6.0). Wrong species/MW/stoichiometry for any caller. Copy-pasted from generate_target_opt.py:74, never reported → NEW. Fix: butene → C4H8 entry.
- [MINOR][NEW] src/gui_common/pty_terminal.py:84-89 — child-side exec/chdir failure → os._exit(1) with no message; terminal shows empty screen. Fix: os.write(2, err) before _exit.
- [MINOR][NEW] src/gui_common/pty_terminal.py:104 vs 111-125 — pyte fed from reader thread while Tk thread walks screen.display; pyte not thread-safe → torn rows. Fix: buffer bytes under lock, feed on Tk tick.
- [MINOR][NEW] mean_value_fusion_gui.py:65 — sqlite3.connect on mistyped path CREATES empty .db then "no such table: mechanisms"; connection never closed. Fix: is_file() check / URI mode=ro + contextlib.closing.
- [MINOR][NEW] rmip_suite_gui.py:177 etc., mso_compare_gui.py:189, nominal_sim_gui.py:205, launcher_gui.py:89 — jobs launched with no cwd + relative default output dirs; launched from $HOME → outputs/ trees land under $HOME. Fix: default launch cwd to repo root.
- [MINOR][NEW] launcher_gui.py:89 — Popen handle discarded, never waited → zombie per exited app. Fix: keep handles, periodic after() reap.
- [MINOR][NEW] all 8 apps (rmip_suite_gui.py:39-41, uncertainty_generator_gui.py:42-44, …) — `sys.path.insert(0, src)` although src/io shadows stdlib io; rmip_cli.py deliberately APPENDS; works only because stdlib io is already in sys.modules. Latent order-dependent hazard contradicting repo's own rule. Fix: append.
- [MINOR][NEW] gui_common/autosave.py, variable_map.py, target_types.py, fuel_data.py imported by ZERO of the 7 apps — plan §1.4 promised per-app AutoSaveManager checkpoints; none wired; all fields reset each launch. Fix: wire AutoSaveManager or drop dead modules.
- [MINOR][NEW] rmip_suite_gui.py:388-393, mso_compare_gui.py:155-162 — remembered path saved only in Browse callback; typed/pasted paths never persisted. Fix: also save in _run/on close.
- [MINOR][NEW] uncertainty_generator_gui.py:283-284 — write_results_csv on Tk main thread in _on_done; PermissionError → console-only traceback, status stuck. Fix: try/except → messagebox + status.
- [NIT][NEW] uncertainty_generator_gui.py:275 — failed reactions put error text under "A_ub" column. Fix: dedicated error column.
- [NIT][NEW] rmip_suite_gui.py:176 — `*ids.split(",")` no strip/filter: trailing comma → int("") argparse error; "1 2" → int("1 2") error. Fix: tokenize comma/space + validate like mean_value_fusion_gui.py:256-261.
- [NIT][NEW] rmip_suite_gui.py:237 — GSA tab hardcodes /home/krithika/zero-rk/build2/inst_dir default; empty field passes `--zerork-install-prefix ""` → cryptic downstream error. Fix: validate non-empty.
- [NIT][NEW] rmip_suite_gui.py:117 — f-string without placeholder; save_settings replaces whole dict (rmip_suite_gui.py:393, mean_value_fusion_gui.py:222) dropping other keys. Fix: load-update-save merge.

## Test-coverage note
tests/test_rmip_suite_gui.py pins _build_command argv against real CLI names (good). But no test constructs the cmd+cwd PAIR — exactly where both BLOCKERs live. No test covers PtyTerminal at all.

## Suggested interactive GUI tests
1. brute_force_sa_gui: default Output dir "outputs/sa" + Run SA → FileNotFoundError doubled path in terminal.
2. brute_force_sa_gui: absolute out dir, override mech B, Run, clear override, Run → target.opt still has B.
3. forward_uq_gui: stale forward_uq_statistics.csv in out dir → shown as new run's results within 2s.
4. any terminal app: run job 15× → one zombie + one fd per run (ps --ppid; ls /proc/<pid>/fd).
5. rmip_suite_gui Reduction: command printing >50 lines then erroring → traceback scrolled away, no scrollback.
6. any terminal app: close window during long run → child SIGHUP-killed, no confirmation.
7. mean_value_fusion_gui: List mechanisms with /tmp/definitely_not_there.db → junk empty file created + wrong error.
8. rmip_suite_gui: paste (not Browse) DB path, run, restart → field empty.

---

## .claude-review/findings-c-foundation.md

# Findings — Reviewer C (foundation: core/, io/, database/, types.py, config.py, stubs.py)

Status: IN PROGRESS (flush 1). Cantera-3 dispatch blocker + cantera_writer AR-uppercase + 0.0-rate lines + undeclared-pseudo-species + `1.7+13` split + glossary-drop already logged by orchestrator — omitted here except added blast radius.

## io/cantera_reader.py — additional blast radius beyond confirmed dispatch blocker

- [BLOCKER][NEW] cantera_reader.py:209-217 — even where `_arrhenius_si` is reachable, units are kmol-based: Cantera 3 `pre_exponential_factor`/`activation_energy` return m-kmol-s SI (verified: GRI `2 O + M` gives A=1.2e11 m6/kmol2/s, not 1.2e5 m6/mol2/s) and Ea in J/kmol, while every other rmip producer/consumer (chemkin parser `_convert_to_si`, fusion, parameter_estimator) uses mol-based SI. Docstring ":214 Cantera returns J/mol" is false. Failure: fix the class dispatch alone → yaml-parsed A_si off by 1000^(order-1), Ea_si off 1000x vs chemkin-parsed → cross-source compare/fusion garbage. Fix: divide A by 1000^(order-1) and Ea by 1000 (or read `rx.input_data`, unit-explicit).
- [MAJOR][NEW] cantera_reader.py:160-206 — `A_orig`/`Ea_orig` set to the same (kmol-)SI values with `Ea_units="J/mol"`. ChemkinWriter default `use_original_units=True` emits A_orig verbatim as CHEMKIN CGS and Ea via `*1/4184` under a `CAL/MOLE` header. Failure: export any yaml-sourced mechanism → A off ~1e9 (bimolec), Ea off 1e6. Fix: leave A_orig/Ea_orig NULL for cantera source (writer then takes SI path) once the SI path itself is fixed (see writer BLOCKER below).
- [MINOR][NEW] cantera_reader.py:93-102 — `_extract_thermo` silently skips any non-NasaPoly2 species thermo (Shomate/NasaPoly1/constant-cp): species gets thermo_type NULL → ChemkinWriter `_format_nasa7` returns [] → species silently absent from THERMO block → Zero-RK/ck2yaml hard-fail. Fix: warn per species and record the unhandled type.

## io/_chemkin_parser.py (the 6 RESUME §1 fixes verified present at 337-353, 456-468, 712, 750-770, 1005-1008, 1421-1440 — new gaps below)

- [BLOCKER][NEW] _chemkin_parser.py:520-546 — DUPLICATE semantics inverted: parser treats `DUPLICATE` as marking the FOLLOWING reaction (comment at 520 says so); CHEMKIN-II spec: it is an auxiliary of the PRECEDING reaction line. Failure: standard pair `R;DUPLICATE;R';DUPLICATE` → R loses its flag, only R' flagged. Writer (chemkin_writer.py:506-511) then emits `DUPLICATE` BEFORE the flagged line, so spec-conforming consumers attach it to the previous reaction — the wrong member of each pair is marked and ck2yaml rejects the round-tripped file ("Undeclared duplicate reactions"). Fix: apply DUPLICATE to the just-collected entry; writer: emit after the reaction line.
- [MAJOR][NEW] _chemkin_parser.py:522,587 — abbreviation `DUP` (USC-Mech II, Aramco, LLNL style) not recognized at all → duplicate flag lost AND `DUP` becomes a phantom no-arrow "reaction" appended to output (empty reactants/products row in DB). Fix: accept `DUP`.
- [MAJOR][NEW] _chemkin_parser.py:750-760,785-800,772-783 + 1288-1303 — keyword joined to first value with no space after the slash (`LOW/2.3E18 -0.9 0./`, `PLOG/1.0 1.2E12 0.5 300/`, `TROE/0.68 78. 1995./`) silently drops the FIRST number: `_iter_numbers`'s first token "LOW/2.3E18" fails `_fortran_float` and the `^`-anchored fallback regex. LOW → len<3 → arrhenius_low never set → falloff exported with empty `low` = pressure dependence lost; PLOG → len<4 → whole entry dropped; TROE → params shift left. All silent. Fix: tokenize `_extract_slash_content(line)` instead of the raw line.
- [MAJOR][NEW] _chemkin_parser.py:450-470 — `REACTIONS KJOULES/MOLE` matches the `"JOULES" in upper` branch → treated as J/mol → Ea off 1000x silently. `MOLECULES` modifier (A per-molecule units) never detected → A off by ~6.022e23. Fix: check "KJOU" before "JOULES"; warn on MOLECULES/EVOLTS.
- [MAJOR][NEW] _chemkin_parser.py:662-698 + core/parser.py:328-335 + chemkin_writer.py:477-481 — bare third-body reactions (`H+O2+M=HO2+M`, no parens) parse `M` as a literal species: parser's SI conversion uses order 3 (incidentally correct), but core/parser silently drops the `M` stoichiometry row (`sp_name_to_id.get("M")` → None → `if sp_id:` skips), so the writer recomputes order=2 from stoichiometry → SI-path export multiplies A_si by 1e6 instead of 1e12 → A off 1e6 for all 50 `third_body` rows in project.db whenever A_orig is absent. Fix: strip `+M` in `_parse_species_side`, set has_third_body, never emit "M" as a species.
- [MAJOR][NEW] _chemkin_parser.py:1057-1108 vs chemkin_reader.py:303-349 vs cantera_reader.py:167-195 — three producers write the same kinetics_data keys `A_si`/`Ea_si` (low/high/PLOG entries) in three unit conventions: fallback parser = raw CGS+cal/mol; RMG path = mol-SI; cantera path = kmol-SI. chemkin_writer.py:523-578 passes them through raw assuming CHEMKIN CGS/cal (its comment at :533-537 admits the `_si` names are lies). Any RMG/cantera-sourced falloff/PLOG mechanism exports LOW/PLOG lines off by 1e6/4.184 (or 1e9/4184). Fix: standardize on true mol-SI in kinetics_data; writer converts per-sub-rate order (LOW = order+1).
- [MAJOR][NEW] chemkin_reader.py:290-300 (RMG path, latent — rmgpy not installed here) — `A_orig`/`Ea_orig` are set to `value_si` while `A_units`/`Ea_units` keep the ORIGINAL unit labels (`str(kin.A.units)`, e.g. "cm^3/(mol*s)", "cal/mol"): SI values labeled as CGS/cal. Writer's orig path then writes J/mol values under CAL/MOLE unconverted (label says cal). Fix: store `value` (original) not `value_si` for the *_orig fields.
- [MINOR][NEW] _chemkin_parser.py:712,757,797,1008 + 1481-1491 — `int(round(sum(coeffs)))` banker's-rounds fractional global-reaction orders (2.5 → 2) and `_convert_to_si` silently skips conversion for order 0 or ≥4 (`else: A_si = A` — a 4th-order reaction stores CGS A labeled SI). Fix: `A_si = A / 10**(6*(order-1))` with float order; warn outside [1,3].
- [MINOR][NEW] _chemkin_parser.py:605-616,651 — any no-arrow line (`HIGH/…/`, `FORD/H2 1.5/`, `REV/…/` without trailing space, `UNITS`, stray continuation fragment) becomes a phantom empty reaction: `_parse_reaction_equation` warns but the empty ParsedReaction is still appended and inserted into the DB (`formula_string=" <=> "`). HIGH (chemically-activated falloff) additionally loses the real high-P rate. Fix: drop entries with no parsed reactants+products; recognize HIGH/FORD enough to warn.
- [MINOR][NEW] _chemkin_parser.py:22 vs whole file — docstring claims `&` continuation support; none exists (no `&` handling anywhere). A continued reaction line yields a kinetics-less reaction plus a numbers-only phantom. Fix: join `&`-terminated lines in preprocessing or delete the claim.
- [MINOR][NEW] _chemkin_parser.py:491-501 — a blank line between a reaction and its aux lines (legal CHEMKIN) flushes the reaction early; the following LOW/TROE line fails the `entry_lines and (...)` guard at :506 and becomes a phantom primary line — pressure dependence silently lost. Fix: don't flush entries on blank lines.
- [MINOR][NEW] _chemkin_parser.py:402-408 — THERMO↔SPECIES matching is case-sensitive; an external therm.dat with different case (`h2o` vs `H2O`) creates a phantom species carrying the thermo while the declared one stays thermo-less (then silently dropped from THERMO on re-export). Fix: case-insensitive fallback lookup.
- [MINOR][NEW] _chemkin_parser.py:1033-1039 (dup at cantera_reader.py:190-194, chemkin_reader.py:317-321) — PLOG "1 atm representative" picks the FIRST entry within ±0.5 atm in file order, not the closest (0.6 atm chosen over an exact 1.0 atm later in the list). Fix: min by |P−101325| within tolerance.
- [MINOR][NEW] _chemkin_parser.py:842-850,1105-1106 — SRI falloff: only param `a` kept (as alpha), b/c/d/e discarded; writer has no SRI branch → exported as plain Arrhenius. SRI pressure dependence silently destroyed end-to-end. Fix: store all 5 params + writer SRI/ line, or refuse loudly.
- [MINOR][NEW] _chemkin_parser.py:662-698 — species names containing `+` (ions: `CH+`, `H3O+`, `E`) are split on `+`: `CH++E` → species "CH" and "E"; charge silently dropped, species mismatch vs SPECIES block. Fix: split on `+` only when followed by a letter/digit token that is a declared species, or split on ` + ` boundaries with lookahead.
- [NIT][NEW] _chemkin_parser.py:160,1306-1309 — `_species_aliases` never populated (docstring claims alias support); `_extract_numbers` dead code.

## io/chemkin_writer.py

- [BLOCKER][NEW] chemkin_writer.py:70,448,492-493 — SI-path Ea written in **kcal**/mol (`Ea_si * 1/4184`) under a header declaring `REACTIONS  CAL/MOLE` → every Ea 1000x too small. Reached whenever `A_orig` IS NULL: mechanisms produced by this suite's own fusion/optimize/unify pipelines and all 8,325 cantera_yaml reactions in outputs/project.db today. Docstring :37 says "Ea: kcal/mol (CHEMKIN convention)" — the header contradicts it. Fix: write `KCAL/MOLE` in the header or divide by 4.184.
- [MAJOR][NEW] chemkin_writer.py:484-490 — orig-units path converts only when `"J" in ea_units and "CAL" not in ea_units`; `Ea_units="kcal/mol"` or `"K"` (Kelvin) pass through numerically unchanged under CAL/MOLE → 1000x / R-factor errors. Safe today only because the fallback parser pre-normalizes to cal/mol. Fix: full unit normalization (kcal ×1000, J ÷4.184, kJ ×239.0, K ×1.987).
- [MINOR][NEW] chemkin_writer.py:666-667 — third-body `+M` patch-up condition `"M" not in rxn_str` is a substring test: any species containing letter M (`MB`, `MD` biodiesel esters) suppresses appending `+M` → efficiency line under a non-third-body equation → strict parser (Zero-RK) rejects. Fix: token-level test for `+M`.
- [MINOR][NEW] chemkin_writer.py:200 — separate-thermo path keeps the block's own "END" (`[1:-1]` drops only the trailing "") and appends another `END` → double terminator in therm.dat, same defect class as the write() duplicate-END fixed in RESUME §1. Fix: slice `[1:-2]`.
- [MINOR][NEW] chemkin_writer.py:674 — efficiency format `{eff:.3f}`: values <5e-4 (AR/1e-30/ zero-collider idiom) become `0.000`… acceptable numerically, but 6.7e-4→0.001 (49% error). Fix: `{eff:.4g}`.
- [NIT][NEW] chemkin_writer.py:88-90,450,507-510 — `_NASA7_FMT*` and `duplicates_seen` are dead code.

## core/

- [MINOR][NEW] core/canonicalize.py:80-110 — reaction canonical key (D2) ignores stoichiometric coefficients: `2 A => B` and `A => B` produce the identical key (`r_smiles` built from species names only, one entry per distinct species). Two reactions differing only in stoichiometry are conflated by compare/fusion/unify. Fix: include coefficient in the joined token (e.g. "2*SMILES").
- [MINOR][NEW] core/canonicalize.py:62-65 — no-RDKit fallback hashes the RAW smiles string for inchi_key while canonicalize() returns raw smiles: the same molecule written as `C=C` vs `C(=C)` in two glossaries gets different fake InChI keys → false UNIQUE classifications. Degradation is warned once, but the hash gives an illusion of a real key (25-char uppercase like a real InChIKey prefix). Fix: prefix fallback keys (`RAW:<hash>`) so downstream can tell.
- [MINOR][NEW] core/graph_builder.py:262-274,725-749 — duplicate reactions share canonical_key/_canon_formula, so `rx_key_to_node[i][key]` keeps only the LAST duplicate and `_assign_global_reaction_labels` gives both members of a duplicate pair the SAME global R-label → ambiguous labels in viz/reduction-target selection. Fix: suffix the key with an occurrence counter.
- [KNOWN(Jul11)][UNFIXED] core/graph_builder.py:486 — `_carbon_number` regex `r'C(\d*)'` still matches Cl/Ca/Co/Cr/Cs/Cd/Ce (layout-only impact).
- [KNOWN(Jul11)][UNFIXED] core/parser.py:348-374 — `_build_canonical_key` still returns None silently, no logging (drives the all-NULL canonical_key state of every mechanism in project.db noted in RESUME §1 item 9).
- [KNOWN(Jul11)][UNFIXED] core/parser.py:33,57 — still imports RMIPConfig despite config.py:6-9 rule.
- [MINOR][NEW] core/parser.py:137-166 — no per-mechanism transaction: mechanism row committed (schema.insert_mechanism commits) before species/reactions; a crash mid-`_insert_reactions` leaves a permanently half-loaded mechanism visible to every consumer with counts NULL. Fix: wrap parse() body in one explicit transaction and update counts before commit.
- [MINOR][NEW] core/parser.py:337-343 — third-body efficiency rows inserted with `species_id=None` for ANY name not in the mechanism (typo'd efficiency names silently accepted); combined with writer `_load_efficiencies` JOIN on species_id, these rows silently vanish on export. Fix: warn when an efficiency names an undeclared species.

## database/

- [KNOWN(Jul11)][FIXED] schema.py:250 (`rowcount`), schema_phase3.py:292 (`rowcount != 0`) — both verified fixed.
- [KNOWN(Jul11)][UNFIXED] migrations.py:563-574, 662-676 — idempotency probes still INSERT with `mechanism_id=0`; with `PRAGMA foreign_keys=ON` (set by init_db/get_connection) the FK violation raises IntegrityError regardless of the CHECK width, so the "already wide — skip" fast path can never trigger: `reduction_runs` and `simulation_runs` are renamed/rebuilt/copied/dropped on EVERY startup. `_ensure_wide_reduction_method_constraint` still catches bare `except Exception` (:572).
- [MAJOR][NEW] migrations.py:62-86,89-113,577-602 — the mechanisms-widen and reduction_runs-widen rebuild scripts are NOT wrapped in a transaction (unlike `_ensure_wide_sim_type_constraint`:702-739, which got BEGIN/COMMIT + a recovery block after a documented live incident). executescript autocommits per statement: a crash between `DROP TABLE mechanisms` and `ALTER TABLE mechanisms_new RENAME` (or between reduction_runs RENAME and CREATE) leaves the DB with no `mechanisms`/`reduction_runs` table and no recovery path. Exposure is amplified by the always-rebuild bug above (reduction_runs rebuild runs on every startup). Fix: same BEGIN TRANSACTION/COMMIT + leftover-table recovery pattern as the phase-6 function.
- [MINOR][NEW] migrations.py:596 — `INSERT INTO reduction_runs SELECT * FROM _reduction_runs_old` is column-order/count dependent (phase-6 rebuild fixed this with explicit column lists); any future ALTER on reduction_runs makes the every-startup rebuild fail mid-script (non-atomic, see above). Fix: explicit column list.
- [MINOR][NEW] schema_phase3.py:277-331 — reloading a dataset with an existing name: `insert_exp_dataset` returns the old id (correct post-fix) but `insert_exp_data_points` appends without clearing → every reload duplicates all points (n_points doubles), silently skewing MRE/RMSE weighting. Fix: delete old points (or refuse) when the dataset already exists.
- [KNOWN(Jul11)][UNFIXED] schema.py:243-248,289-294,481-487 — dynamic column names from kwargs interpolated into SQL (allow-list still absent; still not exploitable from current call sites).

## types.py / config.py

- [KNOWN(Jul11)][FIXED] types.py:882-897 — `ReductionResult.from_dict`/`load` verified back under ReductionResult; NTCReport clean.
- [KNOWN(Jul11)][UNFIXED] config.py:50-72 + types.py:93-100 — `regime_thresholds`/`LTC_MAX_K`/`NTC_MAX_K` still dead config; `SimCondition.regime()` still hardcodes 850/1000.
- [MINOR][NEW] types.py:531-537 — `TemperatureGrid.points()` accumulates `T += dT` float error over ~100 steps; with the 1e-9 guard a grid like (500, 2500, 20) is fine but dT=0.1 over large ranges drifts by >1e-9 and drops the final endpoint non-deterministically per platform. Fix: index-based generation `T_min + i*dT`.


---

## .claude-review/findings-d-analysis-sim.md

# Findings — sub-scope D: src/rmip analysis/, simulation/ (excl. zerork_gsa, gsa_prs_crosscheck), optimization/, reduction/, generation/, cli.py

Note: no in-scope file changed since Jul-11 (git log since 2026-07-11 touched only GUI apps, io/chemkin_writer.py, stubs.py), so prior findings persist; each re-verified at current line numbers. Items already reported by orchestrator (comparison.py non-canonical drop, fusion identity/NULL→0.0, cli.py:1047 _cmd_fuse, report→CWD) are not repeated.

## Findings

- [BLOCKER][NEW] src/rmip/simulation/sensitivity_runner.py:155 — `sim.sensitivity(r.T, i)` passes reactor temperature (a float, e.g. 1205.3) as the *component selector*; verified on Cantera 3.0.1 this returns `None`, then `math.isfinite(None)` (line 156) raises TypeError. Failure scenario: any `CanteraSensitivityRunner.run_idt()` call → crashes after the full integration completes; feature 100% broken. Fix: `s = sim.sensitivity('temperature', i)`.
- [MAJOR][NEW] src/rmip/analysis/fusion.py:599 (also graph_comparator.py:548, comparison.py:161, unified_tree.py:949) — reactions bucketed as `{canonical_key: row}`, but DUPLICATE reactions share one canonical_key (parser.py:348-374 keys on species SMILES only), so all but the last duplicate row silently vanish. Failure scenario: fuse/unify two mechanisms containing an `HO2+HO2=H2O2+O2` DUP pair → fused mechanism keeps only one Arrhenius channel → total rate wrong by up to ~10× at some T; comparison likewise compares an arbitrary single duplicate. Fix: key lookups on `(canonical_key, duplicate ordinal)` or aggregate duplicate rows into lists carried through fusion.
- [MAJOR][NEW] src/rmip/analysis/graph_comparator.py:429-459 — `_kinetics_are_identical` compares only A/n/Ea, never `kinetics_data_json`. Failure scenario: same falloff reaction in 2 mechs with identical high-P Arrhenius but different Troe/low-P/PLOG tables → SHARED_IDENTICAL → FusionEngine COPYs mech-1 kinetics with no divergence flag; k at low P can differ by orders of magnitude yet reads "identical". Fix: for non-arrhenius kinetics_type require canonicalized kinetics_data_json equality (else SHARED_DIVERGENT).
- [MAJOR][NEW] src/rmip/analysis/fusion.py:664-695 (same pattern unified_tree.py:566-619) — FUSE/OPTIMIZE path averages only A/n/Ea, sets `kinetics_data_json=None`, but sets `kinetics_type` by majority vote (fusion.py:675-676) / from source row (unified_tree.py:605). Failure scenario: reaction is TROE in both sources with populated A_si (high-P limit, as parser stores) → the `if not A_vals` PLOG/Troe guard (fusion.py:644) never fires → fused row says kinetics_type="troe"/"falloff" with NULL falloff data → mechanism export crashes or emits falloff reaction without falloff params. Fix: route any rxn_map containing non-arrhenius kinetics_type down the VERBATIM fallback.
- [MAJOR][NEW] src/rmip/analysis/fusion.py:892-897 — `_copy_stoichiometry` skips (log.debug only) stoich rows whose species inchi_key is absent from the fused species table (species with NULL inchi_key dropped at fusion.py:491-493). Failure scenario: one source species has no InChI → every fused reaction involving it is inserted with a missing reactant/product → mass-imbalanced fused mechanism, silently. Fix: warn and skip the whole reaction (or carry non-keyed species by name).
- [MINOR][NEW] src/rmip/analysis/fusion.py:598 vs 767 — `_fuse_reactions` keys NULL-canonical_key rows by formula_string; `_insert_reactions`' lookup keys them as `(mid, "")`; `rxn_lookup.get((src_mid, fr.canonical_key))` misses. Failure scenario: any NULL-key reaction → fused row gets metadata defaults and NO stoichiometry (`_copy_stoichiometry` returns at 878-879). Fix: use the same `or formula_string` fallback in both lookups.
- [MAJOR][KNOWN(Jul11), aggravated] src/rmip/analysis/unified_tree.py:382-385 — `zip([d for d in decisions if d.decision=="OPTIMIZE"], bands)`: bands come only from *successfully built* records with non-None band, decisions include failed ones → not mere truncation, the pairing SHIFTS: a failed OPTIMIZE decision gets the *next* reaction's uncertainty band written to reaction_decisions/uncertainty_band rows. Failure scenario: one OPTIMIZE reaction fails to build (path explicitly logged at build():309-311) → every subsequent band row in the Phase-4 audit DB is attributed to the wrong canonical_key. Fix: carry the decision inside the record and iterate records, not a parallel zip.
- [MAJOR][NEW] src/rmip/analysis/uncertainty_bands.py:419-423,471-477 — `use_cantera_for_falloff=True` is dead on Cantera 3.0.1: `ct.TroeFalloff` and `ct.ChebyshevReaction` do not exist (verified), the AttributeError is swallowed at line 384/479 → all Troe/Chebyshev contributions silently skipped, and even if constructed, `ct.Arrhenius(A_hi, n_hi, Ea_hi)` passes Ea in J/mol where Cantera expects J/kmol (and A in mol-based where Cantera is kmol-based) → k wrong by ~1000× and effectively zero activation energy. Failure scenario: `unify-build --use-cantera-falloff` → bands claim n_skipped contributions or (on older Cantera) mix kmol-based k with mol-based Arrhenius k → uncertainty factors inflated ~1000×. Fix: port to Cantera 3.x `ct.TroeRate`/`ct.ChebyshevRate` and multiply Ea×1000 / convert A to kmol.
- [MAJOR][NEW] src/rmip/simulation/base.py:168-206 — converted-YAML cache lacks atomic write: ck2yaml writes directly to final `chemkin_<hash>.yaml`; a mid-conversion crash/Ctrl-C, or the RuntimeError raise at 187-192 after a partial write, leaves a truncated file that `yaml_path.exists()` (168) reuses forever. Failure scenario: kill `rmip idt` during first conversion → every later command fails with cryptic Cantera YAML parse error until `.rmip_cantera_cache/` is manually purged. Fix: write to `*.tmp` then `os.replace()`; unlink target on exception.
- [MINOR][NEW] src/rmip/simulation/base.py:162-164 — cache key silently omits the thermo file when `thermo_path` is set but missing, and never includes the Cantera version. Failure scenario: user fixes a bad thermo path → same hash as the thermo-less conversion → stale YAML reused; Cantera upgrade → incompatible cached YAML reused. Fix: raise on missing thermo_path; add `ct.__version__` to hash_src.
- [MAJOR][NEW] src/rmip/simulation/jsr_runner.py:81-89 (same pfr_runner.py:85-93) — on `proc.returncode != 0` the runner only warns, then still parses `<work_dir>/output/*.json` and STOREs it. Failure scenario: re-run a case in an existing work_dir with a new condition; pipeline fails → stale JSON from the previous run parsed and inserted into simulation_runs tagged with the NEW condition, converged=True → silent wrong data consumed by rank/bench. Fix: delete stale output before `run()` (or skip store and return failed result when rc != 0).
- [MINOR][NEW] src/rmip/simulation/muqsac_bridge.py:250 / zerork_bridge.py:229,345 — all subprocess bridges default `timeout=None` and no CLI caller passes one. Failure scenario: hung solver (CVode stall, CHEMKIN license prompt) → `rmip jsr/pfr/flux` blocks forever. Fix: finite default (e.g. 3600 s) + surface TimeoutExpired as failed result.
- [MINOR][NEW] src/rmip/simulation/muqsac_bridge.py:174-175 — `_resolve_composition` hardcodes oxidizer species "O2". Failure scenario: `--oxidizer "N2O:1.0"` → target line `Oxidizer -- x->O2 = 0.0` with N2O in Bath_gas — physically wrong deck accepted downstream. Fix: derive oxidizer species from `condition.oxidizer` first token.
- [MINOR][NEW] src/rmip/simulation/lfs_runner.py:205-215 — `_fresh_gas` builds the flame gas with `transport=None`; FreeFlame then only works via Cantera's deprecated implicit transport fallback (DeprecationWarning verified on 3.0.1, removal announced after 3.0). Failure scenario: Cantera 3.1 upgrade → every LFS run returns converged=False. Fix: request `transport_model="mixture-averaged"` explicitly and fail fast when the mechanism lacks transport data.
- [MINOR][NEW] src/rmip/simulation/idt_runner.py:216-232 — coarse integration step is `t_end/n_steps` = 5 ms at defaults; any IDT beyond t_switch (10 ms) is quantized to that grid, and the comment "Refine around the inflection" (230-231) is not implemented. Failure scenario: NTC case with true IDT 12.3 ms → reported 10/15 ms (±20-40 %) with converged=True → regime MREs in bench/rank become resolution noise. Fix: after early-exit, re-integrate the bracketing interval with fine dt.
- [MINOR][NEW] src/rmip/analysis/benchmarking.py:258-265 — `fill_between` of experimental uncertainty over `inv_T` that is not sorted (exp points in DB order). Failure scenario: unsorted dataset → self-crossing shaded polygon garbage in every IDT plot. Fix: sort points by T before plotting.
- [MINOR][NEW] src/rmip/analysis/benchmarking.py:530-551 — `_update_ranks` ranks over ALL rows in mechanism_scores for the dataset/regime, not just `mechanism_ids` passed in. Failure scenario: earlier bench run stored scores for mech 4; new run for mechs 1-3 → stale mech-4 row participates in (and can win) the printed ranking. Fix: filter rows to the current mechanism_ids.
- [MINOR][NEW] src/rmip/simulation/performance_ranker.py:475-478 — `_load_mech_names([])` builds `IN ()` → sqlite3.OperationalError with confusing message. Failure scenario: `rank` invoked with empty mechanism list → raw SQL syntax error instead of validation message. Fix: early-return {} / validate non-empty.
- [MINOR][NEW] src/rmip/analysis/uncertainty_bands.py:293-301 — legacy `plog_rates` conversion assumes bimolecular units (`A_cgs/1e6`) for every entry. Failure scenario: unimolecular PLOG decomposition (A in 1/s) → k wrong by 1e6 in band → inflated f_uncertainty. Fix: convert using reaction order (or refuse legacy format with a warning).
- [KNOWN(Jul11)][MAJOR] src/rmip/simulation/idt_runner.py:216 — ZeroDivisionError for `n_steps < 4`; still unfixed.
- [KNOWN(Jul11)][MAJOR] src/rmip/simulation/sensitivity_runner.py:187-198 — `_estimate_T_ad` swallows all exceptions silently (fallback gas.T+1500, no log); still unfixed.
- [KNOWN(Jul11)][MAJOR] src/rmip/simulation/muqsac_bridge.py:122 — `next(iter(fuel_dict))` StopIteration on empty fuel dict after rmip.target already written (117-118); still unfixed.
- [KNOWN(Jul11)][MAJOR] src/rmip/analysis/parameter_estimator.py:188 — `np.log(A_arr)` without filtering non-positive A → -inf/NaN into MSO bounds; still unfixed (and fusion writes A_si=0.0 rows at fusion.py:632 that can feed it on a second-generation fuse).
- [KNOWN(Jul11)][MAJOR] src/rmip/analysis/fusion.py:908-912 — `_modal_value` tie-break via `max(set(values), key=values.count)` is PYTHONHASHSEED-dependent → non-reproducible fused mechanisms; still unfixed.
- [KNOWN(Jul11)][MAJOR] src/rmip/analysis/uncertainty_bands.py:351 — duplicate PLOG pressure entries → `ln_Phi - ln_Plo == 0` → uncaught ZeroDivisionError; still unfixed.
- [FIXED, verify only] unified_tree.py KEEP_ANCHOR anchor resolution (Jul-11 blocker) — confirmed fixed via `.meta.json` sidecar (unified_tree.py:975-1012).

## Findings (part 2 — cli.py, optimization/, generation/, reduction/)

- [BLOCKER][NEW] src/rmip/cli.py:1138 — `_cmd_optimize` prints `opt_result.objective_initial`, an attribute that does not exist on `OptimizationResult` (optimization/mso_interface.py:136-157; only DB migrations define that name). Failure scenario: any `rmip optimize ... --mso-tool <path>` run → AttributeError crash immediately after the (possibly hours-long) GA completes; secondary bug: `objective_final` may be None on failed runs and is formatted with `:.4f` BEFORE the status check at line 1141. Fix: check `status` first, then print `objective_final` only (guarding None).
- [BLOCKER][NEW] src/rmip/cli.py:1231-1242 vs generation/rmg_interface.py:198,205-217 — `_cmd_complete` constructs `RMGInterface(args.db, work_dir=...)` but `__init__` takes only `db_path`; then calls `generate(oxidizer=, T_list=, P_list=, phi=, rmg_exe=)` — none of these kwargs exist (signature has T_lo_K/T_hi_K/P_atm/rmg_path) — and treats the return (a Path) as a mechanism id. Failure scenario: every `rmip complete` invocation dies with TypeError before doing anything. Fix: align the CLI to the real API (generate → load_rmg_output → find_missing_pathways).
- [MAJOR][NEW] src/rmip/generation/rmg_interface.py:319-329 — `load_rmg_output` builds `MechanismParser(self._db_path)` (parser requires an RMIPConfig, core/parser.py:57) and calls `parser.parse_and_store(...)`, a method that doesn't exist (it's `parse()`, core/parser.py:67). Failure scenario: the documented "Option B: load existing RMG output" path crashes on first use. Fix: `MechanismParser(RMIPConfig(db_path=...)).parse(mech_path=..., ...)`.
- [MAJOR][NEW] src/rmip/generation/rmg_interface.py:627-641 — `_clone_if_needed` clones species without building an old→new id map, then inserts stoichiometry rows carrying the ORIGINAL `srow["species_id"]`. Failure scenario: `append_to_mechanism(..., new_name=...)` → the clone's reactions point at the BASE mechanism's species rows; graph build/export of the clone silently shows wrong or missing participants. Fix: remap species ids exactly as mso_interface.py:529-540 does.
- [MAJOR][NEW] src/rmip/reduction/drg.py:227-230 (inherited by drgep.py:86-89 and pfa/drgpsa) — retained-reaction rule keeps any reaction with `retained.intersection(sp_set)` (≥1 retained species); Lu-Law DRG requires ALL participating species retained. Failure scenario: `rmip reduce` at ε=0.3 reports e.g. "25 sp / 180 rxn" where many of those reactions reference REMOVED species — reaction counts inflated and any mechanism assembled from the step is inconsistent. Fix: `if sp_set <= retained`.
- [MINOR][NEW] src/rmip/reduction/drg.py:177 + 339-369 — `_cantera_rates` maps Cantera→DB reactions by exact `formula_string == equation` string match; unmatched reactions silently fall back to ω=1.0 in `_compute_drg_coefficients` (`rates.get(rxn_id, 1.0)`), mixing dimensionless 1.0 with real rates in mol/m³/s. Failure scenario: DB formula strings formatted differently from Cantera equations (spacing, "<=>" vs "=") → most reactions get ω=1.0, a few get ~1e-8..1e+6 → r_AB garbage with no warning. Fix: log match fraction and abort/fallback wholesale below ~90 % coverage; default unmatched to 0.0.
- [MINOR][NEW] src/rmip/cli.py:1283-1284 — `--use-original-units` is `action="store_true"` with `default=True`: the flag is a no-op and there is no way to disable original units from the CLI. Fix: use `argparse.BooleanOptionalAction` (or `--si-units` inverse flag).
- [MINOR][NEW] src/rmip/cli.py:2098-2135,2154-2194,2064-2081 — `_cmd_jsr`/`_cmd_pfr`/`_cmd_flux` return 0 even when the pipeline exited non-zero or `result.converged` is False (they just print it). Failure scenario: scripted sweeps/CI treat failed reactor runs as success. Fix: `return 0 if result.converged else 1`.
- [KNOWN(Jul11)][MAJOR] src/rmip/cli.py:61-70 — `main()` still has zero try/except around `args.func(args)`; every user error surfaces as a raw traceback. Still unfixed.
- [KNOWN(Jul11)][MAJOR] src/rmip/reduction/drg.py:291-302 — reaction-lookup tables still stored as side-effect instance attributes (`self._rxn_formula_to_species`) shared across all reducer subclasses; concurrent reuse corrupts results. Still unfixed.
- [KNOWN(Jul11)][MAJOR] src/rmip/generation/rmg_interface.py:241 — `O2_mf = fuel_mole_frac * (1-fuel_mole_frac) * 0.21 / fuel_mole_frac` still crashes (ZeroDivision) instead of validating `fuel_mole_frac == 0`. Still unfixed.
- [FIXED, verify only] cli.py:1187-1191 — Jul-11 `rank` RegimeScore-repr bug now fixed (`score.mechanism_id if score else None`).
- [FIXED, verify only] cli.py:2066-2067 — Jul-11 `flux --dry-run` exit-1 bug now fixed (`return 0 if args.dry_run else 1`).

## Findings (part 3 — benchmarking details, earlier flush addenda)

- [MINOR][NEW] src/rmip/analysis/benchmarking.py:258-265 — experimental-uncertainty `fill_between` over unsorted `inv_T` (DB row order). Failure scenario: unsorted dataset → self-crossing shaded polygon garbage in every IDT plot. Fix: sort by T first.
- [MINOR][NEW] src/rmip/analysis/benchmarking.py:530-551 — `_update_ranks` ranks over ALL mechanism_scores rows for the dataset/regime, not just the mechanisms passed to this run; stale rows from earlier benchmarks join (and can win) the printed ranking. Fix: filter to current mechanism_ids.
- [MINOR][NEW] src/rmip/simulation/performance_ranker.py:475-478 — `_load_mech_names([])` builds `IN ()` → cryptic sqlite3.OperationalError instead of a validation error. Fix: validate non-empty mechanism list in `rank()`.

---

## .claude-review/findings-e-orchestration.md

# Findings E — Root orchestration scripts + live legacy paths (persisted by orchestrator, 2026-07-13)

## generate_target_opt.py post-Jul-11 diff (a32dd64): NO regression in generate_uncertainty_xml (verified against Uncertainty.py reader).
- [MINOR][NEW] generate_target_opt.py:1368-1376 — writer emits empty <temp/>/<unsrt/> when row lacks values; Uncertainty.py:1827-1829 does None.split(",") → opaque AttributeError deep in MUQ-SAC. Fix: validate per reaction before writing.
- [NIT][NEW] generate_target_opt.py:1346 — <class> always empty.

## forward_uq script/package collision: verified SAFE at all 3 live import sites (insert-at-0 / importlib file-load / test insert). Rename script for insurance.
- [MAJOR][NEW] forward_uq.py:118-129 — unsrt.pkl cache keyed to NOTHING: stale pickle in cwd silently reused across config/mechanism/XML changes → wrong statistics/Sobol. Fix: key to hash+mtime of uncertainty XML + mechanism.
- [MINOR][KNOWN(Jul11)] forward_uq.py:154-156 min()/max() on empty targets; :45 blanket warnings-ignore; :121-128 pickle cache; :143 open() w/o context; :470 broad except in Sobol loop — all still unfixed.
- [MINOR][NEW] src/forward_uq/sobol_prs.py:71-75 — silently zero-fills missing b_ij when coeff count mismatches (stale responsecoef CSV) → wrong Sobol. Fix: assert exact length. (Sudret-2008 moments verified correct.)

## Root launchers
- [INFO] conftest/rmip_cli/graph_sa_run correctly APPEND src. [NIT][NEW] launcher_gui/forward_uq_gui/uncertainty_generator_gui/test_forward_uq insert at 0 (violates repo rule; latent). resume.sh header is stale copy-paste from another project.

## Forward UQ GUI wrappers
- [BLOCKER][NEW] forward_uq_gui.py:236-250 — cwd=out_dir but forward_uq.py hard-requires Opt/ + DM_FOR_PARTIAL_PRS/ in cwd (374-381, 260-261) and relative Locations re-resolve there → Run with defaults can never succeed; also re-dumps target.opt (comment-stripped) into out_dir. Fix: cwd = original target.opt's dir; absolute --output_dir.
- [MAJOR][NEW] forward_uq_gui.py:255-270 + generate_target_opt.py:5230 — stale forward_uq_statistics.csv picked up as new results (mtime not checked).
- [MINOR][KNOWN(Jul11)] 60s silent poll give-up re-introduced in the new app (gui:256; monolith:5228).
- [MINOR][NEW] generate_target_opt.py:5202-5207 — NamedTemporaryFile(delete=False, dir=".") never deleted; stale tmp*_target.opt in repo root right now.
- [MINOR][KNOWN(Jul11)] generate_target_opt.py:5106-5145 — _run_job needs external gnome-terminal + "; read".

## src/MUQ-SAC live path
- [MAJOR][NEW] run_script.py:458,482 — hardcoded 'python3.9' interpreter; literal '&>SA.out' as argv (no shell → bogus arg, no redirect); returncode never checked → "SA is Done!!" then FileNotFoundError sens_parameters.pkl buries real error. Fix: sys.executable, drop pseudo-redirect, check rc.
- [MAJOR][NEW] data_management.py:224-235 — same hardcoded python3.9 for per-case Cantera driver; no timeout; non-zero exit → [WARNING] then reads possibly-STALE tau.out → silently wrong eta. Fix: sys.executable, fail case on rc!=0, delete stale tau.out first.
- [MAJOR][NEW] src/MUQ-SAC/ResponseSurface.py:315-389 vs 391-421 — evaluate_prs() has NO order-3+ blocks while fit builds them: Order_of_PRS>=3 silently truncated at evaluation → systematically wrong eta. Fix: implement or hard-fail order>2.
- [MAJOR][NEW] src/Sensitivity_Analysis/ResponseSurface.py:347-375 — evaluate() still has the ORIGINAL .index() first-occurrence + slice-restart bugs for order>=3 (Jul-11 port fixed only MatPolyFitTransform) → coefficients applied to wrong monomials, silent corruption in live sens path. Fix: port ii/jj/kk/ll/mm loops into evaluate().
- [MAJOR][KNOWN(Jul11)] generate_target_opt.py:755-761 — DEFAULT_CONFIG["Bin"] dev-machine hardcoded paths still unfixed.
- [MINOR][NEW] run_script.py:12+23, simulation_manager2_0.py:38-43, DesignMatrix.py:17-18, sens_3_params.py:59-60 — sys.path.append('/parallel_yaml_writer.so') dead code; .so imports rely on script-dir rule; missing .so → bare ModuleNotFoundError, no rebuild hint.
- [MINOR][NEW] run_script.py:458,482 capture_output no timeout/streaming (hours, zero live progress); :87 cwd+argv[1] garbage for absolute paths; :102-103 unconditional Bin[samap/jpdap] KeyError for hand-written opts.

## Uncertainty collapsing conventions
- [MINOR][NEW] Uncertainty.py:1937-1940 (min over T-grid, conservative) vs uncertainty_generator_gui.py:93-116 (max over 3 anchors, anti-conservative) — OPPOSITE conventions coexist for the same XML; nothing records which convention a CSV used. Fix: document in CSV header / emit both. GUI anchor math itself verified internally consistent.
- [MINOR][NEW] uncertainty_generator_gui.py:92 + Uncertainty.py:1780-1781 — Parser(mech) runs TWICE per reaction per click → minutes of redundant parsing for big XMLs. Fix: one Parser reused.

## src/mso_compare
- [MAJOR][NEW] pipeline.py:170 + sim_runner.py:254,287 — ThreadPool (up to 6 workers) + process-global os.chdir() in each worker → cwd races silently cross-contaminate HTC/LTC/stage outputs. Fix: max_workers=1, processes, or explicit cwd args.
- [MAJOR][NEW] error_metrics.py:92-96,130-137 — NaN masked per-stage only on pred → stages that failed hardest cases look "better"; NaN in Obs → whole stage eta NaN silently. Fix: common finite mask across obs+all stages + NaN-count warning.
- [MINOR][NEW] error_metrics.py:131 — obs=0 → sigma=0 → inf/NaN eta no warning. sim_runner.py:283,294 — magic exp(...)/10.0 unit conversion duplicated, unexplained. :126 mutable default dict.

## sens_3_params.py (script side of GUI blocker)
- [MAJOR][NEW] sens_3_params.py:126,134 — argv[1] and Locations resolved against cwd (doubled-path with GUI). Fix: abspath immediately; resolve Locations against config's dir.
- [MINOR][NEW] :54-58 ruamel import fallback clobbered by PyYAML import (dead/misleading). run_script.py:480 passes rxn_list.csv argv[2] which sens_3_params never reads.

## Suggested dynamic stress tests (from agent; #5 runnable in seconds)
5. python -c "sys.path.append('src'); from mso_compare.error_metrics import compute_errors_from_df; df with Stage-1 NaNs" → Stage-1 "beats" Nominal via dropped terms.

---

## .claude-review/report.md

# Deep Codebase Review — Findings Report (fresh run 2026-07-13)

Last updated: 2026-07-13

Severity scale: BLOCKER / MAJOR / MINOR / NIT. Every finding tagged NEW or KNOWN(Jul11 §…) vs the archived report-2026-07-11.md. Blocker/Major runtime claims must carry an executed repro command.

## Quick wins
(synthesis)

## Structural improvements
(synthesis)

## Phase 0: Baseline
- 2026-07-13: `python3 -m pytest src/rmip/tests/ tests/ -q` → **481 passed, 135 warnings, 36.45s** — matches RESUME.md expectation. Tree healthy at start.
- [MINOR][NEW] src/rmip/io/cantera_writer.py:484 — baseline tests emit Cantera `NasaPoly2::validate` warnings: exported YAML has s/R and h/RT discontinuities at Tmid=1000 for species (e.g. OH low-T poly gives 20.77, high-T gives 27.68 — huge). Failure scenario: exported mechanisms are thermodynamically inconsistent at the polynomial seam; solvers may behave erratically near 1000 K. Needs investigation: writer may be emitting placeholder/wrong NASA coefficients.

## Phase 1: Code review
(findings appended as discovered)

## Phase 2: GUI & UX (interactive drive)

## Phase 2b: Dynamic stress testing

### CLI pipeline (executed 2026-07-13, throwaway DB in scratchpad)
- Happy path parse/list/summary/sparsity/visualize/report all exit 0 and produce output (FFCM1.yaml 38sp/291rx, GRI3 wetCO .inp 15sp/48rx).
- [BLOCKER][NEW] src/rmip/analysis/comparison.py:111,158 — `compare` silently excludes every species without `inchi_key` and every reaction without `canonical_key`, so results cover only the glossary-resolved subset with NO warning. Repro (executed): parse FFCM1.yaml + GRI3 wetCO with `-g species_smiles.csv` (glossary hit 28.9% / 66.7%) → compare reports universal:10, unique:{1:1,2:0} for a 38-species mechanism (27 species vanish) and 15 shared + 5/6 unique reactions out of 291/48 (~93% of reactions vanish). Scientific output is silently wrong/incomplete. Fix: include unresolved species/reactions in unique-sets keyed by raw name (or at minimum emit a coverage % line in CLI output + JSON `n_excluded` field).
- [BLOCKER][NEW] src/rmip/cli.py:156-178 + core/parser.py:70 — `parse` without `--glossary` stores NO inchi_key/canonical_key (docstring default 'species_smiles.csv' is misleading; real default None), then `compare` returns ALL ZEROS (universal:0, partial:0, unique:0/0 — arithmetically impossible) with exit 0. Repro (executed): parse both mechs without -g → `compare -m 1 2` → all-zero summary, empty comparison_report.json. Even self-compare `-m 1 1` yields zeros. Fix: compare should abort with a clear error (or huge warning) when 0% of species have canonical keys; parse should warn when glossary omitted.
- [MINOR][NEW] src/rmip/cli.py (report cmd) — `report 1 --db …` writes `mechanism_report.html` to CWD (repo root pollution); no --out option honored for the HTML. Repro (executed): file appeared at repo root. Fix: add/route --out for the HTML path.
- [MINOR][NEW] cli argparse UX — `compare 1 2` (positional, as in QUICKSTART-style usage) fails wanting `--mechs`; `visualize -o` / `sparsity -o` rejected (`--export-figure`/`--out` actual). Inconsistent arg conventions across subcommands (some positional mech ids, some --mechs). Fix: accept positional ids uniformly or fix docs.

### Adversarial CHEMKIN parser battery (executed 2026-07-13; files in scratchpad/stress/adv/)
- [BLOCKER][NEW] src/rmip/io/_chemkin_parser.py (reaction line tokenizer) — Fortran-style exponent `1.7+13` (legal CHEMKIN, common in legacy mechanisms) silently corrupts BOTH equation and rate: stored formula `H2 + O2 <=> 2 OH   1.7` and A_orig=13.0 instead of 1.7e13 — 12 orders of magnitude off, exit 0, no warning. Repro (executed): parse fortranexp.inp with `H2+O2=2OH 1.7+13 0.0 47780.`. Fix: recognize `d.d[+-]dd` Fortran floats in the Arrhenius-triple regex before splitting equation/params.
- [MAJOR][NEW] _chemkin_parser.py (species tokenizer in equations) — species names ending in `+` (declared `HO2+` in SPECIES) lose the `+` when referenced in a reaction: stored participant `HO2` (never declared). Two bugs: (a) trailing-`+` names mis-split, (b) NO referential-integrity check — reactions may reference undeclared species silently. Repro (executed): weird.inp `CH2(S)+HO2+=H2+O2` → formula `CH2(S) + HO2 <=> H2 + O2`, species table still holds `HO2+`. Fix: longest-match species-list-aware equation splitting + post-parse validation error for undeclared participants.
- [MINOR][NEW] _chemkin_parser.py — duplicate reaction without `DUPLICATE` keyword accepted silently and stored twice (CHEMKIN spec: fatal). `--check-duplicates` exists but off by default; later Cantera export of such a mechanism will fail far from the cause. Repro (executed): dupes.inp. Fix: warn by default.
- [MINOR][NEW] _chemkin_parser.py — file truncated mid-file (REACTIONS header, no body/END) parses with exit 0, 0 reactions, no "unterminated block" warning; ditto all-END-keywords-removed file. Corrupt downloads look like successful parses. Repro (executed): trunc2.inp, noend.inp. Fix: warn when a block lacks END or REACTIONS parses 0 reactions.
- [OK verified] KCAL/MOLE units line honored (Ea_si ×1000 correct); CRLF ok; tabs+inline `!` comments ok; duplicate SPECIES entries deduped; stoich coefficient 1000 accepted (no sanity bound — borderline NIT).

### Cantera-YAML ingestion + fusion (executed 2026-07-13) — WORST FINDING OF THE REVIEW
- [BLOCKER][NEW] src/rmip/io/cantera_reader.py:154-206 (`_parse_kinetics`), :221 (`_is_pdep`), :225 (`_has_third_body`) — ALL type dispatch uses `type(rx).__name__ == "ElementaryReaction"` etc., but Cantera ≥3.0 (installed: 3.0.1) removed those subclasses; every reaction is class `Reaction`. Every branch misses → fallback returns kinetics_type="reaction", A_si/n/Ea_si=None, kinetics_data={} for EVERY reaction; pressure_dependent always 0; third-body/falloff/PLOG/Chebyshev data never extracted. Repro (executed): parse MECHANISM/FFCM1/FFCM1.yaml → all 291 reactions have A_si NULL, kinetics_data_json `{}`, summary shows bogus kinetics type "reaction 291". EVERY yaml-parsed mechanism in every project DB is kinetics-hollow. Fix: dispatch on `rx.reaction_type` / `type(rx.rate).__name__` (ArrheniusRate, PlogRate, ChebyshevRate, Troe/LindemannRate) per Cantera 3 API.
- [BLOCKER][NEW] downstream silent-vacuous-success on hollow kinetics (all executed): `compare` kinetic_diffs=[] (no rate diff ever reported for yaml mechs); `report` "Rate physical bounds: 1.000 (0 flagged)" vacuously perfect; `fuse` converts NULL→0.0 and stores A_si=0.0, n=0.0, Ea_si=0.0 for every fused reaction — an exported fused mechanism has literally zero rate constants. Fix: after the reader fix, add NOT NULL guards / hard errors when fusing or scoring reactions with missing kinetics.
- [BLOCKER][NEW] src/rmip/analysis/fusion.py — fusing two IDENTICAL copies of FFCM1 (both glossary-parsed, 38sp/291rx each) yields a fused mechanism of 11 species / 20 reactions: like compare, fusion silently operates only on the glossary-resolved subset (28.9% hit) and DISCARDS 93% of the mechanism with no warning. Identity property violated catastrophically. Repro (executed): parse FFCM1.yaml twice with -g species_smiles.csv, `fuse -m 1 3` → mech 4 has 20 reactions. Fix: same as compare — unresolved reactions must pass through VERBATIM, not vanish.
- [BLOCKER][NEW] src/rmip/cli.py:1047 (`_cmd_fuse`) — every `fuse` invocation crashes with `AttributeError: 'FusionResult' object has no attribute 'n_species'` (real fields: n_species_universal/partial/unique), AFTER committing the fused mechanism but BEFORE writing union_spec.json/mso_bounds.json → fuse→optimize pipeline broken; each retry leaves an orphan mechanism row. Repro (executed). Fix: use the three real fields; write artifacts before/independently of the summary print; add a CLI smoke test (zero coverage on _cmd_fuse today).
- [MAJOR][NEW] test suite blind spot — 481 tests pass while the yaml ingestion stores no kinetics at all. No test asserts A_si/kinetics_data of a yaml-parsed reaction. Fix: add round-trip assertions (parse FFCM1.yaml → A_si of H+O2<=>O+OH ≈ known value).

### Export round-trips (executed 2026-07-13)
- [MAJOR][NEW] src/rmip/io/cantera_writer.py:179 — element inference does `el.upper()` → writes `elements: [C, H, O, N, AR]` while species composition correctly says `{Ar: 1}`; Cantera refuses to load (`element not found: AR`). ANY exported mechanism containing a two-letter element (Ar, He, Cl, Na…) is unloadable; C/H/O/N-only test mechanisms mask it. Repro (executed): parse MECHANISM/GRI3/chem_gri30_wetCO.inp → export --format yaml → ct.Solution fails. Fix: preserve canonical element symbol case (`el.capitalize()` for chemical symbols / keep original case), not .upper().
- [MAJOR][NEW] src/rmip/io/chemkin_writer.py — exporting a kinetics-hollow mechanism writes literal `0.000000E+00 0.000 0.000` Arrhenius lines for all 291 reactions with only a `! WARNING: kinetics_type=reaction` comment and log WARNING, exit 0. A user gets a syntactically valid mechanism whose every rate is zero. Fix: hard error (or --force flag) when A_si is NULL/0 for a non-explicit-zero reaction.
- [MINOR][NEW] cli export prints a Cantera-validation warning banner ("file was written but may contain issues") with the actual issue text swallowed — the banner shows asterisks but not the reason. Fix: print the caught exception text.

### ck2yaml stress sweep over MECHANISM/ (executed 2026-07-13; user-requested)
Feature gap: [MAJOR][NEW] the monolith's `convert_mechanism_files()` (generate_target_opt.py:1193 — CHEMKIN .inp+thermo+trans → Cantera YAML via ck2yaml + FlameMaster .pre via ScanMan, then DB ingest) was NOT migrated to any of the 7 standalone apps. Fix: new standalone converter GUI (built this session — see below).
Root causes reproduced for "ck2yaml breaks on a proper mechanism" (each verified on a real file in MECHANISM/):
1. Keromens chem_Keromnes2013_orig_mech_wetCO.inp:113 — Fortran exponent `4.8749+04` on a LOW line → `could not convert string to float`. (Same construct RMIP's own parser silently corrupts into A=13 — see parser battery above. ck2yaml at least fails loudly.) Auto-fixable by preprocessing regex `(\d)([+-]\d{2,3})\b` → `\1E\2`.
2. Aramco Aramco20.mech:702 — `HOCO` used in reactions but declared only via vendor `!\SUBSPECIES:` comment (AramcoMech lumping), not SPECIES → `Unexpected token "HO" in reaction expression`. Needs species-list injection or vendor preprocessor; not auto-fixable safely.
3. GLARBORG_2018_thermo.dat:1151 — thermo entry `CH3CH2NH2 Et-amin T 7/11...` written 2 columns too far right: date overflows into element field (cols 25-26 = "11") → "Error parsing elemental composition". Published file is miswritten; needs column re-alignment of the offending entries.
4. KONNOV_2019 128-957.dat:2484 — SAME miswritten entry as (3) plus CRLF line endings.
5. KONNOV_NCN_2009 .inp:73 — non-standard `REACTIONS BASE M=N2` (Konnov bath-gas notation) → "Unrecognized token on REACTIONS line". Needs token strip preprocessing.
6. SARATHY_2021 — (a) filenames contain spaces (`SMM3_Reaction mechanism.inp`) → any shell-string arg assembly breaks (GUI must use list-form subprocess); (b) after quoting: validation FAILED `Undeclared duplicate reaction H2 + M <=> H + H + M lines 55/138` → needs DUPLICATE keywords added or --no-validate + downstream awareness.
7. FFCM1.chmech + dummy.trans — partial transport file → `No transport data for species 'AR'` (user picks wrong .trans → hard fail; GUI should pre-diff species vs transport entries).
PASS with --permissive: FFCM1(.inp+.thermo+.trans), CRECK, Davis_2005, GRI3, Li_2015, nHeptane, NUIG-NGM_2010, SanDiego, SARATHY(quoted, with --no-validate).
Deliverable: NEW APP `mechanism_converter_gui.py` (repo root, registered in launcher_gui.py) — .inp+thermo+trans → YAML (ck2yaml) + .pre (ScanMan at /home/krithika/FlameMaster/Bin/bin/ScanMan) + RMIP DB ingest; list-form argv (space-safe), absolute paths, worker thread, WM_DELETE_WINDOW guard, Fortran-exponent+CRLF auto-fix. Verified end-to-end: Keromens (raw ck2yaml FAILS) converts clean through the app incl. validation PASS + DB ingest (17sp/49rx, glossary 64.7%). DB ingest deliberately uses the CHEMKIN path, not YAML (cantera_reader BLOCKER).

### Zero-RK gsa-run pipeline (executed 2026-07-13, minimal Sobol N=4, 3 reactions)
- [MAJOR][NEW] parse→export→Zero-RK chain breaks on chemiluminescence mechanisms: Keromens `OHEX<=>OH+HV` uses pseudo-species HV that the original file never declares (standard convention; ck2yaml --permissive silently drops it). RMIP parse stores the reaction with HV as participant (no referential check — see parser battery), chemkin_writer re-exports it, Zero-RK's converter hard-aborts `Syntax error: undeclared product species HV` → `gsa-run` unusable for any excited-species mechanism. Repro (executed): gsa-run on converter-ingested Keromens DB → rc=134 abort. Fix: parser option to drop/declare pseudo-species (HV, M-like tokens) with warning, mirroring ck2yaml --permissive; zerork bridge should pre-validate export.
- [MINOR][NEW] src/rmip/simulation/zerork bridge — subprocess env not sanitized: crash stack shows `/home/krithika/Desktop/ANSYS/LIB_FILES_FOR_CHEMKIN_API/libstdc++.so.6.0.28` injected into perturbAFactorGSA_mpi.x via inherited LD_LIBRARY_PATH; foreign libstdc++ can itself cause aborts. Fix: strip/normalize LD_LIBRARY_PATH for zerork subprocesses.
- [MINOR][NEW] gsa-run --reactions takes global DB row ids but help/UX suggests per-mechanism ids; error message is good, but rmip_suite_gui GSA tab gives no way to discover valid ids. Fix: accept R-labels or per-mech indices.

### Misc dynamic (executed)
- [MINOR][NEW] parse silently stores a second mechanism with an identical name on double-parse (no warn/dedup); `mechanisms` table grows ambiguous duplicates. Fix: warn + `--name` uniqueness check.
- [OK verified] paths with spaces + unicode filenames parse fine; launcher_gui buttons spawn each app as isolated subprocess (verified live).

### GUI interactive drive (executed 2026-07-13, DISPLAY :52.0, scripted driver)
- All 9 apps (8 + new converter): every button invoked with empty fields AND garbage-filled entries ("-999abcé") — ZERO uncaught exceptions; all invalid input rejected via messagebox. Widget-level validation is solid; the defects live in the launched-subprocess seams (findings-b-guis.md).
- [BLOCKER][NEW] nominal_sim_gui.py:200-205 — Run ALWAYS crashes: launches `python src/mso_compare/run_nominal_sim.py` with no cwd/PYTHONPATH; the script's sys.path[0] is src/mso_compare/ so its own `from mso_compare.config import …` (line 44) raises ModuleNotFoundError instantly. Repro (executed): `python3 src/mso_compare/run_nominal_sim.py --help` → ModuleNotFoundError. (mso_compare_gui is immune only by accident: run_mso_pipeline.py sits in src/ so the package resolves.) Third GUI whose primary action never works, alongside brute_force_sa/forward_uq doubled-path blockers (both confirmed by direct read of _run_sa: relative target_opt_path + cwd=out_dir).
- Fix: launch with env PYTHONPATH=<repo>/src (or cwd=<repo>/src… better: `[sys.executable, "-m", "mso_compare.run_nominal_sim", …]` with cwd=src) — and add a subprocess-spawn smoke test per GUI (the --no-gui tests import in-process and miss this whole class).

## Phase 3: Aesthetics & visual design

## Phase 4: Performance & effectiveness

## Phase 5: Architecture & maintainability

---

## .claude-review/progress.md

# Deep Codebase Review — Progress (FRESH RUN 2026-07-13)

Started: 2026-07-13
Last checkpoint: 2026-07-14 (synthesis complete)
Status: DONE — deliverables written to MarkDownFiles/review.md + MarkDownFiles/review_plan.md. Findings detail in findings-{a..e}-*.md + report.md (dynamic evidence). Known coverage gaps listed at the end of review.md (reviewer C: stubs.py/rest of cantera_writer; reviewer D: plog_surface/mechanism_report/missing_species_predictor/drgpsa; MUQ-SAC full PRS + crosscheck E2E not run). Deliverable code this session: mechanism_converter_gui.py (new app, user-requested), launcher_gui.py registry entry, tests/test_launcher_gui.py count 7→8. Final suite state: 481 passing (480 + updated launcher test). NO review fixes applied — that's the user's next step from review_plan.md (or ask for an implementation pass per skill §8).

Prior static-only review archived at `report-2026-07-11.md` / `progress-2026-07-11.md` in this dir.
Approved plan: /home/krithika/.claude-work/plans/do-a-deep-dive-reactive-treehouse.md
Final deliverables (synthesized from report.md at the end): `MarkDownFiles/review.md` (findings) + `MarkDownFiles/review_plan.md` (fix per finding). Tag each finding NEW or KNOWN(Jul11).

## Scope
- Stack: Python 3 combustion-kinetics suite. `src/rmip/` (~28k LOC) + `src/MUQ-SAC/` + `src/mso_compare/` + `src/forward_uq/` + 8 tkinter GUI apps at repo root + `src/gui_common/` + monolith `generate_target_opt.py` (~7k LOC).
- Has GUI: YES — 8 tkinter apps (launcher_gui, rmip_suite_gui, mean_value_fusion_gui, uncertainty_generator_gui, forward_uq_gui, brute_force_sa_gui, nominal_sim_gui, mso_compare_gui) + monolith. Real display :52.0 available; user approved full interactive drive.
- External runtime deps: Cantera 3.0.1 in-env; Zero-RK at /home/krithika/zero-rk/build2/inst_dir/bin + /usr/bin/mpiexec; SALib via /home/krithika/.venvs/salib_gsa/bin/python3 subprocess ONLY. NEVER pip install into shared anaconda env. Always launch via rmip_cli.py, never src/rmip/cli.py directly.
- Phases in scope: [ ] 0 baseline tests [ ] 1 code-review (full fresh) [ ] 2 GUI/UX (interactive drive) [ ] 3 aesthetics (light — tkinter) [ ] 4 performance [ ] 5 architecture [ ] 2b DYNAMIC STRESS TESTING (custom phase per plan: CLI/adversarial parser/fusion/DB/Cantera light paths + bounded heavy Zero-RK/GSA/crosscheck/MUQ-SAC under timeout 10-15min) [ ] 6 synthesis → review.md + review_plan.md

## Phase checklist
- [x] Phase 0: Baseline — 481 passed, 135 warnings, 36.45s. Healthy. (Also logged MINOR: cantera_writer NasaPoly2 Tmid discontinuity warnings.)
- [ ] Phase 1: Code review — 5 subagents launched (a WIP-GSA, b GUIs, c foundation, d analysis/sim/cli, e orchestration+MUQ-SAC) but ALL KILLED by session usage limit (resets 11am Asia/Kolkata) BEFORE writing any findings-*.md files. MUST RELAUNCH all 5 with same prompts (each writes .claude-review/findings-{a..e}-*.md incrementally). Agent c's dying words confirmed the Cantera-3 Reaction-class bug (now independently verified + logged in report.md by orchestrator).
- [ ] Phase 2: GUI/UX interactive drive — not started
- [~] Phase 2b: Dynamic stress testing — IN PROGRESS by orchestrator. DONE: CLI happy path; compare all-zeros + silent-subset BLOCKERs; report.html CWD pollution; adversarial parser battery (Fortran-exponent 12-orders corruption BLOCKER, HO2+ trailing-plus MAJOR, dup-reaction + truncation MINORs); cantera_reader Cantera-3 hollow-kinetics BLOCKER cluster; fusion identity-violation BLOCKER; cli fuse AttributeError BLOCKER. Scratch DBs: scratchpad/stress/{t.db,t2.db,adv/adv.db}. TODO: DB double-parse dup handling; path-with-spaces/unicode; export round-trip (chemkin→yaml→ct.Solution); nominal Cantera IDT via nominal_sim code path; uncertainty XML tiny case; bounded-heavy (Zero-RK IDT 1-cond, gsa-run minimal via cli gsa-run, crosscheck stages, MUQ-SAC design-matrix) each under timeout 900.
- [ ] Phase 3: Aesthetics — not started
- [ ] Phase 4: Performance — not started
- [ ] Phase 5: Architecture — not started (Jul-11 report §5 largely still applies; verify + delta)
- [ ] Phase 6: Synthesis → MarkDownFiles/review.md + review_plan.md — not started

## Currently in progress
Phase 1: agents a/c/d/e resumed after 5pm IST reset (b=GUIs DONE → findings-b-guis.md). Phase 2 GUI drive DONE: all 9 apps (incl. new mechanism_converter_gui) button-mashed empty+garbage via scripted driver — ZERO uncaught exceptions, all errors via messagebox. brute_force_sa doubled-path BLOCKER + shallow-copy MAJOR confirmed by direct read of _run_sa. Phase 2b mostly DONE: see report.md (compare/fusion/cantera_reader BLOCKER cluster, parser battery, export round-trips, ck2yaml sweep incl. 7 root causes, gsa-run E2E pass on GRI-wetCO + HV-abort MAJOR).
USER SCOPE ADDITION (2026-07-13, delivered): built mechanism_converter_gui.py (repo root, in launcher) — CHEMKIN→YAML/.pre/DB with Fortran-exp+CRLF auto-fix; verified E2E on Keromens.

## Next step
When agents a/c/d/e finish: merge findings-*.md into report.md, run synthesis, write MarkDownFiles/review.md + MarkDownFiles/review_plan.md. Remaining optional dynamic: nominal-sim dry-run, MUQ-SAC design-matrix stage, crosscheck stage functions (skip if budget tight — core seams already exercised).

## Log of resumes
- 2026-07-13: fresh run started; archived Jul-11 state; baseline tests launched.
- 2026-07-13 ~06:15: session usage limit killed all 5 Phase-1 agents mid-read (no findings files written). Orchestrator continued Phase 2b after limit relaxed; major BLOCKER cluster found and logged (see report.md Phase 2b).

---

