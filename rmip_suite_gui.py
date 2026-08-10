#!/usr/bin/env python3
"""
rmip_suite_gui.py — Standalone GUI for the RMIP Suite.

Phase 4 of the GUI-separation plan (see
MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md §1.7,
§1.3, §1.2): the umbrella app KP confirmed during planning -- one window
with 4 internal tabs (Graph Comparison, Mechanism Reduction, Global
Sensitivity Analysis, Active Parameter Selection), each a thin form
wrapping an already-existing, already-working CLI. Mechanism Fusion, which
used to live alongside these in the monolith's single "RMIP Analysis" tab,
now has its own dedicated app instead (mean_value_fusion_gui.py, Phase 3)
per this plan's §1.3 scope decision -- not duplicated here.

Every tab launches its backend via the repo-root `rmip_cli.py` launcher
(NEVER `python3 src/rmip/cli.py` directly or `cd src/rmip && python -m
rmip.cli` -- `src/rmip/io/` is a package literally named `io` that shadows
the stdlib module and crashes the interpreter at startup if `src/rmip/`
ends up as sys.path[0]; already documented in rmip_cli.py's own docstring,
re-confirmed this session). The Active Parameter Selection tab launches
src/ActiveParameterScreen.py directly -- empirically confirmed safe despite
a second, previously-undiscovered io-shadowing directory (`src/io/`, a
completely different package from `src/rmip/io/`) also existing at that
script's own directory level; `python3 src/ActiveParameterScreen.py --help`
runs cleanly (verified this session), so no launcher indirection is needed
for it specifically.

Usage:
    python rmip_suite_gui.py                  # open GUI
    python rmip_suite_gui.py --db project.db  # pre-fill DB path on all tabs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC = str(_ROOT / "src")
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
from gui_common.autosave import AutoSaveManager
from gui_common.target_types import TARGET_TYPES, TARGET_TYPE_FIELDS
from gui_common.run_status_export import add_export_button
from mso_io.run_status import RunStatusReport

_APP_NAME = "rmip_suite"
_RMIP_CLI_LAUNCHER = str(_ROOT / "rmip_cli.py")
_ACTIVE_PARAM_SCRIPT = str(_ROOT / "src" / "ActiveParameterScreen.py")
# Own checkpoint file (gui_common/autosave.py's docstring: each split-out app
# gets its own path, never a shared one). Module-level so tests can
# monkeypatch it the same way tests/test_gui_common.py already does for
# gui_common.settings._SETTINGS_DIR. Shared by this app's two repeatable-row
# editors (TargetBuilderTab's fuel blend, ReductionTab's condition rows).
_CHECKPOINT_PATH = _ROOT / ".gui_settings" / "rmip_suite_checkpoint.json"

# TargetBuilderTab/rmip build-target only supports JSR/PFR (mirrors
# MuqsacBridge.build_target_files' own scope restriction) -- deliberately
# NOT all of TARGET_TYPES.
_BUILDABLE_TARGET_TYPES = ["JSR", "PFR"]

# TARGET_TYPE_FIELDS[type] entries mapped to the `rmip build-target` CLI flag
# each one actually feeds (all are real build_target_files() parameters --
# see MuqsacBridge.build_target_files's extra_add handling).
_TARGET_FIELD_TO_CLI_FLAG = {
    "residenceTime":  ("--residence-time", "float", "1.0"),
    "jsr_species":    ("--species", "str", ""),
    "flf_species":    ("--species", "str", ""),
    "flux_analysis":  ("--flux", "bool", False),
    "flux_element":   ("--flux-element", "str", "C"),
    "pfr_length":     ("--pfr-length", "float", "0.1"),
    "pfr_diameter":   ("--pfr-diameter", "float", "0.02"),
    "pfr_mdot":       ("--pfr-mdot", "float", "1e-3"),
    "pfr_n_points":   ("--pfr-n-points", "int", "200"),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Standalone GUI for the RMIP Suite (graph comparison, "
                    "mechanism reduction, global sensitivity analysis, "
                    "active parameter selection)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--db", default=None, help="RMIP SQLite database path to pre-fill")
    p.add_argument("--no-gui", action="store_true",
                   help="Headless smoke check: verify the DB path exists and exit")
    return p.parse_args()


def _field(parent, label, var, width=40, browse_file=None, browse_dir=False, choices=None):
    row = ttk.Frame(parent)
    row.pack(fill=tk.X, pady=2)
    ttk.Label(row, text=label, width=24).pack(side=tk.LEFT)
    if choices:
        ttk.Combobox(row, textvariable=var, values=choices, width=width,
                     state="readonly").pack(side=tk.LEFT)
    else:
        ttk.Entry(row, textvariable=var, width=width).pack(side=tk.LEFT, fill=tk.X, expand=True)
        if browse_file is not None:
            def _browse():
                path = filedialog.askopenfilename(filetypes=browse_file)
                if path:
                    var.set(path)
            ttk.Button(row, text="Browse…", command=_browse).pack(side=tk.LEFT, padx=(6, 0))
        elif browse_dir:
            def _browse():
                path = filedialog.askdirectory()
                if path:
                    var.set(path)
            ttk.Button(row, text="Browse…", command=_browse).pack(side=tk.LEFT, padx=(6, 0))
    return row


class _TerminalTab:
    """Shared scaffolding for a tab whose only action is: assemble a
    command list, run it via the shared PtyTerminal. Each concrete tab
    supplies _build_fields() and _build_command()."""

    def __init__(self, notebook, title: str, db_var: "tk.StringVar",
                 autosave: "AutoSaveManager | None" = None):
        self.db_var = db_var
        self.title = title
        # Optional shared AutoSaveManager (Phase-3 follow-on Part B) -- only
        # tabs with a repeatable row editor (TargetBuilderTab, ReductionTab's
        # multi-condition rows) actually call .mark_dirty() on it; every
        # other tab just leaves this None, unaffected.
        self.autosave = autosave
        self.frame = ttk.Frame(notebook)
        notebook.add(self.frame, text=title)
        self._status_var = tk.StringVar(value="")
        self._last_command: list | None = None
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.frame, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)
        self._fields_frame = ttk.Frame(outer)
        self._fields_frame.pack(fill=tk.X)
        self._build_fields(self._fields_frame)

        btn_row = ttk.Frame(outer)
        btn_row.pack(fill=tk.X, pady=(8, 8))
        ttk.Button(btn_row, text=f"▶  Run", command=self._run).pack(side=tk.LEFT)
        add_export_button(btn_row, self._build_run_status).pack(side=tk.LEFT, padx=(6, 0))
        if not _HAS_PTY_TERMINAL:
            ttk.Label(btn_row, text="⚠ pyte not installed — run: pip install pyte",
                      foreground=PALETTE["warning"]).pack(side=tk.LEFT, padx=8)
        self._extra_buttons(btn_row)

        term_frame = ttk.LabelFrame(outer, text="Live output", padding=4)
        term_frame.pack(fill=tk.BOTH, expand=True)
        self.terminal = PtyTerminal(term_frame, rows=14, cols=105)
        self.terminal.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, textvariable=self._status_var, style="Status.TLabel"
                  ).pack(anchor=tk.W, pady=(4, 0))

    def _extra_buttons(self, btn_row) -> None:
        """Hook for a concrete tab to add extra action buttons next to Run
        (default: none). See GraphComparisonTab for KRUNAL_JULY_23.md
        point 7's "Launch graph viewer" button."""
        pass

    def _build_fields(self, parent) -> None:
        raise NotImplementedError

    def _build_command(self) -> list:
        raise NotImplementedError

    def _run(self) -> None:
        try:
            cmd = self._build_command()
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            return
        if cmd is None:
            return
        self._last_command = cmd
        self.terminal.run(cmd)
        self._status_var.set("Running in embedded terminal…")

    # -- run-status export (KRUNAL_JULY_23.md point 1) -----------------------
    # Shared across every tab: derives inputs/options from whatever
    # _build_command() last assembled (the CLI invocation IS "the options
    # selected" for these thin CLI-wrapper tabs), plus the RMIP database and
    # an output directory if the concrete tab happens to expose one under
    # the common name `out_dir_var`.
    def _build_run_status(self) -> "RunStatusReport":
        try:
            cmd = self._last_command or self._build_command()
        except Exception:
            cmd = None
        out_dir_var = getattr(self, "out_dir_var", None)
        return RunStatusReport(
            tool=f"RMIP Suite — {self.title}",
            inputs={"RMIP database": self.db_var.get()},
            output_dir=out_dir_var.get() if out_dir_var is not None else None,
            options={"command": " ".join(str(c) for c in cmd)} if cmd else {},
            status="unknown",       # runs in a live PTY terminal, no captured exit code
            summary="live terminal output only -- no structured exit status "
                    "available (embedded PtyTerminal, not a captured subprocess)",
            log=self.terminal.text.get("1.0", "end"),
        )


