# W7 — RMG explainability, generation supervisor & input linter

**Closes:** P17 & P26 (no visibility into edge→core promotion / can't inspect the
edge), P30 (jobs never terminate), P16 (prune by count not memory — wrapper), P39
(duplicate library/reaction in RMG input undetected), P15 (non-reproducible across
versions — shared with W8); spikes P12 (polymer generation).
**Effort:** M-L · **Risk:** Med · **Depends on:** `generation/rmg_interface.py`,
an RMG install at `/data/OPEN_CODE/RMG_py` (RMG venv; env-isolated via subprocess).

## What already exists (verified)
`RMGInterface` (`src/rmip/generation/rmg_interface.py`) runs RMG and diffs
missing species/reactions/pathways, then grafts. It does **not** explain *why* RMG
promoted a species, inspect the edge, supervise runaway jobs, lint the input, or
check reproducibility. All wrapper-level — no RMG-internal changes required.

## W7a — Edge/core promotion explainer (P17, P26)
- Parse RMG's run artifacts (`RMG.log`, `chemkin/`, edge/core snapshots) after a run.
- `class RmgRunExplainer.attribute_promotions()` → for each core species, the
  highest-flux reaction and generation iteration that promoted it (RMG logs flux
  data; we read it, we don't modify RMG). Emit a ranked, human-readable "why this
  species is here" report + JSON.
- `inspect_edge()` → list edge species RMG considered but rejected, with their
  characteristic flux (the P26 ask, unmet since 2007).

## W7b — Generation supervisor (P30, P16)
- `class RmgSupervisor.run()` wraps the RMG subprocess with: wall-clock + per-
  iteration timeouts, a **memory-budget monitor** (poll RSS; the P16 workaround
  outside RMG), staged conditions (run T/P points sequentially), and automatic
  tolerance relaxation on non-convergence — writing a run report on early stop so a
  runaway job yields a partial, inspectable result instead of hanging for days.
- Reuse `simulation/subprocess_util.py` for the subprocess lifecycle.

## W7c — RMG input linter (P39)
- `lint_rmg_input(input.py)` — static check of an RMG job file for: a library listed
  in both `libraries` and `seedMechanisms` (→ duplicate reactions, issue #2979/#2882),
  duplicate library entries (#2485), and obviously conflicting reactor/tolerance
  settings. Emits `Finding`s before the (expensive) run starts.

## W7d — Reproducibility diff (P15, shared with W8)
- `reproducibility_diff(runA, runB)` — align two RMG outputs (same input, different
  RMG versions) and report added/removed species & reactions and rate differences,
  so "non-reproducible across versions" becomes a concrete, inspectable diff rather
  than a mystery. Reuses the graph-comparison machinery (`analysis/graph_comparator`).

## W7e — Polymer generation spike (P12) — *exploratory, not a committed deliverable*
Polyethylene-pyrolysis / broad-product generation is requested twice across two
communities and is a genuine research problem. Scope a **spike only**:
- evaluate a lumped-family / template approach (recurring β-scission + H-abstraction
  families with product lumping) layered on RMG's families, bounded by the supervisor
  (W7b) so it can't run away.
- Deliverable of the spike is a go/no-go memo, not a generator. Do not commit the
  full feature up front.

## CLI / GUI
- `rmip rmg-explain <run_dir>`, `rmip rmg-supervise <input.py> [--mem-gb N] [--timeout]`,
  `rmip rmg-lint <input.py>`, `rmip rmg-diff <runA> <runB>`.
- These extend the existing RMG-oriented CLI surface (`_add_family_scan_cmd`,
  `_add_generate_targeted_cmd`).

## Tests
- Explainer/edge/diff run against **recorded RMG artifacts** committed as fixtures
  (no live RMG in CI) — parse-and-report is deterministic on fixed logs.
- `rmg-lint` on a crafted input with a dual-listed library → flagged.
- Supervisor tested with a fake long-running subprocess (timeout/mem-budget fire).

## Acceptance
For a recorded RMG run, `rmip rmg-explain` names why each core species was added and
lists the edge; `rmg-lint` catches a dual-listed library; the supervisor stops a
runaway job with a partial report; `rmg-diff` turns "non-reproducible" into a diff.

---

## ✅ DONE — shipped 2026-07-20

All four modules live in `src/rmip/generation/`; none needs the RMG env
(which is absent on this machine — `rmg_env` referenced by
reaction_family_kb does not exist), per the plan's recorded-artifact test
strategy.

- **W7a** — `rmg_explainer.py`: `RmgRunExplainer(run_dir).explain()` parses
  `RMG.log` with regexes kept **verbatim-compatible with RMG-Py's format
  strings** (extracted from `rmgpy/solver/base.pyx` + `rmgpy/rmg/model.py`
  at /data/OPEN_CODE/RMG_py). Attributes every core species to its first
  promotion event — flux (with time/rate-ratio/tolerance), resurrection,
  singularity, or seed/initial — with the iteration number; edge inventory
  merges log sightings (interruption lines, pruning, Forbidden) with the
  saved `chem_edge_annotated.inp` SPECIES block, ranked by max observed
  rate ratio (the P26 ask). CLI: `rmip rmg-explain <run_dir> [--top-edge
  --json]`.
- **W7b** — `rmg_supervisor.py`: `RmgSupervisor.run(input, outdir)` wraps
  the RMG subprocess (sanitized env, own process group, SIGTERM→SIGKILL
  tree kill) with wall-clock budget, **process-tree RSS budget via /proc**
  (no psutil; the P16 workaround), stall detection on log growth (the P30
  signature), and optional bounded `toleranceMoveToCore ×10` relaxation
  retries; `run_staged([...])` runs per-condition inputs sequentially.
  Every stop writes `supervisor_report.json/.txt` with iterations
  completed, peak RSS, stages, and pointers to partial outputs (+ a hint
  to run rmg-explain on them). Testable via `command_template` fake
  subprocesses. CLI: `rmip rmg-supervise <input...> -o OUT [--mem-gb
  --timeout --stall-timeout --relax-on-stall]`.
- **W7c** — `rmg_lint.py`: `lint_rmg_input(path)` parses input.py with
  `ast` (never executes it): dual-listed reactionLibraries∩seedMechanisms
  (#2979/#2882, error), duplicates within a list (#2485, error),
  interrupt<move tolerance inversion (warning), non-positive tolerance,
  missing database()/model(), dynamically-built lists reported as
  unlintable (never silently passed). CLI: `rmip rmg-lint` (exit 1 on
  errors).
- **W7d** — `rmg_diff.py`: `reproducibility_diff(runA, runB)` aligns two
  RMG output dirs structurally: species by a **Morgan-refinement canonical
  hash of species_dictionary.txt adjacency lists** (label-independent, same
  identity philosophy as graph_comparator's InChI matching but with zero
  RMG/RDKit dependency; multiplicity + u/p/c state included, so OH ≠ OH⁻),
  label fallback for dictionary-less inerts; reactions by canonical
  reactant/product multisets (direction-insensitive when reversible), then
  A/n/Ea compared against tolerances. Reports matched/renamed/added/removed
  species and reactions + ranked rate changes. CLI: `rmip rmg-diff A B`
  (exit 1 when diverged).
- **W7e** — spike delivered as `W7e_polymer_spike_memo.md`: **conditional
  GO** on a lumped homologous-series generator (deterministic template
  enumeration + FiniteSolidReactor melt physics), **NO-GO** on exploratory
  RMG generation of the polymer itself; two env-gated checks listed for
  when the RMG env exists. Not a committed feature.
- **Fixtures:** `fixtures/rmg_run/` (RMG.log written line-for-line in the
  real grammar + edge chemkin snapshot), `fixtures/rmg_diff_a|b/` (renamed
  OH(3)→OH(7), atom-renumbered H2O, added/removed species and reactions, a
  1.5× A-factor change), `fixtures/rmg_input_dual.py` (all three lint
  pathologies).
- **Tests:** `test_rmg_w7.py` — 25 tests, all green: full promotion
  attribution incl. all four mechanisms and iteration numbers, flux
  ranking, edge fates (pruned/forbidden/remained + no-flux merge, and
  later-promoted species excluded), lint hits + clean pass + syntax-error +
  unlintable, graph-key renumbering invariance and radical-state
  discrimination, diff alignment/rate-change/self-identity, and supervisor
  completed / wall-timeout / stall / **memory-budget (real 400 MB
  ballast)** / tolerance-relaxation recovery / staged-batch isolation /
  missing-env error.

Closes **P17, P26, P30, P16 (wrapper), P39**; P15 gains the concrete diff
(the version-regression *harness* half stays in W8). P12 spiked per plan.
