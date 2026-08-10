#!/usr/bin/env python3
"""
brute_force_sa_gui.py — Standalone GUI for Brute-Force Sensitivity Analysis.

Phase 1 pilot of the GUI-separation plan (see
MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md §1.7):
a thin Tk form wrapping src/Sensitivity_Analysis/sens_3_params.py, the
already-working 3-parameter (A, n, Ea) forward/central-difference
sensitivity-analysis tool -- no new SA logic here, this app only assembles
the target.opt-style config that tool already expects and launches it via
an embedded terminal.

KRUNAL_JULY_23.md point 4 overhaul: this app now replicates the option
surface of src/MUQ-SAC/make_input_file.py (solver, ignition-delay
definition, all target.add options) via the shared, framework-free
src/mso_io/target_add_schema.py + target_add_io.py modules, in three tabs:

  - Config     — load an existing target.opt (unchanged from before).
  - Targets    — preview every case in the loaded .target/.add pair,
                 see which are runnable by the LIVE engine today (solver=
                 zerork / target type=PFR / flux_analysis are MUQ-SAC-only
                 additions the live src/Sensitivity_Analysis/ engine can't
                 execute yet -- flagged, not silently dropped), edit a
                 selected case's .add options, and choose to run all or
                 just a selection.
  - Manual entry — build a brand-new case (no existing .target/.add
                 needed) via a form and append it to a working copy.
  - Plot style — full matplotlib customization (format/dpi/colors/fonts/
                 titles/legend/grid/annotations) applied to
                 sens_3_params.py's own SA plots via SENS3P_PLOT_STYLE_JSON.

Multi-process execution is unchanged: this app only assembles inputs and
launches sens_3_params.py, which owns simulation_manager2_0.py's real
Worker/multiprocessing.Pool -- no SA logic is reimplemented here.

Usage:
    python brute_force_sa_gui.py                      # open GUI, load nothing
    python brute_force_sa_gui.py target.opt           # open GUI, pre-load config
    python brute_force_sa_gui.py --target-opt FILE    # equivalent, explicit flag
"""
from __future__ import annotations

import argparse
import copy
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import yaml