class GraphComparisonTab(_TerminalTab):
    """Wraps `rmip_cli.py compare-graph` — classify species/reactions
    across mechanisms into UNIVERSAL/PARTIAL/UNIQUE and SHARED_IDENTICAL/
    SHARED_DIVERGENT/UNIQUE buckets."""

    def _build_fields(self, parent) -> None:
        ttk.Label(parent, text="Graph Comparison", font=FONTS["subheader"]).pack(anchor=tk.W)
        ttk.Label(parent,
                  text="Classify species/reactions across ≥2 mechanisms (rmip compare-graph).",
                  foreground=PALETTE["text_dim"]).pack(anchor=tk.W, pady=(0, 6))
        self.mech_ids_var = tk.StringVar(value="")
        self.out_dir_var = tk.StringVar(value="outputs/graph_cmp")
        self.tol_A_var = tk.StringVar(value="0.01")
        self.tol_n_var = tk.StringVar(value="0.001")
        self.tol_Ea_var = tk.StringVar(value="100.0")
        self.viewer_port_var = tk.StringVar(value="8050")
        self.viewer_label_var = tk.StringVar(value="formula")
        _field(parent, "Mechanism IDs (≥2, comma-sep.)", self.mech_ids_var)
        _field(parent, "Output directory", self.out_dir_var, browse_dir=True)
        _field(parent, "Relative tol. on A", self.tol_A_var, width=10)
        _field(parent, "Absolute tol. on n", self.tol_n_var, width=10)
        _field(parent, "Absolute tol. on Ea (J/mol)", self.tol_Ea_var, width=10)
        _field(parent, "Graph viewer port", self.viewer_port_var, width=10)
        _field(parent, "Reaction node label", self.viewer_label_var,
               choices=["formula", "id"])

    def _build_command(self) -> list:
        db = self.db_var.get().strip()
        ids = self.mech_ids_var.get().strip()
        if not db or not ids:
            raise ValueError("Database path and ≥2 mechanism IDs are required.")
        return [
            sys.executable, _RMIP_CLI_LAUNCHER, "compare-graph",
            "--mechs", *ids.split(","), "--db", db,
            "--out", self.out_dir_var.get().strip() or "outputs/graph_cmp",
            "--tol-A", self.tol_A_var.get().strip() or "0.01",
            "--tol-n", self.tol_n_var.get().strip() or "0.001",
            "--tol-Ea", self.tol_Ea_var.get().strip() or "100.0",
        ]

    # -- KRUNAL_JULY_23.md point 7 -- localhost graph viewer -----------------
    def _extra_buttons(self, btn_row) -> None:
        ttk.Button(btn_row, text="🌐 Launch graph viewer", command=self._launch_viewer
                   ).pack(side=tk.LEFT, padx=(6, 0))
        self._link_label = ttk.Label(btn_row, text="", foreground=PALETTE["accent2"],
                                      cursor="hand2")
        self._link_label.pack(side=tk.LEFT, padx=(10, 0))
        self._link_label.bind("<Button-1>", self._open_link)

    def _launch_viewer(self) -> None:
        try:
            cmd = self._build_command()
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            return
        port = self.viewer_port_var.get().strip() or "8050"
        cmd = cmd + ["--serve", "--port", port, "--label", self.viewer_label_var.get()]
        self._last_command = cmd
        self.terminal.run(cmd)
        self._status_var.set(f"Comparing + launching graph viewer on port {port}…")
        self._pending_url = f"http://localhost:{port}"
        self._link_label.configure(text=f"Open {self._pending_url} (once server starts) ↗")
        # Dash's dev server needs ~1-2s to bind after compare-graph's own
        # classification step finishes; open automatically once, the click
        # handler stays available afterward for a manual re-open.
        self.frame.after(2500, self._open_link)

    def _open_link(self, _evt=None) -> None:
        url = getattr(self, "_pending_url", None)
        if url:
            import webbrowser
            webbrowser.open(url)


