# Mechanism-checking research & next-phase backlog

**Living document — started 2026-07-19.** Purpose: catalogue the checks that the
established combustion-community mechanism-checking tools (LLNL MechChecker, KAUST
CloudFlame, Northeastern ChemCheck) perform, plus the recurring mechanism/simulation
failure modes reported on the Cantera Users' Google Group, then map each against what
this suite already implements so the gaps become the next implementation phase.

> **How to use this file:** keep appending. §1–§2 are the research corpus (external
> tools + Cantera-group failure taxonomy). §3 is the implemented-vs-missing gap map. §4
> is the prioritised backlog. When a backlog item ships, move it to "Done" with the
> module + test name (mirror the `bug.md`/`BUG.md` convention).

---

## 1. External mechanism-checking tools and the checks they perform

### 1.1 LLNL — MechChecker / "Cloud based tool for analysis of chemical kinetic mechanisms"
`https://combustiontools.llnl.gov/mechcheck/` · paper: *Combustion & Flame* 218 (2020)
234–245 (OSTI 1771432). This is the canonical LLNL answer to "check a mechanism".

Checks / diagnostics offered:
- **Ignition-Delay Diagnostic** ("the mechanism checker") — runs a 0-D ignition case for
  a user-specified fuel/oxidizer and surfaces mechanisms that fail to ignite / integrate.
- **Thermodynamic Diagnostic** — detects **NASA-polynomial discontinuities** (Cp/H/S
  mismatch at `Tmid` between the low- and high-T pieces), plots the discontinuity, and
  provides an **automated re-fitting** method that restores continuity while preserving
  the data.
- **Rate-coefficient timescale checks** — flags rate coefficients whose implied
  timescales are unphysically fast.
- **Collision-limit checks** — flags reactions whose rate constant exceeds the
  gas-kinetic collision limit (incl. the subtlety that the collision limit for a
  reaction with **more than two reactants** cannot be computed by the standard formula).
- **Duplicate / pressure-dependent reaction parameter checks** — inappropriate duplicate
  declarations and pressure-dependent (falloff/PLOG) parameterizations.
- **Visual screening** — plot of `log(rate)` vs reaction index to eyeball outliers.
- **Syntax checks** — a leading `+` on positive thermo coefficients, special characters
  in species names, missing `e`/`E` in scientific notation, tab characters in/near lines.
- Inputs: CHEMKIN thermo + mechanism (+ transport) files. Outputs: text reports + plots.

### 1.2 KAUST — CloudFlame "Collision Limit Violation" screening
`https://cloudflame.kaust.edu.sa` · paper: *Screening gas-phase chemical kinetic models:
collision limit compliance and ultrafast timescales* (Combustion & Flame, KAUST).

- **Collision-limit screening for bimolecular reactions across three classes**, handled
  separately: (a) pressure-independent Arrhenius, (b) pressure-dependent **falloff**,
  (c) pressure-dependent **PLOG**. Screens **both forward and reverse** directions.
- Empirical impact: of 20 models published in C&F 2015–16, **15 had rate coefficients
  exceeding the collision limit** — worst case by **73 orders of magnitude**.
- **CSP-based ultrafast-timescale screening** — even collision-limit-compliant models can
  carry unphysically fast timescales; computational singular perturbation is used to flag
  them (stiffness the integrator then chokes on).
- Companion **thermodynamic** and **transport** modules to locate the source of a
  non-compliant reaction.
- Related: *Correction of reaction models using collision limit violation analyses:
  application to a silane reaction model* (C&F 2020) — the "detect → correct" loop.

### 1.3 Northeastern (CoMoChEng) — ChemCheck (Cantera debugging tool)
GitHub `comocheng/ChemCheck`; NSF PAR 10259944; Django/Python web app. The
**Cantera-native** analogue of MechChecker.

