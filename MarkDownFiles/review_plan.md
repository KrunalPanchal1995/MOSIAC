# Review Fix Plan (companion to review.md, 2026-07-14)

IDs match review.md. Ordered by suggested attack sequence, not severity alone — early phases unblock later verification. After each phase: `python3 -m pytest src/rmip/tests/ tests/ -q` must stay ≥481 passing, plus the new tests added in that phase.

## Phase 0 — one-line/dead-simple crashes (do first; each ~minutes, zero risk)
- **B5** cli.py:1047 — replace `n_species` with the 3 real fields; move `export_union_spec`/`export_mso_bounds` BEFORE the summary prints. Add a `fuse` smoke test (currently zero coverage).
- **B8** sensitivity_runner.py:155 — `sim.sensitivity('temperature', i)`.
- **B9** cli.py:1136-1141 — check `status` first; print only `objective_final`, guarding None.
- **B14** nominal_sim_gui.py:200-205 — launch `[sys.executable, "-m", "mso_compare.run_nominal_sim", ...]` with `cwd=str(_REPO/"src")` (or pass env PYTHONPATH). Add a subprocess-spawn smoke test (the `--no-gui` tests import in-process and miss this class entirely).
- **B12** brute_force_sa_gui.py:236-240 — `out = Path(out_dir).resolve()`; write `out/"target.opt"`; pass that absolute path; `cwd=str(out)`. Same one-liner class in **sens_3_params.py:126,134**: `argv[1] = os.path.abspath(argv[1])` immediately, resolve Locations against the config file's dir.
- **M18a** zerork_gsa.py:318 + gsa_prs_crosscheck.py:432 — `max(2, min(n_mpi_ranks, n_rows+1))`.
- **B11** zerork_gsa.py:229 — treat non-finite as failed: `if math.isfinite(idt_s) and idt_s > 0`. Fix the test that encodes failure as 0.0 (test_zerork_gsa.py:209) to use `inf`. Add a guard: if n_failed/n_total > threshold (e.g. 20%), abort with message instead of imputing.

## Phase 1 — scientific-integrity core (the big ones; do as one arc with tests)
- **B1** cantera_reader.py:154-206 — dispatch on `rx.reaction_type` / `type(rx.rate).__name__` (Cantera 3: `ArrheniusRate`, `FalloffRate`+`rate.falloff_coeffs`, `PlogRate.rates`, `ChebyshevRate`; third-body via `rx.third_body`). Rewrite `_is_pdep`/`_has_third_body` the same way.
- **B2** same file — convert kmol→mol at read: `A /= 1000**(order-1)`, `Ea /= 1000`; leave `A_orig/Ea_orig` NULL for cantera source. Unit test: parse FFCM1.yaml, assert A_si of `H + O2 <=> O + OH` equals the known value in mol-SI.
- **B15** chemkin_writer.py:70,448,492-493 — either header `KCAL/MOLE` or divide by 4.184 (pick one, add round-trip test parse→export→parse asserting Ea equality). Fix **M-writer** items while in file: orig-units conversion table (kcal/K/kJ), `+M` token-level test (:666), therm.dat double END (:200), `{eff:.4g}` (:674).
- **B3** comparison.py — unresolved species/reactions go into `unique` keyed by raw name instead of being filtered out; emit coverage % in CLI output and `n_excluded` in JSON; hard-error when 0% keys resolved. 
- **B4** fusion.py — unresolved reactions pass through VERBATIM (never dropped); refuse to fuse rows with NULL kinetics (post-B1 this mostly disappears); identity test: fuse(FFCM1, FFCM1) == FFCM1 within tolerance.
- **B6** _chemkin_parser.py — extend the Arrhenius-triple regex to Fortran floats `(\d)([+-]\d{1,3})\b→\1E\2` *at tokenization* (reuse the tested `fix_fortran_exponents` logic from mechanism_converter_gui.py). Test with `1.7+13`.
- **B7** _chemkin_parser.py:520-546 — attach DUPLICATE to the just-collected reaction; accept `DUP`; writer emits DUPLICATE AFTER the line. Round-trip test through ck2yaml.
- **M1** _chemkin_parser.py — species-list-aware equation splitting (longest match against declared species, so `HO2+` survives); post-parse referential check: undeclared participant = error naming reaction + line (with an `--allow-pseudo-species` escape that drops HV-style tokens with a warning, mirroring ck2yaml --permissive; that also un-breaks gsa-run on chemiluminescence mechanisms).
- **M2** — tokenize `_extract_slash_content(line)` not the raw line for LOW/TROE/PLOG.
- **M3** — check "KJOU" before "JOULES"; warn on MOLECULES/EVOLTS.
- **M4** — strip `+M` in `_parse_species_side`, set has_third_body, never store M as species.
- **M5** — standardize kinetics_data on mol-SI in all three readers; writer converts per sub-rate order (LOW = order+1). One shared helper, tested.
- **M6** cantera_writer.py:179 — keep canonical element case (`el.capitalize()` is fine for element symbols); regression test: export mech with Ar/He, `ct.Solution` must load.
- **M7** chemkin_writer — hard error (or `--force`) when writing a reaction whose A_si is NULL.
- **M8** cantera_reader.py:93-102 — warn per skipped thermo type + record it; investigate cantera_writer.py:484 Tmid discontinuity warnings while there.

