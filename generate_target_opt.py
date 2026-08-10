#!/usr/bin/env python3
"""
generate_target_opt.py — Unified GUI for the RMIP + MUQ-SAC toolchain.

Creates and edits ALL configuration and input files needed by the pipeline:
  1. target.opt  — master YAML config (all sections: Type/Counts/Bin/Stats/RMIP/ForwardUQ)
  2. .target     — experimental data targets (ignition delay, flame speed, etc.)
  3. .add        — addendum: per-dataset solver settings (YAML)
  4. .xml        — uncertainty factors per reaction (temperature-dependent)
  5. .so         — shared-object compilation helper (parallel_yaml_writer, shuffle)

Usage:
  python generate_target_opt.py               # open GUI
  python generate_target_opt.py --no-gui      # print default config to stdout
  python generate_target_opt.py target.opt    # pre-load file
"""

import os
import sys
import re
import csv
import yaml
import pandas as pd
import numpy as np
import json
import shutil
import argparse
import textwrap
import subprocess
from io import StringIO
from pathlib import Path
from copy import deepcopy
from xml.etree import ElementTree as ET
from xml.dom.minidom import parseString

# Repo root -- this file lives at the repo root itself, so its own directory
# IS the root. Used by _default_bin_paths() below so the repo-internal Bin
# entries (yaml_writer/SA_tool/SA_tool_3p) are derived from wherever this
# checkout actually lives, not hardcoded to one machine's pre-move location
# (see MarkDownFiles/WORKBENCH_AUDIT_2026-08-10.md, defect B1).
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# src/ on sys.path for gui_common.theme below -- appended, not inserted at 0:
# src/io is a package named "io" and would shadow the stdlib "io" imported
# just above (StringIO) if it took precedence (same hazard documented in
# rmip_cli.py / mechanism_check_gui.py's identical bootstrap).
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.append(_SRC)

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
    _HAS_TK = True
except ImportError:
    _HAS_TK = False

try:
    import pty
    import signal
    import threading
    import pyte
    _HAS_PTY_TERMINAL = True
except ImportError:
    _HAS_PTY_TERMINAL = False

# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Helper Classes — Auto-Save, Tab Locking, Fuel Normalization
# ─────────────────────────────────────────────────────────────────────────────

class FuelNormalizer:
    """
    Normalize and validate fuel species across GUI tabs and mechanism files.
    Handles:
    - Case-insensitive matching (H2 ≈ h2, NC7H16 ≈ nc7h16)
    - Alias resolution (n-Heptane → NC7H16, heptane → NC7H16)
    - Cross-file consistency (XML vs CSV vs mechanism species)
    """
    # Canonical fuel database (from chem_data.py + aliases)
    CANONICAL_FUELS = {
        # Canonical form → (set of aliases, MW, nu_O2, SMILES or None if uncertain)
        "H2": ({"h2", "hydrogen"}, 2.016, 0.5, "[H][H]"),
        "CO": ({"co", "carbon monoxide"}, 28.01, 0.5, "[C-]#[O+]"),
        "CH4": ({"ch4", "methane"}, 16.043, 2.0, "C"),
        "C2H4": ({"c2h4", "ethene", "ethylene"}, 28.054, 3.0, "C=C"),
        "C2H6": ({"c2h6", "ethane"}, 30.069, 3.5, "CC"),
        "C3H8": ({"c3h8", "propane"}, 44.097, 5.0, "CCC"),
        "C4H10": ({"c4h10", "butane"}, 58.123, 6.5, "CCCC"),
        "C4H6": ({"c4h6", "butene", "butadiene"}, 54.092, 5.5, "C=CC=C"),
        "CH2O": ({"ch2o", "formaldehyde"}, 30.026, 1.0, "C=O"),
        "CH3OH": ({"ch3oh", "methanol"}, 32.042, 1.5, "CO"),
        "C2H5OH": ({"c2h5oh", "ethanol"}, 46.068, 3.0, "CCO"),
        "NH3": ({"nh3", "ammonia"}, 17.031, 0.75, "N"),
        "N2H4": ({"n2h4", "hydrazine"}, 32.052, 1.0, "NN"),
        "NC7H16": ({"nc7h16", "n-heptane", "nheptane", "heptane", "n-c7h16"}, 100.205, 11.0, "CCCCCCC"),
        "NC12H26": ({"nc12h26", "n-dodecane", "n-c12h26", "dodecane"}, 170.338, 18.5, "CCCCCCCCCCCC"),
        "C7H8": ({"c7h8", "toluene"}, 92.141, 9.0, "Cc1ccccc1"),
        # Isomer/exact-structure uncertain — left as None so species-translation
        # treats these as low-confidence rather than silently matching on a guess.
        "IC16H34": ({"ic16h34", "isohexadecane", "i-c16h34"}, 226.441, 24.5, None),
        "C12H23": ({"c12h23"}, 167.311, 17.75, None),
        "OME3": ({"ome3", "polymethoxymethane"}, 136.147, 5.75, "COCOCOCOC"),
        "MB-C5H10O2": ({"mb-c5h10o2", "mb-c5h10o2", "methyl butyrate"}, 86.132, 5.25, "CCCC(=O)OC"),
    }

    @staticmethod
    def normalize(fuel_input: str) -> str:
        """
        Normalize fuel name to canonical form.
        E.g. 'h2' → 'H2', 'n-heptane' → 'NC7H16', 'nheptane' → 'NC7H16'
        Returns canonical form or original input if no match found.
        """
        normalized = fuel_input.strip().lower()
        for canonical, (aliases, _, _, _) in FuelNormalizer.CANONICAL_FUELS.items():
            if normalized == canonical.lower() or normalized in aliases:
                return canonical
        return fuel_input  # fallback to original if not in table

    @staticmethod
    def get_mw(fuel: str) -> float:
        """Get molecular weight (g/mol) for a fuel. Returns None if not found."""
        canonical = FuelNormalizer.normalize(fuel)
        for fuel_key, (aliases, mw, _, _) in FuelNormalizer.CANONICAL_FUELS.items():
            if canonical == fuel_key or canonical.lower() == fuel_key.lower():
                return mw
        return None

    @staticmethod
    def get_nu_o2(fuel: str) -> float:
        """Get stoichiometric O2 (mol O2 / mol fuel) for a fuel. Returns None if not found."""
        canonical = FuelNormalizer.normalize(fuel)
        for fuel_key, (aliases, _, nu, _) in FuelNormalizer.CANONICAL_FUELS.items():
            if canonical == fuel_key or canonical.lower() == fuel_key.lower():
                return nu
        return None

    @staticmethod
    def get_smiles(fuel: str) -> str:
        """Get SMILES for a well-known fuel. Returns None if not found/uncertain."""
        canonical = FuelNormalizer.normalize(fuel)
        for fuel_key, (aliases, _, _, smiles) in FuelNormalizer.CANONICAL_FUELS.items():
            if canonical == fuel_key or canonical.lower() == fuel_key.lower():
                return smiles
        return None

    @staticmethod
    def is_known_fuel(fuel: str) -> bool:
        """Check if fuel is in the canonical database."""
        normalized = fuel.strip().lower()
        for canonical, (aliases, _, _, _) in FuelNormalizer.CANONICAL_FUELS.items():
            if normalized == canonical.lower() or normalized in aliases:
                return True
        return False

    @staticmethod
    def validate_fuel_against_mechanism(fuel: str, mechanism_species: list) -> tuple:
        """
        Validate a fuel against mechanism species list.
        Returns (is_valid, message, suggestions)
        """
        canonical = FuelNormalizer.normalize(fuel)
        mechanism_species_normalized = [s.lower() for s in mechanism_species]

        if canonical.lower() in mechanism_species_normalized:
            return (True, f"✓ Fuel '{canonical}' found in mechanism", [])

        # Try fuzzy match
        suggestions = [s for s in mechanism_species if canonical.lower() in s.lower() or s.lower() in canonical.lower()]
        if suggestions:
            return (False, f"Fuel '{canonical}' NOT in mechanism. Did you mean:", suggestions)

        return (False, f"Fuel '{canonical}' NOT found in mechanism. Available fuels: {', '.join(mechanism_species[:5])}...", [])


class TabLockingManager:
    """Manage tab accessibility: completed tabs editable, unreached tabs locked.

    Uses Notebook <<NotebookTabChanged>> event to intercept and reject tab clicks on locked tabs.
    """

    def __init__(self, notebook, num_tabs):
        self.nb = notebook
        self.num_tabs = num_tabs
        self.visited_tabs = set([0])  # Tab 0 always accessible
        self.current_tab = 0
        self._status_callback = None  # callback to update status bar
        self._validator = None  # optional callable(tab_index) -> list[str] errors
        # Capture pristine tab names ONCE, before any badges are applied
        self._base_titles = [notebook.tab(i, "text") for i in range(num_tabs)]

    def set_status_callback(self, callback):
        """Set callback to update status messages."""
        self._status_callback = callback

    def set_validator(self, callback):
        """Set callback(tab_index) -> list[str] errors, run before advancing to a
        brand-new tab via a direct tab-header click (mirrors the "Next" button's
        validation so clicking a tab header can't bypass required-field checks)."""
        self._validator = callback

    def mark_complete(self, tab_index: int):
        """Mark a tab as visited/complete."""
        self.visited_tabs.add(tab_index)
        self.update_display()

    def can_access(self, tab_index: int) -> bool:
        """Check if user can access a tab (is visited or currently on it)."""
        return tab_index in self.visited_tabs or tab_index == self.current_tab

    def is_next_tab(self, tab_index: int) -> bool:
        """Check if tab is the next accessible tab."""
        return tab_index == max(self.visited_tabs) + 1

    def handle_tab_click(self, tab_index: int) -> bool:
        """Handle user clicking on a tab. Returns True if allowed, False if rejected."""
        if self.can_access(tab_index):
            self.current_tab = tab_index
            self.update_display()
            return True

        if self.is_next_tab(tab_index):
            # Advancing to a brand-new tab must pass the same validation as the
            # "Next" button — previously a direct tab-header click skipped this
            # check entirely, letting required-field validation be bypassed.
            if self._validator:
                errors = self._validator(self.current_tab)
                if errors:
                    if self._status_callback:
                        self._status_callback(
                            f"❌ Fix these on Tab {self.current_tab} first: " + "; ".join(errors))
                    self.nb.select(self.current_tab)
                    return False
            self.current_tab = tab_index
            self.visited_tabs.add(tab_index)
            self.update_display()
            return True

        # Locked — reject the click
        last_visited = max(self.visited_tabs)
        if self._status_callback:
            self._status_callback(f"❌ Tab {tab_index} is locked! Complete Tab {last_visited} first.")
        self.nb.select(self.current_tab)  # Go back to where we were
        return False

    def update_display(self):
        """Update tab visual indicators (✓ for visited, 🔒 for locked)."""
        for i in range(self.num_tabs):
            # Use the pristine tab name captured at __init__ time, never the live (possibly mutated) one
            base_text = self._base_titles[i]

            if i in self.visited_tabs:
                badge = " ✓"
            elif i <= max(self.visited_tabs) + 1:
                badge = ""  # Next accessible tab, no badge
            else:
                badge = " 🔒"  # Locked

            self.nb.tab(i, text=base_text + badge)


class VariableNameMapper:
    """
    Map GUI field names to codebase variable names with comments.
    Ensures aesthetic GUI names translate cleanly to MUQ-SAC/RMIP codebase.
    """
    # GUI name → (codebase name, comment explaining the mapping)
    MAPPINGS = {
        # Project tab
        "proj_name": ("project.name", "Project identifier (no spaces)"),
        "proj_fuel": ("project.fuel_name", "Human-readable fuel name shown in reports"),
        "proj_formula": ("Inputs.fuel.formula", "Cantera/CHEMKIN species ID (e.g. NC7H16)"),
        "proj_outdir": ("project.output_base_dir", "Root for outputs: NOMINAL/, Opt/, etc."),

        # Type tab
        "opt_type": ("Type.optimization_type", "PRS | SAC | direct"),
        "alg_type": ("Type.Algorithm_type", "gradient-based | gradient-based-zeta | evolutionary | custom"),
        "algorithm": ("Type.Algorithm", "SLSQP | L-BFGS-B | trust-constr | SLSQP-zeta | "
                      "L-BFGS-B-zeta | DE | GA-pygad | GA-deap | Powell | <custom>"),

        # Counts
        "n_rxn": ("Counts.total_reactions", "Number of reactions optimized"),
        "n_thr": ("Counts.parallel_threads", "Parallel threads (capped at CPU-5)"),
        "n_tar": ("Counts.targets_count", "Number of experimental target points"),
        "carbon_n": ("SA.carbon_number", "Carbon number for SA grouping (0=H2/CO)"),

        # Locations
        "loc_mech": ("Locations.mechanism", ".inp or .yaml mechanism file"),
        "loc_thermo": ("Locations.thermo_file", "Separate CHEMKIN thermo (.dat)"),
        "loc_unsrt": ("Locations.uncertainty_data", "Uncertainty XML (.xml)"),
        "loc_targets": ("Locations.targets", "Experimental targets (.target file)"),
        "loc_add": ("Locations.addendum", "Solver addendum (.add YAML file)"),

        # Target row fields (dynamic)
        "target_T": ("T", "Temperature (K)"),
        "target_P": ("P", "Pressure (atm or bar, see units)"),
        "target_phi": ("Phi", "Equivalence ratio (unitless)"),
        "target_observed": ("observed", "Measured ignition delay or flame speed"),
        "target_deviation": ("deviation", "Measurement uncertainty (same units as observed)"),

        # Fuel in target
        "fuel_species": ("Fuel", "Fuel species name in .target format"),
        "fuel_xf": ("fuel_x", "Fuel mole fraction in mixture"),

        # Oxidizer in target
        "ox_species": ("Oxidizer", "Oxidizer species (usually O2)"),
        "ox_xf": ("ox_x", "Oxidizer mole fraction"),

        # Bath gas in target
        "bath_species": ("Bath_gas", "Diluent species (N2, AR, etc.)"),
        "bath_xf": ("bath_x", "Diluent mole fraction"),
    }

    @staticmethod
    def get_codebase_name(gui_name: str) -> str:
        """Get codebase variable name from GUI name."""
        return VariableNameMapper.MAPPINGS.get(gui_name, (gui_name, ""))[0]

    @staticmethod
    def get_comment(gui_name: str) -> str:
        """Get explanatory comment for a GUI field."""
        return VariableNameMapper.MAPPINGS.get(gui_name, ("", ""))[1]


_GUI_SETTINGS_PATH = Path(__file__).resolve().parent / ".rmip_gui_settings.json"


def _load_gui_settings() -> dict:
    """Load small persisted GUI settings (e.g. the chosen checkpoint path)."""
    try:
        return json.loads(_GUI_SETTINGS_PATH.read_text())
    except Exception:
        return {}


def _save_gui_settings(settings: dict):
    """Persist small GUI settings (e.g. the chosen checkpoint path)."""
    try:
        _GUI_SETTINGS_PATH.write_text(json.dumps(settings, indent=2))
    except Exception as e:
        print(f"Could not save GUI settings: {e}")


class PtyTerminal(ttk.Frame):
    """A real embedded terminal: spawns a subprocess on a pseudo-terminal
    (stdlib pty.fork()) and renders its live ANSI/VT100 output — colors,
    cursor movement, in-place progress updates — via pyte's screen-buffer
    emulator, refreshed into a read-only Tk Text widget. Unlike a plain
    log-streaming text box, this behaves like a real terminal window because
    the child process actually has a tty (isatty() is True), so tools that
    render progress bars / colorize output based on that behave normally.
    """

    _FG_COLORS = {
        "black": "#45475a", "red": "#f38ba8", "green": "#a6e3a1", "brown": "#f9e2af",
        "blue": "#89b4fa", "magenta": "#cba6f7", "cyan": "#94e2d5", "white": "#cdd6f4",
        "default": "#cdd6f4",
    }

    def __init__(self, parent, rows=24, cols=100, font=("Courier", 10)):
        super().__init__(parent)
        self._rows, self._cols = rows, cols
        self._screen = None
        self._stream = None
        self._pid = None
        self._fd = None
        self._alive = False
        self._refresh_job = None

        self.text = tk.Text(self, width=cols, height=rows, bg="#1e1e2e", fg="#cdd6f4",
                             insertbackground="#cdd6f4", font=font, wrap=tk.NONE, state="disabled")
        self.text.pack(fill=tk.BOTH, expand=True)
        for name, color in self._FG_COLORS.items():
            self.text.tag_configure(f"fg_{name}", foreground=color)

    def is_available(self) -> bool:
        return _HAS_PTY_TERMINAL

    def run(self, cmd: list, cwd: str = None):
        """Spawn cmd on a real pty and start streaming its live output."""
        if not _HAS_PTY_TERMINAL:
            self.text.configure(state="normal")
            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, "pyte is not installed — run: pip install pyte")
            self.text.configure(state="disabled")
            return
        self.stop()
        self._screen = pyte.Screen(self._cols, self._rows)
        self._stream = pyte.ByteStream(self._screen)
        pid, fd = pty.fork()
        if pid == 0:
            # Child: replace this process image entirely with cmd.
            try:
                if cwd:
                    os.chdir(cwd)
                os.execvp(cmd[0], cmd)
            except Exception:
                os._exit(1)
        self._pid = pid
        self._fd = fd
        self._alive = True
        threading.Thread(target=self._read_loop, daemon=True).start()
        self._refresh()

    def _read_loop(self):
        while self._alive:
            try:
                data = os.read(self._fd, 4096)
            except OSError:
                break
            if not data:
                break
            self._stream.feed(data)
        self._alive = False

    def _refresh(self):
        if self._screen is not None:
            self.text.configure(state="normal")
            self.text.delete("1.0", tk.END)
            for row_idx in range(self._rows):
                line = self._screen.display[row_idx]
                row_buf = self._screen.buffer.get(row_idx, {})
                col, n = 0, len(line)
                while col < n:
                    ch = row_buf.get(col)
                    fg = ch.fg if (ch and ch.fg in self._FG_COLORS) else "default"
                    start = col
                    while col < n:
                        c2 = row_buf.get(col)
                        fg2 = c2.fg if (c2 and c2.fg in self._FG_COLORS) else "default"
                        if fg2 != fg:
                            break
                        col += 1
                    self.text.insert(tk.END, line[start:col], (f"fg_{fg}",))
                self.text.insert(tk.END, "\n")
            if not self._alive:
                self.text.insert(tk.END, "\n[process exited]\n")
            self.text.configure(state="disabled")
            self.text.see(tk.END)
        if self._alive:
            self._refresh_job = self.after(150, self._refresh)

    def stop(self):
        self._alive = False
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None
        if self._pid:
            try:
                os.kill(self._pid, signal.SIGTERM)
            except Exception:
                pass
        self._pid = None
        self._fd = None


class AutoSaveManager:
    """Automatically save GUI state every 5 seconds if changed."""

    def __init__(self, root, save_callback, interval_ms=5000):
        self.root = root
        self.save_callback = save_callback
        self.interval_ms = interval_ms
        self.timer_id = None
        self.dirty = False

    def mark_dirty(self):
        """Mark state as dirty and schedule save."""
        self.dirty = True
        self._schedule_save()

    def _schedule_save(self):
        """Cancel pending timer and schedule a new one."""
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
        self.timer_id = self.root.after(self.interval_ms, self._do_save)

    def _do_save(self):
        """Perform the actual save."""
        if self.dirty:
            try:
                self.save_callback()
                self.dirty = False
            except Exception as e:
                print(f"Auto-save error: {e}")

    def on_close(self):
        """Save final state before exit."""
        if self.dirty:
            self._do_save()
        if self.timer_id:
            self.root.after_cancel(self.timer_id)


# ─────────────────────────────────────────────────────────────────────────────
# Theme palette and fonts  (Task 1A)
# ─────────────────────────────────────────────────────────────────────────────
# PALETTE/FONTS used to be defined here verbatim -- the exact same dicts
# also lived independently in gui_common/theme.py and (as hex literals)
# mso_studio/gui/theme.py. gui_common.theme is now the single source for
# the Tk stack (itself a thin adapter over mso_studio.gui.tokens for the 13
# core colors), so this file imports rather than re-defines them. The old
# TAB_COLORS list (per-tab accent chips) was dead code -- grepped zero
# references anywhere in this file -- and is dropped rather than ported.
from gui_common.theme import PALETTE, FONTS, style_text_widget  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Comprehensive help text for every target.opt variable  (Task 1A)
# ─────────────────────────────────────────────────────────────────────────────

_HELP: dict = {
    # project
    "proj_name":    "Short identifier used as the output folder name. No spaces.",
    "proj_fuel":    "Human-readable fuel name shown in reports (e.g. 'n-Heptane').",
    "proj_formula": "Cantera/CHEMKIN species identifier (e.g. NC7H16, H2, CH4).",
    "proj_outdir":  "Root directory for all generated outputs (NOMINAL/, Opt/, Plot/, …).",
    # Type
    "opt_type":     "PRS = Polynomial Response Surface (default, fast). SAC = Sampling of "
                    "Arrhenius Curves. 'direct' = direct optimizer (no surrogate).",
    "alg_type":     "gradient-based: SLSQP/L-BFGS-B/trust-constr/Powell. gradient-based-zeta: "
                    "SLSQP-zeta/L-BFGS-B-zeta (direct ζ-space, analytic Jacobian). "
                    "evolutionary: GA-pygad/GA-deap/DE. custom: type your own Algorithm value.",
    "algorithm":    "Suggestion list reflects what's actually implemented in "
                    "src/MUQ-SAC/OptimizationTool2_0.py (see ⓘ). This field accepts any "
                    "typed value too — unrecognized values fall back to Powell in the backend.",
    # Counts
    "n_rxn":        "Number of reactions selected by sensitivity analysis for optimization. "
                    "Read as len(selected_parameters) from the SA step.",
    "n_thr":        "Parallel threads for NOMINAL simulations. Capped at cpu_count−5 "
                    "to leave headroom for the OS. See 'Thread cap' in Run Jobs tab.",
    "n_tar":        "Number of experimental target data-points used. Must match rows in .target file.",
    "carbon_n":     "Carbon number for SA grouping. 0 = H2/CO/syngas mechanisms.",
    # Bin
    "bin_muqsac":   "Directory containing run_script.py and the MUQ-SAC modules.",
    "bin_solver":   "FlameMaster Bin/bin directory (for FlameMaster solver only).",
    "bin_yaml":     "Path to compiled parallel_yaml_writer.so. See the 'Compile' tab.",
    "bin_samap":    "samap executable — used by the SA subprocess. PLACEHOLDER if not used.",
    "bin_jpdap":    "jpdap executable — used by the SA subprocess. PLACEHOLDER if not used.",
    "bin_sa":       "Path to sens.py (1-parameter A-factor sensitivity).",
    "bin_sa3":      "Path to sens_3_params.py (3-parameter A,n,Ea sensitivity).",
    # Inputs
    "filetype":     "chemkin: standard CHEMKIN-II .inp + thermo. FlameMaster: .pre file.",
    "fuelclass":    "Mono: single fuel species. Multi: fuel blend (use the fuel rows in "
                    "'Files & Paths').",
    "global_rxn":   "Balanced global reaction string, e.g. '2H2+O2==2H2O'. Used to compute "
                    "stoichiometric O2 coefficient and equivalence ratio.",
    "analysis":     "reaction: optimise Arrhenius parameters. thermo: optimise NASA-7 coefficients.",
    # Locations
    "loc_mech":     "Primary mechanism file (.yaml or .inp) for the MUQ-SAC run.",
    "loc_pre":      "FlameMaster .pre file (only needed if fileType=FlameMaster).",
    "loc_unsrt":    "Uncertainty XML file generated in the 'Uncertainty XML' tab.",
    "loc_thermo":   "Separate CHEMKIN thermo file (.dat). Leave blank if embedded in .inp.",
    "loc_trans":    "Transport data file (.dat). Currently out of scope — leave blank.",
    "loc_targets":  ".target file listing all experimental data points. Use the 'Targets' tab.",
    "loc_add":      ".add addendum YAML listing per-dataset solver settings. Use the 'Addendum' tab.",
    # Stats
    "design":       "A-facto: perturb only A-factor (fastest, 1 param/reaction). "
                    "Monte-Carlo-All: perturb A,n,Ea. B1/A1+B1+C1: mixed designs.",
    "order":        "Polynomial order of the response surface. 2=quadratic (recommended). "
                    "Higher orders need more samples (Sampling_of_PRS must scale up).",
    "sampling":     "Samples = Sampling_of_PRS × n_reactions. 4 (default) gives adequate coverage "
                    "for 2nd-order PRS. Use 6–8 for 3rd order or noisy data.",
    "prs_type":     "Partial: use partial_PRS_system (sparse selection). Full: use all monomials.",
    "cutoff":       "SA cut-off (%): reactions with sensitivity below this threshold are excluded "
                    "from optimization. Reduces dimensionality.",
    "mre":          "MRE_criteria (%): mean relative error threshold that triggers adaptive "
                    "outlier retraining (adds N_new samples around outlier regions).",
    "objective":    "powerMeanWMRE: power-mean weighted MRE (recommended, robust). "
                    "WMRE: plain weighted MRE. logRMSE: log-space RMSE. "
                    "penWMRE: adds penalty for violating bounds. omhWMRE: outlier-minimizing.",
    "pm_p":         "Power-mean exponent p. p→0 = geometric mean (uniform). "
                    "p=1 = arithmetic mean. Large p = Chebyshev (worst-case). Default 0.1.",
    "pm_p_start":   "Annealing start value for pm_p. PRS starts with pm_p_start and "
                    "decays to pm_p over num_generations.",
    "num_gen":      "Number of GA generations. 20000 is adequate for most problems.",
    "softmax_beta": "Softmax temperature for softChebysheWMRE objective. Higher = harder Chebyshev.",
    "pen_alpha":    "Penalty fraction (0–1): optimized params must not increase MRE by more "
                    "than (1−pen_alpha)×100 % over nominal. 0.9 = max 10 % degradation allowed.",
    "pen_K":        "Penalty weight K. Larger K = harder constraint enforcement.",
    "w_tig":        "Objective weight for ignition delay (Tig) targets. 1.0 = full weight.",
    "w_fls":        "Objective weight for laminar flame speed (Fls) targets. 0 = off.",
    "out_N":        "N_new: number of new samples added per outlier-retraining pass.",
    "out_mode":     "dm_global: fill gaps across the full design-matrix space. "
                    "local: concentrate new samples around outlier regions.",
    "out_max":      "Maximum number of outlier-retraining passes (prevents infinite loop).",
    # RMIP
    "rmip_db":      "SQLite database for RMIP. Created fresh on first 'rmip parse'. "
                    "Stores mechanisms, species, reactions, thermo.",
    "rmip_glossary":"CSV mapping species names to SMILES (optional). Used by canonicalize.py.",
    # Graph
    "g_layout":     "2D graph layout algorithm. spring=force-directed (best general). "
                    "preset_carbon_ring=grouped by Cn (good for large mechanisms).",
    "g_outdir":     "Directory for exported 2D graph images.",
    "g_fmt":        "Image format for graph export. pdf for vector quality.",
    # Graph3D
    "g3_shell":     "Radial gap between carbon shells (≥2.0). Increase for large mechanisms.",
    "g3_layer":     "Z-height between carbon layers. 0 = flat solar-system plane.",
    "g3_order":     "alpha: species ordered alphabetically on each ring. "
                    "family: grouped by chemical family (hydrocarbons → oxygenates → N-containing).",
    # Comparison
    "cmp_tolA":     "Relative tolerance on A-factor to call a reaction 'identical' (fraction, e.g. 0.01=1%).",
    "cmp_toln":     "Absolute tolerance on temperature exponent n.",
    "cmp_tolE":     "Absolute tolerance on activation energy Ea (J/mol).",
    # Fusion
    "fus_name":     "Name for the fused mechanism stored in the RMIP DB.",
    "fus_uf":       "Uncertainty-factor warning threshold. If max(A)/min(A) > this, logs a WARNING.",
    # Reduction
    "red_method":   "DRG: fast, graph-based. DRGEP: more conservative. PFA: signed fluxes. "
                    "DRGPSA: SA-weighted DRG (needs --sa-json). DRGSA: pure SA ranking.",
    "red_target":   "Comma-separated seed species that must be retained (e.g. fuel, O2, products).",
    "red_eps":      "Maximum threshold ε for the reduction sweep.",
    "red_T":        "Temperature (K) at which rate coefficients are evaluated for DRG graph weights.",
    "red_P":        "Pressure (atm) for rate evaluation.",
    "red_phi":      "Equivalence ratio for Cantera-based rate evaluation.",
    # Unified tree
    "ut_mode":      "anchored: keep anchor mechanism reactions unchanged; import/optimise others. "
                    "optimize_all: geometric-mean all shared reactions.",
    "ut_anchor":    "Name of the anchor mechanism (must match one name in the 'Mechanisms' tab).",
    "ut_tmin":      "Minimum temperature (K) for uncertainty band computation.",
    "ut_tmax":      "Maximum temperature (K) for uncertainty band computation.",
    "ut_dt":        "Temperature step dT (K).",
    "ut_pref":      "Reference pressure (atm) for PLOG interpolation and Cantera falloff.",
    # ForwardUQ
    "uq_n":         "QMC sample count. 50000 is recommended. More = tighter CI but same cost "
                    "(PRS eval is cheap). Diminishing returns beyond 200000.",
    "uq_method":    "sobol: quasi-Monte Carlo (best for high-D, low-discrepancy). "
                    "lhs: Latin hypercube. random: plain Monte Carlo.",
    "uq_outdir":    "Directory for ForwardUQ plots (ignition-delay bands, Sobol indices, etc.).",
    "uq_ci":        "Confidence interval level. 0.95 = [2.5%, 97.5%] prediction interval.",
}

# ─────────────────────────────────────────────────────────────────────────────
# Optimization algorithms actually dispatchable in src/MUQ-SAC/OptimizationTool2_0.py
# (the active dispatch file). Kept as a suggestion list, not an enforced enum —
# the Algorithm field stays a free-text-capable combobox so users running a
# method not listed here (e.g. a new OptimizationTool_v4.py branch) can still
# type it in directly.
# ─────────────────────────────────────────────────────────────────────────────
KNOWN_ALGORITHMS = {
    "SLSQP":         "Gradient-based (scipy), bounded, encoded parameter space. Implemented.",
    "L-BFGS-B":      "Gradient-based (scipy), bounded, encoded parameter space. Implemented.",
    "trust-constr":  "Gradient-based (scipy), constrained, encoded parameter space. Implemented.",
    "SLSQP-zeta":    "Gradient-based, direct ζ-space with analytic Jacobian. Implemented.",
    "L-BFGS-B-zeta": "Gradient-based, direct ζ-space with analytic Jacobian. Implemented.",
    "DE":            "Differential evolution (scipy). Implemented.",
    "GA-pygad":      "Genetic algorithm (PyGAD). Implemented.",
    "GA-deap":       "Genetic algorithm (DEAP). Implemented only if the 'deap' package is installed; "
                     "silently falls back otherwise.",
    "Powell":        "Derivative-free. Used automatically as a fallback for unrecognized values.",
}

ALGORITHM_TYPE_GROUPS = {
    "gradient-based":      ["SLSQP", "L-BFGS-B", "trust-constr", "Powell"],
    "gradient-based-zeta": ["SLSQP-zeta", "L-BFGS-B-zeta"],
    "evolutionary":        ["GA-pygad", "GA-deap", "DE"],
    "custom":              [],  # user-typed algorithm name not in KNOWN_ALGORITHMS
}

# ─────────────────────────────────────────────────────────────────────────────
# Experimental target/simulation types actually dispatched on in
# src/MUQ-SAC/make_input_file.py (create_input_file()). Used everywhere a
# "target_type" combobox is shown (Target Builder, Addendum Builder) so they
# can't drift out of sync with each other or with the backend again.
# ─────────────────────────────────────────────────────────────────────────────
TARGET_TYPES = {
    "Tig":    "Ignition delay (shock tube reflected-shock, or RCM via ign_mode). "
              "Solvers: cantera, CHEMKIN_PRO, FlameMaster.",
    "Fls":    "Freely-propagating laminar flame speed. Solver: cantera only.",
    "Flf":    "Residence-time-controlled reactor calc (JSR-like, despite the name). "
              "Solver: cantera only.",
    "Flf_a":  "Heat-flux / burner-stabilized flame (imposed T profile). "
              "Solvers: cantera, FlameMaster.",
    "JSR":    "Jet/perfectly-stirred reactor (residence-time controlled). "
              "Solvers: cantera, CHEMKIN_PRO, FlameMaster. Supports flux_analysis.",
    "PFR":    "Plug-flow reactor (length/diameter/mdot marched). "
              "Solvers: cantera, CHEMKIN_PRO, FlameMaster (approximate). Supports flux_analysis.",
    "RCM":    "Rapid compression machine (reactive or non_reactive volume profile). "
              "Solvers: cantera, CHEMKIN_PRO.",
    "Flw":    "Flow-reactor species-decay/rate experiment. Solvers: cantera, FlameMaster.",
}

# Fields specific to each target_type, shown only when that type is selected
# in the Addendum Builder row editor (mirrors combustion_target_class.py).
# Columns backing the Experimental Data tab's target-row DataFrame (§1 of the
# GUI rework plan). Matches _add_trow's field list, plus two columns populated
# by the optional HTT/LTT MaxSimulationTime split (see _apply_httltt_split).
_TARGET_ROW_COLUMNS = [
    "dataset_id", "target_type", "fuel_species", "fuel_xf",
    "oxidizer_species", "ox_xf", "bath_species", "bath_xf",
    "T", "P", "P_unit", "phi", "observed", "deviation_pct", "data_weight",
    "max_simulation_time", "temp_target_class",
]

TARGET_TYPE_FIELDS = {
    "Tig":   ["ign_delay_def", "ign_cond", "specific_cond", "BoundaryLayer"],
    "Fls":   ["fls_type", "fls_fuel"],
    "Flf":   ["residenceTime", "flf_species"],
    "Flf_a": ["ExpTempFile", "flow_rate"],
    "JSR":   ["residenceTime", "jsr_species", "flux_analysis", "flux_element"],
    "PFR":   ["pfr_length", "pfr_diameter", "pfr_mdot", "pfr_n_points", "flux_analysis", "flux_element"],
    "RCM":   ["RCM_type", "ign_delay_def", "ign_cond"],
    "Flw":   ["flw_length", "flw_species", "flw_method"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Default configuration
# ─────────────────────────────────────────────────────────────────────────────
def _default_bin_paths():
    """Resolve the toolchain paths that back DEFAULT_CONFIG["Bin"].

    (M28) These were previously hardcoded to KP's dev-machine layout. Each
    now reads from an environment variable, falling back to a default -- so
    an unconfigured checkout behaves reasonably out of the box, while another
    machine (or CI) can override any entry without touching this file.

    (Round-2 audit fix, B1) The three repo-internal entries -- yaml_writer,
    SA_tool, SA_tool_3p -- previously defaulted to a literal
    ``/data/OPEN_CODE/PHASE-3/...`` path: this repo's location *before* it
    moved to its current directory. That old location still exists on disk
    with its own unfixed copy of the code, so any target.opt generated with
    the old default silently ran stale code out from under the current
    checkout (see WORKBENCH_AUDIT_2026-08-10.md, defect B1, and its B5
    corollary -- a pause/edit/resume that can never reach the SA stage
    because the subprocess it spawns isn't even this checkout's copy).
    These three now default to a path *derived from this file's own
    location* (``_REPO_ROOT``), so a fresh checkout anywhere is
    self-contained by construction. ``bin``/``solver_bin`` stay pointed at
    external, non-repo installs (MUQ-SAC standalone binary, FlameMaster) --
    those genuinely aren't part of this repo and have no repo-relative
    answer.
    """
    return {
        "bin": os.environ.get(
            "MSO_MUQSAC_BIN", "/home/krithika/MUQ-SAC/V3.0"),
        "solver_bin": os.environ.get(
            "MSO_FLAMEMASTER_BIN", "/home/krithika/FlameMaster/Bin/bin"),
        "yaml_writer": os.environ.get(
            "MSO_YAML_WRITER_SO",
            os.path.join(_REPO_ROOT, "src/MUQ-SAC/parallel_yaml_writer.so")),
        "samap_executable": os.environ.get(
            "MSO_SAMAP_EXECUTABLE", "PLACEHOLDER_SAMAP"),
        "jpdap_executable": os.environ.get(
            "MSO_JPDAP_EXECUTABLE", "PLACEHOLDER_JPDAP"),
        "SA_tool": os.environ.get(
            "MSO_SA_TOOL",
            os.path.join(_REPO_ROOT, "src/Sensitivity_Analysis/sens.py")),
        "SA_tool_3p": os.environ.get(
            "MSO_SA_TOOL_3P",
            os.path.join(_REPO_ROOT, "src/Sensitivity_Analysis/sens_3_params.py")),
    }


DEFAULT_CONFIG = {
    "project": {
        "name": "My_Study",
        "fuel_name": "H2",
        "fuel_formula": "H2",
        "output_base_dir": "outputs/My_Study",
    },
    "Type": {
        "optimization_type": "PRS",
        "Algorithm_type": "gradient-based",
        "Algorithm": "SLSQP",
    },
    "Counts": {
        "total_reactions": 10,
        "parallel_threads": 4,
        "targets_count": 20,
    },
    "SA": {"carbon_number": 0},
    "Bin": _default_bin_paths(),
    "Inputs": {
        "fileType": "chemkin",
        "fuelClass": "Mono",
        "fuel": {"a": "H2"},
        "global_reaction": "2H2+O2==2H2O",
        "AnalysisType": "reaction",
    },
    "Locations": {
        "mechanism": "PLACEHOLDER_MECHANISM.yaml",
        "Initial_pre_file": "PLACEHOLDER.PRE",
        "uncertainty_data": "PLACEHOLDER_uncertainty.xml",
        "thermo_file": "PLACEHOLDER_thermo.dat",
        "trans_file": "PLACEHOLDER_trans.dat",
        "targets": "PLACEHOLDER.target",
        "addendum": "PLACEHOLDER.add",
    },
    "StartProfilesData": {
        "Fls": {
            "Flame": "UnstretchedPremixed",
            "StartProfilesFile": "PLACEHOLDER_FLS_INIT",
            "CopyTo": "PLACEHOLDER_FLS_DEST",
            "fuel": {"key": "Mono", "From": "H2"},
            "oxidizer": {"key": "Mono", "From": "O2"},
            "bathGas": {"key": "Mono", "From": "N2"},
            "globalReaction": {"FromRxn": "2H2+O2==2H2O"},
            "units": {"pressure": "Pa", "temperature": "K", "concentration": "mol_fraction"},
        },
        "Flf": {
            "Flame": "UnstretchedPremixed",
            "StartProfilesFile": "PLACEHOLDER_FLF_INIT",
            "CopyTo": "PLACEHOLDER_FLF_DEST",
            "fuel": {"key": "Mono", "From": "H2"},
            "oxidizer": {"key": "Mono", "From": "O2"},
            "bathGas": {"key": "Mono", "From": "N2"},
            "globalReaction": {"FromRxn": "2H2+O2==2H2O"},
            "units": {"pressure": "Pa", "temperature": "K", "concentration": "mol_fraction"},
        },
    },
    "Stats": {
        "Design_of_PRS": "A-facto",
        "Order_of_PRS": 2,
        "Sampling_of_PRS": 4,
        "PRS_type": "Partial",
        "cut_off_percentage": 1,
        "MRE_criteria": 5.0,
        "Objective": "powerMeanWMRE",
        "pm_p": 0.1,
        "pm_anneal": True,
        "pm_p_start": 1.0,
        "omh_target_decade": 1.0,
        "pen_alpha": 0.9,
        "pen_K": 100.0,
        "dynamic_weight_freq": 50,
        "dynamic_weight_alpha": 0.2,
        "softmax_beta": 20.0,
        "softmax_anneal": True,
        "softmax_rho": 0.01,
        "num_generations": 20000,
        "outlier_retraining": True,
        "outlier_N_new": 200,
        "outlier_delta_fraction": 0.15,
        "outlier_seed": 42,
        "outlier_max_iter": 5,
        "outlier_target_fraction": 0.5,
        "outlier_sample_mode": "dm_global",
        "outlier_method": "sobol",
        "outlier_uns_cap": 256,
        "outlier_shuffle_factor": 2,
        "Weights": {"Tig": 1.0},
    },
    "RMIP": {
        "database": "project.db",
        "glossary": "species_smiles.csv",
        "mechanisms": [
            {"name": "Mech1", "path": "PLACEHOLDER_mech1.yaml", "format": "cantera_yaml"},
        ],
        "graph": {
            "layout": "spring", "out_dir": "outputs/graphs",
            "export_graphml": True, "export_figure": True, "figure_format": "png",
        },
        "graph3d": {"shell_gap": 2.0, "layer_gap": 1.0, "order": "alpha", "out_dir": "outputs/graphs/3d"},
        "comparison": {"tol_A": 0.01, "tol_n": 0.001, "tol_Ea": 100.0, "out_dir": "outputs/comparison"},
        "fusion": {"name": "Fused_Mech", "description": "", "uf_warn": 10.0, "out_dir": "outputs/fusion"},
        "benchmarking": {"sim_type": "IDT", "tol_T": 20.0, "tol_P": 0.5, "tol_phi": 0.05, "out_dir": "outputs/benchmarking"},
        "reduction": {
            "method": "DRG", "target_species": "H2,O2,H2O", "eps_max": 0.5,
            "T": 1200.0, "P": 1.0, "phi": 1.0, "sa_json": None, "out_dir": "outputs/reduction",
            "target_file": None,  # .target file (full or subset) target_species was derived from
        },
        "sa_analysis": {"fuel": "H2", "T": 1200.0, "P": 1.0, "phi": 1.0, "out_dir": "outputs/sa"},
        "unified_tree": {
            "mode": "anchored", "anchor_mechanism": "Mech1",
            "T_min": 500, "T_max": 2500, "dT": 20, "P_ref_atm": 1.0,
            "use_cantera_for_falloff": False, "out_dir": "outputs/unified",
        },
        "export": {
            "chemkin_path": "outputs/export/mechanism.inp",
            "yaml_path": "outputs/export/mechanism.yaml",
            "embed_uncertainty": True,
        },
    },
    "ForwardUQ": {
        "n_samples": 50000, "method": "sobol",
        "output_dir": "outputs/forward_uq",
        "plot_histogram": True, "plot_sobol": True, "ci_level": 0.95,
    },
}

_SECTION_COMMENTS = {
    "project":           "PROJECT METADATA",
    "Type":              "SECTION 1 — MUQ-SAC Optimization Type",
    "Counts":            "Resource counts",
    "SA":                "Sensitivity analysis metadata",
    "Bin":               "Tool binary / executable locations",
    "Inputs":            "Kinetics file format and fuel definition",
    "Locations":         "Input file locations for MUQ-SAC pipeline",
    "StartProfilesData": "Flame speed start profiles (only needed for LFS targets)",
    "Stats":             "Statistical / PRS settings",
    "RMIP":              "SECTION 2 — RMIP Multi-Mechanism Analysis",
    "ForwardUQ":         "SECTION 3 — Forward UQ Settings",
}


# ─────────────────────────────────────────────────────────────────────────────
# File generators
# ─────────────────────────────────────────────────────────────────────────────

def config_to_yaml(cfg: dict) -> str:
    lines = ["##" + "=" * 78,
             "#  RMIP + MUQ-SAC  Unified Project Configuration",
             f"#  Project: {cfg.get('project', {}).get('name', '')}",
             "#  Usage:",
             "#    python src/MUQ-SAC/run_script.py        target.opt",
             "#    python src/Sensitivity_Analysis/sens.py target.opt",
             "#    python graph_sa_run.py                  target.opt",
             "#    python forward_uq.py                    target.opt",
             "#    python rmip_cli.py <cmd> --config       target.opt",
             "##" + "=" * 78, ""]
    for key, value in cfg.items():
        comment = _SECTION_COMMENTS.get(key, "")
        if comment:
            lines += [f"# {'─'*74}", f"# {comment}", f"# {'─'*74}"]
        lines.append(yaml.dump({key: value}, default_flow_style=False, sort_keys=False))
    return "\n".join(lines)


def generate_target_file(rows: list, output_path: str):
    """Write a .target file from a list of data-point dicts."""
    lines = []
    for r in rows:
        dataset_id = r.get("dataset_id", "dataset_001")
        target_type = r.get("target_type", "Tig")
        sim = r.get("simulation", "Isochor Homo Reactor")
        meas = r.get("measurement_type", "timeDelay")
        ign_mode = r.get("ignition_mode", "reflected")
        flame_type = r.get("flame_type", "N/A")
        reactor_type = r.get("reactor_type", "N/A")
        fuel_type = r.get("fuel_type", "Mono")
        fuel_key = r.get("fuel_key", "a")
        fuel_species = r.get("fuel_species", "H2")
        fuel_xf = float(r.get("fuel_xf", 0.29))
        ox_species = r.get("oxidizer_species", "O2")
        ox_xf = float(r.get("ox_xf", 0.14))
        bg_key = r.get("bath_key", "bg1")
        bg_species = r.get("bath_species", "AR")
        bg_xf = float(r.get("bath_xf", 0.57))
        T = float(r.get("T", 1200.0))
        P = float(r.get("P", 1.0))
        phi_val = r.get("phi", "N/A")
        observed = float(r.get("observed", 100.0))
        deviation = float(r.get("deviation", observed * 0.1))
        data_weight = int(r.get("data_weight", 10))
        P_unit = r.get("P_unit", "atm")
        obs_unit = r.get("obs_unit", "us")

        fuel_str = f"x->{{'{fuel_key}': '{fuel_species}'}} = {{'{fuel_key}': {fuel_xf}}}"
        ox_str = f"x->{ox_species} = {ox_xf}"
        bg_str = f"x->{{'{bg_key}': '{bg_species}'}}={{'{bg_key}': {bg_xf}}}"
        units_str = f"{{'conc': 'mol', 'P': '{P_unit}', 'T': 'K', 'observed': '{obs_unit}'}}"

        line = (f"|{dataset_id}\t| target -- {target_type}"
                f"\t| simulation -- {sim}"
                f"\t| measurnment_type -- {meas}"
                f"\t|Ignition_mode -- {ign_mode}"
                f"\t| Flame_type -- {flame_type}"
                f"\t| Reactor_type -- {reactor_type}"
                f"\t| Fuel_type -- {fuel_type}"
                f"\t| Fuel -- {fuel_str}"
                f"\t| Oxidizer -- {ox_str}"
                f"\t| Bath_gas -- {bg_str}"
                f"\t|T -- {T}"
                f"\t| P -- {P}"
                f"\t| flow_rate -- N/A"
                f"\t|Phi -- {phi_val}"
                f"\t| observed -- {observed}"
                f"\t| obs_unit -- \t| deviation -- {deviation}"
                f"\t|data_weight -- {data_weight}"
                f"\t|units -- {units_str}")
        lines.append(line)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines) + "\n")


def parse_target_file_species(path: str) -> list:
    """Extract the unique Fuel/Oxidizer/Bath_gas species named in a .target file.

    Matches the pipe-delimited format written by generate_target_file() above:
        Fuel -- x->{'a': 'H2'} = {'a': 0.29}
        Oxidizer -- x->O2 = 0.14
        Bath_gas -- x->{'bg1': 'AR'}={'bg1': 0.57}
    Used by the Mechanism Reduction section to seed target_species from an
    existing (or freshly built) .target file instead of retyping species names.
    """
    text = Path(path).read_text()
    species = set()
    for m in re.finditer(r"Fuel\s*--\s*x->\{'[^']*':\s*'([^']+)'\}", text):
        species.add(m.group(1))
    for m in re.finditer(r"Oxidizer\s*--\s*x->(\S+?)\s*=", text):
        species.add(m.group(1))
    for m in re.finditer(r"Bath_gas\s*--\s*x->\{'[^']*':\s*'([^']+)'\}", text):
        species.add(m.group(1))
    return sorted(species)


def generate_addendum_file(datasets: list, output_path: str):
    """Write a .add YAML file from a list of dataset-config dicts.

    Field selection per target_type mirrors combustion_target_class.py's
    per-type addenda (see CLAUDE.md §7.16 / TARGET_TYPE_FIELDS above) — each
    type only gets the keys the backend actually reads for it.
    """
    content = {}
    for d in datasets:
        did = d.get("dataset_id", "dataset_001")
        cfg = {}
        cfg["solver"] = d.get("solver", "cantera")
        ttype = d.get("target_type", "Tig")

        def _f(key):
            v = d.get(key, "")
            return float(v) if v not in ("", None) else None

        def _i(key):
            v = d.get(key, "")
            return int(float(v)) if v not in ("", None) else None

        if ttype == "Fls":
            cfg["type"] = d.get("fls_type") or "phi"
            cfg["fuel"] = d.get("fls_fuel") or d.get("fuel_species", "H2")
        elif ttype in ("JSR", "PFR", "Flf"):
            if _f("residenceTime") is not None:
                cfg["residenceTime"] = _f("residenceTime")
            species = d.get("jsr_species") or d.get("flf_species", "")
            if species:
                cfg["species"] = species
            if ttype == "PFR":
                if _f("pfr_length") is not None:
                    cfg["pfr_length"] = _f("pfr_length")
                if _f("pfr_diameter") is not None:
                    cfg["pfr_diameter"] = _f("pfr_diameter")
                if _f("pfr_mdot") is not None:
                    cfg["pfr_mdot"] = _f("pfr_mdot")
                if _i("pfr_n_points") is not None:
                    cfg["pfr_n_points"] = _i("pfr_n_points")
            if str(d.get("flux_analysis", "")).lower() in ("yes", "true", "1"):
                cfg["flux_analysis"] = True
                if d.get("flux_element"):
                    cfg["flux_element"] = d["flux_element"]
        elif ttype == "RCM":
            if d.get("RCM_type"):
                cfg["RCM_type"] = d["RCM_type"]
            cfg["ign_delay_def"] = d.get("ign_delay_def", "OH*")
            cfg["ign_cond"] = d.get("ign_cond", "onset")
        elif ttype == "Flf_a":
            if d.get("ExpTempFile"):
                cfg["ExpTempFile"] = d["ExpTempFile"]
            if _f("flow_rate") is not None:
                cfg["flow_rate"] = _f("flow_rate")
        elif ttype == "Flw":
            if d.get("flw_length"):
                cfg["flw_length"] = _f("flw_length") or d["flw_length"]
            if d.get("flw_species"):
                cfg["flw_species"] = d["flw_species"]
            if d.get("flw_method"):
                cfg["flw_method"] = d["flw_method"]
        else:  # Tig (default)
            cfg["ign_delay_def"] = d.get("ign_delay_def", "OH*")
            cfg["ign_cond"] = d.get("ign_cond", "onset")
            cfg["specific_cond"] = d.get("specific_cond", "")
            mol_wt = d.get("mol_wt", "")
            if mol_wt:
                cfg["mol_wt"] = int(mol_wt)
            if str(d.get("BoundaryLayer", "")).lower() in ("yes", "true", "1"):
                cfg["BoundaryLayer"] = True

        max_sim_time = d.get("MaxSimulationTime", "")
        if max_sim_time:
            cfg["MaxSimulationTime"] = float(max_sim_time)
        content[did] = cfg
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(content, f, default_flow_style=False, sort_keys=False)


_GLOBAL_RXN_KNOWN_ELEMENTS = {"C", "H", "O", "N", "S"}


def derive_global_reaction(fuel_blend: list, oxidizer: str = "O2"):
    """Build a balanced global combustion reaction string from a fuel blend.

    fuel_blend: list of (species_name_or_formula, coeff, nu_o2) tuples — coeff is
    the stoichiometric coefficient already resolved by the caller (user-supplied
    or mole-fraction-derived), nu_o2 the per-mole-fuel O2 requirement from
    chem_data.compute_nu_o2(). Mirrors compute_nu_o2's own documented balance:
        CxHyOzNwSv + nu_O2*O2 -> x*CO2 + y/2*H2O + w/2*N2 + v*SO2
    (previous behaviour hardcoded CO2+H2O as products regardless of fuel
    composition, which is wrong for N-bearing fuels like NH3).

    Returns (reaction_str, confidence, note) where confidence is "high"/"low" —
    "low" means an element outside {C,H,O,N,S} was seen (halogens, metals, ...)
    or a fuel's formula couldn't be parsed at all; callers should treat "low"
    as a signal to confirm with the user rather than silently writing the guess.
    """
    from chem_data import parse_formula

    totals = {"C": 0.0, "H": 0.0, "N": 0.0, "S": 0.0}
    nu_total = 0.0
    lhs_parts = []
    confidence = "high"
    notes = []
    for sp, coeff, nu in fuel_blend:
        elements = parse_formula(sp)
        if not elements:
            confidence = "low"
            notes.append(f"could not parse element composition for '{sp}'")
        unknown = set(elements) - _GLOBAL_RXN_KNOWN_ELEMENTS
        if unknown:
            confidence = "low"
            notes.append(f"'{sp}' contains {sorted(unknown)}, not handled by this balancer")
        for el in ("C", "H", "N", "S"):
            totals[el] += coeff * elements.get(el, 0.0)
        nu_total += coeff * nu
        lhs_parts.append(sp if coeff == 1 else f"{coeff:.2f}{sp}")

    rhs_parts = []
    if totals["C"] > 1e-9:
        rhs_parts.append("CO2" if abs(totals["C"] - 1) < 1e-9 else f"{totals['C']:.2f}CO2")
    if totals["H"] > 1e-9:
        h2o = totals["H"] / 2.0
        rhs_parts.append("H2O" if abs(h2o - 1) < 1e-9 else f"{h2o:.2f}H2O")
    if totals["N"] > 1e-9:
        n2 = totals["N"] / 2.0
        rhs_parts.append("N2" if abs(n2 - 1) < 1e-9 else f"{n2:.2f}N2")
    if totals["S"] > 1e-9:
        rhs_parts.append("SO2" if abs(totals["S"] - 1) < 1e-9 else f"{totals['S']:.2f}SO2")

    if not rhs_parts:
        confidence = "low"
        notes.append("no recognizable combustion products (C/H/N/S) found in fuel blend")
        rhs_parts = ["CO2", "H2O"]

    rxn = "+".join(lhs_parts) + f"+{nu_total:.2f}{oxidizer}==" + "+".join(rhs_parts)
    return rxn, confidence, "; ".join(notes)


def _rmip_src_on_path():
    """Ensure src/ (containing the rmip package) is importable."""
    import sys as _sys, os as _os
    _src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "src")
    if _src not in _sys.path:
        _sys.path.insert(0, _src)


def translate_species_for_mechanism(species_name: str, target_glossary_path: str,
                                     master_glossary_path: str = None):
    """Translate an abstract fuel/species name into the name a SPECIFIC
    mechanism's own glossary uses for the same chemical species.

    Reuses RMIP's existing D1 species-identity system (InChIKey via RDKit,
    rmip.core.canonicalize) instead of a new mapping system: resolve
    species_name -> SMILES (via master_glossary_path if given, else
    FuelNormalizer's built-in table for common combustion fuels) -> InChIKey,
    then scan the target mechanism's own species_smiles.csv glossary for a
    matching InChIKey.

    Returns (translated_name, confidence, note):
      confidence == "high"  -> exact InChIKey match found in the target glossary,
                               translated_name is that mechanism's own species name.
      confidence == "low"   -> no SMILES could be resolved for species_name, or no
                               match was found in the target glossary; translated_name
                               falls back to the original species_name unchanged.
    """
    _rmip_src_on_path()
    from rmip.core.canonicalize import smiles_to_inchi
    from rmip.io.glossary_reader import load_glossary

    smiles = None
    if master_glossary_path and Path(master_glossary_path).exists():
        try:
            master_glossary = load_glossary(master_glossary_path)
            smiles = master_glossary.get(species_name.upper())
        except Exception:
            smiles = None
    if not smiles:
        smiles = FuelNormalizer.get_smiles(species_name)
    if not smiles:
        return species_name, "low", f"no SMILES known for '{species_name}' — cannot verify identity"

    _, inchi_key = smiles_to_inchi(smiles)
    if not inchi_key:
        return species_name, "low", f"could not derive an InChIKey for '{species_name}' ({smiles})"

    if not target_glossary_path or not Path(target_glossary_path).exists():
        return species_name, "low", f"no glossary supplied for target mechanism — cannot translate '{species_name}'"

    try:
        target_glossary = load_glossary(target_glossary_path)
    except Exception as e:
        return species_name, "low", f"could not read target glossary: {e}"

    for name, sp_smiles in target_glossary.items():
        _, sp_key = smiles_to_inchi(sp_smiles)
        if sp_key and sp_key == inchi_key:
            return name, "high", ""

    return species_name, "low", (
        f"no InChIKey match for '{species_name}' in the target mechanism's glossary — verify manually"
    )


def convert_mechanism_files(inp_path: str, thermo_path: str, trans_path: str,
                             out_dir: str, scanman_bin: str = None):
    """Convert a CHEMKIN mechanism (.inp + thermo + transport) into both a
    Cantera YAML (with transport embedded) and a FlameMaster .pre file.

    Deliberately calls ck2yaml directly rather than going through
    rmip.io.chemkin_writer.ChemkinWriter, which omits --transport per RMIP's
    D6 "transport out of scope" policy (correct for RMIP's own DB-facing
    exports) — MUQ-SAC's cantera_.py solver needs transport data embedded, so
    this is a separate, deliberately transport-inclusive path.

    scanman_bin may be a directory (containing ScanMan/ScanMan.exe) or a
    direct path to the executable; pass None/"" to skip .pre generation.

    Both tools are run in maximally-permissive mode (every flag that trades a
    hard-stop for a warning/relaxed-tolerance, without changing how the input
    is *parsed* — see inline comments for what was deliberately left off and
    why). Full stdout+stderr from both tools is always included in `errors`
    on failure — previously ScanMan's own diagnostic output was swallowed
    entirely, which made real content issues (e.g. an unrecognized species
    token, a non-ASCII byte in a thermo file) impossible to self-diagnose
    from the GUI.

    Returns (yaml_path, pre_path, errors) — either path is None if that half
    failed; errors is a list of human-readable messages. Never swallows
    failures silently — callers must check `errors`, not just the paths.
    """
    errors = []
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(inp_path).stem

    yaml_path = None
    ck2yaml_bin = shutil.which("ck2yaml") or "ck2yaml"
    yaml_out = out_dir / f"{stem}.yaml"
    cmd = [ck2yaml_bin, f"--input={inp_path}"]
    if thermo_path:
        cmd.append(f"--thermo={thermo_path}")
    if trans_path:
        cmd.append(f"--transport={trans_path}")
    cmd.append(f"--output={yaml_out}")
    # Real CHEMKIN mechanisms frequently have benign issues (e.g. duplicate
    # thermo entries for one species) that ck2yaml treats as hard errors by
    # default; --permissive is Cantera's own documented flag for tolerating
    # these (first entry wins) instead of aborting the whole conversion.
    cmd.append("--permissive")
    # --no-validate skips ck2yaml's own post-conversion `ct.Solution(yaml)`
    # round-trip check — a mechanism can have a YAML-valid-but-not-fully-
    # Cantera-clean quirk (e.g. a borderline thermo discontinuity) that would
    # otherwise abort an already-successful file write.
    cmd.append("--no-validate")
    # NOT added: --single-intermediate-temperature. This changes how the
    # LAST value on a species' first thermo line is interpreted (molecular
    # weight instead of the second break temperature) — it's a genuine format
    # switch, not a leniency knob, and silently corrupts normal two-Tmid
    # thermo data if turned on for a mechanism that doesn't use that
    # convention. If ck2yaml's stderr below mentions a thermo-parsing issue
    # tied to this, that's the flag to try manually on the CLI.
    # NOT added: --quiet (suppresses warnings we want to surface) or --debug
    # (only useful interactively; its extra verbosity is appended to `errors`
    # instead, via a second attempt, only if the first one fails).
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and yaml_out.exists():
            yaml_path = str(yaml_out)
        else:
            detail = (result.stderr or result.stdout or "").strip()
            # Retry once with --debug for a fuller diagnostic when the
            # permissive attempt still failed — pure diagnosis, not a
            # different parse mode, so it's safe to always try.
            debug_result = subprocess.run(cmd + ["--debug"], capture_output=True, text=True, timeout=120)
            debug_detail = (debug_result.stderr or debug_result.stdout or "").strip()
            if debug_detail and debug_detail != detail:
                detail = debug_detail
            errors.append(f"ck2yaml failed (code {result.returncode}): {detail[-2000:]}")
    except FileNotFoundError:
        errors.append("ck2yaml executable not found on PATH")
    except subprocess.TimeoutExpired:
        errors.append("ck2yaml timed out (> 120s)")
    except Exception as e:
        errors.append(f"ck2yaml error: {e}")

    pre_path = None
    if not scanman_bin:
        errors.append(".pre generation skipped: no solver bin directory given")
    else:
        scanman_path = Path(scanman_bin)
        if scanman_path.is_dir():
            candidate = scanman_path / "ScanMan"
            if not candidate.exists():
                candidate = scanman_path / "ScanMan.exe"
            scanman_path = candidate
        if not scanman_path.exists():
            errors.append(f"ScanMan not found at {scanman_bin}")
        elif not thermo_path or not Path(thermo_path).exists():
            errors.append(".pre generation skipped: thermo file missing")
        elif not trans_path or not Path(trans_path).exists():
            errors.append(".pre generation skipped: transport file missing")
        else:
            pre_out = out_dir / f"{stem}.pre"
            cmd = [
                str(scanman_path), "-i", inp_path, "-t", thermo_path, "-m", trans_path,
                "-f", "chemkin",
                "-E",       # never-consumed/produced species -> warning, not error
                "-c",       # skip forward/backward reaction consistency check and
                            # skip computing missing pressure-dependent Arrhenius
                            # constants — real permissiveness flag, not just output verbosity
                "-N", "0.05",   # cp discontinuity tolerance (default 1e-3) — already relaxed
                "-T", "0.01",   # element-conservation violation tolerance (default 1e-6)
                # NOT added: -Z. Despite being documented in --help ("tolerances
                # for ... default 1.0e-6"), passing -Z with a value makes
                # ScanMan's own arg parser fall through to printing usage
                # instead of running (confirmed empirically against this
                # ScanMan build, version 4.2.1) — it's not a working flag here.
                "-3sr",     # print third-body/species/reaction lists (diagnostic only)
                "-o", str(pre_out),
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode == 0 and pre_out.exists():
                    pre_path = str(pre_out)
                else:
                    # ScanMan writes its -o file (often empty) even on failure —
                    # remove the stub so a later existence-only check elsewhere
                    # doesn't mistake it for a real .pre file.
                    if pre_out.exists() and pre_out.stat().st_size == 0:
                        pre_out.unlink()
                    detail = (result.stdout or result.stderr or "").strip()
                    errors.append(f"ScanMan failed (code {result.returncode}): {detail[-2000:]}")
            except subprocess.TimeoutExpired:
                errors.append("ScanMan timed out (> 120s)")
            except FileNotFoundError:
                errors.append("ScanMan executable not found")
            except Exception as e:
                errors.append(f"ScanMan error: {e}")

    return yaml_path, pre_path, errors


def generate_uncertainty_xml(reactions: list, output_path: str) -> str:
    """Build a MUQ-SAC uncertainty XML file and return the string."""
    root = ET.Element("uncertainty")
    for i, rxn in enumerate(reactions):
        name = rxn.get("name", "H+O2<=>O+OH")
        # "no" is a required attribute of src/MUQ-SAC/Uncertainty.py's
        # `reaction.__init__` (`self.rIndex = str(Element.attrib["no"])`) --
        # this writer never emitted it, so every uncertainty XML this tab
        # ever produced raised KeyError('no') the moment Uncertainty.py
        # tried to read it back (found while wiring the Uncertainty
        # Generator GUI-split app). "no" is only ever used downstream as a
        # display/tag label (e.g. f"{rIndex}_A"), not as a mechanism lookup
        # key, so a stable 1-based sequence number is a correct, safe fix.
        rxn_el = ET.SubElement(root, "reaction", rxn=name, no=str(i + 1))
        # (Round-2 audit fix, B2) A blank <class> doesn't crash
        # Uncertainty.py's reaction.__init__ outright (self.classification
        # just becomes None, and the only reads of it compare against
        # "PLOG"/"PLOG-Duplicate"), but it's still wrong data -- every
        # reaction this writer ever produced silently lost its
        # classification. "Elementary" matches the convention already
        # established in src/rmip/tests/fixtures/h2_o2_crosscheck_unsrt.xml
        # (built specifically to work around this shipped file's gaps).
        ET.SubElement(rxn_el, "class").text = rxn.get("classification", "Elementary")
        rxn_type = rxn.get("type", "pressure_independent")
        ET.SubElement(rxn_el, "type").text = rxn_type
        # <perturbation_type> is read unconditionally at Uncertainty.py's
        # `reaction.__init__` (`if "factor" in self.perturbation_type:`) --
        # like "no" above, this writer never emitted it either, so the
        # attribute was simply never set and every reaction crashed with
        # AttributeError the moment __init__ reached that line. "arrhenius"
        # (full 3-parameter A/n/Ea, DesignMatrix.py's non-"factor" case) is
        # the correct default -- it matches sens_3_params.py's standard
        # 3-parameter scope, not the reduced 1-parameter A-factor-only mode.
        ET.SubElement(rxn_el, "perturbation_type").text = rxn.get("perturbation_type", "arrhenius")
        sub = ET.SubElement(rxn_el, "sub_type", name="forward")
        ET.SubElement(sub, "multiple").text = "False"
        ET.SubElement(sub, "branches").text = "N/A"
        ET.SubElement(sub, "pressure_limit").text = "low" if rxn_type == "pressure_dependent" else "N/A"
        ET.SubElement(sub, "common_temp").text = "N/A"
        ET.SubElement(sub, "temp_limit").text = "N/A"
        # Data type
        data_mode = rxn.get("data_mode", "constant;array")
        ET.SubElement(rxn_el, "data_type").text = data_mode
        # Temperatures
        temps = rxn.get("temperatures", "")
        if isinstance(temps, list):
            temps = ",".join(str(t) for t in temps)
        ET.SubElement(rxn_el, "temp").text = temps
        # Uncertainties
        unsrt = rxn.get("uncertainties", "")
        if isinstance(unsrt, list):
            unsrt = ",".join(str(u) for u in unsrt)
        ET.SubElement(rxn_el, "unsrt").text = unsrt

    raw = ET.tostring(root, encoding="unicode")
    pretty = parseString(raw).toprettyxml(indent="\t")
    # Fix XML declaration
    lines = pretty.split("\n")
    out = '<?xml version="1.0" encoding="UTF-8"?>\n' + "\n".join(lines[1:])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(out)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Theme application  (Task 1B)
# ─────────────────────────────────────────────────────────────────────────────

def _apply_theme(root: "tk.Tk"):
    """Apply the modern dark theme to the root window and all ttk widgets."""
    if not _HAS_TK:
        return
    root.configure(bg=PALETTE["bg"])
    style = ttk.Style(root)
    style.theme_use("clam")

    # ── Global widget defaults ─────────────────────────────────────────────
    style.configure(".",
        background=PALETTE["surface"],
        foreground=PALETTE["text"],
        fieldbackground=PALETTE["entry_bg"],
        bordercolor=PALETTE["border"],
        darkcolor=PALETTE["bg"],
        lightcolor=PALETTE["surface2"],
        troughcolor=PALETTE["bg"],
        selectbackground=PALETTE["accent"],
        selectforeground=PALETTE["text"],
        font=FONTS["body"],
        relief="flat",
        borderwidth=1,
    )

    # ── Frames ─────────────────────────────────────────────────────────────
    style.configure("TFrame",      background=PALETTE["surface"])
    style.configure("TLabelframe", background=PALETTE["surface"],
                    foreground=PALETTE["accent"], font=FONTS["body_bold"])
    style.configure("TLabelframe.Label", background=PALETTE["surface"],
                    foreground=PALETTE["accent"])

    # ── Labels ─────────────────────────────────────────────────────────────
    style.configure("TLabel",      background=PALETTE["surface"],  foreground=PALETTE["text"])
    style.configure("Dim.TLabel",  background=PALETTE["surface"],  foreground=PALETTE["text_dim"])
    style.configure("Header.TLabel", background=PALETTE["surface"],
                    foreground=PALETTE["accent"], font=FONTS["header"])
    style.configure("SubHeader.TLabel", background=PALETTE["surface"],
                    foreground=PALETTE["accent2"], font=FONTS["subheader"])
    style.configure("Section.TLabel", background=PALETTE["surface"],
                    foreground=PALETTE["text"], font=FONTS["section"])
    style.configure("Status.TLabel", background=PALETTE["bg"],
                    foreground=PALETTE["text_dim"], font=FONTS["status"])

    # ── Buttons ─────────────────────────────────────────────────────────────
    style.configure("TButton",
        background=PALETTE["accent"],
        foreground=PALETTE["text"],
        font=FONTS["body_bold"],
        padding=(8, 4),
        relief="flat",
        borderwidth=0,
    )
    style.map("TButton",
        background=[("active", PALETTE["accent2"]), ("pressed", PALETTE["bg"])],
        foreground=[("active", PALETTE["text"])],
    )
    style.configure("Small.TButton",
        background=PALETTE["surface2"],
        foreground=PALETTE["text_dim"],
        font=FONTS["small"],
        padding=(4, 2),
    )
    style.map("Small.TButton",
        background=[("active", PALETTE["accent"])],
        foreground=[("active", PALETTE["text"])],
    )
    style.configure("Danger.TButton",
        background=PALETTE["error"],
        foreground=PALETTE["text"],
        font=FONTS["small"],
        padding=(3, 1),
    )
    style.map("Danger.TButton",
        background=[("active", "#b91c1c")],
    )

    # ── Entries ─────────────────────────────────────────────────────────────
    style.configure("TEntry",
        fieldbackground=PALETTE["entry_bg"],
        foreground=PALETTE["text"],
        insertcolor=PALETTE["text"],
        bordercolor=PALETTE["border"],
        lightcolor=PALETTE["entry_bg"],
        darkcolor=PALETTE["entry_bg"],
    )
    style.map("TEntry",
        fieldbackground=[("focus", "#1f2937")],
        bordercolor=[("focus", PALETTE["accent"])],
    )

    # ── Combobox ────────────────────────────────────────────────────────────
    style.configure("TCombobox",
        fieldbackground=PALETTE["entry_bg"],
        foreground=PALETTE["text"],
        background=PALETTE["surface"],
        arrowcolor=PALETTE["accent"],
        bordercolor=PALETTE["border"],
    )
    style.map("TCombobox",
        fieldbackground=[("readonly", PALETTE["entry_bg"]), ("focus", "#1f2937")],
        foreground=[("readonly", PALETTE["text"])],
        bordercolor=[("focus", PALETTE["accent"])],
    )
    root.option_add("*TCombobox*Listbox.background", PALETTE["entry_bg"])
    root.option_add("*TCombobox*Listbox.foreground", PALETTE["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", PALETTE["accent"])

    # ── Notebook ────────────────────────────────────────────────────────────
    style.configure("TNotebook",
        background=PALETTE["bg"],
        tabmargins=[2, 4, 0, 0],
        borderwidth=0,
    )
    style.configure("TNotebook.Tab",
        background=PALETTE["surface2"],
        foreground=PALETTE["text_dim"],
        font=FONTS["tab"],
        padding=[12, 6],
        borderwidth=0,
        relief="flat",
    )
    style.map("TNotebook.Tab",
        background=[("selected", PALETTE["surface"]), ("active", PALETTE["surface2"])],
        foreground=[("selected", PALETTE["accent"]), ("active", PALETTE["text"])],
        padding=[("selected", [14, 7])],
    )

    # ── Scrollbar ────────────────────────────────────────────────────────────
    style.configure("TScrollbar",
        background=PALETTE["surface2"],
        troughcolor=PALETTE["bg"],
        arrowcolor=PALETTE["text_dim"],
        borderwidth=0,
        relief="flat",
    )
    style.map("TScrollbar",
        background=[("active", PALETTE["accent"])],
    )

    # ── Separator ────────────────────────────────────────────────────────────
    style.configure("TSeparator", background=PALETTE["border"])

    # ── Canvas / scrolled frames ─────────────────────────────────────────────
    root.option_add("*Canvas.background", PALETTE["surface"])
    root.option_add("*Text.background",   PALETTE["entry_bg"])
    root.option_add("*Text.foreground",   PALETTE["text"])
    root.option_add("*Text.font",         "{%s} %d" % (FONTS['mono'][0], FONTS['mono'][1]))


# ─────────────────────────────────────────────────────────────────────────────
# CLI mode
# ─────────────────────────────────────────────────────────────────────────────

def run_cli(args):
    if args.load and Path(args.load).exists():
        with open(args.load) as f:
            cfg = yaml.safe_load(f)
        print(f"Loaded: {args.load}")
    else:
        cfg = deepcopy(DEFAULT_CONFIG)
        if args.name:
            cfg["project"]["name"] = args.name
        if args.fuel:
            cfg["project"]["fuel_name"] = args.fuel
            cfg["Inputs"]["fuel"]["a"] = args.fuel
        if args.output:
            cfg["project"]["output_base_dir"] = args.output
    out_path = args.out or "target.opt"
    text = config_to_yaml(cfg)
    with open(out_path, "w") as f:
        f.write(text)
    print(f"Written: {out_path}")


# ─────────────────────────────────────────────────────────────────────────────
# GUI
# ─────────────────────────────────────────────────────────────────────────────

class App:
    """Main GUI application."""

    def __init__(self, root: "tk.Tk", initial_cfg: dict = None):
        self.root = root
        self.root.title("RMIP + MUQ-SAC  ·  Configuration Generator")
        self.root.geometry("1100x820")
        self.cfg = deepcopy(initial_cfg or DEFAULT_CONFIG)

        # Phase 4: Auto-save and tab locking
        self._checkpoint_path = _load_gui_settings().get("checkpoint_path")
        self._autosave_mgr = AutoSaveManager(self.root, self._save_checkpoint_silent, interval_ms=5000)
        self._tab_locker = None  # Initialized after notebook is created
        self._fuel_registry = {}  # {fuel_name: {formula, aliases, mw, nu_o2}}

        # dynamic row lists
        self._mech_rows = []
        self._target_rows = []          # [(row_frame, {key: StringVar}, abs_df_index)] for the CURRENT PAGE only
        self._target_df = pd.DataFrame(columns=_TARGET_ROW_COLUMNS)  # full dataset backing the grid
        self._target_page_size = 20
        self._target_page_idx = 0
        self._red_autoloaded = False     # guards the Mechanism Reduction auto-populate (Phase 7)
        self._add_rows = []
        self._xml_rows = []
        self._mech_workflow = tk.StringVar(
            value=self.cfg.get("RMIP", {}).get("mech_workflow", "one_at_a_time"))

        # SA-condition vars: shared between the Reaction Screening tab (which
        # runs the actual SA) and the RMIP Analysis tab (which just persists
        # these into the saved config) — created once here since Reaction
        # Screening now builds earlier in the tab sequence than RMIP Analysis.
        _sa = self.cfg.get("RMIP", {}).get("sa_analysis", {})
        self._sa_fuel = tk.StringVar(value=_sa.get("fuel", "H2"))
        self._sa_T = tk.StringVar(value=str(_sa.get("T", 1200.0)))
        self._sa_P = tk.StringVar(value=str(_sa.get("P", 1.0)))
        self._sa_phi = tk.StringVar(value=str(_sa.get("phi", 1.0)))
        self._sa_out = tk.StringVar(value=_sa.get("out_dir", "outputs/sa"))

        # Try to restore autosave checkpoint on startup
        self._try_restore_autosave()

        self._build_ui()

        # Phase 4: Setup window close handler for final save
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Task 1E: Menu bar ─────────────────────────────────────────────────
        menubar = tk.Menu(self.root, bg=PALETTE["surface"], fg=PALETTE["text"],
                          activebackground=PALETTE["accent"], activeforeground=PALETTE["text"],
                          relief="flat", bd=0)

        # File menu
        m_file = tk.Menu(menubar, tearoff=0,
                         bg=PALETTE["surface"], fg=PALETTE["text"],
                         activebackground=PALETTE["accent"], activeforeground=PALETTE["text"])
        m_file.add_command(label="Load target.opt …",    command=self._load_opt,       accelerator="Ctrl+O")
        m_file.add_command(label="Save target.opt …",    command=self._save_opt,       accelerator="Ctrl+S")
        m_file.add_command(label="Save As …",            command=self._save_opt)
        m_file.add_separator()
        m_file.add_command(label="Save Checkpoint",      command=lambda: self._save_checkpoint())
        m_file.add_command(label="Save Checkpoint As …", command=lambda: self._save_checkpoint_as())
        m_file.add_command(label="Restore Checkpoint …", command=lambda: self._restore_checkpoint())
        m_file.add_separator()
        m_file.add_command(label="Quit",                 command=self.root.quit,        accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=m_file)

        # Insert menu
        m_ins = tk.Menu(menubar, tearoff=0,
                        bg=PALETTE["surface"], fg=PALETTE["text"],
                        activebackground=PALETTE["accent"], activeforeground=PALETTE["text"])
        m_ins.add_command(label="Add target row",           command=self._add_trow)
        m_ins.add_command(label="Add addendum entry",       command=self._add_arow)
        m_ins.add_command(label="Add uncertainty reaction", command=self._add_xrow)
        m_ins.add_separator()
        m_ins.add_command(label="Import CSV into Target Builder …", command=self._import_target_csv)
        m_ins.add_command(label="Import XML dataset (NH3/RKD) …",   command=self._import_xml_dataset)
        menubar.add_cascade(label="Insert", menu=m_ins)

        # Tools menu
        m_tools = tk.Menu(menubar, tearoff=0,
                          bg=PALETTE["surface"], fg=PALETTE["text"],
                          activebackground=PALETTE["accent"], activeforeground=PALETTE["text"])
        m_tools.add_command(label="Generate & Preview target.opt", command=self._preview)
        m_tools.add_separator()
        m_tools.add_command(label="Generate .target file",  command=self._generate_target)
        m_tools.add_command(label="Generate .add file",     command=self._generate_add)
        m_tools.add_command(label="Generate .xml file",     command=self._generate_xml)
        m_tools.add_separator()
        m_tools.add_command(label="Launch Backend Job in Terminal …", command=self._open_run_dialog)
        m_tools.add_command(label="Mechanism Diagnostics …",          command=self._open_diagnostics_dialog)
        m_tools.add_separator()
        m_tools.add_command(label="MW / Stoichiometry Calculator …", command=self._open_mw_dialog)
        m_tools.add_separator()
        m_tools.add_command(label="Generate LaTeX target tables …", command=self._open_latex_tables_dialog)
        m_tools.add_command(label="Read Chemkin Pro CSV (ckcsv) …",command=self._open_ckcsv_viewer)
        menubar.add_cascade(label="Tools", menu=m_tools)

        # Notebook menu (Task 6A/6B)
        m_nb = tk.Menu(menubar, tearoff=0,
                       bg=PALETTE["surface"], fg=PALETTE["text"],
                       activebackground=PALETTE["accent"], activeforeground=PALETTE["text"])
        m_nb.add_command(label="PDF Q&A Notebook …",     command=self._open_pdf_notebook)
        m_nb.add_command(label="Plot Digitizer …",       command=self._open_plot_digitizer)
        m_nb.add_command(label="Extract PDF Tables …",   command=self._open_pdf_table_panel)
        m_nb.add_command(label="Symbolic Regression …",  command=self._open_symreg_panel)
        menubar.add_cascade(label="Notebook", menu=m_nb)

        # LaTeX menu (Task 6C)
        m_latex = tk.Menu(menubar, tearoff=0,
                          bg=PALETTE["surface"], fg=PALETTE["text"],
                          activebackground=PALETTE["accent"], activeforeground=PALETTE["text"])
        m_latex.add_command(label="New LaTeX project …",        command=self._latex_new_project)
        m_latex.add_command(label="Compile project (PDF) …",   command=self._latex_compile)
        m_latex.add_command(label="Append section …",           command=self._latex_append_section)
        m_latex.add_command(label="Import figure …",            command=self._latex_import_figure)
        m_latex.add_command(label="Add collaborator …",         command=self._latex_add_collab)
        m_latex.add_separator()
        m_latex.add_command(label="Append MSO report section…", command=self._append_mso_report_section)
        menubar.add_cascade(label="LaTeX", menu=m_latex)

        # Help menu
        m_help = tk.Menu(menubar, tearoff=0,
                         bg=PALETTE["surface"], fg=PALETTE["text"],
                         activebackground=PALETTE["accent"], activeforeground=PALETTE["text"])
        m_help.add_command(label="Guided tour (Next →)", command=self._start_tour)
        m_help.add_command(label="About RMIP + MUQ-SAC",
                           command=lambda: messagebox.showinfo(
                               "About", "RMIP + MUQ-SAC Unified GUI\n"
                               "Version: 2026-07 batch-1\n"
                               "Owner: KP (IIT Madras, TCL)\n"
                               "Supervisor: Dr. Krithika Narayanaswamy"))
        menubar.add_cascade(label="Help", menu=m_help)

        self.root.config(menu=menubar)
        # Keyboard shortcuts
        self.root.bind("<Control-o>", lambda e: self._load_opt())
        self.root.bind("<Control-s>", lambda e: self._save_opt())
        self.root.bind("<Control-q>", lambda e: self.root.quit())

        # ── Toolbar (quick-save bar) ───────────────────────────────────────
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=8, pady=4)
        for lbl, cmd, tip in [
            ("📂 Load target.opt", self._load_opt, "Load an existing target.opt file from disk"),
            ("💾 Save", self._save_opt, "Save the current configuration to target.opt"),
            ("▶ Preview", self._preview, "Generate and preview the target.opt text"),
        ]:
            btn = ttk.Button(toolbar, text=lbl, command=cmd)
            btn.pack(side=tk.LEFT, padx=3)
            self._hoverable(btn, tip)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Label(toolbar, text="Quick save:").pack(side=tk.LEFT)
        self._quick_path = tk.StringVar(value="target.opt")
        ttk.Entry(toolbar, textvariable=self._quick_path, width=30).pack(side=tk.LEFT, padx=2)
        quick_btn = ttk.Button(toolbar, text="→ Quick Save", command=self._quick_save)
        quick_btn.pack(side=tk.LEFT, padx=2)
        self._hoverable(quick_btn, "Save target.opt directly to the path shown to the left")
        # Thread cap indicator
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        try:
            from chem_data import thread_cap
            _cap = thread_cap()
        except ImportError:
            _cap = max((os.cpu_count() or 4) - 5, 1)
        ttk.Label(toolbar, text=f"CPU cap: {_cap} threads",
                  foreground=PALETTE["text_dim"]).pack(side=tk.LEFT, padx=4)

        # ── Notebook ──────────────────────────────────────────────────────
        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self._nb = nb
        self._num_tabs = 14  # keep in sync with the tab-building calls just below
        self._red_conditions = []  # list[SimCondition], set by the reduction subset-confirm flow

        # Task 7: file-producing tabs (Targets/Addendum/Uncertainty XML) now come
        # BEFORE "Files & Paths" so the user builds those files before being asked
        # to point at their locations — "Files & Paths" becomes a confirmation
        # step, pre-filled from what was just generated.
        self._tab_project(nb)
        self._tab_mechanisms(nb)
        self._tab_experimental_data(nb)  # merged Experimental Data + Targets (was 2 tabs)
        self._tab_target_workbench(nb)   # curate the .target/.add just built, before Addendum
        self._tab_addendum_builder(nb)
        self._tab_reaction_screening(nb)
        self._tab_xml_builder(nb)
        self._tab_locations(nb)
        self._tab_optimization(nb)
        self._tab_rmip_analysis(nb)
        self._tab_forwarduq(nb)
        self._tab_so_compiler(nb)
        self._tab_preview(nb)
        # Appended LAST (index 13), deliberately not inserted mid-sequence --
        # a read-only viewer with no bearing on the config-building flow
        # above, kept out of the way of any tab-index churn there.
        self._tab_project_viewer(nb)

        # Phase 4: Initialize tab locking manager
        self._tab_locker = TabLockingManager(nb, 14)
        self._tab_locker.set_status_callback(lambda msg: self._status.set(msg))
        self._tab_locker.set_validator(self._validate_tab)
        self._tab_locker.update_display()

        # Phase 4: BIND notebook tab change event to enforce locking
        nb.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)

        # ── Status bar ────────────────────────────────────────────────────
        status = ttk.Frame(self.root)
        status.pack(side=tk.BOTTOM, fill=tk.X)
        self._status = tk.StringVar(value="Ready.  |  Auto-save every 5s.  Hover ⓘ for help.")
        ttk.Label(status, textvariable=self._status, anchor=tk.W,
                  style="Status.TLabel", relief=tk.SUNKEN).pack(fill=tk.X, padx=4)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _add_tab_buttons(self, outer_frame, tab_index: int):
        """Add Next/Previous buttons to bottom of a tab (outside scrollable area)."""
        btn_frame = ttk.Frame(outer_frame)
        btn_frame.pack(fill=tk.X, padx=12, pady=8, side=tk.BOTTOM)

        if tab_index > 0:
            ttk.Button(btn_frame, text="◀ Previous", command=lambda: self._prev_tab(tab_index)).pack(side=tk.LEFT, padx=4)

        # Spacer
        ttk.Label(btn_frame, text="").pack(side=tk.LEFT, expand=True)

        if tab_index < self._num_tabs - 1:
            ttk.Button(btn_frame, text="Next ▶", command=lambda: self._next_tab(tab_index)).pack(side=tk.RIGHT, padx=4)

    @staticmethod
    def _scrolled(parent) -> ttk.Frame:
        """Scrollable frame helper."""
        canvas = tk.Canvas(parent, borderwidth=0, background=PALETTE["surface"])
        vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = ttk.Frame(canvas)
        win_id = canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))

        def _on_mousewheel(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_wheel(_e):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel)
            canvas.bind_all("<Button-5>", _on_mousewheel)

        def _unbind_wheel(_e):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)
        return inner

    # ── Task 1D: single reusable click-ⓘ popover ────────────────────────────
    # Only one popover exists at a time; dismiss on outside click or Esc.

    def _show_tip(self, anchor_widget, text: str):
        """Show (or toggle) the single shared info popover near anchor_widget."""
        # If already open for the same widget, close it
        if getattr(self, "_tip_win", None):
            try:
                self._tip_win.destroy()
            except Exception:
                pass
            self._tip_win = None
            if getattr(self, "_tip_anchor", None) is anchor_widget:
                self._tip_anchor = None
                return
        # Build popover
        tip = tk.Toplevel(self.root)
        tip.wm_overrideredirect(True)
        tip.attributes("-topmost", True)
        # Position just below the anchor widget
        x = anchor_widget.winfo_rootx()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 4
        tip.wm_geometry(f"+{x}+{y}")
        frame = tk.Frame(tip, background=PALETTE["tip_bg"],
                         highlightbackground=PALETTE["accent"], highlightthickness=1)
        frame.pack()
        tk.Label(frame, text=text, background=PALETTE["tip_bg"],
                 foreground=PALETTE["tip_fg"], font=FONTS["tip"],
                 wraplength=380, justify=tk.LEFT, padx=10, pady=8).pack()
        self._tip_win = tip
        self._tip_anchor = anchor_widget
        # Dismiss on outside click or Escape
        tip.bind("<Escape>", lambda e: self._close_tip())
        self.root.bind("<Button-1>", self._on_root_click, add="+")

    def _close_tip(self):
        if getattr(self, "_tip_win", None):
            try:
                self._tip_win.destroy()
            except Exception:
                pass
            self._tip_win = None
            self._tip_anchor = None

    def _on_root_click(self, event):
        """Close popover when the user clicks anywhere outside it."""
        tip = getattr(self, "_tip_win", None)
        if tip:
            try:
                wx, wy = tip.winfo_rootx(), tip.winfo_rooty()
                ww, wh = tip.winfo_width(), tip.winfo_height()
                if not (wx <= event.x_root <= wx + ww and wy <= event.y_root <= wy + wh):
                    self._close_tip()
            except Exception:
                self._close_tip()

    def _hoverable(self, widget, text: str):
        """Show `text` in the status bar on mouse-over; restore 'Ready.' on leave.

        Used for icon-only controls (toolbar buttons, row-delete '✕' buttons)
        where there's no room for a persistent text label.
        """
        widget.bind("<Enter>", lambda e: self._status.set(text))
        widget.bind("<Leave>", lambda e: self._status.set("Ready.  |  Auto-save every 5s.  Hover ⓘ for help."))
        return widget

    def _remove_row_button(self, parent, callback, tip="Remove this row"):
        """Small 'x' delete button with a consistent hover tooltip (status bar)."""
        btn = ttk.Button(parent, text="✕", width=3, style="Danger.TButton", command=callback)
        self._hoverable(btn, tip)
        return btn

    def _choose_directory(self, initial: str = "", title: str = None) -> str:
        """Directory chooser that also offers to create a new subfolder.

        Native Tk's askdirectory doesn't reliably expose "create new folder"
        on Linux, so after the user picks a base directory we optionally
        prompt for a subfolder name and create it with os.makedirs.
        """
        kwargs = {"initialdir": initial} if initial else {}
        if title:
            kwargs["title"] = title
        base = filedialog.askdirectory(**kwargs)
        if not base:
            return ""
        if messagebox.askyesno("Create subfolder?",
                                f"Create a new subfolder inside:\n{base}\n\n"
                                "(Choose 'No' to use this folder as-is.)"):
            name = simpledialog.askstring("New Folder", "Folder name:")
            if name:
                new_path = os.path.join(base, name)
                os.makedirs(new_path, exist_ok=True)
                return new_path
        return base

    def _field(self, parent, label: str, var: "tk.Variable", width=38,
               choices=None, browse_file=False, browse_dir=False, tip="", on_select=None,
               editable=False):
        """Standard label + entry/combobox row with optional ⓘ info badge.

        on_select: optional callback(picked_path) called after a file/dir is selected.
        editable: when choices is set, allow typing a value not in the list
                  instead of forcing state="readonly" (e.g. a custom algorithm name).
        """
        f = ttk.Frame(parent)
        f.pack(fill=tk.X, padx=12, pady=2)
        lbl = ttk.Label(f, text=label, width=30, anchor=tk.W)
        lbl.pack(side=tk.LEFT)
        if choices:
            w = ttk.Combobox(f, textvariable=var, values=choices, width=width,
                              state="normal" if editable else "readonly")
        else:
            w = ttk.Entry(f, textvariable=var, width=width)
        w.pack(side=tk.LEFT)
        if browse_file:
            def browse_file_and_callback():
                result = filedialog.askopenfilename()
                if result:
                    var.set(result)
                    if on_select:
                        on_select(result)
                else:
                    result = var.get()
            ttk.Button(f, text="…", width=3, style="Small.TButton",
                       command=browse_file_and_callback
                       ).pack(side=tk.LEFT, padx=2)
        if browse_dir:
            def browse_dir_and_callback():
                result = self._choose_directory(initial=var.get())
                if result:
                    var.set(result)
                    if on_select:
                        on_select(result)
            ttk.Button(f, text="…", width=3, style="Small.TButton",
                       command=browse_dir_and_callback
                       ).pack(side=tk.LEFT, padx=2)
        if tip:
            btn = tk.Label(f, text=" ⓘ ", foreground=PALETTE["accent"],
                           background=PALETTE["surface"], font=FONTS["body_bold"],
                           cursor="hand2")
            btn.pack(side=tk.LEFT, padx=(4, 0))
            btn.bind("<Button-1>", lambda e, t=tip, b=btn: self._show_tip(b, t))
        return f

    @staticmethod
    def _section(parent, title: str):
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(parent, text=title, font=FONTS["section"]).pack(anchor=tk.W, padx=12)

    # ── Tab: Project ──────────────────────────────────────────────────────────

    def _tab_project(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="Project")
        f = self._scrolled(outer)

        ttk.Label(f, text="Project Metadata", font=FONTS["header"]).pack(anchor=tk.W, padx=12, pady=8)
        p = self.cfg.setdefault("project", {})
        # Phase 4: Use traced vars for auto-save on field change
        self._proj_name = self._make_traced_var(p.get("name", "My_Study"))
        self._proj_fuel = self._make_traced_var(p.get("fuel_name", "H2"))
        self._proj_formula = self._make_traced_var(p.get("fuel_formula", "H2"))
        self._proj_outdir = self._make_traced_var(p.get("output_base_dir", "outputs/My_Study"))
        self._field(f, "Project name", self._proj_name, tip="Short name for output folder naming")

        # Task 3: fuel identity is defined once, in the "Files & Paths" fuel-blend
        # table — this is a read-only summary, not another place to type it.
        self._proj_fuel_summary = tk.StringVar(value="(no fuel defined yet — add one in 'Files & Paths')")
        fuel_row = ttk.Frame(f)
        fuel_row.pack(fill=tk.X, padx=12, pady=2)
        ttk.Label(fuel_row, text="Primary fuel", width=30, anchor=tk.W).pack(side=tk.LEFT)
        ttk.Label(fuel_row, textvariable=self._proj_fuel_summary,
                  style="Dim.TLabel").pack(side=tk.LEFT)
        jump_btn = ttk.Button(fuel_row, text="Edit in Files & Paths →", style="Small.TButton",
                              command=lambda: self._select_tab_by_text("Files & Paths"))
        jump_btn.pack(side=tk.LEFT, padx=8)
        self._hoverable(jump_btn, "Fuel species/blend are defined once, in the 'Files & Paths' tab")

        self._field(f, "Output base directory", self._proj_outdir, browse_dir=True)

        self._section(f, "Optimization Type")
        t = self.cfg.setdefault("Type", {})
        self._opt_type = self._make_traced_var(t.get("optimization_type", "PRS"))
        self._alg_type = self._make_traced_var(t.get("Algorithm_type", "gradient-based"))
        self._alg = self._make_traced_var(t.get("Algorithm", "SLSQP"))
        self._field(f, "Optimization type", self._opt_type,
                    choices=["PRS", "SAC", "direct"],
                    tip="PRS = Polynomial Response Surface; SAC = Sampling of Arrhenius Curves")
        self._field(f, "Algorithm type", self._alg_type,
                    choices=list(ALGORITHM_TYPE_GROUPS.keys()), editable=True,
                    tip=_HELP["alg_type"])
        self._field(f, "Algorithm", self._alg,
                    choices=list(KNOWN_ALGORITHMS.keys()), editable=True,
                    tip=_HELP["algorithm"] + "\n\n" +
                        "\n".join(f"{k}: {v}" for k, v in KNOWN_ALGORITHMS.items()))

        self._section(f, "Computational Resources")
        c = self.cfg.setdefault("Counts", {})
        self._n_rxn = self._make_traced_var(str(c.get("total_reactions", 10)))
        self._n_thr = self._make_traced_var(str(c.get("parallel_threads", 4)))
        self._n_tar = self._make_traced_var(str(c.get("targets_count", 20)))
        self._carbon_n = self._make_traced_var(str(self.cfg.get("SA", {}).get("carbon_number", 0)))
        self._field(f, "Total reactions (SA study)", self._n_rxn,
                    tip="Number of reactions selected by sensitivity analysis for optimization")
        self._field(f, "Parallel threads", self._n_thr)
        self._field(f, "Targets count (data points used)", self._n_tar)
        self._field(f, "Carbon number (SA grouping, 0=H2/CO)", self._carbon_n)

        self._add_tab_buttons(outer, 0)

    # ── Tab: File Locations ───────────────────────────────────────────────────

    def _tab_locations(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="Files & Paths")
        f = self._scrolled(outer)

        ttk.Label(f, text="MUQ-SAC Input File Locations",
                  font=FONTS["header"]).pack(anchor=tk.W, padx=12, pady=8)

        self._section(f, "Fuel / Reaction Setup")
        inp = self.cfg.setdefault("Inputs", {})
        lo = self.cfg.setdefault("Locations", {})
        self._inp_filetype = self._make_traced_var(inp.get("fileType", "chemkin"))
        self._inp_rxn     = self._make_traced_var(inp.get("global_reaction", "2H2+O2==2H2O"))
        self._inp_analysis = self._make_traced_var(inp.get("AnalysisType", "reaction"))
        self._field(f, "File type (mechanism format)", self._inp_filetype,
                    choices=["chemkin", "FlameMaster"])
        self._field(f, "Analysis type", self._inp_analysis,
                    choices=["reaction", "thermo"])
        self._field(f, "Global reaction", self._inp_rxn, width=52,
                    tip=_HELP["global_rxn"])

        # ── Task 2A: Multi-fuel blend rows ──────────────────────────────
        fuel_hdr = ttk.Frame(f)
        fuel_hdr.pack(fill=tk.X, padx=12, pady=(8, 0))
        ttk.Label(fuel_hdr, text="Fuel species blend",
                  font=FONTS["section"]).pack(side=tk.LEFT)
        ttk.Button(fuel_hdr, text="+ Add fuel", style="Small.TButton",
                   command=self._add_fuel_row).pack(side=tk.LEFT, padx=8)
        mw_btn = ttk.Button(fuel_hdr, text="MW Calc ⓘ", style="Small.TButton",
                            command=self._open_mw_dialog)
        mw_btn.pack(side=tk.LEFT, padx=2)
        self._hoverable(mw_btn, "Open the molecular-weight / stoichiometry calculator")
        recalc_btn = ttk.Button(fuel_hdr, text="Recalc O₂", style="Small.TButton",
                                command=self._auto_fill_o2)
        recalc_btn.pack(side=tk.LEFT, padx=2)
        self._hoverable(recalc_btn, "Recompute stoichiometric O2 and MW for all fuel rows below")

        col_hdr = ttk.Frame(f)
        col_hdr.pack(fill=tk.X, padx=12, pady=(2, 0))
        for col, w in [("Key (a/b/c…)", 10), ("Species name", 16),
                       ("Mole fraction", 12), ("Global rxn coeff", 14),
                       ("MW (g/mol)", 10), ("nu_O2", 8)]:
            ttk.Label(col_hdr, text=col, width=w, relief=tk.RIDGE,
                      anchor=tk.CENTER, font=FONTS["small"]).pack(side=tk.LEFT)

        self._fuel_container = ttk.Frame(f)
        self._fuel_container.pack(fill=tk.X, padx=12)
        self._fuel_rows: list = []   # list of (key_v, sp_v, xf_v, coeff_v, mw_v, nu_v, row_frame)

        # Populate from loaded config
        saved_fuel = inp.get("fuel", {"a": "H2"})
        saved_coeffs = inp.get("fuel_coeffs", {})
        saved_mw     = inp.get("fuel_mw", {})
        saved_nu     = inp.get("fuel_nu_o2", {})
        for key, species in saved_fuel.items():
            self._add_fuel_row(key=key, species=str(species),
                               coeff=str(saved_coeffs.get(key, "")),
                               mw=str(saved_mw.get(key, "")),
                               nu=str(saved_nu.get(key, "")))
        if not self._fuel_rows:
            self._add_fuel_row("a", "H2", "0.29", "2", "", "")

        self._section(f, "Primary Input Files")
        self._loc_mech = self._make_traced_var(lo.get("mechanism", ""))
        self._loc_pre = self._make_traced_var(lo.get("Initial_pre_file", ""))
        self._loc_unsrt = self._make_traced_var(lo.get("uncertainty_data", ""))
        self._loc_thermo = self._make_traced_var(lo.get("thermo_file", ""))
        self._loc_trans = self._make_traced_var(lo.get("trans_file", ""))
        self._loc_targets = self._make_traced_var(lo.get("targets", ""))
        self._loc_add = self._make_traced_var(lo.get("addendum", ""))
        self._field(f, "Mechanism file (.yaml/.inp)", self._loc_mech,
                    browse_file=True, tip="Primary mechanism for MUQ-SAC optimization",
                    on_select=self._auto_convert_mechanism)
        self._field(f, "PRE file (FlameMaster only)", self._loc_pre, browse_file=True)
        self._field(f, "Uncertainty XML (.xml)", self._loc_unsrt,
                    browse_file=True, tip="Auto-filled after generating one in the 'Uncertainty XML' tab "
                                         "(earlier in the tab order). Browse here only to point at a "
                                         "pre-existing file instead.")
        self._field(f, "Thermo data file (.dat)", self._loc_thermo, browse_file=True)
        self._field(f, "Transport data file (.dat)", self._loc_trans, browse_file=True)
        self._field(f, "Targets file (.target)", self._loc_targets,
                    browse_file=True, tip="Auto-filled after generating one in the 'Targets' tab "
                                         "(earlier in the tab order). Browse here only to point at a "
                                         "pre-existing file instead.")
        self._field(f, "Addendum file (.add)", self._loc_add,
                    browse_file=True, tip="Auto-filled after generating one in the 'Addendum' tab "
                                         "(earlier in the tab order). Browse here only to point at a "
                                         "pre-existing file instead.")

        self._section(f, "Executable Paths")
        b = self.cfg.setdefault("Bin", {})
        self._bin_muqsac = self._make_traced_var(b.get("bin", ""))
        self._bin_solver = self._make_traced_var(b.get("solver_bin", ""))
        self._bin_yaml = self._make_traced_var(b.get("yaml_writer", ""))
        self._bin_samap = tk.StringVar(value=b.get("samap_executable", "PLACEHOLDER_SAMAP"))
        self._bin_jpdap = tk.StringVar(value=b.get("jpdap_executable", "PLACEHOLDER_JPDAP"))
        self._bin_sa = tk.StringVar(value=b.get("SA_tool", ""))
        self._bin_sa3 = tk.StringVar(value=b.get("SA_tool_3p", ""))
        self._field(f, "MUQ-SAC bin directory", self._bin_muqsac, browse_dir=True)
        self._field(f, "Solver bin directory", self._bin_solver, browse_dir=True)
        self._field(f, "parallel_yaml_writer.so", self._bin_yaml,
                    browse_file=True, tip="Compiled from config_tools/parallel_native/. See the 'Compile' tab.")
        self._field(f, "samap executable", self._bin_samap, browse_file=True)
        self._field(f, "jpdap executable", self._bin_jpdap, browse_file=True)
        self._field(f, "SA tool (A-factor, 1-param)", self._bin_sa, browse_file=True)
        self._field(f, "SA tool (3-param A,n,Ea)", self._bin_sa3, browse_file=True)

        self._section(f, "RMIP Database")
        rmip = self.cfg.setdefault("RMIP", {})
        self._rmip_db = self._make_traced_var(rmip.get("database", "project.db"))
        self._rmip_glossary = self._make_traced_var(rmip.get("glossary", "species_smiles.csv"))
        self._field(f, "RMIP SQLite database (.db)", self._rmip_db, browse_file=True)
        self._field(f, "SMILES glossary (.csv, optional)", self._rmip_glossary, browse_file=True)

        self._add_tab_buttons(outer, 7)

    # ── Task 2A helpers: multi-fuel blend rows ────────────────────────────────

    def _add_fuel_row(self, key="", species="", xf="", coeff="", mw="", nu=""):
        if not key:
            letters = "abcdefghijklmnopqrstuvwxyz"
            key = letters[len(self._fuel_rows)] if len(self._fuel_rows) < 26 else f"f{len(self._fuel_rows)}"
        row = ttk.Frame(self._fuel_container)
        row.pack(fill=tk.X, pady=1)
        kv  = tk.StringVar(value=key)
        spv = tk.StringVar(value=species)
        xfv = tk.StringVar(value=xf)
        cov = tk.StringVar(value=coeff)
        mwv = tk.StringVar(value=mw)
        nuv = tk.StringVar(value=nu)
        ttk.Entry(row, textvariable=kv,  width=10).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=spv, width=16).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=xfv, width=12).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=cov, width=14).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=mwv, width=10).pack(side=tk.LEFT)
        nu_entry = ttk.Entry(row, textvariable=nuv, width=8,  state="readonly")
        nu_entry.pack(side=tk.LEFT)
        ttk.Button(row, text="Calc", style="Small.TButton",
                   command=lambda s=spv, m=mwv, n=nuv, e=nu_entry: self._calc_fuel_mw(s, m, n, e)
                   ).pack(side=tk.LEFT, padx=2)
        self._remove_row_button(
            row, lambda r=row, t=(kv,spv,xfv,cov,mwv,nuv): self._rm_fuel_row(r, t)
        ).pack(side=tk.LEFT, padx=2)
        self._fuel_rows.append((kv, spv, xfv, cov, mwv, nuv, nu_entry, row))
        for v in (kv, spv, xfv, cov, mwv, nuv):
            v.trace_add("write", lambda *a: self._sync_fuel_registry())
        self._sync_fuel_registry()

    def _rm_fuel_row(self, row, tup):
        row.destroy()
        self._fuel_rows = [r for r in self._fuel_rows if r[-1] is not row]
        self._sync_fuel_registry()

    def _calc_fuel_mw(self, sp_var: "tk.StringVar",
                      mw_var: "tk.StringVar", nu_var: "tk.StringVar", nu_entry: "ttk.Entry"):
        """Compute MW and nu_O2 for a single fuel species and populate read-only fields."""
        try:
            from chem_data import compute_mw, compute_nu_o2
        except ImportError:
            return
        sp = sp_var.get().strip()
        if not sp:
            return
        mw = compute_mw(sp)
        nu = compute_nu_o2(sp)
        mw_var.set(f"{mw:.3f}" if mw else "")
        nu_entry.configure(state="normal")
        nu_var.set(f"{nu:.4f}")
        nu_entry.configure(state="readonly")

    def _auto_fill_o2(self):
        """Compute blend-weighted nu_O2, update nu fields, and rebuild global reaction."""
        try:
            from chem_data import compute_mw, compute_nu_o2
        except ImportError:
            messagebox.showwarning("Missing module",
                                   "chem_data.py not found in working directory.")
            return
        blend = []
        for kv, spv, xfv, cov, mwv, nuv, nu_entry, _ in self._fuel_rows:
            sp = spv.get().strip()
            try:
                xf = float(xfv.get() or 0)
            except ValueError:
                xf = 0.0
            if sp:
                mw  = compute_mw(sp)
                nu  = compute_nu_o2(sp)
                mwv.set(f"{mw:.3f}" if mw else "")
                nu_entry.configure(state="normal")
                nuv.set(f"{nu:.4f}")
                nu_entry.configure(state="readonly")
                blend.append((sp, xf, nu, kv.get()))

        # Rebuild global reaction from atom balance (products depend on which
        # elements are actually present — see derive_global_reaction).
        fuel_blend = []
        for sp, xf, nu, key in blend:
            coeff = ""
            for row in self._fuel_rows:
                if row[0].get() == key:
                    coeff = row[3].get().strip()
                    break
            c = float(coeff) if coeff else (xf if len(blend) > 1 else 1.0)
            fuel_blend.append((sp, c, nu))
        rxn, confidence, note = derive_global_reaction(fuel_blend)
        self._inp_rxn.set(rxn)
        status = f"Auto-filled O₂: nu_O2 blend = {sum(b[2]*b[1] for b in blend):.4f}"
        if confidence == "low":
            status += f"  [LOW CONFIDENCE: {note}]"
        self._status.set(status)
        self._sync_fuel_registry()

    # ── Task 3: single fuel registry (Files & Paths blend table is the source of truth) ──

    def _sync_fuel_registry(self):
        """Rebuild self._fuel_registry from the Files & Paths fuel-blend rows.

        This is the single source of truth for fuel identity across the GUI —
        the Project tab summary, Target Builder fuel comboboxes, XML-import
        dialog, and MW dialog all read from this instead of keeping their own
        copies of the fuel name/formula.
        """
        self._fuel_registry = {}
        for kv, spv, xfv, cov, mwv, nuv, nu_entry, _ in getattr(self, "_fuel_rows", []):
            sp = spv.get().strip()
            if not sp:
                continue
            self._fuel_registry[sp] = {
                "key": kv.get().strip(),
                "xf": xfv.get().strip(),
                "coeff": cov.get().strip(),
                "mw": mwv.get().strip(),
                "nu_o2": nuv.get().strip(),
            }
        self._refresh_fuel_summary()

    def _refresh_fuel_summary(self):
        """Update the Project tab's read-only fuel summary from the registry."""
        summary_var = getattr(self, "_proj_fuel_summary", None)
        if summary_var is None:
            return
        if not self._fuel_registry:
            summary_var.set("(no fuel defined yet — add one in 'Files & Paths')")
            return
        primary = next(iter(self._fuel_registry))
        info = self._fuel_registry[primary]
        nu = info.get("nu_o2", "")
        summary_var.set(f"{primary}" + (f"  (nu_O2={nu})" if nu else "") +
                         (f"  + {len(self._fuel_registry) - 1} more" if len(self._fuel_registry) > 1 else ""))
        # Keep the underlying config fields (project.fuel_name / Inputs.fuel.formula)
        # in sync so Save/Load and the backend still see a primary fuel name.
        if hasattr(self, "_proj_fuel"):
            self._proj_fuel.set(primary)
        if hasattr(self, "_proj_formula"):
            self._proj_formula.set(primary)

    def _select_tab_by_text(self, text: str):
        """Jump the main notebook to the tab whose label starts with `text`."""
        nb = getattr(self, "_nb", None)
        if nb is None:
            return
        for i in range(len(nb.tabs())):
            if nb.tab(i, "text").strip().startswith(text):
                nb.select(i)
                break

    # Extensions that are already Cantera-native (or otherwise definitely not
    # a CHEMKIN mechanism) — everything else is worth *attempting* to convert.
    # Real CHEMKIN mechanisms are commonly named .inp, but plenty of literature
    # mechanisms use .mech/.ck/.chem/.dat/.txt or no extension at all; gating
    # on ".inp" specifically silently did nothing for any of those (no error,
    # no conversion — indistinguishable from "it's broken").
    _NON_CHEMKIN_EXTENSIONS = (".yaml", ".yml", ".cti", ".xml")

    def _auto_convert_mechanism(self, inp_path: str):
        """Auto-convert a CHEMKIN mechanism to Cantera YAML + FlameMaster .pre.

        Thin wrapper around the module-level convert_mechanism_files(), which
        both this single-mechanism field and the multi-mechanism fan-out
        (Part F) share — failures are surfaced via a dialog rather than
        silently swallowed.
        """
        if inp_path.lower().endswith(self._NON_CHEMKIN_EXTENSIONS):
            return
        yaml_path, pre_path, errors = convert_mechanism_files(
            inp_path, self._loc_thermo.get(), self._loc_trans.get(),
            out_dir=str(Path(inp_path).parent), scanman_bin=self._bin_solver.get(),
        )
        if yaml_path:
            self._status.set(f"✓ Converted to Cantera YAML: {yaml_path}")
        if pre_path:
            self._loc_pre.set(pre_path)
            self._status.set(f"✓ Converted to FlameMaster .pre: {pre_path}")
        if errors:
            messagebox.showwarning("Mechanism conversion issues", "\n".join(errors))

    # ── Tab: Mechanisms ───────────────────────────────────────────────────────

    def _tab_mechanisms(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="Mechanisms")

        ttk.Label(outer, text="Mechanisms to Load into RMIP",
                  font=FONTS["header"]).pack(anchor=tk.W, padx=12, pady=6)
        ttk.Label(outer,
                  text="List all mechanisms to parse and analyze. Order = DB IDs 1, 2, 3…  "
                       "RMIP supports CHEMKIN (.inp) and Cantera YAML (.yaml).",
                  foreground=PALETTE["text_dim"], wraplength=900).pack(anchor=tk.W, padx=12)

        ctrl = ttk.Frame(outer)
        ctrl.pack(fill=tk.X, padx=12, pady=4)
        ttk.Button(ctrl, text="+ Add mechanism", command=self._add_mech).pack(side=tk.LEFT, padx=4)
        conv_all_btn = ttk.Button(ctrl, text="Convert all CHEMKIN rows to YAML/.pre",
                                   command=self._convert_all_mech_rows)
        conv_all_btn.pack(side=tk.LEFT, padx=12)
        self._hoverable(conv_all_btn,
                        "Runs ck2yaml (+ ScanMan, if a solver bin is set on Files & Paths) "
                        "on every row below whose Format is 'chemkin'")

        self._section(outer, "Multi-mechanism processing")
        ttk.Label(outer,
                  text="One at a time: build a separate target.opt (its own mechanism/thermo/"
                       "transport/.pre and species-translated .target) per mechanism folder under "
                       "the output dir.\nFuse into one: parse all into RMIP with their own SMILES "
                       "glossary each, fuse via RMIP's FusionEngine, and build a single target.opt.",
                  foreground=PALETTE["text_dim"], wraplength=900).pack(anchor=tk.W, padx=12)
        wf_row = ttk.Frame(outer)
        wf_row.pack(anchor=tk.W, padx=12, pady=2)
        ttk.Radiobutton(wf_row, text="Process one mechanism at a time", value="one_at_a_time",
                         variable=self._mech_workflow).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(wf_row, text="Fuse all mechanisms into one", value="fuse",
                         variable=self._mech_workflow).pack(side=tk.LEFT)

        # Header — one label row per field, rows below wrap each mechanism's
        # fields onto two lines (primary: name/path/format; secondary:
        # thermo/transport/glossary/pre) to keep the tab a reasonable width.
        hdr = ttk.Frame(outer)
        hdr.pack(fill=tk.X, padx=12, pady=(6, 0))
        for col, w in [("#", 3), ("Name", 18), ("Path (mechanism file)", 40), ("Format", 14)]:
            ttk.Label(hdr, text=col, width=w, relief=tk.RIDGE, anchor=tk.CENTER).pack(side=tk.LEFT)
        hdr2 = ttk.Frame(outer)
        hdr2.pack(fill=tk.X, padx=12)
        for col, w in [("Thermo (.dat)", 22), ("Transport (.dat)", 22),
                       ("Glossary (.csv, Fuse)", 22), ("Initial .pre (opt.)", 22)]:
            ttk.Label(hdr2, text=col, width=w, relief=tk.RIDGE, anchor=tk.CENTER).pack(side=tk.LEFT, padx=(21, 0))

        self._mech_container = ttk.Frame(outer)
        self._mech_container.pack(fill=tk.BOTH, expand=True, padx=12)

        for m in self.cfg.get("RMIP", {}).get("mechanisms", []):
            self._add_mech(m.get("name", ""), m.get("path", ""),
                           m.get("thermo", ""), m.get("trans", ""), m.get("format", "cantera_yaml"),
                           m.get("glossary", ""), m.get("pre", ""))
        if not self._mech_rows:
            self._add_mech()

        self._add_tab_buttons(outer, 1)

    def _add_mech(self, name="", path="", thermo="", trans="", fmt="cantera_yaml",
                  glossary="", pre=""):
        idx = len(self._mech_rows) + 1
        entry = ttk.Frame(self._mech_container, relief=tk.GROOVE, borderwidth=1)
        entry.pack(fill=tk.X, pady=2)
        row1 = ttk.Frame(entry)
        row1.pack(fill=tk.X, pady=1)
        row2 = ttk.Frame(entry)
        row2.pack(fill=tk.X, pady=1)

        nv, pv, tv, trv, fv, glv, prv = (
            tk.StringVar(value=name), tk.StringVar(value=path), tk.StringVar(value=thermo),
            tk.StringVar(value=trans), tk.StringVar(value=fmt),
            tk.StringVar(value=glossary), tk.StringVar(value=pre),
        )
        ttk.Label(row1, text=str(idx), width=3).pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=nv, width=18).pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=pv, width=40).pack(side=tk.LEFT)
        ttk.Button(row1, text="…", width=2,
                   command=lambda v=pv: v.set(filedialog.askopenfilename() or v.get())).pack(side=tk.LEFT)
        ttk.Combobox(row1, textvariable=fv, values=["cantera_yaml", "chemkin"],
                     width=12, state="readonly").pack(side=tk.LEFT, padx=4)
        conv_btn = ttk.Button(row1, text="→YAML/.pre", width=10,
                              command=lambda n=nv, p=pv, t=tv, tr=trv, fm=fv, pr=prv:
                                  self._convert_mech_row(n, p, t, tr, fm, pr))
        conv_btn.pack(side=tk.LEFT, padx=2)
        self._hoverable(conv_btn, "Convert this row's CHEMKIN .inp to Cantera YAML "
                                   "(+ FlameMaster .pre if a solver bin is set)")
        self._remove_row_button(
            entry, lambda r=entry, t=(nv, pv, tv, trv, fv, glv, prv): self._rm_mech(r, t)
        ).pack(side=tk.LEFT, padx=2)

        ttk.Label(row2, text="", width=3).pack(side=tk.LEFT)
        for var, w in ((tv, 22), (trv, 22), (glv, 22), (prv, 22)):
            ttk.Entry(row2, textvariable=var, width=w).pack(side=tk.LEFT)
            ttk.Button(row2, text="…", width=2,
                       command=lambda v=var: v.set(filedialog.askopenfilename() or v.get())).pack(side=tk.LEFT)

        self._mech_rows.append((nv, pv, tv, trv, fv, glv, prv))

    def _rm_mech(self, row, tup):
        row.destroy()
        if tup in self._mech_rows:
            self._mech_rows.remove(tup)

    def _convert_mech_row(self, nv, pv, tv, trv, fv, prv):
        """On-demand YAML/.pre conversion for one Mechanisms-tab row, via the
        already-working convert_mechanism_files() (ck2yaml + ScanMan) — the
        same path _auto_convert_mechanism/_rs_resolve_mechanism_yaml/the
        multi-mechanism batch build already use. make_input_file.py's own
        create_input_file()/s_convert is a separate, less-tested toolchain
        invocation and is deliberately not used here.
        """
        path = pv.get()
        if fv.get() != "chemkin" or not path:
            messagebox.showinfo("Nothing to convert",
                                 "Set Format to 'chemkin' with a mechanism path first.")
            return
        yaml_path, pre_path, errors = convert_mechanism_files(
            path, tv.get(), trv.get(), out_dir=str(Path(path).parent),
            scanman_bin=self._bin_solver.get() if hasattr(self, "_bin_solver") else None,
        )
        label = nv.get() or path
        if yaml_path:
            self._status.set(f"✓ {label}: converted to {yaml_path}")
        if pre_path:
            prv.set(pre_path)
        if errors:
            messagebox.showwarning(f"{label}: conversion issues", "\n".join(errors))

    def _convert_all_mech_rows(self):
        n_done = 0
        for nv, pv, tv, trv, fv, glv, prv in list(self._mech_rows):
            if fv.get() == "chemkin" and pv.get():
                self._convert_mech_row(nv, pv, tv, trv, fv, prv)
                n_done += 1
        if n_done == 0:
            messagebox.showinfo("Nothing to convert", "No CHEMKIN-format rows found.")
        else:
            self._status.set(f"Converted {n_done} CHEMKIN row(s) to YAML/.pre")

    # ── Tab: Optimization (Stats) ─────────────────────────────────────────────

    def _tab_optimization(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="Optimization")
        f = self._scrolled(outer)
        s = self.cfg.setdefault("Stats", {})

        ttk.Label(f, text="PRS / Design Matrix", font=FONTS["section"]).pack(anchor=tk.W, padx=12, pady=6)
        self._design = tk.StringVar(value=s.get("Design_of_PRS", "A-facto"))
        self._order = tk.StringVar(value=str(s.get("Order_of_PRS", 2)))
        self._sampling = tk.StringVar(value=str(s.get("Sampling_of_PRS", 4)))
        self._prs_type = tk.StringVar(value=s.get("PRS_type", "Partial"))
        self._cutoff = tk.StringVar(value=str(s.get("cut_off_percentage", 1)))
        self._mre = tk.StringVar(value=str(s.get("MRE_criteria", 5.0)))
        self._field(f, "Design of PRS", self._design,
                    choices=["A-facto", "Monte-Carlo-All", "LHS-maximin", "B1", "A1+B1+C1"],
                    tip="A-facto: vary only A-factor (1 param). Monte-Carlo-All: vary A,n,Ea.")
        self._field(f, "Order of PRS (polynomial)", self._order, choices=["1", "2", "3"],
                    tip="2 = quadratic (recommended). 1 = linear (fast). 3 = cubic (slow).")
        self._field(f, "Sampling_of_PRS (multiplier)", self._sampling,
                    tip="Number of samples = Sampling × n_reactions. Higher = more accurate PRS.")
        self._field(f, "PRS type", self._prs_type, choices=["Partial", "Full"])
        self._field(f, "Cut-off percentage (%)", self._cutoff,
                    tip="Reactions with SA below this % are excluded from optimization.")
        self._field(f, "MRE_criteria (%)", self._mre,
                    tip="Mean relative error threshold that triggers adaptive retraining.")

        self._section(f, "Objective Function")
        self._obj = tk.StringVar(value=s.get("Objective", "powerMeanWMRE"))
        self._field(f, "Objective", self._obj,
                    choices=["powerMeanWMRE", "WMRE", "logRMSE", "unbiasedWMRE",
                              "logDatasetWMRE", "dynamicWMRE", "softChebysheWMRE",
                              "penWMRE", "omhWMRE"],
                    tip="powerMeanWMRE: recommended for mixed dataset types.")
        self._pm_p = tk.StringVar(value=str(s.get("pm_p", 0.1)))
        self._pm_p_start = tk.StringVar(value=str(s.get("pm_p_start", 1.0)))
        self._num_gen = tk.StringVar(value=str(s.get("num_generations", 20000)))
        self._softmax_beta = tk.StringVar(value=str(s.get("softmax_beta", 20.0)))
        self._pen_alpha = tk.StringVar(value=str(s.get("pen_alpha", 0.9)))
        self._pen_K = tk.StringVar(value=str(s.get("pen_K", 100.0)))
        self._field(f, "pm_p (power-mean exponent)", self._pm_p,
                    tip="Smaller = more uniform weighting. Larger = emphasizes worst-case.")
        self._field(f, "pm_p_start (anneal from)", self._pm_p_start)
        self._field(f, "num_generations (GA)", self._num_gen)
        self._field(f, "softmax_beta (minimax pressure)", self._softmax_beta)
        self._field(f, "pen_alpha (floor fraction)", self._pen_alpha,
                    tip="0.9 = optimized must not be >10% worse than nominal.")
        self._field(f, "pen_K (penalty weight)", self._pen_K)

        self._section(f, "Target Weights (Stats.Weights)")
        ttk.Label(f, text="Objective weight per target_type. 0 = excluded from the objective.",
                  foreground=PALETTE["text_dim"]).pack(anchor=tk.W, padx=12)
        w = s.get("Weights", {"Tig": 1.0})
        # Task 2: one weight field per backend-supported target_type, not just Tig/Fls.
        self._weight_vars = {}
        for ttype in TARGET_TYPES:
            default = w.get(ttype, 1.0 if ttype == "Tig" else 0.0)
            v = tk.StringVar(value=str(default))
            self._weight_vars[ttype] = v
            self._field(f, f"Weight: {ttype}", v, tip=TARGET_TYPES[ttype])

        self._section(f, "Adaptive Outlier Retraining")
        self._out_N = tk.StringVar(value=str(s.get("outlier_N_new", 200)))
        self._out_mode = tk.StringVar(value=s.get("outlier_sample_mode", "dm_global"))
        self._out_max = tk.StringVar(value=str(s.get("outlier_max_iter", 5)))
        self._field(f, "N_new samples per pass", self._out_N)
        self._field(f, "Sample mode", self._out_mode,
                    choices=["dm_global", "local"],
                    tip="dm_global fills gaps across the whole design matrix (recommended).")
        self._field(f, "Max retraining passes", self._out_max)

        self._add_tab_buttons(outer, 8)

    # ── Tab: RMIP Analysis ────────────────────────────────────────────────────

    def _tab_rmip_analysis(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="RMIP Analysis")
        f = self._scrolled(outer)
        rmip = self.cfg.setdefault("RMIP", {})

        ttk.Label(f, text="RMIP Analysis Settings", font=FONTS["header"]).pack(anchor=tk.W, padx=12, pady=6)

        self._section(f, "Graph Visualization (2D)")
        g = rmip.setdefault("graph", {})
        self._g_layout = tk.StringVar(value=g.get("layout", "spring"))
        self._g_outdir = tk.StringVar(value=g.get("out_dir", "outputs/graphs"))
        self._g_fmt = tk.StringVar(value=g.get("figure_format", "png"))
        self._field(f, "2D Layout", self._g_layout,
                    choices=["spring", "circle", "bipartite", "preset_carbon_ring"],
                    tip="spring = force-directed (best for most). preset_carbon_ring = grouped by Cn.")
        self._field(f, "Output dir (2D graphs)", self._g_outdir, browse_dir=True)
        self._field(f, "Export format", self._g_fmt, choices=["png", "pdf", "svg"])

        self._section(f, "3D Planetary Graph (Phase 5C)")
        g3 = rmip.setdefault("graph3d", {})
        self._g3_shell = tk.StringVar(value=str(g3.get("shell_gap", 2.0)))
        self._g3_layer = tk.StringVar(value=str(g3.get("layer_gap", 1.0)))
        self._g3_order = tk.StringVar(value=g3.get("order", "alpha"))
        self._g3_out = tk.StringVar(value=g3.get("out_dir", "outputs/graphs/3d"))
        self._field(f, "Shell gap (radial, ≥2.0)", self._g3_shell)
        self._field(f, "Layer gap (z-height)", self._g3_layer,
                    tip="0 = flat solar-system plane. 1.0 = stacked discs.")
        self._field(f, "Angular order", self._g3_order, choices=["alpha", "family"])
        self._field(f, "Output dir (3D export)", self._g3_out, browse_dir=True)

        self._section(f, "Kinetics / Thermo Comparison")
        cmp = rmip.setdefault("comparison", {})
        self._cmp_tolA = tk.StringVar(value=str(cmp.get("tol_A", 0.01)))
        self._cmp_toln = tk.StringVar(value=str(cmp.get("tol_n", 0.001)))
        self._cmp_tolE = tk.StringVar(value=str(cmp.get("tol_Ea", 100.0)))
        self._cmp_out = tk.StringVar(value=cmp.get("out_dir", "outputs/comparison"))
        self._field(f, "tol_A (rel, fraction)", self._cmp_tolA)
        self._field(f, "tol_n (absolute)", self._cmp_toln)
        self._field(f, "tol_Ea (J/mol)", self._cmp_tolE)
        self._field(f, "Output dir", self._cmp_out, browse_dir=True)

        self._section(f, "Mechanism Fusion")
        fus = rmip.setdefault("fusion", {})
        self._fus_name = tk.StringVar(value=fus.get("name", "Fused_Mech"))
        self._fus_desc = tk.StringVar(value=fus.get("description", ""))
        self._fus_uf = tk.StringVar(value=str(fus.get("uf_warn", 10.0)))
        self._fus_out = tk.StringVar(value=fus.get("out_dir", "outputs/fusion"))
        self._field(f, "Fused mechanism name", self._fus_name)
        self._field(f, "Description", self._fus_desc, width=52)
        self._field(f, "UF warning threshold (× A factor)", self._fus_uf,
                    tip="Reactions with A-factor spread >this emit a warning.")
        self._field(f, "Output dir", self._fus_out, browse_dir=True)

        self._section(f, "Mechanism Reduction")
        red = rmip.setdefault("reduction", {})
        self._red_method = tk.StringVar(value=red.get("method", "DRG"))
        self._red_target = tk.StringVar(value=red.get("target_species", "H2,O2,H2O"))
        self._red_eps = tk.StringVar(value=str(red.get("eps_max", 0.5)))
        self._red_T = tk.StringVar(value=str(red.get("T", 1200.0)))
        self._red_P = tk.StringVar(value=str(red.get("P", 1.0)))
        self._red_phi = tk.StringVar(value=str(red.get("phi", 1.0)))
        self._red_out = tk.StringVar(value=red.get("out_dir", "outputs/reduction"))
        self._field(f, "Reduction method", self._red_method,
                    choices=["DRG", "DRGEP", "PFA", "DRGPSA", "DRGSA"],
                    tip="DRG: fast. DRGEP: more conservative. DRGPSA/DRGSA: SA-weighted.")
        self._field(f, "Target species (comma-separated)", self._red_target)
        self._red_target_file = tk.StringVar(value=red.get("target_file", ""))
        self._field(f, ".target file used for this (if any)", self._red_target_file,
                    tip="Set automatically by 'Import target species from .target…' below.")
        import_btn = ttk.Button(f, text="Import target species from .target…",
                                command=self._open_reduction_target_import)
        import_btn.pack(anchor=tk.W, padx=12, pady=(0, 6))
        self._hoverable(import_btn,
                        "Derive target species from an existing .target file or a subset "
                        "of the rows already built in the Targets tab")
        self._field(f, "eps_max (threshold sweep end)", self._red_eps)
        self._field(f, "T (K) for rate evaluation", self._red_T)
        self._field(f, "P (atm)", self._red_P)
        self._field(f, "phi (equivalence ratio)", self._red_phi)
        self._field(f, "Output dir", self._red_out, browse_dir=True)

        red_mech_row = ttk.Frame(f)
        red_mech_row.pack(fill=tk.X, padx=12, pady=2)
        ttk.Label(red_mech_row, text="Mechanism", width=30, anchor=tk.W).pack(side=tk.LEFT)
        red_mech_names = [nv.get() or pv.get() for nv, pv, tv, trv, fv, glv, prv in self._mech_rows if pv.get()]
        self._red_mechanism = tk.StringVar(value=red_mech_names[0] if red_mech_names else "")
        ttk.Combobox(red_mech_row, textvariable=self._red_mechanism, values=red_mech_names,
                     width=38, state="readonly" if red_mech_names else "disabled").pack(side=tk.LEFT)

        run_red_btn = ttk.Button(f, text="Run Reduction (selected conditions)",
                                  command=self._run_mechanism_reduction_multi_condition)
        run_red_btn.pack(anchor=tk.W, padx=12, pady=(4, 8))
        self._hoverable(run_red_btn,
                        "Runs the selected reducer once per condition in the reduction "
                        "target set (all rows, or the confirmed diverse subset) and unions "
                        "the retained species/reactions across all of them.")

        self._section(f, "Sensitivity Analysis (sa-run)")
        rmip.setdefault("sa_analysis", {})
        # self._sa_fuel/_sa_T/_sa_P/_sa_phi/_sa_out are created once in
        # App.__init__ (shared with the Reaction Screening tab, which now
        # builds earlier in the tab sequence and needs them too) — not
        # recreated here.
        self._field(f, "Fuel", self._sa_fuel,
                    choices=list(self._fuel_registry.keys()) or [self._sa_fuel.get()],
                    editable=True, tip="Defaults from the fuel-blend table (Files & Paths tab).")
        self._field(f, "T (K)", self._sa_T)
        self._field(f, "P (atm)", self._sa_P)
        self._field(f, "phi (equivalence ratio)", self._sa_phi)
        self._field(f, "Output dir", self._sa_out, browse_dir=True)

        self._section(f, "Unified Tree — T-dependent Uncertainty Bands")
        ut = rmip.setdefault("unified_tree", {})
        self._ut_mode = tk.StringVar(value=ut.get("mode", "anchored"))
        self._ut_anchor = tk.StringVar(value=ut.get("anchor_mechanism", ""))
        self._ut_tmin = tk.StringVar(value=str(ut.get("T_min", 500)))
        self._ut_tmax = tk.StringVar(value=str(ut.get("T_max", 2500)))
        self._ut_dt = tk.StringVar(value=str(ut.get("dT", 20)))
        self._ut_pref = tk.StringVar(value=str(ut.get("P_ref_atm", 1.0)))
        self._ut_out = tk.StringVar(value=ut.get("out_dir", "outputs/unified"))
        self._field(f, "Mode", self._ut_mode, choices=["anchored", "optimize_all"],
                    tip="anchored: keep one mechanism as reference. optimize_all: geometric mean all.")
        self._field(f, "Anchor mechanism name", self._ut_anchor,
                    tip="Must match exactly one name in the Mechanisms tab.")
        self._field(f, "T_min (K)", self._ut_tmin)
        self._field(f, "T_max (K)", self._ut_tmax)
        self._field(f, "dT (K step)", self._ut_dt)
        self._field(f, "P_ref (atm)", self._ut_pref)
        self._field(f, "Output dir", self._ut_out, browse_dir=True)

        self._section(f, "Export Paths for Final Mechanism")
        ex = rmip.setdefault("export", {})
        self._ex_ck = tk.StringVar(value=ex.get("chemkin_path", "outputs/export/mechanism.inp"))
        self._ex_yaml = tk.StringVar(value=ex.get("yaml_path", "outputs/export/mechanism.yaml"))
        self._field(f, "CHEMKIN export (.inp)", self._ex_ck)
        self._field(f, "Cantera YAML export (.yaml)", self._ex_yaml)

        self._add_tab_buttons(outer, 9)

    def _open_reduction_target_import(self):
        """Derive Mechanism Reduction's target_species from a .target file,
        either an existing one on disk or a subset of the Targets-tab rows.
        """
        dlg = tk.Toplevel(self.root)
        dlg.title("Import Target Species from .target")
        dlg.geometry("560x480")
        dlg.configure(bg=PALETTE["surface"])
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Import Target Species", font=FONTS["header"]).pack(pady=(12, 4))

        # ── Option A: parse an existing .target file on disk ──────────────
        self._section(dlg, "From an existing .target file")
        path_row = ttk.Frame(dlg); path_row.pack(fill=tk.X, padx=16, pady=4)
        path_var = tk.StringVar(value=self._loc_targets.get())
        ttk.Entry(path_row, textvariable=path_var, width=45).pack(side=tk.LEFT)
        ttk.Button(path_row, text="…", width=3,
                   command=lambda: path_var.set(
                       filedialog.askopenfilename(filetypes=[("target files", "*.target"), ("All", "*")])
                       or path_var.get())
                   ).pack(side=tk.LEFT, padx=2)

        def _use_file():
            path = path_var.get().strip()
            if not path or not Path(path).exists():
                messagebox.showwarning("Not found", "Choose a valid .target file first.", parent=dlg)
                return
            try:
                species = parse_target_file_species(path)
            except Exception as e:
                messagebox.showerror("Parse error", str(e), parent=dlg)
                return
            if not species:
                messagebox.showinfo("No species found", "Couldn't find Fuel/Oxidizer/Bath_gas "
                                                          "entries in that file.", parent=dlg)
                return
            self._red_target.set(",".join(species))
            self._red_target_file.set(path)
            self._status.set(f"Reduction target species from {path}: {', '.join(species)}")
            dlg.destroy()

        ttk.Button(dlg, text="Use species from this file", command=_use_file).pack(pady=4)

        # ── Option B: pick a subset of the rows already built in Targets tab ──
        # Sourced from self._target_df (the full dataset), not self._target_rows
        # (which only ever holds the current page's widgets since the pandas/
        # pagination rework) — otherwise this dialog would only ever see
        # whichever page happened to be open when it was launched.
        self._target_flush_page_to_df()
        self._section(dlg, "From a subset of the Targets tab rows")
        if self._target_df.empty:
            ttk.Label(dlg, text="(No rows in the Targets tab yet — build some there first, "
                                "or use option A above.)",
                      foreground=PALETTE["text_dim"], wraplength=500).pack(anchor=tk.W, padx=16)
        else:
            list_canvas_frame = ttk.Frame(dlg)
            list_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)
            list_canvas = tk.Canvas(list_canvas_frame, height=180, highlightthickness=0)
            list_scroll = ttk.Scrollbar(list_canvas_frame, orient=tk.VERTICAL, command=list_canvas.yview)
            list_frame = ttk.Frame(list_canvas)
            list_frame.bind("<Configure>", lambda e: list_canvas.configure(scrollregion=list_canvas.bbox("all")))
            list_canvas.create_window((0, 0), window=list_frame, anchor="nw")
            list_canvas.configure(yscrollcommand=list_scroll.set)
            list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            list_scroll.pack(side=tk.RIGHT, fill=tk.Y)

            check_vars = []
            for idx, row in self._target_df.iterrows():
                cv = tk.BooleanVar(value=True)
                label = (f"{row['dataset_id']}  ({row['target_type']}, "
                         f"T={row['T']}, P={row['P']}, phi={row['phi']})")
                ttk.Checkbutton(list_frame, text=label, variable=cv).pack(anchor=tk.W)
                check_vars.append((cv, row))

            out_row = ttk.Frame(dlg); out_row.pack(fill=tk.X, padx=16, pady=(6, 0))
            ttk.Label(out_row, text="Write subset to:", width=14).pack(side=tk.LEFT)
            subset_path_var = tk.StringVar(value="targets/reduction_subset.target")
            ttk.Entry(out_row, textvariable=subset_path_var, width=32).pack(side=tk.LEFT)

            def _use_selected():
                selected = [row for cv, row in check_vars if cv.get()]
                if not selected:
                    messagebox.showwarning("Nothing selected", "Check at least one row.", parent=dlg)
                    return
                species = sorted({row[k] for row in selected
                                   for k in ("fuel_species", "oxidizer_species", "bath_species")
                                   if row.get(k)})
                self._red_target.set(",".join(species))
                out_path = subset_path_var.get().strip()
                if out_path:
                    rows = [dict(row) for row in selected]
                    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
                    generate_target_file(rows, out_path)
                    self._red_target_file.set(out_path)
                    self._status.set(f"Reduction subset written: {out_path} "
                                     f"({len(rows)} rows) — species: {', '.join(species)}")
                else:
                    self._status.set(f"Reduction target species from selected rows: {', '.join(species)}")
                dlg.destroy()

            ttk.Button(dlg, text="Use species from selected rows (+ write subset file)",
                       command=_use_selected).pack(pady=6)

        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=4)

    # ── Mechanism Reduction: auto-load target + diverse-subset selection ───────

    def _on_notebook_tab_changed_for_reduction(self, event=None):
        try:
            current_tab_text = self._nb.tab(self._nb.select(), "text")
        except tk.TclError:
            return
        if current_tab_text.strip().startswith("RMIP Analysis") and not self._red_autoloaded:
            self._auto_populate_reduction_target()

    def _auto_populate_reduction_target(self):
        """Auto-populate the Mechanism Reduction target file from whatever has
        been built in the Experimental Data tab, the first time the RMIP
        Analysis tab is opened. Never clobbers a target_file the user already
        set (manually, or from a prior auto-populate) — guarded by
        self._red_autoloaded, which only latches once something is actually
        written (so an empty Experimental Data tab doesn't permanently block
        a later auto-populate once the user adds rows and revisits the tab).
        """
        if self._red_target_file.get():
            self._red_autoloaded = True
            return
        self._target_flush_page_to_df()
        if self._target_df.empty:
            return
        species = sorted({
            row[k] for _, row in self._target_df.iterrows()
            for k in ("fuel_species", "oxidizer_species", "bath_species")
            if row.get(k)
        })
        if species:
            self._red_target.set(",".join(species))
        out_path = "targets/reduction_full.target"
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        generate_target_file(self._target_df.to_dict("records"), out_path)
        self._red_target_file.set(out_path)
        self._red_autoloaded = True
        self._status.set(f"Auto-populated reduction target from Experimental Data tab: "
                          f"{len(species)} species, {len(self._target_df)} rows")
        self._prompt_reduction_subset_choice()

    def _conditions_from_df(self, df) -> list:
        """Convert target-row DataFrame rows into rmip SimCondition objects."""
        _rmip_src_on_path()
        from rmip.types import SimCondition
        conditions = []
        for _, row in df.iterrows():
            try:
                T_K, P_atm, phi = float(row["T"]), float(row["P"]), float(row["phi"])
            except (ValueError, TypeError):
                continue
            fuel = f"{row.get('fuel_species') or 'H2'}:{row.get('fuel_xf') or 1.0}"
            oxidizer = f"{row.get('oxidizer_species') or 'O2'}:{row.get('ox_xf') or 1.0}"
            if row.get("bath_species"):
                oxidizer += f", {row['bath_species']}:{row.get('bath_xf') or 0.0}"
            conditions.append(SimCondition(T_K=T_K, P_atm=P_atm, phi=phi, fuel=fuel, oxidizer=oxidizer))
        return conditions

    def _prompt_reduction_subset_choice(self):
        n_total = len(self._target_df)
        if not messagebox.askyesno(
            "Reduce against subset?",
            f"{n_total} experimental target(s) loaded.\n\n"
            "Reduce the mechanism against ALL of them, or a diverse SUBSET?\n\n"
            "Yes = pick a smaller, representative subset\nNo = use all targets"
        ):
            self._red_conditions = self._conditions_from_df(self._target_df)
            self._status.set(f"Reduction will use all {n_total} target condition(s).")
            return
        n = simpledialog.askinteger(
            "Subset size", f"How many targets to select (out of {n_total})?",
            initialvalue=min(20, n_total), minvalue=2, maxvalue=n_total)
        if n is None:
            self._red_conditions = self._conditions_from_df(self._target_df)
            return
        self._run_reduction_subset_sampling(n, seed=0)

    def _run_reduction_subset_sampling(self, n: int, seed: int = 0):
        _rmip_src_on_path()
        _src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
        if _src_dir not in sys.path:
            sys.path.insert(0, _src_dir)
        from target_sampling import farthest_point_sample, coverage_ratio

        df = self._target_df
        T = pd.to_numeric(df["T"], errors="coerce").to_numpy()
        P = pd.to_numeric(df["P"], errors="coerce").to_numpy()
        phi = pd.to_numeric(df["phi"], errors="coerce").to_numpy()
        points = np.column_stack([T, P, phi])
        valid = np.isfinite(points).all(axis=1)
        idx_map = np.flatnonzero(valid)

        if len(idx_map) < 2:
            messagebox.showwarning("Not enough valid rows",
                "Fewer than 2 rows have numeric T/P/phi (rows with phi='N/A' are excluded "
                "from sampling) — using all targets instead.")
            self._red_conditions = self._conditions_from_df(df)
            return
        if len(idx_map) < n:
            messagebox.showinfo("Fewer valid rows than requested",
                f"Only {len(idx_map)} row(s) have numeric T/P/phi; selecting all of them.")
            n = len(idx_map)

        sel_local = farthest_point_sample(points[valid], n, seed=seed)
        sel_idx = idx_map[sel_local]
        cov = coverage_ratio(points[valid], sel_local)
        self._show_reduction_subset_confirm(df, points, valid, sel_idx, cov, n, seed)

    def _show_reduction_subset_confirm(self, df, points, valid, sel_idx, cov, n, seed):
        """3D T-P-phi scatter (full dataset vs. selected subset) with
        Accept / Redo-with-new-seed / Cancel. Follows the same lazy-import,
        graceful-degrade matplotlib pattern used by pysr_panel.py — this file
        has no other matplotlib usage.
        """
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (registers 3d projection)
            mpl_ok = True
        except ImportError:
            mpl_ok = False

        dlg = tk.Toplevel(self.root)
        dlg.title("Confirm reduction target subset")
        dlg.geometry("640x560")
        dlg.configure(bg=PALETTE["surface"])
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text=f"Selected {n} of {len(df)} targets (seed={seed})",
                  font=FONTS["header"]).pack(pady=(10, 2))
        if cov < 0.6:
            ttk.Label(dlg, text=f"Coverage of full T/P/phi domain: {cov:.0%} — "
                                 "consider increasing N for better domain coverage.",
                      foreground="#f38ba8", wraplength=580).pack(pady=(0, 4))
        else:
            ttk.Label(dlg, text=f"Coverage of full T/P/phi domain: {cov:.0%}",
                      foreground=PALETTE["text_dim"]).pack(pady=(0, 4))

        excluded = int((~valid).sum())
        if excluded:
            ttk.Label(dlg, text=f"({excluded} row(s) without numeric phi were excluded from sampling)",
                      foreground=PALETTE["text_dim"]).pack()

        if mpl_ok:
            fig = Figure(figsize=(6, 5), dpi=90, facecolor="#1e1e2e")
            ax = fig.add_subplot(111, projection="3d", facecolor="#2a2a3e")
            valid_points = points[valid]
            ax.scatter(valid_points[:, 0], valid_points[:, 1], valid_points[:, 2],
                       color="#585b70", s=15, alpha=0.5, label="Full dataset")
            sel_points = points[sel_idx]
            ax.scatter(sel_points[:, 0], sel_points[:, 1], sel_points[:, 2],
                       color="#f38ba8", s=40, marker="^", label=f"Selected ({n})")
            ax.set_xlabel("T (K)", color="#cdd6f4")
            ax.set_ylabel("P (atm)", color="#cdd6f4")
            ax.set_zlabel("phi", color="#cdd6f4")
            ax.tick_params(colors="#cdd6f4")
            ax.legend(facecolor="#2a2a3e", labelcolor="#cdd6f4")
            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=dlg)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10)
        else:
            ttk.Label(dlg, text="matplotlib not found — install it to see the T-P-phi plot.\n"
                                 f"Selected row indices: {sorted(int(i) for i in sel_idx)}",
                      foreground=PALETTE["text_dim"], wraplength=580).pack(pady=20)

        btn_row = ttk.Frame(dlg)
        btn_row.pack(pady=10)

        def _accept():
            self._finalize_reduction_conditions(df, sel_idx)
            dlg.destroy()

        def _redo():
            dlg.destroy()
            self._run_reduction_subset_sampling(n, seed=seed + 1)

        def _cancel():
            self._red_conditions = self._conditions_from_df(df)
            self._status.set("Subset selection cancelled — reduction will use all targets.")
            dlg.destroy()

        ttk.Button(btn_row, text="Accept", command=_accept).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Redo with new seed", command=_redo).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Cancel (use all targets)", command=_cancel).pack(side=tk.LEFT, padx=6)

    def _finalize_reduction_conditions(self, df, sel_idx):
        subset_df = df.iloc[sorted(int(i) for i in sel_idx)]
        self._red_conditions = self._conditions_from_df(subset_df)
        out_path = "targets/reduction_subset.target"
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        generate_target_file(subset_df.to_dict("records"), out_path)
        self._red_target_file.set(out_path)
        self._status.set(f"Reduction subset confirmed: {len(subset_df)} condition(s) → {out_path}")

    def _run_mechanism_reduction_multi_condition(self):
        """Run the selected reducer once per condition in self._red_conditions
        (all targets, or the confirmed diverse subset — set by the subset-
        confirm flow above) and union the retained species/reactions across
        all runs (per confirmed design: union, not intersection — keeps the
        reduced mechanism valid across the whole selected domain).
        """
        import threading
        if not self._red_conditions:
            messagebox.showwarning("No conditions", "Open the RMIP Analysis tab (with target "
                                     "rows already built) first, or use 'Import target species "
                                     "from .target…' to set up reduction conditions.")
            return
        mech_name = self._red_mechanism.get()
        row = next(((pv.get(), fv.get(), tv.get(), trv.get()) for nv, pv, tv, trv, fv, glv, prv
                    in self._mech_rows if (nv.get() or pv.get()) == mech_name), None)
        if not row:
            messagebox.showwarning("No mechanism", "Pick a mechanism in the Mechanism Reduction "
                                                     "section first.")
            return
        mech_path, fmt, thermo, trans = row
        target_species = [s.strip() for s in self._red_target.get().split(",") if s.strip()]
        if not target_species:
            messagebox.showwarning("No target species", "Set target species first (or use "
                                                          "'Import target species from .target…').")
            return
        eps = float(self._red_eps.get() or 0.5)
        method = self._red_method.get()
        out_dir = Path(self._red_out.get() or "outputs/reduction")
        conditions = list(self._red_conditions)

        def _worker():
            try:
                _rmip_src_on_path()
                from rmip.config import RMIPConfig
                from rmip.core.parser import MechanismParser
                from rmip.core.graph_builder import GraphBuilder
                from rmip.reduction.drg import DRGReducer
                from rmip.reduction.drgep import DRGEPReducer
                from rmip.reduction.pfa import PFAReducer
                from rmip.reduction.drgpsa import DRGPSAReducer, DRGSAReducer

                reducer_cls = {"DRG": DRGReducer, "DRGEP": DRGEPReducer, "PFA": PFAReducer,
                               "DRGPSA": DRGPSAReducer, "DRGSA": DRGSAReducer}[method]
                db_path = self._rmip_db.get() or "project.db"
                yaml_path = mech_path
                if fmt == "chemkin":
                    yaml_path, errors = self._rs_resolve_mechanism_yaml(mech_path, thermo, trans, fmt)
                    if not yaml_path:
                        self.root.after(0, lambda: messagebox.showerror(
                            "Conversion failed", "\n".join(errors) or "Could not resolve mechanism."))
                        return

                parser = MechanismParser(RMIPConfig(db_path=db_path))
                mech_id = parser.parse(mech_path, name=mech_name)
                G = GraphBuilder(db_path).build_graph(mech_id, include_reverse_edges=False,
                                                       include_spring=False)
                reducer = reducer_cls(db_path)

                retained_sp, retained_rx = set(), set()
                for cond in conditions:
                    result = reducer.reduce(
                        mech_id=mech_id, G=G, target_species=target_species,
                        epsilon_range=[eps], condition=cond, mech_path=yaml_path, save_db=True,
                    )
                    step = result.steps[-1]
                    retained_sp.update(step.retained_species)
                    retained_rx.update(step.retained_reactions)

                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "union_reduced_species.txt").write_text("\n".join(sorted(retained_sp)))
                (out_dir / "union_reduced_reactions.txt").write_text("\n".join(sorted(retained_rx)))

                def _done():
                    self._status.set(f"Reduction done: {len(conditions)} condition(s) → "
                                      f"union {len(retained_sp)} species, {len(retained_rx)} reactions")
                    messagebox.showinfo("Reduction done",
                        f"{len(conditions)} condition(s) reduced; union: {len(retained_sp)} species, "
                        f"{len(retained_rx)} reactions retained.\nWritten to {out_dir}")
                self.root.after(0, _done)
            except Exception as exc:
                self.root.after(0, lambda e=exc: messagebox.showerror("Reduction failed", str(e)))

        threading.Thread(target=_worker, daemon=True).start()
        self._status.set(f"Running {method} reduction across {len(conditions)} condition(s)…")

    # ── Tab: Forward UQ ───────────────────────────────────────────────────────

    def _tab_forwarduq(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="Forward UQ")
        f = self._scrolled(outer)
        ttk.Label(f, text="Forward Uncertainty Quantification (PRS surrogates)",
                  font=FONTS["header"]).pack(anchor=tk.W, padx=12, pady=6)
        ttk.Label(f, text="Propagates Arrhenius parameter uncertainties through the trained PRS "
                  "to obtain the full distribution of combustion observables.",
                  foreground=PALETTE["text_dim"], wraplength=850).pack(anchor=tk.W, padx=12)
        uq = self.cfg.setdefault("ForwardUQ", {})
        self._uq_n = tk.StringVar(value=str(uq.get("n_samples", 50000)))
        self._uq_method = tk.StringVar(value=uq.get("method", "sobol"))
        self._uq_outdir = tk.StringVar(value=uq.get("output_dir", "outputs/forward_uq"))
        self._uq_ci = tk.StringVar(value=str(uq.get("ci_level", 0.95)))
        self._field(f, "QMC sample count", self._uq_n,
                    tip="50000 recommended. More = tighter CI, but not faster than 1 PRS eval.")
        self._field(f, "Sampling method", self._uq_method,
                    choices=["sobol", "lhs", "random"],
                    tip="sobol = quasi-Monte Carlo (most efficient for high-D).")
        self._field(f, "Output directory", self._uq_outdir, browse_dir=True)
        self._field(f, "Confidence interval level", self._uq_ci,
                    tip="0.95 = 95% CI on outputs. Plot shows [2.5%, 97.5%] bounds.")

        # ── Run / results panel ──────────────────────────────────────────
        ttk.Separator(f, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12, pady=10)
        run_row = ttk.Frame(f)
        run_row.pack(anchor=tk.W, padx=12)
        ttk.Button(run_row, text="▶  Run Forward UQ",
                   command=self._run_forward_uq).pack(side=tk.LEFT, padx=(0,8))
        ttk.Button(run_row, text="📂  Open output folder",
                   command=self._open_uq_outdir).pack(side=tk.LEFT, padx=(0,8))
        ttk.Button(run_row, text="🖼  View output plots",
                   command=self._view_uq_plots).pack(side=tk.LEFT)

        self._uq_status = tk.StringVar(value="")
        ttk.Label(f, textvariable=self._uq_status, foreground="#a6e3a1",
                  wraplength=850).pack(anchor=tk.W, padx=12, pady=(4,0))

        # scrollable results text
        res_frame = ttk.LabelFrame(f, text="Results summary", padding=4)
        res_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
        uq_scroll = tk.Scrollbar(res_frame)
        uq_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._uq_result_text = tk.Text(
            res_frame, height=10,
            yscrollcommand=uq_scroll.set,
            font=("DejaVu Sans Mono", 8),
            bg=PALETTE["surface"], fg=PALETTE["text"],
            relief=tk.FLAT, state=tk.DISABLED,
        )
        self._uq_result_text.pack(fill=tk.BOTH, expand=True)
        uq_scroll.config(command=self._uq_result_text.yview)

        self._add_tab_buttons(outer, 10)

    # ── Tab: Experimental Data (Task: consolidated import + type reference) ───

    def _tab_experimental_data(self, nb):
        """Single home for experimental-dataset import (CSV or XML), the
        target_type reference, AND the .target row-editing grid.

        Import and row-building used to live in two separate tabs
        ("Experimental Data" and "Targets") which covered overlapping ground
        — CSV import in particular was duplicated in both. They're merged
        here: reference table -> CSV import -> XML import -> the full
        row-editing grid -> Save/Generate, all in one place.
        """
        outer = ttk.Frame(nb)
        nb.add(outer, text="Experimental Data")
        f = self._scrolled(outer)

        ttk.Label(f, text="Experimental Data Import", font=FONTS["header"]
                  ).pack(anchor=tk.W, padx=12, pady=8)
        ttk.Label(f,
                  text="Import experimental datasets here, then finish building rows "
                       "(fuel/T/P/phi/observed value) below.",
                  foreground=PALETTE["text_dim"], wraplength=900).pack(anchor=tk.W, padx=12)

        self._section(f, "Target / Simulation Types Supported")
        ref = tk.Text(f, height=len(TARGET_TYPES) + 1, wrap=tk.WORD,
                      background=PALETTE["entry_bg"], foreground=PALETTE["text"],
                      font=FONTS["mono_small"], relief=tk.FLAT, borderwidth=0)
        for ttype, desc in TARGET_TYPES.items():
            ref.insert(tk.END, f"{ttype:8s} {desc}\n")
        ref.configure(state="disabled")
        ref.pack(fill=tk.X, padx=12, pady=(2, 8))

        self._section(f, "Import from CSV")
        ttk.Label(f, text="Add rows directly to the Target Builder from a CSV file "
                          "(columns matching the .target row fields).",
                  foreground=PALETTE["text_dim"], wraplength=900).pack(anchor=tk.W, padx=12)
        csv_btn = ttk.Button(f, text="Import CSV …", command=self._import_target_csv)
        csv_btn.pack(anchor=tk.W, padx=12, pady=4)
        self._hoverable(csv_btn, "Import experimental data rows from a CSV file into the grid below")

        self._section(f, "Import from XML (RKD / ReSpecTh)")
        ttk.Label(f, text="Convert a folder of RKD/ReSpecTh XML files into .target/.add rows "
                          "via the xml2csv converter.",
                  foreground=PALETTE["text_dim"], wraplength=900).pack(anchor=tk.W, padx=12)
        xml_frame = ttk.Frame(f)
        xml_frame.pack(fill=tk.X, padx=12, pady=4)
        self._import_xml_dataset(parent=xml_frame)

        # ── Target File Builder (.target row-editing grid) ──────────────────
        self._section(f, "Experimental Target File Builder (.target)")
        ttk.Label(f,
                  text="Each row = one experimental data point. The file is read by MUQ-SAC "
                       "(run_script.py). Rows are written in the pipe-delimited .target format.\n"
                       "Tip: use 'Import CSV' above to bulk-load data from a spreadsheet export.",
                  foreground=PALETTE["text_dim"], wraplength=900).pack(anchor=tk.W, padx=12)

        ctrl = ttk.Frame(f)
        ctrl.pack(fill=tk.X, padx=12, pady=4)
        ttk.Button(ctrl, text="+ Add row", command=self._add_row_new).pack(side=tk.LEFT, padx=3)
        ttk.Button(ctrl, text="Import CSV …", command=self._import_target_csv).pack(side=tk.LEFT, padx=3)
        ttk.Button(ctrl, text="Clear all", command=self._clear_trows).pack(side=tk.LEFT, padx=3)

        # Header
        hdr = ttk.Frame(f)
        hdr.pack(fill=tk.X, padx=12)
        cols = [("Dataset ID", 14), ("Type", 8), ("Fuel sp.", 10), ("Fuel xf", 7),
                ("Ox sp.", 7), ("Ox xf", 6), ("Bath sp.", 8), ("Bath xf", 6),
                ("T (K)", 8), ("P", 7), ("P unit", 7), ("phi", 6),
                ("Observed", 9), ("Dev (%)", 7), ("Wt", 4)]
        for col, w in cols:
            ttk.Label(hdr, text=col, width=w, relief=tk.RIDGE, anchor=tk.CENTER).pack(side=tk.LEFT)

        # Pagination nav — only the current page's rows are ever materialized
        # as Tk widgets (up to 100 at a time); the full dataset lives in
        # self._target_df. This is what fixes the freeze on large imports.
        nav = ttk.Frame(f)
        nav.pack(fill=tk.X, padx=12, pady=(2, 0))
        self._target_prev_btn = ttk.Button(nav, text="◀ Prev", command=self._target_page_prev)
        self._target_prev_btn.pack(side=tk.LEFT)
        self._target_page_lbl = ttk.Label(nav, text="No rows loaded")
        self._target_page_lbl.pack(side=tk.LEFT, padx=8)
        self._target_next_btn = ttk.Button(nav, text="Next ▶", command=self._target_page_next)
        self._target_next_btn.pack(side=tk.LEFT)
        ttk.Button(nav, text="Page size …", command=self._target_choose_page_size).pack(side=tk.LEFT, padx=12)

        self._target_frame = ttk.Frame(f)
        self._target_frame.pack(fill=tk.BOTH, expand=True, padx=12)

        bot = ttk.Frame(f)
        bot.pack(fill=tk.X, padx=12, pady=6)
        self._target_out = tk.StringVar(value="targets/targets.target")
        ttk.Label(bot, text="Save to:").pack(side=tk.LEFT)
        ttk.Entry(bot, textvariable=self._target_out, width=40).pack(side=tk.LEFT, padx=4)
        ttk.Button(bot, text="Browse", command=lambda: self._target_out.set(
            filedialog.asksaveasfilename(defaultextension=".target") or self._target_out.get()
        )).pack(side=tk.LEFT)
        ttk.Button(bot, text="Generate .target file",
                   command=self._generate_target).pack(side=tk.LEFT, padx=8)

        self._add_tab_buttons(outer, 2)

    # Defaults used only when a brand-new blank row is added via "+ Add row"
    # (rows coming from an import always have every _TARGET_ROW_COLUMNS key
    # present already, via _target_df_load's reindex).
    _TARGET_ROW_DEFAULTS = {
        "dataset_id": "dataset_001", "target_type": "Tig",
        "fuel_species": "H2", "fuel_xf": "0.29",
        "oxidizer_species": "O2", "ox_xf": "0.14",
        "bath_species": "AR", "bath_xf": "0.57",
        "T": "1200.0", "P": "1.0", "P_unit": "atm", "phi": "N/A",
        "observed": "100.0", "deviation_pct": "10", "data_weight": "10",
        "max_simulation_time": "", "temp_target_class": "",
    }

    def _add_trow(self, data: dict = None, abs_idx: int = None):
        """Build one widget-row. Only ever called with ≤ page-size rows at a
        time by _target_render_page — the DataFrame (self._target_df) is the
        source of truth for the full dataset, not these widgets.
        """
        d = data or {}
        row = ttk.Frame(self._target_frame)
        row.pack(fill=tk.X, pady=1)
        fields = [
            ("dataset_id", 14, d.get("dataset_id") or "dataset_001"),
            ("target_type", 8, d.get("target_type") or "Tig"),
            ("fuel_species", 10, d.get("fuel_species") or "H2"),
            ("fuel_xf", 7, d.get("fuel_xf") or "0.29"),
            ("oxidizer_species", 7, d.get("oxidizer_species") or "O2"),
            ("ox_xf", 6, d.get("ox_xf") or "0.14"),
            ("bath_species", 8, d.get("bath_species") or "AR"),
            ("bath_xf", 6, d.get("bath_xf") or "0.57"),
            ("T", 8, d.get("T") or "1200.0"),
            ("P", 7, d.get("P") or "1.0"),
            ("P_unit", 7, d.get("P_unit") or "atm"),
            ("phi", 6, d.get("phi") or "N/A"),
            ("observed", 9, d.get("observed") or "100.0"),
            ("deviation_pct", 7, d.get("deviation_pct") or "10"),
            ("data_weight", 4, d.get("data_weight") or "10"),
        ]
        vars_ = {}
        for key, w, default in fields:
            v = tk.StringVar(value=str(default))
            if key == "target_type":
                cb = ttk.Combobox(row, textvariable=v, values=list(TARGET_TYPES.keys()),
                                   width=w - 1, state="normal")
                cb.pack(side=tk.LEFT)
                self._hoverable(cb, TARGET_TYPES.get(v.get(), ""))
                cb.bind("<<ComboboxSelected>>",
                        lambda e, cb=cb: self._hoverable(cb, TARGET_TYPES.get(cb.get(), "")))
            elif key == "fuel_species":
                # Task 3: pick from the fuel-blend table (Files & Paths tab) instead
                # of retyping a species name here.
                fuel_names = list(self._fuel_registry.keys()) or [str(default)]
                cb = ttk.Combobox(row, textvariable=v, values=fuel_names, width=w - 1, state="normal")
                cb.pack(side=tk.LEFT)

                def _on_fuel_pick(event, v=v, vars_=vars_):
                    info = self._fuel_registry.get(v.get())
                    if info and info.get("xf") and "fuel_xf" in vars_:
                        vars_["fuel_xf"].set(info["xf"])
                cb.bind("<<ComboboxSelected>>", _on_fuel_pick)
            else:
                ttk.Entry(row, textvariable=v, width=w).pack(side=tk.LEFT)
            vars_[key] = v
        self._remove_row_button(
            row, lambda r=row, vs=vars_, ai=abs_idx: self._rm_trow(r, vs, ai)
        ).pack(side=tk.LEFT)
        self._target_rows.append((row, vars_, abs_idx))

    def _target_total_pages(self) -> int:
        n = len(self._target_df)
        if n == 0:
            return 1
        return -(-n // self._target_page_size)  # ceil division

    def _target_render_page(self):
        """Destroy the currently-materialized widget-rows and rebuild only
        the current page's worth (≤ page_size, capped at 100) from
        self._target_df. This is the actual fix for the freeze on large
        imports — file parsing was never the bottleneck, Tk widget count was.
        """
        for row, _, _ in self._target_rows:
            row.destroy()
        self._target_rows = []

        n = len(self._target_df)
        total_pages = self._target_total_pages()
        self._target_page_idx = max(0, min(self._target_page_idx, total_pages - 1))
        start = self._target_page_idx * self._target_page_size
        end = min(start + self._target_page_size, n)

        for i in range(start, end):
            self._add_trow(self._target_df.iloc[i].to_dict(), abs_idx=i)

        if n:
            self._target_page_lbl.config(
                text=f"Page {self._target_page_idx + 1}/{total_pages}  (rows {start + 1}-{end} of {n})")
        else:
            self._target_page_lbl.config(text="No rows loaded")
        self._target_prev_btn.config(state=("normal" if self._target_page_idx > 0 else "disabled"))
        self._target_next_btn.config(
            state=("normal" if self._target_page_idx < total_pages - 1 else "disabled"))

    def _target_flush_page_to_df(self):
        """Write the current page's widget values back into self._target_df
        before navigating away (page change, row add/remove, .target
        generation) — otherwise in-place edits on the visible page are lost.
        """
        for _, vs, abs_idx in self._target_rows:
            if abs_idx is None:
                continue
            for k, v in vs.items():
                self._target_df.at[abs_idx, k] = v.get()

    def _target_page_prev(self):
        self._target_flush_page_to_df()
        if self._target_page_idx > 0:
            self._target_page_idx -= 1
        self._target_render_page()

    def _target_page_next(self):
        self._target_flush_page_to_df()
        if self._target_page_idx < self._target_total_pages() - 1:
            self._target_page_idx += 1
        self._target_render_page()

    def _target_choose_page_size(self):
        """Ask 10/20/50/100 only (cap enforced by offering no free-text entry)."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Rows per page")
        dlg.configure(bg=PALETTE["surface"])
        dlg.transient(self.root)
        dlg.grab_set()
        ttk.Label(dlg, text="How many rows to show per page? (cap: 100)"
                  ).pack(padx=16, pady=(14, 6))
        choice = tk.IntVar(value=self._target_page_size)
        for n in (10, 20, 50, 100):
            ttk.Radiobutton(dlg, text=str(n), variable=choice, value=n).pack(anchor=tk.W, padx=28)

        def _apply():
            self._target_flush_page_to_df()
            self._target_page_size = choice.get()
            self._target_page_idx = 0
            dlg.destroy()
            self._target_render_page()

        ttk.Button(dlg, text="OK", command=_apply).pack(pady=12)
        dlg.wait_window()

    def _target_df_load(self, df: "pd.DataFrame"):
        """Load a full dataset into self._target_df (vectorized, one-shot) and
        render only the first page as widgets.
        """
        df = df.reindex(columns=_TARGET_ROW_COLUMNS, fill_value="")
        df = df.fillna("").astype(str)
        self._target_df = df.reset_index(drop=True)
        self._target_page_idx = 0
        self._target_render_page()

    def _add_row_new(self):
        """+ Add row: append one blank row to the DataFrame and jump to it."""
        self._target_flush_page_to_df()
        new_row = pd.DataFrame([self._TARGET_ROW_DEFAULTS], columns=_TARGET_ROW_COLUMNS)
        self._target_df = pd.concat([self._target_df, new_row], ignore_index=True)
        self._target_page_idx = self._target_total_pages() - 1
        self._target_render_page()

    def _rm_trow(self, row, vs, abs_idx):
        self._target_flush_page_to_df()
        if abs_idx is not None and abs_idx in self._target_df.index:
            self._target_df = self._target_df.drop(index=abs_idx).reset_index(drop=True)
        self._target_render_page()

    def _clear_trows(self, confirm=True):
        if confirm and self._target_rows and not messagebox.askyesno(
            "Clear all", "Remove all experimental-data rows? This cannot be undone."
        ):
            return
        for row, _, _ in self._target_rows:
            row.destroy()
        self._target_rows = []
        self._target_df = pd.DataFrame(columns=_TARGET_ROW_COLUMNS)
        self._target_page_idx = 0
        self._target_render_page()

    def _import_target_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All", "*")])
        if not path:
            return
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        self._target_choose_page_size()
        self._target_df_load(df)
        self._status.set(f"Imported {path} ({len(df)} rows, {self._target_page_size}/page)")

    def _generate_target(self):
        self._target_flush_page_to_df()
        if not self._target_df.empty:
            self._prompt_httltt_split()
        rows = []
        for d in self._target_df.to_dict("records"):
            d = dict(d)
            d.pop("max_simulation_time", None)
            d.pop("temp_target_class", None)
            dev_pct = float(d.pop("deviation_pct", 10) or 10)
            obs = float(d.get("observed", 100) or 100)
            d["deviation"] = obs * dev_pct / 100.0
            rows.append(d)
        if not rows:
            messagebox.showwarning("Empty", "Add at least one data point first.")
            return
        path = self._target_out.get()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        generate_target_file(rows, path)
        self._write_httltt_addendum_overrides(self._add_out.get())
        self._loc_targets.set(path)
        self._status.set(f"Saved: {path}  ({len(rows)} data points)")
        messagebox.showinfo("Done", f"Target file written:\n{path}\n({len(rows)} points)")

    def _prompt_httltt_split(self):
        """Optional pre-write step: let the user split this dataset's rows into
        HTT (high-temperature target) / LTT (low-temperature target) by a
        manual T threshold, each with its own MaxSimulationTime. This is a
        GUI-only convenience, independent of RMIP's algorithmic NTC-onset-based
        HTT/LTT detector (src/rmip/analysis/ntc_detector.py) — cancel at any
        point skips tagging entirely.
        """
        if not messagebox.askyesno(
            "HTT/LTT MaxSimulationTime",
            "Split this dataset into HTT (high-T) / LTT (low-T) targets with "
            "different MaxSimulationTime values?\n\n"
            "Choose 'No' to skip and generate the .target file as-is."
        ):
            return
        t_split = simpledialog.askfloat(
            "HTT/LTT split", "Temperature threshold (K) — rows above this are HTT, below are LTT:",
            initialvalue=1000.0)
        if t_split is None:
            return
        htt_val = simpledialog.askfloat("HTT MaxSimulationTime", "MaxSimulationTime (s) for HTT rows:",
                                          initialvalue=0.4, minvalue=0.0)
        if htt_val is None:
            return
        ltt_val = simpledialog.askfloat("LTT MaxSimulationTime", "MaxSimulationTime (s) for LTT rows:",
                                          initialvalue=10.0, minvalue=0.0)
        if ltt_val is None:
            return
        self._apply_httltt_split(t_split, htt_val, ltt_val)

    def _apply_httltt_split(self, t_split: float, htt_val: float, ltt_val: float):
        t_numeric = pd.to_numeric(self._target_df["T"], errors="coerce")
        is_htt = t_numeric > t_split
        self._target_df.loc[is_htt, "temp_target_class"] = "HTT"
        self._target_df.loc[~is_htt, "temp_target_class"] = "LTT"
        self._target_df.loc[is_htt, "max_simulation_time"] = str(htt_val)
        self._target_df.loc[~is_htt, "max_simulation_time"] = str(ltt_val)
        self._target_render_page()
        self._status.set(f"HTT/LTT split applied at T={t_split} K "
                          f"({int(is_htt.sum())} HTT, {int((~is_htt).sum())} LTT rows)")

    def _write_httltt_addendum_overrides(self, path: str):
        """Push per-dataset_id MaxSimulationTime/temp_target_class values (set
        by _apply_httltt_split, if any) into the .add YAML addendum file — the
        .target row format has no such field, so these live in the addendum,
        keyed by dataset_id (matching generate_addendum_file's contract).
        """
        tagged = self._target_df[self._target_df["max_simulation_time"].astype(str).str.len() > 0]
        if tagged.empty:
            return
        content = {}
        if path and os.path.isfile(path):
            try:
                with open(path) as fh:
                    content = yaml.safe_load(fh) or {}
            except Exception:
                content = {}
        for _, row in tagged.iterrows():
            did = row["dataset_id"]
            entry = content.get(did) or {}
            entry["MaxSimulationTime"] = float(row["max_simulation_time"])
            if row.get("temp_target_class"):
                entry["temp_target_class"] = row["temp_target_class"]
            content[did] = entry
        # Also keep the Addendum tab's own live rows in sync, if a row for
        # this dataset_id already exists there (so the on-screen UI and the
        # .add file on disk don't silently diverge).
        for _, vs in self._add_rows:
            did = vs.get("dataset_id")
            if did and did.get() in content:
                if "MaxSimulationTime" in vs:
                    vs["MaxSimulationTime"].set(str(content[did.get()]["MaxSimulationTime"]))
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as fh:
                yaml.dump(content, fh, default_flow_style=False, sort_keys=False)

    # ── Tab: Target Workbench ────────────────────────────────────────────────

    @staticmethod
    def _muqsac_src_on_path():
        """Ensure src/MUQ-SAC/ (VisualAid.py, combustion_target_class.py,
        Dummy_data_generation.py, ...) and src/ (mso_io, target_sampling.py)
        are importable. MUQ-SAC modules import siblings by bare name, so
        both must be on sys.path -- see VisualAid.py's own top-of-file note
        for why src/ is appended (never inserted at 0, to avoid shadowing
        stdlib) while src/MUQ-SAC/ is inserted at the front (matching how
        run_script.py itself is always executed with that directory first)."""
        root = os.path.dirname(os.path.abspath(__file__))
        muqsac_dir = os.path.join(root, "src", "MUQ-SAC")
        src_dir = os.path.join(root, "src")
        if muqsac_dir not in sys.path:
            sys.path.insert(0, muqsac_dir)
        if src_dir not in sys.path:
            sys.path.append(src_dir)

    def _tab_target_workbench(self, nb):
        """Curate a .target/.add pair before it reaches Addendum: plot,
        sanity-check, generate NTC-aware dummy points, prune for T/P/phi
        coverage, then write a new versioned .target/.add -- never mutates
        the source files (see mso_io.target_add_io.write_curated_set).

        Entirely optional (see _validate_tab's tab_index==3 branch) --
        skipping this tab leaves the Experimental Data tab's own .target/.add
        untouched and Addendum proceeds exactly as it always has.
        """
        outer = ttk.Frame(nb)
        nb.add(outer, text="Target Workbench")
        f = self._scrolled(outer)

        ttk.Label(f, text="Target Workbench", font=FONTS["header"]
                  ).pack(anchor=tk.W, padx=12, pady=8)
        ttk.Label(f,
                  text="Optional curation pass over the .target/.add pair from the "
                       "Experimental Data tab: plot it, run sanity checks, generate "
                       "NTC-aware dummy points, prune for coverage, then write a new "
                       "version. Nothing here is written until you click 'Write new "
                       "version' below, and the source file is never modified.",
                  foreground=PALETTE["text_dim"], wraplength=900).pack(anchor=tk.W, padx=12)

        self._twb_target_path = tk.StringVar(value="")
        self._twb_add_path = tk.StringVar(value="")
        self._twb_ts = None            # loaded VisualAid.TargetSet
        self._twb_dummy_rows = []      # list[pd.Series] staged, not yet written
        self._twb_dummy_template = {}  # dataset_id -> source TargetRow (composition donor)
        self._twb_dropped = set()      # staged line_no drops
        self._twb_findings = []

        self._section(f, "Source .target / .add")
        src_row = ttk.Frame(f)
        src_row.pack(fill=tk.X, padx=12, pady=4)
        ttk.Label(src_row, text="Uses the same files as the Experimental Data tab "
                                 "(Locations.targets / Locations.addendum) by default.",
                  foreground=PALETTE["text_dim"]).pack(anchor=tk.W)
        load_row = ttk.Frame(f)
        load_row.pack(fill=tk.X, padx=12, pady=4)
        ttk.Button(load_row, text="Load from Experimental Data tab",
                   command=self._twb_load_from_experimental_data).pack(side=tk.LEFT, padx=3)
        ttk.Button(load_row, text="Load .target/.add …",
                   command=self._twb_load_dialog).pack(side=tk.LEFT, padx=3)
        self._twb_status = tk.StringVar(value="Not loaded.")
        ttk.Label(f, textvariable=self._twb_status, foreground=PALETTE["text_dim"]
                  ).pack(anchor=tk.W, padx=12, pady=(0, 6))

        self._section(f, "Rows")
        row_ctrl = ttk.Frame(f)
        row_ctrl.pack(fill=tk.X, padx=12, pady=4)
        ttk.Button(row_ctrl, text="Mark selected as dropped",
                   command=self._twb_mark_dropped).pack(side=tk.LEFT, padx=3)
        ttk.Button(row_ctrl, text="Undrop selected",
                   command=self._twb_undrop).pack(side=tk.LEFT, padx=3)

        cols = ("line_no", "dataset_id", "target_type", "T", "P", "phi",
                 "observed", "deviation", "weight", "status")
        self._twb_tree = ttk.Treeview(f, columns=cols, show="headings", height=12,
                                       selectmode="extended")
        for c, w in zip(cols, (55, 200, 80, 70, 60, 60, 80, 80, 60, 90)):
            self._twb_tree.heading(c, text=c)
            self._twb_tree.column(c, width=w, anchor=tk.W)
        self._twb_tree.tag_configure("dropped", foreground="#f38ba8")
        self._twb_tree.tag_configure("dummy", foreground="#f9c74f")
        self._twb_tree.pack(fill=tk.BOTH, expand=False, padx=12, pady=4)

        self._section(f, "Checks")
        chk_row = ttk.Frame(f)
        chk_row.pack(fill=tk.X, padx=12, pady=4)
        ttk.Button(chk_row, text="Run checks", command=self._twb_run_checks).pack(side=tk.LEFT, padx=3)
        self._twb_findings_tree = ttk.Treeview(
            f, columns=("severity", "line_no", "dataset_id", "check", "message"),
            show="headings", height=8)
        for c, w in zip(("severity", "line_no", "dataset_id", "check", "message"),
                         (70, 55, 200, 130, 420)):
            self._twb_findings_tree.heading(c, text=c)
            self._twb_findings_tree.column(c, width=w, anchor=tk.W)
        self._twb_findings_tree.tag_configure("error", foreground="#f38ba8")
        self._twb_findings_tree.tag_configure("warning", foreground="#f9c74f")
        self._twb_findings_tree.tag_configure("info", foreground=PALETTE["text_dim"])
        self._twb_findings_tree.pack(fill=tk.BOTH, expand=False, padx=12, pady=4)

        self._section(f, "Plots")
        plot_row = ttk.Frame(f)
        plot_row.pack(fill=tk.X, padx=12, pady=4)
        self._twb_plot_kind = tk.StringVar(value="T-P-dataset")
        ttk.Combobox(plot_row, textvariable=self._twb_plot_kind, state="readonly",
                     values=["T-P-dataset", "ln(tau) vs 1000/T", "observed vs deviation",
                             "condition coverage"], width=22).pack(side=tk.LEFT, padx=3)
        self._twb_plot_dataset = tk.StringVar(value="")
        self._twb_plot_dataset_combo = ttk.Combobox(
            plot_row, textvariable=self._twb_plot_dataset, state="readonly",
            values=[], width=28)
        self._twb_plot_dataset_combo.pack(side=tk.LEFT, padx=3)
        ttk.Button(plot_row, text="Show plot", command=self._twb_show_plot).pack(side=tk.LEFT, padx=3)
        self._twb_plot_frame = ttk.Frame(f)
        self._twb_plot_frame.pack(fill=tk.BOTH, expand=False, padx=12, pady=4)

        self._section(f, "Generate dummy points")
        dummy_row = ttk.Frame(f)
        dummy_row.pack(fill=tk.X, padx=12, pady=4)
        ttk.Button(dummy_row, text="Generate dummy points …",
                   command=self._twb_generate_dummy_dialog).pack(side=tk.LEFT, padx=3)
        self._twb_dummy_status = tk.StringVar(value="No dummy points staged.")
        ttk.Label(f, textvariable=self._twb_dummy_status, foreground=PALETTE["text_dim"]
                  ).pack(anchor=tk.W, padx=12)

        self._section(f, "Suggest prunable rows")
        prune_row = ttk.Frame(f)
        prune_row.pack(fill=tk.X, padx=12, pady=4)
        ttk.Button(prune_row, text="Suggest prunable rows (coverage) …",
                   command=self._twb_prune_dialog).pack(side=tk.LEFT, padx=3)

        self._section(f, "Write new version")
        ttk.Label(f,
                  text="Writes a new <stem>_v<N>.target + .add (never overwrites the "
                       "source). Runs the combustion_target parser gate immediately "
                       "after writing and reports any row that fails to parse.",
                  foreground=PALETTE["text_dim"], wraplength=900).pack(anchor=tk.W, padx=12)
        write_row = ttk.Frame(f)
        write_row.pack(fill=tk.X, padx=12, pady=4)
        self._twb_out_stem = tk.StringVar(value="targets_curated")
        ttk.Entry(write_row, textvariable=self._twb_out_stem, width=30).pack(side=tk.LEFT, padx=3)
        ttk.Button(write_row, text="Write new .target + .add",
                   command=self._twb_write).pack(side=tk.LEFT, padx=3)
        self._twb_write_status = tk.StringVar(value="")
        ttk.Label(f, textvariable=self._twb_write_status, foreground=PALETTE["text_dim"],
                  wraplength=900).pack(anchor=tk.W, padx=12, pady=(0, 8))

        self._add_tab_buttons(outer, 3)

    def _twb_load_from_experimental_data(self):
        self._twb_target_path.set(self._loc_targets.get())
        self._twb_add_path.set(self._loc_add.get())
        self._twb_do_load()

    def _twb_load_dialog(self):
        tpath = filedialog.askopenfilename(title="Select .target file",
                                            filetypes=[("target files", "*.target"), ("all", "*.*")])
        if not tpath:
            return
        self._twb_target_path.set(tpath)
        apath = filedialog.askopenfilename(title="Select .add file (optional)",
                                            filetypes=[("add files", "*.add"), ("all", "*.*")])
        self._twb_add_path.set(apath or "")
        self._twb_do_load()

    def _twb_do_load(self):
        tpath = self._twb_target_path.get()
        if not tpath or not os.path.isfile(tpath):
            messagebox.showwarning("Target Workbench", "No .target file selected/found.")
            return
        try:
            self._muqsac_src_on_path()
            import VisualAid as _VA
            self._twb_VA = _VA
            apath = self._twb_add_path.get() or None
            self._twb_ts = _VA.TargetSet(tpath, apath)
        except Exception as exc:
            messagebox.showerror("Target Workbench", f"Failed to load: {exc}")
            return
        self._twb_dummy_rows = []
        self._twb_dummy_template = {}
        self._twb_dropped = set()
        self._twb_findings = []
        self._twb_refresh_tree()
        ds_ids = self._twb_ts.dataset_ids()
        for w in self._twb_plot_frame.winfo_children():
            w.destroy()
        self._twb_status.set(f"Loaded {len(self._twb_ts)} rows, {len(ds_ids)} dataset(s) "
                              f"from {tpath}")
        self._twb_plot_dataset_combo.configure(values=ds_ids)
        if ds_ids:
            self._twb_plot_dataset.set(ds_ids[0])

    def _twb_refresh_tree(self):
        for item in self._twb_tree.get_children():
            self._twb_tree.delete(item)
        if not self._twb_ts:
            return
        for r in self._twb_ts.rows:
            status = "dropped" if r.line_no in self._twb_dropped else "ok"
            tag = "dropped" if r.line_no in self._twb_dropped else ()
            self._twb_tree.insert("", tk.END, iid=str(r.line_no), values=(
                r.line_no, r.dataset_id, r.target_type, r.temperature_K, r.pressure_atm,
                r.phi_raw, r.observed, r.deviation, r.data_weight, status), tags=(tag,) if tag else ())
        for i, row in enumerate(self._twb_dummy_rows):
            tag = "dummy"
            self._twb_tree.insert("", tk.END, iid=f"dummy-{i}", values=(
                "-", row.get("dataset_ID"), "Tig", round(float(row.get("Temperature_K", 0)), 1),
                "-", "-", round(float(row.get("observed", 0)), 3), "-", "-", "dummy (staged)"),
                tags=(tag,))

    def _twb_mark_dropped(self):
        for iid in self._twb_tree.selection():
            if iid.isdigit():
                self._twb_dropped.add(int(iid))
        self._twb_refresh_tree()

    def _twb_undrop(self):
        for iid in self._twb_tree.selection():
            if iid.isdigit():
                self._twb_dropped.discard(int(iid))
        self._twb_refresh_tree()

    def _twb_run_checks(self):
        if not self._twb_ts:
            messagebox.showwarning("Target Workbench", "Load a .target file first.")
            return
        add_data = {}
        apath = self._twb_add_path.get()
        if apath and os.path.isfile(apath):
            try:
                import yaml as _yaml
                add_data = _yaml.safe_load(open(apath)) or {}
            except Exception:
                add_data = {}
        checker = self._twb_VA.TargetChecker(self._twb_ts, add_data)
        self._twb_findings = checker.run_all()
        for item in self._twb_findings_tree.get_children():
            self._twb_findings_tree.delete(item)
        for finding in self._twb_findings:
            self._twb_findings_tree.insert("", tk.END, values=(
                finding.severity, finding.line_no or "-", finding.dataset_id,
                finding.check, finding.message), tags=(finding.severity,))
        n_err = sum(1 for x in self._twb_findings if x.severity == "error")
        n_warn = sum(1 for x in self._twb_findings if x.severity == "warning")
        self._twb_status.set(f"Checks: {n_err} error(s), {n_warn} warning(s), "
                              f"{len(self._twb_findings) - n_err - n_warn} info")

    def _twb_show_plot(self):
        if not self._twb_ts:
            messagebox.showwarning("Target Workbench", "Load a .target file first.")
            return
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            messagebox.showinfo("Target Workbench", "matplotlib not found — install it to plot.")
            return
        for w in self._twb_plot_frame.winfo_children():
            w.destroy()
        plotter = self._twb_VA.TargetSetPlotter(self._twb_ts)
        kind = self._twb_plot_kind.get()
        tmp_path = os.path.join(self.cfg.get("project", {}).get("output_base_dir", ".") or ".",
                                 "_twb_plot_tmp.png")
        try:
            os.makedirs(os.path.dirname(tmp_path) or ".", exist_ok=True)
            if kind == "T-P-dataset":
                plotter.plot_t_p_phi(save_path=tmp_path)
            elif kind == "ln(tau) vs 1000/T":
                ds = self._twb_plot_dataset.get() or (self._twb_ts.dataset_ids()[0] if len(self._twb_ts) else None)
                if not ds:
                    messagebox.showinfo("Target Workbench", "No dataset selected.")
                    return
                plotter.plot_lntau_vs_invT(ds, dropped_line_nos=self._twb_dropped, save_path=tmp_path)
            elif kind == "observed vs deviation":
                plotter.plot_observed_vs_deviation(save_path=tmp_path)
            else:
                plotter.plot_condition_coverage(save_path=tmp_path)
        except Exception as exc:
            messagebox.showerror("Target Workbench", f"Plot failed: {exc}")
            return
        try:
            from PIL import Image, ImageTk
            img = Image.open(tmp_path)
            img.thumbnail((760, 520))
            photo = ImageTk.PhotoImage(img)
            lbl = ttk.Label(self._twb_plot_frame, image=photo)
            lbl.image = photo
            lbl.pack()
        except ImportError:
            ttk.Label(self._twb_plot_frame,
                      text=f"Plot saved to {tmp_path} (install Pillow to preview inline).",
                      foreground=PALETTE["text_dim"]).pack()

    def _twb_generate_dummy_dialog(self):
        if not self._twb_ts:
            messagebox.showwarning("Target Workbench", "Load a .target file first.")
            return
        ds_ids = self._twb_ts.dataset_ids()
        if not ds_ids:
            messagebox.showinfo("Target Workbench", "No datasets loaded.")
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Generate dummy points")
        dlg.configure(bg=PALETTE["surface"])
        dlg.transient(self.root)
        dlg.grab_set()
        ttk.Label(dlg, text="Dataset:").pack(anchor=tk.W, padx=10, pady=(10, 2))
        ds_var = tk.StringVar(value=ds_ids[0])
        ttk.Combobox(dlg, textvariable=ds_var, state="readonly", values=ds_ids, width=40
                     ).pack(padx=10, pady=2)
        ttk.Label(dlg, text="Points per zone (before/NTC/after):").pack(anchor=tk.W, padx=10, pady=(8, 2))
        n_var = tk.IntVar(value=10)
        ttk.Entry(dlg, textvariable=n_var, width=10).pack(padx=10, pady=2, anchor=tk.W)

        def do_generate():
            try:
                gen = self._twb_VA.DummyPointGenerator(self._twb_ts, ds_var.get())
                out = gen.generate(points_per_zone=int(n_var.get()))
            except Exception as exc:
                messagebox.showerror("Target Workbench", f"Dummy generation failed: {exc}")
                return
            template = gen.template_row
            self._twb_dummy_template[out["dataset_ID"].iloc[0]] = template
            for _, row in out.iterrows():
                self._twb_dummy_rows.append(row)
            self._twb_dummy_status.set(f"{len(self._twb_dummy_rows)} dummy point(s) staged.")
            self._twb_refresh_tree()
            dlg.destroy()

        ttk.Button(dlg, text="Generate", command=do_generate).pack(pady=10)

    def _twb_prune_dialog(self):
        if not self._twb_ts:
            messagebox.showwarning("Target Workbench", "Load a .target file first.")
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Suggest prunable rows")
        dlg.configure(bg=PALETTE["surface"])
        dlg.transient(self.root)
        dlg.grab_set()
        ttk.Label(dlg, text=f"Rows to drop (of {len(self._twb_ts)}):").pack(anchor=tk.W, padx=10, pady=(10, 2))
        n_var = tk.IntVar(value=max(1, len(self._twb_ts) // 10))
        ttk.Entry(dlg, textvariable=n_var, width=10).pack(padx=10, pady=2, anchor=tk.W)
        result_var = tk.StringVar(value="")
        ttk.Label(dlg, textvariable=result_var, foreground=PALETTE["text_dim"], wraplength=380
                  ).pack(padx=10, pady=8)

        def do_suggest():
            try:
                pruner = self._twb_VA.TargetPruner(self._twb_ts)
                keep, drop, cov = pruner.coverage_prune(n_drop=int(n_var.get()), seed=0)
            except Exception as exc:
                messagebox.showerror("Target Workbench", f"Prune failed: {exc}")
                return
            result_var.set(f"Suggests dropping {len(drop)} row(s), keeping coverage={cov:.2%}. "
                            f"Click Apply to stage these drops (nothing written yet).")
            dlg._twb_suggested_drop = drop

        def do_apply():
            drop = getattr(dlg, "_twb_suggested_drop", None)
            if drop is None:
                messagebox.showinfo("Target Workbench", "Click Suggest first.")
                return
            self._twb_dropped.update(drop)
            self._twb_refresh_tree()
            dlg.destroy()

        btn_row = ttk.Frame(dlg)
        btn_row.pack(pady=6)
        ttk.Button(btn_row, text="Suggest", command=do_suggest).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Apply", command=do_apply).pack(side=tk.LEFT, padx=4)

    def _twb_write(self):
        if not self._twb_ts:
            messagebox.showwarning("Target Workbench", "Load a .target file first.")
            return
        keep = [r.line_no for r in self._twb_ts.rows if r.line_no not in self._twb_dropped]

        new_cases = []
        if self._twb_dummy_rows:
            try:
                from mso_io.target_add_schema import NewCaseFields
            except ImportError:
                self._muqsac_src_on_path()
                from mso_io.target_add_schema import NewCaseFields
            for row in self._twb_dummy_rows:
                ds_full = row["dataset_ID"]
                orig_ds = ds_full[len("dummy_"):] if ds_full.startswith("dummy_") else ds_full
                template = self._twb_dummy_template.get(ds_full)
                if template is None:
                    matches = self._twb_ts.rows_for(orig_ds)
                    template = matches[0] if matches else None
                fuel = dict(template.fuel) if template else {}
                oxidizer_items = list(template.oxidizer.items()) if template else [("O2", 1.0)]
                bath = dict(template.bath_gas) if template else {}
                solver = template.solver if template else "cantera"
                new_cases.append(NewCaseFields(
                    dataset_id=ds_full, target_type="Tig",
                    simulation="Isochor Homo Reactor", solver=solver,
                    temperature_K=float(row["Temperature_K"]), pressure_atm=(
                        template.pressure_atm if template and template.pressure_atm else 1.0),
                    fuel=fuel or {"H2": 1.0},
                    oxidizer=oxidizer_items[0][0] if oxidizer_items else "O2",
                    oxidizer_x=oxidizer_items[0][1] if oxidizer_items else 1.0,
                    bath_gas=bath or {"Ar": 1.0},
                    phi="N/A", observed=float(row["observed"]), deviation=0.0,
                    data_weight=(template.data_weight if template and template.data_weight else 1.0),
                    species="OH"))

        reason_log = [{"action": "drop", "line_no": ln} for ln in sorted(self._twb_dropped)]
        reason_log += [{"action": "generate_dummy", "dataset_id": r["dataset_ID"],
                         "temperature_K": float(r["Temperature_K"])}
                        for r in self._twb_dummy_rows]
        for finding in self._twb_findings:
            if finding.suggested_fix:
                reason_log.append({"action": "finding", "check": finding.check,
                                    "line_no": finding.line_no,
                                    "suggested_fix": finding.suggested_fix})

        try:
            from mso_io.target_add_io import write_curated_set
        except ImportError:
            self._muqsac_src_on_path()
            from mso_io.target_add_io import write_curated_set

        out_dir = os.path.dirname(self._twb_target_path.get()) or "."
        try:
            new_target, new_add, log_path = write_curated_set(
                self._twb_target_path.get(), self._twb_add_path.get() or os.path.join(out_dir, "empty.add"),
                self._twb_out_stem.get() or "targets_curated", keep, new_cases=new_cases,
                reason_log=reason_log, out_dir=out_dir)
        except Exception as exc:
            messagebox.showerror("Target Workbench", f"Write failed: {exc}")
            return

        # Gate: reload the WRITTEN file and run the authoritative parser over
        # every row before telling the user it succeeded.
        try:
            ts2 = self._twb_VA.TargetSet(new_target, new_add)
            checker2 = self._twb_VA.TargetChecker(ts2)
            gate_findings = checker2.check_parses()
            gate_errors = [x for x in gate_findings if x.severity == "error"]
        except Exception as exc:
            gate_errors = [f"reload failed: {exc}"]

        if gate_errors:
            self._twb_write_status.set(
                f"Wrote {new_target} but {len(gate_errors)} row(s) failed the "
                f"combustion_target parser gate -- inspect before using it:\n" +
                "\n".join(str(e) for e in gate_errors[:5]))
            messagebox.showwarning("Target Workbench",
                                    "Written, but some rows failed to parse -- see status text.")
            return

        self._twb_write_status.set(
            f"Wrote {new_target}, {new_add}, {log_path} "
            f"({len(keep)} kept + {len(new_cases)} new = {len(ts2)} rows). "
            f"All rows pass the combustion_target parser gate.")
        messagebox.showinfo("Target Workbench",
                             f"Wrote new version:\n{new_target}\n{new_add}\n\n"
                             f"Point the Experimental Data / Addendum tabs at these "
                             f"if you want the pipeline to use the curated set.")

    # ── Tab: Addendum Builder ─────────────────────────────────────────────────

    def _tab_addendum_builder(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="Addendum")

        ttk.Label(outer, text="Addendum File Builder (.add)",
                  font=FONTS["header"]).pack(anchor=tk.W, padx=12, pady=6)
        ttk.Label(outer,
                  text="The .add (addendum) file is a YAML file that maps each dataset_id "
                       "to solver-specific settings: which solver to use, how to define ignition "
                       "delay, molecular weight, RCM volume profiles, JSR residence time, etc.",
                  foreground=PALETTE["text_dim"], wraplength=900).pack(anchor=tk.W, padx=12)

        ctrl = ttk.Frame(outer)
        ctrl.pack(fill=tk.X, padx=12, pady=4)
        ttk.Button(ctrl, text="+ Add dataset entry", command=self._add_arow).pack(side=tk.LEFT, padx=3)

        hdr = ttk.Frame(outer)
        hdr.pack(fill=tk.X, padx=12)
        for col, w in [("Dataset ID", 18), ("Solver", 12), ("Target type", 10), ("MaxSimulationTime", 10)]:
            ttk.Label(hdr, text=col, width=w, relief=tk.RIDGE, anchor=tk.CENTER).pack(side=tk.LEFT)
        ttk.Label(hdr, text="Type-specific fields (change with 'Target type' above) →",
                  foreground=PALETTE["text_dim"]).pack(side=tk.LEFT, padx=6)

        self._add_frame = ttk.Frame(outer)
        self._add_frame.pack(fill=tk.BOTH, expand=True, padx=12)

        bot = ttk.Frame(outer)
        bot.pack(fill=tk.X, padx=12, pady=6)
        self._add_out = tk.StringVar(value="targets/targets.add")
        ttk.Label(bot, text="Save to:").pack(side=tk.LEFT)
        ttk.Entry(bot, textvariable=self._add_out, width=40).pack(side=tk.LEFT, padx=4)
        ttk.Button(bot, text="Browse", command=lambda: self._add_out.set(
            filedialog.asksaveasfilename(defaultextension=".add") or self._add_out.get()
        )).pack(side=tk.LEFT)
        ttk.Button(bot, text="Generate .add file",
                   command=self._generate_add).pack(side=tk.LEFT, padx=8)

        self._add_tab_buttons(outer, 4)

    # Widget kind for each type-specific field (used by _add_arow's dynamic
    # per-target_type field area). Anything not listed defaults to a plain Entry.
    _ADDENDUM_FIELD_CHOICES = {
        "ign_delay_def": ["OH*", "p", "CHV", "T"],
        "ign_cond":      ["onset", "max", "min"],
        "flux_analysis": ["", "yes"],
        "RCM_type":      ["reactive", "non_reactive"],
        "flw_method":    ["decay", "rate"],
    }

    def _add_arow(self, data: dict = None):
        d = data or {}
        row = ttk.Frame(self._add_frame)
        row.pack(fill=tk.X, pady=1)
        vs = {}

        fixed_fields = [
            ("dataset_id", 18, d.get("dataset_id", "dataset_001")),
            ("solver", 12, d.get("solver", "cantera")),
            ("target_type", 10, d.get("target_type", "Tig")),
            ("MaxSimulationTime", 10, d.get("MaxSimulationTime", "")),
        ]
        for key, w, default in fixed_fields:
            v = tk.StringVar(value=str(default))
            if key == "solver":
                ttk.Combobox(row, textvariable=v, values=["cantera", "FlameMaster", "CHEMKIN_PRO"],
                             width=w - 1, state="readonly").pack(side=tk.LEFT)
            elif key == "target_type":
                cb = ttk.Combobox(row, textvariable=v, values=list(TARGET_TYPES.keys()),
                                   width=w - 1, state="readonly")
                cb.pack(side=tk.LEFT)
                self._hoverable(cb, TARGET_TYPES.get(v.get(), ""))
                cb.bind("<<ComboboxSelected>>",
                        lambda e, cb=cb: (self._hoverable(cb, TARGET_TYPES.get(cb.get(), "")),
                                          self._rebuild_addendum_extra_fields(row)))
            else:
                ttk.Entry(row, textvariable=v, width=w).pack(side=tk.LEFT)
            vs[key] = v

        extra_frame = ttk.Frame(row)
        extra_frame.pack(side=tk.LEFT)
        row._extra_frame = extra_frame
        row._extra_vars = {}       # fname -> StringVar, created lazily, kept across type switches
        row._extra_widgets = {}    # fname -> (label, entry) frame, packed/unpacked, never destroyed
        row._extra_seed = d        # initial values for type-specific fields loaded from a save file
        self._remove_row_button(
            row, lambda r=row, vs_=vs: self._rm_arow(r, vs_)
        ).pack(side=tk.LEFT)
        self._add_rows.append((row, vs))
        self._rebuild_addendum_extra_fields(row)

    def _rebuild_addendum_extra_fields(self, row):
        """Show only the fields relevant to the row's currently-selected target_type.

        Fields are created once per row (lazily) and kept alive across type
        switches (pack/pack_forget) so a value typed in isn't lost if the user
        flips target_type back and forth while editing.
        """
        ttype = None
        for r, vs in self._add_rows:
            if r is row:
                ttype = vs["target_type"].get()
                break
        if ttype is None:
            return
        wanted = TARGET_TYPE_FIELDS.get(ttype, [])
        for fname, (lbl, ent) in row._extra_widgets.items():
            if fname not in wanted:
                lbl.pack_forget()
                ent.pack_forget()
        for fname in wanted:
            if fname not in row._extra_vars:
                default = row._extra_seed.get(fname, "")
                row._extra_vars[fname] = tk.StringVar(value=str(default))
            if fname not in row._extra_widgets:
                lbl = ttk.Label(row._extra_frame, text=fname, width=len(fname) + 1,
                                 foreground=PALETTE["text_dim"])
                choices = self._ADDENDUM_FIELD_CHOICES.get(fname)
                if choices:
                    ent = ttk.Combobox(row._extra_frame, textvariable=row._extra_vars[fname],
                                        values=choices, width=8)
                else:
                    ent = ttk.Entry(row._extra_frame, textvariable=row._extra_vars[fname], width=10)
                row._extra_widgets[fname] = (lbl, ent)
            lbl, ent = row._extra_widgets[fname]
            lbl.pack(side=tk.LEFT, padx=(4, 0))
            ent.pack(side=tk.LEFT)

    def _rm_arow(self, row, vs):
        row.destroy()
        self._add_rows = [(r, v) for r, v in self._add_rows if r != row]

    def _generate_add(self):
        datasets = []
        for row, vs in self._add_rows:
            d = {k: v.get() for k, v in vs.items()}
            d.update({k: v.get() for k, v in getattr(row, "_extra_vars", {}).items()})
            datasets.append(d)
        if not datasets:
            messagebox.showwarning("Empty", "Add at least one dataset entry first.")
            return
        path = self._add_out.get()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        generate_addendum_file(datasets, path)
        self._loc_add.set(path)
        self._status.set(f"Saved: {path}  ({len(datasets)} entries)")
        messagebox.showinfo("Done", f"Addendum file written:\n{path}")

    # ── Tab: Reaction Screening (RMIP comparison / SA -> Uncertainty XML) ──────

    def _tab_reaction_screening(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="Reaction Screening")
        f = self._scrolled(outer)

        ttk.Label(f, text="Reaction Screening", font=FONTS["header"]
                  ).pack(anchor=tk.W, padx=12, pady=8)
        ttk.Label(f,
                  text="Decide which reactions need an uncertainty factor by running an RMIP "
                       "kinetics/thermo comparison across mechanisms, or a Sensitivity Analysis "
                       "on one mechanism — then filter by carbon number and push the survivors "
                       "to the Uncertainty XML tab.",
                  foreground=PALETTE["text_dim"], wraplength=900).pack(anchor=tk.W, padx=12)

        self._rs_mode = tk.StringVar(value="sa")
        mode_row = ttk.Frame(f)
        mode_row.pack(anchor=tk.W, padx=12, pady=6)
        ttk.Radiobutton(mode_row, text="Run RMIP kinetics/thermo comparison", value="comparison",
                         variable=self._rs_mode, command=self._rs_switch_mode).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Radiobutton(mode_row, text="Run Sensitivity Analysis", value="sa",
                         variable=self._rs_mode, command=self._rs_switch_mode).pack(side=tk.LEFT)

        # Stable holder packed once, right here — _rs_switch_mode toggles which
        # child is shown inside it without disturbing the sections below.
        self._rs_mode_holder = ttk.Frame(f)
        self._rs_mode_holder.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # ── Comparison branch ────────────────────────────────────────────────
        self._rs_cmp_frame = ttk.Frame(self._rs_mode_holder)
        self._section(self._rs_cmp_frame, "Mechanisms to compare (≥ 2)")
        self._rs_cmp_container = ttk.Frame(self._rs_cmp_frame)
        self._rs_cmp_container.pack(fill=tk.X, padx=12)
        self._rs_cmp_checks = []
        for nv, pv, tv, trv, fv, glv, prv in self._mech_rows:
            if pv.get():
                cv = tk.BooleanVar(value=False)
                ttk.Checkbutton(self._rs_cmp_container, text=nv.get() or pv.get(),
                                 variable=cv).pack(anchor=tk.W)
                self._rs_cmp_checks.append((cv, nv, pv, fv, glv))
        ttk.Button(self._rs_cmp_frame, text="Run comparison",
                   command=self._rs_run_comparison).pack(anchor=tk.W, padx=12, pady=4)

        # ── SA branch ─────────────────────────────────────────────────────────
        self._rs_sa_frame = ttk.Frame(self._rs_mode_holder)
        self._section(self._rs_sa_frame, "Sensitivity Analysis conditions")
        sa_mech_row = ttk.Frame(self._rs_sa_frame)
        sa_mech_row.pack(fill=tk.X, padx=12, pady=2)
        ttk.Label(sa_mech_row, text="Mechanism", width=30, anchor=tk.W).pack(side=tk.LEFT)
        mech_names = [nv.get() or pv.get() for nv, pv, tv, trv, fv, glv, prv in self._mech_rows if pv.get()]
        self._rs_sa_mech = tk.StringVar(value=mech_names[0] if mech_names else "")
        ttk.Combobox(sa_mech_row, textvariable=self._rs_sa_mech, values=mech_names,
                     width=38, state="readonly" if mech_names else "disabled").pack(side=tk.LEFT)

        self._field(self._rs_sa_frame, "Fuel", self._sa_fuel)
        self._field(self._rs_sa_frame, "T (K)", self._sa_T)
        self._field(self._rs_sa_frame, "P (atm)", self._sa_P)
        self._field(self._rs_sa_frame, "phi (equivalence ratio)", self._sa_phi)
        self._field(self._rs_sa_frame, "Output dir", self._sa_out, browse_dir=True)

        sa_btn_row = ttk.Frame(self._rs_sa_frame)
        sa_btn_row.pack(anchor=tk.W, padx=12, pady=4)
        ttk.Button(sa_btn_row, text="Run SA (sens_3_params.py — full terminal)",
                   command=self._rs_run_sa_terminal).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(sa_btn_row, text="Quick SA (Cantera, in-process)",
                   command=self._rs_run_sa_quick).pack(side=tk.LEFT)

        self._section(self._rs_sa_frame, "Live output")
        term_frame = ttk.Frame(self._rs_sa_frame)
        term_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        self._rs_terminal = PtyTerminal(term_frame, rows=16, cols=110)
        self._rs_terminal.pack(fill=tk.BOTH, expand=True)
        if not _HAS_PTY_TERMINAL:
            ttk.Label(self._rs_sa_frame, text="⚠ pyte not installed — run: pip install pyte",
                      foreground="orange").pack(anchor=tk.W, padx=12)

        self._rs_switch_mode()

        # ── Reaction list + carbon filter (shared by both branches) ─────────
        self._section(f, "Reactions (filtered by carbon number)")
        filt_row = ttk.Frame(f)
        filt_row.pack(anchor=tk.W, padx=12, pady=2)
        ttk.Label(filt_row, text="Carbon number ≥").pack(side=tk.LEFT)
        self._rs_carbon = tk.StringVar(value="0")
        ttk.Spinbox(filt_row, from_=0, to=30, textvariable=self._rs_carbon, width=5,
                    command=self._rs_apply_carbon_filter).pack(side=tk.LEFT, padx=4)
        ttk.Button(filt_row, text="Apply filter", command=self._rs_apply_carbon_filter
                   ).pack(side=tk.LEFT, padx=8)

        self._rs_reaction_frame = ttk.Frame(f)
        self._rs_reaction_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        self._rs_reaction_checks = []   # (BooleanVar, rxn_name)
        self._rs_all_reactions = []     # [(name, carbon, ref_number, ref_label)] from the last run
        self._rs_mech_yaml = None       # resolved on-disk YAML for the last run's mechanism

        ttk.Button(f, text="Add selected to Uncertainty XML",
                   command=self._rs_add_selected_to_xml).pack(anchor=tk.W, padx=12, pady=8)

        self._add_tab_buttons(outer, 5)

    def _rs_switch_mode(self):
        if self._rs_mode.get() == "comparison":
            self._rs_sa_frame.pack_forget()
            self._rs_cmp_frame.pack(fill=tk.X, padx=0, pady=4)
        else:
            self._rs_cmp_frame.pack_forget()
            self._rs_sa_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=4)

    def _rs_resolve_mechanism_yaml(self, path, thermo, trans, fmt):
        """Resolve a mechanism row to an on-disk Cantera YAML path, converting
        from CHEMKIN via Part D's convert_mechanism_files() if needed."""
        if fmt == "cantera_yaml":
            return path, []
        yaml_path, pre_path, errors = convert_mechanism_files(
            path, thermo, trans, out_dir=str(Path(path).parent),
            scanman_bin=self._bin_solver.get() if hasattr(self, "_bin_solver") else None,
        )
        return yaml_path, errors

    def _rs_run_comparison(self):
        selected = [(nv.get() or pv.get(), pv.get(), glv.get()) for cv, nv, pv, fv, glv in self._rs_cmp_checks if cv.get()]
        if len(selected) < 2:
            messagebox.showwarning("Select mechanisms", "Check at least 2 mechanisms to compare.")
            return

        def _worker():
            try:
                _rmip_src_on_path()
                from rmip.config import RMIPConfig
                from rmip.core.parser import MechanismParser
                from rmip.analysis.graph_comparator import GraphComparator
                db_path = self._rmip_db.get() or "project.db"
                parser = MechanismParser(RMIPConfig(db_path=db_path))
                mech_ids = []
                for name, path, glossary in selected:
                    mech_id = parser.parse(path, glossary_path=glossary or None, name=name)
                    mech_ids.append(mech_id)
                cmp = GraphComparator(db_path)
                result = cmp.compare(mech_ids)
                reactions = []
                for rc in result.reaction_classifications:
                    if rc.classification.value == "SHARED_DIVERGENT" and rc.min_A_si and rc.max_A_si:
                        spread = rc.max_A_si / rc.min_A_si if rc.min_A_si > 0 else 0.0
                        reactions.append((rc.formula_string, spread, f"A-spread={spread:.2f}x"))
                self.root.after(0, lambda: self._rs_on_reactions_ready(reactions, self._rs_sa_mech.get()))
            except Exception as e:
                self.root.after(0, lambda e=e: messagebox.showerror("Comparison failed", str(e)))

        threading.Thread(target=_worker, daemon=True).start()
        self._status.set("Running RMIP comparison…")

    def _rs_run_sa_quick(self):
        mech_name = self._rs_sa_mech.get()
        row = next(((pv.get(), fv.get(), tv.get(), trv.get()) for nv, pv, tv, trv, fv, glv, prv
                    in self._mech_rows if (nv.get() or pv.get()) == mech_name), None)
        if not row:
            messagebox.showwarning("No mechanism", "Pick a mechanism first.")
            return
        path, fmt, thermo, trans = row

        def _worker():
            yaml_path, errors = self._rs_resolve_mechanism_yaml(path, thermo, trans, fmt)
            if not yaml_path:
                self.root.after(0, lambda: messagebox.showerror(
                    "Conversion failed", "\n".join(errors) or "Could not resolve a YAML mechanism."))
                return
            try:
                _rmip_src_on_path()
                from rmip.simulation.sensitivity_runner import CanteraSensitivityRunner
                runner = CanteraSensitivityRunner()
                data = runner.run_idt(
                    yaml_path, T_K=float(self._sa_T.get() or 1200.0), P_atm=float(self._sa_P.get() or 1.0),
                    phi=float(self._sa_phi.get() or 1.0), fuel=self._sa_fuel.get(),
                )
                reactions = [(eq, abs(coeff), f"|SA|={abs(coeff):.4f}")
                             for eq, coeff in data.get("coefficients", {}).items()]
                self.root.after(0, lambda: self._rs_on_reactions_ready(reactions, mech_name))
            except Exception as e:
                self.root.after(0, lambda e=e: messagebox.showerror("Quick SA failed", str(e)))

        threading.Thread(target=_worker, daemon=True).start()
        self._status.set("Running Quick SA (Cantera)…")

    def _rs_run_sa_terminal(self):
        mech_name = self._rs_sa_mech.get()
        row = next(((pv.get(), fv.get()) for nv, pv, tv, trv, fv, glv, prv
                    in self._mech_rows if (nv.get() or pv.get()) == mech_name), None)
        if not row:
            messagebox.showwarning("No mechanism", "Pick a mechanism first.")
            return
        path, fmt = row
        out_dir = self._sa_out.get() or "outputs/sa"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        cfg = deepcopy(self._collect())
        cfg["Locations"]["mechanism"] = path
        target_opt_path = str(Path(out_dir) / "target.opt")
        Path(target_opt_path).write_text(config_to_yaml(cfg))
        script = str(Path(__file__).resolve().parent / "src" / "Sensitivity_Analysis" / "sens_3_params.py")
        self._rs_terminal.run([sys.executable, script, target_opt_path], cwd=out_dir)
        self._status.set(f"SA running in embedded terminal (cwd={out_dir})…")

    def _rs_on_reactions_ready(self, reactions, mech_name):
        """reactions: list of (rxn_name, ref_number, ref_label)."""
        row = next(((pv.get(), fv.get(), tv.get(), trv.get()) for nv, pv, tv, trv, fv, glv, prv
                    in self._mech_rows if (nv.get() or pv.get()) == mech_name), None)
        carbon_map = {}
        if row:
            path, fmt, thermo, trans = row
            yaml_path, errors = self._rs_resolve_mechanism_yaml(path, thermo, trans, fmt)
            if yaml_path:
                try:
                    _rmip_src_on_path()
                    from modules.mechanism_utils import load_mechanism, build_species_carbon_map
                    src_dir = str(Path(__file__).resolve().parent / "src")
                    if src_dir not in sys.path:
                        sys.path.insert(0, src_dir)
                    mech = load_mechanism(yaml_path)
                    carbon_map = build_species_carbon_map(mech)
                    self._rs_mech_yaml = yaml_path
                except Exception:
                    carbon_map = {}
        self._rs_carbon_map = carbon_map
        self._rs_all_reactions = []
        for name, ref_number, ref_label in reactions:
            carbon = 0
            for sp, c in carbon_map.items():
                if sp in name and c > carbon:
                    carbon = c
            self._rs_all_reactions.append((name, carbon, ref_number, ref_label))
        self._status.set(f"{len(self._rs_all_reactions)} reactions ready — apply the carbon filter below.")
        self._rs_apply_carbon_filter()

    def _rs_apply_carbon_filter(self):
        for w in self._rs_reaction_frame.winfo_children():
            w.destroy()
        self._rs_reaction_checks = []
        try:
            threshold = int(float(self._rs_carbon.get() or 0))
        except ValueError:
            threshold = 0
        for name, carbon, ref_number, ref_label in self._rs_all_reactions:
            if carbon < threshold:
                continue
            row = ttk.Frame(self._rs_reaction_frame)
            row.pack(fill=tk.X, anchor=tk.W)
            cv = tk.BooleanVar(value=False)
            ttk.Checkbutton(row, text=name, variable=cv, width=55).pack(side=tk.LEFT)
            ttk.Label(row, text=f"C={carbon}  {ref_label}", foreground=PALETTE["text_dim"]).pack(side=tk.LEFT, padx=8)
            self._rs_reaction_checks.append((cv, name))
        if not self._rs_all_reactions:
            ttk.Label(self._rs_reaction_frame,
                      text="(Run a comparison or SA above to populate this list.)",
                      foreground=PALETTE["text_dim"]).pack(anchor=tk.W)

    def _rs_add_selected_to_xml(self):
        selected = [name for cv, name in self._rs_reaction_checks if cv.get()]
        if not selected:
            messagebox.showwarning("Nothing selected", "Check at least one reaction first.")
            return
        for name in selected:
            self._add_xrow(rxn_name=name, rxn_type="pressure_independent", const_u="")
        self._status.set(f"Added {len(selected)} reaction(s) to the Uncertainty XML tab.")
        self._select_tab_by_text("Uncertainty XML")

    # ── Tab: Uncertainty XML Builder ──────────────────────────────────────────

    def _tab_xml_builder(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="Uncertainty XML")

        ttk.Label(outer, text="Uncertainty XML File Builder (.xml)",
                  font=FONTS["header"]).pack(anchor=tk.W, padx=12, pady=6)
        ttk.Label(outer,
                  text="The uncertainty XML stores temperature-dependent uncertainty factors "
                       "(σ_ln k) for each reaction. MUQ-SAC uses these as Cholesky covariance "
                       "inputs. Each reaction needs a comma-separated list of T values and "
                       "matching σ values (same length).\n"
                       "Tip: paste T,σ arrays from a spreadsheet. Constant uncertainty: "
                       "enter one T range and one constant σ, click 'Fill constant'.",
                  foreground=PALETTE["text_dim"], wraplength=900).pack(anchor=tk.W, padx=12)

        ctrl = ttk.Frame(outer)
        ctrl.pack(fill=tk.X, padx=12, pady=4)
        ttk.Button(ctrl, text="+ Add reaction", command=self._add_xrow).pack(side=tk.LEFT, padx=3)
        ttk.Button(ctrl, text="Load from existing XML …", command=self._load_xml).pack(side=tk.LEFT, padx=3)

        # Reactions list
        hdr = ttk.Frame(outer)
        hdr.pack(fill=tk.X, padx=12)
        for col, w in [("Reaction (e.g. H+O2<=>O+OH)", 38), ("Type", 20),
                       ("Constant σ (or leave blank)", 20)]:
            ttk.Label(hdr, text=col, width=w, relief=tk.RIDGE).pack(side=tk.LEFT)

        self._xml_list_frame = ttk.Frame(outer)
        self._xml_list_frame.pack(fill=tk.BOTH, padx=12, pady=2)

        # Selected reaction editor
        self._section(outer, "Temperature / Uncertainty Array for Selected Reaction")
        ttk.Label(outer,
                  text="T (comma-separated, K):", foreground=PALETTE["text_dim"]).pack(anchor=tk.W, padx=12)
        self._xml_T_box = scrolledtext.ScrolledText(outer, height=3, width=100,
                                                    font=FONTS["mono_small"])
        style_text_widget(self._xml_T_box)
        self._xml_T_box.pack(fill=tk.X, padx=12, pady=2)
        ttk.Label(outer, text="σ_lnk (comma-separated, same length as T):",
                  foreground=PALETTE["text_dim"]).pack(anchor=tk.W, padx=12)
        self._xml_u_box = scrolledtext.ScrolledText(outer, height=3, width=100,
                                                    font=FONTS["mono_small"])
        style_text_widget(self._xml_u_box)
        self._xml_u_box.pack(fill=tk.X, padx=12, pady=2)

        fill_frame = ttk.Frame(outer)
        fill_frame.pack(fill=tk.X, padx=12, pady=2)
        ttk.Label(fill_frame, text="Fill constant: T_min").pack(side=tk.LEFT)
        self._xml_fill_tmin = tk.StringVar(value="500")
        self._xml_fill_tmax = tk.StringVar(value="2500")
        self._xml_fill_n = tk.StringVar(value="50")
        self._xml_fill_u = tk.StringVar(value="0.3")
        ttk.Entry(fill_frame, textvariable=self._xml_fill_tmin, width=7).pack(side=tk.LEFT)
        ttk.Label(fill_frame, text="T_max").pack(side=tk.LEFT)
        ttk.Entry(fill_frame, textvariable=self._xml_fill_tmax, width=7).pack(side=tk.LEFT)
        ttk.Label(fill_frame, text="N points").pack(side=tk.LEFT)
        ttk.Entry(fill_frame, textvariable=self._xml_fill_n, width=5).pack(side=tk.LEFT)
        ttk.Label(fill_frame, text="σ value").pack(side=tk.LEFT)
        ttk.Entry(fill_frame, textvariable=self._xml_fill_u, width=7).pack(side=tk.LEFT)
        ttk.Button(fill_frame, text="Fill →", command=self._fill_xml_const).pack(side=tk.LEFT, padx=4)

        bot = ttk.Frame(outer)
        bot.pack(fill=tk.X, padx=12, pady=6)
        self._xml_out = tk.StringVar(value="uncertainty/uncertainty.xml")
        ttk.Label(bot, text="Save to:").pack(side=tk.LEFT)
        ttk.Entry(bot, textvariable=self._xml_out, width=44).pack(side=tk.LEFT, padx=4)
        ttk.Button(bot, text="Browse", command=lambda: self._xml_out.set(
            filedialog.asksaveasfilename(defaultextension=".xml") or self._xml_out.get()
        )).pack(side=tk.LEFT)
        ttk.Button(bot, text="Generate .xml file",
                   command=self._generate_xml).pack(side=tk.LEFT, padx=8)

        self._add_tab_buttons(outer, 6)

    def _add_xrow(self, rxn_name="", rxn_type="pressure_independent", const_u=""):
        row = ttk.Frame(self._xml_list_frame)
        row.pack(fill=tk.X, pady=1)
        nv = tk.StringVar(value=rxn_name)
        tv = tk.StringVar(value=rxn_type)
        cv = tk.StringVar(value=const_u)
        ttk.Entry(row, textvariable=nv, width=38).pack(side=tk.LEFT)
        ttk.Combobox(row, textvariable=tv,
                     values=["pressure_independent", "pressure_dependent"],
                     width=19, state="readonly").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=cv, width=20).pack(side=tk.LEFT)
        ttk.Button(row, text="Select", width=7,
                   command=lambda n=nv, t=tv, c=cv: self._select_xrow(n, t, c)).pack(side=tk.LEFT, padx=2)
        self._remove_row_button(
            row, lambda r=row, d=(nv, tv, cv): self._rm_xrow(r, d)
        ).pack(side=tk.LEFT)
        self._xml_rows.append((nv, tv, cv, row))

    def _rm_xrow(self, row, d):
        row.destroy()
        self._xml_rows = [(n, t, c, r) for n, t, c, r in self._xml_rows if r != row]

    def _select_xrow(self, nv, tv, cv):
        self._current_xml_row = (nv, tv, cv)
        # Populate T/u boxes if there was a previous save (stored in cv comment)
        self._xml_T_box.delete("1.0", tk.END)
        self._xml_u_box.delete("1.0", tk.END)
        self._status.set(f"Editing: {nv.get()}")

    def _fill_xml_const(self):
        try:
            import numpy as np
            tmin = float(self._xml_fill_tmin.get())
            tmax = float(self._xml_fill_tmax.get())
            n = int(self._xml_fill_n.get())
            u_val = float(self._xml_fill_u.get())
            T_arr = np.linspace(tmin, tmax, n)
            T_str = ",".join(f"{t:.3f}" for t in T_arr)
            u_str = ",".join([str(u_val)] * n)
        except Exception:
            N = int(self._xml_fill_n.get() or 10)
            tmin = float(self._xml_fill_tmin.get() or 500)
            tmax = float(self._xml_fill_tmax.get() or 2500)
            step = (tmax - tmin) / max(N - 1, 1)
            T_arr = [tmin + i * step for i in range(N)]
            u_val = float(self._xml_fill_u.get() or 0.3)
            T_str = ",".join(f"{t:.3f}" for t in T_arr)
            u_str = ",".join([str(u_val)] * N)
        self._xml_T_box.delete("1.0", tk.END)
        self._xml_T_box.insert("1.0", T_str)
        self._xml_u_box.delete("1.0", tk.END)
        self._xml_u_box.insert("1.0", u_str)

    def _load_xml(self):
        path = filedialog.askopenfilename(filetypes=[("XML files", "*.xml"), ("All", "*")])
        if not path:
            return
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            for r in root.findall("reaction"):
                name = r.get("rxn", "")
                rtype = r.findtext("type") or "pressure_independent"
                self._add_xrow(rxn_name=name, rxn_type=rtype)
            self._status.set(f"Loaded reactions from {path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _generate_xml(self):
        T_text = self._xml_T_box.get("1.0", tk.END).strip()
        u_text = self._xml_u_box.get("1.0", tk.END).strip()
        reactions = []
        for nv, tv, cv, _ in self._xml_rows:
            rxn = {"name": nv.get(), "type": tv.get()}
            const_u = cv.get().strip()
            if T_text and u_text:
                rxn["temperatures"] = T_text
                rxn["uncertainties"] = u_text
            elif const_u:
                rxn["temperatures"] = "500,2500"
                rxn["uncertainties"] = f"{const_u},{const_u}"
                rxn["data_mode"] = "constant;end_points"
            reactions.append(rxn)
        if not reactions:
            messagebox.showwarning("Empty", "Add at least one reaction first.")
            return
        path = self._xml_out.get()
        generate_uncertainty_xml(reactions, path)
        self._loc_unsrt.set(path)
        self._status.set(f"Saved: {path}  ({len(reactions)} reactions)")
        messagebox.showinfo("Done", f"Uncertainty XML written:\n{path}")

    # ── Tab: .so Compiler ─────────────────────────────────────────────────────

    def _tab_so_compiler(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="Compile")

        ttk.Label(outer, text="Shared-Object File Compiler",
                  font=FONTS["header"]).pack(anchor=tk.W, padx=12, pady=6)
        ttk.Label(outer,
                  text="MUQ-SAC uses three compiled .so files. Run the corresponding setup.py "
                       "from the config_tools directory using pybind11.\n"
                       "Prerequisite: pip install pybind11",
                  foreground=PALETTE["text_dim"], wraplength=900).pack(anchor=tk.W, padx=12)

        _ROOT = Path(__file__).resolve().parent
        # Primary source: config_tools/shared_libs/Shared_Objects (has all three + yaml-cpp)
        # Fallback: parallel_native subdirectories (individual setup.py per file)
        _SHARED = _ROOT / "config_tools/shared_libs/Shared_Objects"
        _PYW = _ROOT / "config_tools/parallel_native/PARALLEL_YAML_WRITER"
        _PYG = _ROOT / "config_tools/parallel_native/PARALLEL_YAML_GENERATOR"
        so_defs = [
            ("parallel_yaml_writer.so",
             _SHARED if (_SHARED / "setup.py").exists() else _PYW,
             _ROOT / "src/MUQ-SAC/parallel_yaml_writer.so",
             "Parallel YAML mechanism writer (used in run_script.py). "
             "Already compiled at src/MUQ-SAC/parallel_yaml_writer.so — recompile only if needed."),
            ("shuffle.so",
             _SHARED if (_SHARED / "setup.py").exists() else _PYG,
             _ROOT / "src/MUQ-SAC/shuffle.so",
             "Design-matrix shuffler (used in DesignMatrix.py). "
             "Already compiled at src/MUQ-SAC/shuffle.so."),
            ("yamlwriter.so",
             _SHARED,
             _ROOT / "src/MUQ-SAC/yamlwriter.so",
             "YAML writer for Sensitivity_Analysis/sens.py. "
             "Already compiled at src/MUQ-SAC/yamlwriter.so."),
        ]

        for so_name, src_dir, dst, description in so_defs:
            frame = ttk.LabelFrame(outer, text=so_name, padding=8)
            frame.pack(fill=tk.X, padx=14, pady=6)
            ttk.Label(frame, text=description, foreground=PALETTE["text_dim"]).pack(anchor=tk.W)
            row = ttk.Frame(frame)
            row.pack(fill=tk.X, pady=4)
            src_var = tk.StringVar(value=str(src_dir))
            dst_var = tk.StringVar(value=str(dst))
            ttk.Label(row, text="Source dir:", width=12).pack(side=tk.LEFT)
            ttk.Entry(row, textvariable=src_var, width=52).pack(side=tk.LEFT)
            ttk.Button(row, text="…", width=3,
                       command=lambda v=src_var: v.set(self._choose_directory(initial=v.get()) or v.get())
                       ).pack(side=tk.LEFT, padx=2)
            row2 = ttk.Frame(frame)
            row2.pack(fill=tk.X)
            ttk.Label(row2, text="Copy .so to:", width=12).pack(side=tk.LEFT)
            ttk.Entry(row2, textvariable=dst_var, width=52).pack(side=tk.LEFT)
            ttk.Button(row2, text="…", width=3,
                       command=lambda v=dst_var: v.set(
                           filedialog.asksaveasfilename(defaultextension=".so") or v.get())
                       ).pack(side=tk.LEFT, padx=2)
            log_var = tk.StringVar(value="")
            ttk.Label(frame, textvariable=log_var, foreground="blue",
                      wraplength=800).pack(anchor=tk.W)
            ttk.Button(frame, text=f"Compile & install {so_name}",
                       command=lambda sv=src_var, dv=dst_var, lv=log_var, sn=so_name:
                       self._compile_so(sv.get(), dv.get(), sn, lv)
                       ).pack(anchor=tk.W, pady=4)

        ttk.Separator(outer).pack(fill=tk.X, pady=8, padx=12)
        ttk.Label(outer, text="Manual compilation commands (run in terminal):",
                  font=FONTS["section"]).pack(anchor=tk.W, padx=12)
        manual = scrolledtext.ScrolledText(outer, height=8, font=FONTS["mono_small"], state=tk.NORMAL)
        style_text_widget(manual)
        manual.pack(fill=tk.X, padx=12, pady=4)
        manual.insert("1.0", textwrap.dedent(f"""\
            # NOTE: .so files are ALREADY COMPILED at src/MUQ-SAC/*.so
            # Only recompile if you change Python version or update the C++ source.

            # Install pybind11 first
            pip install pybind11 --break-system-packages

            # OPTION A: compile all three from config_tools/shared_libs/Shared_Objects/
            cd {_SHARED}
            python setup.py build_ext --inplace
            cp parallel_yaml_writer*.so {_ROOT}/src/MUQ-SAC/parallel_yaml_writer.so
            cp shuffle*.so {_ROOT}/src/MUQ-SAC/shuffle.so
            cp yamlwriter*.so {_ROOT}/src/MUQ-SAC/yamlwriter.so

            # OPTION B: compile individually
            cd {_PYW}
            python setup.py build_ext --inplace
            cp parallel_yaml_writer*.so {_ROOT}/src/MUQ-SAC/parallel_yaml_writer.so

            # Verify
            python -c "import sys; sys.path.insert(0,'{_ROOT}/src/MUQ-SAC'); import parallel_yaml_writer; print('OK')"
        """))
        manual.configure(state=tk.DISABLED)

        self._add_tab_buttons(outer, 11)

    def _compile_so(self, src_dir: str, dst: str, so_name: str, log_var: "tk.StringVar"):
        if not Path(src_dir).exists():
            log_var.set(f"ERROR: source dir not found: {src_dir}")
            return
        setup = Path(src_dir) / "setup.py"
        if not setup.exists():
            log_var.set(f"ERROR: no setup.py in {src_dir}")
            return
        log_var.set("Compiling… (this may take 10-30 s)")
        self.root.update()
        result = subprocess.run(
            [sys.executable, "setup.py", "build_ext", "--inplace"],
            cwd=src_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            log_var.set(f"FAILED:\n{result.stderr[-300:]}")
            return
        # Find the generated .so file
        so_files = list(Path(src_dir).glob("*.so"))
        if not so_files:
            so_files = list(Path(src_dir).rglob("*.so"))
        if not so_files:
            log_var.set("Compiled but .so file not found. Check build/ directory.")
            return
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(so_files[0]), dst)
        log_var.set(f"OK: {so_files[0].name} → {dst}")
        messagebox.showinfo("Compiled", f"{so_name} installed at:\n{dst}")

    # ── Tab: Preview ──────────────────────────────────────────────────────────

    def _tab_preview(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="Preview")
        ttk.Label(outer,
                  text="target.opt preview — click 'Generate & Preview' in toolbar to refresh",
                  foreground=PALETTE["text_dim"]).pack(anchor=tk.W, padx=12, pady=4)
        self._preview_text = scrolledtext.ScrolledText(outer, font=FONTS["mono_small"], wrap=tk.NONE)
        style_text_widget(self._preview_text)
        self._preview_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        mm_row = ttk.Frame(outer)
        mm_row.pack(fill=tk.X, padx=12, pady=(0, 8))
        ttk.Button(mm_row, text="Build All Mechanism Outputs",
                   command=self._build_multi_mechanism_outputs).pack(side=tk.LEFT)
        ttk.Label(mm_row,
                  text="Uses the workflow choice (one-at-a-time / fuse) set in the Mechanisms tab.",
                  foreground=PALETTE["text_dim"]).pack(side=tk.LEFT, padx=8)

        self._add_tab_buttons(outer, 12)

    # ── Tab: Project (mso_project viewer) ───────────────────────────────────

    @staticmethod
    def _mso_project_on_path():
        """Ensure src/ (mso_project, and its own src/MUQ-SAC dependency for
        VisualAid-adjacent bits) is importable. Follows the exact same
        append-not-insert convention as _rmip_src_on_path/
        _muqsac_src_on_path in this file."""
        import sys as _sys, os as _os
        root = _os.path.dirname(_os.path.abspath(__file__))
        src = _os.path.join(root, "src")
        if src not in _sys.path:
            _sys.path.append(src)

    def _tab_project_viewer(self, nb):
        """Read-only viewer over an mso_project Project: browse tracked
        runs/artifacts, register this session's current Locations paths,
        and trigger a report build. Deliberately read-only otherwise --
        registration/capture/resume/report-rules editing are the
        `python -m mso_project` CLI's job (see src/mso_project/cli.py);
        this tab is a window onto that data, not a second way to author it.
        """
        outer = ttk.Frame(nb)
        nb.add(outer, text="Project Tracker")
        f = self._scrolled(outer)

        ttk.Label(f, text="Project Tracker", font=FONTS["header"]
                  ).pack(anchor=tk.W, padx=12, pady=8)
        ttk.Label(f,
                  text="Browse an mso_project project's tracked runs and artifacts -- "
                       "remembers every simulation/analysis output's location no matter "
                       "which pipeline or working directory produced it. Read-only here; "
                       "use the 'python -m mso_project' CLI to register/capture/resume/"
                       "configure report rules.",
                  foreground=PALETTE["text_dim"], wraplength=900).pack(anchor=tk.W, padx=12)

        self._mso_project_on_path()
        try:
            from gui_common.settings import load_settings as _pv_load_settings
            _pv_settings = _pv_load_settings("project_viewer")
        except Exception:
            _pv_settings = {}
        self._proj_viewer_path = tk.StringVar(value=_pv_settings.get("last_project_dir", ""))
        self._proj_viewer_obj = None

        row = ttk.Frame(f)
        row.pack(fill=tk.X, padx=12, pady=4)
        ttk.Entry(row, textvariable=self._proj_viewer_path, width=60).pack(side=tk.LEFT, padx=3)
        ttk.Button(row, text="Browse…", command=self._pv_browse).pack(side=tk.LEFT, padx=3)
        ttk.Button(row, text="Open", command=self._pv_open).pack(side=tk.LEFT, padx=3)
        self._pv_status = tk.StringVar(value="Not opened.")
        ttk.Label(f, textvariable=self._pv_status, foreground=PALETTE["text_dim"]
                  ).pack(anchor=tk.W, padx=12, pady=(0, 6))

        self._section(f, "Register this session's file locations")
        reg_row = ttk.Frame(f)
        reg_row.pack(fill=tk.X, padx=12, pady=4)
        ttk.Button(reg_row, text="Register mechanism/targets/addendum paths",
                   command=self._pv_register_locations).pack(side=tk.LEFT, padx=3)

        self._section(f, "Runs")
        cols = ("run_id", "pipeline", "label", "status", "started_at")
        self._pv_runs_tree = ttk.Treeview(f, columns=cols, show="headings", height=6)
        for c, w in zip(cols, (280, 100, 140, 70, 160)):
            self._pv_runs_tree.heading(c, text=c)
            self._pv_runs_tree.column(c, width=w, anchor=tk.W)
        self._pv_runs_tree.pack(fill=tk.BOTH, expand=False, padx=12, pady=4)

        self._section(f, "Artifacts")
        acols = ("artifact_id", "role", "kind", "path")
        self._pv_artifacts_tree = ttk.Treeview(f, columns=acols, show="headings", height=10)
        for c, w in zip(acols, (60, 160, 60, 480)):
            self._pv_artifacts_tree.heading(c, text=c)
            self._pv_artifacts_tree.column(c, width=w, anchor=tk.W)
        self._pv_artifacts_tree.pack(fill=tk.BOTH, expand=False, padx=12, pady=4)

        self._section(f, "Report")
        rep_row = ttk.Frame(f)
        rep_row.pack(fill=tk.X, padx=12, pady=4)
        ttk.Button(rep_row, text="Build report", command=self._pv_build_report).pack(side=tk.LEFT, padx=3)
        self._pv_report_status = tk.StringVar(value="")
        ttk.Label(f, textvariable=self._pv_report_status, foreground=PALETTE["text_dim"],
                  wraplength=900).pack(anchor=tk.W, padx=12, pady=(0, 8))

        if self._proj_viewer_path.get():
            self._pv_open()

        self._add_tab_buttons(outer, 13)

    def _pv_browse(self):
        d = filedialog.askdirectory(title="Select or create a project directory")
        if d:
            self._proj_viewer_path.set(d)
            self._pv_open()

    def _pv_open(self):
        path = self._proj_viewer_path.get()
        if not path:
            return
        self._mso_project_on_path()
        try:
            from mso_project import Project
            import os as _os
            if _os.path.isfile(_os.path.join(path, "project.yaml")):
                self._proj_viewer_obj = Project.open(path)
            else:
                self._proj_viewer_obj = Project.create(path, name=_os.path.basename(path.rstrip("/")))
        except Exception as exc:
            messagebox.showerror("Project", f"Failed to open/create project: {exc}")
            return

        try:
            from gui_common.settings import load_settings as _ls, save_settings as _ss
            s = _ls("project_viewer")
            s["last_project_dir"] = path
            _ss("project_viewer", s)
        except Exception:
            pass

        self._pv_refresh()
        self._pv_status.set(f"Opened: {self._proj_viewer_obj.root} "
                             f"({len(self._proj_viewer_obj.list_artifacts())} artifact(s))")

    def _pv_refresh(self):
        if not self._proj_viewer_obj:
            return
        for item in self._pv_runs_tree.get_children():
            self._pv_runs_tree.delete(item)
        for r in self._proj_viewer_obj.list_runs():
            self._pv_runs_tree.insert("", tk.END, values=(
                r["run_id"], r["pipeline"], r["label"], r["status"], r["started_at"]))
        for item in self._pv_artifacts_tree.get_children():
            self._pv_artifacts_tree.delete(item)
        for a in self._proj_viewer_obj.list_artifacts():
            self._pv_artifacts_tree.insert("", tk.END, values=(
                a["artifact_id"], a["role"], a["kind"], a["path"]))

    def _pv_register_locations(self):
        if not self._proj_viewer_obj:
            messagebox.showwarning("Project", "Open a project first.")
            return
        candidates = [
            ("mechanism", self.cfg.get("Locations", {}).get("mechanism", "")),
            ("targets", self._loc_targets.get() if hasattr(self, "_loc_targets") else ""),
            ("addendum", self._loc_add.get() if hasattr(self, "_loc_add") else ""),
        ]
        n = 0
        for role, path in candidates:
            if path and os.path.isfile(path):
                self._proj_viewer_obj.register(path, role=f"gui_location_{role}")
                n += 1
        self._pv_refresh()
        self._pv_status.set(f"Registered {n} location(s) from the current session.")

    def _pv_build_report(self):
        if not self._proj_viewer_obj:
            messagebox.showwarning("Project", "Open a project first.")
            return
        self._mso_project_on_path()
        try:
            from mso_project.report import build_report
            result = build_report(self._proj_viewer_obj)
        except Exception as exc:
            messagebox.showerror("Project", f"Report build failed: {exc}")
            return
        self._pv_report_status.set(
            f"Main: {result.main_tex}"
            + (f" (PDF: {result.main_pdf})" if result.main_pdf else " (not compiled)")
            + f"\nSupplementary: {result.supplementary_tex}"
            + (f" (PDF: {result.supplementary_pdf})" if result.supplementary_pdf else " (not compiled)"))

    # ── Collect configuration from all widgets ────────────────────────────────

    def _collect(self) -> dict:
        cfg = deepcopy(DEFAULT_CONFIG)

        cfg["project"].update({
            "name": self._proj_name.get(),
            "fuel_name": self._proj_fuel.get(),
            "fuel_formula": self._proj_formula.get(),
            "output_base_dir": self._proj_outdir.get(),
        })
        cfg["Type"].update({
            "optimization_type": self._opt_type.get(),
            "Algorithm_type": self._alg_type.get(),
            "Algorithm": self._alg.get(),
        })
        cfg["Counts"].update({
            "total_reactions": int(self._n_rxn.get() or 10),
            "parallel_threads": int(self._n_thr.get() or 4),
            "targets_count": int(self._n_tar.get() or 20),
        })
        cfg["SA"]["carbon_number"] = int(self._carbon_n.get() or 0)

        cfg["Bin"].update({
            "bin": self._bin_muqsac.get(),
            "solver_bin": self._bin_solver.get(),
            "yaml_writer": self._bin_yaml.get(),
            "samap_executable": self._bin_samap.get(),
            "jpdap_executable": self._bin_jpdap.get(),
            "SA_tool": self._bin_sa.get(),
            "SA_tool_3p": self._bin_sa3.get(),
        })
        # Task 2B: emit multi-fuel dict from blend rows
        fuel_dict   = {}
        fuel_coeffs = {}
        fuel_mw     = {}
        fuel_nu     = {}
        for kv, spv, xfv, cov, mwv, nuv, nu_entry, _ in getattr(self, "_fuel_rows", []):
            k  = kv.get().strip() or "a"
            sp = spv.get().strip()
            if sp:
                fuel_dict[k]   = sp
                fuel_coeffs[k] = cov.get().strip()
                fuel_mw[k]     = mwv.get().strip()
                fuel_nu[k]     = nuv.get().strip()
        if not fuel_dict:
            fuel_dict = {"a": "H2"}
        fuel_class = "Mono" if len(fuel_dict) == 1 else "Multi"
        cfg["Inputs"].update({
            "fileType":     self._inp_filetype.get(),
            "fuelClass":    fuel_class,
            "fuel":         fuel_dict,
            "fuel_coeffs":  {k: v for k, v in fuel_coeffs.items() if v},
            "fuel_mw":      {k: v for k, v in fuel_mw.items() if v},
            "fuel_nu_o2":   {k: v for k, v in fuel_nu.items() if v},
            "global_reaction": self._inp_rxn.get(),
            "AnalysisType": self._inp_analysis.get(),
        })
        cfg["Locations"].update({
            "mechanism": self._loc_mech.get(),
            "Initial_pre_file": self._loc_pre.get(),
            "uncertainty_data": self._loc_unsrt.get(),
            "thermo_file": self._loc_thermo.get(),
            "trans_file": self._loc_trans.get(),
            "targets": self._loc_targets.get(),
            "addendum": self._loc_add.get(),
        })
        cfg["Stats"].update({
            "Design_of_PRS": self._design.get(),
            "Order_of_PRS": int(self._order.get() or 2),
            "Sampling_of_PRS": int(self._sampling.get() or 4),
            "PRS_type": self._prs_type.get(),
            "cut_off_percentage": float(self._cutoff.get() or 1),
            "MRE_criteria": float(self._mre.get() or 5.0),
            "Objective": self._obj.get(),
            "pm_p": float(self._pm_p.get() or 0.1),
            "pm_p_start": float(self._pm_p_start.get() or 1.0),
            "softmax_beta": float(self._softmax_beta.get() or 20.0),
            "pen_alpha": float(self._pen_alpha.get() or 0.9),
            "pen_K": float(self._pen_K.get() or 100.0),
            "num_generations": int(self._num_gen.get() or 20000),
            "outlier_N_new": int(self._out_N.get() or 200),
            "outlier_sample_mode": self._out_mode.get(),
            "outlier_max_iter": int(self._out_max.get() or 5),
        })
        cfg["Stats"]["Weights"] = {"Tig": 1.0}  # always keep at least Tig, even if 0 below
        for ttype, v in self._weight_vars.items():
            w_val = float(v.get() or 0.0)
            if w_val > 0 or ttype == "Tig":
                cfg["Stats"]["Weights"][ttype] = w_val

        # RMIP
        cfg["RMIP"]["database"] = self._rmip_db.get()
        cfg["RMIP"]["glossary"] = self._rmip_glossary.get()
        cfg["RMIP"]["mechanisms"] = []
        cfg["RMIP"]["mech_workflow"] = self._mech_workflow.get()
        for nv, pv, tv, trv, fv, glv, prv in self._mech_rows:
            if pv.get():
                e = {"name": nv.get(), "path": pv.get(), "format": fv.get()}
                if tv.get():
                    e["thermo"] = tv.get()
                if trv.get():
                    e["trans"] = trv.get()
                if glv.get():
                    e["glossary"] = glv.get()
                if prv.get():
                    e["pre"] = prv.get()
                cfg["RMIP"]["mechanisms"].append(e)

        cfg["RMIP"]["graph"].update({
            "layout": self._g_layout.get(),
            "out_dir": self._g_outdir.get(),
            "figure_format": self._g_fmt.get(),
        })
        cfg["RMIP"]["graph3d"].update({
            "shell_gap": float(self._g3_shell.get() or 2.0),
            "layer_gap": float(self._g3_layer.get() or 1.0),
            "order": self._g3_order.get(),
            "out_dir": self._g3_out.get(),
        })
        cfg["RMIP"]["comparison"].update({
            "tol_A": float(self._cmp_tolA.get() or 0.01),
            "tol_n": float(self._cmp_toln.get() or 0.001),
            "tol_Ea": float(self._cmp_tolE.get() or 100.0),
            "out_dir": self._cmp_out.get(),
        })
        cfg["RMIP"]["fusion"].update({
            "name": self._fus_name.get(),
            "description": self._fus_desc.get(),
            "uf_warn": float(self._fus_uf.get() or 10.0),
            "out_dir": self._fus_out.get(),
        })
        cfg["RMIP"]["reduction"].update({
            "method": self._red_method.get(),
            "target_species": self._red_target.get(),
            "eps_max": float(self._red_eps.get() or 0.5),
            "T": float(self._red_T.get() or 1200.0),
            "P": float(self._red_P.get() or 1.0),
            "phi": float(self._red_phi.get() or 1.0),
            "out_dir": self._red_out.get(),
            "target_file": self._red_target_file.get() or None,
        })
        cfg["RMIP"].setdefault("sa_analysis", {}).update({
            "fuel": self._sa_fuel.get(),
            "T": float(self._sa_T.get() or 1200.0),
            "P": float(self._sa_P.get() or 1.0),
            "phi": float(self._sa_phi.get() or 1.0),
            "out_dir": self._sa_out.get(),
        })
        cfg["RMIP"]["unified_tree"].update({
            "mode": self._ut_mode.get(),
            "anchor_mechanism": self._ut_anchor.get(),
            "T_min": int(self._ut_tmin.get() or 500),
            "T_max": int(self._ut_tmax.get() or 2500),
            "dT": int(self._ut_dt.get() or 20),
            "P_ref_atm": float(self._ut_pref.get() or 1.0),
            "out_dir": self._ut_out.get(),
        })
        cfg["RMIP"]["export"].update({
            "chemkin_path": self._ex_ck.get(),
            "yaml_path": self._ex_yaml.get(),
        })
        cfg["ForwardUQ"].update({
            "n_samples": int(self._uq_n.get() or 50000),
            "method": self._uq_method.get(),
            "output_dir": self._uq_outdir.get(),
            "ci_level": float(self._uq_ci.get() or 0.95),
        })
        return cfg

    # ── Task 1F: Checkpoint save / restore ───────────────────────────────────

    _DEFAULT_CHECKPOINT_PATH = str(Path(__file__).resolve().parent / ".rmip_gui_autosave.json")

    def _get_checkpoint_path(self, force_prompt: bool = False) -> str:
        """Resolve the checkpoint save location, prompting at most once ever.

        The first time a location is needed (autosave firing, or an explicit
        "Save Checkpoint" before one has ever been chosen), a save dialog is
        shown and the result is persisted to .rmip_gui_settings.json so no
        future launch of the GUI ever prompts again. force_prompt=True (used
        by "Save Checkpoint As …") always re-prompts and updates the cache.
        """
        if self._checkpoint_path and not force_prompt:
            return self._checkpoint_path
        p = filedialog.asksaveasfilename(
            title="Choose checkpoint save location",
            defaultextension=".json",
            initialfile=".rmip_gui_checkpoint.json",
            filetypes=[("JSON checkpoint", "*.json"), ("All", "*")],
        )
        if not p:
            # User cancelled — fall back to a fixed default so autosave never blocks.
            p = self._checkpoint_path or self._DEFAULT_CHECKPOINT_PATH
        self._checkpoint_path = p
        _save_gui_settings({"checkpoint_path": p})
        return p

    def _write_checkpoint(self, path: str):
        cfg = self._collect()
        chk = {
            "cfg":         cfg,
            "target_rows": [{k: v.get() for k, v in vs.items()} for _, vs in self._target_rows],
            "add_rows":    [dict({k: v.get() for k, v in vs.items()},
                                 **{k: v.get() for k, v in getattr(row, "_extra_vars", {}).items()})
                            for row, vs in self._add_rows],
            "xml_rows":    [{"name": nv.get(), "type": tv.get(), "const_u": cv.get()}
                            for nv, tv, cv, _ in self._xml_rows],
            "quick_path":  self._quick_path.get(),
        }
        with open(path, "w") as fh:
            json.dump(chk, fh, indent=2)

    def _save_checkpoint_silent(self):
        """Write the checkpoint with no dialog — used by autosave and by the
        "Save Checkpoint" menu item once a location has been chosen."""
        try:
            p = self._get_checkpoint_path()
            self._write_checkpoint(p)
            self._status.set(f"Checkpoint saved: {p}")
        except Exception as ex:
            print(f"Checkpoint save error: {ex}")

    def _save_checkpoint(self):
        """Explicit "Save Checkpoint" menu action — silent after the first-ever use."""
        try:
            self._save_checkpoint_silent()
        except Exception as ex:
            messagebox.showerror("Checkpoint error", str(ex))

    def _save_checkpoint_as(self):
        """Explicit "Save Checkpoint As …" — always re-prompts and updates the cached path."""
        try:
            p = self._get_checkpoint_path(force_prompt=True)
            self._write_checkpoint(p)
            self._status.set(f"Checkpoint saved: {p}")
        except Exception as ex:
            messagebox.showerror("Checkpoint error", str(ex))

    def _restore_checkpoint(self, path: str = None):
        """Reload a previously saved checkpoint JSON.

        If path is provided, loads that file directly; otherwise opens a file dialog.
        """
        if path is None:
            p = filedialog.askopenfilename(
                title="Restore checkpoint",
                filetypes=[("JSON checkpoint", "*.json"), ("All", "*")],
            )
        else:
            p = path
        if not p or not Path(p).exists():
            return
        try:
            with open(p) as fh:
                chk = json.load(fh)
            # Restore config into widgets via cfg update
            self.cfg = chk.get("cfg", self.cfg)
            # Restore quick-save path
            if "quick_path" in chk:
                self._quick_path.set(chk["quick_path"])
            # Restore target rows
            self._clear_trows(confirm=False)
            for d in chk.get("target_rows", []):
                self._add_trow(d)
            # Restore add rows
            for row, _ in list(self._add_rows):
                row.destroy()
            self._add_rows.clear()
            for d in chk.get("add_rows", []):
                self._add_arow(d)
            # Restore xml rows
            for _, _, _, row in list(self._xml_rows):
                row.destroy()
            self._xml_rows.clear()
            for d in chk.get("xml_rows", []):
                self._add_xrow(d.get("name", ""), d.get("type", "pressure_independent"),
                               d.get("const_u", ""))
            self._status.set(f"Checkpoint restored: {p}")
            messagebox.showinfo("Restored", f"Checkpoint restored from:\n{p}\n\n"
                                "Simple fields (Project/Locations/etc.) will repopulate "
                                "on next Generate & Preview.")
        except Exception as ex:
            messagebox.showerror("Restore error", str(ex))

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 4: Auto-Save, Tab Locking, Progressive Navigation
    # ─────────────────────────────────────────────────────────────────────────

    def _on_notebook_tab_changed(self, event):
        """EVENT HANDLER: Intercept tab clicks to enforce locking."""
        # Find which notebook was clicked
        nb = event.widget
        try:
            clicked_tab = nb.index(nb.select())
            # Try to access this tab via the locker
            allowed = self._tab_locker.handle_tab_click(clicked_tab)
            if not allowed:
                # Tab was locked, locker already reverted to previous tab
                pass
        except Exception as e:
            pass  # Ignore errors
        self._on_notebook_tab_changed_for_reduction(event)

    def _try_restore_autosave(self):
        """Auto-load last session checkpoint if it exists (on startup)."""
        chkpt = Path(self._checkpoint_path or self._DEFAULT_CHECKPOINT_PATH)
        if chkpt.exists():
            ans = messagebox.askyesno(
                "Restore Previous Session",
                "Found autosave checkpoint from last session.\n\n"
                "Would you like to restore it and continue where you left off?",
            )
            if ans:
                try:
                    self._restore_checkpoint(str(chkpt))
                except Exception as e:
                    messagebox.showwarning("Restore failed", f"Could not restore checkpoint: {e}")

    def _on_closing(self):
        """Called when window is about to close — save final state."""
        self._autosave_mgr.on_close()
        self.root.destroy()

    def _make_traced_var(self, initial_value: str = "") -> tk.StringVar:
        """Create a StringVar that auto-marks dirty on any change."""
        var = tk.StringVar(value=initial_value)
        var.trace("w", lambda *args: self._autosave_mgr.mark_dirty())
        return var

    @staticmethod
    def _existing_nonempty_file(path: str) -> bool:
        try:
            return bool(path) and Path(path).exists() and Path(path).stat().st_size > 0
        except Exception:
            return False

    def _validate_tab(self, tab_index: int) -> list:
        """Validate current tab; return list of error messages. Empty list = valid."""
        errors = []
        try:
            # Tab 0: Project — requires name, fuel, formula, output dir
            if tab_index == 0:
                for field in ["name", "fuel_name", "fuel_formula", "output_base_dir"]:
                    if not self.cfg.get("project", {}).get(field, "").strip():
                        errors.append(f"Missing: {field}")

            # Tab 2: Experimental Data / Target Builder — requires ≥1 target
            # row OR an existing .target file already on disk (e.g. written
            # by the XML converter, which points self._loc_targets at it).
            if tab_index == 2:
                if len(self._target_rows) == 0 and not self._existing_nonempty_file(self._loc_targets.get()):
                    errors.append("Add at least one target row, or import/generate a .target file first")

            # Tab 3: Target Workbench — curation is optional (plot/check/
            # generate/prune the .target just built), never required to
            # advance; nothing to validate here.

            # Tab 4: Addendum Builder — requires ≥1 addendum entry OR an
            # existing .add file already on disk. (Shifted from 3 -> 4 when
            # the Target Workbench tab was inserted at index 3.)
            if tab_index == 4:
                if len(self._add_rows) == 0 and not self._existing_nonempty_file(self._loc_add.get()):
                    errors.append("Add at least one addendum entry, or import/generate a .add file first")

            # Tab 7: Files & Paths — requires mechanism path. (Shifted from
            # 6 -> 7 when the Target Workbench tab was inserted at index 3.)
            if tab_index == 7:
                if not self.cfg.get("Locations", {}).get("mechanism", "").strip():
                    errors.append("Missing: mechanism file path")

            # Tab 13: Project (mso_project viewer) — read-only, optional,
            # nothing to validate; appended last, see __init__'s nb.add() order.

        except Exception as e:
            errors.append(f"Validation error: {e}")

        return errors

    def _next_tab(self, current_index: int = None):
        """Validate current tab and advance to next."""
        if current_index is None:
            # Get current tab index from notebook
            for i, child in enumerate(self.root.winfo_children()):
                if isinstance(child, ttk.Notebook):
                    current_index = child.index("current")
                    break

        if current_index is None:
            return

        # Validate current tab BEFORE advancing
        errors = self._validate_tab(current_index)
        if errors:
            messagebox.showwarning(
                "Cannot Proceed",
                f"Fix these issues first:\n\n" + "\n".join(f"• {e}" for e in errors),
            )
            return

        # Validation passed - mark this tab as complete
        if self._tab_locker:
            self._tab_locker.mark_complete(current_index)

        # Advance to next tab
        last_idx = self._num_tabs - 1
        next_idx = min(current_index + 1, last_idx)
        for child in self.root.winfo_children():
            if isinstance(child, ttk.Notebook):
                child.select(next_idx)
                break

        # Auto-generate preview if we've reached the last tab
        if next_idx == last_idx:
            try:
                self._preview()
            except Exception as e:
                print(f"Preview generation error: {e}")

        progress = len(self._tab_locker.visited_tabs)
        self._status.set(f"✓ Progress: {progress}/{self._num_tabs} tabs complete. Next: Tab {next_idx}")

    def _prev_tab(self, current_index: int = None):
        """Go back to previous tab."""
        if current_index is None:
            for i, child in enumerate(self.root.winfo_children()):
                if isinstance(child, ttk.Notebook):
                    current_index = child.index("current")
                    break

        if current_index is None or current_index == 0:
            return

        prev_idx = current_index - 1
        for child in self.root.winfo_children():
            if isinstance(child, ttk.Notebook):
                child.select(prev_idx)
                break

    # ── Task 1E stubs: tour, MW dialog, LaTeX tables, XML import ─────────────

    def _start_tour(self):
        """Simple guided tour: cycle through tabs with a hint dialog.

        Tab order (Task 7): file-producing tabs come before "Files & Paths" so
        those files exist by the time their location is asked for.
        """
        steps = [
            (0, "Project",             "Start here: set your project name and output directory."),
            (1, "Mechanisms",          "List all mechanisms for RMIP analysis (CHEMKIN .inp or Cantera .yaml), "
                                       "and choose one-at-a-time vs fuse-into-one processing."),
            (2, "Experimental Data",   "Import experimental datasets from CSV or XML (RKD/ReSpecTh), then "
                                       "build/edit the .target row grid right below it."),
            (3, "Target Workbench",   "Optional: plot, sanity-check, generate dummy points for, and prune "
                                       "the .target set you just built before it feeds Addendum."),
            (4, "Addendum",            "Build the .add file: one entry per dataset with solver settings."),
            (5, "Reaction Screening",  "Run an RMIP comparison or a Sensitivity Analysis, filter reactions "
                                       "by carbon number, and send the survivors to Uncertainty XML."),
            (6, "Uncertainty XML",     "Build the uncertainty .xml: per-reaction σ arrays."),
            (7, "Files & Paths",       "Fuel blend, and confirm the mechanism/targets/addendum/XML paths "
                                       "(auto-filled from what you just built)."),
            (8, "Optimization",       "Configure the PRS design, objective function, and outlier retraining."),
            (9, "RMIP Analysis",      "Set graph, comparison, fusion, reduction, and unified-tree options."),
            (10, "Forward UQ",         "Configure forward propagation through the trained PRS surrogate."),
            (11, "Compile",           "Compile the pybind11 shared objects needed by MUQ-SAC."),
            (12, "Preview",           "Click 'Generate & Preview' to see the full target.opt YAML."),
        ]
        nb = None
        for child in self.root.winfo_children():
            if isinstance(child, ttk.Notebook):
                nb = child
                break
        if not nb:
            return
        for tab_idx, tab_name, hint in steps:
            try:
                nb.select(tab_idx)
                self.root.update()
            except Exception:
                pass
            if not messagebox.askyesno(f"Tour — {tab_name}",
                                       f"{hint}\n\nContinue tour?"):
                break
        self._status.set("Tour complete.")

    def _open_mw_dialog(self):
        """Task 2C — MW / Stoichiometry Calculator dialog."""
        try:
            from chem_data import compute_mw, compute_nu_o2, parse_formula, ATOMIC_WEIGHTS
        except ImportError:
            messagebox.showerror("Missing", "chem_data.py not found.")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("MW / Stoichiometry Calculator")
        dlg.geometry("560x560")
        dlg.configure(bg=PALETTE["surface"])
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Molecular Weight & Stoichiometry Calculator",
                  font=FONTS["header"]).pack(pady=(12, 4))

        # ── Formula entry ─────────────────────────────────────────────
        row1 = ttk.Frame(dlg); row1.pack(fill=tk.X, padx=16, pady=4)
        ttk.Label(row1, text="Formula or species:", width=20).pack(side=tk.LEFT)
        fml_v = tk.StringVar(value="H2")
        ttk.Entry(row1, textvariable=fml_v, width=24, font=FONTS["mono"]).pack(side=tk.LEFT)
        result_v = tk.StringVar(value="")
        ttk.Label(dlg, textvariable=result_v, font=FONTS["body"],
                  foreground=PALETTE["accent2"]).pack(pady=2)

        def _calc(*_):
            fml = fml_v.get().strip()
            mw  = compute_mw(fml)
            nu  = compute_nu_o2(fml)
            atoms = parse_formula(fml)
            result_v.set(
                f"MW = {mw:.4f} g/mol    nu_O2 = {nu:.4f} mol O2/mol fuel\n"
                f"Atoms: {atoms}"
            )

        ttk.Button(dlg, text="Calculate", command=_calc).pack(pady=2)

        # ── Element-by-element builder (ASPEN-style, supports fractions for biomass) ──
        ttk.Separator(dlg).pack(fill=tk.X, padx=12, pady=8)
        ttk.Label(dlg, text="Build formula from elements (supports fractional counts for biomass):",
                  font=FONTS["small"], foreground=PALETTE["text_dim"]).pack(anchor=tk.W, padx=16)

        elem_frame = ttk.Frame(dlg); elem_frame.pack(fill=tk.X, padx=16, pady=4)
        COMMON_ELEMS = ["C", "H", "O", "N", "S", "P", "Cl", "F", "Ar", "He"]
        elem_vars: dict = {}
        for i, el in enumerate(COMMON_ELEMS):
            col = ttk.Frame(elem_frame); col.pack(side=tk.LEFT, padx=4)
            ttk.Label(col, text=el, font=FONTS["body_bold"],
                      foreground=PALETTE["accent"]).pack()
            v = tk.StringVar(value="0")
            ttk.Entry(col, textvariable=v, width=5).pack()
            elem_vars[el] = v

        def _build_formula():
            parts = []
            for el, v in elem_vars.items():
                try:
                    cnt = float(v.get())
                except ValueError:
                    cnt = 0.0
                if cnt > 0:
                    parts.append(f"{el}{cnt:g}")
            fml_v.set("".join(parts))
            _calc()

        ttk.Button(dlg, text="Build formula from elements →", command=_build_formula
                   ).pack(pady=4)

        # ── Results detail ────────────────────────────────────────────
        ttk.Separator(dlg).pack(fill=tk.X, padx=12, pady=8)
        detail_v = tk.StringVar()
        ttk.Label(dlg, textvariable=detail_v, font=FONTS["small"],
                  foreground=PALETTE["text_dim"], justify=tk.LEFT).pack(anchor=tk.W, padx=16)

        def _calc_detail(*_):
            _calc()
            fml = fml_v.get().strip()
            nu  = compute_nu_o2(fml)
            atoms = parse_formula(fml)
            C = atoms.get("C", 0); H = atoms.get("H", 0)
            O = atoms.get("O", 0); N = atoms.get("N", 0); S = atoms.get("S", 0)
            detail_v.set(
                f"Atom balance:  C={C}  H={H}  O={O}  N={N}  S={S}\n"
                f"nu_O2 = C + H/4 + S − O/2 = {C} + {H/4:.3f} + {S} − {O/2:.3f} = {nu:.4f}\n"
                f"Reaction: fuel + {nu:.4f} O2 → {C:.4g}CO2 + {H/2:.4g}H2O"
            )

        ttk.Button(dlg, text="Show atom balance detail", command=_calc_detail).pack(pady=2)

        # ── Apply to a fuel row (Task 3: picker over the single fuel registry,
        #    not a blind "last row" — also fixes a pre-existing unpack/AttributeError
        #    bug where this tried nuv.configure() on a StringVar instead of the entry) ──
        target_row_v = tk.StringVar()
        apply_frame = ttk.Frame(dlg); apply_frame.pack(fill=tk.X, padx=16, pady=(8, 2))
        ttk.Label(apply_frame, text="Apply to fuel row:", width=20).pack(side=tk.LEFT)
        row_picker = ttk.Combobox(apply_frame, textvariable=target_row_v, width=20, state="readonly")
        row_picker.pack(side=tk.LEFT)

        def _refresh_row_choices():
            choices = [kv.get() or f"row {i}" for i, (kv, *_r) in enumerate(getattr(self, "_fuel_rows", []))]
            row_picker["values"] = choices
            if choices and not target_row_v.get():
                target_row_v.set(choices[-1])

        _refresh_row_choices()

        def _apply():
            rows = getattr(self, "_fuel_rows", [])
            if not rows:
                messagebox.showinfo("No fuel rows", "Add a fuel row in 'Files & Paths' first.")
                return
            fml = fml_v.get().strip()
            mw  = compute_mw(fml)
            nu  = compute_nu_o2(fml)
            picked = target_row_v.get()
            match = next((r for r in rows if r[0].get() == picked), rows[-1])
            kv, spv, xfv, cov, mwv, nuv, nu_entry, _row = match
            spv.set(fml)
            mwv.set(f"{mw:.4f}" if mw else "")
            nu_entry.configure(state="normal")
            nuv.set(f"{nu:.4f}")
            nu_entry.configure(state="readonly")
            self._sync_fuel_registry()
            self._status.set(f"Applied {fml}: MW={mw:.4f}, nu_O2={nu:.4f} to fuel row '{kv.get()}'.")
            dlg.destroy()

        ttk.Button(dlg, text="Apply to fuel row…", command=_apply).pack(pady=4)
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=2)

    def _open_latex_tables_dialog(self):
        """Customizable LaTeX target tables — GUI-3 implementation."""
        import sys as _sys, os as _os
        _x2c = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                             "config_tools", "converters_io", "XML2CSV")
        if _x2c not in _sys.path:
            _sys.path.insert(0, _x2c)

        win = tk.Toplevel(self.root)
        win.title("Generate LaTeX Target Tables")
        win.geometry("680x520")
        win.configure(bg=PALETTE["bg"])

        # ── inputs ──────────────────────────────────────────────────
        ttk.Label(win, text="Target CSV file (.target):",
                  style="Header.TLabel").pack(anchor=tk.W, padx=14, pady=(12, 2))
        tf_frame = ttk.Frame(win); tf_frame.pack(fill=tk.X, padx=14)
        tgt_var = tk.StringVar()
        ttk.Entry(tf_frame, textvariable=tgt_var, width=55).pack(side=tk.LEFT)
        ttk.Button(tf_frame, text="Browse…",
                   command=lambda: tgt_var.set(
                       filedialog.askopenfilename(filetypes=[("Target", "*.target *.csv"), ("All","*")])
                       or tgt_var.get())).pack(side=tk.LEFT, padx=4)

        ttk.Label(win, text="BibTeX file (references.bib):",
                  style="Header.TLabel").pack(anchor=tk.W, padx=14, pady=(8, 2))
        bib_frame = ttk.Frame(win); bib_frame.pack(fill=tk.X, padx=14)
        bib_var = tk.StringVar()
        ttk.Entry(bib_frame, textvariable=bib_var, width=55).pack(side=tk.LEFT)
        ttk.Button(bib_frame, text="Browse…",
                   command=lambda: bib_var.set(
                       filedialog.askopenfilename(filetypes=[("BibTeX","*.bib"),("All","*")])
                       or bib_var.get())).pack(side=tk.LEFT, padx=4)

        ttk.Label(win, text="Target types to include (comma-separated):",
                  style="Header.TLabel").pack(anchor=tk.W, padx=14, pady=(8, 2))
        types_var = tk.StringVar(value="Tig,Fls,JSR,Flf,RCM")
        ttk.Entry(win, textvariable=types_var, width=40).pack(anchor=tk.W, padx=14)

        ttk.Label(win, text="Columns to include (comma-separated):",
                  style="Header.TLabel").pack(anchor=tk.W, padx=14, pady=(8, 2))
        cols_var = tk.StringVar(value="T,P,phi,fuel,oxidizer,reference")
        ttk.Entry(win, textvariable=cols_var, width=60).pack(anchor=tk.W, padx=14)

        out_frame = ttk.Frame(win); out_frame.pack(fill=tk.X, padx=14, pady=(8, 2))
        ttk.Label(out_frame, text="Output dir:", style="Header.TLabel").pack(side=tk.LEFT)
        out_var = tk.StringVar(value="latex_tables")
        ttk.Entry(out_frame, textvariable=out_var, width=30).pack(side=tk.LEFT, padx=4)
        ttk.Button(out_frame, text="Browse…",
                   command=lambda: out_var.set(self._choose_directory(initial=out_var.get()) or out_var.get())
                   ).pack(side=tk.LEFT)

        compile_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(win, text="Compile to PDF (requires pdflatex)",
                        variable=compile_var).pack(anchor=tk.W, padx=14, pady=4)

        status_var = tk.StringVar(value="")
        ttk.Label(win, textvariable=status_var, foreground="#a6e3a1").pack(anchor=tk.W, padx=14)

        def _generate():
            import sys as _s, os as _o
            _src = _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), "src")
            if _src not in _s.path:
                _s.path.insert(0, _src)
            try:
                from target_tables import generate_target_tables
                generate_target_tables(
                    target_csv=tgt_var.get().strip(),
                    bib_path=bib_var.get().strip(),
                    target_types=[t.strip() for t in types_var.get().split(",") if t.strip()],
                    columns=[c.strip() for c in cols_var.get().split(",") if c.strip()],
                    out_dir=out_var.get().strip() or "latex_tables",
                    compile_pdf=compile_var.get(),
                )
                status_var.set("Tables generated successfully.")
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=win)

        ttk.Button(win, text="Generate tables", command=_generate).pack(pady=10)

    def _import_xml_dataset(self, parent=None):
        """Import RKD/ReSpecTh XML files — real implementation.

        parent: an existing frame to render into (used by the "Experimental
        Data" tab). If omitted, opens as a standalone Toplevel (kept for the
        Insert-menu entry point).
        """
        if parent is None:
            container = tk.Toplevel(self.root)
            container.title("Import XML Dataset")
            container.geometry("640x420")
            container.configure(bg=PALETTE["bg"])
        else:
            container = parent

        ttk.Label(container, text="XML folder (RKD/ReSpecTh *.xml files):",
                  style="Header.TLabel").pack(anchor=tk.W, padx=14, pady=(12, 2))
        xd_frame = ttk.Frame(container); xd_frame.pack(fill=tk.X, padx=14)
        xdir_var = tk.StringVar(
            value=str(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "DATASET", "AMMONIA_COMBUSTION_EXP_DATA", "NH3_XMLv24"))
        )
        ttk.Entry(xd_frame, textvariable=xdir_var, width=55).pack(side=tk.LEFT)
        ttk.Button(xd_frame, text="Browse…",
                   command=lambda: xdir_var.set(self._choose_directory(initial=xdir_var.get()) or xdir_var.get())
                   ).pack(side=tk.LEFT, padx=4)

        ttk.Label(container, text="Output directory:",
                  style="Header.TLabel").pack(anchor=tk.W, padx=14, pady=(8, 2))
        od_frame = ttk.Frame(container); od_frame.pack(fill=tk.X, padx=14)
        odir_var = tk.StringVar(value="xml_output")
        ttk.Entry(od_frame, textvariable=odir_var, width=40).pack(side=tk.LEFT)
        ttk.Button(od_frame, text="Browse…",
                   command=lambda: odir_var.set(self._choose_directory(initial=odir_var.get()) or odir_var.get())
                   ).pack(side=tk.LEFT, padx=4)

        ttk.Label(container, text="Fuel species (comma-separated):",
                  style="Header.TLabel").pack(anchor=tk.W, padx=14, pady=(8, 2))
        # Task 3: default from the fuel-blend table (Files & Paths tab) instead of
        # a hardcoded species — still editable since XML datasets may cover a
        # different fuel than the one being optimized.
        fuel_row = ttk.Frame(container); fuel_row.pack(fill=tk.X, padx=14)
        fuel_var = tk.StringVar(value=",".join(self._fuel_registry.keys()) or "NH3")
        ttk.Entry(fuel_row, textvariable=fuel_var, width=30).pack(side=tk.LEFT)
        use_blend_btn = ttk.Button(
            fuel_row, text="Use blend fuels", style="Small.TButton",
            command=lambda: fuel_var.set(",".join(self._fuel_registry.keys())))
        use_blend_btn.pack(side=tk.LEFT, padx=4)
        self._hoverable(use_blend_btn, "Fill in from the fuel-blend table (Files & Paths tab)")

        ttk.Label(container, text="Solver (tagged into every .add entry):",
                  style="Header.TLabel").pack(anchor=tk.W, padx=14, pady=(8, 2))
        solver_row = ttk.Frame(container); solver_row.pack(fill=tk.X, padx=14)
        solver_var = tk.StringVar(value="cantera")
        ttk.Combobox(solver_row, textvariable=solver_var,
                     values=["cantera", "CHEMKIN_PRO", "FlameMaster"],
                     width=16, state="readonly").pack(side=tk.LEFT)

        prog_var = tk.StringVar(value="")
        ttk.Label(container, textvariable=prog_var, foreground="#a6e3a1",
                  wraplength=600).pack(anchor=tk.W, padx=14, pady=4)

        def _run_conversion():
            import sys as _sys2, os as _os2, threading
            _x2c = _os2.path.join(
                _os2.path.dirname(_os2.path.abspath(__file__)),
                "config_tools", "converters_io", "XML2CSV"
            )
            if _x2c not in _sys2.path:
                _sys2.path.insert(0, _x2c)

            fuels = [f.strip() for f in fuel_var.get().split(",") if f.strip()]
            input_fuel = {chr(ord("a") + i): sp for i, sp in enumerate(fuels)}
            xdir = xdir_var.get().strip()
            odir = odir_var.get().strip() or "xml_output"
            solver = solver_var.get()

            def _worker():
                try:
                    from xml2csv import main as xml2csv_main
                    result = xml2csv_main(xml_dir=xdir, out_dir=odir,
                                           fuel_list=fuels, input_fuel=input_fuel, solver=solver)
                    abs_odir = os.path.abspath(odir)
                    n_ok = result["n_files_ok"] if result else 0
                    n_rows = result["n_rows"] if result else 0
                    # xml2csv now captures the actual per-file skip reason
                    # (e.g. "Missing commonProperties or dataGroup in X.xml")
                    # instead of only logging it to a console the GUI user may
                    # never see — show a sample directly so "0 files
                    # converted" is never an unexplained dead end.
                    warns = (result.get("warnings") or []) if result else []
                    warn_sample = "\n".join(f"  • {w}" for w in warns[:5])
                    if len(warns) > 5:
                        warn_sample += f"\n  … and {len(warns) - 5} more (see console log for the rest)"

                    # Trust xml2csv's own row count (tracked during parsing)
                    # instead of re-deriving it by re-globbing *.target files —
                    # that re-glob was fragile (stale leftover files in the
                    # same output dir could produce a wrong count) and is what
                    # caused the misleading "0 target rows written" message.
                    if not result or n_ok == 0:
                        msg = "No XML files were successfully converted."
                        if warn_sample:
                            msg += f"\nReason(s):\n{warn_sample}"
                        else:
                            msg += " (see console log for per-file skip reasons)."
                    elif n_rows == 0:
                        msg = f"{n_ok} file(s) parsed but produced 0 target rows — check the XML content."
                    else:
                        msg = (f"Done. {n_rows} target rows written to {odir}.\n"
                               "Check xml_output/*.target  /  *.add  /  references.bib  /  *.csv")
                        if warn_sample:
                            msg += f"\n{result['n_files_skipped']} file(s) skipped:\n{warn_sample}"
                    self.root.after(0, lambda m=msg: prog_var.set(m))
                    self.root.after(0, lambda: self._status.set(f"XML import: {n_rows} rows → {odir}"))

                    # Point the Files & Paths tab's targets/addendum fields at
                    # what the converter just wrote, so the "existing file on
                    # disk" validation check (see _validate_tab) can find it
                    # without requiring the user to also re-import as rows.
                    if result and result.get("target_path"):
                        self.root.after(0, lambda p=result["target_path"]: self._loc_targets.set(p))
                    if result and result.get("add_path"):
                        self.root.after(0, lambda p=result["add_path"]: self._loc_add.set(p))

                    # Auto-import the emitted CSV into the Experimental Data
                    # tab's grid — no manual "Import CSV" click needed when
                    # the source was an XML conversion.
                    if result and result.get("csv_path"):
                        csv_path = result["csv_path"]
                        df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)

                        def _auto_import(df=df, csv_path=csv_path):
                            self._target_choose_page_size()
                            self._target_df_load(df)
                            self._status.set(f"Auto-imported {csv_path} into Experimental Data tab")

                        self.root.after(0, _auto_import)
                except Exception as exc:
                    self.root.after(0, lambda e=exc: messagebox.showerror(
                        "Conversion error", str(e), parent=container))

            prog_var.set("Running xml2csv converter…")
            threading.Thread(target=_worker, daemon=True).start()

        ttk.Button(container, text="Run xml2csv conversion", command=_run_conversion).pack(pady=10)

    # ── Task 4E: GUI job launcher ─────────────────────────────────────────────

    def _run_job(self, cmd: str, label: str = "Job"):
        """
        Launch `cmd` in an external terminal window.
        Tries gnome-terminal → xterm → konsole in order.
        PID is tracked and shown in the status bar.
        """
        import subprocess, shutil, threading

        def _find_terminal():
            for term in ("gnome-terminal", "xterm", "konsole", "x-terminal-emulator"):
                if shutil.which(term):
                    return term
            return None

        term = _find_terminal()
        if term is None:
            messagebox.showerror(
                "No terminal found",
                "Could not find gnome-terminal, xterm, or konsole.\n"
                "Please install one and retry.",
            )
            return

        try:
            if term == "gnome-terminal":
                proc = subprocess.Popen(
                    ["gnome-terminal", "--", "bash", "-c", f"{cmd}; echo; echo '-- Done. Press Enter --'; read"],
                )
            elif term == "konsole":
                proc = subprocess.Popen(
                    ["konsole", "-e", "bash", "-c", f"{cmd}; echo; echo '-- Done. Press Enter --'; read"],
                )
            else:
                # xterm / x-terminal-emulator
                proc = subprocess.Popen(
                    [term, "-e", f"bash -c '{cmd}; echo; echo -- Done. Press Enter --; read'"],
                )

            pid = proc.pid
            self._status.set(f"[{label}] launched (PID {pid}) — terminal window opened.")

            # Background watcher: update status when terminal exits
            def _watch():
                proc.wait()
                self._status.set(f"[{label}] PID {pid} finished.")
            threading.Thread(target=_watch, daemon=True).start()

        except Exception as exc:
            messagebox.showerror("Launch error", str(exc))

    def _open_run_dialog(self):
        """Open a dialog to choose and launch a backend job in a terminal."""
        win = tk.Toplevel(self.root)
        win.title("Run Job")
        win.configure(bg=PALETTE["bg"])
        win.geometry("560x340")
        win.resizable(False, False)

        ttk.Label(win, text="Command to run:", style="Header.TLabel").pack(anchor=tk.W, padx=16, pady=(14,4))
        cmd_var = tk.StringVar(value="python run_script.py target.opt")
        ttk.Entry(win, textvariable=cmd_var, width=60).pack(padx=16, fill=tk.X)

        ttk.Label(win, text="Working directory:", style="Header.TLabel").pack(anchor=tk.W, padx=16, pady=(10,4))
        wd_var = tk.StringVar(value=os.getcwd())
        wd_frame = ttk.Frame(win)
        wd_frame.pack(padx=16, fill=tk.X)
        ttk.Entry(wd_frame, textvariable=wd_var, width=50).pack(side=tk.LEFT)
        ttk.Button(wd_frame, text="Browse…",
                   command=lambda: wd_var.set(self._choose_directory(initial=wd_var.get()) or wd_var.get())
                   ).pack(side=tk.LEFT, padx=4)

        ttk.Label(win, text="Label (shown in status bar):", style="Header.TLabel").pack(anchor=tk.W, padx=16, pady=(10,4))
        lbl_var = tk.StringVar(value="MUQ-SAC")
        ttk.Entry(win, textvariable=lbl_var, width=30).pack(padx=16, anchor=tk.W)

        def _launch():
            import shlex
            wd = wd_var.get().strip() or os.getcwd()
            cmd = f"cd {shlex.quote(wd)} && {cmd_var.get().strip()}"
            self._run_job(cmd, label=lbl_var.get() or "Job")
            win.destroy()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=14)
        ttk.Button(btn_frame, text="Launch in Terminal", command=_launch).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side=tk.LEFT)

    # ── Forward UQ launcher ───────────────────────────────────────────────────

    def _run_forward_uq(self):
        """Save current target.opt then launch forward_uq.py in a terminal."""
        import os as _os, tempfile as _tmp, threading

        # Save current config to a temp target.opt so we use fresh values
        cfg = self._collect()
        text = config_to_yaml(cfg)
        tmp_opt = _tmp.NamedTemporaryFile(
            suffix="_target.opt", mode="w", delete=False, dir="."
        )
        tmp_opt.write(text)
        tmp_opt.close()
        opt_path = _os.path.abspath(tmp_opt.name)

        n_samples  = self._uq_n.get().strip()
        method     = self._uq_method.get().strip()
        out_dir    = self._uq_outdir.get().strip() or "ForwardUQ"
        fwd_script = _os.path.join(
            _os.path.dirname(_os.path.abspath(__file__)), "forward_uq.py"
        )

        import shlex
        cmd = (
            f"python {shlex.quote(fwd_script)} {shlex.quote(opt_path)} "
            f"--n_samples {shlex.quote(n_samples)} --method {shlex.quote(method)} "
            f"--output_dir {shlex.quote(out_dir)}"
        )
        self._uq_status.set(f"Launching: {cmd}")
        self._run_job(cmd, label="ForwardUQ")

        # After a short delay try to read results CSV if it lands
        def _poll_results():
            import time, os, glob
            for _ in range(30):                    # wait up to 60 s
                time.sleep(2)
                hits = glob.glob(f"{out_dir}/**/forward_uq_statistics.csv",
                                 recursive=True) or glob.glob("forward_uq_statistics.csv")
                if hits:
                    try:
                        import csv
                        rows = list(csv.DictReader(open(hits[0])))
                        lines = [f"Loaded {hits[0]} — {len(rows)} cases:"]
                        for r in rows[:10]:
                            parts = [f"{k}={v}" for k, v in list(r.items())[:5]]
                            lines.append("  " + "  ".join(parts))
                        self.root.after(0, lambda txt="\n".join(lines): self._uq_append_result(txt))
                    except Exception as exc:
                        self.root.after(0, lambda e=exc: self._uq_append_result(f"(CSV read error: {e})"))
                    break

        threading.Thread(target=_poll_results, daemon=True).start()

    def _open_uq_outdir(self):
        import os as _os, subprocess as _sp, shutil
        d = self._uq_outdir.get().strip() or "ForwardUQ"
        if _os.path.isdir(d):
            opener = shutil.which("xdg-open") or shutil.which("open")
            if opener:
                _sp.Popen([opener, d])
        else:
            messagebox.showinfo("Not found", f"Directory not found:\n{d}")

    def _uq_append_result(self, text: str):
        self._uq_result_text.config(state=tk.NORMAL)
        self._uq_result_text.insert(tk.END, text + "\n")
        self._uq_result_text.see(tk.END)
        self._uq_result_text.config(state=tk.DISABLED)
        self._uq_status.set("Results loaded — check output folder for plots.")

    def _view_uq_plots(self):
        """Open a scrollable thumbnail viewer for all PNG/PDF plots in the UQ output dir."""
        import os as _os, glob as _glob
        d = self._uq_outdir.get().strip() or "ForwardUQ"
        if not _os.path.isdir(d):
            messagebox.showinfo("Not found", f"Output directory not found:\n{d}")
            return
        imgs = sorted(
            _glob.glob(_os.path.join(d, "**", "*.png"), recursive=True)
            + _glob.glob(_os.path.join(d, "**", "*.jpg"), recursive=True)
        )
        if not imgs:
            messagebox.showinfo("No plots", f"No PNG/JPG files found in:\n{d}")
            return
        try:
            from PIL import Image, ImageTk
        except ImportError:
            messagebox.showerror("Pillow required",
                                 "Install Pillow to use the plot viewer:\n  pip install Pillow")
            return

        win = tk.Toplevel(self.root)
        win.title(f"UQ Plots — {_os.path.basename(d)}  ({len(imgs)} files)")
        win.geometry("1000x720")
        win.configure(bg=PALETTE["bg"])

        # Scrollable canvas
        canvas = tk.Canvas(win, bg=PALETTE["bg"], highlightthickness=0)
        vbar   = tk.Scrollbar(win, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=PALETTE["bg"])
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)

        # Thumbnails in a 3-column grid
        thumb_refs = []   # prevent GC
        THUMB_W, THUMB_H = 290, 220
        for i, path in enumerate(imgs):
            try:
                im = Image.open(path)
                im.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
                tk_im = ImageTk.PhotoImage(im)
            except Exception:
                continue
            thumb_refs.append(tk_im)
            col, row = i % 3, i // 3
            frame = tk.Frame(inner, bg=PALETTE["surface"], padx=4, pady=4,
                             relief=tk.GROOVE, bd=1)
            frame.grid(row=row, column=col, padx=6, pady=6)
            lbl = tk.Label(frame, image=tk_im, bg=PALETTE["surface"])
            lbl.pack()
            cap = tk.Label(frame, text=_os.path.basename(path),
                           bg=PALETTE["surface"], fg=PALETTE["text"],
                           wraplength=THUMB_W, font=("DejaVu Sans", 7))
            cap.pack()
            # Double-click to open at full size
            def _open_full(p=path):
                opener = shutil.which("xdg-open") or shutil.which("eog") or shutil.which("open")
                if opener:
                    import subprocess as _sp2
                    _sp2.Popen([opener, p])
            lbl.bind("<Double-Button-1>", lambda e, p=path: _open_full(p))

        win.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas._thumb_refs = thumb_refs   # keep alive

    # ── Task 6A: PDF Notebook ─────────────────────────────────────────────────

    def _open_pdf_notebook(self):
        """Open the Gemini PDF Q&A notebook in a new Toplevel window."""
        import sys as _sys, os as _os
        _nb_src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "src")
        if _nb_src not in _sys.path:
            _sys.path.insert(0, _nb_src)
        try:
            from notebook_gemini.gemini_client import GeminiClient
            from notebook_gemini.pdf_panel import PDFNotebookPanel
        except ImportError as exc:
            messagebox.showerror("Import error", str(exc))
            return

        win = tk.Toplevel(self.root)
        win.title("Gemini PDF Notebook")
        win.geometry("940x660")
        win.configure(bg=PALETTE["bg"])
        client = GeminiClient()
        panel = PDFNotebookPanel(win, client=client, palette=PALETTE)
        panel.pack(fill=tk.BOTH, expand=True)

    # ── Task 6B: Plot Digitizer ───────────────────────────────────────────────

    def _open_plot_digitizer(self):
        """Open the plot digitizer in a new Toplevel window."""
        import sys as _sys, os as _os
        _nb_src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "src")
        if _nb_src not in _sys.path:
            _sys.path.insert(0, _nb_src)
        try:
            from notebook_gemini.gemini_client import GeminiClient
            from notebook_gemini.digitizer import DigitizerPanel
        except ImportError as exc:
            messagebox.showerror("Import error", str(exc))
            return

        win = tk.Toplevel(self.root)
        win.title("Plot Digitizer")
        win.geometry("1000x740")
        win.configure(bg=PALETTE["bg"])
        client = GeminiClient()
        panel = DigitizerPanel(win, client=client, palette=PALETTE)
        panel.pack(fill=tk.BOTH, expand=True)

    def _open_pdf_table_panel(self):
        """Open the PDF table extraction panel in a new Toplevel window."""
        import sys as _sys, os as _os
        _nb_src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "src")
        if _nb_src not in _sys.path:
            _sys.path.insert(0, _nb_src)
        try:
            from notebook_gemini.gemini_client import GeminiClient
            from notebook_gemini.pdf_table_panel import PDFTablePanel
        except ImportError as exc:
            messagebox.showerror("Import error", str(exc))
            return
        win = tk.Toplevel(self.root)
        win.title("Extract PDF Tables")
        win.geometry("920x680")
        win.configure(bg=PALETTE["bg"])
        client = GeminiClient()
        panel = PDFTablePanel(win, client=client, palette=PALETTE)
        panel.pack(fill=tk.BOTH, expand=True)

    def _open_symreg_panel(self):
        """Open the symbolic regression / poly-fit panel in a new Toplevel window."""
        import sys as _sys, os as _os
        _nb_src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "src")
        if _nb_src not in _sys.path:
            _sys.path.insert(0, _nb_src)
        try:
            from notebook_gemini.gemini_client import GeminiClient
            from notebook_gemini.pysr_panel import PySRPanel
        except ImportError as exc:
            messagebox.showerror("Import error", str(exc))
            return
        win = tk.Toplevel(self.root)
        win.title("Symbolic Regression / Polynomial Fit")
        win.geometry("1100x760")
        win.configure(bg=PALETTE["bg"])
        client = GeminiClient()
        panel = PySRPanel(win, client=client, palette=PALETTE)
        panel.pack(fill=tk.BOTH, expand=True)

    # ── Task 6C: LaTeX project helpers ───────────────────────────────────────

    def _latex_new_project(self):
        import sys as _sys, os as _os
        _src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "src")
        if _src not in _sys.path:
            _sys.path.insert(0, _src)
        from latex_project import LaTeXProject

        proj_dir = self._choose_directory(title="Choose or create project folder")
        if not proj_dir:
            return
        title = simpledialog.askstring("Title", "Document title:",
                                       initialvalue="NH3 Combustion Study") or "Untitled"
        author = simpledialog.askstring("Author", "Author name:", initialvalue="KP") or "KP"
        try:
            LaTeXProject(proj_dir).create(title, author=author)
            messagebox.showinfo("Created", f"LaTeX project created at:\n{proj_dir}")
            self._status.set(f"LaTeX project: {proj_dir}")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _latex_compile(self):
        import sys as _sys, os as _os
        _src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "src")
        if _src not in _sys.path:
            _sys.path.insert(0, _src)
        from latex_project import LaTeXProject

        proj_dir = self._choose_directory(title="Select LaTeX project folder")
        if not proj_dir:
            return
        self._status.set("Compiling LaTeX…")
        self.root.update_idletasks()
        ok = LaTeXProject(proj_dir).compile(open_pdf=True)
        self._status.set("LaTeX compile OK." if ok else "LaTeX compile failed — check terminal.")

    def _latex_append_section(self):
        import sys as _sys, os as _os
        _src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "src")
        if _src not in _sys.path:
            _sys.path.insert(0, _src)
        from latex_project import LaTeXProject

        proj_dir = self._choose_directory(title="Select LaTeX project folder")
        if not proj_dir:
            return

        win = tk.Toplevel(self.root)
        win.title("Append section")
        win.geometry("620x480")
        win.configure(bg=PALETTE["bg"])

        ttk.Label(win, text="Section key (unique, no spaces):").pack(anchor=tk.W, padx=12, pady=(10,2))
        key_var = tk.StringVar()
        ttk.Entry(win, textvariable=key_var, width=30).pack(padx=12, anchor=tk.W)

        ttk.Label(win, text="Section title:").pack(anchor=tk.W, padx=12, pady=(8,2))
        title_var = tk.StringVar()
        ttk.Entry(win, textvariable=title_var, width=50).pack(padx=12, anchor=tk.W)

        ttk.Label(win, text="LaTeX body (paste or type):").pack(anchor=tk.W, padx=12, pady=(8,2))
        body_txt = tk.Text(win, height=14, font=("DejaVu Sans Mono", 9),
                           bg=PALETTE["surface"], fg=PALETTE["text"])
        body_txt.pack(fill=tk.BOTH, expand=True, padx=12)

        def _do_append():
            key = key_var.get().strip().replace(" ", "_")
            title = title_var.get().strip()
            body = body_txt.get("1.0", tk.END).strip()
            if not (key and title):
                messagebox.showwarning("Missing", "Key and title are required.", parent=win)
                return
            try:
                LaTeXProject(proj_dir).append_section(key, title, body)
                messagebox.showinfo("Done", f"Section '{title}' appended.", parent=win)
                win.destroy()
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=win)

        ttk.Button(win, text="Append", command=_do_append).pack(pady=8)

    def _latex_import_figure(self):
        import sys as _sys, os as _os
        _src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "src")
        if _src not in _sys.path:
            _sys.path.insert(0, _src)
        from latex_project import LaTeXProject

        proj_dir = self._choose_directory(title="Select LaTeX project folder")
        if not proj_dir:
            return
        src = filedialog.askopenfilename(
            title="Select figure file",
            filetypes=[("Figures", "*.pdf *.png *.eps *.jpg"), ("All", "*")]
        )
        if not src:
            return
        caption = simpledialog.askstring("Caption", "Figure caption:", initialvalue="") or ""
        try:
            snippet = LaTeXProject(proj_dir).import_figure(src, caption=caption)
            win = tk.Toplevel(self.root)
            win.title("LaTeX snippet")
            win.geometry("500x180")
            txt = tk.Text(win, font=("DejaVu Sans Mono", 9), wrap=tk.NONE)
            style_text_widget(txt)
            txt.insert(tk.END, snippet)
            txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
            ttk.Button(win, text="Close", command=win.destroy).pack(pady=4)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _latex_add_collab(self):
        import sys as _sys, os as _os
        _src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "src")
        if _src not in _sys.path:
            _sys.path.insert(0, _src)
        from latex_project import LaTeXProject

        proj_dir = self._choose_directory(title="Select LaTeX project folder")
        if not proj_dir:
            return
        name  = simpledialog.askstring("Name",  "Collaborator name:") or ""
        email = simpledialog.askstring("Email", "Collaborator email:") or ""
        remote = simpledialog.askstring("Remote URL",
                                        "Git remote URL (leave blank to skip):",
                                        initialvalue="") or None
        if not (name and email):
            return
        try:
            LaTeXProject(proj_dir).add_collaborator(name, email, remote_url=remote)
            messagebox.showinfo("Done", f"Collaborator {name} <{email}> registered.")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _append_mso_report_section(self):
        """Generate an MSO run_report section and append it to an existing LaTeX project.

        run_report.py has no argparse of its own -- it only accepts a full
        cfg dict via ``--config <cfg.yaml>`` (the same dict
        interactive_session() would have built) or falls through to that
        blocking interactive prompt (see run_report.py main(), and
        mso_studio.core.mso_reports's module docstring, which documents this
        as a known pre-existing mismatch). This dialog only collects a
        metadata YAML + an output dir, so it cannot assemble the full
        multi-stage cfg (stage names, per-threshold cost CSVs, etc.) without
        the larger rewrite that's out of scope here. Instead it builds the
        smallest valid single-stage cfg from what it does collect (plus one
        optional error-CSV folder prompt, since analysis/plot/latex
        generation all tolerate empty per-stage data -- see
        mso_io.mso_analysis.run_full_analysis, which `.get()`s every
        per-stage field with a default) and calls run_report.py --config,
        instead of the old positional-args form that run_report.py doesn't
        understand and that used to hang waiting on stdin.
        """
        import sys as _sys, os as _os
        _src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "src")
        if _src not in _sys.path:
            _sys.path.insert(0, _src)
        # 1) Choose LaTeX project folder
        proj_dir = self._choose_directory(title="Select LaTeX project folder to append into")
        if not proj_dir:
            return
        # 2) Choose the MSO metadata YAML (run_report input)
        meta_path = filedialog.askopenfilename(
            title="Select MSO report metadata YAML",
            filetypes=[("YAML", "*.yaml *.yml"), ("All", "*")],
        )
        if not meta_path:
            return
        # 3) Choose output directory for run_report artefacts
        out_dir = self._choose_directory(title="Select output directory for report artefacts")
        if not out_dir:
            return
        # 3b) Optional: folder of error CSVs -- the report's core content.
        # Skippable; an empty stage still produces a valid (sparse,
        # metadata-only) report rather than crashing (see docstring above).
        error_folder = self._choose_directory(
            title="Select folder of error CSVs to include (Cancel for a metadata-only report)"
        ) or None

        # 4) Assemble the smallest valid run_report cfg and hand it a real
        # --config <yaml>, instead of the CLI args run_report.py can't parse.
        import yaml as _yaml
        import tempfile as _tempfile
        cfg = {
            "n_stages": 1,
            "stage_names": ["MSO Optimization"],
            "stage_labels": ["MSO"],
            "thresholds": [0.01],
            "primary_threshold": 0.01,
            "yaml_path": meta_path,
            "stage_configs": [{
                "name": "MSO Optimization",
                "label": "MSO",
                "error_folder": error_folder,
                "cost_csvs": {},
                "prs_stats_csv": None,
                "sensitivity_csv": None,
                "convergence_csv": None,
                "idt_plots_folder": None,
            }],
            "output_dir": out_dir,
            "compile_pdf": True,
        }
        # Required fields we cannot fabricate a meaningful value for --
        # fail fast with a clear message instead of letting run_report.py
        # hang on interactive_session() or crash deep inside analysis.
        if not meta_path or not out_dir:
            messagebox.showerror(
                "Missing input",
                "MSO report needs a metadata YAML and an output directory; "
                "cannot proceed.",
            )
            return
        try:
            with _tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False,
                dir=out_dir, prefix="_run_report_cfg_",
            ) as _fh:
                _yaml.safe_dump(cfg, _fh)
                cfg_path = _fh.name
        except Exception as exc:
            messagebox.showerror("Error", f"Could not write run_report cfg:\n{exc}")
            return

        # 5) Run run_report as a subprocess (it has heavy deps)
        run_report_py = _os.path.join(_src, "run_report.py")
        if not _os.path.exists(run_report_py):
            messagebox.showerror("Not found", f"run_report.py not found at:\n{run_report_py}")
            return
        import subprocess as _sp2
        result = _sp2.run(
            [sys.executable, run_report_py, "--config", cfg_path],
            capture_output=True, text=True,
        )
        tex_candidates = []
        for root, _, files in _os.walk(out_dir):
            for f in files:
                if f.endswith(".tex"):
                    tex_candidates.append(_os.path.join(root, f))
        if not tex_candidates:
            if result.returncode != 0:
                messagebox.showerror("run_report failed",
                                     result.stderr[:1200] or result.stdout[:1200])
            else:
                messagebox.showwarning("No .tex", "run_report ran but produced no .tex file.")
            return
        # Use the first .tex found
        tex_path = tex_candidates[0]
        try:
            with open(tex_path, "r", encoding="utf-8") as fh:
                body = fh.read()
        except Exception as exc:
            messagebox.showerror("Read error", str(exc))
            return
        # 6) Append as section in the LaTeX project
        from latex_project import LaTeXProject
        section_key = _os.path.splitext(_os.path.basename(meta_path))[0]
        title = simpledialog.askstring("Section title",
                                        "Title for this report section:",
                                        initialvalue="MSO Optimization Report") or "MSO Report"
        try:
            LaTeXProject(proj_dir).append_section(section_key, title, body)
            messagebox.showinfo("Done",
                                f"Section '{title}' appended to LaTeX project in:\n{proj_dir}")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _open_ckcsv_viewer(self):
        """Open the Chemkin Pro ckcsv viewer panel."""
        import sys as _sys, os as _os
        _src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "src")
        if _src not in _sys.path:
            _sys.path.insert(0, _src)
        try:
            from pychemkin_reader import CKCSVViewerPanel
        except ImportError as exc:
            messagebox.showerror("Import error", str(exc))
            return
        win = tk.Toplevel(self.root)
        win.title("Chemkin Pro ckcsv Viewer")
        win.geometry("1000x640")
        win.configure(bg=PALETTE["bg"])
        panel = CKCSVViewerPanel(win, palette=PALETTE)
        panel.pack(fill=tk.BOTH, expand=True)

    def _open_diagnostics_dialog(self):
        """Open the Mechanism Diagnostics panel (Task 5C)."""
        win = tk.Toplevel(self.root)
        win.title("Mechanism Diagnostics")
        win.configure(bg=PALETTE["bg"])
        win.geometry("700x560")

        # --- top controls ---
        top = ttk.Frame(win)
        top.pack(fill=tk.X, padx=16, pady=(14, 6))
        ttk.Label(top, text="Mechanism file (Cantera YAML):", style="Header.TLabel").pack(anchor=tk.W)
        mf_frame = ttk.Frame(top)
        mf_frame.pack(fill=tk.X, pady=4)
        mech_var = tk.StringVar()
        ttk.Entry(mf_frame, textvariable=mech_var, width=60).pack(side=tk.LEFT)
        ttk.Button(mf_frame, text="Browse…",
                   command=lambda: mech_var.set(
                       filedialog.askopenfilename(filetypes=[("YAML", "*.yaml *.yml"), ("CTI", "*.cti"), ("All", "*")])
                       or mech_var.get()
                   )).pack(side=tk.LEFT, padx=4)

        param_frame = ttk.Frame(top)
        param_frame.pack(fill=tk.X, pady=4)
        for label, var_name, default, width in [
            ("Thermo tol (ΔCp/R):", "thermo_tol", "0.01", 6),
            ("Coll-limit (cm³/mol/s):", "coll_lim", "1e14", 8),
            ("Rev-rate tol:", "rev_tol", "0.1", 6),
            ("T ref (K):", "t_ref", "1500", 6),
        ]:
            ttk.Label(param_frame, text=label).pack(side=tk.LEFT, padx=(8, 2))
            v = tk.StringVar(value=default)
            setattr(win, f"_d_{var_name}", v)
            ttk.Entry(param_frame, textvariable=v, width=width).pack(side=tk.LEFT)

        ttk.Button(top, text="Run diagnostics", command=lambda: _run()).pack(pady=6)

        # --- output text box ---
        out_frame = ttk.Frame(win)
        out_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        scroll = tk.Scrollbar(out_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        txt = tk.Text(out_frame, yscrollcommand=scroll.set, font=("DejaVu Sans Mono", 9),
                      bg=PALETTE["surface"], fg=PALETTE["text"], relief=tk.FLAT, wrap=tk.NONE)
        txt.pack(fill=tk.BOTH, expand=True)
        scroll.config(command=txt.yview)

        def _run():
            mech = mech_var.get().strip()
            if not mech:
                messagebox.showwarning("No file", "Please choose a mechanism YAML first.", parent=win)
                return
            try:
                thermo_tol = float(win._d_thermo_tol.get())
                coll_lim   = float(win._d_coll_lim.get())
                rev_tol    = float(win._d_rev_tol.get())
                t_ref      = float(win._d_t_ref.get())
            except ValueError as exc:
                messagebox.showerror("Bad parameter", str(exc), parent=win)
                return

            txt.delete("1.0", tk.END)
            txt.insert(tk.END, f"Running diagnostics on:\n  {mech}\n\n")
            win.update_idletasks()

            try:
                import sys as _sys, os as _os
                _diag_src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                          "src", "MUQ-SAC")
                if _diag_src not in _sys.path:
                    _sys.path.insert(0, _diag_src)
                from mech_diagnostics import MechDiagnostics
                import io

                diag = MechDiagnostics(mech, thermo_tol=thermo_tol,
                                       coll_limit_cgs=coll_lim,
                                       rev_ratio_tol=rev_tol, T_ref=t_ref)
                report = diag.run()

                # Capture print_report output
                buf = io.StringIO()
                old_stdout = _sys.stdout
                _sys.stdout = buf
                MechDiagnostics.print_report(report)
                _sys.stdout = old_stdout
                txt.insert(tk.END, buf.getvalue())
            except Exception as exc:
                txt.insert(tk.END, f"ERROR: {exc}\n")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _preview(self):
        cfg = self._collect()
        text = config_to_yaml(cfg)
        self._preview_text.delete("1.0", tk.END)
        self._preview_text.insert("1.0", text)
        self._status.set("Preview refreshed.")

    def _save_opt(self):
        cfg = self._collect()
        path = filedialog.asksaveasfilename(
            defaultextension=".opt",
            filetypes=[("target.opt files", "*.opt *.yaml"), ("All files", "*")],
            initialfile="target.opt",
        )
        if not path:
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            fh.write(config_to_yaml(cfg))
        self._status.set(f"Saved: {path}")
        messagebox.showinfo("Saved", f"target.opt written to:\n{path}")

    def _quick_save(self):
        cfg = self._collect()
        path = self._quick_path.get()
        if not path:
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            fh.write(config_to_yaml(cfg))
        self._status.set(f"Quick-saved: {path}")

    # ── Multi-mechanism fan-out (one-at-a-time / fuse) ─────────────────────────

    def _mm_translated_rows(self, translations):
        """Deep-copy the Targets-tab rows with fuel/oxidizer/bath species names
        substituted per the given {original_name: translated_name} map."""
        rows = []
        for _, vs in self._target_rows:
            d = {k: v.get() for k, v in vs.items()}
            try:
                dev_pct = float(d.pop("deviation_pct", 10) or 10)
                obs = float(d.get("observed", 100) or 100)
            except ValueError:
                dev_pct, obs = 10.0, 100.0
            d["deviation"] = obs * dev_pct / 100.0
            for key in ("fuel_species", "oxidizer_species", "bath_species"):
                if d.get(key) in translations:
                    d[key] = translations[d[key]]
            rows.append(d)
        return rows

    def _mm_confirm_dialog(self, mech_label, rxn, translations, notes):
        """Low-confidence species-translation / global-reaction confirmation.
        Mutates `translations` in place with any edits. Returns (proceed, rxn)."""
        result = {"proceed": False, "rxn": rxn}
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Confirm — {mech_label}")
        dlg.geometry("620x460")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text=f"Please confirm for: {mech_label}", font=FONTS["header"]).pack(pady=(10, 4))
        ttk.Label(dlg, text="Some values could not be verified automatically (no InChIKey match, or "
                            "an unrecognized element in the fuel formula) — review before writing files.",
                  foreground="orange", wraplength=580).pack(padx=12)

        self._section(dlg, "Global reaction")
        rxn_var = tk.StringVar(value=rxn)
        ttk.Entry(dlg, textvariable=rxn_var, width=70).pack(padx=12, pady=4, fill=tk.X)

        self._section(dlg, "Species mapping (edit if wrong)")
        map_frame = ttk.Frame(dlg)
        map_frame.pack(fill=tk.X, padx=12)
        trans_vars = {}
        for sp, translated in translations.items():
            row = ttk.Frame(map_frame)
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=sp, width=16).pack(side=tk.LEFT)
            ttk.Label(row, text="→").pack(side=tk.LEFT, padx=4)
            v = tk.StringVar(value=translated)
            ttk.Entry(row, textvariable=v, width=20).pack(side=tk.LEFT)
            trans_vars[sp] = v

        self._section(dlg, "Notes")
        notes_box = tk.Text(dlg, height=6, wrap=tk.WORD)
        style_text_widget(notes_box)
        notes_box.insert("1.0", "\n".join(notes) or "(none)")
        notes_box.configure(state="disabled")
        notes_box.pack(fill=tk.X, padx=12, pady=4)

        def _accept():
            result["proceed"] = True
            result["rxn"] = rxn_var.get()
            for sp, v in trans_vars.items():
                translations[sp] = v.get()
            dlg.destroy()

        def _cancel():
            result["proceed"] = False
            dlg.destroy()

        btn_row = ttk.Frame(dlg)
        btn_row.pack(pady=10)
        ttk.Button(btn_row, text="Accept", command=_accept).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_row, text="Cancel (skip this mechanism)", command=_cancel).pack(side=tk.LEFT)

        dlg.wait_window()
        return result["proceed"], result["rxn"]

    def _mm_fuel_blend_raw(self):
        """[(species_name, mole_fraction_str), ...] from the Files & Paths fuel-blend table."""
        return [(spv.get().strip(), xfv.get()) for kv, spv, xfv, cov, mwv, nuv, nu_entry, _ in self._fuel_rows
                if spv.get().strip()]

    def _mm_translate_and_derive_rxn(self, fuel_blend_raw, glossary_path=None, fused_lookup=None):
        """Translate each fuel species and derive the global reaction.

        fused_lookup: optional callable(species_name) -> (translated, confidence,
        note), used for the fuse path (InChIKey lookup against the fused
        mechanism's own species table) instead of a per-mechanism glossary file.

        Returns (translations: dict, rxn: str, low_conf_notes: list[str]).
        """
        from chem_data import compute_nu_o2
        translations, low_conf_notes = {}, []
        for sp, xf in fuel_blend_raw:
            if fused_lookup:
                translated, confidence, note = fused_lookup(sp)
            else:
                translated, confidence, note = translate_species_for_mechanism(sp, glossary_path)
            translations[sp] = translated
            if confidence == "low":
                low_conf_notes.append(f"{sp} → {translated}: {note}")

        fuel_blend_for_rxn = []
        for sp, xf in fuel_blend_raw:
            try:
                xf_val = float(xf) if xf else 1.0
            except ValueError:
                xf_val = 1.0
            coeff = xf_val if len(fuel_blend_raw) > 1 else 1.0
            fuel_blend_for_rxn.append((translations[sp], coeff, compute_nu_o2(translations[sp])))
        if fuel_blend_for_rxn:
            rxn, rxn_confidence, rxn_note = derive_global_reaction(fuel_blend_for_rxn)
            if rxn_confidence == "low":
                low_conf_notes.append(rxn_note)
        else:
            rxn = ""
            low_conf_notes.append("no fuel blend configured (Files & Paths tab)")
        return translations, rxn, low_conf_notes

    def _build_multi_mechanism_outputs(self):
        """Fan target.opt (+ its mechanism/thermo/transport/.pre/.target inputs)
        out across every mechanism in the Mechanisms tab, per the one-at-a-time
        vs fuse workflow choice (radio button in that tab)."""
        mechs = [(nv.get() or pv.get(), pv.get(), tv.get(), trv.get(), fv.get(), glv.get(), prv.get())
                 for nv, pv, tv, trv, fv, glv, prv in self._mech_rows if pv.get()]
        if not mechs:
            messagebox.showwarning("No mechanisms", "Add at least one mechanism in the Mechanisms tab first.")
            return
        base_cfg = self._collect()
        output_base = base_cfg.get("project", {}).get("output_base_dir", "outputs")
        fuel_blend_raw = self._mm_fuel_blend_raw()

        if self._mech_workflow.get() == "fuse":
            self._mm_build_fused(mechs, base_cfg, output_base, fuel_blend_raw)
        else:
            self._mm_build_one_at_a_time(mechs, base_cfg, output_base, fuel_blend_raw)

    def _mm_build_one_at_a_time(self, mechs, base_cfg, output_base, fuel_blend_raw):
        n_ok = n_skip = 0
        for name, path, thermo, trans, fmt, glossary, pre in mechs:
            out_dir = Path(output_base) / name
            out_dir.mkdir(parents=True, exist_ok=True)

            yaml_path, pre_path = path, pre
            if fmt == "chemkin":
                yaml_path, converted_pre, conv_errors = convert_mechanism_files(
                    path, thermo, trans, out_dir=str(out_dir),
                    scanman_bin=(None if pre else (self._bin_solver.get() if hasattr(self, "_bin_solver") else None)),
                )
                if not pre:
                    pre_path = converted_pre
                if conv_errors:
                    messagebox.showwarning(f"{name}: conversion issues", "\n".join(conv_errors))
                if not yaml_path:
                    n_skip += 1
                    continue

            translations, rxn, low_conf_notes = self._mm_translate_and_derive_rxn(fuel_blend_raw, glossary)

            proceed = True
            if low_conf_notes:
                proceed, rxn = self._mm_confirm_dialog(name, rxn, translations, low_conf_notes)
            if not proceed:
                n_skip += 1
                continue

            rows = self._mm_translated_rows(translations)
            target_path = out_dir / "case.target"
            if rows:
                generate_target_file(rows, str(target_path))

            mech_cfg = deepcopy(base_cfg)
            mech_cfg["Locations"]["mechanism"] = yaml_path
            mech_cfg["Locations"]["thermo_file"] = thermo
            mech_cfg["Locations"]["trans_file"] = trans
            if pre_path:
                mech_cfg["Locations"]["Initial_pre_file"] = pre_path
            if rows:
                mech_cfg["Locations"]["targets"] = str(target_path)
            if rxn:
                mech_cfg["Inputs"]["global_reaction"] = rxn
            mech_cfg["project"]["output_base_dir"] = str(out_dir)
            (out_dir / "target.opt").write_text(config_to_yaml(mech_cfg))
            n_ok += 1

        messagebox.showinfo("Done", f"Built {n_ok} mechanism folder(s) under {output_base}"
                             + (f"  ({n_skip} skipped)" if n_skip else ""))
        self._status.set(f"Built {n_ok} mechanism output folder(s), {n_skip} skipped.")

    def _mm_build_fused(self, mechs, base_cfg, output_base, fuel_blend_raw):
        if len(mechs) < 2:
            messagebox.showwarning("Need 2+ mechanisms", "Fuse mode requires at least 2 mechanisms.")
            return
        try:
            _rmip_src_on_path()
            from rmip.config import RMIPConfig
            from rmip.core.parser import MechanismParser
            from rmip.analysis.graph_comparator import GraphComparator
            from rmip.analysis.fusion import FusionEngine
            from rmip.io.cantera_writer import CanteraYAMLWriter
            from rmip.database.schema import get_species_by_inchi_key
            from rmip.core.canonicalize import smiles_to_inchi
            import sqlite3
        except Exception as e:
            messagebox.showerror("RMIP import failed", str(e))
            return

        db_path = self._rmip_db.get() or "project.db"
        parser = MechanismParser(RMIPConfig(db_path=db_path))
        mech_ids = []
        for name, path, thermo, trans, fmt, glossary, pre in mechs:
            try:
                mech_id = parser.parse(path, glossary_path=glossary or None,
                                        thermo_path=thermo or None, name=name)
                mech_ids.append(mech_id)
            except Exception as e:
                messagebox.showerror(f"Parse failed: {name}", str(e))
                return

        try:
            cmp = GraphComparator(db_path)
            result = cmp.compare(mech_ids)
            engine = FusionEngine(db_path)
            fusion_result = engine.fuse(result, name=f"{self._proj_name.get()}_fused")
        except Exception as e:
            messagebox.showerror("Fusion failed", str(e))
            return

        fused_id = fusion_result.fused_mechanism_id
        out_dir = Path(output_base) / "fused"
        out_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = str(out_dir / "fused_mechanism.yaml")
        try:
            CanteraYAMLWriter(db_path).write(fused_id, yaml_path)
        except Exception as e:
            messagebox.showerror("YAML export failed", str(e))
            return

        def _fused_lookup(species_name):
            smiles = FuelNormalizer.get_smiles(species_name)
            if not smiles:
                return species_name, "low", f"no SMILES known for '{species_name}'"
            _, inchi_key = smiles_to_inchi(smiles)
            if not inchi_key:
                return species_name, "low", f"could not derive an InChIKey for '{species_name}'"
            conn = sqlite3.connect(db_path)
            try:
                rows = get_species_by_inchi_key(conn, inchi_key, fused_id)
            finally:
                conn.close()
            if rows:
                return rows[0]["name"], "high", ""
            return species_name, "low", f"no InChIKey match for '{species_name}' in the fused mechanism"

        translations, rxn, low_conf_notes = self._mm_translate_and_derive_rxn(
            fuel_blend_raw, fused_lookup=_fused_lookup)

        proceed = True
        if low_conf_notes:
            proceed, rxn = self._mm_confirm_dialog("fused mechanism", rxn, translations, low_conf_notes)
        if not proceed:
            self._status.set("Fuse build cancelled.")
            return

        rows = self._mm_translated_rows(translations)
        target_path = out_dir / "case.target"
        if rows:
            generate_target_file(rows, str(target_path))

        mech_cfg = deepcopy(base_cfg)
        mech_cfg["Locations"]["mechanism"] = yaml_path
        if rows:
            mech_cfg["Locations"]["targets"] = str(target_path)
        if rxn:
            mech_cfg["Inputs"]["global_reaction"] = rxn
        mech_cfg["project"]["output_base_dir"] = str(out_dir)
        (out_dir / "target.opt").write_text(config_to_yaml(mech_cfg))

        messagebox.showinfo("Done", f"Fused mechanism built at:\n{out_dir}")
        self._status.set(f"Fused mechanism written to {out_dir}")

    def _load_opt(self):
        path = filedialog.askopenfilename(
            filetypes=[("target.opt / YAML", "*.opt *.yaml"), ("All files", "*")])
        if not path:
            return
        try:
            with open(path) as fh:
                loaded = yaml.safe_load(fh)
            self.cfg = loaded or {}
            messagebox.showinfo("Loaded",
                                f"Loaded: {path}\n\nClose and reopen the GUI (or restart) "
                                "to fully populate all tabs from the loaded file.")
            self._status.set(f"Loaded: {path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="RMIP + MUQ-SAC unified config file generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          python generate_target_opt.py                    # open GUI
          python generate_target_opt.py --no-gui           # print defaults to target.opt
          python generate_target_opt.py target.opt         # pre-load a file in GUI
          python generate_target_opt.py --no-gui \\
              --name H2_Study --fuel H2 --out my.opt
        """),
    )
    parser.add_argument("load", nargs="?", help="Pre-load existing target.opt")
    parser.add_argument("--no-gui", action="store_true", help="CLI-only mode")
    parser.add_argument("--name", help="Project name")
    parser.add_argument("--fuel", help="Fuel name")
    parser.add_argument("--output", help="Output base directory")
    parser.add_argument("--out", help="Output path (CLI mode)")
    args = parser.parse_args()

    if args.no_gui or not _HAS_TK:
        run_cli(args)
        return

    root = tk.Tk()
    _apply_theme(root)          # Task 1B — apply modern dark theme before building UI
    initial_cfg = None
    if args.load and Path(args.load).exists():
        with open(args.load) as fh:
            initial_cfg = yaml.safe_load(fh)

    App(root, initial_cfg=initial_cfg)
    root.mainloop()


if __name__ == "__main__":
    main()