class ReductionTab(_TerminalTab):
    """Wraps `rmip_cli.py reduce` — DRG/DRGEP/PFA/DRGPSA/DRGSA mechanism
    reduction sweep.

    Phase-3 follow-on Part D adds a repeatable multi-condition row editor
    (FEATURE_GAPS_FROM_MONOLITH.md ranked candidate #5 — the union-reduce
    orchestration, see rmip.reduction.multi_condition): when the tree has
    ≥1 rows, one `--condition T,P,phi,fuel` flag is emitted per row instead
    of the plain single-condition invocation; an empty tree leaves the
    original single-condition behaviour unchanged. Also adds the
    `--mech-path` file picker this tab was missing entirely (needed for
    real Cantera rate evaluation — without it every condition degrades to
    the same unweighted/flux_score fallback)."""

    def _build_fields(self, parent) -> None:
        ttk.Label(parent, text="Mechanism Reduction", font=FONTS["subheader"]).pack(anchor=tk.W)
        ttk.Label(parent,
                  text="DRG/DRGEP/PFA/DRGPSA/DRGSA reduction sweep (rmip reduce). Add one or "
                       "more rows below to run the multi-condition union-reduce workflow "
                       "instead of a single condition.",
                  foreground=PALETTE["text_dim"]).pack(anchor=tk.W, pady=(0, 6))
        self.mech_id_var = tk.StringVar(value="")
        self.method_var = tk.StringVar(value="DRG")
        self.target_var = tk.StringVar(value="")
        self.eps_max_var = tk.StringVar(value="0.5")
        self.eps_steps_var = tk.StringVar(value="51")
        self.out_var = tk.StringVar(value="")
        self.mech_path_var = tk.StringVar(value="")
        _field(parent, "Mechanism ID", self.mech_id_var)
        _field(parent, "Method", self.method_var, choices=["DRG", "DRGEP", "PFA", "DRGPSA", "DRGSA"])
        _field(parent, "Target species (comma-sep.)", self.target_var)
        _field(parent, "Max epsilon", self.eps_max_var, width=10)
        _field(parent, "Epsilon steps", self.eps_steps_var, width=10)
        _field(parent, "Output JSON (blank = default name)", self.out_var)
        _field(parent, "Mechanism file (--mech-path, for Cantera rates)", self.mech_path_var,
               browse_file=[("Cantera/CHEMKIN", "*.yaml *.yml *.inp"), ("All files", "*.*")])

        # ── Multi-condition rows (Part D) ───────────────────────────────
        mc_frame = ttk.LabelFrame(parent, text="Conditions (optional — leave empty for "
                                                "single-condition reduction)", padding=6)
        mc_frame.pack(fill=tk.X, pady=(8, 4))
        columns = ("T_K", "P_atm", "phi", "fuel")
        self._cond_tree = ttk.Treeview(mc_frame, columns=columns, show="headings", height=4)
        for col, label, width in zip(columns, ("T [K]", "P [atm]", "phi", "Fuel"),
                                      (90, 90, 70, 220)):
            self._cond_tree.heading(col, text=label)
            self._cond_tree.column(col, width=width, anchor=tk.W)
        self._cond_tree.pack(fill=tk.X, pady=(0, 4))
        self._cond_rows: list = []  # [(T_K, P_atm, phi, fuel), ...]

        add_row = ttk.Frame(mc_frame)
        add_row.pack(fill=tk.X, pady=2)
        self._cond_T_var = tk.StringVar(value="1000.0")
        self._cond_P_var = tk.StringVar(value="1.0")
        self._cond_phi_var = tk.StringVar(value="1.0")
        self._cond_fuel_var = tk.StringVar(value="H2:1.0")
        ttk.Entry(add_row, textvariable=self._cond_T_var, width=10).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(add_row, textvariable=self._cond_P_var, width=10).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(add_row, textvariable=self._cond_phi_var, width=8).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(add_row, textvariable=self._cond_fuel_var, width=22).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(add_row, text="+ Add condition", command=self._add_cond_row
                   ).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(add_row, text="− Remove selected", command=self._remove_cond_row
                   ).pack(side=tk.LEFT, padx=(4, 0))

    def _add_cond_row(self) -> None:
        try:
            T_K = float(self._cond_T_var.get())
            P_atm = float(self._cond_P_var.get())
            phi = float(self._cond_phi_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "T/P/phi must be numeric.")
            return
        fuel = self._cond_fuel_var.get().strip()
        if not fuel:
            messagebox.showwarning("Missing fuel", "Enter a fuel composition (e.g. H2:1.0).")
            return
        self._cond_tree.insert("", tk.END, values=(T_K, P_atm, phi, fuel))
        self._cond_rows.append((T_K, P_atm, phi, fuel))
        if self.autosave:
            self.autosave.mark_dirty()

    def _remove_cond_row(self) -> None:
        sel = self._cond_tree.selection()
        for item in sel:
            idx = self._cond_tree.index(item)
            self._cond_tree.delete(item)
            if 0 <= idx < len(self._cond_rows):
                del self._cond_rows[idx]
        if sel and self.autosave:
            self.autosave.mark_dirty()

    def _build_command(self) -> list:
        db = self.db_var.get().strip()
        mech_id = self.mech_id_var.get().strip()
        target = self.target_var.get().strip()
        if not db or not mech_id or not target:
            raise ValueError("Database path, mechanism ID, and target species are required.")
        cmd = [
            sys.executable, _RMIP_CLI_LAUNCHER, "reduce", mech_id,
            "--db", db, "--method", self.method_var.get(),
            "--target", target,
            "--eps-max", self.eps_max_var.get().strip() or "0.5",
            "--eps-steps", self.eps_steps_var.get().strip() or "51",
        ]
        if self.out_var.get().strip():
            cmd += ["--out", self.out_var.get().strip()]
        if self.mech_path_var.get().strip():
            cmd += ["--mech-path", self.mech_path_var.get().strip()]
        for T_K, P_atm, phi, fuel in self._cond_rows:
            cmd += ["--condition", f"{T_K},{P_atm},{phi},{fuel}"]
        return cmd


