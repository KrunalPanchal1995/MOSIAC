#!/usr/bin/env python3
"""
mean_value_fusion_gui.py — Standalone GUI for the Mean Value / Mechanism
Fusion Generator.

Phase 3 of the GUI-separation plan (see
MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md §1.7
and §1.3's scope decision): wraps rmip.analysis.parameter_estimator's
consensus-parameter math via rmip.stubs.FusionEngine (built this session,
2026-07-12) -- geometric mean of A, arithmetic mean of n/Ea across
mechanisms' shared-but-divergent reactions, plus element-balance
validation and CHEMKIN/Cantera-YAML export.

Unlike the other Phase 1/2/3 apps, this one calls the RMIP library directly
in-process (GraphComparator -> build_union_spec -> FusionEngine.fuse()) via
a background thread, rather than shelling out to a subprocess -- this
matches the pattern the monolith's own RMIP Analysis tab already used for
its in-process comparison/reduction workers, since there's no existing
standalone CLI for stubs.FusionEngine specifically (only
rmip.analysis.fusion.FusionEngine has a CLI, `rmip fuse`, which lacks
fuse_overrides/file-writing/element-balance-validation).

Usage:
    python mean_value_fusion_gui.py                  # open GUI
    python mean_value_fusion_gui.py --db project.db  # pre-fill DB path
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
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
from gui_common.settings import load_settings, save_settings
from gui_common.autosave import AutoSaveManager
from gui_common.run_status_export import add_export_button
from mso_io.run_status import RunStatusReport

_APP_NAME = "mean_value_fusion"
# Own checkpoint file (gui_common/autosave.py's docstring: each split-out app
# gets its own path, never a shared one). Module-level so tests can
# monkeypatch it the same way tests/test_gui_common.py already does for
# gui_common.settings._SETTINGS_DIR.
_CHECKPOINT_PATH = _ROOT / ".gui_settings" / "mean_value_fusion_checkpoint.json"
_DEFAULT_GLOSSARY = str(_ROOT / "species_smiles.csv")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Standalone GUI for the Mean Value / Mechanism Fusion Generator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--db", default=None, help="RMIP SQLite database path to pre-fill")
    p.add_argument("--no-gui", action="store_true",
                   help="Headless smoke check: verify the DB path exists and exit")
    # Headless fusion mode (KRUNAL_JULY_23.md PySide6 conversion): runs the
    # SAME _run_fusion() the Tk GUI calls -- there was previously no
    # standalone CLI for rmip.stubs.FusionEngine specifically (only `rmip
    # fuse`, which lacks fuse_overrides/file-writing/element-balance-
    # validation/glossary-backfill) -- so mso_studio.core.fusion shells out
    # to this script rather than importing rmip/Cantera into the PySide6 venv.
    p.add_argument("--fuse", action="store_true",
                   help="Headless fusion: run _run_fusion() with the flags below")
    p.add_argument("--mechs", nargs="+", type=int, help="Mechanism DB ids to fuse (>=2)")
    p.add_argument("--tol-A", type=float, default=0.01)
    p.add_argument("--tol-n", type=float, default=0.001)
    p.add_argument("--tol-Ea", type=float, default=100.0)
    p.add_argument("--output-name", default="Fused_Mech")
    p.add_argument("--output-dir", default="outputs/fusion")
    p.add_argument("--write-cantera", action="store_true")
    p.add_argument("--priority-order", nargs="+", type=int, default=None,
                   help="Mechanism ids, highest priority first (enables priority-pick mode)")
    p.add_argument("--glossary", default=_DEFAULT_GLOSSARY,
                   help="Species glossary CSV for the automatic backfill step "
                        "(pass '' to skip)")
    return p.parse_args()


def _list_mechanisms(db_path: str) -> list:
    """Returns [(id, name, format, n_species, n_reactions), ...]."""
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, name, format, n_species, n_reactions FROM mechanisms ORDER BY id"
        ).fetchall()
    return rows


class FusionDegenerateError(RuntimeError):
    """Raised instead of silently reporting a 0-species/0-reaction (or
    entirely-empty-overlap) "fused" mechanism -- the exact failure mode
    KRUNAL_JULY_23.md reported: fusing Davis-2005 + Keromenes-2013 +
    Li-2015 produced "Fused_Mech (fused, 0 sp / 0 rxn)" with no error at
    all. See _run_fusion's glossary-backfill step and its docstring."""


