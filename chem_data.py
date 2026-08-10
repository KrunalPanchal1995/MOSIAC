"""
chem_data.py — Shared combustion chemistry data and utilities.

Provides:
  - ATOMIC_WEIGHTS         : standard atomic weights dict
  - DEFAULT_FUEL_MW        : default fuel molecular weights (fallback table)
  - DEFAULT_STOICH_O2      : default stoichiometric O2 coefficients (nu_O2 per mole fuel)
  - compute_mw(formula)    : compute MW from a chemical formula string (e.g. "C7H16", "NH3")
  - compute_nu_o2(formula) : compute stoichiometric O2 from atom balance (CxHyOzNwSv + O2 → ...)
  - compute_nu_o2_blend(fuels) : blend-weighted stoichiometric O2
  - thread_cap()           : max parallel threads = cpu_count - 5 (floor 1)

Used by: generate_target_opt.py, combustion_target_class.py (both copies), xml2csv.py
"""

import os
import re

# ─────────────────────────────────────────────────────────────────────────────
# Atomic weights (g/mol) — IUPAC 2021 abridged
# ─────────────────────────────────────────────────────────────────────────────
ATOMIC_WEIGHTS: dict = {
    "H":  1.008,
    "He": 4.003,
    "Li": 6.941,
    "Be": 9.012,
    "B":  10.81,
    "C":  12.011,
    "N":  14.007,
    "O":  15.999,
    "F":  18.998,
    "Ne": 20.180,
    "Na": 22.990,
    "Mg": 24.305,
    "Al": 26.982,
    "Si": 28.086,
    "P":  30.974,
    "S":  32.065,
    "Cl": 35.453,
    "Ar": 39.948,
    "K":  39.098,
    "Ca": 40.078,
    "Fe": 55.845,
    "Cu": 63.546,
    "Zn": 65.38,
    "Br": 79.904,
    "Kr": 83.798,
    "Mo": 95.96,
    "Ag": 107.868,
    "I":  126.904,
    "Cs": 132.905,
    "Ba": 137.327,
    "W":  183.84,
    "Pt": 195.084,
    "Au": 196.967,
    "Hg": 200.59,
    "Pb": 207.2,
}

# ─────────────────────────────────────────────────────────────────────────────
# Default fuel tables (hard-coded fallbacks; prefer compute_mw / compute_nu_o2)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_FUEL_MW: dict = {
    # Bath / oxidizer / diluent species (set to 0 → excluded from φ calc)
    "O2":  32.0,  "o2":  32.0,
    "N2":  28.0,  "n2":  28.0,
    "AR":  39.948,"Ar":  39.948,"ar": 39.948,
    "HE":  4.003, "He":  4.003, "he": 4.003,
    "CO2": 44.0,  "co2": 44.0,
    "H2O": 18.0,  "h2o": 18.0,
    # Fuels
    "H2":        2.016,  "h2":        2.016,
    "CO":        28.01,  "co":        28.01,
    "CH4":       16.043,
    "C2H4":      28.054,
    "C2H6":      30.069,
    "C3H8":      44.097,
    "C4H10":     58.123,
    "C4H6":      54.092,
    "CH2O":      30.026,
    "CH3OH":     32.042,
    "C2H5OH":    46.068,
    "NH3":       17.031,
    "N2H4":      32.052,
    "NC7H16":   100.205,  "nc7h16":  100.205,
    "NC12H26":  170.338,
    "C7H8":      92.141,
    "IC16H34":  226.441,
    "C12H23":   167.311,
    "OME3":     136.147,
    "MB-C5H10O2":  86.132,
}

DEFAULT_STOICH_O2: dict = {
    # nu_O2 = stoichiometric moles of O2 per mole of fuel
    # bath / diluents
    "O2": 0.0, "o2": 0.0,
    "N2": 0.0, "n2": 0.0,
    "AR": 0.0, "Ar": 0.0, "ar": 0.0,
    "HE": 0.0, "He": 0.0, "he": 0.0,
    "CO2": 0.0, "co2": 0.0,
    "H2O": 0.0, "h2o": 0.0,
    # fuels (computed from CxHyOzNwSv + nu_O2·O2 → xCO2 + y/2·H2O + ...)
    "H2":        0.5,
    "h2":        0.5,
    "CO":        0.5,
    "co":        0.5,
    "CH4":       2.0,
    "C2H4":      3.0,
    "C2H6":      3.5,
    "C3H8":      5.0,
    "C4H10":     6.5,
    "C4H6":      5.5,
    "CH2O":      1.0,
    "CH3OH":     1.5,
    "C2H5OH":    3.0,
    "NH3":       0.75,
    "N2H4":      1.0,
    "NC7H16":   11.0,
    "nc7h16":   11.0,
    "NC12H26":  18.5,
    "C7H8":      9.0,
    "IC16H34":  24.5,
    "C12H23":   17.75,
    "OME3":      5.75,
    "MB-C5H10O2": 5.25,
}


# ─────────────────────────────────────────────────────────────────────────────
# Formula parser
# ─────────────────────────────────────────────────────────────────────────────

