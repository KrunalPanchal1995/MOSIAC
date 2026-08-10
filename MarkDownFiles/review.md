# Deep Review + Stress Test — Findings (2026-07-13/14)

Method: fresh static review (5 parallel reviewers) + **first-ever dynamic stress pass** — CLI pipelines run with real + adversarial inputs, Zero-RK/SALib/mpiexec seams exercised, all 9 GUIs launched and button-mashed on DISPLAY :52.0 with empty/garbage inputs. Baseline before testing: **481 tests passed** (matches RESUME.md). Every finding marked **(EXEC)** was reproduced by actually running code; line numbers verified this session.
Detail files (consolidated 2026-07-22 from `.claude-review/` into one archive, same content): `MarkDownFiles/REVIEW_EVIDENCE_ARCHIVE.md` -- sections "report.md" (dynamic evidence) and "findings-{a..e}-*.md" (per-area static detail). Fixes for every ID: `MarkDownFiles/review_plan.md`.
Prior static review: same archive, section "report-2026-07-11.md". Tags: NEW vs KNOWN(Jul11).

---

## BLOCKERS (wrong science or 100%-broken features)

**B1. Cantera-3 reader stores NO kinetics for any YAML mechanism** — `src/rmip/io/cantera_reader.py:154-206` (EXEC, NEW)
`_parse_kinetics` dispatches on class names (`ElementaryReaction`…) that Cantera ≥3.0 removed; every reaction falls through → `A_si/n/Ea_si=NULL`, `kinetics_data={}`, `pressure_dependent=0`; `_is_pdep`/`_has_third_body` (:221,:225) always False. Verified: FFCM1.yaml → all 291 reactions hollow. **Every yaml-parsed mechanism in every project DB is affected.** Downstream "succeeds" vacuously: `compare` kinetic_diffs=[], `report` rate-bounds score 1.000, `fuse` writes literal 0.0 rates.

**B2. Even after B1 is fixed, YAML-read units are kmol-based while the rest of the suite is mol-based** — `cantera_reader.py:209-217` (NEW)
Cantera 3 returns m-kmol-s + J/kmol; chemkin parser/fusion/estimator use mol-SI. A off 1000^(order−1), Ea off 1000×. Also `A_orig/Ea_orig` get SI values labeled as original units (:160-206) → CHEMKIN export off ~1e9.

**B3. `compare` silently drops everything not glossary-resolved; without a glossary it returns all-zeros with exit 0** — `src/rmip/analysis/comparison.py:111,158` (EXEC, NEW)
With glossary (FFCM1 hit=28.9%): 27/38 species and ~93% of reactions vanish from the report, no warning. Without: universal=0, unique=0/0 (arithmetically impossible), exit 0. Even self-compare returns zeros.

**B4. Fusion violates identity and destroys data** — `src/rmip/analysis/fusion.py` (EXEC, NEW)
Fusing two identical FFCM1 copies → 11/38 species, 20/291 reactions (same silent glossary-subset drop), and NULL kinetics become **A_si=0.0** in the fused rows.

**B5. `fuse` CLI crashes on every invocation** — `src/rmip/cli.py:1047` (EXEC, NEW)
`fusion_result.n_species` doesn't exist (real: `n_species_universal/partial/unique`) → AttributeError AFTER committing the fused mechanism, BEFORE writing union_spec.json/mso_bounds.json → fuse→optimize pipeline dead; each retry leaves an orphan DB row.

**B6. CHEMKIN parser silently corrupts Fortran-exponent rates** — `src/rmip/io/_chemkin_parser.py` reaction tokenizer (EXEC, NEW)
`1.7+13` (legal CHEMKIN, common in legacy files) → equation stored as `H2 + O2 <=> 2 OH   1.7`, **A=13.0 instead of 1.7e13** — 12 orders of magnitude, exit 0. (ck2yaml at least fails loudly on the same construct — Keromens line 113.)

**B7. DUPLICATE semantics inverted end-to-end** — `_chemkin_parser.py:520-546` + `chemkin_writer.py:506-511` (NEW)
Parser attaches `DUPLICATE` to the *following* reaction (spec: preceding); writer emits it *before* the line. Round-tripped files mark the wrong member of each pair; ck2yaml rejects. `DUP` abbreviation not recognized at all (becomes a phantom empty reaction row).

**B8. Cantera sensitivity runner 100% broken** — `src/rmip/simulation/sensitivity_runner.py:155` (NEW)
`sim.sensitivity(r.T, i)` passes the temperature *float* as component selector → returns None → `math.isfinite(None)` TypeError after full integration. Fix is one token: `'temperature'`.