_SRC = str(Path(__file__).resolve().parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    _HAS_TK = True
except ImportError:
    _HAS_TK = False

from gui_common.theme import PALETTE, FONTS, apply_theme
from gui_common.pty_terminal import PtyTerminal, _HAS_PTY_TERMINAL
from gui_common.settings import load_settings, save_settings
from gui_common.run_status_export import add_export_button
from mso_io.run_status import RunStatusReport
from mso_io.plot_style import PlotStyle, EXPORT_FORMATS, LEGEND_LOCATIONS, GRID_AXES
from mso_io.target_add_schema import (
    SOLVERS, TARGET_TYPES, IGN_COND_CHOICES, NewCaseFields, fields_for,
    ADD_DEFAULTS, is_runnable,
)
from mso_io.target_add_io import (
    preview_targets, load_add, save_add, set_case_options, append_case,
    write_filtered_target_file, TargetPreview,
)

_APP_NAME = "brute_force_sa"
_SENS_3_PARAMS_SCRIPT = str(
    Path(__file__).resolve().parent / "src" / "Sensitivity_Analysis" / "sens_3_params.py"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Standalone GUI for Brute-Force Sensitivity Analysis (sens_3_params.py)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("target_opt", nargs="?", default=None,
                   help="Path to an existing target.opt-style YAML to pre-load")
    p.add_argument("--target-opt", dest="target_opt_flag", default=None,
                   help="Equivalent to the positional argument")
    p.add_argument("--no-gui", action="store_true",
                   help="Headless smoke check: load config (if given) and exit, no Tk window")
    return p.parse_args()


class BruteForceSAApp:
    """Standalone Brute-Force SA GUI. No dependency on generate_target_opt.py's
    App class -- loads/saves its own scoped config, launches sens_3_params.py
    directly."""

    def __init__(self, root: "tk.Tk", initial_config_path: str | None = None):
        self.root = root
        self.root.title("Brute-Force Sensitivity Analysis")
        self.root.geometry("1180x820")

        self._cfg: dict = {}
        self._cfg_path_var = tk.StringVar(value=initial_config_path or "")
        self._mech_override_var = tk.StringVar(value="")
        self._out_dir_var = tk.StringVar(value="outputs/sa")
        self._status_var = tk.StringVar(value="Load a target.opt file to begin.")

        # Targets tab state
        self._targets: List[TargetPreview] = []
        self._add_data: Dict[str, dict] = {}
        self._selected_ids: set = set()
        self._selected_rows: List[str] = []       # tree iids -> self._row_source
        self._row_source: Dict[str, tuple] = {}    # iid -> (source_target_path, line_no)
        self._row_source_path: Dict[int, str] = {}  # id(TargetPreview) -> source path
        self._run_selected_only = tk.BooleanVar(value=False)
        self._field_vars: Dict[str, tk.StringVar] = {}
        self._current_target_id: Optional[str] = None

        # Manual-entry tab state
        self._manual_target_type = tk.StringVar(value="Tig")
        self._manual_solver = tk.StringVar(value="cantera")
        self._manual_vars: Dict[str, tk.StringVar] = {}

        # Plot-style tab state
        self._style = PlotStyle()
        self._style_vars: Dict[str, tk.Variable] = {}

        settings = load_settings(_APP_NAME)
        if not initial_config_path and settings.get("last_target_opt"):
            initial_config_path = settings["last_target_opt"]
            self._cfg_path_var.set(initial_config_path)

        self._build_ui()

        if initial_config_path:
            self._load_config(initial_config_path)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text="Brute-Force Sensitivity Analysis",
                  font=FONTS["header"]).pack(anchor=tk.W)
        ttk.Label(outer,
                  text="Wraps src/Sensitivity_Analysis/sens_3_params.py — perturbs each "
                       "reaction's A, n, and Ea independently (forward/central difference).",
                  foreground=PALETTE["text_dim"], wraplength=1100).pack(anchor=tk.W, pady=(0, 10))

        nb = ttk.Notebook(outer)
        nb.pack(fill=tk.BOTH, expand=True)
        self._nb = nb

        config_tab = ttk.Frame(nb, padding=8)
        targets_tab = ttk.Frame(nb, padding=8)
        manual_tab = ttk.Frame(nb, padding=8)
        style_tab = ttk.Frame(nb, padding=8)
        nb.add(config_tab, text="Config")
        nb.add(targets_tab, text="Targets")
        nb.add(manual_tab, text="Manual entry")
        nb.add(style_tab, text="Plot style")

        self._build_config_tab(config_tab)
        self._build_targets_tab(targets_tab)
        self._build_manual_tab(manual_tab)
        self._build_style_tab(style_tab)

        # ── Run + live output (shared across all tabs) ─────────────────
        run_frame = ttk.LabelFrame(outer, text="Run", padding=8)
        run_frame.pack(fill=tk.X, pady=(10, 0))
        out_row = ttk.Frame(run_frame)
        out_row.pack(fill=tk.X)
        ttk.Label(out_row, text="Output dir", width=12).pack(side=tk.LEFT)
        ttk.Entry(out_row, textvariable=self._out_dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(out_row, text="Browse…", command=self._browse_out_dir).pack(
            side=tk.LEFT, padx=(6, 0))

        btn_row = ttk.Frame(run_frame)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        self._run_btn = ttk.Button(btn_row, text="Run SA (sens_3_params.py)",
                                    command=self._run_sa)
        self._run_btn.pack(side=tk.LEFT)
        add_export_button(btn_row, self._build_run_status).pack(side=tk.LEFT, padx=(6, 0))
        self._gate_label = ttk.Label(btn_row, text="", foreground=PALETTE["warning"])
        self._gate_label.pack(side=tk.LEFT, padx=(10, 0))
        if not _HAS_PTY_TERMINAL:
            ttk.Label(btn_row, text="⚠ pyte not installed — run: pip install pyte",
                      foreground=PALETTE["warning"]).pack(side=tk.LEFT, padx=8)

        term_frame = ttk.LabelFrame(outer, text="Live output", padding=4)
        term_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self._terminal = PtyTerminal(term_frame, rows=14, cols=110)
        self._terminal.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, textvariable=self._status_var, style="Status.TLabel"
                  ).pack(anchor=tk.W, pady=(6, 0))

    def _build_config_tab(self, parent) -> None:
        cfg_frame = ttk.LabelFrame(parent, text="target.opt configuration", padding=8)
        cfg_frame.pack(fill=tk.X, pady=(0, 10))
        row = ttk.Frame(cfg_frame)
        row.pack(fill=tk.X)
        ttk.Entry(row, textvariable=self._cfg_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="Load…", command=self._browse_and_load).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(row, text="Reload", command=self._reload_config).pack(side=tk.LEFT, padx=(6, 0))

        self._cfg_summary = ttk.Label(cfg_frame, text="(nothing loaded)",
                                       foreground=PALETTE["text_dim"], justify=tk.LEFT)
        self._cfg_summary.pack(anchor=tk.W, pady=(6, 0))

        mech_frame = ttk.LabelFrame(parent, text="Mechanism (optional override)", padding=8)
        mech_frame.pack(fill=tk.X, pady=(0, 10))
        mech_row = ttk.Frame(mech_frame)
        mech_row.pack(fill=tk.X)
        ttk.Entry(mech_row, textvariable=self._mech_override_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(mech_row, text="Browse…", command=self._browse_mechanism).pack(
            side=tk.LEFT, padx=(6, 0))
        ttk.Label(mech_frame,
                  text="Leave blank to use the mechanism already set in the loaded "
                       "target.opt's Locations.mechanism.",
                  foreground=PALETTE["text_dim"]).pack(anchor=tk.W, pady=(4, 0))

    # -- Targets tab ----------------------------------------------------

    def _build_targets_tab(self, parent) -> None:
        top = ttk.Frame(parent)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Every case in the loaded .target/.add pair. Rows marked "
                             "⚠ use a solver/target-type combo (zerork / PFR / "
                             "flux_analysis) only src/MUQ-SAC/'s make_input_file.py "
                             "supports -- the live engine can't run them yet.",
                  foreground=PALETTE["text_dim"], wraplength=1100, justify=tk.LEFT
                  ).pack(anchor=tk.W)

        body = ttk.Frame(parent)
        body.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        tree_frame = ttk.Frame(body)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        cols = ("line", "id", "type", "solver", "T", "P", "runnable")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                   selectmode="extended", height=16)
        for c, w in zip(cols, (40, 140, 60, 90, 70, 70, 60)):
            self._tree.heading(c, text=c.upper())
            self._tree.column(c, width=w, anchor=tk.W)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vs = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vs.set)
        vs.pack(side=tk.LEFT, fill=tk.Y)
        self._tree.bind("<<TreeviewSelect>>", self._on_target_select)
        self._tree.tag_configure("blocked", foreground=PALETTE["warning"])

        sel_row = ttk.Frame(body)
        sel_row.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ttk.Checkbutton(sel_row, text="Run only the rows selected above",
                         variable=self._run_selected_only).pack(side=tk.LEFT)
        ttk.Button(sel_row, text="Select all", command=lambda: self._tree.selection_set(self._tree.get_children())
                   ).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(sel_row, text="Clear selection", command=lambda: self._tree.selection_remove(self._tree.get_children())
                   ).pack(side=tk.LEFT, padx=(6, 0))

        # Selected case's .add option editor
        edit_frame = ttk.LabelFrame(body, text="Selected case — .add options", padding=8)
        edit_frame.grid(row=0, column=1, sticky="nsew")
        edit_frame.columnconfigure(1, weight=1)
        self._edit_holder = ttk.Frame(edit_frame)
        self._edit_holder.pack(fill=tk.BOTH, expand=True)
        self._edit_placeholder = ttk.Label(
            self._edit_holder, text="Select a single case on the left to edit its options.",
            foreground=PALETTE["text_dim"], wraplength=320)
        self._edit_placeholder.pack(anchor=tk.W)
        ttk.Button(edit_frame, text="Apply to this case", command=self._apply_case_edits
                   ).pack(anchor=tk.W, pady=(6, 0))

    def _on_target_select(self, _evt=None) -> None:
        sel = self._tree.selection()
        self._selected_ids = {self._tree.set(iid, "id") for iid in sel}
        self._selected_rows = list(sel)   # tree iids -> self._row_source
        for w in self._edit_holder.winfo_children():
            w.destroy()
        self._field_vars = {}
        if len(sel) != 1:
            self._current_target_id = None
            ttk.Label(self._edit_holder,
                      text="Select a single case to edit its options."
                           if len(sel) == 0 else
                           f"{len(sel)} cases selected — bulk edit not supported, "
                           "select one to edit.",
                      foreground=PALETTE["text_dim"], wraplength=320).pack(anchor=tk.W)
            return

        dataset_id = self._tree.set(sel[0], "id")
        self._current_target_id = dataset_id
        target_type = self._tree.set(sel[0], "type") or "Tig"
        add_entry = self._add_data.get(dataset_id, {})
        solver = add_entry.get("solver", ADD_DEFAULTS["solver"])

        ok, reason = is_runnable(solver, target_type, bool(add_entry.get("flux_analysis", False)))
        if not ok:
            ttk.Label(self._edit_holder, text=f"⚠ Not runnable by the live engine: {reason}",
                      foreground=PALETTE["warning"], wraplength=320, justify=tk.LEFT
                      ).pack(anchor=tk.W, pady=(0, 6))

        row = ttk.Frame(self._edit_holder)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="solver", width=16).pack(side=tk.LEFT)
        solver_var = tk.StringVar(value=solver)
        self._field_vars["solver"] = solver_var
        ttk.Combobox(row, textvariable=solver_var, values=SOLVERS, state="readonly", width=16
                     ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        for key in fields_for(target_type, solver):
            if key == "solver":
                continue
            row = ttk.Frame(self._edit_holder)
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=key, width=16).pack(side=tk.LEFT)
            current = add_entry.get(key, ADD_DEFAULTS.get(key, ""))
            var = tk.StringVar(value=str(current))
            self._field_vars[key] = var
            if key == "ign_cond":
                ttk.Combobox(row, textvariable=var, values=IGN_COND_CHOICES,
                             state="readonly", width=16).pack(side=tk.LEFT, fill=tk.X, expand=True)
            else:
                ttk.Entry(row, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _apply_case_edits(self) -> None:
        if not self._current_target_id:
            messagebox.showinfo("No case selected", "Select a single case first.")
            return
        overrides = {}
        for key, var in self._field_vars.items():
            raw = var.get().strip()
            overrides[key] = _coerce(raw)
        self._add_data = set_case_options(self._add_data, self._current_target_id, overrides)
        self._status_var.set(f"Updated .add options for {self._current_target_id} "
                              "(applies to the working copy used at Run time).")

    # -- Manual entry tab -------------------------------------------------

    def _build_manual_tab(self, parent) -> None:
        ttk.Label(parent,
                  text="Build a brand-new case without an existing .target/.add file. "
                       "Appended to a working copy on Run (existing files, if loaded, "
                       "are never overwritten).",
                  foreground=PALETTE["text_dim"], wraplength=1100).pack(anchor=tk.W, pady=(0, 8))

        form = ttk.Frame(parent)
        form.pack(fill=tk.X)
        form.columnconfigure(1, weight=1)

        def entry_row(r, label, key, default):
            ttk.Label(form, text=label).grid(row=r, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=default)
            self._manual_vars[key] = var
            ttk.Entry(form, textvariable=var).grid(row=r, column=1, sticky="ew", padx=6, pady=2)

        entry_row(0, "Dataset ID", "dataset_id", "manual_case_1")
        ttk.Label(form, text="Target type").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Combobox(form, textvariable=self._manual_target_type, values=TARGET_TYPES,
                     state="readonly", width=16).grid(row=1, column=1, sticky="w", padx=6, pady=2)
        ttk.Label(form, text="Solver").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Combobox(form, textvariable=self._manual_solver, values=SOLVERS,
                     state="readonly", width=16).grid(row=2, column=1, sticky="w", padx=6, pady=2)
        self._manual_gate_label = ttk.Label(form, text="", foreground=PALETTE["warning"])
        self._manual_gate_label.grid(row=3, column=0, columnspan=2, sticky="w")
        self._manual_target_type.trace_add("write", lambda *_: self._refresh_manual_gate())
        self._manual_solver.trace_add("write", lambda *_: self._refresh_manual_gate())

        entry_row(4, "Simulation", "simulation", "Isochor Homo Reactor")
        entry_row(5, "T [K]", "temperature_K", "1000")
        entry_row(6, "P [atm]", "pressure_atm", "1.0")
        entry_row(7, "Fuel (species:frac, …)", "fuel", "H2:0.02")
        entry_row(8, "Oxidizer species", "oxidizer", "O2")
        entry_row(9, "Oxidizer fraction", "oxidizer_x", "0.01")
        entry_row(10, "Bath gas (species:frac, …)", "bath_gas", "Ar:0.97")
        entry_row(11, "Phi", "phi", "N/A")
        entry_row(12, "Observed (IDT, μs or your unit)", "observed", "0")
        entry_row(13, "Deviation (std dev / weight source)", "deviation", "1.0")
        entry_row(14, "Data weight", "data_weight", "1.0")
        entry_row(15, "species (ign_delay_def target)", "species", "OH")
        entry_row(16, "ign_cond", "ign_cond", "max")
        entry_row(17, "ign_delay_def", "ign_delay_def", "OH")

        ttk.Button(parent, text="Add case to working .target/.add",
                   command=self._add_manual_case).pack(anchor=tk.W, pady=(10, 0))
        self._manual_status = ttk.Label(parent, text="", foreground=PALETTE["text_dim"])
        self._manual_status.pack(anchor=tk.W, pady=(4, 0))
        self._refresh_manual_gate()

    def _refresh_manual_gate(self) -> None:
        ok, reason = is_runnable(self._manual_solver.get(), self._manual_target_type.get())
        self._manual_gate_label.config(
            text="" if ok else f"⚠ Not runnable by the live engine yet: {reason}")

    def _parse_species_fracs(self, text: str) -> Dict[str, float]:
        out = {}
        for chunk in text.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            sp, _, frac = chunk.partition(":")
            out[sp.strip()] = float(frac.strip())
        if not out:
            raise ValueError("expected 'species:fraction' pairs, comma-separated")
        return out

    def _add_manual_case(self) -> None:
        try:
            fields = NewCaseFields(
                dataset_id=self._manual_vars["dataset_id"].get().strip(),
                target_type=self._manual_target_type.get(),
                simulation=self._manual_vars["simulation"].get().strip(),
                solver=self._manual_solver.get(),
                temperature_K=float(self._manual_vars["temperature_K"].get()),
                pressure_atm=float(self._manual_vars["pressure_atm"].get()),
                fuel=self._parse_species_fracs(self._manual_vars["fuel"].get()),
                oxidizer=self._manual_vars["oxidizer"].get().strip(),
                oxidizer_x=float(self._manual_vars["oxidizer_x"].get()),
                bath_gas=self._parse_species_fracs(self._manual_vars["bath_gas"].get()),
                phi=self._manual_vars["phi"].get().strip(),
                observed=float(self._manual_vars["observed"].get() or 0),
                deviation=float(self._manual_vars["deviation"].get() or 1.0),
                data_weight=float(self._manual_vars["data_weight"].get() or 1.0),
                species=self._manual_vars["species"].get().strip(),
                add_overrides={
                    "ign_cond": self._manual_vars["ign_cond"].get().strip(),
                    "ign_delay_def": self._manual_vars["ign_delay_def"].get().strip(),
                },
            )
        except ValueError as e:
            messagebox.showerror("Bad input", str(e))
            return
        if not fields.dataset_id:
            messagebox.showerror("Missing dataset ID", "Give the new case a dataset ID.")
            return

        out = Path(self._out_dir_var.get().strip() or "outputs/sa").resolve()
        out.mkdir(parents=True, exist_ok=True)
        working_target = out / "manual_cases.target"
        working_add = out / "manual_cases.add"
        idx = append_case(str(working_target), str(working_add), fields)
        self._manual_status.config(
            text=f"Added case #{idx} '{fields.dataset_id}' → {working_target.name} / "
                 f"{working_add.name}. Point Config's target.opt Locations at these (or "
                 "load them below) to include it in a run.")
        self._refresh_targets_from(str(working_target), str(working_add), merge=True)

    # -- Plot style tab ---------------------------------------------------

    def _build_style_tab(self, parent) -> None:
        ttk.Label(parent,
                  text="Applied to sens_3_params.py's own SA plots via "
                       "SENS3P_PLOT_STYLE_JSON — every field below maps to a real "
                       "matplotlib knob (see src/mso_io/plot_style.py).",
                  foreground=PALETTE["text_dim"], wraplength=1100).pack(anchor=tk.W, pady=(0, 8))

        form = ttk.Frame(parent)
        form.pack(fill=tk.X)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        def combo(r, c, label, key, values, default):
            ttk.Label(form, text=label).grid(row=r, column=c, sticky="w", pady=2)
            var = tk.StringVar(value=str(default))
            self._style_vars[key] = var
            ttk.Combobox(form, textvariable=var, values=values, state="readonly",
                         width=14).grid(row=r, column=c + 1, sticky="w", padx=6, pady=2)

        def entry(r, c, label, key, default):
            ttk.Label(form, text=label).grid(row=r, column=c, sticky="w", pady=2)
            var = tk.StringVar(value=str(default))
            self._style_vars[key] = var
            ttk.Entry(form, textvariable=var, width=18).grid(row=r, column=c + 1, sticky="w", padx=6, pady=2)

        def check(r, c, label, key, default):
            var = tk.BooleanVar(value=default)
            self._style_vars[key] = var
            ttk.Checkbutton(form, text=label, variable=var).grid(
                row=r, column=c, columnspan=2, sticky="w", pady=2)

        combo(0, 0, "Export format", "export_format", EXPORT_FORMATS, "png")
        entry(0, 2, "DPI", "dpi", 150)
        entry(1, 0, "Color scheme (colormap name)", "color_scheme", "default")
        entry(1, 2, "Explicit colors (comma-sep)", "colors", "")
        entry(2, 0, "Font family", "font_family", "")
        entry(2, 2, "Legend font size", "font_size_legend", 9)
        entry(3, 0, "Title font size", "font_size_title", 12)
        entry(3, 2, "Axis label font size", "font_size_axis_label", 10)
        entry(4, 0, "Tick label font size", "font_size_tick_label", 8)
        combo(4, 2, "Legend location", "legend_loc", LEGEND_LOCATIONS, "best")
        entry(5, 0, "Title", "title", "")
        entry(5, 2, "X label", "xlabel", "")
        entry(6, 0, "Y label", "ylabel", "")
        combo(6, 2, "Grid", "grid", GRID_AXES, "none")
        check(7, 0, "Show legend", "show_legend", True)
        check(7, 2, "Tight layout", "tight_layout", True)

    def _collect_style(self) -> PlotStyle:
        v = self._style_vars
        colors_raw = v["colors"].get().strip()
        colors = [c.strip() for c in colors_raw.split(",") if c.strip()] or None
        return PlotStyle(
            export_format=v["export_format"].get(),
            dpi=int(float(v["dpi"].get() or 150)),
            color_scheme=v["color_scheme"].get() or "default",
            colors=colors,
            font_family=v["font_family"].get(),
            font_size_title=int(float(v["font_size_title"].get() or 12)),
            font_size_axis_label=int(float(v["font_size_axis_label"].get() or 10)),
            font_size_tick_label=int(float(v["font_size_tick_label"].get() or 8)),
            font_size_legend=int(float(v["font_size_legend"].get() or 9)),
            title=v["title"].get(),
            xlabel=v["xlabel"].get(),
            ylabel=v["ylabel"].get(),
            show_legend=bool(v["show_legend"].get()),
            legend_loc=v["legend_loc"].get(),
            grid=v["grid"].get(),
            tight_layout=bool(v["tight_layout"].get()),
        )

    # ------------------------------------------------------------------
    # Config load/save
    # ------------------------------------------------------------------

    def _browse_and_load(self) -> None:
        path = filedialog.askopenfilename(
            title="Select target.opt", filetypes=[("YAML", "*.opt *.yaml *.yml"), ("All files", "*.*")])
        if path:
            self._cfg_path_var.set(path)
            self._load_config(path)

    def _reload_config(self) -> None:
        path = self._cfg_path_var.get().strip()
        if path:
            self._load_config(path)

    def _load_config(self, path: str) -> None:
        try:
            with open(path) as fh:
                self._cfg = yaml.safe_load(fh) or {}
        except Exception as e:
            messagebox.showerror("Load failed", f"Could not load {path!r}:\n{e}")
            return

        locations = self._cfg.get("Locations", {})
        stats = self._cfg.get("Stats", {})
        mech = locations.get("mechanism", "(not set)")
        targets = locations.get("targets", "(not set)")
        addendum = locations.get("addendum", "(not set)")
        sa_scheme = stats.get("SA_scheme", "(default)")
        self._cfg_summary.configure(
            text=(f"Mechanism : {mech}\n"
                  f"Targets   : {targets}\n"
                  f"Addendum  : {addendum}\n"
                  f"SA scheme : {sa_scheme}")
        )
        self._status_var.set(f"Loaded {path}")
        save_settings(_APP_NAME, {"last_target_opt": path})

        base = Path(path).resolve().parent
        targets_path = _resolve_maybe(locations.get("targets"), base)
        addendum_path = _resolve_maybe(locations.get("addendum"), base)
        if targets_path and os.path.exists(targets_path):
            self._refresh_targets_from(targets_path, addendum_path, merge=False)
        else:
            self._targets = []
            self._add_data = {}
            self._tree.delete(*self._tree.get_children())

    def _refresh_targets_from(self, target_path: str, add_path: Optional[str], merge: bool) -> None:
        try:
            rows = preview_targets(target_path, add_path)
        except Exception as e:
            messagebox.showerror("Could not read targets", f"{target_path}:\n{e}")
            return
        if add_path and os.path.exists(add_path):
            try:
                add_loaded = load_add(add_path)
            except Exception:
                add_loaded = {}
        else:
            add_loaded = {}

        # Rows carry their source file + within-file line number (tracked
        # by Python object identity in self._row_source_path) so "run
        # selected only" can filter each source file correctly even when
        # merging (e.g. a loaded target.opt's targets + manually-added
        # cases from a separate working file) -- two source files can both
        # have a "line 1", so the Treeview iid must NOT just be the line
        # number once more than one source is present.
        if merge:
            existing_ids = {r.dataset_id for r in self._targets}
            new_rows = [r for r in rows if r.dataset_id not in existing_ids]
            for r in new_rows:
                self._row_source_path[id(r)] = target_path
            self._targets += new_rows
            self._add_data.update(add_loaded)
        else:
            self._targets = rows
            self._add_data = add_loaded
            self._row_source_path = {id(r): target_path for r in rows}

        self._tree.delete(*self._tree.get_children())
        self._row_source = {}    # iid -> (source_target_path, line_no)
        for seq, r in enumerate(self._targets):
            iid = str(seq)
            self._row_source[iid] = (self._row_source_path.get(id(r), target_path), r.line_no)
            tags = () if r.runnable else ("blocked",)
            self._tree.insert("", "end", iid=iid, values=(
                r.line_no, r.dataset_id, r.target_type, r.solver,
                f"{r.temperature_K:g}" if r.temperature_K is not None else "",
                f"{r.pressure_atm:g}" if r.pressure_atm is not None else "",
                "✓" if r.runnable else "⚠",
            ), tags=tags)

        n_blocked = sum(1 for r in self._targets if not r.runnable)
        if n_blocked:
            self._gate_label.config(
                text=f"{n_blocked}/{len(self._targets)} loaded case(s) are not runnable "
                     "by the live engine (see Targets tab).")
        else:
            self._gate_label.config(text="")

    def _browse_mechanism(self) -> None:
        path = filedialog.askopenfilename(
            title="Select mechanism file",
            filetypes=[("CHEMKIN/Cantera", "*.inp *.yaml *.yml"), ("All files", "*.*")])
        if path:
            self._mech_override_var.set(path)

    def _browse_out_dir(self) -> None:
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            self._out_dir_var.set(path)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _run_sa(self) -> None:
        if not self._cfg:
            messagebox.showwarning("No config", "Load a target.opt file first.")
            return

        selected_blocked = [r for r in self._targets
                             if r.dataset_id in self._selected_ids and not r.runnable]
        if self._run_selected_only.get() and selected_blocked:
            names = ", ".join(r.dataset_id for r in selected_blocked)
            if not messagebox.askyesno(
                    "Non-runnable cases selected",
                    f"{len(selected_blocked)} selected case(s) use a solver/target-type "
                    f"the live engine can't execute yet ({names}). They will be included "
                    "in the run and will likely fail or be skipped. Continue anyway?"):
                return

        out_dir = self._out_dir_var.get().strip() or "outputs/sa"
        out = Path(out_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)

        cfg = copy.deepcopy(self._cfg)
        mech_override = self._mech_override_var.get().strip()
        if mech_override:
            cfg.setdefault("Locations", {})["mechanism"] = mech_override

        # Working copy of .add with any per-case edits applied.
        if self._add_data:
            working_add = out / "addendum_working.add"
            save_add(str(working_add), self._add_data)
            cfg.setdefault("Locations", {})["addendum"] = str(working_add)

        # Optionally restrict to just the selected rows. Selected rows may
        # come from more than one source file (the loaded target.opt's
        # .target plus a manual-entry working file) -- filter each source
        # by its own line numbers, then concatenate into one combined file
        # (each line is an independent case, so line order doesn't matter
        # to combustion_target_class's parser).
        if self._run_selected_only.get() and self._selected_rows:
            by_source: Dict[str, List[int]] = {}
            for iid in self._selected_rows:
                src, line_no = self._row_source.get(iid, (None, None))
                if src and line_no:
                    by_source.setdefault(src, []).append(line_no)
            combined = out / "targets_selected.target"
            total = 0
            with open(combined, "w") as dst:
                for src_path, line_nos in by_source.items():
                    part = out / f"_filtered_{Path(src_path).stem}.target"
                    n = write_filtered_target_file(src_path, line_nos, str(part))
                    dst.write(part.read_text())
                    total += n
            if total:
                cfg.setdefault("Locations", {})["targets"] = str(combined)
                self._status_var.set(f"Running {total} selected target row(s)…")

        target_opt_path = out / "target.opt"
        with open(target_opt_path, "w") as fh:
            yaml.safe_dump(cfg, fh, default_flow_style=False, sort_keys=False)

        style = self._collect_style()
        style_path = out / "plot_style.json"
        style.save(str(style_path))
        os.environ["SENS3P_PLOT_STYLE_JSON"] = str(style_path)

        self._terminal.run([sys.executable, _SENS_3_PARAMS_SCRIPT, str(target_opt_path)], cwd=str(out))
        self._status_var.set(f"SA running in embedded terminal (cwd={out})…")

    # -- run-status export (KRUNAL_JULY_23.md point 1) -----------------------
    def _build_run_status(self) -> RunStatusReport:
        locations = self._cfg.get("Locations", {})
        return RunStatusReport(
            tool="Brute-Force Sensitivity Analysis",
            inputs={
                "target.opt": self._cfg_path_var.get(),
                "mechanism (Locations.mechanism)": locations.get("mechanism", ""),
                "mechanism override": self._mech_override_var.get(),
                "targets": locations.get("targets", ""),
                "addendum": locations.get("addendum", ""),
                "selected targets": ", ".join(sorted(self._selected_ids)) or "(all)",
            },
            output_dir=self._out_dir_var.get(),
            options={"SA scheme": self._cfg.get("Stats", {}).get("SA_scheme", ""),
                     "run selected only": str(self._run_selected_only.get())},
            status="unknown",       # sens_3_params.py runs in a live PTY terminal
            summary="live terminal output only -- no structured exit status "
                    "available (embedded PtyTerminal, not a captured subprocess)",
            log=self._terminal.text.get("1.0", "end"),
        )


def _resolve_maybe(path: Optional[str], base: Path) -> Optional[str]:
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = base / p
    return str(p)


def _coerce(raw: str):
    """Best-effort str->native type for a .add option field typed into a
    plain tk.Entry (bool/int/float/str), so booleans round-trip correctly
    instead of becoming the truthy string "False"."""
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def main() -> int:
    args = parse_args()
    target_opt = args.target_opt_flag or args.target_opt

    if args.no_gui or not _HAS_TK:
        if target_opt:
            with open(target_opt) as fh:
                cfg = yaml.safe_load(fh) or {}
            print(f"Loaded {target_opt}: "
                  f"mechanism={cfg.get('Locations', {}).get('mechanism')}")
        else:
            print("No target.opt given (--no-gui smoke check, nothing to load).")
        return 0

    root = tk.Tk()
    apply_theme(root)
    app = BruteForceSAApp(root, initial_config_path=target_opt)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