def parse_formula(formula: str) -> dict:
    """
    Parse a chemical formula string into element→count dict.
    Supports fractional counts (for biomass): 'C1H1.74O0.69N0.01'.
    Does NOT handle nested parentheses (not needed for combustion fuels).

    Examples:
      "H2"       → {"H": 2.0}
      "C7H16"    → {"C": 7.0, "H": 16.0}
      "C1H1.74O0.69N0.01" → {"C": 1.0, "H": 1.74, "O": 0.69, "N": 0.01}
    """
    # Match element symbol (capital + optional lowercase) followed by optional count (int or float)
    pattern = r'([A-Z][a-z]?)(\d+\.?\d*|\.?\d+)?'
    elements: dict = {}
    for m in re.finditer(pattern, formula):
        elem = m.group(1)
        count_str = m.group(2)
        count = float(count_str) if count_str else 1.0
        elements[elem] = elements.get(elem, 0.0) + count
    return elements


def compute_mw(formula: str) -> float:
    """
    Compute molecular weight from a chemical formula string.
    Falls back to DEFAULT_FUEL_MW if formula is a species name.

    Returns 0.0 if formula is empty or unrecognised.
    """
    if not formula:
        return 0.0
    # Try exact lookup first (handles species names like "NC7H16")
    if formula in DEFAULT_FUEL_MW:
        return DEFAULT_FUEL_MW[formula]
    elements = parse_formula(formula)
    if not elements:
        return 0.0
    mw = 0.0
    for elem, count in elements.items():
        mw += ATOMIC_WEIGHTS.get(elem, 0.0) * count
    return mw


def compute_nu_o2(formula: str) -> float:
    """
    Compute stoichiometric O2 requirement (nu_O2) from atom balance:

        CₓHᵧOᵤNᵥSᵥ  +  nu_O2 · O2  →  x·CO2 + y/2·H2O + w/2·N2 + v·SO2

    For inert species (no C/H/S) → returns 0.0.
    For a species key in DEFAULT_STOICH_O2 → uses the lookup first (faster, avoids
    parsing species names like "NC7H16").
    Oxygen atoms already in the fuel reduce the O2 requirement.
    Sulphur contribution: 1 S atom needs 1 O2.

    Returns nu_O2 (moles O2 per mole fuel).  May be 0.0 for non-combustibles.
    """
    if not formula:
        return 0.0
    if formula in DEFAULT_STOICH_O2:
        return DEFAULT_STOICH_O2[formula]
    elements = parse_formula(formula)
    C  = elements.get("C",  0.0)
    H  = elements.get("H",  0.0)
    O  = elements.get("O",  0.0)
    S  = elements.get("S",  0.0)
    # nu_O2 = C + H/4 + S - O/2
    nu = C + H / 4.0 + S - O / 2.0
    return max(nu, 0.0)


def compute_nu_o2_blend(fuels: list) -> float:
    """
    Compute blend-weighted stoichiometric O2.

    Args:
        fuels: list of (formula_or_species, mole_fraction) tuples.
               Mole fractions need not sum to 1 (will be normalised).

    Returns:
        Total nu_O2 = sum(x_i * nu_O2_i) / sum(x_i)
    """
    total_x = 0.0
    total_nu = 0.0
    for formula, xf in fuels:
        xf = float(xf)
        if xf <= 0:
            continue
        total_x += xf
        total_nu += xf * compute_nu_o2(formula)
    if total_x == 0:
        return 0.0
    return total_nu / total_x


def compute_phi_from_blend(fuel_dict: dict, x_o2: float) -> float:
    """
    Compute equivalence ratio φ from mole fractions.

    Args:
        fuel_dict: {species: mole_fraction} for fuel species
        x_o2:     mole fraction of O2 in the mixture

    Returns φ = (F/A)_actual / (F/A)_stoich
    """
    total_fuel = sum(fuel_dict.values())
    if total_fuel <= 0 or x_o2 <= 0:
        return 0.0
    o2_required = sum(
        xf * compute_nu_o2(sp)
        for sp, xf in fuel_dict.items()
    )
    if o2_required <= 0:
        return 0.0
    F_A_actual = total_fuel / x_o2
    F_A_stoich = total_fuel / o2_required
    return F_A_actual / F_A_stoich


# ─────────────────────────────────────────────────────────────────────────────
# Thread cap
# ─────────────────────────────────────────────────────────────────────────────

def thread_cap() -> int:
    """
    Maximum safe parallel threads = os.cpu_count() - 5 (floor 1).
    Reserves 5 cores for OS + monitoring processes.
    """
    n = (os.cpu_count() or 4) - 5
    return max(n, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Quick self-test (run as script)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("H2",       {"mw": 2.016,    "nu": 0.5}),
        ("CH4",      {"mw": 16.043,   "nu": 2.0}),
        ("C7H16",    {"mw": 100.205,  "nu": 11.0}),
        ("C2H5OH",   {"mw": 46.068,   "nu": 3.0}),
        ("NH3",      {"mw": 17.031,   "nu": 0.75}),
        ("C1H1.74O0.69N0.01", {"mw": None,  "nu": None}),  # biomass — print only
    ]
    print("chem_data self-test")
    print(f"  thread_cap() = {thread_cap()}")
    for formula, expected in tests:
        mw  = compute_mw(formula)
        nu  = compute_nu_o2(formula)
        elems = parse_formula(formula)
        print(f"  {formula:20s}  MW={mw:8.3f}  nu_O2={nu:.4f}  atoms={elems}")
    print("Done.")
