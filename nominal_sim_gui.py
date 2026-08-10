#!/usr/bin/env python3
"""
nominal_sim_gui.py — Standalone GUI for Nominal Simulation (parallel).

Phase 2 of the GUI-separation plan (see
MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md §1.7):
a thin Tk form wrapping src/mso_compare/run_nominal_sim.py -- per KP's
clarifying answer during planning, "Nominal sim in parallel" means this
mso_compare pipeline's nominal-only runner (template_nominal_only.yaml),
not src/MUQ-SAC/nominal_sim_v3.py (the other, unrelated "nominal sim"
driver that turned out to exist in this codebase).

Data contract: run_nominal_sim.py is driven entirely by an mso_compare
pipeline YAML config (see src/mso_compare/template_nominal_only.yaml) with
named "run labels" (nominal_htc, nominal_ltc, ...) -- this app loads that
config, lists its run labels via mso_compare.config.load_config(), lets the
user pick one + a dry-run toggle, then launches
`run_nominal_sim.py --config ... --run ...` via the shared PtyTerminal.

Usage:
    python nominal_sim_gui.py                     # open GUI, load nothing
    python nominal_sim_gui.py mso_config.yaml     # open GUI, pre-load config
    python nominal_sim_gui.py --config FILE       # equivalent, explicit flag
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent
_SRC = str(_REPO / "src")
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

_APP_NAME = "nominal_sim"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Standalone GUI for Nominal Simulation (run_nominal_sim.py)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("config", nargs="?", default=None,
                   help="Path to an existing mso_compare pipeline YAML to pre-load")
    p.add_argument("--config", dest="config_flag", default=None,
                   help="Equivalent to the positional argument")
    p.add_argument("--no-gui", action="store_true",
                   help="Headless smoke check: load config (if given), list run labels, exit")
    return p.parse_args()


def _load_run_labels(config_path: str) -> list:
    """Returns the list of run labels defined in the config's `simulations`
    block, via mso_compare.config.load_config() (in-process, no subprocess)."""
    from mso_compare.config import load_config
    _, cfg = load_config(config_path)
    return list(cfg.simulations.keys())


class NominalSimApp:
    """Standalone Nominal Simulation GUI. Loads an mso_compare pipeline
    config, lists its run labels, launches run_nominal_sim.py directly via
    the shared PtyTerminal."""

    def __init__(self, root: "tk.Tk", initial_config_path: str | None = None):
        self.root = root
        self.root.title("Nominal Simulation (mso_compare)")
        self.root.geometry("860x600")

        self._cfg_path_var = tk.StringVar(value=initial_config_path or "")
        self._run_label_var = tk.StringVar(value="")
        self._dry_run_var = tk.BooleanVar(value=False)
        self._status_var = tk.StringVar(value="Load an mso_compare pipeline YAML to begin.")

        settings = load_settings(_APP_NAME)
        if not initial_config_path and settings.get("last_config"):
            initial_config_path = settings["last_config"]
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

        ttk.Label(outer, text="Nominal Simulation (parallel)",
                  font=FONTS["header"]).pack(anchor=tk.W)
        ttk.Label(outer,
                  text="Wraps src/mso_compare/run_nominal_sim.py — runs one named nominal "
                       "simulation (HTC/LTC/custom, per the pipeline YAML's run labels), "
                       "parallelized internally via multiprocessing.",
                  foreground=PALETTE["text_dim"], wraplength=800).pack(anchor=tk.W, pady=(0, 10))

        # ── Config load ──────────────────────────────────────────────────
        cfg_frame = ttk.LabelFrame(outer, text="Pipeline configuration (mso_compare YAML)", padding=8)
        cfg_frame.pack(fill=tk.X, pady=(0, 10))
        row = ttk.Frame(cfg_frame)
        row.pack(fill=tk.X)
        ttk.Entry(row, textvariable=self._cfg_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="Load…", command=self._browse_and_load).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(row, text="Reload", command=self._reload_config).pack(side=tk.LEFT, padx=(6, 0))

        self._cfg_summary = ttk.Label(cfg_frame, text="(nothing loaded)",
                                       foreground=PALETTE["text_dim"], justify=tk.LEFT)
        self._cfg_summary.pack(anchor=tk.W, pady=(6, 0))

        # ── Run selection ────────────────────────────────────────────────
        run_frame = ttk.LabelFrame(outer, text="Run", padding=8)
        run_frame.pack(fill=tk.X, pady=(0, 10))
        label_row = ttk.Frame(run_frame)
        label_row.pack(fill=tk.X)
        ttk.Label(label_row, text="Run label", width=14).pack(side=tk.LEFT)
        self._run_label_combo = ttk.Combobox(label_row, textvariable=self._run_label_var,
                                              values=[], width=30, state="readonly")
        self._run_label_combo.pack(side=tk.LEFT)

        ttk.Checkbutton(run_frame, text="Dry run (print what would be run, don't execute)",
                         variable=self._dry_run_var).pack(anchor=tk.W, pady=(6, 0))

        btn_row = ttk.Frame(run_frame)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        self._run_btn = ttk.Button(btn_row, text="▶  Run Nominal Simulation", command=self._run_sim)
        self._run_btn.pack(side=tk.LEFT)
        add_export_button(btn_row, self._build_run_status).pack(side=tk.LEFT, padx=(6, 0))
        if not _HAS_PTY_TERMINAL:
            ttk.Label(btn_row, text="⚠ pyte not installed — run: pip install pyte",
                      foreground=PALETTE["warning"]).pack(side=tk.LEFT, padx=8)

        # ── Live output ──────────────────────────────────────────────────
        term_frame = ttk.LabelFrame(outer, text="Live output", padding=4)
        term_frame.pack(fill=tk.BOTH, expand=True)
        self._terminal = PtyTerminal(term_frame, rows=18, cols=110)
        self._terminal.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, textvariable=self._status_var, style="Status.TLabel"
                  ).pack(anchor=tk.W, pady=(6, 0))

    # ------------------------------------------------------------------
    # Config load
    # ------------------------------------------------------------------

    def _browse_and_load(self) -> None:
        path = filedialog.askopenfilename(
            title="Select mso_compare pipeline YAML",
            filetypes=[("YAML", "*.yaml *.yml"), ("All files", "*.*")])
        if path:
            self._cfg_path_var.set(path)
            self._load_config(path)

    def _reload_config(self) -> None:
        path = self._cfg_path_var.get().strip()
        if path:
            self._load_config(path)

    def _load_config(self, path: str) -> None:
        try:
            labels = _load_run_labels(path)
        except Exception as e:
            messagebox.showerror("Load failed", f"Could not load {path!r}:\n{e}")
            return

        self._run_label_combo.configure(values=labels)
        if labels:
            self._run_label_var.set(labels[0])
        self._cfg_summary.configure(text=f"{len(labels)} run label(s): {', '.join(labels)}")
        self._status_var.set(f"Loaded {path}")
        save_settings(_APP_NAME, {"last_config": path})

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _run_sim(self) -> None:
        config_path = self._cfg_path_var.get().strip()
        run_label = self._run_label_var.get().strip()
        if not config_path or not run_label:
            messagebox.showwarning("Nothing to run", "Load a config and pick a run label first.")
            return

        # `-m mso_compare.run_nominal_sim` with cwd/PYTHONPATH=src would put
        # src/ at the front of sys.path *before* interpreter init finishes --
        # and src/io/ (a real legacy package) shadows the stdlib `io` module
        # the interpreter itself needs to set up sys.stdin/stdout/stderr,
        # crashing with "Fatal Python error: init_sys_streams" before any
        # user code runs. Bootstrapping via `-c` + runpy defers the sys.path
        # insert until after interpreter init, sidestepping the collision.
        bootstrap = (
            "import sys, runpy; "
            f"sys.path.insert(0, {str(_REPO / 'src')!r}); "
            "runpy.run_module('mso_compare.run_nominal_sim', run_name='__main__')"
        )
        cmd = [sys.executable, "-c", bootstrap,
               "--config", str(Path(config_path).resolve()), "--run", run_label]
        if self._dry_run_var.get():
            cmd.append("--dry-run")

        self._terminal.run(cmd)
        self._status_var.set(f"Running '{run_label}' in embedded terminal…")

    # -- run-status export (KRUNAL_JULY_23.md point 1) -----------------------
    def _build_run_status(self) -> RunStatusReport:
        output_dir = None
        config_path = self._cfg_path_var.get().strip()
        run_label = self._run_label_var.get().strip()
        if config_path and run_label:
            try:
                from mso_compare.config import load_config
                _, cfg = load_config(config_path)
                output_dir = cfg.simulations[run_label].output_dir
            except Exception:
                pass                                # best-effort only
        return RunStatusReport(
            tool="Nominal Simulation (mso_compare)",
            inputs={"pipeline config": config_path},
            output_dir=output_dir,
            options={"run label": run_label, "dry run": self._dry_run_var.get()},
            status="unknown",       # runs in a live PTY terminal, no captured exit code
            summary="live terminal output only -- no structured exit status "
                    "available (embedded PtyTerminal, not a captured subprocess)",
            log=self._terminal.text.get("1.0", "end"),
        )


def main() -> int:
    args = parse_args()
    config_path = args.config_flag or args.config

    if args.no_gui or not _HAS_TK:
        if config_path:
            labels = _load_run_labels(config_path)
            print(f"Loaded {config_path}: run labels = {labels}")
        else:
            print("No config given (--no-gui smoke check, nothing to load).")
        return 0

    root = tk.Tk()
    apply_theme(root)
    app = NominalSimApp(root, initial_config_path=config_path)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
