"""
Tests for rmip_suite_gui.py (Phase 4 of the GUI-separation split -- the
umbrella app: Graph Comparison, Mechanism Reduction, Global Sensitivity
Analysis, Active Parameter Selection).

Covers the pure command-assembly logic each tab's _build_command()
implements, without needing a live Tk root -- constructs the same
tk.StringVar-backed objects a real tab would and checks the resulting CLI
argv list. This is the part most likely to silently drift from the real
CLI's argument names (rmip_cli.py's reduce/gsa-run/compare-graph), so it's
worth testing precisely.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_rmip_suite_gui.py -v
"""
import os
import subprocess
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))

import tkinter as tk
from tkinter import ttk

import rmip_suite_gui as app


@pytest.fixture
def tk_root():
    root = tk.Tk()
    yield root
    root.destroy()


class TestNoGuiSmoke:
    def test_no_db_given(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "rmip_suite_gui.py"), "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "No --db given" in proc.stdout

    def test_reports_db_existence(self):
        db = os.path.join(_ROOT, "outputs", "project.db")
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "rmip_suite_gui.py"), "--db", db, "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "exists=" in proc.stdout


class TestGraphComparisonTabCommand:
    def test_build_command(self, tk_root):
        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="project.db")
        tab = app.GraphComparisonTab(nb, "Graph Comparison", db_var)
        tab.mech_ids_var.set("1,2,3")

        cmd = tab._build_command()
        assert cmd[0] == sys.executable
        assert "compare-graph" in cmd
        assert "--mechs" in cmd
        idx = cmd.index("--mechs")
        assert cmd[idx + 1:idx + 4] == ["1", "2", "3"]
        assert "--db" in cmd and "project.db" in cmd

    def test_missing_mech_ids_raises(self, tk_root):
        from tkinter import ttk
        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="project.db")
        tab = app.GraphComparisonTab(nb, "Graph Comparison", db_var)
        with pytest.raises(ValueError):
            tab._build_command()

    def test_missing_db_raises(self, tk_root):
        from tkinter import ttk
        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="")
        tab = app.GraphComparisonTab(nb, "Graph Comparison", db_var)
        tab.mech_ids_var.set("1,2")
        with pytest.raises(ValueError):
            tab._build_command()


class TestGraphComparisonViewer:
    """KRUNAL_JULY_23.md point 7 -- compare-graph wrote JSON but never gave
    a way to actually view the comparison graph. Covers the GUI-side
    "Launch graph viewer" button: it must append --serve/--port/--label to
    the same command _build_command() assembles, and surface a clickable
    localhost link."""

    def test_launch_viewer_appends_serve_flags(self, tk_root):
        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="project.db")
        tab = app.GraphComparisonTab(nb, "Graph Comparison", db_var)
        tab.mech_ids_var.set("2,3,4")
        tab.viewer_port_var.set("8099")
        tab.viewer_label_var.set("id")

        captured = []
        tab.terminal.run = lambda cmd, cwd=None: captured.append(cmd)
        tab.frame.after = lambda *a, **k: None  # don't actually schedule
        tab._launch_viewer()

        assert len(captured) == 1
        cmd = captured[0]
        assert cmd[-6:] == ["--serve", "--port", "8099", "--label", "id"][-6:] or (
            "--serve" in cmd and "--port" in cmd and "8099" in cmd
            and "--label" in cmd and "id" in cmd
        )
        assert "compare-graph" in cmd

    def test_launch_viewer_sets_clickable_link_text(self, tk_root):
        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="project.db")
        tab = app.GraphComparisonTab(nb, "Graph Comparison", db_var)
        tab.mech_ids_var.set("2,3")
        tab.viewer_port_var.set("8123")
        tab.terminal.run = lambda cmd, cwd=None: None
        tab.frame.after = lambda *a, **k: None
        tab._launch_viewer()
        assert "http://localhost:8123" in tab._link_label.cget("text")

    def test_open_link_opens_browser(self, tk_root, monkeypatch):
        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="project.db")
        tab = app.GraphComparisonTab(nb, "Graph Comparison", db_var)
        tab._pending_url = "http://localhost:8050"
        opened = []
        import webbrowser
        monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url))
        tab._open_link()
        assert opened == ["http://localhost:8050"]

    def test_launch_viewer_invalid_input_shows_no_run(self, tk_root, monkeypatch):
        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="")   # missing db -> _build_command raises
        tab = app.GraphComparisonTab(nb, "Graph Comparison", db_var)
        tab.mech_ids_var.set("1,2")
        monkeypatch.setattr(app.messagebox, "showerror", lambda *a, **k: None)
        captured = []
        tab.terminal.run = lambda cmd, cwd=None: captured.append(cmd)
        tab._launch_viewer()
        assert captured == []


