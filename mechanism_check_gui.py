#!/usr/bin/env python3
"""
mechanism_check_gui.py — Mechanism Health-Check (GUI front-end)

A dedicated desktop app for the ``rmip check`` mechanism diagnostics scoped in
MECHANISM_CHECK_RESEARCH.md (LLNL MechChecker / KAUST CloudFlame / Northeastern
ChemCheck-style checks, plus the Cantera-Users failure taxonomy).

Features
--------
* Check **any number of mechanisms** — add many files and run them **all at
  once** ("Check All") or **one at a time** ("Check Selected").
* Pick which diagnostics to run and set the (T,P) screening grid.
* Colour-coded findings tree (error / warning / info) grouped per mechanism.
* **Repair workflow**: obvious defects (thermo Tmid discontinuity, unmarked
  duplicate) get an *auto* fix pre-selected; ambiguous ones (collision-limit
  violation, negative-PLOG piece, Ea unit trap) expose a drop-down of the
  pre-built options so *you* decide. "Apply Fixes & Export" writes a corrected
  Cantera YAML and re-checks it to prove the repair.

The heavy lifting lives in ``rmip.analysis.mechanism_check`` /
``rmip.analysis.mechanism_fixer`` so the GUI and the CLI share one engine.

Usage:
    python mechanism_check_gui.py
    python mechanism_check_gui.py --no-gui   # headless self-test
"""
from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
import traceback
from pathlib import Path
from typing import Dict, List, Optional

_ROOT = Path(__file__).resolve().parent
_SRC = str(_ROOT / "src")
if _SRC not in sys.path:
    sys.path.append(_SRC)          # append (not insert) — keep stdlib io precedence

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
from mso_io.mechanism_check_fix_examples import fix_example_for as _fix_example_for

from rmip.analysis.mechanism_check import (
    MechanismChecker, CheckReport, ALL_CHECKS,
)
from rmip.analysis import mechanism_fixer as fixer_mod

_APP_NAME = "mechanism_check"

# human-friendly labels for the check ids
_CHECK_LABELS = {
    "load": "Load / parse (ck2yaml + Cantera)",
    "rate_sweep": "Rate NaN / negative sweep (T,P)",
    "collision_limit": "Collision-limit screen (fwd+rev)",
    "thermo_discontinuity": "Thermo Tmid discontinuity",
    "element_balance": "Element / charge balance",
    "duplicates": "Unmarked duplicate reactions",
    "third_body_duplicates": "Third-body-implied duplicate reactions",
    "pdep_sanity": "Pressure-dependent sanity (PLOG/falloff)",
    "completeness": "Completeness (unused / transport / T-range)",
    "unit_sanity": "Activation-energy unit sanity",
    "sim_setup_sanity": "Sim-setup smoke test (bounded const-V ignition)",
    "csp_timescales": "CSP ultrafast-timescale screening",
    "syntax_lint": "Syntax lint (line/column, raw text scan)",
}
_SEV_TAG = {"error": "sev_error", "warning": "sev_warning", "info": "sev_info"}
_SEV_ICON = {"error": "✗", "warning": "▲", "info": "•"}

# Worked "how do I fix this" examples per finding category (KRUNAL_JULY_23.md
# point 3), shown in the detail pane alongside the raw message/error text.
# Live in mso_io.mechanism_check_fix_examples (imported above as
# _fix_example_for) so the PySide6 port can render identical detail text
# without importing this module, which pulls in Cantera-dependent
# rmip.analysis.mechanism_check at module level.


def finding_for_iid(reports: Dict[str, CheckReport], iid: str):
    """Look up the (path, Finding) for a tree row's iid ("{id(rep)}:{fid}" —
    see MechanismCheckApp._add_report_to_tree). Returns (None, None) for a
    mechanism-header row or an iid from a since-cleared report. Pure/no-Tk
    so it's unit-testable without a live display (TESTING_CONVENTIONS.md)."""
    if ":" not in iid:
        return None, None
    rep_id_s, fid_s = iid.split(":", 1)
    try:
        rep_id, fid = int(rep_id_s), int(fid_s)
    except ValueError:
        return None, None
    for path, rep in reports.items():
        if id(rep) == rep_id and 0 <= fid < len(rep.findings):
            return path, rep.findings[fid]
    return None, None


