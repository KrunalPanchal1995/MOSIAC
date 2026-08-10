#!/usr/bin/env python3
"""
launcher_gui.py — Single entry point listing all split-out GUI apps.

Phase 6 (optional) of the GUI-separation plan (see
MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md
§1.6): splitting generate_target_opt.py into 7 standalone apps means KP
loses the single "one script to run" entry point this window restores --
each button spawns the corresponding app as its own subprocess (not
imported in-process), so a crash in one app can never take this launcher
or any other running app down with it.

Usage:
    python launcher_gui.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC = str(_ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    _HAS_TK = True
except ImportError:
    _HAS_TK = False

from gui_common.theme import PALETTE, FONTS, apply_theme, style_text_widget

# (button label, script filename, one-line description) -- derived from
# mso_studio.launcher.catalog.CATALOG (RUNNER_SCIENCE entries: the
# Tkinter/anaconda apps this window lists; the Qt launcher and MSO Studio
# have their own buttons below, not part of this list). CATALOG is now the
# single source of truth for "what apps exist" -- this used to be an
# independently hand-maintained list that a drift-guard test
# (test_launcher_catalog.py) merely *checked* against the catalog; inverting
# the direction so it's generated from the catalog makes drift structurally
# impossible instead of merely detected.
from mso_studio.launcher.catalog import CATALOG, RUNNER_SCIENCE

_APPS = [
    (entry.title, entry.script, entry.description)
    for entry in CATALOG
    if entry.script and entry.runner == RUNNER_SCIENCE
]


class LauncherApp:
    def __init__(self, root: "tk.Tk"):
        self.root = root
        self.root.title("RMIP / MUQ-SAC Toolchain Launcher")
        self.root.geometry("620x540")
        self._build_ui()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text="RMIP / MUQ-SAC Toolchain", font=FONTS["header"]
                  ).pack(anchor=tk.W)
        ttk.Label(outer,
                  text="Each task now has its own dedicated app (see "
                       "MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md). "
                       "Pick one below — it opens as its own independent window/process.",
                  foreground=PALETTE["text_dim"], wraplength=560).pack(anchor=tk.W, pady=(0, 14))

        # ---- new game-style PySide6 launcher (preferred) --------------
        row = ttk.Frame(outer)
        row.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(row, text="✨ Open the new launcher (PySide6)", width=34,
                   command=self._launch_new_launcher).pack(side=tk.LEFT)
        ttk.Label(row,
                  text="Steam-style library view of every app below: search, "
                       "favourites, running-process tracking, and a live "
                       "environment status strip. This window (Tkinter) stays "
                       "as the zero-dependency fallback.",
                  foreground=PALETTE["text_dim"], wraplength=340,
                  justify=tk.LEFT).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Separator(outer).pack(fill=tk.X, pady=(8, 12))

        for label, script, description in _APPS:
            row = ttk.Frame(outer)
            row.pack(fill=tk.X, pady=4)
            btn = ttk.Button(row, text=label, width=34,
                              command=lambda s=script, l=label: self._launch(s, l))
            btn.pack(side=tk.LEFT)
            ttk.Label(row, text=description, foreground=PALETTE["text_dim"],
                      wraplength=340, justify=tk.LEFT).pack(side=tk.LEFT, padx=(10, 0))

        # ---- MSO Studio (PySide6 integrator) -------------------------
        ttk.Separator(outer).pack(fill=tk.X, pady=(12, 8))
        row = ttk.Frame(outer)
        row.pack(fill=tk.X, pady=4)
        ttk.Button(row, text="Open MSO Studio (PySide6)", width=34,
                   command=self._launch_mso_studio).pack(side=tk.LEFT)
        ttk.Label(row,
                  text="New unified GUI integrator (nominal sim, mechanism "
                       "comparison, sensitivity, optimization, LaTeX reports). "
                       "Its Tools page has PySR/curve fitting, the plot "
                       "digitizer, and Gemini-backed PDF Q&A/table extraction "
                       "(KRUNAL_JULY_23.md point 8 — these already exist here, "
                       "just not visible from this launcher window before now). "
                       "Runs in its own dedicated .venv-gui interpreter.",
                  foreground=PALETTE["text_dim"], wraplength=340,
                  justify=tk.LEFT).pack(side=tk.LEFT, padx=(10, 0))

        # ---- W9: Doctor / Recipes pane -------------------------------
        ttk.Separator(outer).pack(fill=tk.X, pady=(12, 8))
        row = ttk.Frame(outer)
        row.pack(fill=tk.X, pady=4)
        ttk.Button(row, text="Doctor / Recipes", width=34,
                   command=self._open_doctor).pack(side=tk.LEFT)
        ttk.Label(row,
                  text="Check the toolchain a task needs (with fixes for "
                       "anything missing) and look up which command covers "
                       "your task",
                  foreground=PALETTE["text_dim"], wraplength=340,
                  justify=tk.LEFT).pack(side=tk.LEFT, padx=(10, 0))

    # ------------------------------------------------------------------
    # W9 — Doctor / Recipes window
    # ------------------------------------------------------------------
    def _open_doctor(self) -> None:
        try:
            from rmip.config.preflight import TASKS
            from rmip.config.recipes import RECIPES, find_recipes, render_recipes
        except Exception as e:
            messagebox.showerror("Unavailable",
                                 f"Could not import rmip.config: {e}")
            return

        win = tk.Toplevel(self.root)
        win.title("Doctor / Recipes")
        win.geometry("760x520")
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ---- Doctor tab ----
        doc = ttk.Frame(nb, padding=8)
        nb.add(doc, text="Doctor — toolchain preflight")
        bar = ttk.Frame(doc)
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="Task:").pack(side=tk.LEFT)
        task_var = tk.StringVar(value="all")
        ttk.Combobox(bar, textvariable=task_var, state="readonly",
                     values=sorted(TASKS), width=14).pack(side=tk.LEFT, padx=6)
        doc_out = tk.Text(doc, wrap=tk.WORD, font=FONTS.get("mono", ("Courier", 9)))
        style_text_widget(doc_out)
        doc_out.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        def _run_doctor():
            doc_out.delete("1.0", tk.END)
            doc_out.insert(tk.END, f"Checking prerequisites for task "
                                   f"'{task_var.get()}' …\n")
            doc_out.update_idletasks()

            def worker():
                from rmip.config.preflight import check_environment
                try:
                    text = check_environment(task=task_var.get()).to_text()
                except Exception as exc:                   # noqa: BLE001
                    text = f"doctor failed: {exc}"
                doc_out.after(0, lambda: (doc_out.delete("1.0", tk.END),
                                          doc_out.insert(tk.END, text)))

            import threading
            threading.Thread(target=worker, daemon=True).start()

        ttk.Button(bar, text="Run doctor", command=_run_doctor
                   ).pack(side=tk.LEFT, padx=6)

        # ---- Recipes tab ----
        rec = ttk.Frame(nb, padding=8)
        nb.add(rec, text="Recipes — how do I…?")
        rbar = ttk.Frame(rec)
        rbar.pack(fill=tk.X)
        query_var = tk.StringVar()
        entry = ttk.Entry(rbar, textvariable=query_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        rec_out = tk.Text(rec, wrap=tk.WORD, font=FONTS.get("mono", ("Courier", 9)))
        style_text_widget(rec_out)
        rec_out.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        def _search(*_):
            q = query_var.get().strip()
            rec_out.delete("1.0", tk.END)
            if q:
                rec_out.insert(tk.END, render_recipes(find_recipes(q), query=q))
            else:
                rec_out.insert(tk.END, render_recipes(RECIPES))

        ttk.Button(rbar, text="Find command", command=_search
                   ).pack(side=tk.LEFT, padx=6)
        ttk.Button(rbar, text="Show all", command=lambda: (
            query_var.set(""), _search())).pack(side=tk.LEFT)
        entry.bind("<Return>", _search)
        _search()   # pre-fill with the full recipe list

    def _launch_new_launcher(self) -> None:
        # Same cross-interpreter pattern as _launch_mso_studio below: the new
        # launcher needs PySide6, which lives only in .venv-gui.
        venv_python = _ROOT / ".venv-gui" / "bin" / "python"
        script_path = _ROOT / "launcher_qt.py"
        if not venv_python.exists():
            messagebox.showerror(
                "GUI venv not set up",
                "The new launcher's dedicated virtual environment doesn't exist yet.\n\n"
                "Run this once from a terminal:\n"
                "    ./scripts/setup_gui_venv.sh",
            )
            return
        try:
            subprocess.Popen([str(venv_python), str(script_path)])
        except Exception as e:
            messagebox.showerror("Launch failed", f"Could not launch the new launcher:\n{e}")

    def _launch(self, script: str, label: str) -> None:
        script_path = _ROOT / script
        if not script_path.exists():
            messagebox.showerror("Not found", f"{script} not found at {script_path}")
            return
        try:
            subprocess.Popen([sys.executable, str(script_path)])
        except Exception as e:
            messagebox.showerror("Launch failed", f"Could not launch {label}:\n{e}")

    def _launch_mso_studio(self) -> None:
        # MSO Studio needs PySide6, which is deliberately NOT installed in
        # this (anaconda) interpreter -- see the env-isolation policy in
        # project memory. It runs in its own .venv-gui, so this launches a
        # different interpreter than every other button above.
        venv_python = _ROOT / ".venv-gui" / "bin" / "python"
        script_path = _ROOT / "run_mso_studio.py"
        if not venv_python.exists():
            messagebox.showerror(
                "GUI venv not set up",
                "MSO Studio's dedicated virtual environment doesn't exist yet.\n\n"
                "Run this once from a terminal:\n"
                "    ./scripts/setup_gui_venv.sh",
            )
            return
        try:
            subprocess.Popen([str(venv_python), str(script_path)])
        except Exception as e:
            messagebox.showerror("Launch failed", f"Could not launch MSO Studio:\n{e}")


def main() -> int:
    if not _HAS_TK:
        print("tkinter not available -- cannot show the launcher window.")
        for label, script, description in _APPS:
            print(f"  {label:45s} python3 {script}")
        return 0

    root = tk.Tk()
    apply_theme(root)
    LauncherApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
