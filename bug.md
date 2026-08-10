# bug.md -- Unresolved bugs / known limitations

Compiled 2026-07-17 from every .md/.txt file in this repo plus this session's own work.
See `MarkDownFiles/HISTORY/` for the chronological narrative, and `BUG.md` (uppercase)
for the resolved counterpart list. Ordered roughly by severity/blast-radius within each
section, not by discovery date.

---

## From the 2026-07-13/14 deep review (`MarkDownFiles/review.md`), review_plan.md Phases 3-5

**RESOLVED 2026-07-19** (see `BUG.md` § "2026-07-19 robustness + RMG/DRG batch" for
per-item resolution + regression tests): **B10, M15, M16, M17, M18b, M19, M20, M21,
M22, M23, M25, M26.**

**RESOLVED 2026-07-20**: **M27.** `PtyTerminal` (`src/gui_common/pty_terminal.py`) --
all 4 sub-bugs fixed in the same shared widget (fixes all 5 terminal-backed GUI apps
at once, since they all import this one module):
1. fd+zombie leak: `stop()` (`pty_terminal.py:213-253`) now sends SIGTERM, polls
   `os.waitpid(pid, os.WNOHANG)` for up to ~1s in 50ms increments, escalates to
   SIGKILL + a final blocking `os.waitpid` if the child hasn't exited, and always
   closes `self._fd` (guarded, may already be closed) before clearing
   `self._pid`/`self._fd`.
2. reader-thread restart race: `run()` (`pty_terminal.py:92-122`) now bumps a
   monotonic `self._gen` counter per call and passes `(gen, fd)` explicitly into
   `_read_loop` (`pty_terminal.py:124-152`), which checks `gen == self._gen` both
   before each `os.read()` and again before `self._stream.feed(data)` -- a stale
   reader thread from a just-superseded session can no longer corrupt the new
   session's rendered output.
3. no scrollback: `run()` now builds `pyte.HistoryScreen(cols, rows, history=2000,
   ratio=0.5)` instead of a plain `pyte.Screen`; Page Up/Down and mouse wheel
   (`<Prior>`/`<Next>`/`<MouseWheel>`/`<Button-4>`/`<Button-5>`) are bound on the
   `Text` widget (`pty_terminal.py:77-81`) to call `prev_page()`/`next_page()`
   followed by an immediate re-render via the newly-factored-out
   `_refresh_once()` (`pty_terminal.py:154-181`, separated from the periodic
   `_refresh()` timer at `183-186`).
4. no window-close guard: `__init__` now binds `<Destroy>` on the frame itself
   (`pty_terminal.py:87`, handler at `207-211`), calling `self.stop()` only when
   `event.widget is self` (ignoring bubbled `<Destroy>` events from child
   widgets like `self.text`).

Regression tests: `src/rmip/tests/test_pty_terminal.py` (4 tests, all passing) --
reaping+fd-clearing after `stop()`, no cross-session contamination across two
back-to-back `run()` calls, prompt reaping on `Toplevel.destroy()`, and
`HistoryScreen`/scroll-binding construction.

**RESOLVED 2026-07-22**: **M28.** `generate_target_opt.py`'s `DEFAULT_CONFIG["Bin"]` now
built by `_default_bin_paths()`, which sources each of its 5 absolute paths (`bin`,
`solver_bin`, `yaml_writer`, `SA_tool`, `SA_tool_3p`; 2 more are `PLACEHOLDER_*` strings,
unaffected) from an env var (`MSO_MUQSAC_BIN`, `MSO_FLAMEMASTER_BIN`, `MSO_YAML_WRITER_SO`,
`MSO_SA_TOOL`, `MSO_SA_TOOL_3P`) with the old literal as the documented default, so an
unconfigured checkout on this machine behaves identically while another machine/CI can
override any entry without editing the file. No open items remain in this table.

## MINOR list (review.md, review_plan.md Phase 5) -- "not urgent... none are started"

Parser leniency warnings on truncated files; the no-RDKit fallback fabricating fake InChI keys;
per-mechanism transaction handling; `report` CLI writing to CWD; argparse inconsistency
across subcommands; a no-op `--use-original-units` flag; IDT coarse-grid quantization;
LFS's deprecated implicit-transport model; benchmarking's stale-row ranking; `rank`'s
empty-list SQL error; an uncertainty-convention mismatch between `Uncertainty.py`
(min-over-T, conservative) and `uncertainty_generator_gui.py` (max-over-3-anchors,
anti-conservative) for the same XML input, with nothing in the file format recording
which convention a given output used; `gui_common` settings non-atomic write; "butene"
incorrectly aliased to C4H6; `sys.path.insert(0, ...)` violating the repo's own
append-only-path rule in all 8 GUI apps; and more not individually itemized here -- see
`MarkDownFiles/review.md`/`review_plan.md` directly for the complete original list.

## Deferred cleanup items (not bugs, but standing "not done" decisions)

| Description | Notes |
|---|---|
| Quick win #13: delete `bkp`/`backup` dirs (~11,554 LOC) | User explicitly declined at the time ("this repo is not under git ... no cheap rollback"). Repo IS under git now (since 2026-07-11) but this was never revisited |
| Structural improvement #2: archive `MUQ-SAC_EXTENDED/` (~16,070 LOC) | Same status as above |
| Structural improvements #3-#7 (2026-07-11 review): O(N) `.index()` lookup consolidation, `class App` God-Object decomposition, numeric-field input validation, full PySide6 migration, `config_tools/` split | Never started per any later document |
| `stubs.py` modules: `PathwayCompleter` (needs RMG-Py), `UQFusion` (needs a MUQ-SAC covariance adapter, blocked on a referenced-but-nonexistent `CLAUDE.md` section), `AIRecommender`, `ChangeLog`, `ReportEngine` | Explicitly still unimplemented, out of scope per RESUME.md |

## `Future.md` restart/checkpoint bug audit (2026-07-05) -- AUDITED + CONFIRMED RESOLVED 2026-07-19

Audit conclusion: all six FUTURE-BUGs are **already fixed** in the current
`src/MUQ-SAC/` copy (labelled "Bug 1/2/3/4/5 fix" and "Task 4A" in the source),
verified by reading each cited location this session:

| ID | Status | Where fixed |
|---|---|---|
| FUTURE-BUG-1 | Fixed | `simulation_manager2_0.py` -- sentinel written to `<case_dir_path>/.done`, path built from `optDir` (captured up front), never `os.getcwd()` |
| FUTURE-BUG-2 | Fixed | per-case body wrapped in `try: … finally: os.chdir(optDir)` in `make_dir_in_parallel` |
| FUTURE-BUG-3 | Fixed | `partial_PRS_system.py::partial_DesignMatrix` restart branch iterates `p_design_matrix` (partial), not `design_matrix` (full) |
| FUTURE-BUG-4 | Fixed | same file verifies on-disk `mechanism_*.yaml` count == `len(p_design_matrix)` and wipes+regenerates if a chunk-write was interrupted |
| FUTURE-BUG-5 | Fixed | `locations` writes dedupe against lines already on disk; **also hardened this session** the nominal-run writer (both `MUQ-SAC` and `Sensitivity_Analysis` copies) with the same dedupe |
| FUTURE-BUG-6 | Fixed | `Worker.progress_file` is a required absolute path (Task 4A); MUQ-SAC copy raises if unset. NOTE: the `Sensitivity_Analysis` copy still keeps a `os.path.dirname(os.getcwd())` fallback -- lower-risk (that pipeline is the sens_3_params path left out of scope), noted here, not changed |

## Real-mechanism second-tier GUI stress test (2026-07-17) -- new, unresolved

