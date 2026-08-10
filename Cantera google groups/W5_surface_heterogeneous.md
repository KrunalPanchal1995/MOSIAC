# W5 — Surface / heterogeneous / finite-solid support

**Closes:** P6 (bulk = infinite reservoir), P7 (clamping injects mass), P8 (coverage
Σθ=1 drift), P9 (non-isothermal fragility), P21 (RMG vs Cantera surface divergence),
P25 (liquid mole-fraction unphysical); shares P4 (surface-site balancing).
**Effort:** L · **Risk:** High · **Depends on:** Cantera Interface API; verified
today the codebase has **no** `ct.Interface`/`ReactorSurface`/coverage handling.

This is the source doc's "single richest vein" and its heaviest workstream. Phase it.

## Phase W5a — Finite bulk-solid reactor (P6, P7, P8, P9)

**Problem.** Cantera's `Reactor`/`ReactorSurface` treats a bulk solid as an infinite
thermodynamic reservoir — its mass is not an ODE state — so a depleting char/solid
cannot be modeled without a hand-rolled outer loop that (P7) injects artificial mass
when clamping negatives and (P8) lets Σθ drift, and (P9) is numerically fragile
non-isothermally.

**Design.** New module `src/rmip/simulation/finite_solid_reactor.py`:
- `class FiniteSolidReactor` wrapping a gas `Solution` + `Interface` + a bulk phase,
  integrating an **augmented state vector** that *includes bulk-phase moles/mass*
  (and reactive surface area as a function of remaining solid), advanced with a
  stiff integrator (SciPy `solve_ivp`/`BDF`, already available; no new dep).
  - Mass conservation: enforce non-negativity via a **projected/positivity-preserving
    step** (clip the *rates*, not the *state*, so no artificial mass is created —
    the explicit fix for P7), with a per-step mass-balance audit that errors if drift
    exceeds tol.
  - `Σθ = 1` enforced as an algebraic constraint each accepted step (P8).
  - Adaptive dt with a stiffness guard for the exothermic non-isothermal case (P9);
    optional isothermal mode.
  - Shrinking-core surface-area model as a pluggable callable.
- Reuse `simulation/base.py`'s runner conventions and `subprocess_util` if a heavy
  backend is ever needed (not expected — SciPy suffices).

**Tests.** A shrinking char fixture: total element mass conserved to 1e-8 over full
burnout (proves no artificial mass, P7); Σθ stays 1 (P8); isothermal vs non-isothermal
both integrate to completion (P9); bulk mass monotonically depletes (P6).

## Phase W5b — Surface-mechanism cross-solver validator (P21)

**Problem.** RMG's own surface solver and Cantera give different results for the same
surface mechanism — an open interoperability discrepancy.

**Design.** `src/rmip/simulation/surface_crosscheck.py`:
- Run a canonical surface case (steady-state coverages / rates) through **Cantera's
  Interface kinetics** and, via subprocess in the RMG venv, through **RMG's solver**;
  align species/reactions and diff coverages, rates, and Keq.
- Emit `Finding`s per reaction where the two diverge beyond tol, ranked by magnitude
  — this operationalises P21 as a *detector* even though the underlying fix lives in
  RMG (cross-links to W7 and the RMG-internal notes in `99_OUT_OF_SCOPE.md`).
- Reuse the existing cross-check scaffolding pattern from
  `simulation/gsa_prs_crosscheck.py`.

**Tests.** A tiny surface mechanism where the two solvers agree (regression guard)
and a constructed case with a known Keq inconsistency that the validator flags.

## Phase W5c — Liquid / multiphase composition sanity (P25)

**Problem.** A liquid-phase solvent set by mole fraction came out ~10× below its
known pure concentration; root cause never identified.

**Design.** `src/rmip/analysis/multiphase_sanity.py`:
- Given a multiphase setup, check that setting composition by mole fraction yields
  a molar concentration consistent with the phase's density/EoS; flag order-of-
  magnitude mismatches with the likely cause (wrong phase density, activity model,
  or mole-fraction-vs-concentration confusion).
- Cross-link into `rmip check` as check id `multiphase_sanity`.

## Surface-site balancing (P4, shared with W2)
A helper `balance_surface_sites(interface_dict)` that inserts an empty-site
placeholder and balances surface-reaction stoichiometry; used by both the converter
preflight (W2) and this workstream.

## CLI / GUI
- `rmip react-solid <mech> --fuel … --bulk … [--isothermal] [--out traj.csv]`.
- `rmip surface-crosscheck <mech>` (needs RMG venv).
- Fold `multiphase_sanity` into `rmip check`.
- A "Heterogeneous Reactor" GUI is Phase-C polish, not part of the initial build.

## Acceptance
A depleting-char case integrates to full burnout with element mass conserved and
Σθ=1 held; the cross-solver validator flags a constructed Keq divergence; the
liquid-composition diagnostic reproduces and explains the P25 order-of-magnitude gap.

## Risk notes
Highest-risk workstream: Cantera's bulk-phase state limitation is real (P6 is
unsolved *in Cantera itself*), so W5a is a genuine new numerical formulation, not a
wrapper. Keep W5a behind a clearly-scoped shrinking-core model rather than a general
multiphase solver. W5b/W5c are lower-risk detectors.

---