def _run_fusion(db_path: str, mech_ids: list, tol_A: float, tol_n: float, tol_Ea: float,
                 output_name: str, output_dir: str, write_cantera: bool,
                 priority_order: list | None = None,
                 glossary_path: str | None = _DEFAULT_GLOSSARY,
                 write_uncertainty_csv: bool = True) -> dict:
    """Runs (glossary backfill ->) GraphComparator -> build_union_spec ->
    FusionEngine.fuse() -> validate_element_balance(). Returns a plain dict
    summary (thread-safe to pass back to the Tk main thread via root.after()).

    glossary backfill (KRUNAL_JULY_23.md point 6 -- fusing Davis-2005 +
    Keromenes-2013 + Li-2015 produced "Fused_Mech (fused, 0 sp / 0 rxn)",
    silently): root cause was that those 3 mechanisms were parsed into the
    DB without ``--glossary``, so every species has a null inchi_key and
    every reaction a null canonical_key -- GraphComparator's own (correct,
    deliberate) safety fallback for that case keys each species/reaction
    per-mechanism instead of guessing a cross-mechanism match, which means
    fusion degenerates into pure concatenation (or, on an older code path,
    an empty union entirely). The real fix is resolving those keys, not
    working around the fallback -- see rmip.core.glossary_backfill for the
    full analysis. Run automatically, unconditionally (no checkbox) before
    every fusion, same as the converter's "fix this automatically" asks:
    it only ever fills a gap (never touches an already-resolved species/
    reaction), so it's always safe to run, including when nothing needs it.

    priority_order (feature gap closed 2026-07-17, bug.md): this GUI could
    previously only ever call the mean/consensus fusion strategy -- the
    per-reaction "take the highest-priority mechanism's kinetics verbatim"
    mode existed only on the separate CLI-only fuse_kld.py-style driver.
    When given, every reaction shared across mech_ids is copied verbatim
    from the highest-priority present mechanism instead of averaged; the
    n_fuse bucket is correspondingly empty (see FusionEngine.fuse's own
    docstring in stubs.py)."""
    from rmip.analysis.graph_comparator import GraphComparator
    from rmip.stubs import FusionEngine

    glossary_summary = None
    if glossary_path and Path(glossary_path).is_file():
        from rmip.core.glossary_backfill import backfill_glossary
        glossary_summary = backfill_glossary(db_path, mech_ids, glossary_path)

    cmp = GraphComparator(db_path, tol_A=tol_A, tol_n=tol_n, tol_Ea=tol_Ea)
    result = cmp.compare(mech_ids)
    spec = cmp.build_union_spec(result)

    n_reactions_total = (len(spec.verbatim_reactions) + len(spec.copy_reactions)
                         + len(spec.fuse_reactions))
    if len(spec.species_map) == 0 or n_reactions_total == 0:
        raise FusionDegenerateError(
            f"Fusion of mechanisms {mech_ids} produced an empty union "
            f"({len(spec.species_map)} species, {n_reactions_total} "
            "reactions) -- refusing to write an empty 'fused' mechanism. "
            "This is the exact failure KRUNAL_JULY_23.md reported. Check "
            "that the mechanism IDs actually have species/reactions stored "
            "(rmip_cli.py list-mechanisms), and that a species glossary "
            "was available for backfill (glossary_summary above, if any).")

    engine = FusionEngine(spec, db_path)
    fused_mech_id = engine.fuse(output_name, output_dir=output_dir, write_cantera=write_cantera,
                                 priority_order=priority_order)
    balance = engine.validate_element_balance(fused_mech_id)

    # KRUNAL_JULY_23.md point 6 -- emit per-reaction uncertainty data in the
    # format Point 5's Uncertainty Quantification and File Generator
    # consumes directly as a "Classification CSV" (never write it for
    # priority_order runs: that mode copies one mechanism's kinetics
    # verbatim per reaction, so there's no cross-mechanism divergence left
    # to band -- see FusionEngine.fuse's own docstring).
    uncertainty_csv_path = None
    n_uncertainty_reactions = 0
    if write_uncertainty_csv and not priority_order:
        from rmip.analysis.fusion_uncertainty import FusionUncertaintyEngine
        from rmip.analysis.fusion_uncertainty_classification import write_classification_csv

        records = FusionUncertaintyEngine().compute(result)
        if records:
            uncertainty_csv_path = str(
                Path(output_dir) / f"{output_name}_uncertainty_classification.csv")
            write_classification_csv(records, uncertainty_csv_path)
            n_uncertainty_reactions = len(records)

    return {
        "fused_mech_id": fused_mech_id,
        "n_verbatim": len(spec.verbatim_reactions),
        "n_copy": len(spec.copy_reactions),
        "n_fuse": len(spec.fuse_reactions) if not priority_order else 0,
        "n_species": len(spec.species_map),
        "balanced": balance["balanced"],
        "violations": balance["violations"],
        "output_dir": output_dir,
        "output_name": output_name,
        "priority_order": priority_order,
        "glossary_summary": glossary_summary,
        "uncertainty_csv_path": uncertainty_csv_path,
        "n_uncertainty_reactions": n_uncertainty_reactions,
    }


