# W6 — Ignition-delay sensitivity as a first-class, documented capability

**Closes:** P20 (no built-in IDT sensitivity — 8-year recurring ask, 2018→2026);
helps P36 (which example to use).
**Effort:** S · **Risk:** Low · **Depends on:** `simulation/sensitivity_runner.py`,
`simulation/idt_runner.py`.

## Problem
Users have re-derived IDT sensitivity from scratch for ~8 years, re-hitting the same
gotchas: choice of IDT definition, **logarithmic vs linear normalisation** (log is
correct — IDTs span orders of magnitude), one-sided vs central finite differences,
and the `set_multiplier`-only-scales-a-runtime-vector subtlety.

## What already exists (verified)
`CanteraSensitivityRunner.run_idt` (`src/rmip/simulation/sensitivity_runner.py`)
already does a **CVODES local IDT sensitivity** via Cantera's `IdealGasReactor` SA,
exposed as the `sa-run` CLI command, with an ignition threshold on temperature rise.
So P20 is **~70% built** — this workstream is polish + the missing options + docs,
not a from-scratch implementation.

## Goal
Promote it to a documented, first-class utility with the three things users keep
re-deriving: a clear IDT definition, correct log-normalisation, and both brute-force
and CVODES methods with a worked example.

## Design (extend, don't replace)
In `sensitivity_runner.py` / a new `idt_sensitivity.py`:
- **IDT definition** — make it explicit and selectable: max-|dT/dt|, OH/CH* peak,
  or fixed-ΔT threshold (current). Store the choice in the report.
- **Normalisation** — add **logarithmic sensitivity** `d ln(τ)/d ln(k_i)` as the
  default reported quantity (the correct form), keeping linear available.
- **Method** — keep CVODES local SA; add a **brute-force perturb-and-resolve**
  path (central difference by default, one-sided optional) using `set_multiplier`
  on a fresh gas per perturbation, with a clear note that the stored A-factor is
  untouched (the recurring `set_multiplier` gotcha, documented in-code).
- **Batch/parallel** — reuse `idt_runner`'s parallel harness for the brute-force
  sweep.
- Output a ranked top-N reactions table (reuse the `mechanism_report`/`Finding`
  rendering) + JSON.

## CLI / GUI
- Extend `sa-run`: `--observable idt --idt-def {dTdt,OH,threshold}
  --norm {log,linear} --method {cvodes,brute} --diff {central,forward}`.
- A small GUI surface (or a tab in an existing SA GUI) exposing fuel/oxidiser/φ/T/P,
  the IDT definition, and a ranked bar chart of log-sensitivities.
- **P36 tie-in:** a one-line "recipe" doc mapping the task ("IDT sensitivity") to
  this command — folds into W9's recipe router.

## Tests (`src/rmip/tests/test_idt_sensitivity.py`)
- On a small mechanism (h2o2/gri-subset), CVODES and brute-force top-5 reactions
  agree in rank; log-normalisation matches the analytic scaling on a 1-reaction toy;
  central vs forward difference converge as perturbation → 0.

## Acceptance
`rmip sa-run --observable idt --norm log --method brute` produces a ranked,
log-normalised IDT-sensitivity report that matches the CVODES path, with a worked
example and doc — retiring the 8-year re-derivation.

---

## ✅ DONE — shipped 2026-07-19

- **Module:** `src/rmip/simulation/idt_sensitivity.py` — `IdtSensitivityAnalyzer`
  + `IdtSensitivityResult`. Reports **d ln(τ)/d ln(k)** (log norm, default) or raw
  (dτ/d ln k). Two methods that agree:
  - `brute` — perturb each reaction's `set_multiplier` by ±δ on a fresh gas,
    re-integrate; central (default) or forward diff; optional `ProcessPoolExecutor`.
  - `cvodes` — Cantera reactor SA converted to a true τ-sensitivity via the
    implicit-function relation `S_τ = −(T_ign·S_T)/(τ·(dT/dt)|_τ)` at the threshold
    crossing (fast; no longer a temperature proxy).
  - Selectable IDT definition: `dTdt` (default), `threshold`, `species`;
    reactor `constV` (default) / `constP`. No-ignition guard raises with the §2.2
    advice. (The recurring `set_multiplier` gotcha is documented in-code.)
- **CLI:** `rmip idt-sens <mech> --fuel --T --P --phi [--method --idt-def
  --norm --diff --delta --reactor --species --top --workers --json]`
  (`cli.py:_cmd_idt_sens`), with an ASCII tornado chart.
- **GUI:** `idt_sensitivity_gui.py` (registered in `launcher_gui.py`) — full case
  controls + embedded matplotlib tornado chart (red = shortens IDT, blue =
  lengthens); `--no-gui` self-test.
- **Note on `sa-run`:** rather than change `sa-run`'s existing §10 output
  (consumed by `rmip sensitivity`/`visualize`), the first-class capability ships as
  the new **`idt-sens`** command. `sa-run`/`CanteraSensitivityRunner` are left
  intact; `idt-sens` supersedes them for true τ-sensitivity.
- **Tests:** `src/rmip/tests/test_idt_sensitivity.py` — 12 tests, all green.
  Verified: base IDT; **brute vs cvodes top-5 overlap ≥4, same #1, values within
  10%**; physical signs (chain-branching <0, chain-termination >0); log↔raw
  relationship; central/forward agree; species/threshold definitions; no-ignition
  guard; CLI. On h2o2 @1000 K/10 atm the two methods match to ~3%.

Closes **P20**; helps **P36** (a clear canonical command for this task).