class GSATab(_TerminalTab):
    """Wraps `rmip_cli.py gsa-run` — real Sobol/Morris GSA via SALib +
    Zero-RK's perturbAFactorGSA_mpi.x (this session's earlier work)."""

    def _build_fields(self, parent) -> None:
        ttk.Label(parent, text="Global Sensitivity Analysis", font=FONTS["subheader"]).pack(anchor=tk.W)
        ttk.Label(parent,
                  text="Sobol/Morris GSA over reaction A-factors (rmip gsa-run).",
                  foreground=PALETTE["text_dim"]).pack(anchor=tk.W, pady=(0, 6))
        self.mech_id_var = tk.StringVar(value="")
        self.method_var = tk.StringVar(value="sobol")
        self.n_samples_var = tk.StringVar(value="256")
        self.reactions_var = tk.StringVar(value="all")
        self.zerork_dir_var = tk.StringVar(value="/home/krithika/zero-rk/build2/inst_dir")
        self.T_var = tk.StringVar(value="1000.0")
        self.P_var = tk.StringVar(value="1.0")
        self.phi_var = tk.StringVar(value="1.0")
        self.fuel_var = tk.StringVar(value="")
        self.oxidizer_var = tk.StringVar(value="O2:1.0, N2:3.76")
        _field(parent, "Mechanism ID", self.mech_id_var)
        _field(parent, "Method", self.method_var, choices=["sobol", "morris"])
        _field(parent, "Base sample count N", self.n_samples_var, width=10)
        _field(parent, "Reactions (IDs comma-sep., or 'all')", self.reactions_var)
        _field(parent, "Zero-RK install prefix", self.zerork_dir_var, browse_dir=True)
        _field(parent, "T (K)", self.T_var, width=10)
        _field(parent, "P (atm)", self.P_var, width=10)
        _field(parent, "phi", self.phi_var, width=10)
        _field(parent, "Fuel (e.g. H2:1.0)", self.fuel_var)
        _field(parent, "Oxidizer", self.oxidizer_var)

    def _build_command(self) -> list:
        db = self.db_var.get().strip()
        mech_id = self.mech_id_var.get().strip()
        fuel = self.fuel_var.get().strip()
        if not db or not mech_id or not fuel:
            raise ValueError("Database path, mechanism ID, and fuel are required.")
        return [
            sys.executable, _RMIP_CLI_LAUNCHER, "gsa-run", mech_id,
            "--db", db, "--method", self.method_var.get(),
            "--n-samples", self.n_samples_var.get().strip() or "256",
            "--reactions", self.reactions_var.get().strip() or "all",
            "--zerork-install-prefix", self.zerork_dir_var.get().strip(),
            "--T", self.T_var.get().strip() or "1000.0",
            "--P", self.P_var.get().strip() or "1.0",
            "--phi", self.phi_var.get().strip() or "1.0",
            "--fuel", fuel,
            "--oxidizer", self.oxidizer_var.get().strip() or "O2:1.0, N2:3.76",
        ]