class MeanValueFusionApp:
    """Standalone Mean Value / Mechanism Fusion Generator GUI."""

    def __init__(self, root: "tk.Tk", initial_db: str | None = None):
        self.root = root
        self.root.title("Mean Value / Mechanism Fusion Generator")
        self.root.geometry("880x660")

        self._db_var = tk.StringVar(value=initial_db or "")
        self._mech_ids_var = tk.StringVar(value="")
        self._tol_A_var = tk.StringVar(value="0.01")
        self._tol_n_var = tk.StringVar(value="0.001")
        self._tol_Ea_var = tk.StringVar(value="100.0")
        self._output_name_var = tk.StringVar(value="Fused_Mech")
        self._output_dir_var = tk.StringVar(value="outputs/fusion")
        self._glossary_var = tk.StringVar(value=_DEFAULT_GLOSSARY)
        self._write_cantera_var = tk.BooleanVar(value=False)
        self._priority_mode_var = tk.BooleanVar(value=False)
        self._priority_order_var = tk.StringVar(value="")
        self._status_var = tk.StringVar(value="Enter a database path and mechanism IDs to begin.")
        # last-run state, for "Export run status…" (KRUNAL_JULY_23.md pt. 1)
        self._last_summary: dict | None = None
        self._last_error: str | None = None

        settings = load_settings(_APP_NAME)
        if not initial_db and settings.get("last_db"):
            initial_db = settings["last_db"]
            self._db_var.set(initial_db)

        self._build_ui()

        # Autosave/checkpoint safety net (Phase-3 follow-on Part B --
        # FEATURE_GAPS_FROM_MONOLITH.md ranked candidate #3). This app has no
        # repeatable row editor, so the natural mutation point is any of the
        # persisted form fields changing -- traced directly rather than
        # threading a mark_dirty() call through every individual handler.
        self._autosave = AutoSaveManager(self.root, save_callback=self._autosave_save)
        for var in (self._mech_ids_var, self._tol_A_var, self._tol_n_var,
                    self._tol_Ea_var, self._output_name_var, self._output_dir_var,
                    self._glossary_var, self._priority_order_var,
                    self._write_cantera_var, self._priority_mode_var):
            var.trace_add("write", lambda *_a: self._autosave.mark_dirty())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _autosave_save(self) -> None:
        """AutoSaveManager's save_callback -- snapshot the in-progress
        fusion form so a crash/close doesn't lose it."""
        state = {
            "db": self._db_var.get(),
            "mech_ids": self._mech_ids_var.get(),
            "tol_A": self._tol_A_var.get(),
            "tol_n": self._tol_n_var.get(),
            "tol_Ea": self._tol_Ea_var.get(),
            "output_name": self._output_name_var.get(),
            "output_dir": self._output_dir_var.get(),
            "glossary": self._glossary_var.get(),
            "write_cantera": self._write_cantera_var.get(),
            "priority_mode": self._priority_mode_var.get(),
            "priority_order": self._priority_order_var.get(),
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

        ttk.Label(outer, text="Mean Value / Mechanism Fusion Generator",
                  font=FONTS["header"]).pack(anchor=tk.W)
        ttk.Label(outer,
                  text="Wraps rmip.stubs.FusionEngine — merges N mechanisms: geometric mean of "
                       "A, arithmetic mean of n/Ea for shared-but-divergent reactions (FUSE "
                       "bucket), verbatim/copy for the rest — or, in priority-pick mode, "
                       "verbatim from the highest-priority present mechanism instead of "
                       "averaging. Validates element balance and writes merged CHEMKIN + "
                       "optional Cantera YAML.",
                  foreground=PALETTE["text_dim"], wraplength=820).pack(anchor=tk.W, pady=(0, 10))

        # ── Database + mechanism selection ──────────────────────────────
        db_frame = ttk.LabelFrame(outer, text="Database + mechanisms to fuse", padding=8)
        db_frame.pack(fill=tk.X, pady=(0, 10))
        db_row = ttk.Frame(db_frame)
        db_row.pack(fill=tk.X)
        ttk.Label(db_row, text="RMIP database", width=16).pack(side=tk.LEFT)
        ttk.Entry(db_row, textvariable=self._db_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(db_row, text="Browse…", command=self._browse_db).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(db_row, text="List mechanisms", command=self._list_mechanisms
                   ).pack(side=tk.LEFT, padx=(6, 0))

        self._mech_list_text = tk.Text(db_frame, height=5, font=FONTS["mono_small"],
                                        bg=PALETTE["surface"], fg=PALETTE["text"],
                                        relief=tk.FLAT, state=tk.DISABLED)
        self._mech_list_text.pack(fill=tk.X, pady=(6, 0))

        ids_row = ttk.Frame(db_frame)
        ids_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(ids_row, text="Mechanism IDs (≥2, comma-sep.)", width=26).pack(side=tk.LEFT)
        ttk.Entry(ids_row, textvariable=self._mech_ids_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        gl_row = ttk.Frame(db_frame)
        gl_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(gl_row, text="Species glossary CSV", width=26).pack(side=tk.LEFT)
        ttk.Entry(gl_row, textvariable=self._glossary_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(gl_row, text="Browse…", command=self._browse_glossary).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(db_frame,
                  text="Applied automatically before fusing (fills in any species/reaction "
                       "identity a mechanism was parsed without a glossary for -- this is "
                       "what caused 'Fused_Mech (fused, 0 sp / 0 rxn)'). Never touches an "
                       "already-resolved species/reaction; leave blank to skip.",
                  foreground=PALETTE["text_dim"], wraplength=820, justify=tk.LEFT
                  ).pack(anchor=tk.W, pady=(4, 0))

        # ── Tolerances ───────────────────────────────────────────────────
        tol_frame = ttk.LabelFrame(outer, text="Kinetics-identity tolerances (SHARED_IDENTICAL vs. SHARED_DIVERGENT)", padding=8)
        tol_frame.pack(fill=tk.X, pady=(0, 10))

        def _tol_field(label, var):
            r = ttk.Frame(tol_frame)
            r.pack(fill=tk.X, pady=2)
            ttk.Label(r, text=label, width=28).pack(side=tk.LEFT)
            ttk.Entry(r, textvariable=var, width=12).pack(side=tk.LEFT)

        _tol_field("Relative tol. on A (fraction)", self._tol_A_var)
        _tol_field("Absolute tol. on n", self._tol_n_var)
        _tol_field("Absolute tol. on Ea (J/mol)", self._tol_Ea_var)

        # ── Output ───────────────────────────────────────────────────────
        out_frame = ttk.LabelFrame(outer, text="Output", padding=8)
        out_frame.pack(fill=tk.X, pady=(0, 10))
        name_row = ttk.Frame(out_frame)
        name_row.pack(fill=tk.X, pady=2)
        ttk.Label(name_row, text="Fused mechanism name", width=22).pack(side=tk.LEFT)
        ttk.Entry(name_row, textvariable=self._output_name_var, width=30).pack(side=tk.LEFT)

        out_row = ttk.Frame(out_frame)
        out_row.pack(fill=tk.X, pady=2)
        ttk.Label(out_row, text="Output directory", width=22).pack(side=tk.LEFT)
        ttk.Entry(out_row, textvariable=self._output_dir_var, width=40).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(out_row, text="Browse…", command=self._browse_out_dir).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Checkbutton(out_frame, text="Also write Cantera YAML (via ck2yaml)",
                         variable=self._write_cantera_var).pack(anchor=tk.W, pady=(4, 0))

        # ── Fusion strategy ──────────────────────────────────────────────
        strat_frame = ttk.LabelFrame(outer, text="Fusion strategy", padding=8)
        strat_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Checkbutton(
            strat_frame,
            text="Priority-pick mode (verbatim from the highest-priority present "
                 "mechanism instead of averaging)",
            variable=self._priority_mode_var,
            command=self._on_priority_mode_toggled,
        ).pack(anchor=tk.W)
        self._priority_order_row = ttk.Frame(strat_frame)
        self._priority_order_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(self._priority_order_row, text="Priority order (comma-sep. mechanism IDs, "
                  "highest first)", width=44).pack(side=tk.LEFT)
        self._priority_order_entry = ttk.Entry(
            self._priority_order_row, textvariable=self._priority_order_var)
        self._priority_order_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._on_priority_mode_toggled()

        # ── Run ──────────────────────────────────────────────────────────
        btn_row = ttk.Frame(outer)
        btn_row.pack(fill=tk.X, pady=(0, 10))
        self._run_btn = ttk.Button(btn_row, text="▶  Run Fusion", command=self._run_fusion_clicked)
        self._run_btn.pack(side=tk.LEFT)
        add_export_button(btn_row, self._build_run_status).pack(side=tk.LEFT, padx=(6, 0))

        # ── Results ──────────────────────────────────────────────────────
        res_frame = ttk.LabelFrame(outer, text="Results", padding=4)
        res_frame.pack(fill=tk.BOTH, expand=True)
        self._result_text = tk.Text(res_frame, height=12, font=FONTS["mono_small"],
                                     bg=PALETTE["surface"], fg=PALETTE["text"],
                                     relief=tk.FLAT, state=tk.DISABLED)
        self._result_text.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, textvariable=self._status_var, style="Status.TLabel"
                  ).pack(anchor=tk.W, pady=(6, 0))

    # ------------------------------------------------------------------
    # Database / mechanism helpers
    # ------------------------------------------------------------------

    def _browse_db(self) -> None:
        path = filedialog.askopenfilename(
            title="Select RMIP database", filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")])
        if path:
            self._db_var.set(path)
            save_settings(_APP_NAME, {"last_db": path})

    def _list_mechanisms(self) -> None:
        db_path = self._db_var.get().strip()
        if not db_path:
            messagebox.showwarning("No database", "Enter a database path first.")
            return
        try:
            rows = _list_mechanisms(db_path)
        except Exception as e:
            messagebox.showerror("Query failed", str(e))
            return
        lines = [f"{r[0]}: {r[1]} ({r[2]}, {r[3]} sp / {r[4]} rxn)" for r in rows]
        self._mech_list_text.configure(state=tk.NORMAL)
        self._mech_list_text.delete("1.0", tk.END)
        self._mech_list_text.insert(tk.END, "\n".join(lines) or "(no mechanisms found)")
        self._mech_list_text.configure(state=tk.DISABLED)

    def _browse_out_dir(self) -> None:
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            self._output_dir_var.set(path)

    def _browse_glossary(self) -> None:
        path = filedialog.askopenfilename(
            title="Select species glossary", filetypes=[("CSV/YAML", "*.csv *.yaml *.yml"),
                                                         ("All files", "*.*")])
        if path:
            self._glossary_var.set(path)

    def _on_priority_mode_toggled(self) -> None:
        state = tk.NORMAL if self._priority_mode_var.get() else tk.DISABLED
        self._priority_order_entry.configure(state=state)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _run_fusion_clicked(self) -> None:
        db_path = self._db_var.get().strip()
        ids_raw = self._mech_ids_var.get().strip()
        if not db_path or not ids_raw:
            messagebox.showwarning("Missing input", "Enter a database path and mechanism IDs.")
            return
        try:
            mech_ids = [int(s.strip()) for s in ids_raw.split(",") if s.strip()]
        except ValueError:
            messagebox.showerror("Invalid input", "Mechanism IDs must be comma-separated integers.")
            return
        if len(mech_ids) < 2:
            messagebox.showwarning("Need ≥2 mechanisms", "Enter at least 2 mechanism IDs to fuse.")
            return

        try:
            tol_A = float(self._tol_A_var.get())
            tol_n = float(self._tol_n_var.get())
            tol_Ea = float(self._tol_Ea_var.get())
        except ValueError:
            messagebox.showerror("Invalid tolerance", "Tolerances must be numeric.")
            return

        output_name = self._output_name_var.get().strip() or "Fused_Mech"
        output_dir = self._output_dir_var.get().strip() or "outputs/fusion"
        write_cantera = self._write_cantera_var.get()

        priority_order = None
        if self._priority_mode_var.get():
            po_raw = self._priority_order_var.get().strip()
            if not po_raw:
                messagebox.showwarning(
                    "Missing priority order",
                    "Priority-pick mode is checked but no priority order was entered.")
                return
            try:
                priority_order = [int(s.strip()) for s in po_raw.split(",") if s.strip()]
            except ValueError:
                messagebox.showerror(
                    "Invalid input", "Priority order must be comma-separated integers.")
                return
            if set(priority_order) != set(mech_ids):
                messagebox.showerror(
                    "Priority order mismatch",
                    "Priority order must list exactly the same mechanism IDs entered above "
                    "(just reordered by priority, highest first).")
                return

        self._status_var.set("Running fusion…")
        self._run_btn.configure(state=tk.DISABLED)

        glossary_path = self._glossary_var.get().strip() or None

        def _worker():
            try:
                summary = _run_fusion(db_path, mech_ids, tol_A, tol_n, tol_Ea,
                                       output_name, output_dir, write_cantera,
                                       priority_order=priority_order,
                                       glossary_path=glossary_path)
                self.root.after(0, lambda: self._on_fusion_done(summary))
            except Exception as e:
                self.root.after(0, lambda e=e: self._on_fusion_error(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_fusion_done(self, summary: dict) -> None:
        self._run_btn.configure(state=tk.NORMAL)
        self._last_summary, self._last_error = summary, None
        priority_order = summary.get("priority_order")
        strategy_line = (
            f"COPY={summary['n_copy']}  FUSE={summary['n_fuse']}"
            if not priority_order else
            f"COPY={summary['n_copy']}  PRIORITY-PICK (order={priority_order})"
        )
        lines = []
        gs = summary.get("glossary_summary")
        if gs:
            lines.append("Glossary backfill (before comparing):")
            for mid, s in gs.items():
                lines.append(
                    f"  mech {mid}: species {s['species_resolved']}/"
                    f"{s['species_unresolved_before']} newly resolved "
                    f"({s['species_still_unresolved']} still unresolved); "
                    f"reactions {s['reactions_resolved']}/"
                    f"{s['reactions_total_unresolved_before']} newly resolved")
            lines.append("")
        lines += [
            f"Fused mechanism DB id : {summary['fused_mech_id']}",
            f"Species               : {summary['n_species']}",
            f"Reactions             : VERBATIM={summary['n_verbatim']}  {strategy_line}",
            f"Element balance       : {'OK' if summary['balanced'] else 'VIOLATIONS FOUND'}",
        ]
        if not summary["balanced"]:
            lines.append("  Unbalanced reactions:")
            for v in summary["violations"][:10]:
                lines.append(f"    {v}")
        lines.append(f"Output written to     : {summary['output_dir']}/{summary['output_name']}.inp (+.dat)")
        if summary.get("uncertainty_csv_path"):
            lines.append(
                f"Uncertainty CSV       : {summary['uncertainty_csv_path']} "
                f"({summary['n_uncertainty_reactions']} FUSE reaction(s) -- load this as "
                "the Classification CSV in Uncertainty Quantification and File Generator)")
        self._result_text.configure(state=tk.NORMAL)
        self._result_text.delete("1.0", tk.END)
        self._result_text.insert(tk.END, "\n".join(lines))
        self._result_text.configure(state=tk.DISABLED)
        self._status_var.set("Fusion complete.")

    def _on_fusion_error(self, error: Exception) -> None:
        self._run_btn.configure(state=tk.NORMAL)
        self._last_summary, self._last_error = None, str(error)
        self._status_var.set(f"Fusion failed: {error}")
        messagebox.showerror("Fusion failed", str(error))

    # -- run-status export (KRUNAL_JULY_23.md point 1) -----------------------
    def _build_run_status(self) -> RunStatusReport:
        inputs = {
            "RMIP database": self._db_var.get(),
            "mechanism IDs": self._mech_ids_var.get(),
            "species glossary CSV": self._glossary_var.get(),
        }
        options = {
            "tol_A": self._tol_A_var.get(), "tol_n": self._tol_n_var.get(),
            "tol_Ea": self._tol_Ea_var.get(),
            "write_cantera": self._write_cantera_var.get(),
            "priority_mode": self._priority_mode_var.get(),
            "priority_order": self._priority_order_var.get(),
        }
        if self._last_error is not None:
            return RunStatusReport(
                tool="Mean Value / Mechanism Fusion Generator",
                inputs=inputs, output_dir=self._output_dir_var.get(),
                options=options, status="failed", summary=self._last_error,
                log=self._result_text.get("1.0", "end"))
        if self._last_summary is None:
            return RunStatusReport(
                tool="Mean Value / Mechanism Fusion Generator",
                inputs=inputs, output_dir=self._output_dir_var.get(),
                options=options, status="unknown",
                summary="no fusion has been run yet")
        s = self._last_summary
        return RunStatusReport(
            tool="Mean Value / Mechanism Fusion Generator",
            inputs=inputs, output_dir=self._output_dir_var.get(),
            options=options, status="success",
            summary=f"fused mech id {s['fused_mech_id']}: {s['n_species']} species, "
                    f"balance {'OK' if s['balanced'] else 'VIOLATIONS'}",
            log=self._result_text.get("1.0", "end"))


def main() -> int:
    args = parse_args()

    if args.fuse:
        if not args.db or not args.mechs or len(args.mechs) < 2:
            print("ERROR: --fuse requires --db and >=2 --mechs")
            return 1
        try:
            summary = _run_fusion(
                args.db, args.mechs, args.tol_A, args.tol_n, args.tol_Ea,
                args.output_name, args.output_dir, args.write_cantera,
                priority_order=args.priority_order,
                glossary_path=args.glossary or None,
            )
        except Exception as e:            # FusionDegenerateError or anything else
            print(f"ERROR: {e}")
            return 1
        print(f"fused_mech_id={summary['fused_mech_id']}")
        print(f"n_species={summary['n_species']}")
        print(f"n_verbatim={summary['n_verbatim']} n_copy={summary['n_copy']} "
              f"n_fuse={summary['n_fuse']}")
        print(f"balanced={summary['balanced']}")
        if summary.get("glossary_summary"):
            for mid, s in summary["glossary_summary"].items():
                print(f"glossary_backfill mech={mid} "
                      f"species_resolved={s['species_resolved']} "
                      f"reactions_resolved={s['reactions_resolved']}")
        print(f"output={summary['output_dir']}/{summary['output_name']}.inp")
        if summary.get("uncertainty_csv_path"):
            print(f"uncertainty_csv={summary['uncertainty_csv_path']}")
            print(f"n_uncertainty_reactions={summary['n_uncertainty_reactions']}")
        return 0

    if args.no_gui or not _HAS_TK:
        if args.db:
            print(f"DB path: {args.db} (exists={Path(args.db).exists()})")
        else:
            print("No --db given (--no-gui smoke check, nothing to check).")
        return 0

    root = tk.Tk()
    apply_theme(root)
    app = MeanValueFusionApp(root, initial_db=args.db)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