## Phase 2 — silent-wrong-results in analysis/optimization
- **M9** — key reaction maps on `(canonical_key, occurrence_index)` everywhere (fusion.py:599, comparison.py:161, unified_tree.py:949, graph_comparator.py:548, gsa_prs_crosscheck.py:587); graph_builder R-labels get occurrence suffix.
- **M10** graph_comparator — non-arrhenius types require canonicalized kinetics_data_json equality for SHARED_IDENTICAL.
- **M11** fusion/unified_tree — any rxn_map containing non-arrhenius kinetics_type → VERBATIM fallback.
- **M12** fusion.py:892-897 — skip the whole reaction with a WARNING (or carry species by name); never insert mass-imbalanced stoichiometry.
- **M13** unified_tree.py:382-385 — store the band on the record; iterate records; kill the parallel zip.
- **M14** uncertainty_bands — port to `ct.TroeRate`/`ct.ChebyshevRate`, convert mol↔kmol + Ea×1000; un-swallow the AttributeError.
- **M15** drg.py:227-230 — `if sp_set <= retained`; rates fallback 0.0 + abort below 90% equation-match coverage (log the fraction).
- **B10/M-rmg** cli.py:1231-1242 + rmg_interface.py — align `_cmd_complete` to the real API; fix `load_rmg_output` to `MechanismParser(RMIPConfig(...)).parse(...)`; `_clone_if_needed` must remap species ids (copy the mso_interface.py:529-540 pattern).
- **M16** cli.py — jsr/pfr/flux `return 0 if result.converged else 1`; wrap `main()` dispatch in try/except printing a clean error (KNOWN Jul11).
- **M17** migrations.py — wrap both rebuilds in BEGIN/COMMIT + leftover-table recovery (copy the phase-6 pattern verbatim); fix the idempotency probe (use PRAGMA table_info or a real existing mechanism_id) so rebuilds stop running on every startup; explicit column list in the INSERT…SELECT; schema_phase3 dataset reload: delete old points first.