class ActiveParamSelectionTab(_TerminalTab):
    """Wraps src/ActiveParameterScreen.py directly (no rmip_cli.py launcher
    needed -- this script isn't part of the rmip package and empirically
    doesn't hit the io-shadowing crash, verified this session)."""

    def _build_fields(self, parent) -> None:
        ttk.Label(parent, text="Active Parameter Selection", font=FONTS["subheader"]).pack(anchor=tk.W)
        ttk.Label(parent,
                  text="Screen reactions/species by SA sensitivity threshold + carbon-number "
                       "cutoff (src/ActiveParameterScreen.py).",
                  foreground=PALETTE["text_dim"]).pack(anchor=tk.W, pady=(0, 6))
        self.sens_dir_var = tk.StringVar(value=".")
        self.mechanism_var = tk.StringVar(value="mechanism.yaml")
        self.threshold_var = tk.StringVar(value="0.05")
        self.carbon_var = tk.StringVar(value="0")
        self.fuel_var = tk.StringVar(value="Fuel")
        self.results_dir_var = tk.StringVar(value="results")
        self.classification_file_var = tk.StringVar(value="")
        self.generate_xml_var = tk.BooleanVar(value=False)
        self.generate_plots_var = tk.BooleanVar(value=False)
        self.generate_latex_var = tk.BooleanVar(value=False)
        self.filtered_mech_var = tk.BooleanVar(value=False)

        _field(parent, "SA results directory (--sens-dir)", self.sens_dir_var, browse_dir=True)
        _field(parent, "Mechanism YAML", self.mechanism_var,
               browse_file=[("Cantera YAML", "*.yaml *.yml"), ("All files", "*.*")])
        _field(parent, "Sensitivity threshold", self.threshold_var, width=10)
        _field(parent, "Carbon number cutoff", self.carbon_var, width=10)
        _field(parent, "Fuel label", self.fuel_var)
        _field(parent, "Results directory", self.results_dir_var, browse_dir=True)
        _field(parent, "Classification CSV (optional, for XML/plots/LaTeX)",
               self.classification_file_var,
               browse_file=[("CSV", "*.csv"), ("All files", "*.*")])
        ttk.Checkbutton(parent, text="Generate XML", variable=self.generate_xml_var).pack(anchor=tk.W)
        ttk.Checkbutton(parent, text="Generate plots", variable=self.generate_plots_var).pack(anchor=tk.W)
        ttk.Checkbutton(parent, text="Generate LaTeX tables", variable=self.generate_latex_var).pack(anchor=tk.W)
        ttk.Checkbutton(parent, text="Also write filtered mechanism YAML",
                         variable=self.filtered_mech_var).pack(anchor=tk.W)

    def _build_command(self) -> list:
        mech = self.mechanism_var.get().strip()
        if not mech:
            raise ValueError("Mechanism YAML path is required.")
        cmd = [
            sys.executable, _ACTIVE_PARAM_SCRIPT,
            "--sens-dir", self.sens_dir_var.get().strip() or ".",
            "--mechanism", mech,
            "--threshold", self.threshold_var.get().strip() or "0.05",
            "--carbon", self.carbon_var.get().strip() or "0",
            "--fuel", self.fuel_var.get().strip() or "Fuel",
            "--results-dir", self.results_dir_var.get().strip() or "results",
        ]
        needs_class = (self.generate_xml_var.get() or self.generate_plots_var.get()
                       or self.generate_latex_var.get())
        if needs_class:
            if not self.classification_file_var.get().strip():
                raise ValueError("XML/plots/LaTeX require a classification CSV.")
            cmd += ["--classification-file", self.classification_file_var.get().strip()]
        if self.generate_xml_var.get():
            cmd.append("--generate-xml")
        if self.generate_plots_var.get():
            cmd.append("--generate-plots")
        if self.generate_latex_var.get():
            cmd.append("--generate-latex")
        if self.filtered_mech_var.get():
            cmd.append("--filtered-mechanism")
        return cmd


