"""
Tests for mso_compare_gui.py (Phase 3 of the GUI-separation split).

Headless surface only -- see test_brute_force_sa_gui.py's module docstring
for why the Tk UI itself isn't repeated here as an automated test.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_mso_compare_gui.py -v
"""
import os
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import mso_compare_gui as app


class TestNoGuiSmoke:
    def test_no_config_given(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "mso_compare_gui.py"), "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "No config given" in proc.stdout

    def test_reports_config_existence(self):
        template = os.path.join(_ROOT, "src", "mso_compare", "template_nominal_only.yaml")
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "mso_compare_gui.py"), template, "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "exists=True" in proc.stdout

    def test_missing_config_reports_false(self, tmp_path):
        missing = str(tmp_path / "does_not_exist.yaml")
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "mso_compare_gui.py"), missing, "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "exists=False" in proc.stdout
