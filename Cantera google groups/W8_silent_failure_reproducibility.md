# W8 — Silent-failure detectors & version-behaviour regression harness

**Closes:** P33 (import "succeeds" but all rates silently zero), P35 (case-mismatch
species names across sections — shared with W2), P28 (LFS shifts across Cantera
versions), P15 (RMG non-reproducible — shared with W7).
**Effort:** M · **Risk:** Low · **Depends on:** `mechanism_check.py`, the simulation
runners (`idt_runner`, `lfs_runner`).

## Problem
The hardest bugs for a person to catch are the ones that produce **no error**: a
mechanism that loads but computes all-zero rates while species are consumed (P33),
a species written two ways across file sections (P35), and *silent behaviour changes
across versions* (P28/P15) that quietly break validation workflows.

## W8a — Silent-failure detectors (P33, P35)
New checks folded into the `rmip check` battery (`mechanism_check.py`):
- **Zero-rate / decoupled reactions (P33)** — over the screening (T,P) grid, flag
  reactions whose forward *and* reverse rate constants are identically ~0 at all
  conditions (dead reactions), and species that appear in reactions but whose net
  production rate is identically zero everywhere (decoupled). `check_rate_sweep`
  already walks the grid — add a zero/near-zero pass and a species-coupling pass.
- **Cross-section name consistency (P35)** — for CHEMKIN inputs this lives in W2's
  preflight; add the YAML/loaded-Solution analogue: detect species referenced only
  by a case-variant, and thermo/transport records whose name doesn't match the
  species list (Cantera usually catches this, but surface/edge cases slip through).

## W8b — Version-behaviour regression harness (P28, P15)
New module `src/rmip/analysis/version_regression.py`:
- A **canonical case suite** (a few mechanisms × {IDT, LFS, equilibrium} at fixed
  conditions) with committed **golden outputs**.
- `run_suite(cantera_env)` executes the suite against a given Cantera (the current
  env, or another version in an isolated venv via subprocess — env-isolation) and
  `diff_against_golden()` reports any output that moved beyond tolerance, with the
  magnitude — so a version bump's behaviour change (P28) is caught deliberately
  instead of by surprise.
- The same harness, pointed at two RMG outputs, backs W7d's reproducibility diff
  (P15): shared diff/report code, different inputs.
- Designed to run in CI or on demand; golden files are regenerated with an explicit
  `--bless` flag (audited, never silent).

## CLI / GUI
- New checks appear automatically in `rmip check` (W8a).
- `rmip regression [--env path/to/venv/python] [--bless] [--json]` (W8b).

## Tests (`src/rmip/tests/test_silent_failure.py`, `test_version_regression.py`)
- Fixture with a deliberately dead reaction (A=0) and a decoupled species → flagged
  (P33); a YAML with a case-variant species reference → flagged (P35).
- Regression harness: golden match passes; a perturbed mechanism trips the diff with
  the correct magnitude; `--bless` updates goldens.

## Acceptance
A mechanism that loads but computes all-zero rates is flagged (no more silent
success); a version bump that shifts LFS is caught by `rmip regression` with the
numeric delta; the same engine turns RMG cross-version drift into a diff.

---

## DONE (shipped 2026-07-20, uncommitted)

- **W8a — silent-failure detectors** — two new checks in
  `mechanism_check.py`, auto-surfaced in `rmip check` and the GUI (both
  enumerate `ALL_CHECKS`):
  - `zero_rates` (P33): sweeps the screening (T,P) grid with *every* species
    present (so nothing is zero merely from composition) and flags
    **dead reactions** (fwd AND rev k ≤ 1e-90 everywhere; per-reaction
    warnings capped at 25, with a `delete_reaction` fix) and **decoupled
    species** (participate in reactions but creation+destruction identically
    zero). The headline case — *every* reaction dead — is a single
    `all-rates-zero` **error**: the silent import failure is silent no more.
  - `name_consistency` (P35 YAML analogue): raw-YAML scan (runs even when
    `ct.Solution` rejects the file) of phase species lists, equation tokens
    (via a falloff/`(+M)`/coefficient-aware tokenizer `_equation_species`)
    and third-body efficiencies against the declared species section:
    `species-case-mismatch` (error, auto-fix `rename_species_ref` rewrites
    every reference — proven to turn an unloadable mech loadable),
    `species-case-twins` (both `AR` and `Ar` declared), and
    `undeclared-species-ref` (warning).
- **W8b — version-behaviour regression harness** —
  `analysis/version_regression.py` + `analysis/_regression_worker.py`:
  - The worker is deliberately **stdlib+cantera only** (zero rmip imports),
    so `run_suite(env_python=...)` executes the identical suite inside any
    Cantera venv via subprocess+JSON (env-isolation pattern; LD_LIBRARY_PATH
    sanitized) — the target env does not need rmip installed.
  - Canonical suite: {h2o2, gri30} × {equilibrium(T_ad+X), IDT(max-dT/dt),
    LFS(FreeFlame)} at fixed conditions; goldens committed at
    `analysis/goldens/version_regression_golden.json` (blessed under Cantera
    3.0.1; H2 LFS 2.351 m/s, CH4 LFS 0.381 m/s, T_ad 2388/2226 K; full
    suite ≈20 s). Per-task tolerances: idt 5%, lfs 2%, equilibrium 0.5%.
  - `diff_against_golden` reports every observable that moved, with the
    relative magnitude; goldens are regenerated ONLY via `--bless`
    (refuses payloads with failed cases). `diff_result_sets` is generic over
    any two result sets — pointed at two RMG builds it is the behavioural
    half of P15 (rmg-diff being the structural half).
  - CLI: `rmip regression [--env PY] [--cases J] [--golden J] [--bless]
    [--tol idt=0.1 ...] [--json]` (exit 1 on drift).
- **Tests:** `test_silent_failure.py` (15 — dead/decoupled/all-zero flagged,
  healthy + slow-but-live mechs clean, case-variant caught pre-load, rename
  fix → loadable + clean re-check, tokenizer table) and
  `test_version_regression.py` (11 — real subprocess run, physical-value
  sanity, bless/match/drift-magnitude (Δ=0.2/1.2 exact), tolerance
  override, bless-refusal, missing-golden error, new/missing/failed case
  statuses, RMG-style two-run diff). Full suite 883 green.

**Acceptance met:** an all-zero-rate mechanism now FAILS `rmip check`; an
LFS shift across Cantera versions is caught by `rmip regression` with the
numeric delta; the same engine diffs two RMG runs behaviourally.
