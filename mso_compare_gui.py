#!/usr/bin/env python3
"""
mso_compare_gui.py — Standalone GUI for MSO Compare.

Phase 3 of the GUI-separation plan (see
MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md §1.7):
a thin Tk form wrapping src/run_mso_pipeline.py's 4-phase pipeline
(simulate -> merge -> error-metrics -> plots), each phase independently
skippable exactly as the underlying CLI already supports.

Distinct from nominal_sim_gui.py (Phase 2): that app runs ONE named
nominal-only simulation; this app runs the FULL multi-run comparison
pipeline (nominal vs. stage1 vs. stage2, HTC/LTC) that src/mso_compare/
was actually built for -- see that package's own README.md for the config
schema.

Usage:
    python mso_compare_gui.py                     # open GUI, load nothing
    python mso_compare_gui.py mso_config.yaml     # open GUI, pre-load config
    python mso_compare_gui.py --config FILE       # equivalent, explicit flag
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

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

_APP_NAME = "mso_compare"
_RUN_MSO_PIPELINE_SCRIPT = str(Path(__file__).resolve().parent / "src" / "run_mso_pipeline.py")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Standalone GUI for MSO Compare (run_mso_pipeline.py)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("config", nargs="?", default=None,
                   help="Path to an existing mso_compare pipeline YAML to pre-load")
    p.add_argument("--config", dest="config_flag", default=None,
                   help="Equivalent to the positional argument")
    p.add_argument("--no-gui", action="store_true",
                   help="Headless smoke check: verify the config path exists and exit")
    return p.parse_args()


class MSOCompareApp:
    """Standalone MSO Compare GUI. Launches run_mso_pipeline.py directly
    via the shared PtyTerminal -- no in-process pipeline logic here."""

    def __init__(self, root: "tk.Tk", initial_config_path: str | None = None):
        self.root = root
        self.root.title("MSO Compare")
        self.root.geometry("880x660")

        self._cfg_path_var = tk.StringVar(value=initial_config_path or "")
        self._regime_var = tk.StringVar(value="both")
        self._skip_sim_var = tk.BooleanVar(value=False)
        self._skip_merge_var = tk.BooleanVar(value=False)
        self._skip_errors_var = tk.BooleanVar(value=False)
        self._skip_plots_var = tk.BooleanVar(value=False)
        self._dry_run_var = tk.BooleanVar(value=False)
        self._verbose_var = tk.BooleanVar(value=False)
        self._status_var = tk.StringVar(value="Load an mso_compare pipeline YAML to begin.")

        settings = load_settings(_APP_NAME)
        if not initial_config_path and settings.get("last_config"):
            initial_config_path = settings["last_config"]
            self._cfg_path_var.set(initial_config_path)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text="MSO Compare", font=FONTS["header"]).pack(anchor=tk.W)
        ttk.Label(outer,
                  text="Wraps src/run_mso_pipeline.py — the 4-phase multi-run comparison "
                       "pipeline: simulate (nominal/stage1/stage2) → merge by φ/P → "
                       "χ² error metrics → PDF plots. Each phase is independently skippable.",
                  foreground=PALETTE["text_dim"], wraplength=820).pack(anchor=tk.W, pady=(0, 10))

        # ── Config load ──────────────────────────────────────────────────
        cfg_frame = ttk.LabelFrame(outer, text="Pipeline configuration (mso_compare YAML)", padding=8)
        cfg_frame.pack(fill=tk.X, pady=(0, 10))
        row = ttk.Frame(cfg_frame)
        row.pack(fill=tk.X)
        ttk.Entry(row, textvariable=self._cfg_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="Browse…", command=self._browse_config).pack(side=tk.LEFT, padx=(6, 0))

        # ── Phase toggles ────────────────────────────────────────────────
        phase_frame = ttk.LabelFrame(outer, text="Phases", padding=8)
        phase_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Checkbutton(phase_frame, text="Skip Phase 1 — simulate (use existing sim outputs)",
                         variable=self._skip_sim_var).pack(anchor=tk.W)
        ttk.Checkbutton(phase_frame, text="Skip Phase 2 — merge (use existing merged outputs)",
                         variable=self._skip_merge_var).pack(anchor=tk.W)
        ttk.Checkbutton(phase_frame, text="Skip Phase 3 — error metrics",
                         variable=self._skip_errors_var).pack(anchor=tk.W)
        ttk.Checkbutton(phase_frame, text="Skip Phase 4 — plots",
                         variable=self._skip_plots_var).pack(anchor=tk.W)

        regime_row = ttk.Frame(phase_frame)
        regime_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(regime_row, text="Regime (Phases 2-4)", width=20).pack(side=tk.LEFT)
        ttk.Combobox(regime_row, textvariable=self._regime_var, values=["htc", "ltc", "both"],
                     width=10, state="readonly").pack(side=tk.LEFT)

        opts_row = ttk.Frame(phase_frame)
        opts_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Checkbutton(opts_row, text="Dry run", variable=self._dry_run_var).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(opts_row, text="Verbose (DEBUG logging)", variable=self._verbose_var).pack(side=tk.LEFT)

        # ── Run ──────────────────────────────────────────────────────────
        btn_row = ttk.Frame(outer)
        btn_row.pack(fill=tk.X, pady=(0, 10))
        self._run_btn = ttk.Button(btn_row, text="▶  Run MSO Compare Pipeline", command=self._run_pipeline)
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
    # Config
    # ------------------------------------------------------------------

    def _browse_config(self) -> None:
        path = filedialog.askopenfilename(
            title="Select mso_compare pipeline YAML",
            filetypes=[("YAML", "*.yaml *.yml"), ("All files", "*.*")])
        if path:
            self._cfg_path_var.set(path)
            save_settings(_APP_NAME, {"last_config": path})
            self._status_var.set(f"Loaded {path}")

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _run_pipeline(self) -> None:
        config_path = self._cfg_path_var.get().strip()
        if not config_path:
            messagebox.showwarning("No config", "Select a pipeline YAML first.")
            return

        cmd = [sys.executable, _RUN_MSO_PIPELINE_SCRIPT, "--config", config_path,
               "--regime", self._regime_var.get()]
        if self._skip_sim_var.get():
            cmd.append("--skip-simulations")
        if self._skip_merge_var.get():
            cmd.append("--skip-merge")
        if self._skip_errors_var.get():
            cmd.append("--skip-error-metrics")
        if self._skip_plots_var.get():
            cmd.append("--skip-plots")
        if self._dry_run_var.get():
            cmd.append("--dry-run")
        if self._verbose_var.get():
            cmd.append("--verbose")

        self._terminal.run(cmd)
        self._status_var.set("MSO Compare pipeline running in embedded terminal…")

    # -- run-status export (KRUNAL_JULY_23.md point 1) -----------------------
    def _build_run_status(self) -> RunStatusReport:
        return RunStatusReport(
            tool="MSO Compare",
            inputs={"pipeline config": self._cfg_path_var.get()},
            options={
                "regime": self._regime_var.get(),
                "skip simulate": self._skip_sim_var.get(),
                "skip merge": self._skip_merge_var.get(),
                "skip error metrics": self._skip_errors_var.get(),
                "skip plots": self._skip_plots_var.get(),
                "dry run": self._dry_run_var.get(),
                "verbose": self._verbose_var.get(),
            },
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
            print(f"Config path: {config_path} (exists={Path(config_path).exists()})")
        else:
            print("No config given (--no-gui smoke check, nothing to load).")
        return 0

    root = tk.Tk()
    apply_theme(root)
    app = MSOCompareApp(root, initial_config_path=config_path)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
