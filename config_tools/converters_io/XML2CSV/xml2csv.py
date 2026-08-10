#!/usr/bin/env python3
"""
xml2csv.py — Convert ReSpecTh/RKD XML combustion datasets to target.opt / addendum.add

Fixes vs original:
  - Functionized: main(xml_dir, out_dir, fuel_list, input_fuel)
  - CWD-independence: xml_dir / out_dir parameters; no implicit os.listdir()
  - target.opt opened with "w" before the loop (overwrite), "a" per-file (append)
  - AssertionError hard stops → logged warnings + continue (keeps partial output)
  - and/or precedence bug in flame-type classifier fixed
  - molwt[species] KeyError fixed: compute_mw(species) from chem_data
  - bibliographyLink extracted and written to references.bib
  - Stoichiometry sourced from chem_data.DEFAULT_STOICH_O2 (with atom-balance fallback)
  - Mixed-indent TabErrors fixed (pure 4-space throughout)

Usage:
    python xml2csv.py [xml_dir] [out_dir]
    python xml2csv.py                          # defaults: cwd -> cwd
    python xml2csv.py /path/to/xmls /path/out  # explicit dirs

API:
    from xml2csv import main
    main("/path/to/xmls", "/path/out",
         fuel_list=["NH3", "H2"],
         input_fuel={"a": "NH3", "b": "H2"})
"""

import sys
import os
import re
import logging
import xml.etree.ElementTree as ET
import numpy as np
import csv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Load shared chemistry data
# ─────────────────────────────────────────────────────────────────────────────
try:
    _root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from chem_data import (
        DEFAULT_STOICH_O2 as _DEFAULT_NU,
        compute_mw as _compute_mw,
        compute_nu_o2 as _compute_nu_o2,
    )
    _BASE_STOICH = dict(_DEFAULT_NU)
    _HAS_CHEM_DATA = True
except ImportError:
    log.warning("chem_data.py not found; using built-in stoichiometry fallback table.")
    _BASE_STOICH = {
        "H2": 0.5, "CO": 0.5, "O2": 0.0, "N2": 0.0, "h2": 0.5, "co": 0.5,
        "o2": 0.0, "n2": 0.0, "HE": 0.0, "AR": 0.0, "He": 0.0, "Ar": 0.0,
        "NH3": 0.75, "H2O": 0.0, "CO2": 0.0, "C2H5OH": 3.0, "CH4": 2.0,
        "CH3OH": 1.5, "NC7H16": 11.0, "MB-C5H10O2": 6.5,
    }
    def _compute_mw(sp):
        return 0.0
    def _compute_nu_o2(sp):
        return 0.0
    _HAS_CHEM_DATA = False

# ─────────────────────────────────────────────────────────────────────────────
# Fuel_type global (single or multi)
# ─────────────────────────────────────────────────────────────────────────────
FUEL_TYPE = "Multi"

# ─────────────────────────────────────────────────────────────────────────────
# Flat CSV schema mirroring generate_target_opt.py's _TARGET_ROW_COLUMNS, so a
# CSV emitted here is directly consumable by the Experimental Data tab's
# "Import from CSV" with zero column-mapping. For multi-fuel/bath-gas entries
# (dicts keyed by fuel/species letter), only the FIRST item is flattened into
# this row's fuel_species/fuel_xf (or bath_species/bath_xf) — a known
# simplification versus the full multi-species .target line, which retains
# every species.
# ─────────────────────────────────────────────────────────────────────────────
_CSV_FIELDNAMES = [
    "dataset_id", "target_type", "fuel_species", "fuel_xf",
    "oxidizer_species", "ox_xf", "bath_species", "bath_xf",
    "T", "P", "P_unit", "phi", "observed", "deviation_pct", "data_weight",
]


def _first_species_xf(id_dict, xf_dict):
    """First (species, mole-fraction) pair from a {letter: value} dict, or ("", "")."""
    if not id_dict:
        return "", ""
    first_key = next(iter(id_dict))
    return str(id_dict[first_key]), str(xf_dict.get(first_key, ""))


def _nu_o2(species):
    """Return stoichiometric O2 coefficient for species (with atom-balance fallback)."""
    v = _BASE_STOICH.get(species, None)
    if v is not None:
        return v
    return _compute_nu_o2(species)


def _mol_wt(species):
    """Return MW for species (with atom-balance fallback from chem_data)."""
    return _compute_mw(species) or 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Bibliography extraction
# ─────────────────────────────────────────────────────────────────────────────

def _extract_bib(root, citekey):
    """
    Extract bibliographyLink/details from a ReSpecTh XML root element.
    Returns a BibTeX @article{...} string, or None if details are missing.
    """
    bib_el = root.find(".//bibliographyLink")
    if bib_el is None:
        return None
    details = bib_el.find("details")
    doi_el = bib_el.find("referenceDOI")
    doi = doi_el.text.strip() if doi_el is not None and doi_el.text else ""
    if details is None:
        desc = bib_el.find("description")
        if desc is not None and desc.text:
            return f"% {citekey}: {desc.text.strip()}\n"
        return None
    def _t(tag):
        el = details.find(tag)
        return el.text.strip() if el is not None and el.text else ""
    author = _t("author")
    journal = _t("journal")
    title = _t("title")
    year = _t("year")
    volume = _t("volume")
    number = _t("number")
    pages = _t("pages")
    entry = (
        f"@article{{{citekey},\n"
        f"  author  = {{{author}}},\n"
        f"  title   = {{{title}}},\n"
        f"  journal = {{{journal}}},\n"
        f"  year    = {{{year}}},\n"
        f"  volume  = {{{volume}}},\n"
        f"  number  = {{{number}}},\n"
        f"  pages   = {{{pages}}},\n"
        f"  doi     = {{{doi}}},\n"
        f"}}\n"
    )
    return entry


def _make_citekey(root, dataset_name):
    """Generate a stable Author+Year citekey from bibliographyLink/details."""
    bib_el = root.find(".//bibliographyLink")
    if bib_el is None:
        return dataset_name
    details = bib_el.find("details")
    if details is None:
        return dataset_name
    author_el = details.find("author")
    year_el = details.find("year")
    author = author_el.text.strip() if author_el is not None and author_el.text else ""
    year = year_el.text.strip() if year_el is not None and year_el.text else ""
    first_author = author.split(" and ")[0].split(",")[0].strip().split()[-1]
    return f"{first_author}{year}" if first_author and year else dataset_name


# ─────────────────────────────────────────────────────────────────────────────
# Pressure unit conversion helper
# ─────────────────────────────────────────────────────────────────────────────