class TargetBuilderTab(_TerminalTab):
    """Wraps `rmip_cli.py build-target` — builds a .target/.add/target.opt
    file set for a single JSR/PFR condition (MuqsacBridge.build_target_files,
    Phase-3 follow-on Part A; FEATURE_GAPS_FROM_MONOLITH.md ranked candidate
    #1). Scoped to EXACTLY what build_target_files() supports: JSR/PFR only
    (other TARGET_TYPES entries have no builder here or anywhere else)."""

    def _build_fields(self, parent) -> None:
        ttk.Label(parent, text="Target Builder", font=FONTS["subheader"]).pack(anchor=tk.W)
        ttk.Label(parent,
                  text="Build a .target/.add/target.opt file set for a JSR/PFR condition "
                       "(rmip build-target). Scoped to JSR/PFR only, matching "
                       "MuqsacBridge.build_target_files -- other target types "
                       "(Tig/Fls/Flf/RCM/Flw) have no builder here.",
                  foreground=PALETTE["text_dim"], wraplength=880).pack(anchor=tk.W, pady=(0, 6))

        self.mech_id_var = tk.StringVar(value="")
        self.base_opt_var = tk.StringVar(value="target.opt")
        self.type_var = tk.StringVar(value="JSR")
        self.solver_var = tk.StringVar(value="cantera")
        self.T_var = tk.StringVar(value="1000.0")
        self.P_var = tk.StringVar(value="1.0")
        self.phi_var = tk.StringVar(value="1.0")
        self.oxidizer_var = tk.StringVar(value="O2:1.0, N2:3.76")
        self.work_dir_var = tk.StringVar(value="outputs/target_builder")
        self.dataset_id_var = tk.StringVar(value="")
        self._extra_vars: dict = {}

        _field(parent, "Mechanism ID", self.mech_id_var)
        _field(parent, "Base target.opt", self.base_opt_var,
               browse_file=[("target.opt", "*.opt"), ("All files", "*.*")])
        type_row = _field(parent, "Target type", self.type_var,
                           choices=_BUILDABLE_TARGET_TYPES)
        # Rebuild the dynamic extra-fields frame whenever the type changes.
        for child in type_row.winfo_children():
            if isinstance(child, ttk.Combobox):
                child.bind("<<ComboboxSelected>>", lambda e: self._rebuild_extra_fields())
        _field(parent, "Solver", self.solver_var, choices=["cantera", "chemkin", "flamemaster"])
        _field(parent, "T (K)", self.T_var, width=10)
        _field(parent, "P (atm)", self.P_var, width=10)
        _field(parent, "phi", self.phi_var, width=10)
        _field(parent, "Oxidizer", self.oxidizer_var)
        _field(parent, "Work directory", self.work_dir_var, browse_dir=True)
        _field(parent, "Dataset id (blank = auto)", self.dataset_id_var)

        # ── Fuel blend row editor (species + mole fraction pairs) ───────
        fuel_frame = ttk.LabelFrame(parent, text="Fuel blend (species + mole fraction)", padding=6)
        fuel_frame.pack(fill=tk.X, pady=(6, 4))
        columns = ("species", "mole_fraction")
        self._fuel_tree = ttk.Treeview(fuel_frame, columns=columns, show="headings", height=4)
        for col, label, width in zip(columns, ("Species", "Mole fraction"), (200, 140)):
            self._fuel_tree.heading(col, text=label)
            self._fuel_tree.column(col, width=width, anchor=tk.W)
        self._fuel_tree.pack(fill=tk.X, pady=(0, 4))
        self._fuel_rows: list = []  # [(species, mole_fraction), ...]

        add_row = ttk.Frame(fuel_frame)
        add_row.pack(fill=tk.X, pady=2)
        self._fuel_sp_var = tk.StringVar(value="")
        self._fuel_frac_var = tk.StringVar(value="1.0")
        ttk.Entry(add_row, textvariable=self._fuel_sp_var, width=20).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(add_row, textvariable=self._fuel_frac_var, width=10).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(add_row, text="+ Add fuel", command=self._add_fuel_row).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(add_row, text="− Remove selected", command=self._remove_fuel_row
                   ).pack(side=tk.LEFT, padx=(4, 0))

        # ── Dynamic per-target-type extra fields ─────────────────────────
        self._extra_frame = ttk.LabelFrame(parent, text="Target-type-specific fields", padding=6)
        self._extra_frame.pack(fill=tk.X, pady=(6, 4))
        self._rebuild_extra_fields()

    def _add_fuel_row(self) -> None:
        sp = self._fuel_sp_var.get().strip()
        if not sp:
            messagebox.showwarning("Missing species", "Enter a fuel species name first.")
            return
        try:
            frac = float(self._fuel_frac_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Mole fraction must be numeric.")
            return
        self._fuel_tree.insert("", tk.END, values=(sp, frac))
        self._fuel_rows.append((sp, frac))
        self._fuel_sp_var.set("")
        if self.autosave:
            self.autosave.mark_dirty()

    def _remove_fuel_row(self) -> None:
        sel = self._fuel_tree.selection()
        for item in sel:
            idx = self._fuel_tree.index(item)
            self._fuel_tree.delete(item)
            if 0 <= idx < len(self._fuel_rows):
                del self._fuel_rows[idx]
        if sel and self.autosave:
            self.autosave.mark_dirty()

    def _rebuild_extra_fields(self) -> None:
        for child in self._extra_frame.winfo_children():
            child.destroy()
        self._extra_vars = {}
        ttype = self.type_var.get()
        for key in TARGET_TYPE_FIELDS.get(ttype, []):
            flag_info = _TARGET_FIELD_TO_CLI_FLAG.get(key)
            if flag_info is None:
                continue  # not a real build_target_files() parameter
            flag, kind, default = flag_info
            if kind == "bool":
                var = tk.BooleanVar(value=bool(default))
                ttk.Checkbutton(self._extra_frame, text=key, variable=var).pack(anchor=tk.W)
            else:
                var = tk.StringVar(value=str(default))
                _field(self._extra_frame, key, var, width=16)
            self._extra_vars[key] = (var, kind, flag)

    def _build_command(self) -> list:
        db = self.db_var.get().strip()
        mech_id = self.mech_id_var.get().strip()
        base_opt = self.base_opt_var.get().strip()
        work_dir = self.work_dir_var.get().strip()
        if not db or not mech_id or not base_opt or not work_dir:
            raise ValueError("Database path, mechanism ID, base target.opt, and work "
                              "directory are all required.")
        if not self._fuel_rows:
            raise ValueError("Add at least one fuel-blend row (species + mole fraction).")

        fuel = ", ".join(f"{sp}:{frac}" for sp, frac in self._fuel_rows)
        cmd = [
            sys.executable, _RMIP_CLI_LAUNCHER, "build-target", mech_id,
            "--db", db, "--base-target-opt", base_opt,
            "--target-type", self.type_var.get(), "--solver", self.solver_var.get(),
            "--fuel", fuel,
            "--oxidizer", self.oxidizer_var.get().strip() or "O2:1.0, N2:3.76",
            "--T", self.T_var.get().strip() or "1000.0",
            "--P", self.P_var.get().strip() or "1.0",
            "--phi", self.phi_var.get().strip() or "1.0",
            "--work-dir", work_dir,
        ]
        if self.dataset_id_var.get().strip():
            cmd += ["--dataset-id", self.dataset_id_var.get().strip()]
        for var, kind, flag in self._extra_vars.values():
            if kind == "bool":
                if var.get():
                    cmd.append(flag)
            else:
                val = str(var.get()).strip()
                if val:
                    cmd += [flag, val]
        return cmd


class ReSpecThImportTab(_TerminalTab):
    """Wraps the EXISTING `rmip_cli.py import-respecth` subcommand (Phase-3
    follow-on Part C; FEATURE_GAPS_FROM_MONOLITH.md ranked candidate #4) —
    no core/CLI change needed here, this is a GUI front-end only."""

    def _build_fields(self, parent) -> None:
        ttk.Label(parent, text="ReSpecTh / RKD XML Importer", font=FONTS["subheader"]).pack(anchor=tk.W)
        ttk.Label(parent,
                  text="Ingest ReSpecTh/PrIMe (RKD XML) experimental data — bridges both the "
                       "legacy .target pipeline and the rmip DB (rmip import-respecth).",
                  foreground=PALETTE["text_dim"]).pack(anchor=tk.W, pady=(0, 6))

        self.xml_path_var = tk.StringVar(value="")
        self.fuel_var = tk.StringVar(value="NH3")
        self.solver_var = tk.StringVar(value="cantera")
        self.out_dir_var = tk.StringVar(value="")
        self.dataset_prefix_var = tk.StringVar(value="")
        self.no_db_var = tk.BooleanVar(value=False)

        xml_row = ttk.Frame(parent)
        xml_row.pack(fill=tk.X, pady=2)
        ttk.Label(xml_row, text="XML file or directory", width=24).pack(side=tk.LEFT)
        ttk.Entry(xml_row, textvariable=self.xml_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        def _browse_file():
            path = filedialog.askopenfilename(filetypes=[("XML", "*.xml"), ("All files", "*.*")])
            if path:
                self.xml_path_var.set(path)

        def _browse_dir():
            path = filedialog.askdirectory()
            if path:
                self.xml_path_var.set(path)

        ttk.Button(xml_row, text="Browse file…", command=_browse_file).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(xml_row, text="Browse dir…", command=_browse_dir).pack(side=tk.LEFT, padx=(6, 0))

        _field(parent, "--fuel (comma-sep. species)", self.fuel_var)
        _field(parent, "--solver", self.solver_var, choices=["cantera", "CHEMKIN_PRO", "FlameMaster"])
        _field(parent, "--out-dir", self.out_dir_var, browse_dir=True)
        _field(parent, "--dataset-prefix", self.dataset_prefix_var)
        ttk.Checkbutton(parent, text="--no-db (legacy artefacts only, skip DB loading)",
                         variable=self.no_db_var).pack(anchor=tk.W, pady=(4, 0))

    def _build_command(self) -> list:
        db = self.db_var.get().strip()
        xml_path = self.xml_path_var.get().strip()
        if not db or not xml_path:
            raise ValueError("Database path and an XML file/directory are required.")
        cmd = [
            sys.executable, _RMIP_CLI_LAUNCHER, "import-respecth", xml_path,
            "--db", db,
            "--fuel", self.fuel_var.get().strip() or "NH3",
            "--solver", self.solver_var.get(),
        ]
        if self.out_dir_var.get().strip():
            cmd += ["--out-dir", self.out_dir_var.get().strip()]
        if self.dataset_prefix_var.get().strip():
            cmd += ["--dataset-prefix", self.dataset_prefix_var.get().strip()]
        if self.no_db_var.get():
            cmd.append("--no-db")
        return cmd


class RMIPSuiteApp:
    """Standalone RMIP Suite GUI -- umbrella window with 6 internal tabs."""

    def __init__(self, root: "tk.Tk", initial_db: str | None = None):
        self.root = root
        self.root.title("RMIP Suite")
        self.root.geometry("980x760")

        self._db_var = tk.StringVar(value=initial_db or "")

        settings = load_settings(_APP_NAME)
        if not initial_db and settings.get("last_db"):
            self._db_var.set(settings["last_db"])

        # Autosave/checkpoint safety net (Phase-3 follow-on Part B --
        # FEATURE_GAPS_FROM_MONOLITH.md ranked candidate #3), shared by this
        # app's two repeatable-row-editor tabs (TargetBuilderTab's fuel
        # blend, ReductionTab's condition rows) -- one checkpoint file for
        # the whole app, per gui_common/autosave.py's own-file-per-app rule.
        self._autosave = AutoSaveManager(self.root, save_callback=self._autosave_save)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text="RMIP Suite", font=FONTS["header"]).pack(anchor=tk.W)
        ttk.Label(outer,
                  text="Graph comparison, mechanism reduction, global sensitivity analysis, "
                       "active parameter selection, target-file building, and ReSpecTh/RKD "
                       "XML import — the RMIP-library-backed tools grouped under one umbrella, "
                       "per the GUI-separation plan's scope decision (mechanism fusion has "
                       "moved to its own app, see mean_value_fusion_gui.py).",
                  foreground=PALETTE["text_dim"], wraplength=920).pack(anchor=tk.W, pady=(0, 8))

        db_row = ttk.Frame(outer)
        db_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(db_row, text="RMIP database (shared by all tabs)", width=30).pack(side=tk.LEFT)
        ttk.Entry(db_row, textvariable=self._db_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(db_row, text="Browse…", command=self._browse_db).pack(side=tk.LEFT, padx=(6, 0))

        nb = ttk.Notebook(outer)
        nb.pack(fill=tk.BOTH, expand=True)

        self.tabs = [
            GraphComparisonTab(nb, "Graph Comparison", self._db_var),
            ReductionTab(nb, "Mechanism Reduction", self._db_var, autosave=self._autosave),
            GSATab(nb, "Global Sensitivity Analysis", self._db_var),
            ActiveParamSelectionTab(nb, "Active Parameter Selection", self._db_var),
            TargetBuilderTab(nb, "Target Builder", self._db_var, autosave=self._autosave),
            ReSpecThImportTab(nb, "ReSpecTh Import", self._db_var),
        ]
        self._reduction_tab = self.tabs[1]
        self._target_builder_tab = self.tabs[4]

    def _browse_db(self) -> None:
        path = filedialog.askopenfilename(
            title="Select RMIP database", filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")])
        if path:
            self._db_var.set(path)
            save_settings(_APP_NAME, {"last_db": path})

    def _autosave_save(self) -> None:
        """AutoSaveManager's save_callback -- snapshot the two repeatable
        row editors (TargetBuilderTab's fuel blend, ReductionTab's
        conditions) so a crash/close doesn't lose in-progress rows."""
        state = {
            "db": self._db_var.get(),
            "target_builder_fuel_rows": getattr(self._target_builder_tab, "_fuel_rows", []),
            "reduction_condition_rows": getattr(self._reduction_tab, "_cond_rows", []),
        }
        _CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CHECKPOINT_PATH.write_text(json.dumps(state, indent=2))

    def _on_close(self) -> None:
        self._autosave.on_close()
        self.root.destroy()


def main() -> int:
    args = parse_args()

    if args.no_gui or not _HAS_TK:
        if args.db:
            print(f"DB path: {args.db} (exists={Path(args.db).exists()})")
        else:
            print("No --db given (--no-gui smoke check, nothing to check).")
        return 0

    root = tk.Tk()
    apply_theme(root)
    app = RMIPSuiteApp(root, initial_db=args.db)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