## ✅ DONE — shipped 2026-07-20

- **W5a** — `src/rmip/simulation/finite_solid_reactor.py`: `FiniteSolidReactor`
  integrates the augmented **extensive** state `[gas species masses, surface
  species moles, bulk mass, T]` with SciPy BDF inside an adaptive-dt ladder
  (failed chunk → dt/4, retry; bottoming out raises `IntegrationError` with
  P9 guidance; `isothermal=True` fallback mode).
  - P7 by construction: rates (not states) vanish as inventories deplete —
    shrinking-core `A(m_b)→0` for the bulk, mass action for gas; residual
    integrator negatives projected within an **audited** tolerance
    (`MassBalanceError` on drift > `mass_audit_rtol`).  BDF preserves the
    linear element-mass invariants of Cantera's exactly-conserving rates, so
    conservation lands at ~1e-15 in practice, far inside the 1e-8 target.
  - P8 structurally: coverages come from normalizing extensive surface moles,
    so Σθ=1 always; a separate site-total audit flags site-unbalanced
    mechanisms (P4 tie-in) instead of drifting.
  - Pluggable `area_model` (shrinking-core default, `constant_area` provided).
    Documented approximations: lumped gas+solid T, surface energy storage
    neglected, coverage relaxation on the initial site inventory.
  - CLI: `rmip react-solid <mech> --T --P --X --volume --bulk-mass [--area
    --area-model --isothermal --t-end --out traj.csv]` (phase names
    auto-detected from YAML thermo models).
  - Fixture: `fixtures/char_oxidation.yaml` (generated by
    `_make_char_fixture.py` from installed GRI thermo) — gas O2/CO/CO2/N2 +
    bulk C(b) + surface {(s), O(s)}, O2 adsorption + char oxidation + CO
    burnout. 14 tests (`test_finite_solid_reactor.py`): burnout with element
    mass conserved ≪1e-8, Σθ=1, monotone depletion, both energy modes,
    isothermal slower than adiabatic (physics), O2-starvation stalls cleanly,
    constant-area model, CSV round-trip.
- **W5b** — `src/rmip/simulation/surface_crosscheck.py`: `SurfaceCrossChecker`
  diffs Cantera vs an RMG-side result — per-reaction **log10 K =
  −ΔG°/(RT ln10)** (dimensionless, unit-convention-free; the P21 Keq class)
  and steady-state coverages (`advance_coverages`) when provided. Reactions
  aligned via `canonical_equation` (sides sorted, arrows/whitespace unified),
  optional `species_map` for RMG naming; unmatched entries reported, never
  dropped. Emits ranked `Finding`s (`to_findings`). RMG side: **live** via
  `_rmg_surface_backend.py` subprocess in the RMG env (needs CHEMKIN input —
  RMG can't read Cantera YAML; sanitized env + finite timeout via
  subprocess_util) or **offline** via `--rmg-json`. CLI:
  `rmip surface-crosscheck` (exit 1 on divergence). 12 tests
  (`test_surface_crosscheck.py`): Cantera-vs-itself zero-flag regression
  guard, constructed Keq divergence flagged+ranked (acceptance case),
  coverage divergence, tolerance boundary, unmatched reporting, species_map,
  Keq-only note, findings/rendering, clean live-mode error paths. (No RMG env
  exists on this machine — the live path degrades to explained errors, same
  pattern as reaction_family_kb.)
- **W5c** — `src/rmip/analysis/multiphase_sanity.py`: two probes per
  condensed phase — (1) internal identity (Cantera's reported concentration
  vs ρ/W at pure composition: the mole-fraction-vs-concentration confusion
  class) and (2) reference magnitude vs a built-in composition-keyed table of
  10 pure-liquid concentrations (water 55.35 M, …), plus density
  plausibility. Warning-only; real-gas phases (Redlich-Kwong/Peng-Robinson)
  skipped; pure-gas mechanisms yield zero findings. Wired into `rmip check`
  as check id `multiphase_sanity` (→ shows in mechanism_check_gui
  automatically). Fixture `fixtures/liquid_p25.yaml` (water density wrong by
  exactly 10×) **reproduces and explains the P25 gap**: "5.53 mol/L vs 55.35
  (10.0x below) — likely wrong species density/molar volume (phase density
  99.7 kg/m³; water is ~997)".
- **P4** — `src/rmip/analysis/surface_sites.py::balance_surface_sites(doc)`:
  raw-YAML repair (Cantera ≥3.0 *rejects* site-unbalanced surface reactions
  at load); appends the empty-site species (auto-detected by empty
  composition, or a synthesized `(v)` vacancy) to the deficient side using
  per-species `sites:` sizes; input dict never mutated; notes per change.
  Turns a Cantera-rejected mechanism into one that loads (verified in tests).
- **Tests:** 12 in `test_multiphase_sanity.py` (W5c + P4) — all three W5
  suites green (38 new tests), full rmip suite 828 passed. NB: new tests use
  `yaml.safe_dump` because MUQ-SAC's `MechanismParser` poisons PyYAML's
  default Dumper globally (`add_implicit_resolver(..., None, ...)`).
- **Deferred as planned:** the "Heterogeneous Reactor" GUI (Phase-C polish).

Closes **P6, P7, P8, P9, P21 (detector), P25, P4**.