def _pressure_factor(p_unit, context):
    factors = {
        "mbar": 0.001 * 1e5,
        "bar": 1e5,
        "atm": 101325.0,
        "Pa": 1.0,
        "kPa": 1e3,
        "KPa": 1e3,
        "Torr": 133.322,
        "torr": 133.322,
        "MPa": 1e6,
        "mPa": 1e6,
    }
    if p_unit in factors:
        return factors[p_unit], "Pa"
    log.warning("Unknown pressure unit '%s' in %s — treating as Pa", p_unit, context)
    return 1.0, p_unit


# ─────────────────────────────────────────────────────────────────────────────
# Ignition type parser
# ─────────────────────────────────────────────────────────────────────────────

_IGN_SPECIES_MW = {
    "OH*": ("OH*", 17), "OHEX": ("OH*", 17), "OHV": ("OH*", 17),
    "OH": ("OH", 17),
    "CH": ("CH", 13), "CHEX": ("CH*", 13), "CH*": ("CH*", 13),
    "soot": ("CH", 13),
    "O": ("O", 16),
    "O2": ("O2", 32),
    "C2": ("p", 24),
    "C2H5OH": ("C2H5OH", 46),
    "CH3OH": ("CH3OH", 32),
    "H2O": ("H2O", 18),
    "CH3": ("CH3", 15),
    "CH4": ("CH4", 16),
    "CO": ("CO", 28),
    "CO2": ("CO2", 44),
    "NH3": ("NH3", 17),
    "p": ("p", 17),
}

_IGN_COND_MAP = {
    "max": "max",
    "d/dt max": "dt-max",
    "baseline max intercept from d/dt": "dt-max",
    "baseline min intercept from d/dt": "onset",
    "concentration": "specific",
    "relative concentration": None,  # handled specially
}


def _parse_ign_type(root, file_label):
    """
    Parse <ignitionType> element.
    Returns (ignDef, cond, specific_cond, molWeight) or None on failure.
    """
    ign_el = root.find(".//ignitionType")
    if ign_el is None:
        return None

    raw_target = ign_el.attrib.get("target", "")
    ign_type = ign_el.attrib.get("type", "")
    ignDef = None
    molWeight = 17

    # Match species by priority
    for key, (ign_name, mw) in _IGN_SPECIES_MW.items():
        if key in raw_target:
            ignDef = ign_name
            molWeight = mw
            break

    if ignDef is None:
        # Last-resort: check for "CO;O;"
        if "CO;O;" in raw_target or "CO" in raw_target:
            ignDef = "CO"
            molWeight = 28
        else:
            log.warning("Unknown ignition target '%s' in %s — skipping file", raw_target, file_label)
            return None

    # Parse ignition condition
    if ign_type == "max":
        cond = "max"
        specific_cond = ""
    elif ign_type in ("d/dt max", "baseline max intercept from d/dt"):
        cond = "dt-max"
        specific_cond = ""
    elif ign_type == "baseline min intercept from d/dt":
        cond = "onset"
        specific_cond = ""
    elif ign_type == "concentration":
        cond = "specific"
        units = ign_el.attrib.get("units", "")
        amount = ign_el.attrib.get("amount", "0")
        if units == "mol/cm3":
            sc = float(amount) * 6.022e23
            specific_cond = f"{sc};molecule/cm3"
        else:
            specific_cond = f"{amount};{units}"
    elif ign_type == "relative concentration":
        if ignDef == "p":
            cond = "onset"
            specific_cond = ""
        else:
            cond = "specific"
            amount = ign_el.attrib.get("amount", "")
            units = ign_el.attrib.get("units", "")
            specific_cond = f"{amount};{units}"
    elif ign_type == "relative increase":
        # Same shape as "relative concentration": a fractional change (amount,
        # can be negative for a decrease) relative to baseline, in the target
        # species' own units (usually "unitless"). Confirmed against a real
        # file: <ignitionType target="NH3" type="relative increase"
        # amount="-0.5" units="unitless"/>
        cond = "specific"
        amount = ign_el.attrib.get("amount", "")
        units = ign_el.attrib.get("units", "")
        specific_cond = f"{amount};{units}"
    else:
        log.warning("Unknown ignition delay definition '%s' in %s — skipping file", ign_type, file_label)
        return None

    return ignDef, cond, specific_cond, molWeight


# ─────────────────────────────────────────────────────────────────────────────
# Flame / target type classifier
# ─────────────────────────────────────────────────────────────────────────────

_FLS_MODES = {
    "premixed", "spherical", "modified Bunsen burner", "unstretched",
    "slot burner", "laminar", "outwardly propagating spherical flame",
    "constant volume combustion chamber",
    "extrapolation method to zero stretch: LS",
    "extrapolation method to zero stretch: NQ",
    "cylindrical", "twin flat", "counterflow",
}

# Real ReSpecTh datasets frequently never use the literal kind "flame" for
# laminar-burning-velocity methods — they use the specific apparatus/method
# name directly. These all map to the generic Fls/Unstretched bucket.
# "heat flux burner" is handled separately (see _classify_target) since it
# gets its own exp_tag ("Flf_a") for the imposed-temperature-profile path.
_FLS_KINDS_GENERIC = {
    "outwardly propagating spherical flame",
    "flame cone method",
    "vertical tube flame propagation method",
    "flame area method",
    "laminar flat flame matrix burner",
    "externally heated diverging channel",
}

# Base JSR/flow-reactor apparatus kinds, matched after stripping a trailing
# material qualifier like "(quartz)"/"(fused silica)" — real datasets use
# many such variants ("stirred reactor (quartz)", "Perfectly stirred reactor
# (silica)", "flow reactor (alumina)", "jet stirred reactor" without
# "measurement", etc.) that a literal-string match would all miss.
_JSR_BASE_KINDS = {
    "stirred reactor", "flow reactor", "jet stirred reactor", "perfectly stirred reactor",
}

# Keyword fallback for flame-speed apparatus kinds not explicitly listed
# above — classified as generic Fls with a WARNING (not a skip) so future
# unlisted apparatus-name variants degrade gracefully instead of silently
# dropping data.
_FLS_FALLBACK_KEYWORDS = ("flame", "burner", "propagat", "bunsen")


def _strip_kind_qualifier(kind):
    """Normalize an apparatus 'kind' string for robust matching: lowercase
    and strip a trailing parenthetical material qualifier, e.g.
    'Stirred reactor (quartz)' -> 'stirred reactor'."""
    if not kind:
        return ""
    return re.sub(r"\s*\([^)]*\)\s*$", "", kind).strip().lower()


