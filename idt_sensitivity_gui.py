#!/usr/bin/env python3
"""
idt_sensitivity_gui.py — Ignition-Delay Sensitivity (GUI front-end)

W6 (Cantera google groups/W6_idt_sensitivity.md) — a first-class desktop tool for
the ignition-delay sensitivity capability (community problem P20, an 8-year
recurring ask). Reports the logarithmic sensitivity d ln(τ)/d ln(k_i) for every
reaction, by either the gold-standard brute-force method or the fast CVODES
method, with a selectable IDT definition — and draws the ranked tornado chart.

The engine lives in ``rmip.simulation.idt_sensitivity`` so this GUI and the
``rmip idt-sens`` CLI share one implementation.

Usage:
    python idt_sensitivity_gui.py
    python idt_sensitivity_gui.py --no-gui   # headless self-test
"""
from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
import traceback
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent
_SRC = str(_ROOT / "src")
if _SRC not in sys.path:
    sys.path.append(_SRC)

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    _HAS_TK = True
except ImportError:
    _HAS_TK = False

from gui_common.theme import PALETTE, FONTS, apply_theme
from gui_common.settings import load_settings, save_settings
from gui_common.run_status_export import add_export_button
from mso_io.run_status import RunStatusReport
from mso_io.plot_style import (
    PlotStyle, apply_style, save_figure, EXPORT_FORMATS, LEGEND_LOCATIONS, GRID_AXES,
)

from rmip.simulation.idt_sensitivity import (
    IdtSensitivityAnalyzer, IdtSensitivityResult,
)

_APP_NAME = "idt_sensitivity"


