# W4 — Thermo / transport data provenance & cross-check

**Closes:** P10 (Arkane K-salt thermo off vs JANAF — systematic ΔHf/ΔG), P27 (O3
NASA-polynomial dataset dispute); surfaces P19 (charged species).
**Effort:** M · **Risk:** Med (reference-data licensing) · **Depends on:**
`thermo_fitter.py`, shipped `mechanism_check` thermo checks.

## Problem
There is no way to tell whether a mechanism's species thermo is *trustworthy*.
Real cases: Arkane's ΔHf/ΔG for K-salts is systematically off vs JANAF (Cp/S fine),
and experts disagree on the "correct" O3 NASA polynomial. The suite can repair a
*discontinuity* (`thermo_fitter`) but cannot compare a species against an
authoritative reference and flag an outlier with the size of the discrepancy.

## Goal
A provenance/cross-reference tool: for each species, compare its NASA-7-derived
ΔHf(298), S(298), and Cp(T) against a reference database (Burcat/ATcT/JANAF) matched
by formula/InChI, and flag outliers with the **discrepancy magnitude** and which
property diverges (systematic ΔHf vs random noise — the P10 signature).

## Design

New module `src/rmip/analysis/thermo_provenance.py`:
- **Reference store** `src/rmip/data/thermo_refs/` — a curated, redistributable
  subset first (elements + common combustion species from the Burcat/ATcT tables,
  which are public); the loader supports pointing at a user-supplied full
  Burcat/ATcT file so we don't vendor a license-encumbered dataset. Env-isolation:
  no new pip deps; parse the plain-text tables ourselves.
- `class ThermoProvenanceChecker`:
  - match species by composition + (optional) InChI/name alias table.
  - evaluate H(298)/S(298)/Cp(T-grid) from the mechanism's NASA-7 (reuse
    `thermo_fitter.nasa7_*`) and from the reference.
  - `Finding` per species when |ΔHf mech − ref| exceeds a tolerance, tagged with
    absolute + relative discrepancy and a "systematic (ΔHf/ΔG only) vs distributed"
    classifier (the P10 diagnostic).
  - `FixOption(kind="choice")`: adopt-reference-thermo / keep / show-both — never
    auto-overwrite thermo (provenance is a human call).
- **Charged-species surfacing (P19)** — list ionic species (non-zero
  `species.charge`) and confirm the mechanism declares an electron/`E` and
  charge-balances (the charge check already exists in
  `mechanism_check.check_element_balance`); cross-link here.
- **Transport sanity** — flag unphysical Lennard-Jones well-depth/diameter/dipole
  (already partially in completeness); compare against reference transport where
  available.

## CLI / GUI
- `rmip thermo-check <mech> [--refs burcat.dat] [--tol-hf 2.0] [--json]`.
- New check id `thermo_provenance` in the `rmip check` battery (opt-in; needs a
  refs file), so it renders in the shipped GUI.

## Tests (`src/rmip/tests/test_thermo_provenance.py`)
- Fixture: a mechanism whose one species' `a6` (enthalpy) coefficient is perturbed
  → flagged as a systematic ΔHf outlier of the injected magnitude; unperturbed
  species pass.
- O3-style: two datasets for the same species disagree → both reported with the
  discrepancy.

## Acceptance
Given a refs file, a species with a wrong ΔHf is flagged with the numeric
discrepancy and classified systematic; clean species pass; no auto-overwrite.

## Open decision
Which reference to ship as the built-in subset (Burcat is the pragmatic default;
ATcT is more authoritative but larger). Default to Burcat-subset + user-supplied
override; ATcT support behind the same loader interface.
*Resolved:* built-in = a curated **ATcT/CODATA scalar subset** (25 common species,
physical constants, redistributable); user-supplied Burcat/ATcT via
`load_chemkin_thermo_refs` (CHEMKIN THERMO format).

---

## ✅ DONE — shipped 2026-07-19

- **Module:** `src/rmip/analysis/thermo_provenance.py` — `ThermoProvenanceChecker`
  + `BUILTIN_REFS` (25 species: ΔHf°298/S°298/Cp°298 from ATcT/CODATA) +
  `load_chemkin_thermo_refs` (user Burcat THERM.DAT loader, name-matched) +
  `render_comparison_table`. Compares NASA-7-derived ΔHf/S/Cp(298) per species;
  flags outliers with the **numeric discrepancy** and the P10 classifier:
  `systematic-enthalpy` (ΔHf off, S/Cp fine) vs `distributed`. Matching is
  **name + composition guarded** (isomers can't false-match). Physics validated
  up-front: clean h2o2/GRI-3.0 deviate ≤1.9 kJ/mol from ATcT → default 8 kJ/mol
  tolerance gives **zero false positives on 24 matched GRI species**.
- **Repair:** `mechanism_fixer.shift_enthalpy_to_ref` — shifts a6 of both
  T-ranges by −ΔH/R (moves ΔHf onto the reference; Cp/S untouched). **Choice**
  fix, recommended only for the systematic case; never auto (provenance is a
  human call, per plan / P27).
- **Engine:** new `thermo_provenance` check in the `rmip check` battery
  (warning-only severity so references legitimately disagreeing never fails a
  verdict); shows in the mechanism-check GUI automatically.
- **CLI:** `rmip thermo-check <mech> [--refs THERM.DAT --tol-hf --tol-s --tol-cp
  --all --json]` — deviation table ranked by |ΔHf|.
- **Tests:** `src/rmip/tests/test_thermo_provenance.py` — 12 tests, all green.
  Verified: no false positives (h2o2 + GRI); injected +25 kJ/mol OH error
  flagged systematic with correct magnitude and repaired by the shift fix
  (re-check clean); composition guard; user-refs loader round-trip; CLI codes.

Closes **P10, P27**; P19's symptom (charge) remains covered by
`check_element_balance`.