class TestReductionTabCommand:
    def test_build_command(self, tk_root):
        from tkinter import ttk
        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="project.db")
        tab = app.ReductionTab(nb, "Mechanism Reduction", db_var)
        tab.mech_id_var.set("8")
        tab.target_var.set("H2,O2,H2O")
        tab.method_var.set("DRGEP")

        cmd = tab._build_command()
        assert "reduce" in cmd
        assert "8" in cmd
        assert "--method" in cmd
        assert cmd[cmd.index("--method") + 1] == "DRGEP"
        assert "--target" in cmd
        assert cmd[cmd.index("--target") + 1] == "H2,O2,H2O"

    def test_missing_target_raises(self, tk_root):
        from tkinter import ttk
        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="project.db")
        tab = app.ReductionTab(nb, "Mechanism Reduction", db_var)
        tab.mech_id_var.set("8")
        with pytest.raises(ValueError):
            tab._build_command()


class TestGSATabCommand:
    def test_build_command(self, tk_root):
        from tkinter import ttk
        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="project.db")
        tab = app.GSATab(nb, "Global Sensitivity Analysis", db_var)
        tab.mech_id_var.set("8")
        tab.fuel_var.set("H2:1.0")

        cmd = tab._build_command()
        assert "gsa-run" in cmd
        assert "8" in cmd
        assert "--fuel" in cmd
        assert cmd[cmd.index("--fuel") + 1] == "H2:1.0"
        assert "--zerork-install-prefix" in cmd

    def test_missing_fuel_raises(self, tk_root):
        from tkinter import ttk
        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="project.db")
        tab = app.GSATab(nb, "Global Sensitivity Analysis", db_var)
        tab.mech_id_var.set("8")
        with pytest.raises(ValueError):
            tab._build_command()


class TestActiveParamSelectionTabCommand:
    def test_build_command_minimal(self, tk_root):
        from tkinter import ttk
        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="")  # this tab doesn't use the shared DB
        tab = app.ActiveParamSelectionTab(nb, "Active Parameter Selection", db_var)
        tab.mechanism_var.set("mech.yaml")

        cmd = tab._build_command()
        assert cmd[1].endswith("ActiveParameterScreen.py")
        assert "--mechanism" in cmd
        assert cmd[cmd.index("--mechanism") + 1] == "mech.yaml"
        assert "--generate-xml" not in cmd  # not requested

    def test_generate_xml_requires_classification_file(self, tk_root):
        from tkinter import ttk
        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="")
        tab = app.ActiveParamSelectionTab(nb, "Active Parameter Selection", db_var)
        tab.mechanism_var.set("mech.yaml")
        tab.generate_xml_var.set(True)
        with pytest.raises(ValueError):
            tab._build_command()

    def test_generate_xml_with_classification_file(self, tk_root):
        from tkinter import ttk
        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="")
        tab = app.ActiveParamSelectionTab(nb, "Active Parameter Selection", db_var)
        tab.mechanism_var.set("mech.yaml")
        tab.generate_xml_var.set(True)
        tab.classification_file_var.set("classes.csv")

        cmd = tab._build_command()
        assert "--generate-xml" in cmd
        assert "--classification-file" in cmd
        assert cmd[cmd.index("--classification-file") + 1] == "classes.csv"