class IdtSensitivityApp:
    def __init__(self, root: "tk.Tk"):
        self.root = root
        root.title("Ignition-Delay Sensitivity")
        root.geometry("1160x780")
        apply_theme(root)
        self._q: "queue.Queue[tuple]" = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._result: Optional[IdtSensitivityResult] = None
        # last-run state, for "Export run status…" (KRUNAL_JULY_23.md pt. 1)
        self._last_error: Optional[str] = None
        self._style_vars: dict = {}   # KRUNAL_JULY_23.md pt. 4 -- plot customization
        self._last_fig = None

        s = load_settings(_APP_NAME)
        self._build_ui(s)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(120, self._drain)

    # ------------------------------------------------------------------ UI
    def _build_ui(self, s: dict) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Ignition-Delay Sensitivity",
                  style="Header.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Logarithmic sensitivity  d ln(τ) / d ln(k)  per "
                              "reaction — brute-force or CVODES.",
                  style="Dim.TLabel").pack(anchor="w", pady=(0, 8))

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=340)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_controls(body, s)
        self._build_output(body)

        self._status = ttk.Label(outer, text="Ready.", style="Status.TLabel",
                                 anchor="w")
        self._status.pack(fill="x", pady=(8, 0))

    def _build_controls(self, parent, s: dict) -> None:
        left = ttk.Frame(parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        cf = ttk.LabelFrame(left, text="Case", padding=8)
        cf.pack(fill="x")
        cf.columnconfigure(1, weight=1)
        self.v = {}

        def row(r, label, key, default, browse=False):
            ttk.Label(cf, text=label).grid(row=r, column=0, sticky="w", pady=1)
            var = tk.StringVar(value=str(s.get(key, default)))
            self.v[key] = var
            e = ttk.Entry(cf, textvariable=var, width=20)
            e.grid(row=r, column=1, sticky="ew", padx=4)
            if browse:
                ttk.Button(cf, text="…", width=3, command=lambda: self._pick(var)
                           ).grid(row=r, column=2)

        row(0, "Mechanism (.yaml)", "mech", "", browse=True)
        row(1, "Fuel", "fuel", "H2")
        row(2, "Oxidizer", "oxidizer", "O2:1.0, N2:3.76")
        row(3, "T [K]", "T", "1000")
        row(4, "P [atm]", "P", "10")
        row(5, "phi", "phi", "1.0")
        row(6, "threshold ΔT [K]", "threshold_dT", "400")
        row(7, "species (for def)", "species", "OH")
        row(8, "delta (brute)", "delta", "0.05")
        row(9, "top-N", "top", "20")

        of = ttk.LabelFrame(left, text="Method & definition", padding=8)
        of.pack(fill="x", pady=(10, 0))
        of.columnconfigure(1, weight=1)
        self.choice = {}

        def combo(r, label, key, values, default):
            ttk.Label(of, text=label).grid(row=r, column=0, sticky="w", pady=1)
            var = tk.StringVar(value=s.get(key, default))
            self.choice[key] = var
            ttk.Combobox(of, textvariable=var, values=values, state="readonly",
                         width=16).grid(row=r, column=1, sticky="ew", padx=4)

        combo(0, "method", "method", ["brute", "cvodes"], "brute")
        combo(1, "IDT definition", "idt_def", ["dTdt", "threshold", "species"], "dTdt")
        combo(2, "reactor", "reactor", ["constV", "constP"], "constV")
        combo(3, "normalization", "norm", ["log", "raw"], "log")
        combo(4, "diff (brute)", "diff", ["central", "forward"], "central")

        self._build_style_controls(left, s)

        rf = ttk.Frame(left)
        rf.pack(fill="x", pady=(12, 0))
        self.btn_run = ttk.Button(rf, text="▶  Compute", command=self._run)
        self.btn_run.pack(side="left")
        ttk.Button(rf, text="Save JSON…", style="Small.TButton",
                   command=self._save).pack(side="left", padx=6)
        ttk.Button(rf, text="Save chart…", style="Small.TButton",
                   command=self._save_chart).pack(side="left", padx=6)
        add_export_button(rf, self._build_run_status).pack(side="left", padx=6)

    def _build_style_controls(self, left, s: dict) -> None:
        """KRUNAL_JULY_23.md point 4 -- "every option that matplotlib
        provides must be available" for this chart's export."""
        pf = ttk.LabelFrame(left, text="Plot style", padding=8)
        pf.pack(fill="x", pady=(10, 0))
        pf.columnconfigure(1, weight=1)

        def combo(r, label, key, values, default):
            ttk.Label(pf, text=label).grid(row=r, column=0, sticky="w", pady=1)
            var = tk.StringVar(value=s.get(f"style_{key}", default))
            self._style_vars[key] = var
            ttk.Combobox(pf, textvariable=var, values=values, state="readonly",
                         width=14).grid(row=r, column=1, sticky="ew", padx=4)

        def entry(r, label, key, default):
            ttk.Label(pf, text=label).grid(row=r, column=0, sticky="w", pady=1)
            var = tk.StringVar(value=s.get(f"style_{key}", default))
            self._style_vars[key] = var
            ttk.Entry(pf, textvariable=var, width=16).grid(
                row=r, column=1, sticky="ew", padx=4)

        combo(0, "export format", "export_format", EXPORT_FORMATS, "png")
        entry(1, "dpi", "dpi", "150")
        entry(2, "color scheme", "color_scheme", "default")
        entry(3, "font family", "font_family", "")
        entry(4, "title font size", "font_size_title", "12")
        entry(5, "axis font size", "font_size_axis_label", "10")
        entry(6, "tick font size", "font_size_tick_label", "7")
        entry(7, "title", "title", "")
        entry(8, "x label", "xlabel", "")
        combo(9, "legend loc", "legend_loc", LEGEND_LOCATIONS, "best")
        combo(10, "grid", "grid", GRID_AXES, "none")

    def _collect_style(self) -> PlotStyle:
        v = self._style_vars
        return PlotStyle(
            export_format=v["export_format"].get(),
            dpi=int(float(v["dpi"].get() or 150)),
            color_scheme=v["color_scheme"].get() or "default",
            font_family=v["font_family"].get(),
            font_size_title=int(float(v["font_size_title"].get() or 12)),
            font_size_axis_label=int(float(v["font_size_axis_label"].get() or 10)),
            font_size_tick_label=int(float(v["font_size_tick_label"].get() or 7)),
            title=v["title"].get(),
            xlabel=v["xlabel"].get(),
            legend_loc=v["legend_loc"].get(),
            grid=v["grid"].get(),
        )

    def _save_chart(self):
        if self._last_fig is None:
            messagebox.showinfo("Nothing to save", "Run a computation first.")
            return
        style = self._collect_style()
        p = filedialog.asksaveasfilename(
            defaultextension=f".{style.export_format}",
            filetypes=[(style.export_format.upper(), f"*.{style.export_format}")])
        if p:
            out = save_figure(self._last_fig, p, style)
            self._status.config(text=f"Chart saved → {out}")

    def _build_output(self, parent) -> None:
        right = ttk.Frame(parent)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=3)
        right.rowconfigure(1, weight=2)
        right.columnconfigure(0, weight=1)

        # chart
        chart = ttk.LabelFrame(right, text="Ranked sensitivities", padding=4)
        chart.grid(row=0, column=0, sticky="nsew")
        chart.rowconfigure(0, weight=1)
        chart.columnconfigure(0, weight=1)
        self._chart_holder = ttk.Frame(chart)
        self._chart_holder.grid(row=0, column=0, sticky="nsew")
        self._canvas = None

        # log
        lf = ttk.LabelFrame(right, text="Log", padding=4)
        lf.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)
        self._log = tk.Text(lf, height=10, bg=PALETTE["entry_bg"],
                            fg=PALETTE["text"], wrap="none")
        self._log.grid(row=0, column=0, sticky="nsew")
        vs = ttk.Scrollbar(lf, orient="vertical", command=self._log.yview)
        self._log.configure(yscrollcommand=vs.set)
        vs.grid(row=0, column=1, sticky="ns")

    # -------------------------------------------------------------- actions
    def _pick(self, var):
        p = filedialog.askopenfilename(
            filetypes=[("Cantera YAML", "*.yaml *.yml"), ("All", "*.*")])
        if p:
            var.set(p)

    def _run(self):
        if self._worker is not None and self._worker.is_alive():
            messagebox.showinfo("Busy", "A computation is already running.")
            return
        try:
            kw = dict(
                mechanism_path=self.v["mech"].get().strip(),
                fuel=self.v["fuel"].get().strip(),
                oxidizer=self.v["oxidizer"].get().strip(),
                T_K=float(self.v["T"].get()), P_atm=float(self.v["P"].get()),
                phi=float(self.v["phi"].get()),
                reactor=self.choice["reactor"].get(),
                idt_definition=self.choice["idt_def"].get(),
                threshold_dT=float(self.v["threshold_dT"].get()),
                species=self.v["species"].get().strip() or None)
        except ValueError as e:
            messagebox.showerror("Bad input", f"Numeric field problem: {e}")
            return
        if not kw["mechanism_path"] or not os.path.exists(kw["mechanism_path"]):
            messagebox.showerror("Missing mechanism", "Choose a Cantera YAML file.")
            return
        method = self.choice["method"].get()
        run_kw = dict(norm=self.choice["norm"].get())
        if method == "brute":
            run_kw.update(diff=self.choice["diff"].get(),
                          delta=float(self.v["delta"].get()))
        self._save_state()
        self._log.delete("1.0", "end")
        self._set_running(True, "Computing…")

        def work():
            try:
                analyzer = IdtSensitivityAnalyzer(**kw)
                result = analyzer.run(method=method, **run_kw)
                self._q.put(("result", result))
            except Exception:
                self._q.put(("error", traceback.format_exc()))
            self._q.put(("done",))

        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

    def _save(self):
        if self._result is None:
            messagebox.showinfo("Nothing to save", "Run a computation first.")
            return
        p = filedialog.asksaveasfilename(defaultextension=".json",
                                         filetypes=[("JSON", "*.json")])
        if p:
            self._result.save(p)
            self._status.config(text=f"Saved → {p}")

    # --------------------------------------------------------- queue drain
    def _drain(self):
        try:
            while True:
                msg = self._q.get_nowait()
                if msg[0] == "result":
                    self._result = msg[1]
                    self._last_error = None
                    top = int(self.v["top"].get() or 20)
                    self._log.insert("end", self._result.render_text(n=top) + "\n")
                    self._draw_chart(self._result, top)
                elif msg[0] == "error":
                    self._last_error = msg[1].strip().splitlines()[-1]
                    self._log.insert("end", "ERROR:\n" + msg[1][-1600:] + "\n")
                    messagebox.showerror("Failed", msg[1].strip().splitlines()[-1])
                elif msg[0] == "done":
                    self._set_running(False, "Done." if self._result else "Failed.")
        except queue.Empty:
            pass
        self.root.after(120, self._drain)

    # -- run-status export (KRUNAL_JULY_23.md point 1) -----------------------
    def _build_run_status(self) -> RunStatusReport:
        return RunStatusReport(
            tool="Ignition-Delay Sensitivity",
            inputs={"mechanism (.yaml)": self.v["mech"].get(),
                    "fuel": self.v["fuel"].get(),
                    "oxidizer": self.v["oxidizer"].get()},
            options={
                "T [K]": self.v["T"].get(), "P [atm]": self.v["P"].get(),
                "phi": self.v["phi"].get(),
                "method": self.choice["method"].get(),
                "IDT definition": self.choice["idt_def"].get(),
                "reactor": self.choice["reactor"].get(),
                "normalization": self.choice["norm"].get(),
                "diff (brute)": self.choice["diff"].get(),
                "delta (brute)": self.v["delta"].get(),
                "threshold dT [K]": self.v["threshold_dT"].get(),
            },
            status="failed" if self._last_error else
                   ("success" if self._result is not None else "unknown"),
            summary=self._last_error,
            log=self._log.get("1.0", "end"),
        )

    def _draw_chart(self, result: IdtSensitivityResult, n: int):
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except Exception as e:
            self._log.insert("end", f"(chart unavailable: {e})\n")
            return
        for w in self._chart_holder.winfo_children():
            w.destroy()
        pairs = result.top(n)[::-1]
        labels = [eq for eq, _ in pairs]
        vals = [v for _, v in pairs]
        colors = [PALETTE["error"] if v < 0 else PALETTE["accent"] for v in vals]
        fig = Figure(figsize=(6.5, max(2.5, 0.32 * len(pairs))),
                     facecolor=PALETTE["surface"])
        ax = fig.add_subplot(111)
        ax.set_facecolor(PALETTE["surface"])
        ax.barh(range(len(vals)), vals, color=colors)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=7, color=PALETTE["text"])
        ax.axvline(0, color=PALETTE["text_dim"], lw=0.8)
        xlabel = ("d ln(τ) / d ln(k)" if result.normalization == "log"
                  else "dτ / d ln(k) [s]")
        ax.set_xlabel(xlabel, color=PALETTE["text"], fontsize=9)
        ax.tick_params(colors=PALETTE["text_dim"], labelsize=7)
        for spine in ax.spines.values():
            spine.set_color(PALETTE["border"])

        if self._style_vars:
            style = self._collect_style()
            # Only apply the parts of PlotStyle that don't fight the dark
            # theme's own axis coloring (title/xlabel/font sizes/grid) --
            # apply_style's own show_legend/legend_loc are skipped here
            # since this chart has no legend.
            if style.title:
                ax.set_title(style.title, color=PALETTE["text"], fontsize=style.font_size_title)
            if style.xlabel:
                ax.set_xlabel(style.xlabel, color=PALETTE["text"], fontsize=style.font_size_axis_label)
            else:
                ax.xaxis.label.set_fontsize(style.font_size_axis_label)
            ax.tick_params(labelsize=style.font_size_tick_label)
            if style.font_family:
                for text in [ax.title, ax.xaxis.label] + ax.get_yticklabels() + ax.get_xticklabels():
                    text.set_family(style.font_family)
            if style.grid != "none":
                ax.grid(True, axis=("both" if style.grid == "both" else style.grid),
                        alpha=0.3, color=PALETTE["text_dim"])

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self._chart_holder)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._canvas = canvas
        self._last_fig = fig

    # ---------------------------------------------------------------- misc
    def _set_running(self, running: bool, status: str = ""):
        self.btn_run.state(["disabled" if running else "!disabled"])
        if status:
            self._status.config(text=status)

    def _save_state(self):
        save_settings(_APP_NAME, {**{k: v.get() for k, v in self.v.items()},
                                  **{k: v.get() for k, v in self.choice.items()}})

    def _on_close(self):
        try:
            self._save_state()
        except Exception:
            pass
        self.root.destroy()


# ===========================================================================
def _headless_selftest() -> int:
    import warnings
    warnings.filterwarnings("ignore")
    import cantera as ct
    mech = os.path.join(ct.__path__[0], "data", "h2o2.yaml")
    analyzer = IdtSensitivityAnalyzer(mech, fuel="H2", T_K=1000, P_atm=10, phi=1.0)
    rb = analyzer.run_brute(delta=0.05, norm="log")
    rc = analyzer.run_cvodes(norm="log")
    bset = {e for e, _ in rb.top(5)}
    cset = {e for e, _ in rc.top(5)}
    print(f"base IDT = {rb.idt_s:.3e} s")
    print(f"brute top-3:  {[e for e, _ in rb.top(3)]}")
    print(f"cvodes top-3: {[e for e, _ in rc.top(3)]}")
    print(f"top-5 overlap: {len(bset & cset)}/5")
    print("TK available:", _HAS_TK)
    return 0 if len(bset & cset) >= 4 else 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--no-gui", action="store_true",
                    help="Headless self-test (brute vs cvodes agreement).")
    args = ap.parse_args()
    if args.no_gui or not _HAS_TK:
        return _headless_selftest()
    root = tk.Tk()
    IdtSensitivityApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
