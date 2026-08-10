"""
Tests for nominal_sim_gui.py (Phase 2 of the GUI-separation split).

Headless surface only -- see test_brute_force_sa_gui.py's module docstring
for why the Tk UI itself isn't repeated here as an automated test.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_nominal_sim_gui.py -v
"""
import os
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))

import nominal_sim_gui as app


class TestNoGuiSmoke:
    def test_no_config_given(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "nominal_sim_gui.py"), "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "No config given" in proc.stdout

    def test_loads_real_template_and_lists_run_labels(self):
        template = os.path.join(_ROOT, "src", "mso_compare", "template_nominal_only.yaml")
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "nominal_sim_gui.py"),
             template, "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "nominal_htc" in proc.stdout
        assert "nominal_ltc" in proc.stdout

    def test_config_flag_equivalent_to_positional(self):
        template = os.path.join(_ROOT, "src", "mso_compare", "template_nominal_only.yaml")
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "nominal_sim_gui.py"),
             "--config", template, "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "nominal_htc" in proc.stdout


class TestRunSimSubprocessSpawn:
    """B14 regression: `_run_sim()` used to launch run_nominal_sim.py as a
    bare script (`[sys.executable, ".../run_nominal_sim.py", ...]`) with no
    cwd/PYTHONPATH set. That script's own sys.path bootstrap is itself wrong
    for this repo's layout (`_SCRIPTS_DIR.parent / "src"` resolves to the
    nonexistent src/src when the script already lives in src/mso_compare/)
    -- every real Run click died instantly with ModuleNotFoundError. The
    `--no-gui` tests above only exercise the in-process argument-parsing
    path and can't catch this.

    Naively fixing it with `-m mso_compare.run_nominal_sim` + cwd/PYTHONPATH
    pointed at src/ trades one crash for a worse one: src/io/ is a real
    legacy package that then shadows the stdlib `io` module the interpreter
    needs during its own startup, so the child dies with "Fatal Python
    error: init_sys_streams" before any of this repo's code even runs. This
    test drives the actual fix -- `_run_sim()` bootstraps via `-c` + runpy
    so the sys.path insert happens *after* interpreter init."""

    def test_bootstrap_invocation_succeeds(self):
        import nominal_sim_gui as _app
        template = os.path.join(_ROOT, "src", "mso_compare", "template_nominal_only.yaml")
        bootstrap = (
            "import sys, runpy; "
            f"sys.path.insert(0, {str(_app._REPO / 'src')!r}); "
            "runpy.run_module('mso_compare.run_nominal_sim', run_name='__main__')"
        )
        proc = subprocess.run(
            [sys.executable, "-c", bootstrap,
             "--config", template, "--run", "nominal_htc", "--dry-run"],
            capture_output=True, text=True, timeout=30,
        )
        assert "ModuleNotFoundError" not in proc.stderr
        assert "Fatal Python error" not in proc.stderr
        assert proc.returncode == 0, proc.stderr


class TestLoadRunLabels:
    def test_load_run_labels_returns_list(self):
        template = os.path.join(_ROOT, "src", "mso_compare", "template_nominal_only.yaml")
        labels = app._load_run_labels(template)
        assert labels == ["nominal_htc", "nominal_ltc"]