- **Syntax-error detection with actionable diagnostic messages** — missing digits at end
  of a line, missing exponent sign, missing comment sign, stray tabs, etc. (goes beyond
  silent auto-fixing: it *tells the user what's wrong and where*).
- **Thermo discontinuity detection + visualization** — lists species whose NASA
  polynomials are discontinuous and plots the Cp/H/S curves so the kink is visible.
- **Collision-limit violation list** — bimolecular reactions exceeding the collision
  limit (noting these usually show up in the **reverse** direction).
- **Duplicate / pressure-dependent parameter checks.**
- **CHEMKIN ⇄ Cantera conversion** with the errors surfaced inline.

### 1.4 Cantera's own `ck2yaml` validation (the baseline every user hits first)
`https://cantera.org/stable/userguide/ck2yaml-tutorial.html`

- **Undeclared species** in a reaction → `InputFileError`.
- **Undeclared duplicate reactions** — including the classic trap where a generic
  third-body reaction and a specific reaction (e.g. `M` vs `O2`) collide (Cantera issue
  #1193); and third-body efficiencies referencing undeclared species (#1683).
- **Thermo record mismatches** — species name in the thermo block must match the SPECIES
  block; phase flag (S/L/G) must be in column 45.
- `--permissive` downgrades recoverable duplicate transport/thermo errors to warnings.

---

## 2. Cantera Users' Google Group — recurring debugging/simulation failure taxonomy
`https://groups.google.com/g/cantera-users` (recursive scan, 2026-07-19). These are the
real-world failure modes a "check my mechanism / why won't my sim run" tool must catch.

### 2.1 Integrator (CVODES) failures — the #1 category
- **Negative rate constants in pressure-dependent reactions** (PLOG/`pdep_arrhenius`)
  produce `NaN` during log-P interpolation between pressures → `CVodesIntegrator::step:
  CVodes error encountered`. Fails above some T, works below. **Diagnostic the experts
  give:** `np.nonzero(np.isnan(gas.forward_rate_constants))` at the failure T/P/comp;
  verify the *combined* rate constant is never negative at any T in range.
- Recoverable CVODE errors ⇐ very fast/stiff components ⇐ unphysical reaction rates.
- **Unit trap:** activation energies are J/kmol natively in Cantera — silent 1000× errors.

### 2.2 "No ignition" in 0-D ignition-delay simulations
- **Wrong mechanism for the fuel** (e.g. GRI-3.0 used for ammonia — never validated for
  it). **Integration time shorter than the IDT** (ends before ignition). **Wrong reactor
  type** — constant-pressure used where a **constant-volume** reactor is standard for
  shock-tube IDT. Mixture outside flammability.

### 2.3 1-D flame (freeflame / counterflow / stagnation) convergence failures
- **Root cause is usually the mechanism, not the numerics**: bad thermo for a species
  (e.g. CH2HCO) and **reverse rate constants tens of orders above the collision limit**
  make a physically meaningful solution impossible (SF mechanism thread). Debug order:
  *validate kinetics/thermo first, tune the solver second.*
- Numerics that matter once the mechanism is clean: grid `ratio`/`slope`/`curve` +
  `prune`, initial guess (equilibrium products), domain width, transport model, and
  whether conditions are autoignitive / outside flammability limits.

### 2.4 Reactor-network setup errors
- **Division by zero** from `tres = mass / mdot` when `mdot=0` at `t=0`; take an initial
  step first, or give a constant/functional mdot.
- **Excessive stiffness** from a large valve coefficient `K` (drop by 2–3 orders);
  igniter mdot should be tiny vs the main streams, or initialize via
  `set_equivalence_ratio` + equilibrium instead of an igniter stream.

### 2.5 Conversion / data-quality (`ck2yaml`) — see §1.4.

### 2.6 Other recurring themes (application breadth, for context)
Laminar-flame-speed pressure dependence; sensitivity-of-IDT definitions; surface/
heterogeneous kinetics (`ck2yaml` surface files); OpenSMOKE conversion; NASA thermo
accuracy for specific species (ozone); real-gas EoS & critical constants; liquid-phase
species; MATLAB/Windows library-load issues; biomass/coal gasification with char;
particle-combustion coupling; ExtensibleReactor for spray.

---

## 3. Gap map — this suite vs the checks above

**Already implemented (fully or partially):**
- `analysis/reverse_rate_scanner.py` — implied `k_rev(T) = k_fwd/Kc` vs the gas-kinetic
  collision limit, **reverse direction, per reversible reaction, swept over T**. (Partial
  collision-limit: covers the reverse-direction case §1.2/§2.3 emphasise.)
- `analysis/thermo_fitter.py` — NASA-7 `Tmid` discontinuity **repair** (C0/C1-continuous
  refit via KKT), i.e. the *fix* half of §1.1's thermodynamic diagnostic.
- `reduction/csp.py` — CSP eigen-timescale machinery (τ_k = 1/|Re λ_k|), currently wired
  to QSSA/lumping, not to model screening.
- `FusionEngine.validate_element_balance` — element-balance check, but scoped to the
  fusion engine, not exposed as a general per-mechanism check.
- CHEMKIN parser — Fortran-exponent (`1.7+13`) and CRLF **auto-fix**, DUPLICATE semantics,
  `allow_pseudo_species` (permissive undeclared-participant drop).

**Not implemented (the gaps → §4 backlog):**
1. No unified `rmip check`/lint CLI entry point — there is no single "health-check this
   mechanism" command (`grep` confirms no check/lint/diagnose subcommand).
2. **Forward + falloff + PLOG collision-limit screening** (CloudFlame's 3-class, both
   directions). Suite only does reverse-direction implied rate.
3. **NaN / negative rate-constant sweep over a (T,P) grid** — the single most common
   CVODES-failure diagnostic from §2.1; not implemented anywhere.
4. **CSP ultrafast-timescale *model screening*** as a diagnostic (machinery exists, not
   applied to flag unphysically fast reactions/species).
5. **ChemCheck-style syntax linter with diagnostic messages** (line/column + reason),
   distinct from the parser's silent auto-fix.
6. **Thermo-discontinuity *diagnostic report + plot*** (list every species, Cp/H/S jump
   magnitude at Tmid) — only repair exists, no standalone detect/report/visualize.
7. **General element/mass balance + charge balance** exposed for any mechanism.
8. **Undeclared-duplicate detection** (duplicate-but-unmarked; generic-third-body-vs-
   specific overlap, Cantera #1193; third-body efficiencies for undeclared species #1683).
9. **Pressure-dependent reaction sanity** (PLOG negative/non-monotonic pieces; falloff
   Troe parameter sanity; missing high/low-P limits).
10. **Missing/unused species** (declared-but-unused; used-without-thermo; used-without-
    transport).
11. **Thermo T-range coverage** vs the intended simulation T (extrapolation warnings).
12. **Transport data completeness/sanity module** (missing transport; unphysical
    well-depth/diameter/dipole).
13. **Simulation-setup sanity pre-checks** — const-V vs const-P for IDT; integration time
    vs expected IDT; flammability-limit / autoignitive pre-check (the §2.2/§2.3 "no
    ignition" and flame-non-convergence causes).
14. **Unit-sanity check** (Ea magnitude plausibility; catches the J/kmol vs cal/mol trap).

---

## 4. Prioritised implementation backlog (next phase)

Ordered by (failure-frequency in §2) × (cheapness given existing infra). Each is a
candidate `rmip check` sub-diagnostic; the umbrella is item P0.

- **P0 — `rmip check` umbrella command + report object.** One CLI/entry point that runs a
  configurable battery of diagnostics over a mechanism (DB id or CHEMKIN/YAML file) and
  emits a structured report (JSON + human text, later HTML like MechChecker). Everything
  below plugs into it. Reuse the `mechanism_report.py` rendering pattern.
- **P1 — Rate-constant NaN/negative sweep over (T,P).** Load via the existing Cantera
  `MechanismLoader`, evaluate `gas.forward_rate_constants`/`reverse_rate_constants` on a
  (T,P) grid, report any NaN/Inf/negative with the offending reaction + condition.
  Directly targets §2.1, the top real-world failure. Cheapest high-value item.
- **P2 — Full collision-limit screen (forward + falloff + PLOG, both directions).**
  Generalise `reverse_rate_scanner` into a 3-class screen per §1.2; handle >2-reactant
  reactions explicitly (flag, don't mis-compute). Emit the worst-offenders list.
- **P3 — Thermo-discontinuity diagnostic + plot.** Factor the detection out of
  `thermo_fitter`, report every species' Cp/H/S jump at Tmid with magnitude, plot; offer
  the existing repair as `--fix`.
- **P4 — Element/mass + charge balance, general.** Promote `validate_element_balance` to a
  standalone check over any mechanism_id/file; add charge balance for ionised species.
- **P5 — Duplicate / pressure-dependent sanity.** Undeclared-duplicate detection
  (incl. third-body-vs-specific overlap); PLOG monotonicity/negativity; falloff Troe
  sanity; missing P-limits.
- **P6 — Completeness checks.** Unused species, species used without thermo/transport,
  thermo T-range vs a target simulation range, transport completeness/sanity.
- **P7 — Simulation-setup sanity pre-checks.** const-V vs const-P IDT guard;
  integration-time-vs-expected-IDT; flammability / autoignitive pre-check; reactor-network
  zero-mdot/valve-K stiffness lints (§2.2–§2.4).
- **P8 — CSP ultrafast-timescale model screening.** Wire `csp.py` to flag reactions/
  species with unphysically fast timescales as a model-quality diagnostic (§1.2).
- **P9 — Syntax linter with messages.** ChemCheck-style diagnostic messages (line/column
  + reason) layered on the CHEMKIN reader, complementing the silent auto-fix (§1.3/1.4).

### Done
Shipped 2026-07-19 — unified engine + fixer + CLI + GUI, all Cantera-direct
(no DB required), multi-mechanism, with auto + user-choice repairs. Tests:
`src/rmip/tests/test_mechanism_check.py` (17 tests, all green); fixtures generated
by `src/rmip/tests/fixtures/_make_broken_mech.py` (broken_mech / broken_dup /
broken_plog).

- **P0 — umbrella.** `rmip check <mech…>` CLI subcommand (`src/rmip/cli.py`,
  `_cmd_check`) + `MechanismChecker`/`CheckReport`/`Finding`/`FixOption` in
  `src/rmip/analysis/mechanism_check.py`; JSON + coloured-text reports; GUI
  `mechanism_check_gui.py` (registered in `launcher_gui.py`). Runs one mechanism
  or many, all-at-once or one-at-a-time.
- **P1 — rate NaN/negative sweep** over a (T,P) grid on fwd+rev rate constants
  (`check_rate_sweep`).
- **P2 — collision-limit screen**, fwd+rev, all three rate classes at once
  (Arrhenius/falloff/PLOG — evaluated at grid P), >2-body flagged as
  uncheckable (`check_collision_limit`, `collision_limit_kmol`).
- **P3 — thermo Tmid discontinuity** report (`check_thermo_discontinuity`) with
  auto-refit fix reusing `thermo_fitter.refit_from_coeffs`.
- **P4 — element + charge balance** per reaction (`check_element_balance`).
- **P5 — duplicates + pdep sanity.** Unmarked-duplicate detection via a raw-YAML
  scan that works **even when Cantera refuses the file** (`check_duplicates`),
  with a `mark_duplicate` auto-fix; PLOG negative-A / unsorted-P and falloff Troe
  / missing-limit checks (`check_pdep_sanity`), also raw-scan so a negative-PLOG
  file (rejected at `PlogRate::validate` in Cantera 3.x) is still caught + fixed.
- **P6 — completeness.** Unused species (diluent-aware), missing transport,
  thermo T-range vs target (`check_completeness`).
- **P14 — Ea unit sanity** — J/mol and J/kmol vs cal/mol traps, with ÷4.184 /
  ÷4184 reinterpret options (`check_unit_sanity`).
- **Repair engine** `src/rmip/analysis/mechanism_fixer.py` — edits the parsed
  YAML and re-emits a loadable Cantera file. Auto fixes: thermo refit,
  mark-duplicate. Choice fixes (pre-built options in the GUI/CLI): collision
  scale-A / delete / ignore, plog drop-negative, Ea reinterpret, remove-species.
  `--fix auto|all`; every fix re-checked to prove the repair.

Shipped 2026-07-20 — P7/P8/P9 wired into `check` (all Cantera-direct,
DB-free, deliberately narrower than the original backlog wording — see
caveats below). Tests: `src/rmip/tests/test_mechanism_check.py` grew from 17
to 28 (all green); new fixture `broken_integrator.yaml`
(`build_integrator_failure_dict` in `_make_broken_mech.py`).

- **P7 — sim-setup sanity** (`check_sim_setup_sanity`). A bounded
  constant-volume ignition **smoke test**: builds a `ct.IdealGasReactor` +
  `ct.ReactorNet` at the existing benign screening composition and the
  hottest/lowest-pressure point of the existing (T,P) grid, and attempts a
  short, step- *and* wall-clock-bounded `advance` (no `signal.alarm` — the
  deadline is checked inside the loop, so it is safe from a GUI worker
  thread). If CVODES raises or the reactor state goes non-finite, that is a
  `warning`/`integrator-failure` finding. **Deliberately narrower** than the
  original P7 scope (const-V/const-P guard *for a target IDT*,
  integration-time-vs-expected-IDT, flammability pre-check): those need a
  fuel + reactor-type + target input that this DB-free `MechanismChecker`
  does not have — only `self.gas` and a composition-independent T/P grid.
  That target-specific check belongs with `MuqsacBridge` /
  `nominal_sim_gui.py`, which do have a target; P7 here only rules out the
  generic "the integrator cannot even take a step on this mechanism"
  failure class (§2.1).
- **P8 — CSP ultrafast-timescale screening** (`check_csp_timescales`). Calls
  the pure, DB-free helpers already in `rmip.reduction.csp`
  (`chemical_jacobian`/`mode_decomposition`/`timescales_from_eigs`/
  `csp_pointers`) directly against `self.gas` — no `CSPAnalyzer` instance, no
  DB — at the benign screening composition and a reduced 3-point subset
  (first/middle/last) of the configured `T_grid` at the lowest configured
  pressure (an O(n^3) eigendecomposition per point, kept deliberately tiny).
  Flags any finite mode below a conservative `1e-12` s "ultrafast" floor,
  naming the dominant species via the CSP pointer matrix when available. A
  new `csp_max_species` constructor kwarg (default 500, backward-compatible)
  skips the eigendecomposition above that species count with an `info`
  finding instead of paying an O(n^3) cost on a large mechanism. **Uses a
  synthetic/generic screening composition, not a physically-anchored
  ignition state** — for the physically-grounded analysis (needs a fuel +
  DB), use `rmip.reduction.csp.CSPAnalyzer.analyze(at="ignition")`.
- **P9 — syntax linter** (`check_syntax_lint`, new
  `src/rmip/analysis/syntax_lint.py::SyntaxLinter`). A raw, line-by-line text
  scan — no YAML/Cantera parsing — for: (a) the classic CHEMKIN
  missing-exponent typo (`1.7-13` meaning `1.7E-13`); (b) stray tab
  characters; (c) numeric fields truncated mid-token (trailing bare `.` or
  `E`); (d) suspicious characters in a species-name token of a reaction
  equation (handles both CHEMKIN `.inp` and YAML `- equation: ...` forms,
  including the falloff `(+M)` third-body wrapper). Each issue carries a
  1-indexed line and, where determinable, column. Wired into the same
  pre-load fallback path as `duplicates`/`pdep_sanity`/`name_consistency` —
  unlike those, it needs no parsed YAML at all, so it is the one check that
  still reports on a CHEMKIN `.inp` that `ck2yaml` itself refuses to convert
  (today's only other signal there is `ck2yaml`'s raw stderr passthrough via
  `_clean_cantera_error`).

---

## 5. Sources
- LLNL MechChecker — https://combustiontools.llnl.gov/mechcheck/help/ ; "Cloud based tool
  for analysis of chemical kinetic mechanisms", C&F 218 (2020), OSTI 1771432 —
  https://www.osti.gov/servlets/purl/1771432
- KAUST CloudFlame collision-limit / ultrafast-timescale screening —
  https://cloudflame.kaust.edu.sa/Simulations ;
  https://repository.kaust.edu.sa/items/517f2623-1ce2-4258-bc5b-57e610710ffc ;
  "Correction of reaction models using collision limit violation analyses" —
  https://www.sciencedirect.com/science/article/abs/pii/S0010218020301310
- ChemCheck — https://github.com/comocheng/ChemCheck ; NSF PAR —
  https://par.nsf.gov/servlets/purl/10259944 ; fulltext —
  https://repository.library.northeastern.edu/files/neu:bz60f915m/fulltext.pdf
- Cantera `ck2yaml` — https://cantera.org/stable/userguide/ck2yaml-tutorial.html ;
  issues Cantera/cantera #1193, #1683, #1281
- Cantera Users' Group — https://groups.google.com/g/cantera-users (threads: CVODES error
  9e_4Qbuvf8s; no-ignition W1lW4Gq6d0Y; stagnation-flame DvdBp0ceC40; reactor-network
  SZW6ouTVBKM; ck2yaml duplicates YTfAmG7YIQg)
- Verification/validation methodology — Zhukov, ISRN (2012),
  https://onlinelibrary.wiley.com/doi/10.5402/2012/475607