def build_detail_text(path: Optional[str], f) -> str:
    """Render one Finding's full detail — message, location, the underlying
    tool error (if any), a worked fix example, and its fix options — as the
    plain selectable/copyable text shown in the GUI's detail pane. Pure/no-Tk
    so it's unit-testable without a live display."""
    lines = [
        f"Mechanism : {os.path.basename(path) if path else '(unknown)'}",
        f"Check     : {f.check}   Category: {f.category}   "
        f"Severity: {f.severity.upper()}",
        f"Location  : {f.location}",
        "",
        f.message,
    ]
    # the underlying tool error (ck2yaml/Cantera traceback) — this is exactly
    # the text KRUNAL_JULY_23.md reported as invisible/uncopyable
    err = (f.details or {}).get("error")
    if err:
        lines += ["", "Underlying tool error", "-" * 22, str(err).rstrip()]
    example = _fix_example_for(f.category)
    if example:
        lines += ["", "How to fix this", "-" * 16, example]
    if f.fix_options:
        lines += ["", "Available auto/choice fixes:"]
        for o in f.fix_options:
            tag = "auto" if o.kind == "auto" else o.kind
            lines.append(f"  • [{tag}] {o.label} — {o.description}")
    return "\n".join(lines)


# ===========================================================================
# Headless engine helpers (shared, importable, GUI-independent)
# ===========================================================================
def run_checks(paths: List[str], checks: Optional[List[str]] = None,
               **kw) -> Dict[str, tuple]:
    """Check each path. Returns {path: (checker, report)} (checkers kept live)."""
    out: Dict[str, tuple] = {}
    for p in paths:
        chk = MechanismChecker(p, **kw)
        rep = chk.run(checks=checks)
        out[p] = (chk, rep)
    return out


