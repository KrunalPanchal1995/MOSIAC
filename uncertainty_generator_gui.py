#!/usr/bin/env python3
"""
uncertainty_generator_gui.py — Standalone GUI for Uncertainty Quantification
and File Generation.

KRUNAL_JULY_23.md point 5: renamed from "Uncertainty Generator" (the app's
class/window title said as much, and it only ever supported hand-typed
reaction rows) to match what this tool actually does end-to-end -- the
primary workflow is now driven by SA-data + a mechanism + a classification
CSV (src/ActiveParameterScreen.py's own pipeline: screening -> XML/plots/
LaTeX/filtered-mechanism generation), not manual per-reaction entry. Manual
XML entry and the standalone bounds-collapse tool are kept as secondary
tabs -- both still real, tested capabilities, just no longer the front door.

Phase 5 of the GUI-separation plan (see
MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md §1.7,
§2 item 8): wraps src/MUQ-SAC/Uncertainty.py's existing per-anchor-
temperature Class B/C bound machinery, collapsed to ONE global symmetric
A-factor bound per reaction -- the exact formula confirmed with KP before
writing this: for each reaction, take
    max(|kappa_max(T) - kappa_nom(T)|, |kappa_nom(T) - kappa_min(T)|)
across all 3 anchor temperatures (kappa = ln(k), so this delta is already
directly ln(uncertainty factor) -- no separate division needed, unlike a
literal linear-space relative deviation), then apply that one bound
symmetrically to ln(A) at the nominal (T-independent) A-factor:
    A_lb = A_nominal / exp(max_delta),  A_ub = A_nominal * exp(max_delta)

Found and fixed two real, previously-undiscovered bugs in
generate_target_opt.py's generate_uncertainty_xml() while building this --
every uncertainty XML that function ever wrote was missing the `no` and
`perturbation_type` attributes Uncertainty.py's own `reaction.__init__`
requires, so re-loading any of them into Uncertainty.py crashed immediately
(KeyError, then AttributeError). Fixed in generate_target_opt.py directly,
not routed around here.

Usage:
    python uncertainty_generator_gui.py
    python uncertainty_generator_gui.py --xml unsrt.xml --mechanism mech.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC = str(_ROOT / "src")
_MUQSAC_SRC = str(_ROOT / "src" / "MUQ-SAC")
for p in (_SRC, _MUQSAC_SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    _HAS_TK = True
except ImportError:
    _HAS_TK = False

from gui_common.theme import PALETTE, FONTS, apply_theme
from gui_common.pty_terminal import PtyTerminal, _HAS_PTY_TERMINAL
from gui_common.settings import load_settings, save_settings
from gui_common.autosave import AutoSaveManager
from gui_common.run_status_export import add_export_button
from mso_io.run_status import RunStatusReport

_APP_NAME = "uncertainty_generator"
_ACTIVE_PARAM_SCRIPT = str(_ROOT / "src" / "ActiveParameterScreen.py")
# Built-in demo (KRUNAL_JULY_23.md point 5's "clt" example), paths resolved
# relative to THIS checkout -- the shipped `clt` file itself hardcodes a
# different clone's absolute paths (/home/krithika/mechanism-optimization-
# suite/...), not usable verbatim.
_DEMO_DIR = _ROOT / "DATASET" / "METHYL_BUTANOATE_2026" / "ACTIVE_PARAMETER_SELECTION"
_DEMO = {
    "sens_dir": str(_DEMO_DIR / "METHYLBUTANOATE"),
    "mechanism": str(_DEMO_DIR / "MB_MB2D_LALIT_2024.yaml"),
    "classification_file": str(_DEMO_DIR / "results" / "master_active_reactions_CLASSIFIED.csv"),
    "fuel": "MB_MB2D_LALIT_2024",
    "threshold": "0.05",
    "carbon": "5",
    "compare_temperatures": "698 908 1287",
}
# Own checkpoint file (gui_common/autosave.py's docstring: each split-out app
# gets its own path, never a shared one). Module-level so tests can
# monkeypatch it the same way tests/test_gui_common.py already does for
# gui_common.settings._SETTINGS_DIR.
_CHECKPOINT_PATH = _ROOT / ".gui_settings" / "uncertainty_generator_checkpoint.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Standalone GUI for the Uncertainty Generator "
                    "(collapses temperature-dependent uncertainty bands to "
                    "one symmetric A-factor bound per reaction)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--xml", default=None, help="Uncertainty XML path to pre-fill")
    p.add_argument("--mechanism", default=None, help="Mechanism file path to pre-fill")
    p.add_argument("--no-gui", action="store_true",
                   help="Headless smoke check: verify paths exist and exit")
    # Headless modes (KRUNAL_JULY_23.md PySide6 conversion): let
    # mso_studio.core.uncertainty shell out to this script in the anaconda
    # interpreter, since compute_symmetric_bounds needs src/MUQ-SAC's
    # scipy/numpy stack (generate_uncertainty_xml itself needs only stdlib,
    # but both go through the same bridge for one consistent recipe).
    p.add_argument("--generate-xml", action="store_true",
                   help="Headless: build an uncertainty XML from --reactions-json")
    p.add_argument("--reactions-json",
                   help="JSON file: list of {name,type,temperatures,uncertainties} dicts")
    p.add_argument("--output", help="Output XML path for --generate-xml")
    p.add_argument("--compute-bounds", action="store_true",
                   help="Headless: collapse --xml's bands to symmetric A-factor bounds")
    p.add_argument("--output-csv", help="Output CSV path for --compute-bounds")
    return p.parse_args()


def compute_symmetric_bounds(xml_path: str, mech_path: str) -> list:
    """
    For every <reaction> in the uncertainty XML, compute one global
    symmetric A-factor bound (see this module's own docstring for the
    exact formula, confirmed with KP).

    Returns a list of dicts: {rxn, A_nominal, factor, A_lb, A_ub} on
    success, or {rxn, error} for any reaction that couldn't be resolved
    (e.g. not present in the given mechanism) -- one bad reaction must not
    abort the whole batch.
    """
    import numpy as np
    import Uncertainty

    tree = ET.parse(xml_path)
    results = []
    for elem in tree.getroot().findall("reaction"):
        rxn_name = elem.attrib.get("rxn", "(unknown)")
        try:
            r = Uncertainty.reaction(elem, mech_path, {})
            T_anchors = np.array([
                r.temperatures[0],
                (r.temperatures[0] + r.temperatures[-1]) / 2,
                r.temperatures[-1],
            ])
            kappa_max = r.getKappaMax(None)
            kappa_min = r.getKappaMin(T_anchors)
            kappa_nom = r.getNominal(None)

            deltas = np.concatenate([
                np.abs(kappa_max - kappa_nom),
                np.abs(kappa_nom - kappa_min),
            ])
            max_delta_ln_k = float(deltas.max())
            factor = float(np.exp(max_delta_ln_k))

            A_nominal = float(np.exp(r.P[0]))
            results.append({
                "rxn": rxn_name,
                "A_nominal": A_nominal,
                "factor": factor,
                "A_lb": A_nominal / factor,
                "A_ub": A_nominal * factor,
            })
        except Exception as e:
            results.append({"rxn": rxn_name, "error": str(e)})
    return results


def generate_uncertainty_xml(reactions: list, output_path: str) -> str:
    """Build a MUQ-SAC uncertainty XML file and return the string.

    Ported from generate_target_opt.py (the pre-split monolith) verbatim --
    this exact function, and its two 'no'/'perturbation_type' attribute
    fixes (see comments below), already existed and worked there. It was
    simply never carried into any of the 8 GUI-separation-project standalone
    apps (launcher_gui.py's registry), so nothing in the new split GUI set
    could generate an uncertainty XML at all -- only *collapse* an existing
    one (compute_symmetric_bounds, above). Found while stress-testing mean-
    value-fusion + uncertainty generation end-to-end on a fused mechanism
    (2026-07-17): the user's GUI-fusion complaint explicitly named "the GUI
    must be capable of generating xml files" as a requirement, and no app in
    the launcher could do it -- this was the root cause.
    """
    import xml.etree.ElementTree as ET
    from xml.dom.minidom import parseString

    root = ET.Element("uncertainty")
    for i, rxn in enumerate(reactions):
        name = rxn.get("name", "H+O2<=>O+OH")
        # "no" is a required attribute of src/MUQ-SAC/Uncertainty.py's
        # `reaction.__init__` (`self.rIndex = str(Element.attrib["no"])`) --
        # only ever used downstream as a display/tag label, not a mechanism
        # lookup key, so a stable 1-based sequence number is a correct fix.
        rxn_el = ET.SubElement(root, "reaction", rxn=name, no=str(i + 1))
        # <class> (reaction classification: Elementary/PLOG/Falloff/ThirdBody/
        # Duplicate) is read by MechManipulator2_0.py's doPerturbation() to
        # dispatch to the right perturbation method -- a blank value matches
        # none of its if/elif branches, so perturbation SILENTLY no-ops for
        # that reaction (same defect already documented for the shipped
        # DATASET/H2_O2_TEST/uncertainty/H2_uncertainty.xml, see
        # h2_o2_crosscheck_unsrt.xml's docstring). This generator produced
        # exactly that same silently-broken shape until now. "Elementary" is
        # the correct default for a plain A/n/Ea reaction (matches how
        # `type`/`perturbation_type` already default below); callers with a
        # PLOG/Falloff/ThirdBody/Duplicate reaction can override via
        # rxn["classification"].
        ET.SubElement(rxn_el, "class").text = rxn.get("classification", "Elementary")
        rxn_type = rxn.get("type", "pressure_independent")
        ET.SubElement(rxn_el, "type").text = rxn_type
        # <perturbation_type> is read unconditionally at Uncertainty.py's
        # `reaction.__init__` (`if "factor" in self.perturbation_type:`) --
        # "arrhenius" (full 3-parameter A/n/Ea) is the correct default,
        # matching sens_3_params.py's standard 3-parameter scope.
        ET.SubElement(rxn_el, "perturbation_type").text = rxn.get("perturbation_type", "arrhenius")
        sub = ET.SubElement(rxn_el, "sub_type", name="forward")
        ET.SubElement(sub, "multiple").text = "False"
        ET.SubElement(sub, "branches").text = "N/A"
        ET.SubElement(sub, "pressure_limit").text = "low" if rxn_type == "pressure_dependent" else "N/A"
        ET.SubElement(sub, "common_temp").text = "N/A"
        ET.SubElement(sub, "temp_limit").text = "N/A"
        data_mode = rxn.get("data_mode", "constant;array")
        ET.SubElement(rxn_el, "data_type").text = data_mode
        temps = rxn.get("temperatures", "")
        if isinstance(temps, list):
            temps = ",".join(str(t) for t in temps)
        ET.SubElement(rxn_el, "temp").text = temps
        unsrt = rxn.get("uncertainties", "")
        if isinstance(unsrt, list):
            unsrt = ",".join(str(u) for u in unsrt)
        ET.SubElement(rxn_el, "unsrt").text = unsrt

    raw = ET.tostring(root, encoding="unicode")
    pretty = parseString(raw).toprettyxml(indent="\t")
    lines = pretty.split("\n")
    out = '<?xml version="1.0" encoding="UTF-8"?>\n' + "\n".join(lines[1:])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(out)
    return out


def write_results_csv(results: list, out_path: str) -> None:
    import csv
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["reaction", "A_nominal", "factor", "A_lb", "A_ub", "error"])
        for r in results:
            writer.writerow([
                r["rxn"], r.get("A_nominal", ""), r.get("factor", ""),
                r.get("A_lb", ""), r.get("A_ub", ""), r.get("error", ""),
            ])


class UncertaintyGeneratorApp:
    """Standalone Uncertainty Generator GUI. Calls Uncertainty.reaction
    in-process via a background thread (heavyweight MUQ-SAC import, no
    subprocess needed) -- same pattern as mean_value_fusion_gui.py."""

    def __init__(self, root: "tk.Tk", initial_xml: str | None = None,
                 initial_mechanism: str | None = None):
        self.root = root
        self.root.title("Uncertainty Quantification and File Generator")
        self.root.geometry("980x720")
        self._sa_vars: dict = {}
        self._sa_check_vars: dict = {}
        self._sa_last_command: list | None = None

        self._xml_var = tk.StringVar(value=initial_xml or "")
        self._mech_var = tk.StringVar(value=initial_mechanism or "")
        self._out_csv_var = tk.StringVar(value="outputs/uncertainty_bounds.csv")
        self._status_var = tk.StringVar(value="Load an uncertainty XML and mechanism to begin.")
        self._results = []

        self._gen_out_var = tk.StringVar(value="outputs/uncertainty.xml")
        self._gen_status_var = tk.StringVar(value="")
        self._gen_rows: list = []  # [(rxn_var, type_var, temp_var, unsrt_var), ...]
        # last-run state, for "Export run status…" (KRUNAL_JULY_23.md pt. 1)
        self._last_status = "unknown"
        self._last_error: str | None = None

        settings = load_settings(_APP_NAME)
        if not initial_xml and settings.get("last_xml"):
            self._xml_var.set(settings["last_xml"])
        if not initial_mechanism and settings.get("last_mechanism"):
            self._mech_var.set(settings["last_mechanism"])

        self._build_ui()

        # Autosave/checkpoint safety net (Phase-3 follow-on Part B --
        # FEATURE_GAPS_FROM_MONOLITH.md ranked candidate #3). The
        # reaction-row editor above is the longest-running data entry in
        # this app, so its existing add/remove callbacks mark state dirty.
        self._autosave = AutoSaveManager(self.root, save_callback=self._autosave_save)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _autosave_save(self) -> None:
        """AutoSaveManager's save_callback -- snapshot the in-progress
        generator rows + input paths so a crash/close doesn't lose them."""
        state = {
            "xml": self._xml_var.get(),
            "mechanism": self._mech_var.get(),
            "out_csv": self._out_csv_var.get(),
            "gen_out": self._gen_out_var.get(),
            "gen_rows": self._gen_rows,
        }
        _CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CHECKPOINT_PATH.write_text(json.dumps(state, indent=2))

    def _on_close(self) -> None:
        self._autosave.on_close()
        self.root.destroy()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text="Uncertainty Quantification and File Generator",
                  font=FONTS["header"]).pack(anchor=tk.W)
        ttk.Label(outer,
                  text="Primary workflow: SA data + mechanism + classification CSV → "
                       "screening, uncertainty XML, plots, LaTeX tables, filtered mechanism "
                       "(src/ActiveParameterScreen.py). Manual XML entry and the standalone "
                       "symmetric-bounds collapse tool (src/MUQ-SAC/Uncertainty.py) are kept "
                       "as secondary tabs.",
                  foreground=PALETTE["text_dim"], wraplength=920).pack(anchor=tk.W, pady=(0, 10))

        nb = ttk.Notebook(outer)
        nb.pack(fill=tk.BOTH, expand=True)
        sa_tab = ttk.Frame(nb, padding=8)
        gen_tab = ttk.Frame(nb, padding=8)
        bounds_tab = ttk.Frame(nb, padding=8)
        nb.add(sa_tab, text="From SA data (ActiveParameterScreen)")
        nb.add(gen_tab, text="Manual XML entry")
        nb.add(bounds_tab, text="Compute symmetric bounds")

        self._build_sa_tab(sa_tab)

        # ── Generate ─────────────────────────────────────────────────────
        # (ported from generate_target_opt.py's "Uncertainty XML" tab --
        # this GUI-split app previously only *collapsed* an existing XML,
        # see the "Inputs"/"Results" sections below; nothing in any of the
        # launcher's 8 apps could *generate* one from scratch.)
        gen_frame = ttk.LabelFrame(gen_tab, text="Generate uncertainty XML", padding=8)
        gen_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(gen_frame,
                  text="Add one row per reaction (comma-separated T[K] and matching σ_lnk arrays, "
                       "same length), then Generate. The written path auto-fills "
                       "'Uncertainty XML' below so you can immediately collapse it.",
                  foreground=PALETTE["text_dim"], wraplength=850).pack(anchor=tk.W, pady=(0, 6))

        columns = ("rxn", "type", "temps", "unsrt")
        self._gen_tree = ttk.Treeview(gen_frame, columns=columns, show="headings", height=5)
        for col, label, width in zip(columns,
                                      ("Reaction", "Type", "T [K]", "σ_lnk"),
                                      (260, 130, 220, 220)):
            self._gen_tree.heading(col, text=label)
            self._gen_tree.column(col, width=width, anchor=tk.W)
        self._gen_tree.pack(fill=tk.X, pady=(0, 4))

        add_row = ttk.Frame(gen_frame)
        add_row.pack(fill=tk.X, pady=2)
        self._gen_rxn_var = tk.StringVar()
        self._gen_type_var = tk.StringVar(value="pressure_independent")
        self._gen_temps_var = tk.StringVar(value="500,2500")
        self._gen_unsrt_var = tk.StringVar(value="0.3,0.3")
        ttk.Entry(add_row, textvariable=self._gen_rxn_var, width=28).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Combobox(add_row, textvariable=self._gen_type_var,
                     values=["pressure_independent", "pressure_dependent"],
                     width=18, state="readonly").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(add_row, textvariable=self._gen_temps_var, width=18).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(add_row, textvariable=self._gen_unsrt_var, width=18).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(add_row, text="+ Add row", command=self._add_gen_row).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(add_row, text="− Remove selected", command=self._remove_gen_row).pack(side=tk.LEFT, padx=(4, 0))

        gen_out_row = ttk.Frame(gen_frame)
        gen_out_row.pack(fill=tk.X, pady=(6, 2))
        ttk.Label(gen_out_row, text="Output XML", width=18).pack(side=tk.LEFT)
        ttk.Entry(gen_out_row, textvariable=self._gen_out_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(gen_out_row, text="Browse…", command=self._browse_gen_out).pack(side=tk.LEFT, padx=(6, 0))

        gen_btn_row = ttk.Frame(gen_frame)
        gen_btn_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(gen_btn_row, text="▶  Generate XML", command=self._generate_xml_clicked).pack(side=tk.LEFT)
        ttk.Label(gen_btn_row, textvariable=self._gen_status_var,
                  foreground=PALETTE["text_dim"]).pack(side=tk.LEFT, padx=(10, 0))

        # ── Inputs ───────────────────────────────────────────────────────
        in_frame = ttk.LabelFrame(bounds_tab, text="Inputs", padding=8)
        in_frame.pack(fill=tk.X, pady=(0, 10))

        xml_row = ttk.Frame(in_frame)
        xml_row.pack(fill=tk.X, pady=2)
        ttk.Label(xml_row, text="Uncertainty XML", width=18).pack(side=tk.LEFT)
        ttk.Entry(xml_row, textvariable=self._xml_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(xml_row, text="Browse…", command=self._browse_xml).pack(side=tk.LEFT, padx=(6, 0))

        mech_row = ttk.Frame(in_frame)
        mech_row.pack(fill=tk.X, pady=2)
        ttk.Label(mech_row, text="Mechanism file", width=18).pack(side=tk.LEFT)
        ttk.Entry(mech_row, textvariable=self._mech_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(mech_row, text="Browse…", command=self._browse_mechanism).pack(side=tk.LEFT, padx=(6, 0))

        out_row = ttk.Frame(in_frame)
        out_row.pack(fill=tk.X, pady=2)
        ttk.Label(out_row, text="Output CSV", width=18).pack(side=tk.LEFT)
        ttk.Entry(out_row, textvariable=self._out_csv_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(out_row, text="Browse…", command=self._browse_out_csv).pack(side=tk.LEFT, padx=(6, 0))

        # ── Run ──────────────────────────────────────────────────────────
        btn_row = ttk.Frame(bounds_tab)
        btn_row.pack(fill=tk.X, pady=(0, 10))
        self._run_btn = ttk.Button(btn_row, text="▶  Compute Symmetric Bounds", command=self._run_clicked)
        self._run_btn.pack(side=tk.LEFT)
        add_export_button(btn_row, self._build_run_status).pack(side=tk.LEFT, padx=(6, 0))

        # ── Results ──────────────────────────────────────────────────────
        res_frame = ttk.LabelFrame(bounds_tab, text="Results", padding=4)
        res_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("rxn", "A_nominal", "factor", "A_lb", "A_ub")
        self._tree = ttk.Treeview(res_frame, columns=columns, show="headings", height=14)
        for col, width in zip(columns, (300, 130, 90, 130, 130)):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=width, anchor=tk.W)
        self._tree.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, textvariable=self._status_var, style="Status.TLabel"
                  ).pack(anchor=tk.W, pady=(6, 0))

    # ------------------------------------------------------------------
    # SA-data-driven tab (KRUNAL_JULY_23.md point 5 -- the primary workflow)
    # ------------------------------------------------------------------

    def _build_sa_tab(self, parent) -> None:
        ttk.Label(parent,
                  text="Wraps src/ActiveParameterScreen.py directly -- every option it "
                       "accepts is exposed below. Inputs are an SA-results directory "
                       "(FM_sensitivity_T_*_case_*.txt), a mechanism YAML, and (for XML/"
                       "plots/LaTeX/filtered-mechanism) a classification CSV -- never "
                       "hand-typed reactions.",
                  foreground=PALETTE["text_dim"], wraplength=920, justify=tk.LEFT
                  ).pack(anchor=tk.W, pady=(0, 8))

        form = ttk.Frame(parent)
        form.pack(fill=tk.X)

        def entry(label, key, default="", browse=None):
            row = ttk.Frame(form)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=label, width=22).pack(side=tk.LEFT)
            var = tk.StringVar(value=default)
            self._sa_vars[key] = var
            ttk.Entry(row, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True)
            if browse == "dir":
                ttk.Button(row, text="Browse…",
                           command=lambda v=var: self._browse_dir_into(v)).pack(side=tk.LEFT, padx=(6, 0))
            elif browse == "file":
                ttk.Button(row, text="Browse…",
                           command=lambda v=var: self._browse_file_into(v)).pack(side=tk.LEFT, padx=(6, 0))

        entry("SA results dir (--sens-dir)", "sens_dir", ".", browse="dir")
        entry("Mechanism YAML (--mechanism)", "mechanism", "mechanism.yaml", browse="file")
        entry("Threshold (--threshold)", "threshold", "0.05")
        entry("Carbon cutoff (--carbon)", "carbon", "0")
        entry("Fuel label (--fuel)", "fuel", "Fuel")
        entry("Results dir (--results-dir)", "results_dir", "results", browse="dir")
        entry("Classification CSV (--classification-file)", "classification_file", "", browse="file")
        entry("Compare temperatures (--compare-temperatures, space-sep K)", "compare_temperatures", "")
        entry("Compare colors (--compare-colors, space-sep)", "compare_colors", "")

        check_frame = ttk.Frame(parent)
        check_frame.pack(fill=tk.X, pady=(6, 0))

        def check(label, key, col, row):
            var = tk.BooleanVar(value=False)
            self._sa_check_vars[key] = var
            ttk.Checkbutton(check_frame, text=label, variable=var).grid(
                row=row, column=col, sticky="w", padx=(0, 16), pady=2)

        check("Generate XML (--generate-xml)", "generate_xml", 0, 0)
        check("Generate plots (--generate-plots)", "generate_plots", 1, 0)
        check("Per-case plots (--per-case-plots)", "per_case_plots", 2, 0)
        check("Generate LaTeX (--generate-latex)", "generate_latex", 0, 1)
        check("LaTeX longtable (--longtable)", "longtable", 1, 1)
        check("Filtered mechanism (--filtered-mechanism)", "filtered_mechanism", 2, 1)

        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=tk.X, pady=(10, 4))
        ttk.Button(btn_row, text="Load demo (Methyl Butanoate)",
                   command=self._load_sa_demo).pack(side=tk.LEFT)
        self._sa_run_btn = ttk.Button(btn_row, text="▶  Run ActiveParameterScreen",
                                       command=self._run_sa_screen)
        self._sa_run_btn.pack(side=tk.LEFT, padx=(6, 0))
        add_export_button(btn_row, self._build_sa_run_status).pack(side=tk.LEFT, padx=(6, 0))
        if not _HAS_PTY_TERMINAL:
            ttk.Label(btn_row, text="⚠ pyte not installed — run: pip install pyte",
                      foreground=PALETTE["warning"]).pack(side=tk.LEFT, padx=8)

        term_frame = ttk.LabelFrame(parent, text="Live output", padding=4)
        term_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self._sa_terminal = PtyTerminal(term_frame, rows=14, cols=110)
        self._sa_terminal.pack(fill=tk.BOTH, expand=True)

    def _browse_dir_into(self, var: "tk.StringVar") -> None:
        path = filedialog.askdirectory()
        if path:
            var.set(path)

    def _browse_file_into(self, var: "tk.StringVar") -> None:
        path = filedialog.askopenfilename()
        if path:
            var.set(path)

    def _load_sa_demo(self) -> None:
        for key, val in _DEMO.items():
            if key in self._sa_vars:
                self._sa_vars[key].set(val)
        for key in ("generate_xml", "generate_plots", "generate_latex"):
            self._sa_check_vars[key].set(True)
        self._status_var.set(
            "Loaded demo: DATASET/METHYL_BUTANOATE_2026/ACTIVE_PARAMETER_SELECTION "
            "(the 'clt' example's 4 staged invocations, combined into one run).")

    def _build_sa_command(self) -> list:
        v = self._sa_vars
        mech = v["mechanism"].get().strip()
        if not mech:
            raise ValueError("Mechanism YAML path is required.")
        needs_class = any(self._sa_check_vars[k].get() for k in
                           ("generate_xml", "generate_plots", "generate_latex", "filtered_mechanism"))
        class_file = v["classification_file"].get().strip()
        if needs_class and not class_file:
            raise ValueError("XML/plots/LaTeX/filtered-mechanism require a classification CSV.")

        cmd = [
            sys.executable, _ACTIVE_PARAM_SCRIPT,
            "--sens-dir", v["sens_dir"].get().strip() or ".",
            "--mechanism", mech,
            "--threshold", v["threshold"].get().strip() or "0.05",
            "--carbon", v["carbon"].get().strip() or "0",
            "--fuel", v["fuel"].get().strip() or "Fuel",
            "--results-dir", v["results_dir"].get().strip() or "results",
        ]
        if class_file:
            cmd += ["--classification-file", class_file]
        if self._sa_check_vars["generate_xml"].get():
            cmd.append("--generate-xml")
        if self._sa_check_vars["generate_plots"].get():
            cmd.append("--generate-plots")
        if self._sa_check_vars["per_case_plots"].get():
            cmd.append("--per-case-plots")
        if self._sa_check_vars["generate_latex"].get():
            cmd.append("--generate-latex")
        if self._sa_check_vars["longtable"].get():
            cmd.append("--longtable")
        if self._sa_check_vars["filtered_mechanism"].get():
            cmd.append("--filtered-mechanism")
        temps = v["compare_temperatures"].get().strip()
        if temps:
            cmd += ["--compare-temperatures", *temps.split()]
        colors = v["compare_colors"].get().strip()
        if colors:
            cmd += ["--compare-colors", *colors.split()]
        return cmd

    def _run_sa_screen(self) -> None:
        try:
            cmd = self._build_sa_command()
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            return
        self._sa_last_command = cmd
        self._sa_terminal.run(cmd)
        self._status_var.set("ActiveParameterScreen running in embedded terminal…")

    def _build_sa_run_status(self) -> RunStatusReport:
        v = self._sa_vars
        return RunStatusReport(
            tool="Uncertainty Quantification and File Generator — from SA data",
            inputs={"SA results dir": v["sens_dir"].get(),
                    "mechanism": v["mechanism"].get(),
                    "classification CSV": v["classification_file"].get()},
            output_dir=v["results_dir"].get(),
            options={k: var.get() for k, var in self._sa_check_vars.items()},
            status="unknown",       # runs in a live PTY terminal, no captured exit code
            summary="live terminal output only -- no structured exit status "
                    "available (embedded PtyTerminal, not a captured subprocess)",
            log=self._sa_terminal.text.get("1.0", "end"),
        )

    # ------------------------------------------------------------------
    # Generate (manual entry)
    # ------------------------------------------------------------------

    def _add_gen_row(self) -> None:
        name = self._gen_rxn_var.get().strip()
        if not name:
            messagebox.showwarning("Missing reaction", "Enter a reaction string first (e.g. H+O2<=>O+OH).")
            return
        rtype = self._gen_type_var.get()
        temps = self._gen_temps_var.get().strip()
        unsrt = self._gen_unsrt_var.get().strip()
        self._gen_tree.insert("", tk.END, values=(name, rtype, temps, unsrt))
        self._gen_rows.append((name, rtype, temps, unsrt))
        self._gen_rxn_var.set("")
        self._autosave.mark_dirty()

    def _remove_gen_row(self) -> None:
        sel = self._gen_tree.selection()
        for item in sel:
            idx = self._gen_tree.index(item)
            self._gen_tree.delete(item)
            if 0 <= idx < len(self._gen_rows):
                del self._gen_rows[idx]
        if sel:
            self._autosave.mark_dirty()

    def _browse_gen_out(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save uncertainty XML", defaultextension=".xml",
            filetypes=[("XML", "*.xml"), ("All files", "*.*")])
        if path:
            self._gen_out_var.set(path)

    def _generate_xml_clicked(self) -> None:
        if not self._gen_rows:
            messagebox.showwarning("Empty", "Add at least one reaction row first.")
            return
        out_path = self._gen_out_var.get().strip()
        if not out_path:
            messagebox.showwarning("Missing output", "Set an output XML path first.")
            return
        reactions = [
            {"name": name, "type": rtype, "temperatures": temps, "uncertainties": unsrt}
            for name, rtype, temps, unsrt in self._gen_rows
        ]
        try:
            generate_uncertainty_xml(reactions, out_path)
        except Exception as e:
            messagebox.showerror("Generation failed", str(e))
            return
        self._gen_status_var.set(f"Wrote {len(reactions)} reaction(s) → {out_path}")
        # Bridge straight into the collapse workflow below.
        self._xml_var.set(out_path)
        save_settings(_APP_NAME, {"last_xml": out_path, "last_mechanism": self._mech_var.get()})

    # ------------------------------------------------------------------
    # Browse
    # ------------------------------------------------------------------

    def _browse_xml(self) -> None:
        path = filedialog.askopenfilename(
            title="Select uncertainty XML", filetypes=[("XML", "*.xml"), ("All files", "*.*")])
        if path:
            self._xml_var.set(path)
            save_settings(_APP_NAME, {"last_xml": path, "last_mechanism": self._mech_var.get()})

    def _browse_mechanism(self) -> None:
        path = filedialog.askopenfilename(
            title="Select mechanism file",
            filetypes=[("CHEMKIN/Cantera", "*.inp *.yaml *.yml *.txt"), ("All files", "*.*")])
        if path:
            self._mech_var.set(path)
            save_settings(_APP_NAME, {"last_xml": self._xml_var.get(), "last_mechanism": path})

    def _browse_out_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Select output CSV", defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if path:
            self._out_csv_var.set(path)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _run_clicked(self) -> None:
        xml_path = self._xml_var.get().strip()
        mech_path = self._mech_var.get().strip()
        if not xml_path or not mech_path:
            messagebox.showwarning("Missing input", "Select an uncertainty XML and a mechanism file.")
            return

        self._status_var.set("Computing…")
        self._run_btn.configure(state=tk.DISABLED)

        def _worker():
            try:
                results = compute_symmetric_bounds(xml_path, mech_path)
                self.root.after(0, lambda: self._on_done(results))
            except Exception as e:
                self.root.after(0, lambda e=e: self._on_error(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_done(self, results: list) -> None:
        self._run_btn.configure(state=tk.NORMAL)
        self._results = results
        for row in self._tree.get_children():
            self._tree.delete(row)
        n_ok = n_err = 0
        for r in results:
            if "error" in r:
                n_err += 1
                self._tree.insert("", tk.END, values=(r["rxn"], "", "", "", f"ERROR: {r['error']}"))
            else:
                n_ok += 1
                self._tree.insert("", tk.END, values=(
                    r["rxn"], f"{r['A_nominal']:.4g}", f"{r['factor']:.4g}",
                    f"{r['A_lb']:.4g}", f"{r['A_ub']:.4g}",
                ))

        out_path = self._out_csv_var.get().strip() or "outputs/uncertainty_bounds.csv"
        write_results_csv(results, out_path)
        self._last_status = "success" if n_err == 0 else "failed"
        self._last_error = None
        self._status_var.set(f"{n_ok} reaction(s) bounded, {n_err} error(s) — written to {out_path}")

    def _on_error(self, error: Exception) -> None:
        self._run_btn.configure(state=tk.NORMAL)
        self._last_status, self._last_error = "failed", str(error)
        self._status_var.set(f"Failed: {error}")
        messagebox.showerror("Computation failed", str(error))

    # -- run-status export (KRUNAL_JULY_23.md point 1) -----------------------
    def _build_run_status(self) -> RunStatusReport:
        log_lines = [f"Generated XML: {self._gen_status_var.get()}"] if self._gen_status_var.get() else []
        for r in self._results:
            if "error" in r:
                log_lines.append(f"  ERROR {r['rxn']}: {r['error']}")
            else:
                log_lines.append(f"  {r['rxn']}: A_nominal={r['A_nominal']:.4g} "
                                 f"factor={r['factor']:.4g} [{r['A_lb']:.4g}, {r['A_ub']:.4g}]")
        return RunStatusReport(
            tool="Uncertainty Generator",
            inputs={"uncertainty XML": self._xml_var.get(),
                    "mechanism file": self._mech_var.get()},
            output_dir=self._out_csv_var.get(),
            options={"generated reaction rows": len(self._gen_rows)},
            status=self._last_status,
            summary=self._last_error,
            log="\n".join(log_lines),
        )


def main() -> int:
    args = parse_args()

    if args.generate_xml:
        if not args.reactions_json or not args.output:
            print("ERROR: --generate-xml requires --reactions-json and --output")
            return 1
        reactions = json.loads(Path(args.reactions_json).read_text())
        generate_uncertainty_xml(reactions, args.output)
        print(f"n_reactions={len(reactions)}")
        print(f"output={args.output}")
        return 0

    if args.compute_bounds:
        if not args.xml or not args.mechanism:
            print("ERROR: --compute-bounds requires --xml and --mechanism")
            return 1
        results = compute_symmetric_bounds(args.xml, args.mechanism)
        n_ok = sum(1 for r in results if "error" not in r)
        n_err = len(results) - n_ok
        out_csv = args.output_csv or "outputs/uncertainty_bounds.csv"
        write_results_csv(results, out_csv)
        for r in results:
            if "error" in r:
                print(f"ERROR {r['rxn']}: {r['error']}")
            else:
                print(f"OK {r['rxn']}: A_nominal={r['A_nominal']:.6g} "
                      f"factor={r['factor']:.6g} A_lb={r['A_lb']:.6g} A_ub={r['A_ub']:.6g}")
        print(f"n_ok={n_ok}")
        print(f"n_err={n_err}")
        print(f"output_csv={out_csv}")
        return 0 if n_err == 0 else 1

    if args.no_gui or not _HAS_TK:
        if args.xml:
            print(f"XML path: {args.xml} (exists={Path(args.xml).exists()})")
        if args.mechanism:
            print(f"Mechanism path: {args.mechanism} (exists={Path(args.mechanism).exists()})")
        if not args.xml and not args.mechanism:
            print("No --xml/--mechanism given (--no-gui smoke check, nothing to check).")
        return 0

    root = tk.Tk()
    apply_theme(root)
    app = UncertaintyGeneratorApp(root, initial_xml=args.xml, initial_mechanism=args.mechanism)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