| Description | File/module | Notes |
|---|---|---|
| **Secondary, separate bug found while diagnosing the fusion A_orig bug (now fixed, see BUG.md)**: `src/MUQ-SAC/data_management.py::run_sim`'s Step 5 unconditionally requires the literal string `"soln2ck_2.py"` to appear somewhere in the generated per-case `run` script before executing it, but `make_input_file.py`'s `solver == "cantera"` branch (the one actually used whenever a target's `.add` file specifies `solver: cantera`, which is every target this suite's own dummy AND real fixtures use) generates a `run` script containing ONLY `python3.9 cantera_.py &> solve` -- it never contains `soln2ck_2.py` by design (that command belongs only to the `CHEMKIN_PRO`/`zerork`/FlameMaster solver branches, which do a CHEMKIN-round-trip cantera_1.py doesn't need). Consequence: whenever a `solver: cantera` simulation fails for ANY reason on its first attempt (ignition timeout, numerical issue, anything) and the pipeline's serial retry logic invokes `run_sim` to retry it, the retry ALWAYS immediately fails with the confusing, wrong `RuntimeError("Could not find the soln2ck_2.py command in the run script.")` instead of either genuinely retrying the Cantera simulation or reporting the real underlying error -- masking whatever the actual first-attempt failure was. First observed while investigating why a real-fused-mechanism `nominal_sim_gui`/`mso_compare_gui` run produced NaN results; confirmed independent of mechanism content (reproduces for solver=cantera regardless of what actually caused the first-attempt failure). | `src/MUQ-SAC/data_management.py::run_sim` (Step 5, ~line 200), `src/MUQ-SAC/make_input_file.py`'s `solver=="cantera"` branch (the `s_run` template with no `soln2ck_2.py`) | **RESOLVED 2026-07-19.** Fixed exactly per the fix direction: `run_sim` Step 5 now branches on the case's actual solver via a new `_run_script_needs_soln2ck(solver)` helper (only `CHEMKIN_PRO`/`zerork` require the `soln2ck_2.py` line; `cantera` runs directly), so a `solver: cantera` retry no longer raises the spurious `RuntimeError` and no longer masks the real first-attempt failure. Regression test: `src/rmip/tests/test_soln2ck_retry_mask.py` (ties the predicate to `make_input_file.py`'s `s_run` templates so they can't drift apart). |
| **`sens_3_params.py` (brute_force_sa_gui's underlying tool) silently fails to complete ANY simulation against a real, moderately-large (17-species/56-reaction) mechanism** -- every nominal AND perturbed case's per-instance working directory is missing its required `mechanism.yaml` (the `Design_of_PRS: A-facto` branch of `data_management.py::run_sim` hard-requires `os.path.join(workdir, "mechanism.yaml")` to already exist), so every single simulation in the run reports `ETA=N/A`, the retry pass also fails identically, and the final SA-coefficient step crashes with `IndexError: index 0 is out of bounds for axis 0 with size 0` trying to read an empty result array. 100% reproducible against the real Keromnes/Li/Davis fused mechanism (`Fused_mean_KLD_v2`, 17 sp/56 rxn) with a real target.opt (2 real IDT targets, 12 real reactions with a realistic factor/arrhenius uncertainty mix) -- the exact same code path, same `Design_of_PRS: A-facto` setting, completes cleanly end-to-end on the small dummy fixture (9 sp/8 rxn, `test_brute_force_sa_b12_and_mono_fuel_fix_no_longer_crash`). **Ruled out as NOT a race condition**: reproduces identically with `parallel_threads: 1` (single Pool worker, no concurrency) as with 2. **Ruled out as NOT a mechanism-content/parsing problem**: calling the exact compiled writer the pipeline uses (`yamlwriter.dump_to_yaml`, imported via `sys.path.append('/yamlwriter.so')`) directly, single-process, with the mechanism dict built the SAME way production does (`MechanismParser.Parser(mech_path).mech`) on this exact real mechanism succeeds and writes a valid `mechanism.yaml`. No Python exception or `error_callback` "Got an error" message ever appears in the full run's output, ruling out a normal Python-level failure inside the `multiprocessing.Pool` worker (`simulation_manager2_0.py::run_map`, dispatched via `do_job_map_create`) -- the worker writes `cantera_.py`/`FlameMaster.input`/`extract.py`/`run` (all the steps BEFORE the `yamlwriter.dump_to_yaml` call in `run_map`) successfully, but the mechanism.yaml write immediately after never lands, and `Pool.join()` still returns normally. **2026-07-17 (later): found and fixed one concrete, independently-real contributing bug while re-investigating this** -- `simulation_manager2_0.py::Worker.__init__` (all 3 live copies: `Sensitivity_Analysis/simulation_manager2_0.py`, `Sensitivity_Analysis/simulation_manager.py`, `MUQ-SAC/simulation_manager2_0.py`; `MUQ-SAC_EXTENDED`'s copy left untouched per the standing out-of-scope decision) unconditionally created a SECOND, completely unused `concurrent.futures.ProcessPoolExecutor(max_workers=workers)` alongside the `multiprocessing.Pool` actually used -- never referenced again anywhere in the class, never shut down. `Worker(...)` is instantiated up to 11 times across one `sens_3_params.py` run (once per YAML-generation chunk/variant: A/n/Ea x forward/central-difference), so at a real `parallel_threads` count (target.opt templates default to 100) this could leak into the hundreds-to-thousands of never-terminated OS processes across a single SA run -- a plausible contributor to exactly the kind of silent, load-dependent native-level failure described here, though NOT independently proven to be the full root cause: two separate controlled repro attempts this session (bare fork + `yamlwriter.dump_to_yaml` on the real 56-reaction mechanism; the same, preceded by a real Cantera nominal-IDT simulation in the parent process to mimic `sens_3_params.py`'s actual call order) both completed cleanly with NO crash, at only 2 workers / up to 6 tasks -- meaning the leak (or whatever the true trigger is) likely needs either a much higher real `parallel_threads`/task count or genuinely more `Worker(...)` instantiations than either repro exercised to manifest. Removed the dead `self.pool1` regardless (unambiguously wasteful/dangerous on its own merits) but the underlying yamlwriter-in-a-forked-worker mystery itself is still NOT conclusively root-caused. **Further mitigated 2026-07-20**: added `_write_mechanism_yaml_verified()` (`src/Sensitivity_Analysis/simulation_manager2_0.py`, immediately above `run_map`), which wraps the ONE `yamlwriter.dump_to_yaml(location, "mechanism.yaml", params[-2])` call site inside `run_map` (only that call -- `run_map_2`/`run_map_3`/`run_map_opt`/`run_direct_map` and their writers are untouched) with verify+retry+fallback: after each call it checks `os.path.exists(out_path) and os.path.getsize(out_path) > 0`; on failure it retries (up to 3x, 0.25s apart), then falls back to a pure-Python dump via the same ruamel-backed `yaml` module already used elsewhere in this file (`run_direct_map`'s pattern); if even that fails it raises a clear `RuntimeError` naming the path and both failure modes, instead of silently letting execution fall through into `data_management.py::run_sim` and the confusing downstream `IndexError`. Root-cause read of `config_tools/converters_io/YAML_WRITER/yamlwriter.cpp::dump_to_yaml` (untouched, read-only): **confirmed** -- it opens its output with a bare `std::ofstream fout(filepath);` with no `is_open()`/`fail()` check afterward and never calls `fout.exceptions(...)` to enable exceptions, so a failed open (or a failed write) is a silent no-op by C++ `ofstream` default semantics: no exception, no file, `Pool.join()` still returns normally -- exactly matching the previously-unexplained symptom. The actual trigger for why the open/write fails specifically under real-scale mechanisms inside a forked `multiprocessing.Pool` worker is still not nailed down (would need strace/gdb under real load), but the silent-failure MECHANISM itself is now confirmed and, more importantly, no longer able to propagate past this call site undetected. Regression tests: `src/rmip/tests/test_simulation_manager_yaml_write.py` (3 tests: happy path via the real compiled extension, fallback-succeeds when the extension silently no-ops, RuntimeError when both the extension AND the fallback fail). The `.cpp` file itself is intentionally NOT modified (out of scope; the mitigation lives entirely on the Python side). | `src/Sensitivity_Analysis/simulation_manager2_0.py::run_map` (calls `yamlwriter.dump_to_yaml` via the new `_write_mechanism_yaml_verified` wrapper), `::Worker.__init__` (the `pool1` leak, now fixed), `src/Sensitivity_Analysis/data_management.py::run_sim` (the consumer that raises `FileNotFoundError` when the file never arrives) | **Real, significant limitation, further mitigated 2026-07-20** -- the silent-failure MECHANISM is now confirmed (bare `std::ofstream`, no exceptions, no `is_open()` check) and can no longer pass through undetected: the call site now retries and falls back to a pure-Python YAML dump, and raises a clear `RuntimeError` if both paths fail, rather than letting the caller silently proceed into the confusing `IndexError`. The `pool1` leak is fixed and verified safe (`test_brute_force_sa_b12_and_mono_fuel_fix_no_longer_crash` still passes end-to-end, 123s). What is NOT yet done: a real-scale (17sp/56rxn) end-to-end regression test through the actual `sens_3_params.py`/GUI stress-sweep path (would need a full target.opt + 12-reaction uncertainty-XML fixture built from scratch, per the existing `GUI_STRESS_TEST_PLAN.md` real-mechanism repro) -- flagged as a manual/future verification step; the 3 unit tests above are the currently-shipped minimum. Repro preserved: real target.opt + real fused mechanism + real 12-reaction uncertainty XML, described above; rerunning `python src/Sensitivity_Analysis/sens_3_params.py <that target.opt>` reproduces the underlying yamlwriter silent-failure trigger in under 2 minutes (now surfaced as a retry+fallback+clear-error instead of a downstream `IndexError`). **Root-cause investigation completed 2026-07-23** (evidence + fixtures: `Test_run_23_JULY/sens_3_params_investigation/`): built a fresh, fully real, self-contained repro from scratch (the original session's own repro fixtures had been cleaned from the repo) -- re-parsed and re-fused the real Keromnes/Li/Davis sources with the self-third-body canonicalizer fix active (`rmip_cli.py parse` + `mean_value_fusion_gui._run_fusion(..., write_cantera=True)`) to get a `Fused_mean_KLD_v2.yaml` that actually loads in Cantera (the on-disk `outputs/fusion_keromnes_li_davis/mean_unsrt/Fused_mean_KLD.yaml` still fails `ct.Solution()` with the known undeclared-duplicate-reaction issue and can't be used for a live-simulation repro at all); built a real 46-reaction mixed factor/arrhenius uncertainty XML against this mechanism's own real reactions (up from the original 12, to scale-test harder); reused the real T=1450/1350 K, P=2.2 atm H2/O2/Ar IDT target pair already present in `src/rmip/tests/fixtures/gui_stress/` (same values documented in this entry's original repro). **Traced the actual production write path precisely, and it is NOT what this entry's earlier "further mitigated" paragraph protected.** `sens_3_params.py`'s brute-force SA calls `SM.make_dir_in_parallel` (never `Worker.do_job_map_create`/`run_map`, which the 2026-07-20 `_write_mechanism_yaml_verified` wrapper protects and which this pipeline turns out never to call at all). `make_dir_in_parallel` dispatches per-case-directory file writes to `run_map_opt` (via `do_job_create_opt`), which writes `cantera_.py`/`FlameMaster.input`/`extract.py`/`run` but **never writes a `mechanism.yaml` at all** -- confirmed both by reading `run_map_opt`'s body (no yaml call anywhere) and by inspecting real output directories from a live run (`SA_3P/multiply_A/case-0/0/` etc. genuinely have no `mechanism.yaml`, by design, not by failure). Instead, each per-case `cantera_.py` references its mechanism by an **absolute path** into a *shared*, once-per-design-matrix-row file tree (`Perturbed_Mech_SA_3P_BruteForce/{A_factor,n,Ea,A_factor_neg,n_neg,Ea_neg}/mechanism_<row>.yaml`, e.g. `gas = ct.Solution('/abs/path/.../A_factor/mechanism_0.yaml')`), written by a *separate*, earlier method: `SM.getPerturbedMechLocation` -> `Worker.do_job_map_create_3` -> `run_map_3` -> `yamlwriter.dump_to_yaml` -- i.e. the real production silent-failure-risk call site is `run_map_3`, which this entry's own 2026-07-20 scope note correctly flagged as untouched but which nobody had yet connected to this specific bug's actual reproduction pathway. **Could NOT reproduce the original missing-file symptom at any tested scale on the current code state**, despite deliberately exceeding the original attempt's load by a wide margin: 46 real reactions (vs 12), `parallel_threads: 100` (the documented target.opt template default, vs the original's 1-2), `SA_scheme: central_difference` (11 `Worker()` instantiations total, matching the max this entry itself calculated), real 56-reaction mechanism, multiple independent full end-to-end runs -- every run completed 100% cleanly, all 276 `mechanism_<n>.yaml` files present and non-empty every time, real physically-sane SA coefficients computed, reaching the script's own `AssertionError("3-PARAM SA DONE")` completion sentinel exactly like the shipped dummy-fixture regression test. **Directly tested and refuted this entry's own "pool1 leak -> resource exhaustion" theory**: read CPython 3.9's `concurrent.futures.process` source and confirmed `ProcessPoolExecutor.__init__` does **not** eagerly fork worker OS processes -- process spawning is lazy, triggered only by `submit()`/`map()`, and the old leaked `pool1` was (by this entry's own description) never referenced or submitted to anywhere -- so it never forked any child processes at all; each leaked instantiation costs only ~6 file descriptors (its internal `Queue`/`SimpleQueue`/`_ThreadWakeup` pipes), nowhere near this machine's `ulimit -n` of 1,048,576. Empirically confirmed with a standalone script (`Test_run_23_JULY/sens_3_params_investigation/repro_pool1_leak_hypothesis.py`) that deliberately recreates the exact old leaky `Worker.__init__` pattern around 1,100 real `yamlwriter.dump_to_yaml` calls on the real 56-reaction mechanism (11 calls x 100 workers, matching this entry's own numbers): zero failures, `/proc` entry count flat throughout (1933 -> 1932), parent fd count grew by exactly ~6 per call as predicted. **Conclusion**: the true trigger for the original 2026-07-17 observation is still not pinned down with certainty -- it may have been an indirect side effect of the M30 `DesignMatrix2_0.py` fix (2026-07-19, which changed `getSA_3P_samples`'s chunk-width/index mapping and could plausibly have altered what fed into this exact pipeline stage) rather than the `pool1`/yamlwriter theories this entry originally proposed, or it may have depended on transient environmental conditions (system load/memory pressure at that moment) that a controlled repro can't recreate after the fact; genuinely not reproducible today is the honest conclusion, not "fixed and understood." **What IS newly and concretely fixed regardless of that open question**: `run_map_3` -- the actual call site this pipeline uses for every mechanism-perturbation write -- was not covered by the 2026-07-20 mitigation and is now routed through the same `_write_mechanism_yaml_verified` verify/retry/fallback wrapper (`simulation_manager2_0.py::run_map_3`, one-line change plus an updated docstring on the wrapper's scope note), closing a real coverage gap independent of whether the original race is reproducible; `run_map` itself remains unused by this pipeline but is left as-is (harmless, and other callers may exist). 2 new regression tests added (`test_simulation_manager_yaml_write.py::test_run_map_3_is_the_real_production_write_path_and_now_protected`, `::test_run_map_3_happy_path_real_extension`), full existing suite re-run clean. Also captured direct syscall-level proof with `strace -f -e trace=openat,write,close` around a real (smaller-scale, `parallel_threads: 20`) run: every single `openat(AT_FDCWD, "<absolute path>/Perturbed_Mech_SA_3P_BruteForce/.../mechanism_<n>.yaml", O_WRONLY|O_CREAT|O_TRUNC, 0666)` call across all 3 buckets it reached (A_factor/n/Ea, 12 reactions each = 36 opens) returned a valid fd, every matching `write()` returned the full requested byte count (no short writes), every `close()` returned 0, and zero `EMFILE`/`ENFILE`/`ENOSPC`/`EACCES` appear anywhere in the full trace -- this also directly confirms the path passed to `yamlwriter.dump_to_yaml` is **always absolute** (`AT_FDCWD` + a full `/data/...` path, never a bare relative filename), which independently rules out the task's step-4 "concurrent `os.chdir()` + relative-path collision" theory for this call site: there is no relative path here for two workers to race on. Evidence, fixtures, and logs for all of the above: `Test_run_23_JULY/sens_3_params_investigation/` (re-fused `mean_v2/Fused_mean_KLD_v2.{yaml,inp,dat}`, `kld_12rxn_unsrt.xml`/`kld_46rxn_unsrt.xml`, `kld_repro*.opt`, `dryrun1.log`/`heavy_run1.log`/`heavy46_run1.log`/`postfix_run1.log`, `repro_pool1_leak_hypothesis.py` + `pool1_leak_repro.log`, `strace_run1.log.gz` (full raw trace, gzipped) + `strace_run1_mechanism_calls_only.log` (pre-filtered to just the `mechanism_`/error-code lines) + `strace_run1_stdout.log`). **Note (2026-08-04)**: `Test_run_23_JULY/` itself is now gitignored (119 MB of test-run output, never meant to be committed) but still present on local disk at this path -- only the `mean_v2/Fused_mean_KLD_v2.yaml` mechanism was worth preserving in git long-term, and it's now also tracked as a fixture at `src/rmip/tests/fixtures/fused_mechanisms/Fused_mean_KLD_v2.yaml` (verified re-loads clean, 17 sp/56 rxn, at the new path). |

## This session (2026-07-17) -- scoped but explicitly NOT implemented

| Description | File/module | Why not done |
|---|---|---|
| Zero-RK flame speed (`Fls` target, `premixedSteady.x`) | `src/MUQ-SAC/make_input_file.py` (no `Fls` zerork branch exists) | Investigated thoroughly: Zero-RK's `premixed_steady_flame_solver_mpi.x` is a fixed-inlet-velocity burner-stabilized solver, not a single-subprocess-call bridge like Tig/JSR/RCM. Needs a real multi-stage bootstrap pipeline (unsteady run for an initial profile -> Lewis_file generation -> steady KINSOL solve -> adaptive regrid-and-retry loop) confirmed via Zero-RK's own bundled Python driver (`flamesolver.py::compute_steady_flame_speeds`). Deliberately not rushed -- would produce a plausible-looking but physically wrong bridge. Needs a dedicated follow-up session, ideally after the user weighs in on required fidelity vs. a cheaper approximation |
| Zero-RK counterflow + extinction strain rate (`counterflowSteady`/`Unsteady.x`) | No target type exists for this at all | Same class of blocker as flame speed above (`counterflowflamesolver.py`/`counterflowpremixedflamesolver.py` mirror the same bootstrap-pipeline shape). Also needs a genuinely new target-type tag (confirmed `Flw` is already claimed by an unrelated flow-reactor-slope target) |
| Sweep the other 5 launcher GUIs (brute_force_sa, forward_uq, nominal_sim, mso_compare, rmip_suite, mechanism_converter) against a fused mechanism | -- | **DONE** (committed `c88ccb3`, confirmed 2026-07-19): `GUI_STRESS_TEST_PLAN.md` fully executed. All 8 launcher GUIs have in-process worker-function runs in `src/rmip/tests/test_gui_stress_sweep.py` (17 tests, all pass, ~111 s) against the checked-in `src/rmip/tests/fixtures/gui_stress/` fixtures. B13 (forward_uq doubled-path) fixed + regression-tested there; M24 (mso_compare CWD race) covered with a ≥2-worker concurrent run; rmip_suite all 4 tabs (incl. previously-zero-coverage GSA + Active-Param) tested. |
| Literal (not in-process-function-call) Tk GUI driving on a live display, to directly answer "does the GUI itself work" | -- | Abandoned mid-session for safety after a misdirected click hit another live agent session's window on the shared X display (`:52.0`); switched to calling the GUI's own worker functions in-process, which is faithful to the same code path but is not literally the same as a human clicking through the widgets |

## `run_report.py` -- `src/io/` package name collides with stdlib `io` (found 2026-07-21, **RESOLVED 2026-07-22**)

| Description | File/module | Notes |
|---|---|---|
| `src/run_report.py` imported its sibling modules as `from io.mso_io import ...` / `io.mso_analysis` / `io.mso_plots` / `io.mso_latex`. `src/io/` was a real Python package literally named `io`, so this could not resolve under any normal CPython invocation, confirmed both ways: **(a)** if `src/` is not on `sys.path` at interpreter start (e.g. `sys.path.insert()`'d after startup, or run from repo root without `cd src`), the interpreter's own bootstrap has already cached `sys.modules['io']` as the real stdlib module, so `from io.mso_io import ...` failed with `ModuleNotFoundError: No module named 'io.mso_io'; 'io' is not a package`. **(b)** if `src/` *is* on `sys.path` at interpreter start (`cd src && python run_report.py`, exactly as the script's own docstring instructs: "Run: python run_report.py"), the interpreter's bootstrap `import io` (needed internally for stdio setup) resolved to the local empty-namespace `src/io/` package instead of real `io`, and CPython crashed before any user code ran: `Fatal Python error: init_sys_streams: can't initialize sys standard streams` / `AttributeError: module 'io' has no attribute 'open'`. Found while wiring MSO Studio's (`src/mso_studio/`, the new PySide6 GUI) "richer per-module LaTeX export" for the Mechanism Comparison page -- see `src/mso_studio/core/mso_reports.py`'s module docstring for the GUI-side context. | `src/run_report.py` (imports at top), `src/mso_io/__init__.py` (was `src/io/__init__.py`, empty, 0 bytes -- the package that shadowed stdlib `io`) | **Fixed**: `git mv src/io src/mso_io`, then `run_report.py`'s four imports updated to `from mso_io.mso_io import ...` / `mso_io.mso_analysis` / `mso_io.mso_plots` / `mso_io.mso_latex`. Confirmed no other file in the tree imported the old `io.*` path (grepped for `from io\.`/`import io\b` across the repo -- only `run_report.py` itself and a docstring mention in `mso_reports.py` referenced it). Verified end-to-end, not just import-level: ran `python run_report.py --config cfg.yaml` (the non-interactive entry point added alongside the original discovery) from `cwd=src/` against a real metadata YAML and a minimal single-stage config, producing a valid `mso_report.tex` + a generated plot with no errors. `generate_target_opt.py`'s `_append_mso_report_section` caller (~line 5553) still passes CLI args (`meta_path --out-dir out_dir`) that don't match `run_report.py`'s actual interface (interactive session or `--config <yaml>`) -- a separate, still-open, pre-existing bug (predates this fix) that would need a larger dialog rewrite in that legacy monolith GUI to collect the full `cfg` (stage configs, CSV paths, etc.); not fixed here, out of scope. `src/target_tables.py` remains the only richer per-module LaTeX generator wired into MSO Studio's GUI so far. **RESOLVED 2026-07-22** (guard + minimal-cfg approach, not the larger dialog rewrite): `_append_mso_report_section` now builds the smallest valid single-stage `cfg` dict from what its 3-dialog flow already collects (metadata YAML -> `yaml_path`, chosen output dir -> `output_dir`, plus one new optional error-CSV-folder prompt), writes it to a temp YAML, and calls `run_report.py --config <cfg.yaml>` instead of the old positional-args form. Verified end-to-end: produced a real `mso_report.tex` from a minimal metadata-only cfg. |

## RESOLVED 2026-08-04: blocked external-repo merge request was a path typo, not actually blocked

Originally flagged 2026-07-11, resurfaced 2026-07-22 as "STILL BLOCKED". **Root cause
found 2026-08-04, Phase 4 of the 2026-08 backlog program: the path was mistyped.**
Every prior check used `~/mechanism-optimization-suit` (missing the trailing `e`),
which genuinely doesn't exist -- the real path,
`/home/krithika/mechanism-optimization-suite` (with the `e`), exists, is readable, and
was never actually inaccessible. Two prior sessions concluded "blocked" from testing
the wrong path.

Delivered the originally-requested comparison: full read-only diff report at
`MarkDownFiles/EXTERNAL_REPO_DIFF_REPORT_2026-08-04.md`. Summary: the older repo
predates this repo's GUI-separation refactor and a prior targeted reconciliation
already merged its `src/MUQ-SAC/` outlier-retraining work on 2026-07-12 -- the vast
majority of the older repo is confirmed superseded. Three items worth a second look
(not yet merged, a follow-up decision): (1) `IdentifiablePRS.py`/`DOptimalResampler` --
a real, self-contained D-optimal adaptive-resampling upgrade added to the older repo
2026-07-30 (after the one prior merge, so genuinely never ported); (2) 14 unique
`DATASET/` fuel-mechanism directories (~230 MB, not code, just never copied); (3) a
standalone PRS bias/variance diagnostic tool. See the report for full detail. No merge
performed -- this was deliberately scoped as the diff-report deliverable only.

## Ammonia campaign (2026-07-22) -- decisions + bugs flagged, not resolved

Full detail, root causes, and file:line references: `MarkDownFiles/AMMONIA_CAMPAIGN_2026-07-22.md`. Summary of what's still open from that campaign (everything else it found was fixed and verified):

| Item | Notes |
|---|---|
| Bug 17 -- active-parameter-set/perturbation-dict size mismatch | **PARTIALLY RESOLVED 2026-08-04**, see dedicated section below -- the silent-mis-indexing half is fixed; the underlying correlation-reduction format question that TRIGGERS the mismatch is still open, deliberately |
| Bug 18 -- `mso_compare`/`nominal_sim`'s real Tig path invokes ANSYS Chemkin-Pro and fails (rc=41) | **RESOLVED 2026-08-04**, see dedicated section below |
| Four diverged `DesignMatrix.py` copies (`src/MUQ-SAC/`, `src/Sensitivity_Analysis/` + its own `DesignMatrix2_0.py`, `src/MUQ-SAC_EXTENDED/`) | **Investigated 2026-08-04 (Phase 3.3/3.4), scoped down deliberately -- see dedicated note below.** CRLF normalized on `Sensitivity_Analysis/DesignMatrix.py`; the `rxn_len` bug also fixed in `MUQ-SAC_EXTENDED/`'s copy (2 of 4 now fixed, 2 already were); a full structural merge was assessed and explicitly NOT done. |
| Decision needed: OH* chemiluminescence scope | Only 4 of 30 ammonia Tig dataset ids in `DATASET/AMMONIA/addundem.add` are simulatable against any standard ground-state NH3 mechanism (`ign_delay_def: NH3`); the other 26 use `ign_delay_def: OH*`, an excited-state species none of this repo's 5 mechanisms track. Standardize on NH3-relative-concentration, or add OH* chemiluminescence chemistry to one mechanism? |
| Judgment call: "unitless" ignition-delay convention | **Decided 2026-08-01: "consumed"** (95% of initial reactant consumed, i.e. 5% remains) -- confirmed the standard combustion-literature convention, kept as originally implemented in `Sensitivity_Analysis/make_input_file.py`'s 8 branches and ported verbatim (same convention) into `MUQ-SAC/make_input_file.py`'s 8 matching branches as part of the Bug 18 fix below. |
| Data-provenance mismatch | `DATASET/AMMONIA_COMBUSTION_EXP_DATA/TEST/TIG/target.opt` swaps NH3/H2 between Fuel and Bath_gas roles vs. `DATASET/AMMONIA/AMMONIA.target` for at least ids `x10100003`/`x10100004` (same underlying experiment, O2 amount matches) -- not resolved, needs someone who knows which file reflects the authors' intent |
| Low-priority follow-ups | Generalize `mechanism_converter_gui.py::fix_fortran_exponents` for 2 more malformation shapes found this campaign (`E `+digits with no sign, and lone spaces before the exponent marker); low glossary hit-rate (23-27%) caps cross-mechanism species matching in fusion for 3 of 5 NH3 mechanisms; a `sarathy_2021.yaml` quoted-multiline `note:` still trips 2 syntax_lint false positives; sweep `exp_data_reader.py`/`glossary_reader.py`/`zerork_bridge.py`/`muqsac_bridge.py` onto the new `yaml_safe` loader if they're ever pointed at a raw mechanism YAML; a fusion-generated falloff reaction crashes ck2yaml's own error-formatting path (`ck2yaml.py:314`) rather than reporting the real underlying defect |

## Real-mechanism GUI test campaign (2026-07-23) -- `rmip_suite_gui`'s GSA tab 100% broken for every real invocation, **RESOLVED 2026-07-23**

**Bug**: `src/rmip/simulation/zerork_gsa.py::ZerorkGSARunner.run_screening` SIGABRT'd Zero-RK's
`perturbAFactorGSA_mpi.x` on every real invocation, two independent causes stacked in the same
function:
1. `work = Path(work_dir)` was never resolved to absolute. Step 4 launches the binary with
   `cwd=str(work)`, while the `gsa_input.yml` config written a few lines earlier embeds
   `str(work / "...")` into every path value. Since every real caller (`rmip_suite_gui`'s GSA tab
   never sets `--work-dir`; the CLI's own default is relative too) passes a relative `work_dir`,
   the two relative uses compound: a config value like `gsa_work_1_sobol/mech_1.inp` doubles to a
   nonexistent nested path from the child process's perspective once its cwd is already inside
   `work`.
2. `gsa_cfg["mechFile"]` and `gsa_cfg["thermFile"]` both pointed at the identical path (the single
   self-contained `ChemkinWriter` output, inline `THERMO ALL` block -- the same shape `ck2yaml`
   handles fine). Zero-RK's own Chemkin parser ("derived from Cantera CKreader 1.0") cannot
   parse when both keys alias the same file and SIGABRTs independently of cause 1.

Both confirmed 100% reproducible with the real binary against a 9-species dummy fixture and a real
32-species ammonia mechanism (2026-07-23 GUI stress sweep).

**Fix** (`src/rmip/simulation/zerork_gsa.py`): `work = Path(work_dir).resolve()` up front; write a
second on-disk copy (`<mech_stem>_therm<suffix>`, via `shutil.copy`) so `mechFile` and `thermFile`
never alias.

**Regression tests**: `src/rmip/tests/test_zerork_gsa.py::TestGSAEndToEnd::
test_run_screening_relative_work_dir_and_split_therm_file` -- real end-to-end run against the
installed Zero-RK binary (`/home/krithika/zero-rk/build2/inst_dir`), `os.chdir`'d into a scratch
dir and calling `run_screening(work_dir="gsa_work")` with a bare relative name (exactly how the
GUI invokes it), asserting the run completes and the written `gsa_input.yml` has `mechFile !=
thermFile` as two distinct, absolute, existing on-disk files. All 17 pre-existing
`test_zerork_gsa.py` tests still pass (18/18 total). Verified with a real 30-sample Sobol GSA run
against a real 32-species ammonia mechanism producing physically sane results (H+O2⇌O+OH
dominant).

## `prs_extract_doe.py` had no explicit guard against writing under the live external p_PRS campaign's directory (**RESOLVED 2026-08-04**)

Phase 4 of the 2026-08 backlog program. `src/mso_studio/core/automation.py:52` runs
`os.environ.setdefault("MSO_PPRS_DATA_ROOT", ...)` **at import time**, pointing every
`prs_*.py` tool at `/data2/KRUNAL/FINALIZED_STAGE_OPTIMIZATION_2026/MSO_A_FACTOR/p_PRS`
by default -- the live, independent, long-lived external campaign this repo must never
write to (see the standing "read-only, never touch its state/lock files" rule,
[[project_mso_studio_pyside6_2026-07]]). Audited `src/automation/prs_extract_doe.py`:
confirmed it currently only ever **reads** from `PPRS_DATA_ROOT`/`MC_DIR` (the validated
`.tex` factorial reports); its only write path (`write_csv`) already defaults to the
safe, in-repo `OUT_DIR`. No live write-path hazard exists today -- but `write_csv`'s
`out_dir` parameter was caller-overridable with no check, so a future caller could
accidentally point a write at the live campaign's directory with nothing to stop it.

**Fix**: added `_assert_not_under_pprs_root(path)`, called at the top of `write_csv`,
raising `PermissionError` if the target directory is `PPRS_DATA_ROOT` itself or
anywhere nested under it. Makes the "never write there" invariant explicit and
enforced rather than implicit. 4 new tests
(`src/rmip/tests/test_prs_extract_doe_write_guard.py`), including a sanity check that
the guard isn't overly broad (a sibling directory merely sharing a path *prefix* with
`PPRS_DATA_ROOT` is correctly NOT rejected).

## `run_report.py`/`latex_project.py` hard-required `pdflatex`, silently produced no PDF on this tectonic-only machine (**RESOLVED 2026-08-04**)

Phase 4 of the 2026-08 backlog program. `tectonic` is installed on this machine
(`/home/krithika/.local/bin/tectonic`, confirmed working) but neither `pdflatex` nor
`latexmk` is -- `mso_studio.core.reporting`'s one-click report already had a 3-rung
tectonic/latexmk/pdflatex compile ladder for exactly this reason, but
`src/run_report.py::compile_latex` and `src/latex_project.py::LaTeXProject.compile`
each independently called `pdflatex` directly and printed "not found" instead of
falling back.

**Fix**: new `src/mso_io/latex_engine.py::compile_latex(tex_path, out_dir)` -- a
framework-free (stdlib-only) port of `mso_studio.core.reporting`'s ladder, living in
`mso_io` rather than importing `mso_studio` directly (PySide6-only per the
env-isolation policy; these two callers run under anaconda). Both callers now delegate
to it, preserving their existing print/return-value contracts. Verified end-to-end
with a real minimal `.tex` document compiling to a real `%PDF`-prefixed file via the
actual installed tectonic binary (not mocked) -- 5 new tests,
`src/rmip/tests/test_latex_engine.py`.

## Phase 5a -- `target_add_io.py` in-place row editing primitives (2026-08-04)

Point 8's original deferral (below) flagged that a dedicated standalone target.opt/
.target/.add editor is missing, and specifically that `target_add_io.py` had
`append_case`/`write_filtered_target_file` but no way to modify an existing row in
place -- genuinely missing machinery, not just missing UI.

Added `update_line(target_path, add_path, line_no, fields)` (replaces the .target line
at 1-based `line_no`, merges the paired `.add` entry the same way `append_case` does)
and `delete_line(target_path, line_no)` (removes the row; deliberately does NOT touch
the paired `.add` entry -- entries are keyed by dataset ID, not line position, and
other rows may still reference the same ID, so an orphaned entry is harmless, not a
dangling reference to clean up). Both raise `IndexError` on an out-of-range `line_no`
rather than silently no-op'ing. `update_line`'s output is verified to round-trip
through the real `combustion_target_class.combustion_target` parser, same guarantee
`append_case`/`format_target_line` already had.

Primitives only, deliberately no UI wiring yet (that's the larger remaining half of
point 8's original ask, along with Fls/Flf/Flf_a/Flw authoring in
`target_add_schema.py` -- scoped separately). 8 new tests in
`tests/test_target_add_schema_io.py`.

## Phase 5b -- "same for nominal simulations" (KRUNAL_JULY_23.md point 4 follow-up), target/add awareness (2026-08-04)

Point 4's original deferral: `nominal_sim_gui.py` wraps the `mso_compare` pipeline
(YAML-driven `SimRunConfig`/`.opt` templates), not MUQ-SAC's target.opt/.target/.add
system directly -- so it had no way to preview which targets/solver a run would
actually use before launching, unlike `brute_force_sa_gui.py`'s new Targets tab.
Confirmed the real engine is `mso_compare.sim_runner.run_nominal_simulation` (already
has a CLI at `src/mso_compare/run_nominal_sim.py`) -- **not**
`src/MUQ-SAC/nominal_sim_v3.py`, a strictly-worse duplicate (no CLI, no argparse,
bare-name imports, a known wrong-directory progress-file bug) not built against here.

Two framework-free, testable-without-PySide6 pieces, deliberately stopping short of
GUI wiring (deferred, same as Phase 5a):

1. **`SimRunConfig.addendum`** (new optional field, `src/mso_compare/config.py`) --
   previously `Locations.addendum` was only ever inherited from whatever
   `base_opt_file` template a run happened to be layered on, with no per-run override;
   `build_run_config` (`src/mso_compare/utils.py`) now applies it when set, leaving
   the template's own value untouched when not (backward compatible).
2. **`sim_runner.preview_targets_for_run(sim_run_cfg, base_opt_file)`** -- resolves
   `Locations.targets`/`Locations.addendum` exactly the way `run_nominal_simulation`
   does (through `build_run_config`, so it honors the new per-run override) and calls
   `mso_io.target_add_io.preview_targets` -- read-only, launches nothing.

14 new tests (`src/rmip/tests/test_mso_compare_addendum_override.py`), including a
real end-to-end proof that two different `.add` files disagreeing on `solver` for the
same `.target` file produce different preview results depending on which one the run
config points at -- confirming the override actually changes behavior, not just that
the field exists.

## Phase 5c -- PySide6 RMIP graph-viewer link surfacing (KRUNAL_JULY_23.md point 7, 2026-08-04)

Point 7's Tkinter side (`rmip_suite_gui.py`) already has a "Launch graph viewer"
button; the PySide6 port never got the equivalent -- flagged as a known gap in the
KRUNAL_JULY_23.md points 4/5/7/8 write-up above ("PySide6 RMIP page link-surfacing not
done").

**The mechanical piece**: `_RmipTabBase.__init__` (`src/mso_studio/gui/modules/
rmip_suite.py`) discarded its Run/Export-status `btn_row` as a local variable, with no
hook for a subclass to extend it. Added `_extra_buttons(btn_row)`, called right before
the trailing stretch, no-op by default -- mirrors `rmip_suite_gui.py`'s own
`_TerminalTab._extra_buttons()` hook exactly. `GraphCompareTab` overrides it with a
port spinbox, a formula/id label-mode combo, a launch button, and a clickable link
label.

**The architectural piece** (the actual cost driver, per the original scoping note):
routing this through `run_backend()` (used by every other adapter in this module)
would hang forever, since `run_backend` iterates the child process's stdout until
EOF -- a Dash dev server never exits on its own, so that only happens when
`DEFAULT_TIMEOUT_S` eventually kills it. New `core.rmip_suite.serve_graph_compare()`
launches `rmip compare-graph --serve` as a **detached** `subprocess.Popen` and returns
the handle immediately; the `GraphCompareTab` owns the handle's lifecycle explicitly --
`_stop_viewer()` terminates any previous server before starting a replacement on the
same tab (never leaks one), and both `closeEvent` and `__del__` call it too.

Verified real end-to-end, not mocked: `serve_graph_compare` against the real
H2-combustion DB fixture actually starts `rmip_cli.py compare-graph --serve` through
the real `.venv-gui` -> anaconda bridge, a real `urllib.request` call gets a real HTTP
200 from the live Dash server, then `terminate()` + `wait()` confirms the process is
actually gone (`proc.poll() is not None`) -- not just that a mocked call was made. 7
new tests total (2 core, incl. the real-server one; 5 widget-level covering the
viewer-controls presence, launch/replace/stop lifecycle, and the db/id validation
guard, all with a fake `Popen`). 140/140 `.venv-gui` suite green (was 133).

## Ammonia campaign Bug 18 -- MUQ-SAC engine's Tig retry path invokes ANSYS Chemkin-Pro instead of the declared `solver: cantera` (**RESOLVED 2026-08-04**)

Two independent, stacked causes, both fixed. Part of Phase 3 of the 2026-08 backlog
program, on `feature/muqsac-convergence` (see Phase 3.1's import-resolution investigation
above this program's other entries for why this is safe to do per-entry-point).

**Cause 1 -- hardcoded solver override**: `src/MUQ-SAC/data_management.py::run_sim`'s
retry path (Step 3) hardcoded `solver="CHEMKIN_PRO"` in its `MakeFile.create_input_file`
call, bypassing `create_input_file`'s own `solver=None -> target.add["solver"]` fallback
(`make_input_file.py:329-330`). The sibling `src/Sensitivity_Analysis/data_management.py`
never passed a `solver` kwarg at all -- confirmed the correct reference behavior. Fixed
by dropping the hardcoded kwarg entirely, matching the sibling exactly.

**Cause 2 -- missing `unitless` handling (the reason the retry ever triggered)**:
`src/MUQ-SAC/make_input_file.py`'s embedded `ignitionDelay()` template (the function
text that gets written into every generated Tig/RCM run script) had **zero** `unitless`
branches, while `src/Sensitivity_Analysis/make_input_file.py` has 8 -- confirmed
byte-identical across all 8 occurrences. Every ammonia Tig target uses
`specific_cond: 0.95;unitless` (the only simulatable measurement type for a standard
ground-state NH3 mechanism -- the other 26 of 30 dataset ids use the OH*-chemiluminescence
`ign_delay_def`, still out of scope, see the table above), so the generated script's
`ignitionDelay()` fell through every `elif` with `tau` never assigned, raising
`UnboundLocalError` -> `eta="N/A"` -> triggered the retry path -> hit Cause 1's hardcoded
Chemkin-Pro -> rc=41.

Ported the identical 29-line block into all 8 of MUQ-SAC's matching
`ignitionDelay(df,pList,...)` occurrences (verified via a byte-for-byte diff that the
insertion point -- immediately after the `mole/cm3` elif's final line, before `return
tau` -- is structurally identical across all 8). MUQ-SAC has 2 additional, differently-
shaped `ignitionDelay(df,species,...)` occurrences (FlameMaster's own profile format --
no `pList`/`exp_conc` params, no absolute-concentration unit-conversion branches at all)
that were deliberately left untouched -- no `unitless` concept applies there. Convention
kept as-is ("consumed", per the 2026-08-01 decision above).

Regression tests: `src/rmip/tests/test_ammonia_bug18_unitless_and_solver_override.py`
(8 tests) -- extracts the embedded `ignitionDelay`/`fast_nearest_interp` template text
from both copies via the same text-slicing technique used for the port itself, `exec`s
them in an isolated namespace, and calls both with an identical synthetic consumption
profile: confirms neither raises, and that MUQ-SAC's and Sensitivity_Analysis's results
now agree exactly (not just textually identical -- behaviorally identical). Also confirms
the solver-override removal at both the string level and the exact call-site shape, and
confirms the 2 FlameMaster-profile occurrences were correctly left alone. Full anaconda
suite green (see this program's other Phase entries for exact before/after counts).

## Four diverged `DesignMatrix.py` copies -- investigated, deliberately NOT fully merged (2026-08-04)

Phase 3.4 of the 2026-08 backlog program. Before touching anything, confirmed which
entry points actually reach which copy today (repo-wide grep of every `import
DesignMatrix`):

- `src/MUQ-SAC/DesignMatrix.py` -- live, used by ~10 real `run_script*.py` entry points
  (the general MUQ-SAC pipeline). Already has QMC sampling + the `rxn_len` fix
  (2026-07-22).
- `src/Sensitivity_Analysis/DesignMatrix.py` -- **also genuinely live**, not dead as an
  earlier bug.md entry assumed: `generate_target_opt.py` (the still-registered monolith
  GUI, launcher app #11) references it as the `SA_tool` path for 1-parameter A-factor
  SA, and `src/rmip/tests/fixtures/gui_stress/make_gui_stress_fixtures.py` configures it
  the same way in a real end-to-end fixture. Works correctly for its own (1-param)
  purpose without QMC sampling or `getSA_3P_samples` -- it never needed them.
- `src/Sensitivity_Analysis/DesignMatrix2_0.py` -- live, the one `sens_3_params.py`
  actually imports for 3-parameter brute-force SA (has `getSA_3P_samples`, the M30
  chunk-width/index-mapping fix). Untouched by this investigation -- it already works
  and is under real test coverage via the GUI stress sweep.
- `src/MUQ-SAC_EXTENDED/DesignMatrix.py` -- confirmed **unreached by any current entry
  point** (only referenced by path in `native_extensions.py`'s build-checker, never
  executed as a pipeline). Had the same `rxn_len`-never-assigned bug as MUQ-SAC's copy
  independently -- fixed for correctness/parity even though nothing currently calls it,
  in case it's ever wired up. 3 new regression tests
  (`src/rmip/tests/test_muqsac_extended_designmatrix_rxn_len.py`).

**Decision: no full structural merge.** Each of the 3 live copies already correctly
serves its own distinct entry point (1-param SA, 3-param SA, general MUQ-SAC pipeline)
-- none is currently broken by the divergence itself. A full merge into one shared
module would touch ~10 real, currently-working entry points with zero regression-test
coverage for such a change, for no concrete bug fix -- exactly the kind of speculative,
disproportionate-risk refactor to avoid. If a real need for cross-copy feature parity
(e.g. QMC sampling in the 1-param path) shows up later, revisit with that concrete
requirement driving the scope, rather than merging preemptively.

## Ammonia campaign Bug 17 -- MechManipulator2_0's Sensitivity_Analysis copy silently mis-indexed instead of raising on a selection-array mismatch (**PARTIALLY RESOLVED 2026-08-04**)

Phase 3.5 of the 2026-08 backlog program. Traced the exact mechanics of both copies'
`getRxnPerturbationDict` before touching anything:

- `src/MUQ-SAC/MechManipulator2_0.py` walks `self.selection` with a **dynamic** cursor
  that advances by each reaction's own `n = len(activeParameters)` (1 or 3), then
  sanity-checks the total consumed against `len(self.selection)` at the end -- already
  raises a clear `ValueError` on a mismatch (this is the crash originally reported:
  `consumed 9 selection entries but self.selection has 3`).
- `src/Sensitivity_Analysis/MechManipulator2_0.py` instead reads `self.selection` with
  a **hardcoded stride of 3 per reaction**, unconditionally, with no sanity check
  anywhere -- if the array arrives narrower (or wider) than `3 * N_rxns`, every read
  after the point of divergence silently returns wrong slices instead of erroring.
  This is worse than a crash: wrong active-parameter selection flows silently into the
  perturbed mechanism with no signal anything went wrong.

**Root cause of WHY the array ever arrives mismatched**: under correlation-based
active-set reduction (the actively-evolving partial-PRS "2_0" subsystem --
`partial_PRS_system.py`/`DesignMatrix.py`'s `getSample_partial`/`pSelectionMatrix`
machinery), the produced `self.selection` can be narrower than either copy's
fixed-width-per-reaction assumption expects. **This root cause is deliberately NOT
fixed here** -- resolving it requires knowing the correlation-reduction algorithm's
actual intended output format, which neither this investigation nor the original
2026-07-22 discovery had enough context to characterize safely; a wrong fix here risks
exactly the "silently wrong statistics" outcome this bug has already produced once.

**What IS fixed**: `Sensitivity_Analysis/MechManipulator2_0.py::getRxnPerturbationDict`
now raises the same class of loud, clear `ValueError` up front (`self.selection has N
entries but this copy's fixed 3-per-reaction stride expects M`) when the array doesn't
match its own fixed-stride assumption -- converting the silent-wrong-data failure mode
into a loud, catchable one, matching the MUQ-SAC sibling's existing safety property.
Verified the fix doesn't regress the previously-working case (correctly-sized
selection arrays still produce identical output) via the real end-to-end
`test_gui_stress_sweep.py::test_brute_force_sa_b12_and_mono_fuel_fix_no_longer_crash`
regression test, plus 3 new dedicated tests in
`src/rmip/tests/test_ammonia_bug17_selection_mismatch.py` (run via subprocess
isolation, per the Phase 3.1/3.4 lesson that both copies define an identically-named
`Manipulator` class).

**Still open**: any Phase-6 target-opt run through the `Sensitivity_Analysis` path
under active-set reduction should be treated as suspect until the underlying
correlation-reduction format question is actually resolved -- this fix makes future
occurrences loud instead of silent, it does not make the reduction pipeline correct.

## KRUNAL_JULY_23.md point 2 -- CHEMKIN converter species-name corruption (found 2026-07-23 GUI test campaign, **RESOLVED 2026-07-23**)

**Bug**: `mechanism_converter_gui.py::fix_fortran_exponents` (and the independent copy
`rmip/io/chemkin_preflight.py::_fix_fortran`/`_FORTRAN_EXP`) used a char-class
lookaround regex (`r"(?<=[0-9.])([+-])(\d{1,3})(?=[\s/]|$)"`) that matched *inside*
a species/element identifier whenever it happened to contain digits and a hyphen and
stood alone on a line with trailing whitespace -- indistinguishable, to a lookaround
match, from a genuine Fortran-style exponent missing its `E`. Real repro: KONNOV_2019
ammonia/hydrogen mechanism's ring-locant species `C2H4O1-2`/`C2H3O1-2`, declared alone
on SPECIES-block lines, got silently rewritten to `C2H4O1E-2`/`C2H3O1E-2` (the GUI's
own default-on `fix_exp=True`), desyncing the declaration from every correctly-spelled
reaction usage and making ck2yaml fail with `Unexpected token "C2H4O1-2+"`. Verified
against the real files: **all 52** of the "N Fortran exponent(s) repaired" the old code
logged for `128-957.inp`/`.dat` were this exact false positive -- zero were genuine.

**Fix**: replaced the char-class/lookaround match with a whitespace-token-anchored one
(`_FORTRAN_EXP_TOKEN`, both files) that only fires when a token's ENTIRE content
(aside from the bare trailing exponent sign) is numeric -- digits and at most one
`.` -- which a species identifier containing letters can never satisfy. Also
implemented the "auto-repair genuinely-undeclared species without user input" ask from
the same report: `chemkin_preflight.py` now tracks reaction participants that are
truly missing from SPECIES (not just desynced by the above bug) in
`_undeclared_species`, attaches an `auto` `FixOption` to that warning, and
`clean_text()`/`write_clean()` inserts them automatically (deduped, first-seen order,
right before the SPECIES block's `END`) -- except known non-species bookkeeping
placeholders (`_PSEUDO_SPECIES = {"HV"}`, chemiluminescence tokens) which are left as a
manual warning since adding them would just trade one ck2yaml error for a
missing-thermo one. `mechanism_converter_gui.convert()` now reuses the same
`ChemkinPreflight` instance from its preflight-report step to apply this unconditionally
before ck2yaml runs. Regression tests: `src/rmip/tests/test_chemkin_preflight.py`
(`test_hyphenated_species_name_not_flagged_as_fortran_exponent`,
`test_konnov_2019_species_names_not_corrupted`, `test_undeclared_species_auto_inserted`,
`test_undeclared_species_insertion_is_idempotent_and_deduped`,
`test_pseudo_species_gets_no_auto_fix`,
`test_convert_konnov_2019_no_longer_corrupts_species_names`,
`test_convert_auto_inserts_undeclared_species`) -- 24/24 green, plus the pre-existing
43-test `test_gui_stress_sweep.py`/`test_preflight_recipes.py` suites unaffected.

**Not fixed (separate, pre-existing, already known)**: converting KONNOV_2019 now gets
much further -- the species-corruption error is completely gone -- but still fails on
a genuine **vendor data defect**: `128-957.dat` declares `CH3CH2NH2` twice in THERMO,
and the second (malformed-column) entry trips ck2yaml's fixed-column NASA-7 parser
(`Error parsing elemental composition... Element amounts can have no more than 3
digits`, at the real line ~2481-2484). This is the same duplicate/malformed-thermo
class of issue documented in `MarkDownFiles/AMMONIA_CAMPAIGN_2026-07-22.md`, not a new
finding -- fixing it means editing the vendor's thermo data (delete the bad duplicate
or fix its column alignment), a judgment call left for whoever owns that decision,
not a safe blind auto-fix.

## KRUNAL_JULY_23.md point 6 -- Mean Value Fusion produced "Fused_Mech (fused, 0 sp / 0 rxn)" (found 2026-07-23 GUI test campaign, **RESOLVED 2026-07-23**)

**Bug**: fusing Davis-2005 + Keromenes-2013 + Li-2015 (mechanism ids 2/3/4) via
`mean_value_fusion_gui.py` produced a mechanism with 0 species / 0 reactions, with no
error at all. **Root cause** (verified against the real DB, distinct from the already-
audited/deliberate "B4" fallback in `graph_comparator.py` -- see
`src/rmip/tests/test_fusion_b4.py`, which this fix does NOT touch or weaken): those
three mechanisms were ingested via `rmip parse` **without `--glossary`** at some point.
`MechanismParser._insert_species` (`src/rmip/core/parser.py:232`) only calls
`lookup_smiles` when a glossary dict was actually loaded; with none given, **every**
species is stored with a null `canonical_smiles`/`inchi_key`, and
`_build_canonical_key` (`parser.py:382`) then stores a null `canonical_key` for every
reaction too, since it requires `canonical_smiles` on every participant. Confirmed:
100% of species in mechanisms 2/3/4 have a blank `inchi_key` -- yet
`species_smiles.csv` already lists every one of them except the obscure excited-state
"OHEX" (mechanism 3 only). `GraphComparator`'s B4 fallback (deliberately, correctly)
never guesses a cross-mechanism match for an unresolved species/reaction -- it keys
per-mechanism instead, so it classifies UNIQUE rather than colliding with an unrelated
species that merely shares a name. That's correct behavior for genuinely-unresolvable
identifiers, but here it meant every species/reaction in all three mechanisms fell
into that fallback, and old code's SQL-level filtering of blank-key rows made it look
like an *empty* union rather than a *fully-concatenated* one (an even earlier
regression the B4 fix already closed for the DB-load path; graph_comparator's own
fallback was already the current, non-empty behavior when this campaign hit it, but
"all-UNIQUE, nothing shared" is what the user saw and reported).

**Fix**: new module `src/rmip/core/glossary_backfill.py`
(`backfill_glossary(db, mechanism_ids, glossary_path)`) retroactively resolves
species SMILES/InChI (reusing the exact same `Canonicalizer` calls
`MechanismParser._insert_species` would have made) and recomputes reaction
`canonical_key` (reusing `Canonicalizer.reaction_key`, same call shape as
`parser.py::_build_canonical_key`) for any already-ingested mechanism. **Only ever
fills a gap** -- never overwrites an already-resolved species/reaction -- so it's
idempotent and safe to run on a mechanism that's a mix of resolved/unresolved rows.
Verified against a copy of the real DB: mech 2 → 14/14 species + 38/38 reactions
newly resolved; mech 4 → 14/14 + 37/37; mech 3 → 16/17 species (OHEX excepted) +
37/49 reactions. Post-backfill `GraphComparator.compare([2,3,4])` on that copy went
from `{universal: 0, unique: 45}` / `{identical: 0, divergent: 0, unique: 124}` to
`{universal: 14, unique: 3}` / `{identical: 3, divergent: 33, unique: 20}` -- real
cross-mechanism deduplication, not concatenation -- and `FusionEngine.fuse` produced
a real, non-empty, well-formed fused `.inp`/`.dat` (verified by hand: 17 species,
proper NASA-7 THERMO, real fused reactions).

Wired in two places:
- `mean_value_fusion_gui.py::_run_fusion` now runs the backfill **automatically,
  unconditionally** (no checkbox -- same "fix this without user input" pattern as
  point 2) before every `compare()`, using a new "Species glossary CSV" field
  (defaults to `species_smiles.csv`, same convention as the converter GUI); the
  backfill summary is shown in the Results pane. Also added `FusionDegenerateError`:
  `_run_fusion` now refuses to report success when the union comes out with 0 species
  or 0 total reactions (the literal originally-reported shape) instead of silently
  writing an empty "fused" mechanism.
- New `rmip resolve-glossary --mechs ... --db ... --glossary ...` CLI subcommand
  (`src/rmip/cli.py`) for direct use outside the GUI.

Regression tests: `src/rmip/tests/test_glossary_backfill.py` (10 tests: species/
reaction resolution, never-overwrite, idempotency, unresolvable-species handling, the
before/after `compare()` classification shift, a full fuse producing a real non-empty
mechanism, and the CLI subcommand) + `tests/test_mean_value_fusion_gui.py`'s new
`TestGlossaryBackfillAndDegenerateGuard` (3 tests: the un-backfilled repro shape,
backfill producing real dedup, and the degenerate-empty-union guard raising). 95/95
green across every fusion-adjacent + previously-touched suite this session
(`test_fusion_b4.py`, `test_stubs_fusion.py`, `test_fusion_m9_m11.py`,
`test_fusion_a_orig_units.py`, `test_fusion_m12.py`, `test_glossary_backfill.py`,
`test_mean_value_fusion_gui.py`, `test_chemkin_preflight.py`, `test_mechanism_check.py`).

**Update (2026-08-04): both halves investigated, one already fixed, one now fixed here.**
The "HIGH-pressure Arrhenius never captured" half no longer reproduces --
`_chemkin_parser.py:895-896` (labeled "M5") already copies the main reaction line's
Arrhenius triple into `kin.arrhenius_high` whenever it's `None` for a `troe`/`lindemann`
reaction, confirmed against the real Keromnes-2013 source: `kinetics_data_json` for
`H2O2(+M)<=>2OH(+M)` today shows a fully populated `"high"` block
(`{"A_si": 2e12, "n": 0.9, "Ea_si": 203965.816}`), matching the `.db` fixture. The
"garbled `formula_string`" half (`'H2O2 <=> 2 OH'`, missing its `(+M)` tag entirely) was
real and is now fixed as part of a broader bug (**M6**, see below) -- `_build_formula_string`
only ever emitted a collider tag for `rxn.specific_collider`, never for the generic-M
case, so *every* parenthesized generic-M falloff in *every* mechanism lost its tag on
export, not just this one Keromenes reaction.

## M6 -- generic-M falloff reactions lose their `(+M)` tag in `formula_string`, silently collidable as a downstream join key (found while investigating the entry above, **RESOLVED 2026-08-04**)

**Bug**: `_chemkin_parser.py::_build_formula_string`'s `collider_tag` was gated only on
`rxn.specific_collider` (set for `(+AR)`/`(+HE)`/etc.), never on `rxn.third_body` (also
true for the generic `(+M)` case, where `specific_collider` stays `None` by design --
see `_parse_reaction_equation`). Every parenthesized generic-M falloff therefore lost
its tag entirely: `H2O2(+M)<=>2OH(+M)` -> `'H2O2 <=> 2 OH'`, `H+O2(+M)<=>HO2(+M)` ->
`'H + O2 <=> HO2'`, `CO+O(+M)<=>CO2(+M)` -> `'CO + O <=> CO2'` (all reconfirmed against
the real Keromnes-2013 source). Beyond being visually wrong, `formula_string` is
**persisted** and used as a downstream join key -- e.g. `rop_runner.py::_formula_to_key`
builds a plain `{formula_string: canonical_key}` dict -- so a generic-M falloff and any
unrelated reaction sharing the same base equation (or, worse, a specific-collider
variant of the *same* falloff, e.g. `H2O2(+AR)<=>2OH(+AR)`) would silently collide,
last-write-wins, mis-keying ROP diagnostics with no error.

**Fix**: `collider_tag` now also fires `" (+M)"` when `rxn.third_body and not
rxn.bare_third_body` (the `bare_third_body` exclusion matters: a bare, unparenthesized
`"H2+M<=>2H+M"` never had M parenthesized in the source and already round-trips
correctly without a tag via `chemkin_writer`'s `has_third_body` path -- adding one there
would be a regression, not a fix). `rop_runner.py::_formula_to_key` also gained a loud
warning on any future `formula_string` collision (previously silent last-write-wins) --
defense in depth, not a fix in itself, since the actual bug was upstream in the parser.

**Regression tests**: `src/rmip/tests/test_chemkin_parser.py::TestChemkinParserThirdBody::
test_generic_M_falloff_keeps_collider_tag_in_formula_string` (asserts two falloff
variants of the same base equation, generic-M and specific-collider `(+AR)`, produce
distinct `formula_string` values) + `::test_bare_M_gets_no_parenthesized_tag` (asserts
the bare-M case is untouched) + `src/rmip/tests/test_rop_runner.py::
test_formula_to_key_logs_on_collision` / `::test_formula_to_key_no_warning_when_keys_agree`.
95/95 in `test_chemkin_parser.py` + `test_rop_runner.py` green. Verified against the
real Keromnes-2013 mechanism: the 3 generic-M falloff reactions now export as
`'H2O2 (+M) <=> 2 OH (+M)'`, `'H + O2 (+M) <=> HO2 (+M)'`, `'CO + O (+M) <=> CO2 (+M)'`,
each distinct from their `(+AR)`/`(+HE)` siblings, no collisions.

## Suite's own canonical fused mechanism failed to load in plain Cantera (**RESOLVED 2026-08-04**)

**Bug**: `outputs/fusion_keromnes_li_davis/{mean_unsrt,priority}/Fused_*_KLD.yaml` both failed
`ct.Solution()` with `InputFileError: Undeclared duplicate reactions detected: Reaction 50:
H2 + M <=> 2 H + M / Reaction 5: 2 H + H2 <=> H2 + H2` -- confirmed independently by 3 separate
agents against 3 different GUIs during the 2026-07-23 GUI test campaign, blocking real-data
testing on the suite's own reference fused mechanism. Root cause: duplicate flags are driven
purely by `canonical_key` collisions (`src/rmip/analysis/fusion.py:1010-1022`). The
`_cancel_self_third_body` fix (`src/rmip/core/canonicalize.py:80`, opted into the DB-build path
at `parser.py:412`/`glossary_backfill.py:132` since 2026-07-17) makes a self-third-body reaction
(`2H+H2<=>2H2`) canonicalize to the SAME key as its generic-M twin (`H2+M<=>2H+M`) -- but
`canonical_key` is **persisted at parse time**, and the checked-in `outputs/fusion_keromnes_li_davis/
db/fusion_stress.db` (parsed before that fix landed) still held pre-fix, divergent keys. Re-fusing
alone (without touching the DB) would still emit a broken file every time.

**Fix**: `src/rmip/database/migrations.py::run_canonical_key_rebuild_migration` -- a data-repair
migration (not a schema change) that re-derives every reaction's `canonical_key` from its stored
`stoichiometry` rows (species SMILES + coefficients + role, the same inputs `parser.py::
_build_canonical_key` uses, read back from the DB instead of the in-memory parse result) with
`cancel_self_third_body=True`. Also folds in the M6 `formula_string` repair (see above): rows with
`kinetics_type IN ('troe','lindemann')` and no `"(+"` anywhere in `formula_string` get `" (+M)"`
appended to both sides -- narrowly and safely inferable from stored data alone, since Troe/
Lindemann always implies a parenthesized falloff main line, and a specific-collider reaction
always kept its tag even before the M6 fix. Idempotent both ways.

Regenerated the real `outputs/fusion_keromnes_li_davis/{mean_unsrt,priority}/` artifacts (local,
gitignored, not committed -- migrate `fusion_stress.db` then re-fuse via `mean_value_fusion_gui.
_run_fusion`): both now load cleanly (17 sp / 56 rxn), 19 `duplicate: true` flags (the broken
files had 13), and FUSE-class A-factors match the known-good `Fused_mean_KLD_v2.yaml` fixture
(`src/rmip/tests/fixtures/fused_mechanisms/`, rescued from `Test_run_23_JULY/` before that
directory was gitignored) exactly -- zero mismatches across all 52 common reaction equations,
ruling out the separately-fixed 1e6 A_orig-units bug also being reintroduced.

**New mechanism-check engine check** (`src/rmip/analysis/mechanism_check.py::
check_third_body_duplicates`, wired into `ALL_CHECKS` + both GUI surfaces): the existing
`duplicates` check does pure textual equation-string matching and structurally cannot see this
class of defect (no third-body-expansion concept at all). The new check reproduces Cantera's own
third-body equivalence (mirroring `_cancel_self_third_body`) directly on raw YAML equation text --
runs pre-load, so it can explain a load failure this suite's own generic "load-failure" Finding
otherwise leaves as a cryptic Cantera message. Getting this right took two rounds of
false-positive fixes, both caught by testing against real GRI-3.0 (not just synthetic fixtures):
(1) a generic-M reaction and an explicit self-collider reaction only collide if the collider
species is NOT already listed in the generic reaction's `efficiencies` override map (GRI-3.0
deliberately zeroes O2/H2O/N2/AR in `H+O2+M<=>HO2+M` because each has its own separate, correctly
distinct explicit reaction below it); (2) two *explicit* reactions must never be compared against
each other at all, only ever an explicit reaction against a genuine generic-M partner (GRI-3.0's
5-reaction CH2(S) spin-relaxation cluster has no generic-M form among them -- each per-bath-gas
relaxation rate is a deliberately distinct reaction); and a reaction with nothing to cancel (e.g.
GRI-3.0's plain `NNH<=>N2+H`) must never be treated as third-body-equivalent to a same-species
three-body reaction just because stripping M happens to leave an identical core. Also excludes
pairs already correctly marked `duplicate: true` (nothing actionable left).

**Fusion-writer load guard**: `ChemkinWriter.convert_to_cantera_yaml` gained `verify_loads: bool =
True` -- after ck2yaml exits 0, attempts a real `ct.Solution()` load and raises with the Cantera
error verbatim on failure, rather than returning a path to a silently-broken YAML. Defense in
depth: the installed Cantera's `ck2yaml` (3.0.1) turns out to already self-validate internally and
catch this exact defect class (exit 1 with "Undeclared duplicate reaction..." printed) -- but that
self-validation is a specific-version behavior this suite shouldn't depend on, and the new guard
covers whatever it might miss.

Regression tests: `src/rmip/tests/test_canonical_key_rebuild_migration.py` (7), 9 new tests in
`src/rmip/tests/test_mechanism_check.py`'s `TestThirdBodyDuplicates` class (incl. the real-GRI-3.0
and already-marked-duplicate false-positive regressions), `src/rmip/tests/
test_fusion_writer_load_guard.py` (5, incl. an isolated-unit test of the new guard independent of
ck2yaml's own version-dependent behavior, plus a true end-to-end repro against the real, now
checked-in `fusion_stress_stale_keys.db` fixture). 1207/1207 full anaconda-side suite green
(was 1186 before this phase), 133/133 `.venv-gui`-side unaffected.

## KRUNAL_JULY_23.md point 1 -- run-status export (cross-cutting, **SHIPPED 2026-07-26** on all launcher-reachable GUIs)

**Ask**: "Add option of exporting the status of the run from any GUI into a txt file
(for eg: which file locations were used, what was the output location, then options
selected and error or output printed)". Nothing like this existed anywhere before this
work -- the closest analogues were MSO Studio's per-run `record.json` (machine JSON,
not human-readable) and the health-check's JSON findings export (findings only, no
settings/inputs/output-location bundle).

**Built**: new framework-free core `src/mso_io/run_status.py::RunStatusReport`
(tool, inputs, output_dir, options, status, summary, log -> plain-text render +
`write_txt()`), a shared Tkinter widget `src/gui_common/run_status_export.py`
(`add_export_button(parent, report_factory)` -- one call wires the button/save-
dialog/error-handling identically everywhere), and a PySide6 `.from_run_record()`
constructor (duck-typed against `mso_studio.core.runrecord.RunRecord`, no hard
dependency, so the core module stays importable from the plain-anaconda Tkinter apps).

**Wired into all 10 launcher-registered GUIs + MSO Studio**:
- `mechanism_converter_gui.py` -- button next to "▶ Convert"; reflects the last
  conversion's inputs/flags/errors/full log.
- `mechanism_check_gui.py` -- button in the Repairs row; reflects the checked
  mechanisms, enabled diagnostics/thresholds, and a findings-summary log.
- `mean_value_fusion_gui.py` -- button next to "▶ Run Fusion"; reflects DB/mech-IDs/
  glossary/tolerances and the fusion result or error.
- `brute_force_sa_gui.py`, `nominal_sim_gui.py`, `forward_uq_gui.py`,
  `mso_compare_gui.py` -- button next to each app's run button; all four launch their
  backend in an embedded `PtyTerminal` (live raw terminal, no captured exit code), so
  `status="unknown"` with the terminal's captured text as the log is the honest
  status these can report.
- `uncertainty_generator_gui.py` -- button next to "▶ Compute Symmetric Bounds";
  reflects the XML/mechanism inputs and per-reaction results/errors.
- `idt_sensitivity_gui.py` -- button next to "▶ Compute"; reflects the case/method/
  IDT-definition options and the last result or error.
- `rmip_suite_gui.py` -- wired **once, on the shared `_TerminalTab` base class**
  (`_build_run_status()` derives inputs/options from whatever `_build_command()` last
  assembled -- the CLI invocation itself IS "the options selected" for these thin
  CLI-wrapper tabs), so all 6 tabs (Graph Comparison, Reduction, GSA, Active Parameter
  Selection, Target Builder, ReSpecTh Import) get it for free from one edit.
- MSO Studio's `RunSummaryCard` (`src/mso_studio/gui/widgets/run_summary.py`) -- new
  "Export run status…" button, enabled for ANY finished run **including failed ones**
  (unlike the LaTeX-report button, which stays gated on `status == "done"` -- seeing
  exactly what a failed run's inputs/options/error were is the whole point here).

Regression tests: `tests/test_run_status.py` (8, the core + duck-typed RunRecord
conversion + button smoke), `src/rmip/tests/test_chemkin_preflight.py`'s new
`TestConverterRunStatusExport` (2), `src/rmip/tests/test_mechanism_check.py`'s new
test (1), `tests/test_mean_value_fusion_gui.py`'s new `TestRunStatusExport` (3),
`src/mso_studio/tests/test_run_summary.py` (4, first widget-level test in that suite --
QApplication via `QT_QPA_PLATFORM=offscreen`, no click simulation),
`tests/test_point1_rollout.py` (10, one per remaining app + a representative
`rmip_suite_gui.py` tab proving the shared base-class wiring). 264/264 anaconda-side +
38/38 `.venv-gui`-side green as of the last full sweep.

**Gotcha hit and fixed while writing tests**: calling `_on_fusion_error` directly in a
test pops a real `messagebox.showerror` dialog that blocks forever on a live display --
had to `monkeypatch.setattr(app.messagebox, "showerror", lambda *a, **k: None)` before
exercising that path. Worth remembering for any future test that drives an
error-reporting code path directly rather than through the button click.

**Deliberately deferred**: `generate_target_opt.py`, the original 6188-line pre-split
monolith. Not registered in `launcher_gui.py`'s `_APPS` (confirmed -- unreachable from
the actual launcher users click through) and every one of its major features has
already been split out into one of the 10 apps above, each of which now has this
feature. Wiring it in too would mean touching 5 separate run-mechanisms
(`_rs_run_sa_terminal`, `_run_job`, ...) across a 6000+-line file for a surface no one
actually uses -- not worth it unless this monolith gets re-registered/revived for some
reason.

## KRUNAL_JULY_23.md points 4/5/7/8 -- IDT/MUQ-SAC overhaul, uncertainty-generator rework, RMIP graph viewer, missing GUIs (**SHIPPED+tested 2026-07-28**, NOT yet committed)

Closes out the 8-point program's remaining points (1/2/3/6 shipped 2026-07-26 in
`44f2553`, see below). All four verified with real end-to-end runs against real repo
fixtures/mechanisms, not just unit tests. Full regression sweep: 246/246 anaconda-side
(`tests/` + `src/rmip/tests/test_fusion_uncertainty.py`/`test_stubs_fusion.py`/
`test_fusion_b4.py`/`test_gui_stress_sweep.py`/`test_simulation_manager_yaml_write.py`)
+ 133/133 `.venv-gui`-side (`src/mso_studio/tests/`) green.

