"""
Tests for uncertainty_generator_gui.py (Phase 5 of the GUI-separation
split -- the one phase that was blocked pending KP's confirmation of the
exact symmetric-bound formula; confirmed 2026-07-12: for each reaction,
max(|kappa_max(T)-kappa_nom(T)|, |kappa_nom(T)-kappa_min(T)|) across all
anchor temperatures, applied symmetrically to ln(A) at the nominal
A-factor).

Covers compute_symmetric_bounds()/write_results_csv() directly against a
real mechanism (MECHANISM/FFCM1/FFCM1.yaml, already in this repo) and a
freshly-generated uncertainty XML (via generate_target_opt.py's
generate_uncertainty_xml(), the function this session found and fixed two
real bugs in -- missing `no`/`perturbation_type` attributes that crashed
Uncertainty.py's own reaction class on every previously-generated XML).

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_uncertainty_generator_gui.py -v
"""
import csv
import os
import subprocess
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import uncertainty_generator_gui as app
from generate_target_opt import generate_uncertainty_xml

_MECHANISM = os.path.join(_ROOT, "MECHANISM", "FFCM1", "FFCM1.yaml")
_needs_mechanism = pytest.mark.skipif(
    not os.path.exists(_MECHANISM), reason="MECHANISM/FFCM1/FFCM1.yaml not present"
)


def _write_xml(tmp_path, reactions):
    xml_path = str(tmp_path / "unsrt.xml")
    generate_uncertainty_xml(reactions, xml_path)
    return xml_path


class TestNoGuiSmoke:
    def test_no_args_given(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "uncertainty_generator_gui.py"), "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "No --xml/--mechanism given" in proc.stdout

    def test_reports_path_existence(self, tmp_path):
        xml_path = _write_xml(tmp_path, [{"name": "H + O2 <=> O + OH"}])
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "uncertainty_generator_gui.py"),
             "--xml", xml_path, "--mechanism", "/does/not/exist.yaml", "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "exists=True" in proc.stdout
        assert "exists=False" in proc.stdout


class TestGeneratedXMLHasRequiredAttributes:
    """Regression test for the two bugs found this session -- without
    these, Uncertainty.py's reaction.__init__ crashes immediately."""

    def test_no_attribute_present(self, tmp_path):
        import xml.etree.ElementTree as ET
        xml_path = _write_xml(tmp_path, [
            {"name": "H + O2 <=> O + OH"}, {"name": "O + H2 <=> H + OH"},
        ])
        root = ET.parse(xml_path).getroot()
        nos = [el.attrib["no"] for el in root.findall("reaction")]
        assert nos == ["1", "2"]

    def test_perturbation_type_present_and_defaults_to_arrhenius(self, tmp_path):
        import xml.etree.ElementTree as ET
        xml_path = _write_xml(tmp_path, [{"name": "H + O2 <=> O + OH"}])
        root = ET.parse(xml_path).getroot()
        el = root.find("reaction")
        ptype = el.find("perturbation_type")
        assert ptype is not None
        assert ptype.text == "arrhenius"

    def test_perturbation_type_override_respected(self, tmp_path):
        import xml.etree.ElementTree as ET
        xml_path = _write_xml(tmp_path, [
            {"name": "H + O2 <=> O + OH", "perturbation_type": "factor"},
        ])
        root = ET.parse(xml_path).getroot()
        el = root.find("reaction")
        assert el.find("perturbation_type").text == "factor"


@_needs_mechanism
class TestComputeSymmetricBounds:
    def test_real_reaction_produces_symmetric_bound(self, tmp_path):
        xml_path = _write_xml(tmp_path, [
            {"name": "H + O2 <=> O + OH", "type": "pressure_independent",
             "temperatures": "500.0,900.0,1300.0,1700.0,2100.0,2500.0",
             "uncertainties": "0.40,0.30,0.25,0.20,0.17,0.15"},
        ])
        results = app.compute_symmetric_bounds(xml_path, _MECHANISM)

        assert len(results) == 1
        r = results[0]
        assert "error" not in r
        assert r["A_nominal"] > 0
        assert r["factor"] > 1.0
        # Symmetric: A_lb = A_nominal/factor, A_ub = A_nominal*factor
        assert r["A_lb"] == pytest.approx(r["A_nominal"] / r["factor"], rel=1e-9)
        assert r["A_ub"] == pytest.approx(r["A_nominal"] * r["factor"], rel=1e-9)
        # Bounds must actually bracket the nominal, symmetrically in log-space
        import math
        log_span_up = math.log(r["A_ub"]) - math.log(r["A_nominal"])
        log_span_down = math.log(r["A_nominal"]) - math.log(r["A_lb"])
        assert log_span_up == pytest.approx(log_span_down, rel=1e-9)

    def test_unknown_reaction_reports_error_not_crash(self, tmp_path):
        xml_path = _write_xml(tmp_path, [
            {"name": "NOT + A <=> REAL + REACTION",
             "temperatures": "500.0,900.0,1300.0,1700.0,2100.0,2500.0",
             "uncertainties": "0.3,0.28,0.26,0.24,0.22,0.2"},
        ])
        results = app.compute_symmetric_bounds(xml_path, _MECHANISM)
        assert len(results) == 1
        assert "error" in results[0]

    def test_mixed_valid_and_invalid_reactions(self, tmp_path):
        xml_path = _write_xml(tmp_path, [
            {"name": "H + O2 <=> O + OH",
             "temperatures": "500.0,900.0,1300.0,1700.0,2100.0,2500.0",
             "uncertainties": "0.40,0.30,0.25,0.20,0.17,0.15"},
            {"name": "NOT + A <=> REAL + REACTION",
             "temperatures": "500.0,900.0,1300.0,1700.0,2100.0,2500.0",
             "uncertainties": "0.3,0.28,0.26,0.24,0.22,0.2"},
        ])
        results = app.compute_symmetric_bounds(xml_path, _MECHANISM)
        assert len(results) == 2
        assert "error" not in results[0]
        assert "error" in results[1]

    def test_write_results_csv(self, tmp_path):
        xml_path = _write_xml(tmp_path, [
            {"name": "H + O2 <=> O + OH",
             "temperatures": "500.0,900.0,1300.0,1700.0,2100.0,2500.0",
             "uncertainties": "0.40,0.30,0.25,0.20,0.17,0.15"},
        ])
        results = app.compute_symmetric_bounds(xml_path, _MECHANISM)
        out_csv = str(tmp_path / "bounds.csv")
        app.write_results_csv(results, out_csv)

        with open(out_csv) as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 1
        assert rows[0]["reaction"] == "H + O2 <=> O + OH"
        assert float(rows[0]["factor"]) > 1.0


