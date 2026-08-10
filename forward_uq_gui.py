#!/usr/bin/env python3
"""
forward_uq_gui.py — Standalone GUI for Forward Uncertainty Quantification.

Phase 2 of the GUI-separation plan (see
MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md §1.7):
a thin Tk form wrapping forward_uq.py, the already-working PRS-surrogate
Monte-Carlo/Sobol propagation tool -- no new UQ logic here.

Data contract: like Brute-Force SA (see brute_force_sa_gui.py), forward_uq.py
needs a full target.opt-shaped YAML (it reads Locations for the mechanism/
uncertainty XML, and expects run_script.py's cached PRS coefficients to
already exist -- see forward_uq.py's own docstring/README). This app loads
an *existing* target.opt rather than reconstructing that whole config tree,
and only exposes the fields forward_uq.py's CLI actually varies:
--n_samples/--method/--seed/--output_dir.

Standardizes on the shared PtyTerminal (gui_common.pty_terminal) instead of
the monolith's external-OS-terminal-window launch path for this tab
(generate_target_opt.py's _run_job()) -- per the GUI-separation plan's
decision to make PtyTerminal the one long-job launch mechanism across all
split-out apps.

Usage:
    python forward_uq_gui.py                      # open GUI, load nothing
    python forward_uq_gui.py target.opt           # open GUI, pre-load config
    python forward_uq_gui.py --target-opt FILE    # equivalent, explicit flag
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import sys
import threading
import time
from pathlib import Path

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

_APP_NAME = "forward_uq"
_FORWARD_UQ_SCRIPT = str(Path(__file__).resolve().parent / "forward_uq.py")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Standalone GUI for Forward UQ (forward_uq.py)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("target_opt", nargs="?", default=None,
                   help="Path to an existing target.opt-style YAML to pre-load")
    p.add_argument("--target-opt", dest="target_opt_flag", default=None,
                   help="Equivalent to the positional argument")
    p.add_argument("--no-gui", action="store_true",
                   help="Headless smoke check: load config (if given) and exit, no Tk window")
    return p.parse_args()


class ForwardUQApp:
    """Standalone Forward UQ GUI. Loads/saves its own scoped config,
    launches forward_uq.py directly via the shared PtyTerminal."""

    def __init__(self, root: "tk.Tk", initial_config_path: str | None = None):
        self.root = root
        self.root.title("Forward Uncertainty Quantification")
        self.root.geometry("900x680")

        self._cfg: dict = {}
        self._cfg_path_var = tk.StringVar(value=initial_config_path or "")
        self._n_samples_var = tk.StringVar(value="50000")
        self._method_var = tk.StringVar(value="sobol")
        self._seed_var = tk.StringVar(value="42")
        self._out_dir_var = tk.StringVar(value="outputs/forward_uq")
        self._status_var = tk.StringVar(value="Load a target.opt file to begin.")

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

        ttk.Label(outer, text="Forward Uncertainty Quantification",
                  font=FONTS["header"]).pack(anchor=tk.W)
        ttk.Label(outer,
                  text="Wraps forward_uq.py — propagates Arrhenius parameter uncertainties "
                       "through a trained PRS surrogate (Monte-Carlo/Sobol/LHS) to get the "
                       "full distribution of combustion observables.",
                  foreground=PALETTE["text_dim"], wraplength=840).pack(anchor=tk.W, pady=(0, 10))

        # ── Config load ──────────────────────────────────────────────────
        cfg_frame = ttk.LabelFrame(outer, text="target.opt configuration", padding=8)
        cfg_frame.pack(fill=tk.X, pady=(0, 10))
        row = ttk.Frame(cfg_frame)
        row.pack(fill=tk.X)
        ttk.Entry(row, textvariable=self._cfg_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="Load…", command=self._browse_and_load).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(row, text="Reload", command=self._reload_config).pack(side=tk.LEFT, padx=(6, 0))

        self._cfg_summary = ttk.Label(cfg_frame, text="(nothing loaded)",
                                       foreground=PALETTE["text_dim"], justify=tk.LEFT)
        self._cfg_summary.pack(anchor=tk.W, pady=(6, 0))
        ttk.Label(cfg_frame,
                  text="Requires run_script.py's cached PRS coefficients to already exist for "
                       "this mechanism (see forward_uq.py's own docstring).",
                  foreground=PALETTE["text_dim"], wraplength=820).pack(anchor=tk.W, pady=(4, 0))

        # ── UQ parameters ────────────────────────────────────────────────
        params_frame = ttk.LabelFrame(outer, text="Sampling parameters", padding=8)
        params_frame.pack(fill=tk.X, pady=(0, 10))

        def _field(label, var, choices=None, width=20):
            r = ttk.Frame(params_frame)
            r.pack(fill=tk.X, pady=2)
            ttk.Label(r, text=label, width=22).pack(side=tk.LEFT)
            if choices:
                ttk.Combobox(r, textvariable=var, values=choices, width=width,
                             state="readonly").pack(side=tk.LEFT)
            else:
                ttk.Entry(r, textvariable=var, width=width).pack(side=tk.LEFT)

        _field("QMC sample count", self._n_samples_var)
        _field("Sampling method", self._method_var, choices=["sobol", "lhs", "numpy"])
        _field("Random seed", self._seed_var)
        out_row = ttk.Frame(params_frame)
        out_row.pack(fill=tk.X, pady=2)
        ttk.Label(out_row, text="Output directory", width=22).pack(side=tk.LEFT)
        ttk.Entry(out_row, textvariable=self._out_dir_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(out_row, text="Browse…", command=self._browse_out_dir).pack(side=tk.LEFT, padx=(6, 0))

        # ── Run ──────────────────────────────────────────────────────────
        btn_row = ttk.Frame(outer)
        btn_row.pack(fill=tk.X, pady=(0, 10))
        self._run_btn = ttk.Button(btn_row, text="▶  Run Forward UQ", command=self._run_uq)
        self._run_btn.pack(side=tk.LEFT)
        add_export_button(btn_row, self._build_run_status).pack(side=tk.LEFT, padx=(6, 0))
        if not _HAS_PTY_TERMINAL:
            ttk.Label(btn_row, text="⚠ pyte not installed — run: pip install pyte",
                      foreground=PALETTE["warning"]).pack(side=tk.LEFT, padx=8)

        # ── Live output ──────────────────────────────────────────────────
        term_frame = ttk.LabelFrame(outer, text="Live output", padding=4)
        term_frame.pack(fill=tk.BOTH, expand=True)
        self._terminal = PtyTerminal(term_frame, rows=16, cols=110)
        self._terminal.pack(fill=tk.BOTH, expand=True)

        # ── Results summary (polled after the run finishes) ──────────────
        res_frame = ttk.LabelFrame(outer, text="Results summary (forward_uq_statistics.csv)", padding=4)
        res_frame.pack(fill=tk.X, pady=(6, 0))
        self._result_text = tk.Text(res_frame, height=6, font=FONTS["mono_small"],
                                     bg=PALETTE["surface"], fg=PALETTE["text"],
                                     relief=tk.FLAT, state=tk.DISABLED)
        self._result_text.pack(fill=tk.X)

        ttk.Label(outer, textvariable=self._status_var, style="Status.TLabel"
                  ).pack(anchor=tk.W, pady=(6, 0))

    # ------------------------------------------------------------------
    # Config load
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
        uq = self._cfg.get("ForwardUQ", {})
        self._cfg_summary.configure(
            text=(f"Mechanism : {locations.get('mechanism', '(not set)')}\n"
                  f"Uncertainty XML : {locations.get('uncertainty_data', '(not set)')}")
        )
        if uq.get("n_samples"):
            self._n_samples_var.set(str(uq["n_samples"]))
        if uq.get("method"):
            self._method_var.set(uq["method"])
        if uq.get("output_dir"):
            self._out_dir_var.set(uq["output_dir"])
        self._status_var.set(f"Loaded {path}")
        save_settings(_APP_NAME, {"last_target_opt": path})

    def _browse_out_dir(self) -> None:
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            self._out_dir_var.set(path)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _run_uq(self) -> None:
        if not self._cfg:
            messagebox.showwarning("No config", "Load a target.opt file first.")
            return

        out_dir = self._out_dir_var.get().strip() or "outputs/forward_uq"
        # B13: forward_uq.py resolves BOTH its config positional arg and
        # --output_dir relative to its own cwd (`workdir = os.getcwd()`,
        # `out = os.path.join(workdir, args.output_dir)`). Launching it with
        # cwd=out_dir while also passing a relative target_opt_path / a
        # relative --output_dir built from that same out_dir doubles both
        # ("outputs/forward_uq/outputs/forward_uq/..."), so the config load
        # fails with FileNotFoundError before Step 1 ever runs. Resolve
        # out_dir to absolute up front and derive both args from that one
        # absolute value -- no path is relative to anything anymore.
        out_dir_abs = Path(out_dir).resolve()
        out_dir_abs.mkdir(parents=True, exist_ok=True)

        target_opt_path = str(out_dir_abs / "target.opt")
        with open(target_opt_path, "w") as fh:
            yaml.safe_dump(self._cfg, fh, default_flow_style=False, sort_keys=False)

        cmd = [
            sys.executable, _FORWARD_UQ_SCRIPT, target_opt_path,
            "--n_samples", self._n_samples_var.get().strip() or "50000",
            "--method", self._method_var.get().strip() or "sobol",
            "--seed", self._seed_var.get().strip() or "42",
            "--output_dir", str(out_dir_abs),
        ]
        # M26: record when this run started so the poller only accepts a
        # results CSV written *by this run*, never a stale one left in out_dir
        # by a previous run. Subtract a small skew margin for clock/mtime
        # granularity.
        run_started_at = time.time() - 1.0
        self._terminal.run(cmd, cwd=str(out_dir_abs))
        self._status_var.set(f"Forward UQ running in embedded terminal (cwd={out_dir_abs})…")

        threading.Thread(
            target=self._poll_results, args=(str(out_dir_abs), run_started_at),
            daemon=True,
        ).start()

    def _poll_results(self, out_dir: str, run_started_at: float) -> None:
        for _ in range(30):  # wait up to 60 s
            time.sleep(2)
            hits = [
                h for h in glob.glob(
                    f"{out_dir}/**/forward_uq_statistics.csv", recursive=True)
                if os.path.getmtime(h) >= run_started_at   # M26: fresh only
            ]
            if hits:
                hits.sort(key=os.path.getmtime, reverse=True)  # newest first
                try:
                    rows = list(csv.DictReader(open(hits[0])))
                    lines = [f"Loaded {hits[0]} — {len(rows)} case(s):"]
                    for r in rows[:10]:
                        parts = [f"{k}={v}" for k, v in list(r.items())[:5]]
                        lines.append("  " + "  ".join(parts))
                    text = "\n".join(lines)
                except Exception as exc:
                    text = f"(CSV read error: {exc})"
                self.root.after(0, lambda t=text: self._show_results(t))
                return

    def _show_results(self, text: str) -> None:
        self._result_text.configure(state=tk.NORMAL)
        self._result_text.delete("1.0", tk.END)
        self._result_text.insert(tk.END, text)
        self._result_text.configure(state=tk.DISABLED)

    # -- run-status export (KRUNAL_JULY_23.md point 1) -----------------------
    def _build_run_status(self) -> RunStatusReport:
        locations = self._cfg.get("Locations", {})
        log = (self._terminal.text.get("1.0", "end") + "\n--- results summary ---\n"
               + self._result_text.get("1.0", "end"))
        return RunStatusReport(
            tool="Forward Uncertainty Quantification",
            inputs={
                "target.opt": self._cfg_path_var.get(),
                "mechanism": locations.get("mechanism", ""),
                "uncertainty XML": locations.get("uncertainty_data", ""),
            },
            output_dir=self._out_dir_var.get(),
            options={"n_samples": self._n_samples_var.get(),
                    "method": self._method_var.get(),
                    "seed": self._seed_var.get()},
            status="unknown",       # runs in a live PTY terminal, no captured exit code
            summary="live terminal output only -- no structured exit status "
                    "available (embedded PtyTerminal, not a captured subprocess)",
            log=log,
        )


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
    app = ForwardUQApp(root, initial_config_path=target_opt)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