## Phase 3 — pipeline robustness (MUQ-SAC / mso_compare / forward_uq / GSA)
- **M22** run_script.py + data_management.py — `sys.executable`; delete `'&>SA.out'` pseudo-arg (use `stdout=open(...)` if the log is wanted); check returncode and surface stderr; delete stale `tau.out` before each case; treat rc≠0 as case failure.
- **M23** both ResponseSurface.py — implement order≥3 in the evaluators mirroring the fixed fit loops, or `raise ValueError("order>2 unsupported")` at construction. Add the agent's no-solver test: fit exact cubic, evaluate at a point with equal components, assert match.
- **M24** mso_compare pipeline — `max_workers=1` now (correct), processes later; long-term remove `os.chdir` from sim_runner in favor of explicit paths.
- **M25** error_metrics — one common finite mask across Obs + all stage columns; warn with NaN counts; guard obs=0 → σ=0.
- **M26** forward_uq.py — key `unsrt.pkl` to sha1(uncertainty-XML path+mtime, mechanism path+mtime); both result pollers: only accept CSV with mtime > launch time, poll until child exit (PtyTerminal knows the pid), always set a final status.
- **B13** forward_uq_gui — cwd = directory of the ORIGINAL target.opt; write the GUI's temp copy as `target_gui_run.opt`; askyesno before overwriting any existing file.
- **M19** gsa_prs_crosscheck — require n_rows ≥ 2×n_coefficients and ≥5 test points for a verdict; add timeout to `_salib_call` and delete stale response JSON first.
- **M20** simulation/base.py — write cache to `*.tmp` + `os.replace`; unlink on exception; hash includes thermo path (raise if missing) + `ct.__version__`.
- **M21** jsr/pfr runners — purge `output/` before run; rc≠0 → failed result, never store.
- **M18b** zerork bridges — sanitize env (strip LD_LIBRARY_PATH or set to Zero-RK's own lib dir); finite default timeout (3600s) on all bridge subprocesses; muqsac_bridge oxidizer from condition, not hardcoded "O2".

## Phase 4 — GUI hardening (findings-b has exact lines for all)
- **M27** pty_terminal.py — close fd + waitpid in `stop()`; per-run generation token for the reader thread; `pyte.HistoryScreen(history=5000)` or tee to logfile + "Open full log"; write child exec errors to fd 2 before `os._exit`.
- All 5 terminal apps — `root.protocol("WM_DELETE_WINDOW", ...)` with running-job confirmation (copy the pattern from mechanism_converter_gui.py, which already has it).
- brute_force_sa shallow copy → `copy.deepcopy`; settings.py atomic write (tmp+os.replace); mean_value_fusion `is_file()` check before sqlite connect + close connections; default launch cwd = repo root everywhere; save typed (not just browsed) paths; `sys.path.insert→append` in all apps; fuel_data "butene"→C4H8; launcher reaps children with an `after()` poll.
- Uncertainty conventions — document min-vs-max in the CSV header and GUI label; reuse one Parser per compute run.
- Monolith (if it stays alive): validate temps/unsrt per reaction before writing XML (None.split crash); delete NamedTemporaryFile after use; fix DEFAULT_CONFIG["Bin"] placeholders (**M28**, KNOWN since Jul-11).

## Phase 5 — minors batch
Work through the MINOR list in review.md + findings files area by area (parser leniency warnings, canonicalize stoich coefficients, per-mechanism transaction, report --out, argparse consistency, `--use-original-units` BooleanOptionalAction, IDT refinement, LFS explicit transport, benchmarking sort/filter, SRI support-or-refuse, rank IN() guard, forward_uq rename to run_forward_uq_cli.py). None are urgent; all are one-sitting each.

## Verification recipe (end of each phase)
1. `python3 -m pytest src/rmip/tests/ tests/ -q` — ≥481 + new tests green.
2. Round-trip: `parse FFCM1.yaml -g species_smiles.csv` → assert kinetics non-NULL; `compare -m 1 1` → 100% shared; `fuse` two FFCM1 copies → identity; `export --format yaml` → `ct.Solution` loads (incl. an Ar-containing mech).
3. Adversarial re-run: the 10 files in scratchpad battery (recreate from review report §parser battery) — Fortran exponent now parses to 1.7e13; undeclared species now errors.
4. GSA: `gsa-run` minimal (N=4, 3 reactions) on GRI-wetCO — still passes; inject an `inf` row into a saved gsa_output.dat and assert the run aborts with the failed-sample message.
5. GUI: `python3 <app>.py --no-gui` for all 9 + one real Run per app from the launcher (converter: Keromens end-to-end).