def _real_display_env():
    return bool(os.environ.get("DISPLAY"))


@pytest.mark.skipif(not _real_display_env(), reason="needs a real X display")
class TestSaTabLiveTk:
    """KRUNAL_JULY_23.md point 5 -- the new "From SA data
    (ActiveParameterScreen)" primary tab. Real (withdrawn) tk.Tk() root,
    same convention as src/rmip/tests/test_gui_stress_sweep.py."""

    @pytest.fixture
    def app_and_root(self, monkeypatch):
        # gui_common.settings persists to the real repo's .gui_settings/*.json
        # -- redirect both the read (__init__'s load_settings) and every
        # write (_load_sa_demo/_browse_* don't call it, but be defensive)
        # so tests never pollute real on-disk GUI state.
        monkeypatch.setattr(app, "load_settings", lambda name: {})
        monkeypatch.setattr(app, "save_settings", lambda name, data: None)
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        gui = app.UncertaintyGeneratorApp(root)
        yield gui, root
        root.destroy()

    def test_window_title_renamed(self, app_and_root):
        gui, root = app_and_root
        assert root.title() == "Uncertainty Quantification and File Generator"

    def test_load_demo_populates_fields(self, app_and_root):
        gui, root = app_and_root
        gui._load_sa_demo()
        assert gui._sa_vars["mechanism"].get() == app._DEMO["mechanism"]
        assert gui._sa_vars["fuel"].get() == "MB_MB2D_LALIT_2024"
        assert gui._sa_check_vars["generate_xml"].get() is True
        assert gui._sa_check_vars["generate_plots"].get() is True
        assert gui._sa_check_vars["generate_latex"].get() is True

    def test_demo_paths_exist_in_this_checkout(self, app_and_root):
        gui, root = app_and_root
        gui._load_sa_demo()
        assert os.path.isdir(gui._sa_vars["sens_dir"].get())
        assert os.path.isfile(gui._sa_vars["mechanism"].get())
        assert os.path.isfile(gui._sa_vars["classification_file"].get())

    def test_build_sa_command_matches_real_clt_invocation(self, app_and_root):
        gui, root = app_and_root
        gui._load_sa_demo()
        cmd = gui._build_sa_command()
        assert cmd[0] == sys.executable
        assert cmd[1] == app._ACTIVE_PARAM_SCRIPT
        for flag, value in (("--sens-dir", app._DEMO["sens_dir"]),
                             ("--mechanism", app._DEMO["mechanism"]),
                             ("--threshold", "0.05"), ("--carbon", "5"),
                             ("--fuel", "MB_MB2D_LALIT_2024")):
            assert flag in cmd
            assert cmd[cmd.index(flag) + 1] == value
        assert "--generate-xml" in cmd
        assert "--generate-plots" in cmd
        assert "--generate-latex" in cmd
        assert "--compare-temperatures" in cmd
        idx = cmd.index("--compare-temperatures")
        assert cmd[idx + 1:idx + 4] == ["698", "908", "1287"]

    def test_missing_mechanism_raises(self, app_and_root):
        gui, root = app_and_root
        gui._sa_vars["mechanism"].set("")
        with pytest.raises(ValueError, match="[Mm]echanism"):
            gui._build_sa_command()

    def test_xml_without_classification_file_raises(self, app_and_root):
        gui, root = app_and_root
        gui._sa_vars["mechanism"].set("mech.yaml")
        gui._sa_check_vars["generate_xml"].set(True)
        gui._sa_vars["classification_file"].set("")
        with pytest.raises(ValueError, match="classification"):
            gui._build_sa_command()

    def test_run_sa_screen_launches_terminal_with_built_command(self, app_and_root):
        gui, root = app_and_root
        gui._load_sa_demo()
        captured = []
        gui._sa_terminal.run = lambda cmd, cwd=None: captured.append(cmd)
        gui._run_sa_screen()
        assert len(captured) == 1
        assert captured[0] == gui._build_sa_command()

    def test_manual_and_bounds_tabs_still_present(self, app_and_root):
        """The rework must not drop the pre-existing manual-entry / bounds
        tabs -- KRUNAL_JULY_23.md point 5 asked to keep them as secondary
        tabs, not remove them."""
        gui, root = app_and_root
        assert hasattr(gui, "_gen_tree")   # manual XML entry
        assert hasattr(gui, "_tree")       # bounds results table