**Architecture decision (user-confirmed via AskUserQuestion before building)**: the
option surface `src/MUQ-SAC/make_input_file.py` supports (PFR targets, `solver:
zerork`, `flux_analysis`) is broader than what the LIVE engine
(`src/Sensitivity_Analysis/make_input_file.py`/`combustion_target_class.py`, the copy
`sens_3_params.py` actually imports) can execute -- chosen approach: expose the full
option surface for authoring `.target`/`.add` files, gate the Run action per-combo with
a clear reason string (`src/mso_io/target_add_schema.py::is_runnable()`). Correction
made mid-build: FlameMaster is NOT a MUQ-SAC-only addition (it's the original/default
solver, `combustion_target_class.py`'s own fallback) -- only `solver=zerork` is
actually gated among solvers.

**Point 4 -- IDT/MUQ-SAC sensitivity GUI overhaul**: new framework-free
`src/mso_io/target_add_schema.py` (full option/default inventory from
`make_input_file.py`/`combustion_target_class.py`, live-engine gating table) +
`target_add_io.py` (`.target`/`.add` read/write; `format_target_line()` round-trip-
verified against the REAL `combustion_target_class.combustion_target` parser, not just
its own inverse) + `plot_style.py` (matplotlib customization dataclass). Primary target
turned out to be `brute_force_sa_gui.py` (the actual target.opt-driven multiprocess
engine "using Brute force method" refers to), not `idt_sensitivity_gui.py` (a separate,
already-adequate single-condition tool -- given a light plot-style addition only). New
Targets/Manual-entry/Plot-style tabs; "run selected only" filters by LINE NUMBER not
dataset ID (one dataset ID commonly spans many T/P rows -- filtering by ID would've
pulled in siblings). `sens_3_params.py` gained an optional `SENS3P_PLOT_STYLE_JSON` env
hook at its two `savefig` call sites. PySide6 `SensitivityPage` got the same target
preview/gating/plot-style treatment. **Deferred**: "same for nominal simulations" --
`nominal_sim_gui.py` turned out to wrap a completely different pipeline (`mso_compare`
YAML-driven, not MUQ-SAC's target.opt/.target/.add system) per its own docstring; the
real target may be the separate, GUI-less `src/MUQ-SAC/nominal_sim_v3.py` -- needs its
own investigation, not guessed at here.

**Point 7 -- RMIP graph comparison localhost viewer**: `union_graph_spec.json` itself
carries no structural/stoichiometry data to build a network from (`GraphComparator`'s
classification result only has formula strings + canonical keys) -- `rmip compare-graph
--serve --port N` reuses the already-tested `GraphBuilder.build_union_graphs` + Dash
`NetworkVisualizer` (same code `rmip visualize --union` uses) against the just-compared
mechanism DB ids instead. N>2 compared mechanisms show the first 2 side-by-side
(`NetworkVisualizer`'s hard panel cap) with a printed note. Verified real: `rmip_cli.py
compare-graph --mechs 2 3 4 --db outputs/project.db --serve --port 8077` served a live
200 on `localhost:8077`. `rmip_suite_gui.py`'s Graph Comparison tab gained a "Launch
graph viewer" button + auto-opening clickable link (new `_TerminalTab._extra_buttons()`
hook, reusable by future tabs). PySide6 RMIP page link-surfacing not done.

**Point 5 -- Uncertainty Generator rename + rework**: renamed to "Uncertainty
Quantification and File Generator" everywhere (window title, launcher label, PySide6
page title). New primary "From SA data (ActiveParameterScreen)" tab/section wrapping
`src/ActiveParameterScreen.py` directly with its full flag set (including
`--per-case-plots`/`--longtable`/`--compare-temperatures`/`--compare-colors`, which
`rmip_suite_gui.py`'s pre-existing `ActiveParamSelectionTab` was missing) + a "Load
demo" button seeded from `DATASET/METHYL_BUTANOATE_2026/ACTIVE_PARAMETER_SELECTION`
(the shipped `clt` example file hardcodes a *different* clone's absolute paths, not
usable verbatim -- resolved relative to this checkout instead). Verified real: the
demo's exact 4-invocation combo run standalone produced 41 active reactions + real
XML/plot/LaTeX output. Manual XML entry + symmetric-bounds collapse kept as secondary
tabs, unchanged. PySide6 `UncertaintyPage` got the equivalent new section + a new
`mso_studio.core.uncertainty.run_active_parameter_screen()` adapter.

**Point 6 follow-on (fusion -> uncertainty handoff)**: new
`src/rmip/analysis/fusion_uncertainty_classification.py` bridges
`FusionUncertaintyEngine` records to the `Reaction_ID,Reaction,Reaction_Type,Group,f`
classification-CSV format Point 5's tool consumes (HTC/LTC split at a configurable T,
worst-case factor per group). Wired into `mean_value_fusion_gui.py::_run_fusion`
(Tkinter GUI result pane, `--fuse` CLI summary, PySide6 bridge) as
`write_uncertainty_csv=True` by default (skipped for `priority_order` runs -- verbatim-
copy mode has no cross-mechanism divergence left to band). **Found+fixed a real bug
while wiring the PySide6 side**: `mso_studio.core.fusion._parse_summary`'s generic
`key.startswith("n_")` catch-all (meant for the combined `"n_verbatim=X n_copy=Y
n_fuse=Z"` line) silently swallowed the new `n_uncertainty_reactions=N` line too, since
elif chains short-circuit on the first match and the catch-all was listed before the
specific key -- caught by the existing real end-to-end bridge test
(`test_run_fusion_real_h2_fixture_end_to_end`), not a mock. Fixed by reordering the
elif chain (specific keys before the generic prefix catch-all).

**Point 8 -- Missing GUIs**: `generate_target_opt.py` (the pre-split monolith)
registered in `launcher_gui.py` (now 11 apps); launcher's MSO Studio description now
explicitly names PySR/digitizer/Gemini PDF Q&A (already existed in the Tools page,
just never mentioned in the launcher window, which was the actual complaint -- "I do
not see those in the list"). Two genuinely new backends: `src/mso_io/notebook_gen.py`
(dependency-free nbformat-v4 `.ipynb` writer -- deliberately hand-writes the schema
instead of depending on the `nbformat` package, present in anaconda but not
`.venv-gui`, per the env-isolation policy; validated against the real `nbformat`
package's own `validate()`) and `src/mso_io/native_extensions.py` (discovers the
REAL source+build.sh/setup.py for `yamlwriter`/`parallel_yaml_writer`/`shuffle` under
`config_tools/` -- the original scoping assumption was that source might not exist at
all; it does). Both get a new Tools-page tab (`NotebookGenTab`, `NativeExtensionsTab`).
Verified real: rebuilt `shuffle.cpp` via the GUI's own `build_extension()` function,
clean g++ compile, then reverted the resulting artifact (not something the user asked
to actually change). **Deferred**: a dedicated standalone target.opt/.target/.add
editor GUI (Point 4's `brute_force_sa_gui.py` additions cover much of this need
already, but not as a focused, format-agnostic standalone tool).

## KRUNAL_JULY_23.md -- Tkinter -> PySide6 conversion (user asked 2026-07-26; **1 of ~11 apps ported so far**)

**Ask**: convert every standalone Tkinter GUI to PySide6 (the original approved plan
was hybrid -- fix bugs in Tkinter now, port later; the user asked to start the port
immediately, alongside finishing point 1). See [[project_mso_studio_pyside6_2026-07]]
(corrected 2026-07-24: "replacing Tkinter" there overstated what had landed -- only 6
MSO Studio pages existed, none of the 11 standalone apps).

**Ported: Mechanism Converter** (the natural first port -- `convert()` is already
framework-free, just a `log` callback, matching MSO Studio's own core/gui split).
- Added a headless `--convert` CLI mode to `mechanism_converter_gui.py`'s `main()`
  (mirrors every keyword of `convert()` 1:1) so the PySide6 side can shell out to it
  in the anaconda interpreter rather than importing `rmip`/Cantera into the
  PySide6-only venv (per the env-isolation policy -- see `backends.py`'s docstring).
- New `src/mso_studio/core/converter.py`: `ConverterParams` dataclass +
  `run_convert(params, on_line=, cancel_event=) -> RunRecord`, following
  `core/nominal.py`'s `science_command`/`run_backend` pattern exactly. Does NOT raise
  on a conversion failure (unlike most other adapters) -- a bad mechanism is an
  expected outcome, not an infrastructure error, so it returns a RunRecord with
  `status="failed"` and the tool's own `ERROR:` line as `record.error`, not a generic
  "backend exited non-zero".
- New `src/mso_studio/gui/modules/converter.py::ConverterPage`, registered in
  `PAGE_FACTORIES` (`mso_studio.gui.modules.__init__`) as "Mechanism Converter" --
  first entry in the nav, reachable via `run_mso_studio.py`.
- **Verified the actual two-interpreter bridge end-to-end** with the real KONNOV_2019
  mechanism, run from PySide6's own test suite: `.venv-gui` python -> anaconda
  python3.9 subprocess -> `mechanism_converter_gui.py --convert` -> confirms the
  point-2 fix (no `C2H4O1E-2` corruption, no `Unexpected token` error) holds through
  this path too, not just when `convert()` is called in-process from Tkinter.

Regression tests: `src/rmip/tests/test_chemkin_preflight.py`'s new
`TestConverterHeadlessCli` (3, the CLI contract), `src/mso_studio/tests/test_converter.py`
(5, including the real end-to-end KONNOV bridge test, skipped if the anaconda
interpreter isn't found), `src/mso_studio/tests/test_converter_page.py` (5, widget-level
`build_core_call`/`populate_results`). 48/48 green in the full `.venv-gui` MSO Studio
suite; app launches with the new page confirmed via a `MainWindow(PAGE_FACTORIES)`
smoke construction under `QT_QPA_PLATFORM=offscreen`.

**Already effectively ported (PySide6 equivalent wraps the identical backend --
verified, not assumed)**: `nominal_sim_gui.py` and MSO Studio's `NominalSimPage` both
wrap `src/mso_compare/run_nominal_sim.py`; `mso_compare_gui.py` and `ComparePage` both
wrap `src/run_mso_pipeline.py`; `brute_force_sa_gui.py` and `idt_sensitivity_gui.py`
are BOTH already covered by `SensitivityPage`'s two sub-tabs
(`mso_studio.core.sensitivity.run_brute_force_sa` / `run_idt_sensitivity`). No new
code needed for these four -- only eventual retirement of the Tkinter duplicates once
users are comfortable with MSO Studio.

**Ported: RMIP Suite (all 6 tabs)** -- Graph Comparison, Mechanism Reduction, Global
Sensitivity Analysis, Active Parameter Selection, Target Builder, ReSpecTh Import.
None of the 6 needed a new headless CLI (5 already had `rmip_cli.py` subcommands,
1 -- Active Parameter Selection -- already had its own argparse CLI via
`src/ActiveParameterScreen.py`). New `src/mso_studio/core/rmip_suite.py` (6
`Params` dataclasses + 6 `run_*` functions sharing one `_run()` plumbing helper) and
new `src/mso_studio/gui/modules/rmip_suite.py::RMIPSuitePage` -- a plain
`QWidget`+`QTabWidget` (not `ModulePage`, since each tab is its own independent
action -- matches `ToolsPage`'s existing multi-action pattern in this codebase) with
a shared `_RmipTabBase` mini-base-class (Run/Stop, log view, `RunWorker` wiring,
"Export run status…") that each of the 6 tab classes only needs to supply
`build_core_call()`/`populate_results()` for -- one shared-base-class edit covering
all 6 tabs, same shape as Point 1's rollout onto the Tk app's own `_TerminalTab`.
Verified real end-to-end bridge for Graph Comparison against the H2-combustion
fixture. 22 new tests (14 core + 8 page), all green.

**The `generate_target_opt.py` monolith remains Tkinter-only, deliberately** (see this
file's point-1 section for why: not reachable from the launcher, fully superseded).

**Ported: Mechanism Health-Check** -- no new headless CLI needed (the existing
`rmip check --json` CLI already had a full contract). New
`src/mso_studio/core/mechanism_check.py::run_check`; factored the Tk app's
`_FIX_EXAMPLES` dict + detail-text renderer into a new dependency-free shared module
`src/mso_io/mechanism_check_fix_examples.py` (`fix_example_for`,
`build_detail_text_from_dict`) so both the Tk app and the new `MechanismCheckPage`
render identical descriptive-error + worked-fix-example text (KRUNAL_JULY_23.md point
3) without the PySide6 side needing Cantera. 15 new tests (6 core + 5 page +
4 the shared-module refactor didn't break in the existing 33-test Tk suite).

**Ported: Mechanism Fusion** -- added a `--fuse` headless CLI mode to
`mean_value_fusion_gui.py` (there was no standalone CLI for `rmip.stubs.FusionEngine`
specifically before this). New `src/mso_studio/core/fusion.py::run_fusion` --
inherits point 6's automatic-glossary-backfill + degenerate-empty-union-guard fix
since it calls the same `_run_fusion()`. Verified end-to-end against the real
H2-combustion fixture through the actual bridge. 15 new tests (3 CLI + 6 core +
6 page).

**Ported: Uncertainty Generator** -- added `--generate-xml`/`--compute-bounds`
headless CLI modes to `uncertainty_generator_gui.py`. New
`src/mso_studio/core/uncertainty.py` (`run_generate_xml`, `run_compute_bounds`) --
`generate_uncertainty_xml` itself needs only stdlib, but goes through the same
subprocess bridge as `compute_symmetric_bounds` (which needs src/MUQ-SAC's
scipy/numpy stack) for one consistent recipe. Verified end-to-end with the known-good
`mech_std.yaml` fixture (A_nominal=9.841E+13, matching
`test_gui_stress_sweep.py::test_uncertainty_generator_roundtrip`'s own verified
number). 15 new tests (2 CLI + 4 core + 6 page + a widget-test file).

**Ported: Forward UQ** -- no new headless CLI needed (`forward_uq.py` already has a
full argparse contract, unlike the other 4 ports). New
`src/mso_studio/core/forward_uq.py::run_forward_uq` -- unlike the other adapters,
RAISES `BackendError` on failure rather than returning a `status="failed"` record
(matches `core.nominal.run_nominal`'s pattern: no meaningful "partial success" concept
for a single Monte-Carlo run). **Real-bridge gotcha found while testing**:
`forward_uq.py` resolves its `Opt/` PRS-cache directory as
`os.path.join(os.getcwd(), "Opt")`, and this adapter launches with `cwd=output_dir`
-- exactly like the original Tk app's own `_run_uq()` already did -- so `output_dir`
must be the SAME directory the `Opt/` cache already lives in, not a fresh empty one;
documented prominently in `ForwardUqParams`'s docstring and the page's setup-panel
label/caption. Verified end-to-end via the same synthetic-PRS-cache bootstrap
`test_gui_stress_sweep.py::test_forward_uq_full_run_with_synthetic_prs_cache` uses.
10 new tests (5 core + 5 page).

**PySide6 conversion COMPLETE: all 11 Tkinter apps now have a PySide6 equivalent.**
Converter, health-check, fusion, uncertainty generator, forward UQ, and RMIP suite
(6 tabs) ported directly this session; nominal sim, MSO compare, brute-force SA, IDT
sensitivity already had one via existing pages. Only the deliberately-deprioritized
`generate_target_opt.py` monolith stays Tkinter-only. 113/113 `.venv-gui` MSO Studio
tests green; app launches with all 12 pages (11 ported + Tools) confirmed via a
`MainWindow(PAGE_FACTORIES)` smoke construction. Each follows the same 3-piece
recipe: (1) a headless CLI mode on the existing script if one doesn't already exist,
(2) a `core/<name>.py` adapter (`Params` dataclass + `run_<name>(params, on_line=,
cancel_event=) -> RunRecord`, shelling out via `science_command`/`run_backend` for
anything needing Cantera/rmip/MUQ-SAC), (3) a
`gui/modules/<name>.py::<Name>Page(ModulePage)` (or a plain `QWidget`+`QTabWidget`
for multi-action pages like RMIP Suite/Tools) + `PAGE_FACTORIES` entry.