def _classify_target(Target_kind, Target_mode, add_mod, file_label):
    """
    Classify the experimental target type.
    Returns (exp, exp_tag, Simulation_type, MeasurnmentType, reactorType,
             ignitionMode, flameType) or None on unknown type.
    """
    base_kind = _strip_kind_qualifier(Target_kind)

    # Fix: parenthesise the and/or compound condition properly
    if Target_kind == "flame" and "HFM" not in add_mod and Target_mode in _FLS_MODES:
        return (
            "laminar burning velocity", "Fls", "UnstretchedPremixed",
            "", "", "", "Unstretched",
        )
    if Target_kind in ("shock tube", "ignition delay measurement"):
        return (
            "ignition delay", "Tig", "Isochor Homo Reactor",
            "", "", "reflected", "",
        )
    if Target_kind in ("stirred reactor", "flow reactor", "jet stirred reactor measurement"):
        return (
            "composition", "JSR", "Isobar Homo Reactor",
            "CONC", "FlowReactor", "", "",
        )
    if base_kind in _JSR_BASE_KINDS:
        return (
            "composition", "JSR", "Isobar Homo Reactor",
            "CONC", "FlowReactor", "", "",
        )
    if Target_kind == "flame" and Target_mode == "burner-stabilized":
        return (
            "composition", "Flf", "UnstretchedPremixed",
            "CONC", "", "", "HeatFlux",
        )
    if Target_kind == "flame" and "HFM" in add_mod:
        return (
            "laminar burning velocity", "Flf", "UnstretchedPremixed",
            "velocity", "", "", "HeatFlux",
        )
    if Target_kind == "rapid compression machine":
        return (
            "ignition delay", "RCM", "Isochor Homo Reactor",
            "", "", "reflected", "",
        )
    if base_kind == "heat flux burner":
        # Heat-flux-burner method: an imposed experimental T(x) profile
        # constrains the simulation (see combustion_target_class.py's "Flf"
        # ExpTempFile handling, which fires on any target containing "Flf")
        # -> distinct exp_tag "Flf_a" so the GUI/backend treat it as the
        # imposed-temperature-profile flame type, not the generic Fls bucket.
        return (
            "laminar burning velocity", "Flf_a", "UnstretchedPremixed",
            "velocity", "", "", "HeatFlux",
        )
    if base_kind in _FLS_KINDS_GENERIC:
        return (
            "laminar burning velocity", "Fls", "UnstretchedPremixed",
            "", "", "", "Unstretched",
        )
    if Target_kind and any(kw in Target_kind.lower() for kw in _FLS_FALLBACK_KEYWORDS):
        log.warning(
            "Classifying unrecognized kind='%s' mode='%s' in %s as generic "
            "laminar burning velocity (Fls) via fallback heuristic — verify.",
            Target_kind, Target_mode, file_label,
        )
        return (
            "laminar burning velocity", "Fls", "UnstretchedPremixed",
            "", "", "", "Unstretched",
        )
    log.warning("Unknown experiment type: kind='%s', mode='%s' in %s — skipping",
                Target_kind, Target_mode, file_label)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Per-file XML parser
# ─────────────────────────────────────────────────────────────────────────────

