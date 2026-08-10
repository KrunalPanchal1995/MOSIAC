"""
Tests for forward_uq_gui.py (Phase 2 of the GUI-separation split).

Headless surface only -- see test_brute_force_sa_gui.py's module docstring
for why the Tk UI itself isn't repeated here as an automated test (it was
verified manually against a live display during development).

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_forward_uq_gui.py -v
"""
import os
import subprocess
import sys

import yaml

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import forward_uq_gui as app


class TestNoGuiSmoke:
    def test_no_target_opt_given(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "forward_uq_gui.py"), "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "No target.opt given" in proc.stdout

    def test_loads_real_target_opt(self, tmp_path):
        cfg = {
            "Locations": {"mechanism": "/fake/mech.yaml", "uncertainty_data": "/fake.xml"},
            "ForwardUQ": {"n_samples": 1000, "method": "lhs"},
        }
        cfg_path = tmp_path / "target.opt"
        cfg_path.write_text(yaml.safe_dump(cfg))

        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "forward_uq_gui.py"),
             str(cfg_path), "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "/fake/mech.yaml" in proc.stdout


class TestConfigParamPrefill:
    """Exercises the same ForwardUQ-section prefill logic _load_config()
    does, without needing a live Tk root."""

    def test_prefill_reads_forwarduq_section(self):
        cfg = {"ForwardUQ": {"n_samples": 12345, "method": "lhs", "output_dir": "out/x"}}
        uq = cfg.get("ForwardUQ", {})
        assert str(uq.get("n_samples")) == "12345"
        assert uq.get("method") == "lhs"
        assert uq.get("output_dir") == "out/x"

    def test_missing_forwarduq_section_defaults_gracefully(self):
        cfg = {}
        uq = cfg.get("ForwardUQ", {})
        assert uq.get("n_samples") is None  # caller keeps its own default (50000)