# ===========================================================================
# GUI
# ===========================================================================
class MechanismCheckApp:
    def __init__(self, root: "tk.Tk"):
        self.root = root
        root.title("Mechanism Health-Check")
        root.geometry("1180x820")
        apply_theme(root)

        self._q: "queue.Queue[tuple]" = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        # live state: path -> checker, path -> report
        self.checkers: Dict[str, MechanismChecker] = {}
        self.reports: Dict[str, CheckReport] = {}
        # fix selections: {(path, finding_id): option_id_or_None}
        self.fix_choice: Dict[tuple, "tk.StringVar"] = {}

        s = load_settings(_APP_NAME)
        self._build_ui(s)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(120, self._drain)

    # ------------------------------------------------------------------ UI
    def _build_ui(self, s: dict) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Mechanism Health-Check",
                  style="Header.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Diagnose combustion mechanisms and repair the "
                              "obvious faults — one at a time or all at once.",
                  style="Dim.TLabel").pack(anchor="w", pady=(0, 8))

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=360)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_left(body, s)
        self._build_right(body)

        # status bar
        self._status = ttk.Label(outer, text="Ready.", style="Status.TLabel",
                                 anchor="w")
        self._status.pack(fill="x", pady=(8, 0))

    def _build_left(self, parent, s: dict) -> None:
        left = ttk.Frame(parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # --- mechanism list ---
        mf = ttk.LabelFrame(left, text="Mechanisms", padding=8)
        mf.pack(fill="both", expand=False)
        ttk.Label(mf, text="Cantera YAML (.yaml/.yml) loads directly; CHEMKIN "
                          "(.inp/.mech/.ck/.cti) is converted via ck2yaml "
                          "first — a convert failure surfaces as a 'load' "
                          "finding below, with the real ck2yaml error in the "
                          "detail pane.", style="Dim.TLabel",
                 wraplength=330, justify="left").pack(anchor="w", pady=(0, 4))
        self.mech_list = tk.Listbox(mf, height=7, selectmode="extended",
                                    bg=PALETTE["entry_bg"], fg=PALETTE["text"],
                                    selectbackground=PALETTE["accent"],
                                    activestyle="none", highlightthickness=0)
        self.mech_list.pack(fill="both", expand=True)
        btns = ttk.Frame(mf)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="Add files…", command=self._add_files).pack(side="left")
        ttk.Button(btns, text="Remove", style="Small.TButton",
                   command=self._remove_selected).pack(side="left", padx=4)
        ttk.Button(btns, text="Clear", style="Small.TButton",
                   command=self._clear_mechs).pack(side="left")

        # --- checks ---
        cf = ttk.LabelFrame(left, text="Diagnostics to run", padding=8)
        cf.pack(fill="x", pady=(10, 0))
        self.check_vars: Dict[str, tk.BooleanVar] = {}
        saved_checks = set(s.get("checks", list(ALL_CHECKS)))
        for name in ALL_CHECKS:
            v = tk.BooleanVar(value=name in saved_checks)
            self.check_vars[name] = v
            ttk.Checkbutton(cf, text=_CHECK_LABELS.get(name, name),
                            variable=v).pack(anchor="w")

        # --- options ---
        of = ttk.LabelFrame(left, text="Screening grid & thresholds", padding=8)
        of.pack(fill="x", pady=(10, 0))
        of.columnconfigure(1, weight=1)
        self.opt_vars: Dict[str, tk.StringVar] = {}

        def orow(r, label, key, default):
            ttk.Label(of, text=label).grid(row=r, column=0, sticky="w")
            v = tk.StringVar(value=str(s.get(key, default)))
            self.opt_vars[key] = v
            ttk.Entry(of, textvariable=v, width=22).grid(row=r, column=1,
                                                         sticky="ew", padx=4, pady=2)
        orow(0, "T grid (K)", "T_grid", "300 800 1400 1800 2200 2500")
        orow(1, "P grid (atm)", "P_grid", "0.1 1 10 50")
        orow(2, "Collision exceed. ×", "collision_exceedance", "10")
        orow(3, "Target T high (K)", "target_T_high", "2500")

        # --- run buttons ---
        rf = ttk.Frame(left)
        rf.pack(fill="x", pady=(12, 0))
        self.btn_all = ttk.Button(rf, text="▶  Check All", command=self._check_all)
        self.btn_all.pack(side="left")
        self.btn_sel = ttk.Button(rf, text="Check Selected",
                                  command=self._check_selected)
        self.btn_sel.pack(side="left", padx=6)

    def _build_right(self, parent) -> None:
        right = ttk.Frame(parent)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=3)
        right.rowconfigure(1, weight=0)
        right.rowconfigure(3, weight=2)
        right.columnconfigure(0, weight=1)

        # --- findings tree ---
        tf = ttk.LabelFrame(right, text="Findings", padding=6)
        tf.grid(row=0, column=0, sticky="nsew")
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)
        cols = ("sev", "check", "message", "location")
        self.tree = ttk.Treeview(tf, columns=cols, show="tree headings",
                                 selectmode="browse")
        self.tree.heading("sev", text="")
        self.tree.heading("check", text="Check")
        self.tree.heading("message", text="Finding")
        self.tree.heading("location", text="Location")
        self.tree.column("#0", width=40, stretch=False)
        self.tree.column("sev", width=32, anchor="center", stretch=False)
        self.tree.column("check", width=140, stretch=False)
        self.tree.column("message", width=520)
        self.tree.column("location", width=160)
        self.tree.tag_configure("sev_error", foreground=PALETTE["error"])
        self.tree.tag_configure("sev_warning", foreground=PALETTE["warning"])
        self.tree.tag_configure("sev_info", foreground=PALETTE["accent2"])
        self.tree.tag_configure("mech", foreground=PALETTE["accent"],
                                font=FONTS["body_bold"])
        vs = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._on_finding_selected)

        # --- finding detail pane (selectable/copyable — the real ck2yaml/
        # Cantera error text lives in Finding.details["error"] and was
        # previously only visible via "Export JSON report…"; the Treeview
        # cells above and messagebox dialogs are not selectable at all.
        # KRUNAL_JULY_23.md: "you cannot even copy the error msg... it says
        # LOAD failed[,] [m]ake the errors thrown more descriptive[,] give
        # examples on how they can fix the issue raised.") ---
        df = ttk.LabelFrame(right, text="Finding details (select a row above — "
                                        "text here is selectable/copyable)",
                            padding=6)
        df.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        df.rowconfigure(0, weight=1)
        df.columnconfigure(0, weight=1)
        self.detail_text = tk.Text(df, height=7, wrap="word",
                                   bg=PALETTE["entry_bg"],
                                   fg=PALETTE["text"],
                                   relief="flat", padx=6, pady=4)
        self.detail_text.grid(row=0, column=0, sticky="nsew")
        dvs = ttk.Scrollbar(df, orient="vertical", command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=dvs.set, state="disabled")
        dvs.grid(row=0, column=1, sticky="ns")
        self._set_detail_text("Select a finding above to see its full message, "
                              "the underlying tool error (if any), and a "
                              "worked example of how to fix it.")

        # --- summary line ---
        self._summary = ttk.Label(right, text="", style="SubHeader.TLabel")
        self._summary.grid(row=2, column=0, sticky="w", pady=(6, 4))

        # --- fixes panel (scrollable) ---
        ff = ttk.LabelFrame(right, text="Repairs — choose an action per fixable "
                                        "finding, then apply", padding=6)
        ff.grid(row=3, column=0, sticky="nsew")
        ff.rowconfigure(0, weight=1)
        ff.columnconfigure(0, weight=1)
        canvas = tk.Canvas(ff, bg=PALETTE["surface"], highlightthickness=0)
        fvs = ttk.Scrollbar(ff, orient="vertical", command=canvas.yview)
        self.fix_frame = ttk.Frame(canvas)
        self.fix_frame.bind("<Configure>",
                            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self._fix_window = canvas.create_window((0, 0), window=self.fix_frame,
                                                anchor="nw")
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(self._fix_window, width=e.width))
        canvas.configure(yscrollcommand=fvs.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        fvs.grid(row=0, column=1, sticky="ns")
        self._fix_canvas = canvas

        af = ttk.Frame(right)
        af.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        self.btn_apply = ttk.Button(af, text="Apply Fixes & Export…",
                                    command=self._apply_fixes, state="disabled")
        self.btn_apply.pack(side="left")
        ttk.Button(af, text="Export JSON report…", style="Small.TButton",
                   command=self._export_json).pack(side="left", padx=6)
        add_export_button(af, self._build_run_status, text="Export run status…"
                          ).pack(side="left", padx=6)

    # -------------------------------------------------------------- actions
    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select mechanism file(s)",
            filetypes=[("Mechanisms", "*.yaml *.yml *.inp *.mech *.ck *.cti"),
                       ("All files", "*.*")])
        for p in paths:
            if p not in self.mech_list.get(0, "end"):
                self.mech_list.insert("end", p)

    def _remove_selected(self) -> None:
        for i in reversed(self.mech_list.curselection()):
            self.mech_list.delete(i)

    def _clear_mechs(self) -> None:
        self.mech_list.delete(0, "end")

    def _check_all(self) -> None:
        self._start_check(list(self.mech_list.get(0, "end")))

    def _check_selected(self) -> None:
        sel = [self.mech_list.get(i) for i in self.mech_list.curselection()]
        if not sel:
            messagebox.showinfo("No selection",
                                "Select one or more mechanisms in the list, "
                                "or use 'Check All'.")
            return
        self._start_check(sel)

    def _selected_checks(self) -> List[str]:
        return [n for n in ALL_CHECKS if self.check_vars[n].get()]

    def _grid(self, key: str) -> Optional[List[float]]:
        raw = self.opt_vars[key].get().strip()
        if not raw:
            return None
        try:
            return [float(x) for x in raw.replace(",", " ").split()]
        except ValueError:
            return None

    def _start_check(self, paths: List[str]) -> None:
        if self._busy():
            return
        if not paths:
            messagebox.showinfo("No mechanisms", "Add at least one mechanism file.")
            return
        checks = self._selected_checks()
        if not checks:
            messagebox.showinfo("No diagnostics", "Enable at least one diagnostic.")
            return
        try:
            exceed = float(self.opt_vars["collision_exceedance"].get())
            targeth = float(self.opt_vars["target_T_high"].get())
        except ValueError:
            messagebox.showerror("Bad option",
                                 "Collision exceedance and target-T must be numbers.")
            return
        kw = dict(T_grid_K=self._grid("T_grid"), P_atm_grid=self._grid("P_grid"),
                  collision_exceedance=exceed, target_T_high=targeth)
        self._save_state()
        self._set_running(True, f"Checking {len(paths)} mechanism(s)…")
        # drop previous live checkers
        self._cleanup_checkers()
        self.reports.clear()
        self._set_detail_text("Select a finding above to see its full message, "
                              "the underlying tool error (if any), and a "
                              "worked example of how to fix it.")

        def work():
            try:
                for p in paths:
                    self._q.put(("progress", f"Checking {os.path.basename(p)}…"))
                    chk = MechanismChecker(p, **kw)
                    rep = chk.run(checks=checks)
                    self._q.put(("report", p, chk, rep))
            except Exception:
                self._q.put(("error", traceback.format_exc()))
            self._q.put(("done_check",))

        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

    def _apply_fixes(self) -> None:
        if self._busy():
            return
        # gather selected fixes per mechanism
        plan: Dict[str, List[dict]] = {}
        for (path, fid), var in self.fix_choice.items():
            oid = var.get()
            if not oid or oid == "__skip__":
                continue
            rep = self.reports.get(path)
            if rep is None:
                continue
            finding = rep.findings[fid]
            opt = next((o for o in finding.fix_options if o.id == oid), None)
            if opt is None:
                continue
            plan.setdefault(path, []).append(
                {"option_id": opt.id, "params": opt.params, "location": finding.location})
        if not plan:
            messagebox.showinfo("Nothing selected",
                                "Choose at least one repair action first.")
            return
        out_dir = filedialog.askdirectory(title="Folder for corrected mechanism(s)")
        if not out_dir:
            return
        checks = self._selected_checks()
        self._set_running(True, "Applying fixes…")

        def work():
            try:
                for path, fixes in plan.items():
                    chk = self.checkers.get(path)
                    if chk is None or chk.yaml_path is None:
                        self._q.put(("progress",
                                     f"Cannot fix {os.path.basename(path)} — no YAML."))
                        continue
                    fixer = fixer_mod.MechanismFixer(chk.yaml_path)
                    results = fixer.apply(fixes)
                    base = os.path.splitext(os.path.basename(path))[0]
                    out = os.path.join(out_dir, base + ".fixed.yaml")
                    fixer.write(out)
                    recheck = MechanismChecker(out).run(checks=checks)
                    self._q.put(("fixed", path, out, results, recheck))
            except Exception:
                self._q.put(("error", traceback.format_exc()))
            self._q.put(("done_fix",))

        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

    def _export_json(self) -> None:
        if not self.reports:
            messagebox.showinfo("Nothing to export", "Run a check first.")
            return
        path = filedialog.asksaveasfilename(
            title="Save JSON report", defaultextension=".json",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        import json
        payload = {p: r.to_dict() for p, r in self.reports.items()}
        with open(path, "w") as fh:
            json.dump(payload, fh, indent=2, default=str)
        self._status.config(text=f"Report written to {path}")

    # -- run-status export (KRUNAL_JULY_23.md point 1) ----------------------
    def _build_run_status(self) -> RunStatusReport:
        inputs = {os.path.basename(p): p for p in self.mech_list.get(0, "end")}
        options = {
            "diagnostics": ", ".join(n for n, v in self.check_vars.items() if v.get()),
            **{k: v.get() for k, v in self.opt_vars.items()},
        }
        if not self.reports:
            return RunStatusReport(
                tool="Mechanism Health-Check", inputs=inputs, options=options,
                status="unknown", summary="no check has been run yet")
        total_err = sum(r.n_errors for r in self.reports.values())
        total_warn = sum(r.n_warnings for r in self.reports.values())
        log_lines = []
        for path, rep in self.reports.items():
            c = rep.counts()
            log_lines.append(f"{os.path.basename(path)}: "
                             f"[{'LOADED' if rep.loaded else 'LOAD FAILED'}] "
                             f"{c['error']}E / {c['warning']}W / {c['info']}I")
            for f in rep.sorted_findings():
                log_lines.append(f"  [{f.severity}] {f.check}: {f.message}")
        return RunStatusReport(
            tool="Mechanism Health-Check", inputs=inputs, options=options,
            status="success" if total_err == 0 else "failed",
            summary=f"{total_err} error(s), {total_warn} warning(s) across "
                    f"{len(self.reports)} mechanism(s)",
            log="\n".join(log_lines),
        )

    # --------------------------------------------------------- queue drain
    def _drain(self) -> None:
        try:
            while True:
                msg = self._q.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    self._status.config(text=msg[1])
                elif kind == "report":
                    _, path, chk, rep = msg
                    self.checkers[path] = chk
                    self.reports[path] = rep
                    self._add_report_to_tree(path, rep)
                elif kind == "fixed":
                    _, path, out, results, recheck = msg
                    self._show_fix_result(path, out, results, recheck)
                elif kind == "error":
                    messagebox.showerror("Engine error", msg[1][-1500:])
                elif kind == "done_check":
                    self._rebuild_fix_panel()
                    summary = self._overall_summary()
                    self._summary.config(text=summary)
                    self._set_running(False, summary)
                elif kind == "done_fix":
                    self._set_running(False, "Fixes applied — corrected files written.")
        except queue.Empty:
            pass
        self.root.after(120, self._drain)

    # --------------------------------------------------------- detail pane
    def _set_detail_text(self, text: str) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")

    def _on_finding_selected(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        path, f = finding_for_iid(self.reports, sel[0])
        if f is None:
            self._set_detail_text("(mechanism header row — select a finding "
                                  "underneath it for details)")
            return
        self._set_detail_text(build_detail_text(path, f))

    # ------------------------------------------------------------- rendering
    def _add_report_to_tree(self, path: str, rep: CheckReport) -> None:
        c = rep.counts()
        label = (f"{os.path.basename(path)}   "
                 f"[{'LOADED' if rep.loaded else 'LOAD FAILED'}]  "
                 f"{c['error']}E / {c['warning']}W / {c['info']}I")
        node = self.tree.insert("", "end", text="", values=("", "", label, ""),
                                open=True, tags=("mech",))
        for i, f in enumerate(rep.sorted_findings()):
            # find the finding's index in the ORIGINAL list (for fix mapping)
            fid = rep.findings.index(f)
            self.tree.insert(node, "end", iid=f"{id(rep)}:{fid}",
                             values=(_SEV_ICON.get(f.severity, "•"),
                                     f.check,
                                     f.message,
                                     f.location),
                             tags=(_SEV_TAG.get(f.severity, ""),))

    def _overall_summary(self) -> str:
        if not self.reports:
            return "No results."
        te = sum(r.n_errors for r in self.reports.values())
        tw = sum(r.n_warnings for r in self.reports.values())
        nfix = sum(1 for r in self.reports.values() for f in r.findings if f.fixable)
        verdict = "ALL PASS" if te == 0 else f"{te} error(s)"
        return (f"{len(self.reports)} mechanism(s): {verdict}, {tw} warning(s); "
                f"{nfix} fixable finding(s).")

    def _rebuild_fix_panel(self) -> None:
        for w in self.fix_frame.winfo_children():
            w.destroy()
        self.fix_choice.clear()

        any_fix = False
        row = 0
        for path, rep in self.reports.items():
            fixables = [(i, f) for i, f in enumerate(rep.findings) if f.fixable]
            if not fixables:
                continue
            any_fix = True
            ttk.Label(self.fix_frame, text=os.path.basename(path),
                      style="SubHeader.TLabel").grid(row=row, column=0, columnspan=3,
                                                     sticky="w", pady=(8, 2))
            row += 1
            for fid, f in fixables:
                icon = _SEV_ICON.get(f.severity, "•")
                msg = f.message if len(f.message) < 88 else f.message[:85] + "…"
                lbl = ttk.Label(self.fix_frame, text=f"{icon} {msg}",
                                style="Dim.TLabel", wraplength=560, justify="left")
                lbl.grid(row=row, column=0, sticky="w", padx=(12, 6))

                # build option menu: recommended first, then rest, then skip
                labels, id_by_label = [], {}
                ordered = sorted(f.fix_options, key=lambda o: not o.recommended)
                for o in ordered:
                    tag = "  (auto)" if o.kind == "auto" else ""
                    disp = o.label + tag + ("  ★" if o.recommended else "")
                    labels.append(disp)
                    id_by_label[disp] = o.id
                skip_label = "— skip (leave as-is) —"
                labels.append(skip_label)
                id_by_label[skip_label] = "__skip__"

                # default: auto fix or recommended → its id; else skip
                default_opt = f.auto_fix or next(
                    (o for o in f.fix_options if o.recommended), None)
                default_disp = next(
                    (d for d, oid in id_by_label.items()
                     if default_opt and oid == default_opt.id), skip_label)

                var = tk.StringVar(value=id_by_label[default_disp])
                disp_var = tk.StringVar(value=default_disp)

                def on_pick(dv=disp_var, v=var, m=id_by_label):
                    v.set(m.get(dv.get(), "__skip__"))

                cb = ttk.Combobox(self.fix_frame, values=labels, state="readonly",
                                  textvariable=disp_var, width=48)
                cb.grid(row=row, column=1, sticky="e", padx=6, pady=1)
                cb.bind("<<ComboboxSelected>>", lambda e, cb=on_pick: cb())
                self.fix_choice[(path, fid)] = var
                row += 1

        if not any_fix:
            ttk.Label(self.fix_frame, text="No fixable findings.",
                      style="Dim.TLabel").grid(row=0, column=0, sticky="w", padx=8)
        self.btn_apply.config(state=("normal" if any_fix else "disabled"))
        self._fix_canvas.yview_moveto(0.0)

    def _show_fix_result(self, path, out, results, recheck) -> None:
        applied = sum(1 for r in results if r.status == "applied")
        lines = [f"{os.path.basename(path)} → {out}",
                 f"  applied {applied}/{len(results)} fix(es); re-check: "
                 f"loaded={recheck.loaded}, {recheck.n_errors} error(s), "
                 f"{recheck.n_warnings} warning(s)."]
        for r in results:
            icon = {"applied": "✓", "skipped": "–", "failed": "✗"}.get(r.status, "?")
            lines.append(f"    {icon} {r.option_id}: {r.message}")
        messagebox.showinfo("Fixes applied", "\n".join(lines))
        self._status.config(text=f"Corrected mechanism written to {out}")

    # ---------------------------------------------------------------- misc
    def _busy(self) -> bool:
        if self._worker is not None and self._worker.is_alive():
            messagebox.showinfo("Busy", "A task is already running.")
            return True
        return False

    def _set_running(self, running: bool, status: str = "") -> None:
        state = "disabled" if running else "!disabled"
        for b in (self.btn_all, self.btn_sel):
            b.state([state])
        if not running:
            self.btn_apply.state(["!disabled"] if self.fix_choice else ["disabled"])
        if status:
            self._status.config(text=status)

    def _save_state(self) -> None:
        save_settings(_APP_NAME, {
            "checks": self._selected_checks(),
            **{k: v.get() for k, v in self.opt_vars.items()},
        })

    def _cleanup_checkers(self) -> None:
        for chk in self.checkers.values():
            try:
                chk.cleanup()
            except Exception:
                pass
        self.checkers.clear()

    def _on_close(self) -> None:
        self._cleanup_checkers()
        try:
            self._save_state()
        except Exception:
            pass
        self.root.destroy()


# ===========================================================================
# Entry point + headless self-test
# ===========================================================================
def _headless_selftest() -> int:
    """Exercise the engine on the bundled broken fixtures without a display."""
    fx = _ROOT / "src" / "rmip" / "tests" / "fixtures"
    targets = [fx / "broken_mech.yaml", fx / "broken_dup.yaml",
               fx / "broken_plog.yaml"]
    missing = [str(t) for t in targets if not t.exists()]
    if missing:
        print("Fixtures missing (run _make_broken_mech.py):", missing)
        return 1
    results = run_checks([str(t) for t in targets])
    ok = True
    for p, (chk, rep) in results.items():
        c = rep.counts()
        nfix = sum(1 for f in rep.findings if f.fixable)
        print(f"{os.path.basename(p)}: loaded={rep.loaded} "
              f"errors={c['error']} warnings={c['warning']} fixable={nfix}")
        if c["error"] == 0:
            ok = False
        chk.cleanup()
    print("TK available:", _HAS_TK)
    return 0 if ok else 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--no-gui", action="store_true",
                    help="Headless self-test on the bundled broken fixtures.")
    args = ap.parse_args()
    if args.no_gui or not _HAS_TK:
        if not _HAS_TK and not args.no_gui:
            print("tkinter unavailable — running headless self-test instead.")
        return _headless_selftest()
    root = tk.Tk()
    MechanismCheckApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