def _parse_xml_file(xml_path, fuel_list, input_fuel, stoichiometry, solver="cantera"):
    """
    Parse a single ReSpecTh/RKD XML file.
    Returns (add_block: str, target_rows: str, bib_entry: str | None,
    csv_rows: list[dict]) or (None, None, None, None) if parsing fails or
    the file should be skipped. csv_rows mirrors target_rows in flat,
    RMIP-Experimental-Data-tab-compatible form (see _CSV_FIELDNAMES).
    """
    file_ = os.path.basename(xml_path)
    dataset = file_.split(".")[0]
    log.info("Parsing %s", file_)

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as exc:
        log.warning("XML parse error in %s: %s — skipping", file_, exc)
        return None, None, None, None

    root = tree.getroot()

    # ── Metadata ────────────────────────────────────────────────────────────
    Target = None
    Target_kind = None
    Target_mode = None
    add_mod = []
    bibliography = None
    commonProp = None
    dataGroup = None

    for el in root.findall(".//*"):
        tag = el.tag
        if "experimentType" in tag:
            Target = root.find(".//experimentType")
            Target = Target.text if Target is not None else None
        if "kind" in tag:
            k = root.find(".//kind")
            Target_kind = k.text if k is not None else Target
        if "mode" in tag:
            ms = root.findall(".//mode")
            for m in ms:
                if m.text:
                    add_mod.append(m.text)
            if ms:
                Target_mode = ms[0].text
        if "bibliographyLink" in tag:
            bibliography = root.find(".//bibliographyLink")
        if "commonProperties" in tag:
            commonProp = root.find(".//commonProperties")
        if "dataGroup" in tag:
            dataGroup = root.findall(".//dataGroup")

    if Target_kind is None:
        Target_kind = Target

    # ── Bibliography ─────────────────────────────────────────────────────────
    citekey = _make_citekey(root, dataset)
    bib_entry = _extract_bib(root, citekey)

    # ── addendum preamble ────────────────────────────────────────────────────
    add = f"{dataset}:\n"

    # Determine Fls_type (solver type)
    count = count_p = 0
    if dataGroup:
        for group in dataGroup:
            for child in group:
                if child.tag == "property" and child.attrib.get("name") == "composition":
                    count += 1
                elif child.tag == "property" and child.attrib.get("name") == "pressure":
                    count_p += 1

    if count == 0 and count_p == 0:
        Fls_type = "phi"
        add += f" solver: {solver}\n type: phi\n Fuel: {input_fuel}\n"
    elif count == 0 and count_p == 1:
        Fls_type = "pressure"
        add += f" solver: {solver}\n type: pressure\n"
    else:
        Fls_type = "composition"
        add += f" solver: {solver}\n"

    # ── Ignition type ────────────────────────────────────────────────────────
    MeasurnmentType = ""
    ignDef = cond = specific_cond = ""
    molWeight = 17

    for el in root.findall("*"):
        if "ignitionType" in el.tag:
            result = _parse_ign_type(root, file_)
            if result is None:
                return None, None, None, None
            ignDef, cond, specific_cond, molWeight = result
            MeasurnmentType = root.find(".//ignitionType").attrib.get("target", "") + \
                              root.find(".//ignitionType").attrib.get("type", "")
            add += (f" ign_delay_def: {ignDef}\n ign_cond: {cond}\n"
                    f" specific_cond: {specific_cond}\n mol_wt: {molWeight}\n")

    if commonProp is None or dataGroup is None:
        log.warning("Missing commonProperties or dataGroup in %s — skipping", file_)
        return None, None, None, None

    # ── Parse commonProperties ───────────────────────────────────────────────
    properties = {}
    concentartion_Dict = {}
    unsrt = {}

    for child in commonProp:
        if child.tag != "property":
            continue
        name = child.attrib.get("name", "")

        if name in ("initial composition", "concentration"):
            for zero in child:
                temp = {}
                for minusOne in zero:
                    if minusOne.tag == "speciesLink":
                        temp["name"] = minusOne.attrib.get("preferredKey", "")
                        temp["CAS"] = minusOne.attrib.get("CAS", "")
                        temp["InChI"] = minusOne.attrib.get("InChI", "")
                        temp["SMILES"] = minusOne.attrib.get("SMILES", "")
                        temp["chemName"] = minusOne.attrib.get("chemName", "")
                    elif minusOne.tag == "amount":
                        temp["value"] = minusOne.text
                        temp["unit"] = minusOne.attrib.get("units", "")
                if "name" in temp:
                    concentartion_Dict[temp["name"]] = temp
            properties[name] = concentartion_Dict

        elif name in ("evaluated standard deviation", "uncertainty"):
            type_ = child.attrib.get("reference", "")
            unsrt_Dict = {}
            if type_ == "composition":
                for i in child:
                    if i.tag == "speciesLink":
                        unsrt_Dict["specification"] = i.attrib
                        type_ = type_ + "_" + i.attrib.get("preferredKey", "")
            unsrt_Dict["type"] = child.attrib.get("kind", "")
            if "method" in child.attrib:
                unsrt_Dict["method"] = child.attrib["method"]
            else:
                unsrt_Dict["method"] = "instrumental error"
                unsrt_Dict["bound"] = child.attrib.get("bound", "")
                if "label" in child.attrib:
                    unsrt_Dict["label"] = child.attrib["label"]
            unsrt_Dict["sourcetype"] = child.attrib.get("sourcetype", "")
            unsrt_Dict["units"] = child.attrib.get("units", "")
            for zero in child:
                unsrt_Dict["value"] = zero.text
            unsrt[type_] = unsrt_Dict
            properties["Unsrt"] = unsrt

        elif name == "pressure":
            temp = {}
            if "label" in child.attrib:
                temp["label"] = child.attrib["label"]
            temp["unit"] = child.attrib.get("units", "")
            temp["sourcetype"] = child.attrib.get("sourcetype", "")
            for zero in child:
                if zero.tag == "value":
                    temp["value"] = zero.text
            properties["pressure"] = temp

        elif name == "temperature":
            temp = {}
            temp["label"] = child.attrib.get("label", "")
            temp["unit"] = child.attrib.get("units", "")
            temp["sourcetype"] = child.attrib.get("sourcetype", "")
            for zero in child:
                if zero.tag == "value":
                    temp["value"] = zero.text
            properties["temperature"] = temp

        elif name == "pressure rise":
            temp = {}
            temp["label"] = child.attrib.get("label", "")
            temp["unit"] = child.attrib.get("units", "")
            temp["sourcetype"] = child.attrib.get("sourcetype", "")
            for zero in child:
                if zero.tag == "value":
                    temp["value"] = float(zero.text) * 100
            properties["pressure rise"] = temp

        elif name == "volume":
            temp = {}
            temp["label"] = child.attrib.get("label", "")
            temp["unit"] = child.attrib.get("units", "")
            temp["sourcetype"] = child.attrib.get("sourcetype", "")
            for zero in child:
                if zero.tag == "value":
                    temp["value"] = float(zero.text)
            properties["volume"] = temp

        elif name == "residence time":
            temp = {}
            temp["label"] = child.attrib.get("label", "")
            temp["unit"] = child.attrib.get("units", "")
            temp["sourcetype"] = child.attrib.get("sourcetype", "")
            for zero in child:
                if zero.tag == "value":
                    temp["value"] = float(zero.text)
            properties["residence time"] = temp

    # ── Parse dataGroups ─────────────────────────────────────────────────────
    datagroupDict = {}
    for group in dataGroup:
        Dict = {}
        points = {}
        temp = {}
        group_id = group.attrib.get("id", "dg1")

        for ind, child in enumerate(group):
            if child.tag == "property":
                name = child.attrib.get("name", "")
                if name in ("composition", "concentration", "initial composition", "final composition"):
                    tem = {}
                    for zero in child:
                        tem["specification"] = zero.attrib
                    tem["name"] = name
                    tem["id"] = child.attrib.get("id", "")
                    tem["label"] = child.attrib.get("label", "")
                    tem["sourcetype"] = child.attrib.get("sourcetype", "")
                    tem["units"] = child.attrib.get("units", "")
                    temp[child.attrib.get("id", "")] = tem

                elif (name == "uncertainty" and child.attrib.get("units") == "cm/s") or \
                     (name == "evaluated standard deviation" and child.attrib.get("units") == "cm/s"):
                    if "laminar burning velocity" not in unsrt:
                        unsrt["laminar burning velocity"] = {}
                    unsrt["laminar burning velocity"]["var"] = child.attrib.get("id", "")
                    unsrt["laminar burning velocity"]["type"] = child.attrib.get("kind", "")
                    unsrt["laminar burning velocity"]["units"] = child.attrib.get("units", "")

                elif name == "evaluated standard deviation" and \
                        child.attrib.get("reference") == "ignition delay":
                    unsrt["ignition delay"] = {}
                    unsrt["ignition delay"]["var"] = child.attrib.get("id", "")
                    unsrt["ignition delay"]["type"] = child.attrib.get("kind", "")
                    unsrt["ignition delay"]["units"] = child.attrib.get("units", "")

                else:
                    temp[child.attrib.get("id", "")] = child.attrib

            elif child.tag == "dataPoint":
                data = {}
                for zero in child:
                    data[zero.tag] = zero.text
                points[str(ind - 2)] = data

        Dict["Variables"] = temp
        Dict["DataPoints"] = points
        datagroupDict[group_id] = Dict

    if "dg1" not in datagroupDict:
        log.warning("No dg1 group in %s — skipping", file_)
        return None, None, None, None

    ndpt = len(datagroupDict["dg1"]["DataPoints"])
    if ndpt == 0:
        log.warning("No data points in dg1 of %s — skipping", file_)
        return None, None, None, None

    # ── Extract uncertainty value arrays ─────────────────────────────────────
    if "laminar burning velocity" in unsrt and "var" in unsrt["laminar burning velocity"]:
        unsrt["laminar burning velocity"]["value"] = [
            float(datagroupDict["dg1"]["DataPoints"][pt][unsrt["laminar burning velocity"]["var"]])
            for pt in datagroupDict["dg1"]["DataPoints"]
        ]
    if "ignition delay" in unsrt and "var" in unsrt["ignition delay"]:
        unsrt["ignition delay"]["value"] = [
            float(datagroupDict["dg1"]["DataPoints"][pt][unsrt["ignition delay"]["var"]])
            for pt in datagroupDict["dg1"]["DataPoints"]
        ]

    # ── Volume / residence time ──────────────────────────────────────────────
    if "volume" in properties:
        volume = float(properties["volume"]["value"])
        volume_unit = properties["volume"]["unit"]
    else:
        volume = ""
        volume_unit = ""

    if "residence time" in properties:
        res_unit = properties["residence time"]["unit"]
        res_val = float(properties["residence time"]["value"])
        if res_unit == "ms":
            res_time = 0.001 * res_val
        elif res_unit == "us":
            res_time = 1e-6 * res_val
        else:
            res_time = res_val
        res_unit = "s"
    else:
        res_time = ""
        res_unit = ""

    add += f" residenceTime: {res_time}\n maxSimulationTime: {res_time * 5 if res_time != '' else ''}\n volume: {volume}\n"

    # ── Pressure ─────────────────────────────────────────────────────────────
    pressure = []
    p_unit = "Pa"
    p_sigma = 0

    if "pressure" in properties:
        p_unit = properties["pressure"]["unit"]
        fact, p_unit = _pressure_factor(p_unit, file_)
        pressure = [fact * float(properties["pressure"]["value"])] * ndpt
        if "pressure" in unsrt:
            p_sigma = unsrt["pressure"]["value"]
    else:
        for var in datagroupDict["dg1"]["Variables"]:
            if datagroupDict["dg1"]["Variables"][var].get("name") == "pressure":
                p_unit_raw = datagroupDict["dg1"]["Variables"][var].get("units", "Pa")
                fact, p_unit = _pressure_factor(p_unit_raw, file_)
                for pt in datagroupDict["dg1"]["DataPoints"]:
                    pressure.append(fact * float(datagroupDict["dg1"]["DataPoints"][pt][var]))
        if "pressure" in unsrt:
            p_sigma = unsrt["pressure"]["value"]

    # ── Flow rate ─────────────────────────────────────────────────────────────
    flow_unit = ""
    flowRate = [""] * ndpt

    if "flow rate" in properties:
        flow_unit = properties["flow rate"]["unit"]
        flowRate = [float(properties["flow rate"]["value"])] * ndpt
    elif "flow rate" in datagroupDict:
        fl = []
        for var in datagroupDict["dg1"]["Variables"]:
            if datagroupDict["dg1"]["Variables"][var].get("name") == "flow rate":
                flow_unit = datagroupDict["dg1"]["Variables"][var].get("units", "")
                for pt in datagroupDict["dg1"]["DataPoints"]:
                    fl.append(datagroupDict["dg1"]["DataPoints"][pt][var])
        flowRate = fl if fl else [""] * ndpt

    # ── Composition (common properties) ──────────────────────────────────────
    List_fuel = []
    List_fuel_x = []
    bathgas = []
    bathgas_conc = []
    ox = []
    ox_x = []
    phi = None

    a_ = "initial composition" if "initial composition" in properties else (
        "concentration" if "concentration" in properties else None
    )

    if a_ is not None:
        # Common-properties composition
        actual_fuel = []
        input_fuel_x = {}
        input_bath_gas = {}
        input_oxidizer_x = 0.0

        for sp in properties[a_]:
            if sp in fuel_list:
                actual_fuel.append(sp)
                for fuel_key, fuel_sp in input_fuel.items():
                    if fuel_sp == sp:
                        input_fuel_x[fuel_key] = float(properties[a_][sp]["value"])
            elif sp == "O2":
                input_oxidizer_x = float(properties[a_][sp]["value"])
            else:
                input_bath_gas[sp] = float(properties[a_][sp]["value"])

        # Stoichiometric F/A ratio
        st_fuel_x = float(len(actual_fuel))
        st_ox_x = sum(_nu_o2(f) for f in actual_fuel)
        if st_ox_x <= 0:
            log.warning("Stoichiometric O2 is zero for fuels %s in %s — phi=0", actual_fuel, file_)
            return None, None, None, None
        F_A_st = st_fuel_x / st_ox_x

        actual_fuel_x = sum(input_fuel_x.values())
        if input_oxidizer_x <= 0:
            log.warning("Oxidizer x=0 in common props of %s — phi=0", file_)
            return None, None, None, None
        F_A_ct = actual_fuel_x / input_oxidizer_x
        phi_val = round(F_A_ct / F_A_st, 2)

        bath_gas = {}
        bath_gas_x = {}
        list_a = [chr(97 + j) for j in range(len(input_bath_gas))]
        for ind, sp in enumerate(input_bath_gas):
            bath_gas[list_a[ind]] = sp
            bath_gas_x[list_a[ind]] = input_bath_gas[sp]

        # Use plain Python lists (not np.repeat) so dict elements index correctly
        List_fuel = [dict(input_fuel)] * ndpt
        List_fuel_x = [dict(input_fuel_x)] * ndpt
        bathgas = [dict(bath_gas)] * ndpt
        bathgas_conc = [dict(bath_gas_x)] * ndpt
        ox = ["O2"] * ndpt
        ox_x = [input_oxidizer_x] * ndpt
        phi = [phi_val] * ndpt

    else:
        # Varying composition per data point
        actual_fuel = []
        input_fuel_x = {}
        bathgasDict = {}
        ox_x = []

        for var in datagroupDict["dg1"]["Variables"]:
            var_name = datagroupDict["dg1"]["Variables"][var].get("name", "")
            if var_name in ("composition", "concentration", "initial composition", "final composition"):
                pref_key = datagroupDict["dg1"]["Variables"][var].get(
                    "specification", {}).get("preferredKey", "")
                if pref_key in fuel_list:
                    fuel_conc = [
                        float(datagroupDict["dg1"]["DataPoints"][pt][var])
                        for pt in datagroupDict["dg1"]["DataPoints"]
                    ]
                    actual_fuel.append(pref_key)
                    input_fuel_x[pref_key] = fuel_conc
                elif pref_key == "O2":
                    ox = np.repeat("O2", ndpt)
                    ox_x = [
                        float(datagroupDict["dg1"]["DataPoints"][pt][var])
                        for pt in datagroupDict["dg1"]["DataPoints"]
                    ]
                else:
                    temp_list = [
                        float(datagroupDict["dg1"]["DataPoints"][pt][var])
                        for pt in datagroupDict["dg1"]["DataPoints"]
                    ]
                    bathgasDict[pref_key] = temp_list

        st_fuel_x = float(len(actual_fuel))
        st_ox_x = sum(_nu_o2(f) for f in actual_fuel)
        if st_ox_x <= 0:
            log.warning("Stoichiometric O2 is zero for fuels %s in %s", actual_fuel, file_)
            return None, None, None, None
        F_A_st = st_fuel_x / st_ox_x

        phi = []
        for i in range(ndpt):
            actual_fuel_x = sum(input_fuel_x[f][i] for f in actual_fuel if f in input_fuel_x)
            actual_ox_x = ox_x[i] if i < len(ox_x) else 0.0
            if actual_ox_x <= 0:
                phi.append(0.0)
            else:
                phi.append(round((actual_fuel_x / actual_ox_x) / F_A_st, 2))
        phi = np.asarray(phi)

        bath_gas = {}
        list_a = [chr(97 + j) for j in range(len(bathgasDict))]
        list_b = [chr(97 + j) for j in range(len(input_fuel_x))]
        for ind, sp in enumerate(bathgasDict):
            bath_gas[list_a[ind]] = sp
        bathgas = [dict(bath_gas)] * ndpt
        bathgas_conc = []
        for i in range(ndpt):
            row = {list_a[ind]: bathgasDict[sp][i] for ind, sp in enumerate(bathgasDict)}
            bathgas_conc.append(row)

        temp_fuel = {list_b[ind]: sp for ind, sp in enumerate(input_fuel_x)}
        List_fuel = [dict(temp_fuel)] * ndpt
        List_fuel_x = []
        for i in range(ndpt):
            row = {list_b[ind]: input_fuel_x[sp][i] for ind, sp in enumerate(input_fuel_x)}
            List_fuel_x.append(row)

    # Fill any missing fuel keys per-row
    for ind, row in enumerate(List_fuel):
        for j in row:
            if j not in List_fuel_x[ind]:
                List_fuel_x[ind][j] = 0.0

    # ── Temperature ──────────────────────────────────────────────────────────
    temperature = []
    t_unit = "K"
    t_sigma = 0

    if "temperature" in properties:
        t_unit = properties["temperature"].get("unit", "K")
        temperature = [float(properties["temperature"]["value"])] * ndpt
        if "temperature" in unsrt:
            t_sigma = unsrt["temperature"]["value"]
    else:
        for var in datagroupDict["dg1"]["Variables"]:
            if datagroupDict["dg1"]["Variables"][var].get("name") == "temperature":
                t_unit = datagroupDict["dg1"]["Variables"][var].get("units", "K")
                temperature = [
                    float(datagroupDict["dg1"]["DataPoints"][pt][var])
                    for pt in datagroupDict["dg1"]["DataPoints"]
                ]
        if "temperature" in unsrt:
            t_sigma = unsrt["temperature"]["value"]

    # ── Pressure rise (dpdt) ─────────────────────────────────────────────────
    dpdt = []
    if "pressure rise" in properties:
        dpdt_unit = properties["pressure rise"]["unit"]
        dpdt = [float(properties["pressure rise"]["value"])] * ndpt
        add += f" BoundaryLayer: True\n dpdt:\n"
        for i, T in enumerate(temperature):
            add += f"  {float(T)} : {dpdt[i]}\n"
    else:
        for var in datagroupDict["dg1"]["Variables"]:
            if datagroupDict["dg1"]["Variables"][var].get("name") == "pressure rise":
                for pt in datagroupDict["dg1"]["DataPoints"]:
                    dpdt.append(float(datagroupDict["dg1"]["DataPoints"][pt][var]))
        if dpdt:
            add += f" BoundaryLayer: True\n dpdt:\n"
            for i, T in enumerate(temperature):
                add += f"  {float(T)} : {dpdt[i]}\n"

    add += "\n"

    # ── Classify target type ─────────────────────────────────────────────────
    target_cls = _classify_target(Target_kind, Target_mode, add_mod, file_)
    if target_cls is None:
        return None, None, None, None
    exp, exp_tag, Simulation_type, MeasurnmentType_cls, reactorType, ignitionMode, flameType = target_cls
    if MeasurnmentType_cls:
        MeasurnmentType = MeasurnmentType_cls

    # ── Heat-flux-burner temperature profile (Flf_a only) ────────────────────
    # combustion_target_class.py reads an experimental T(x) burner profile
    # from target.add["ExpTempFile"] (+ a matching "file_header" describing
    # its columns) whenever the target type contains "Flf" — this data isn't
    # part of the standard ReSpecTh XML for a burning-velocity measurement, so
    # look for a companion file named after this XML's own filename, and only
    # wire it in if KP has actually supplied one. Convention:
    # <same dir as the xml>/<dataset>_Texp.csv, two columns (distance, T).
    if exp_tag == "Flf_a":
        temp_profile_path = os.path.join(os.path.dirname(os.path.abspath(xml_path)),
                                          f"{dataset}_Texp.csv")
        if os.path.isfile(temp_profile_path):
            add += f" ExpTempFile: {temp_profile_path}\n file_header: [distance, T]\n"
            log.info("Found companion temperature profile for %s -> %s", file_, temp_profile_path)
        else:
            log.info("No companion temperature profile for %s (expected %s) — "
                      "ExpTempFile left unset.", file_, os.path.basename(temp_profile_path))

    # ── Experimental target values ────────────────────────────────────────────
    exp_target = []
    exp_unit = ""
    exp_std_dnvt = []
    exp_std_dvnt_unit = ""
    exp_sigma_type = "absolute"
    exp_composition = {}
    specific_cond_jsr = {}

    if exp_tag == "JSR":
        for var in datagroupDict["dg1"]["Variables"]:
            var_info = datagroupDict["dg1"]["Variables"][var]
            var_name = var_info.get("name", "")

            if "residence time" in var_name:
                specific_cond_jsr["residence time"] = []
                x_unit = var_info.get("units", "s")
                fact = {"s": 1.0, "ms": 0.001, "us": 1e-6}.get(x_unit, 1.0)
                for pt in datagroupDict["dg1"]["DataPoints"]:
                    specific_cond_jsr["residence time"].append(
                        fact * float(datagroupDict["dg1"]["DataPoints"][pt][var]))

            elif "composition" in var_name:
                x_id = var_info.get("id", "")
                exp_unit = var_info.get("units", "")
                species = var_info.get("specification", {}).get("preferredKey", "")
                if not species:
                    continue
                exp_composition[species] = {"observation": []}
                for pt in datagroupDict["dg1"]["DataPoints"]:
                    exp_composition[species]["observation"].append(
                        float(datagroupDict["dg1"]["DataPoints"][pt][var]))

                exp_ = exp + "_" + species
                if exp_ in unsrt:
                    exp_sigma_val = float(unsrt[exp_].get("value", 0))
                    exp_sigma_type_ = unsrt[exp_].get("type", "absolute")
                    std_unit = unsrt[exp_].get("units", "")
                    if std_unit == "ppm":
                        exp_sigma_val /= 1e6
                    if exp_sigma_type_ == "relative":
                        std_arr = exp_sigma_val * np.asarray(exp_composition[species]["observation"])
                    else:
                        std_arr = np.repeat(exp_sigma_val, ndpt)
                    exp_composition[species]["std_unit"] = std_unit
                    exp_composition[species]["std"] = std_arr

            elif "time" in var_name:
                x_unit = var_info.get("units", "s")
                fact = {"s": 1.0, "ms": 0.001, "us": 1e-6}.get(x_unit, 1.0)
                specific_cond_jsr["time"] = [
                    fact * float(datagroupDict["dg1"]["DataPoints"][pt][var])
                    for pt in datagroupDict["dg1"]["DataPoints"]
                ]

            elif "temperature" in var_name:
                specific_cond_jsr["temperature"] = [
                    float(datagroupDict["dg1"]["DataPoints"][pt][var])
                    for pt in datagroupDict["dg1"]["DataPoints"]
                ]

        for key in ("time", "temperature", "residence time"):
            if key not in specific_cond_jsr:
                specific_cond_jsr[key] = [""] * ndpt

    else:
        for var in datagroupDict["dg1"]["Variables"]:
            var_info = datagroupDict["dg1"]["Variables"][var]
            if exp in var_info.get("name", ""):
                exp_unit = var_info.get("units", "")
                for pt in datagroupDict["dg1"]["DataPoints"]:
                    exp_target.append(float(datagroupDict["dg1"]["DataPoints"][pt][var]))

        if exp in unsrt:
            unsrt_exp = unsrt[exp]
            if "var" in unsrt_exp:
                exp_sigma = np.asarray(unsrt_exp["value"])
            else:
                exp_sigma = unsrt_exp.get("value", 0)
                if unsrt_exp.get("units") == "ppm":
                    exp_sigma = float(exp_sigma) / 1e6
            exp_sigma_type = unsrt_exp.get("type", "absolute")
            exp_std_dvnt_unit = unsrt_exp.get("units", "")
        else:
            log.warning("No uncertainty entry for '%s' in %s — using 0", exp, file_)
            exp_sigma = 0
            exp_sigma_type = "absolute"
            exp_std_dvnt_unit = ""

        if exp_sigma_type == "relative":
            exp_std_dnvt = np.asarray(exp_target) * np.asarray(exp_sigma).astype(float)
        else:
            if isinstance(exp_sigma, (list, tuple, np.ndarray)):
                exp_std_dnvt = np.asarray(exp_sigma)
            else:
                exp_std_dnvt = np.repeat(float(exp_sigma), ndpt)

    Input_units = {
        "conc": "mol",
        "P": p_unit,
        "T": t_unit,
        "observed": exp_unit,
        "flow": flow_unit,
    }

    # ── Addendum for JSR species ─────────────────────────────────────────────
    if exp_tag == "JSR":
        for each in exp_composition:
            mol_wt_val = _mol_wt(each)
            add += (
                f"{dataset}_{each}:\n"
                f" solver: {solver}\n"
                f" species: {each}\n"
                f" mol_wt: {mol_wt_val}\n"
                f" residenceTime: {res_time}# in sec\n"
                f" maxSimulationTime: {res_time * 5 if res_time != '' else ''}# in sec\n"
                f" volume: {volume}#in cm3\n\n"
            )

    # ── Build target rows ────────────────────────────────────────────────────
    rows = ""
    csv_rows = []
    if exp_tag == "JSR":
        for each in exp_composition:
            for i in range(ndpt):
                fuel_species, fuel_xf = _first_species_xf(List_fuel[i], List_fuel_x[i])
                bath_species, bath_xf = _first_species_xf(
                    bathgas[i] if bathgas else {}, bathgas_conc[i] if bathgas_conc else {})
                observed_val = exp_composition[each]["observation"][i]
                std_val = exp_composition[each]["std"][i] if "std" in exp_composition[each] else 0
                deviation_pct = (100.0 * std_val / observed_val) if observed_val else ""
                csv_rows.append({
                    "dataset_id": f"{dataset}_{each}", "target_type": exp_tag,
                    "fuel_species": fuel_species, "fuel_xf": fuel_xf,
                    "oxidizer_species": str(ox[i]), "ox_xf": str(ox_x[i]),
                    "bath_species": bath_species, "bath_xf": bath_xf,
                    "T": temperature[i], "P": pressure[i], "P_unit": p_unit, "phi": phi[i],
                    "observed": observed_val, "deviation_pct": deviation_pct, "data_weight": ndpt,
                })
                rows += (
                    "{}\t|{}_{}\t| target -- {}\t| simulation -- {}\t|"
                    " measurnment_type -- {}\t|Ignition_mode -- {}\t| Flame_type -- {}\t|"
                    " Reactor_type -- {}\t| Fuel_type -- {}\t| Fuel -- x->{} = {}\t|"
                    " Oxidizer -- x->{} = {}\t| Bath_gas -- x->{}={}\t|T -- {}\t| P -- {}\t|"
                    " flow_rate -- {}\t|Phi -- {}\t| volume -- {}\t|volume_unit -- {}\t|"
                    " residence_time -- {}\t|observed_quantity -- {}\t| specific_details -- {}\t|"
                    " observation_type -- {}\t|observed -- {}\t| obs_unit --{} \t|"
                    " deviation -- {}\t|data_weight -- {}\t|units -- {}\n"
                ).format(
                    i + 1, dataset, each,
                    exp_tag, Simulation_type, MeasurnmentType, ignitionMode, flameType, reactorType,
                    FUEL_TYPE, List_fuel[i], List_fuel_x[i],
                    ox[i], ox_x[i],
                    bathgas[i] if bathgas else {},
                    bathgas_conc[i] if bathgas_conc else {},
                    temperature[i], pressure[i], flowRate[i],
                    phi[i],
                    volume, volume_unit, res_time, each,
                    {
                        "time": specific_cond_jsr["time"][i],
                        "residence time": specific_cond_jsr["residence time"][i],
                        "temperature": specific_cond_jsr["temperature"][i],
                    },
                    "profile",
                    exp_composition[each]["observation"][i],
                    exp_composition[each].get("std_unit", ""),
                    exp_composition[each]["std"][i] if "std" in exp_composition[each] else 0,
                    ndpt, Input_units,
                )
    else:
        for i in range(ndpt):
            fuel_species, fuel_xf = _first_species_xf(List_fuel[i], List_fuel_x[i])
            bath_species, bath_xf = _first_species_xf(
                bathgas[i] if bathgas else {}, bathgas_conc[i] if bathgas_conc else {})
            observed_val = exp_target[i] if i < len(exp_target) else ""
            std_val = exp_std_dnvt[i] if i < len(exp_std_dnvt) else 0
            deviation_pct = (100.0 * std_val / observed_val) if observed_val else ""
            csv_rows.append({
                "dataset_id": dataset, "target_type": exp_tag,
                "fuel_species": fuel_species, "fuel_xf": fuel_xf,
                "oxidizer_species": str(ox[i]), "ox_xf": str(ox_x[i]),
                "bath_species": bath_species, "bath_xf": bath_xf,
                "T": temperature[i], "P": pressure[i], "P_unit": p_unit, "phi": phi[i],
                "observed": observed_val, "deviation_pct": deviation_pct, "data_weight": ndpt,
            })
            rows += (
                "{}\t|{}\t| target -- {}\t| simulation -- {}\t|"
                " measurnment_type -- {}\t|Ignition_mode -- {}\t| Flame_type -- {}\t|"
                " Reactor_type -- {}\t| Fuel_type -- {}\t| Fuel -- x->{} = {}\t|"
                " Oxidizer -- x->{} = {}\t| Bath_gas -- x->{}={}\t|T -- {}\t| P -- {}\t|"
                " flow_rate -- {}\t|Phi -- {}\t| observed -- {}\t| obs_unit --{} \t|"
                " deviation -- {}\t|data_weight -- {}\t|units -- {}\n"
            ).format(
                i + 1, dataset,
                exp_tag, Simulation_type, MeasurnmentType, ignitionMode, flameType, reactorType,
                FUEL_TYPE,
                List_fuel[i], List_fuel_x[i],
                ox[i], ox_x[i],
                bathgas[i] if bathgas else {},
                bathgas_conc[i] if bathgas_conc else {},
                temperature[i], pressure[i], flowRate[i],
                phi[i],
                exp_target[i] if i < len(exp_target) else "",
                exp_std_dvnt_unit,
                exp_std_dnvt[i] if i < len(exp_std_dnvt) else 0,
                ndpt, Input_units,
            )

    return add, rows, bib_entry, csv_rows


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def main(
    xml_dir=".",
    out_dir=None,
    fuel_list=None,
    input_fuel=None,
    stoichiometry=None,
    solver="cantera",
):
    """
    Convert all *.xml files in xml_dir to target.opt / addendum.add / references.bib.

    Args:
        xml_dir:      Directory containing *.xml files (default: cwd)
        out_dir:      Output directory (default: xml_dir)
        fuel_list:    List of fuel species names, e.g. ["NH3", "H2"]
        input_fuel:   Dict mapping letter keys to species, e.g. {"a": "NH3", "b": "H2"}
        stoichiometry: Optional override dict {species: nu_O2}; merged with chem_data defaults
        solver:       Solver tag written into every .add block: "cantera",
                      "CHEMKIN_PRO", or "FlameMaster" (see make_input_file.py)
    """
    xml_dir = os.path.abspath(xml_dir)
    out_dir = os.path.abspath(out_dir) if out_dir else xml_dir
    os.makedirs(out_dir, exist_ok=True)

    # Defaults
    if fuel_list is None:
        fuel_list = ["NH3"]
    if input_fuel is None:
        input_fuel = {"a": "NH3"}

    # Merge stoichiometry overrides
    merged_stoich = dict(_BASE_STOICH)
    if stoichiometry:
        merged_stoich.update(stoichiometry)

    xml_files = sorted(f for f in os.listdir(xml_dir) if f.lower().endswith(".xml"))
    if not xml_files:
        log.warning("No XML files found in %s", xml_dir)
        return {
            "n_files_ok": 0, "n_files_skipped": 0, "n_rows": 0,
            "target_path": None, "add_path": None, "bib_path": None, "csv_path": None,
            "warnings": [f"No .xml files found in {xml_dir}"],
        }

    # Capture per-file WARNING+ log records (e.g. "Missing commonProperties or
    # dataGroup in X.xml — skipping") so callers that have no console access
    # (a GUI thread) can show the real reason instead of a bare "0 files
    # converted" — previously these warnings were logged but never surfaced
    # anywhere else, which made a directory of not-quite-ReSpecTh-format XML
    # files (or any other per-file skip) indistinguishable from a real bug.
    _captured_warnings = []

    class _CaptureHandler(logging.Handler):
        def emit(self, record):
            _captured_warnings.append(self.format(record))

    _capture_handler = _CaptureHandler(level=logging.WARNING)
    _capture_handler.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_capture_handler)

    # NOTE: "target.opt" is reserved elsewhere in this toolchain for the
    # master YAML config (generate_target_opt.py's own output) — naming this
    # file "target.opt" collided with that and broke the GUI's "*.target"
    # row-count glob after import (always reported 0 rows). This file is the
    # pipe-delimited .target experimental-data format, so it gets a .target
    # extension like the manually-built one does.
    target_path = os.path.join(out_dir, "converted.target")
    add_path = os.path.join(out_dir, "addundem.add")
    bib_path = os.path.join(out_dir, "references.bib")
    csv_path = os.path.join(out_dir, "converted.csv")

    # Open with "w" to overwrite (not "a+")
    target_fh = open(target_path, "w", encoding="utf-8")
    bib_fh = open(bib_path, "w", encoding="utf-8")
    bib_fh.write("% references.bib — auto-generated by xml2csv.py\n\n")
    bib_seen = set()

    all_add = ""
    all_csv_rows = []
    global_count = 0
    n_ok = n_skip = 0

    try:
        for file_ in xml_files:
            xml_path = os.path.join(xml_dir, file_)
            try:
                add_block, rows, bib_entry, csv_rows = _parse_xml_file(
                    xml_path, fuel_list, input_fuel, merged_stoich, solver=solver
                )
            except Exception as exc:
                # A single malformed/unexpected-structure XML must not abort
                # the whole batch — log it as a skip (with the real reason)
                # and keep going, matching this module's own stated design
                # ("AssertionError hard stops -> logged warnings + continue").
                # Previously only _parse_xml_file's own internal early-returns
                # were "safe" this way; any other exception type propagated
                # and killed the entire conversion.
                log.warning("Unexpected error parsing %s: %s — skipping", file_, exc)
                n_skip += 1
                continue

            if add_block is None:
                n_skip += 1
                continue

            all_add += add_block
            target_fh.write(rows)
            global_count += rows.count("\n")
            if csv_rows:
                all_csv_rows.extend(csv_rows)

            if bib_entry and bib_entry not in bib_seen:
                bib_fh.write(bib_entry + "\n")
                bib_seen.add(bib_entry)

            n_ok += 1
    finally:
        target_fh.close()
        bib_fh.close()
        log.removeHandler(_capture_handler)

    with open(add_path, "w", encoding="utf-8") as fh:
        fh.write(all_add)

    if all_csv_rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDNAMES)
            writer.writeheader()
            writer.writerows(all_csv_rows)
    else:
        csv_path = None

    log.info("Done: %d files parsed, %d skipped, %d target rows.", n_ok, n_skip, global_count)
    log.info("Outputs: %s, %s, %s, %s", target_path, add_path, bib_path, csv_path)

    return {
        "n_files_ok": n_ok, "n_files_skipped": n_skip, "n_rows": global_count,
        "target_path": target_path, "add_path": add_path,
        "bib_path": bib_path, "csv_path": csv_path,
        # Capped so a huge batch of skips doesn't produce an unwieldy payload
        # for GUI display — still enough to show the real, actionable reason.
        "warnings": _captured_warnings[:30],
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    xml_dir_ = args[0] if len(args) > 0 else "."
    out_dir_ = args[1] if len(args) > 1 else None
    main(xml_dir_, out_dir_)