**B9. `optimize` CLI crashes after the GA finishes** — `src/rmip/cli.py:1138` (NEW)
`opt_result.objective_initial` doesn't exist on OptimizationResult; also `objective_final:.4f` formats None before the status check. Hours of GA → AttributeError.

**B10. `complete` CLI never worked** — `cli.py:1231-1242` vs `generation/rmg_interface.py:198+` (NEW)
Constructor kwarg and every `generate()` kwarg mismatched with the real API; return value (a Path) treated as mechanism id → TypeError on any invocation. Related: `load_rmg_output` calls nonexistent `parse_and_store` (rmg_interface.py:319-329).

**B11. GSA: non-ignition samples poison every Sobol/Morris index** — `src/rmip/simulation/zerork_gsa.py:229` (EXEC, NEW)
Zero-RK writes `inf` for non-ignition; code checks `idt_s > 0` (assumes "non-positive") so `inf` passes as valid → mean-imputation propagates inf/garbage into all indices with no error. Confirmed: `_parse_gsa_output` returned `[inf, 0.0061]` on an inf row. (The uncommitted off-by-one fix itself was verified CORRECT against the Zero-RK source.)

**B12. brute_force_sa_gui "Run SA" always crashes with defaults** — `brute_force_sa_gui.py:236-240` + `sens_3_params.py:126` (confirmed by direct read, NEW)
Relative `outputs/sa/target.opt` passed as argv while `cwd=outputs/sa` → child resolves `outputs/sa/outputs/sa/target.opt`.

**B13. forward_uq_gui "Run" can essentially never succeed** — `forward_uq_gui.py:236-250` + `forward_uq.py:108,374-381` (NEW)
Same doubled-relative-path crash with defaults; with an absolute out dir, forward_uq.py hard-requires `Opt/` + `DM_FOR_PARTIAL_PRS/` in cwd (a fresh empty dir) → guaranteed failure; the only workaround silently overwrites the project's own target.opt comment-stripped.

**B14. nominal_sim_gui "Run" always crashes** — `nominal_sim_gui.py:200-205` (EXEC, NEW)
Launches `src/mso_compare/run_nominal_sim.py` with no PYTHONPATH/cwd; script's sys.path[0] is the package dir itself → `ModuleNotFoundError: mso_compare` instantly. (mso_compare_gui survives only because run_mso_pipeline.py happens to sit in `src/`.)

**B15. CHEMKIN writer SI path writes Ea in kcal under a CAL/MOLE header** — `chemkin_writer.py:70,448,492-493` (NEW)
Every Ea 1000× too small whenever `A_orig` IS NULL — which today means all fusion/optimize/unify products and all yaml-sourced rows.

---

## MAJOR (silent wrong results, broken flows)

Parser/writer/IO:
- M1 `_chemkin_parser.py` equation tokenizer eats trailing `+` of ion species (`HO2+`→`HO2`) and accepts undeclared participants with no referential check (EXEC). Blast radius: Keromens `OHEX<=>OH+HV` ingests, exports, then **Zero-RK aborts rc=134 → gsa-run unusable for chemiluminescence mechanisms** (EXEC).
- M2 `_chemkin_parser.py:750-800,1288-1303` — `LOW/2.3E18…` (no space after slash) silently drops the first number → falloff/PLOG/TROE data lost or shifted.
- M3 `_chemkin_parser.py:450-470` — `KJOULES/MOLE` matched as JOULES (Ea 1000× off); `MOLECULES` modifier ignored (A off by 6e23).
- M4 `_chemkin_parser.py:662-698` + `core/parser.py:328-335` + writer — bare `+M` third bodies: M stored as species then dropped → order miscomputed → A off 1e6 on SI-path export (50 rows in project.db).
- M5 kinetics_data `A_si/Ea_si` written in 3 different unit conventions by the 3 readers; writer assumes CGS/cal → falloff/PLOG exports off 1e6-1e9 for RMG/cantera-sourced mechs (`_chemkin_parser.py:1057-1108`, `chemkin_reader.py:290-349`, `cantera_reader.py:167-195`).
- M6 `cantera_writer.py:179` — `el.upper()` → `elements: [AR]` vs composition `{Ar: 1}` → **exported YAML unloadable for any mechanism with 2-letter elements** (EXEC: GRI-wetCO round trip fails `element not found: AR`).
- M7 `chemkin_writer.py` exports hollow mechanisms as all-`0.000000E+00` Arrhenius lines, exit 0 (EXEC).
- M8 `cantera_reader.py:93-102` — non-NasaPoly2 thermo silently skipped → species absent from THERMO on export → solvers hard-fail. Baseline tests also show writer emits h/s discontinuities at Tmid (cantera_writer.py:484 warnings — investigate together).

