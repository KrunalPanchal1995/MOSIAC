"""
Tests for KRUNAL_JULY_23.md point 1's rollout onto the remaining Tkinter
apps (beyond the 3 -- converter/health-check/fusion -- already covered by
their own dedicated test suites). Real tk.Tk() root, no synthetic clicks --
same convention as test_gui_stress_sweep.py's widget-construction checks.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_point1_rollout.py -v
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))


@pytest.fixture
def tk_root():
    tk = pytest.importorskip("tkinter")
    root = tk.Tk()
    yield root
    root.destroy()


class TestBruteForceSA:
    def test_build_run_status(self, tk_root):
        import brute_force_sa_gui as gui
        app = gui.BruteForceSAApp(tk_root)
        app._cfg = {"Locations": {"mechanism": "/m.yaml", "targets": "/t.target"},
                    "Stats": {"SA_scheme": "central"}}
        app._cfg_path_var.set("/target.opt")
        app._out_dir_var.set("/out")
        report = app._build_run_status()
        assert report.tool == "Brute-Force Sensitivity Analysis"
        assert report.inputs["mechanism (Locations.mechanism)"] == "/m.yaml"
        assert report.output_dir == "/out"
        assert report.options["SA scheme"] == "central"


class TestNominalSim:
    def test_build_run_status_before_load(self, tk_root):
        import nominal_sim_gui as gui
        app = gui.NominalSimApp(tk_root)
        app._cfg_path_var.set("/does/not/exist.yaml")
        app._run_label_var.set("nominal_htc")
        report = app._build_run_status()
        assert report.tool == "Nominal Simulation (mso_compare)"
        assert report.inputs["pipeline config"] == "/does/not/exist.yaml"
        assert report.options["run label"] == "nominal_htc"
        # config doesn't exist -> output_dir lookup fails gracefully, not raise
        assert report.output_dir is None


class TestForwardUQ:
    def test_build_run_status(self, tk_root):
        import forward_uq_gui as gui
        app = gui.ForwardUQApp(tk_root)
        app._cfg = {"Locations": {"mechanism": "/m.yaml", "uncertainty_data": "/u.xml"}}
        app._cfg_path_var.set("/target.opt")
        app._n_samples_var.set("1000")
        report = app._build_run_status()
        assert report.tool == "Forward Uncertainty Quantification"
        assert report.inputs["mechanism"] == "/m.yaml"
        assert report.options["n_samples"] == "1000"


class TestMSOCompare:
    def test_build_run_status(self, tk_root):
        import mso_compare_gui as gui
        app = gui.MSOCompareApp(tk_root)
        app._cfg_path_var.set("/config.yaml")
        app._regime_var.set("htc")
        app._skip_plots_var.set(True)
        report = app._build_run_status()
        assert report.tool == "MSO Compare"
        assert report.inputs["pipeline config"] == "/config.yaml"
        assert report.options["regime"] == "htc"
        assert report.options["skip plots"] is True


class TestUncertaintyGenerator:
    def test_build_run_status_before_any_run(self, tk_root):
        import uncertainty_generator_gui as gui
        app = gui.UncertaintyGeneratorApp(tk_root)
        app._xml_var.set("/u.xml")
        app._mech_var.set("/m.yaml")
        report = app._build_run_status()
        assert report.tool == "Uncertainty Generator"
        assert report.inputs["uncertainty XML"] == "/u.xml"
        assert report.status == "unknown"

    def test_build_run_status_after_done_with_results(self, tk_root):
        import uncertainty_generator_gui as gui
        app = gui.UncertaintyGeneratorApp(tk_root)
        app._on_done([
            {"rxn": "H+O2<=>O+OH", "A_nominal": 1e14, "factor": 1.5, "A_lb": 1e13, "A_ub": 1e15},
            {"rxn": "BAD+X<=>Y", "error": "no thermo"},
        ])
        report = app._build_run_status()
        assert report.status == "failed"          # one of the two rows errored
        assert "H+O2<=>O+OH" in report.log
        assert "no thermo" in report.log


class TestIdtSensitivity:
    def test_build_run_status_before_any_run(self, tk_root):
        import idt_sensitivity_gui as gui
        app = gui.IdtSensitivityApp(tk_root)
        app.v["mech"].set("/m.yaml")
        app.choice["method"].set("brute")
        report = app._build_run_status()
        assert report.tool == "Ignition-Delay Sensitivity"
        assert report.inputs["mechanism (.yaml)"] == "/m.yaml"
        assert report.options["method"] == "brute"
        assert report.status == "unknown"

    def test_build_run_status_after_error(self, tk_root):
        import idt_sensitivity_gui as gui
        app = gui.IdtSensitivityApp(tk_root)
        app._last_error = "mechanism file not found"
        report = app._build_run_status()
        assert report.status == "failed"
        assert report.summary == "mechanism file not found"


class TestRmipSuite:
    """One representative tab (GraphComparisonTab) -- the export button and
    _build_run_status live on the shared _TerminalTab base class, so every
    other tab (Reduction/GSA/ActiveParamSelection/TargetBuilder/ReSpecTh)
    gets the identical behavior for free."""

    def test_build_run_status_reflects_last_built_command(self, tk_root):
        import tkinter as tk
        from tkinter import ttk
        import rmip_suite_gui as gui

        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="/project.db")
        tab = gui.GraphComparisonTab(nb, "Graph Comparison", db_var)
        tab.mech_ids_var.set("2,3,4")
        tab.out_dir_var.set("/out/graph_cmp")

        report = tab._build_run_status()
        assert report.tool == "RMIP Suite — Graph Comparison"
        assert report.inputs["RMIP database"] == "/project.db"
        assert report.output_dir == "/out/graph_cmp"
        assert "compare-graph" in report.options["command"]
        assert "2,3,4" not in report.options["command"]  # split into separate argv tokens
        assert "2" in report.options["command"] and "4" in report.options["command"]

    def test_build_run_status_handles_invalid_input_gracefully(self, tk_root):
        """_build_command() raises ValueError when required fields are
        missing -- _build_run_status must not propagate that, just show an
        empty options dict."""
        import tkinter as tk
        from tkinter import ttk
        import rmip_suite_gui as gui

        nb = ttk.Notebook(tk_root)
        db_var = tk.StringVar(value="")
        tab = gui.GraphComparisonTab(nb, "Graph Comparison", db_var)
        report = tab._build_run_status()
        assert report.options == {}