Analysis/fusion/reduction/CLI:
- M9 duplicate reactions share one canonical_key → `{key: row}` maps keep only the last: fusion/comparison/unified_tree/graph_comparator silently drop channels (fusion.py:599, comparison.py:161, unified_tree.py:949, graph_comparator.py:548); crosscheck's `{formula: id}` has the same collision (gsa_prs_crosscheck.py:587).
- M10 `graph_comparator.py:429-459` — kinetics equality compares A/n/Ea only, never falloff/PLOG tables → "SHARED_IDENTICAL" for reactions differing by orders of magnitude at low P.
- M11 `fusion.py:664-695` (and unified_tree.py:566-619) — FUSE averages A/n/Ea but nulls kinetics_data while keeping kinetics_type="troe" → falloff reaction without falloff params on export.
- M12 `fusion.py:892-897` + :491-493 — species without InChI dropped from fused stoichiometry → mass-imbalanced fused mechanisms, silently.
- M13 `unified_tree.py:382-385` — decisions↔bands zip SHIFTS after any failed OPTIMIZE build → uncertainty bands attributed to wrong reactions in the audit DB (KNOWN Jul11, aggravated).
- M14 `uncertainty_bands.py:419-477` — Cantera-2 class names again (`ct.TroeFalloff`) + J/mol-vs-J/kmol mixup → falloff contributions silently skipped or k off ~1000×.
- M15 `reduction/drg.py:227-230` — keeps reactions with ≥1 retained species (Lu-Law requires ALL) → inflated, inconsistent reductions; also ω=1.0 fallback for unmatched reactions (:177,339-369).
- M16 `cli.py` jsr/pfr/flux return 0 on failed/unconverged runs (:2064-2194); `main()` has no error handling (KNOWN).
- M17 `migrations.py:62-113,577-602` — table-rebuild scripts not transactional (DROP…RENAME window can destroy `mechanisms`); amplified by the every-startup rebuild bug (:563-574 FK-violating idempotency probe). `schema_phase3.py:277-331` dataset reload duplicates all data points.

Simulation/GSA/MUQ-SAC/mso_compare:
- M18 `zerork_gsa.py:318` (+crosscheck:432) — `max(1, min(...))` allows n_mpi_ranks=1 which Zero-RK always rejects (EXEC: exit 255); mean-imputation biases S1/ST toward zero for the failing reactions (no threshold guard).
- M19 `gsa_prs_crosscheck.py` — PRS fit gate accepts ≥4 rows for a 10-coefficient order-2 fit validated on 1-2 points → meaningless AGREE/DISAGREE verdicts; `_salib_call` no timeout, can reuse stale JSON; test encodes failure as 0.0 so the inf path stays green (test_zerork_gsa.py:209).
- M20 `simulation/base.py:162-206` — Cantera-conversion cache: non-atomic write (truncated YAML cached forever) + hash omits missing thermo path and Cantera version → stale/corrupt cache reuse.
- M21 `jsr_runner.py:81-89` / `pfr_runner.py:85-93` — on rc≠0 still parses stale output JSON and stores it converged=True under the new condition.
- M22 MUQ-SAC `run_script.py:458,482` + `data_management.py:224-235` — hardcoded `python3.9`; literal `'&>SA.out'` argv; returncode unchecked ("SA Done!!" then missing-pickle crash); per-case failures read stale `tau.out` → silently wrong η.
- M23 `MUQ-SAC/ResponseSurface.py:391-421` — `evaluate_prs` has no order≥3 terms while fit builds them → Order_of_PRS:3 silently truncated. `Sensitivity_Analysis/ResponseSurface.py:347-375` — `evaluate()` still has the original `.index()`/slice bugs for order≥3 (only the fit half was ported on Jul-11).
- M24 `mso_compare/pipeline.py:170` + `sim_runner.py:254,287` — ThreadPool × process-global `os.chdir()` → cwd races cross-contaminate HTC/LTC/stage outputs.
- M25 `mso_compare/error_metrics.py:92-137` — per-stage NaN masking makes χ² non-comparable (failed-hardest-cases stage "wins"); NaN in Obs → stage ε NaN silently.
- M26 `forward_uq.py:118-129` — `unsrt.pkl` cache keyed to nothing → stale uncertainties silently reused across config changes. Stale-CSV result pickup in both pollers (forward_uq_gui.py:255-270, monolith:5230).
- M27 GUI subprocess seams (findings-b): PtyTerminal leaks fd+zombie per job (pty_terminal.py:134-145), reader-thread restart race (:96-105), zero scrollback (pyte.Screen at 14-18 rows) for the ONE launch mechanism, no WM_DELETE_WINDOW guard anywhere (multi-hour jobs killed silently), brute_force_sa shallow-copy makes mech override sticky (:231-234).
- M28 monolith `generate_target_opt.py:755-761` DEFAULT_CONFIG["Bin"] dev-machine paths (KNOWN, unfixed).
- M29 Feature gap (user-reported, EXEC): the monolith's CHEMKIN→YAML/.pre/DB conversion GUI was never migrated. **Delivered this session: `mechanism_converter_gui.py`** (+ launcher entry) with Fortran-exponent/CRLF auto-fix; verified end-to-end on Keromens. ck2yaml failure taxonomy (7 reproduced root causes) in `MarkDownFiles/REVIEW_EVIDENCE_ARCHIVE.md`, "report.md" section, §ck2yaml.

---

## MINOR (selected; full lists in findings files)

- Parser: truncated/END-less files parse silently; dup reactions accepted without DUPLICATE (EXEC); blank line flushes aux data (pressure dependence lost); case-sensitive THERMO matching; SRI falloff destroyed end-to-end; PLOG 1-atm pick takes first-in-window not closest; fractional orders rounded; `&` continuation claimed but unimplemented; phantom empty reactions from no-arrow lines.
- `report` CLI writes mechanism_report.html to CWD (EXEC); argparse conventions inconsistent across subcommands (EXEC); `--use-original-units` flag is a no-op (default True + store_true).
- `canonicalize.py` ignores stoichiometric coefficients in keys (`2A→B` ≡ `A→B`); no-RDKit fallback fabricates InChI-lookalike keys; duplicate pairs share one global R-label.
- `core/parser.py`: no per-mechanism transaction (half-loaded mechanisms persist); double-parse of same name silently duplicates (EXEC); typo'd third-body efficiency names silently vanish.
- Simulation: subprocess bridges default timeout=None; muqsac_bridge hardcodes oxidizer "O2"; LFS relies on deprecated implicit transport (breaks on Cantera 3.1); IDT coarse-grid quantization ±20-40% beyond 10 ms with no refinement; zerork env not sanitized (ANSYS libstdc++ leaked into MPI subprocess — observed in crash stack, EXEC).
- Uncertainty conventions: Uncertainty.py uses min-over-T (conservative) vs uncertainty_generator_gui max-over-anchors (anti-conservative) for the same XML — nothing records which convention a CSV used; Parser runs twice per reaction per click.
- gui_common: settings write not atomic; "butene"→C4H6 alias wrong (butadiene); sqlite connect creates junk DB file on typo'd path; relative output dirs resolve against launch cwd; autosave modules dead (plan promised per-app checkpoints); `sys.path.insert(0,src)` violates repo's own append rule in all 8 apps.
- forward_uq: 60s silent poll give-up (KNOWN, copy-pasted into new app); sobol_prs zero-fills mismatched coefficient vectors; empty-target min()/max() ValueError (KNOWN).
- benchmarking: fill_between over unsorted inv_T; rankings include stale rows from previous runs; `IN ()` SQL error on empty rank list.
- monolith: `<temp/>` empty-element XML → None.split crash deep in MUQ-SAC; NamedTemporaryFile(delete=False) litter (present in repo root now).

## Verified-OK (so you don't chase ghosts)
481-test baseline green; KCAL/CRLF/tab/comment parsing correct; spaces/unicode paths fine; launcher crash-isolation works; **gsa-run works end-to-end on a clean mechanism** (Sobol via mpiexec, physically sensible indices — EXEC); the uncommitted `_parse_gsa_output` off-by-one fix is CORRECT; Manipulator-vs-GSA sampling domains match; forward_uq script/package collision handled at all live import sites; nominal_sim `_, cfg = load_config()` unpack correct; all GUI-assembled CLI flags match real argparse definitions; GUI widget-level validation solid (9 apps × empty+garbage drive → zero uncaught exceptions, EXEC); post-Jul-11 `generate_uncertainty_xml` diff has no regression; Sudret-2008 Sobol moment math correct.

## Coverage gaps (honest accounting)
Reviewer C didn't finish stubs.py FusionEngine math + rest of cantera_writer; reviewer D didn't finish plog_surface/mechanism_report/missing_species_predictor/drgpsa. MUQ-SAC full PRS optimization and the crosscheck end-to-end were not run (bounded-heavy budget); design-matrix stage untested dynamically. Session usage limits killed agents twice; everything else was re-verified after resume.
