"""
Tests for launcher_gui.py (Phase 6, optional, of the GUI-separation split).

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_launcher_gui.py -v
"""
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import launcher_gui as app


class TestAppRegistry:
    def test_every_listed_script_exists(self):
        for label, script, description in app._APPS:
            path = os.path.join(_ROOT, script)
            assert os.path.exists(path), f"{label} points at missing script {script}"

    def test_uncertainty_generator_now_listed(self):
        """Phase 5 was blocked on a formula confirmation (now resolved,
        2026-07-12) -- confirms it was added once actually built, per this
        file's module docstring history in launcher_gui.py."""
        labels = [label for label, _, _ in app._APPS]
        assert any("uncertainty" in l.lower() for l in labels)

    def test_all_apps_listed(self):
        # 7 from the 2026-07-12 GUI split + mechanism_converter_gui (2026-07-13)
        # + mechanism_check_gui + idt_sensitivity_gui (2026-07-2x)
        # + generate_target_opt.py (KRUNAL_JULY_23.md point 8, 2026-07-28) = 11.
        # + Mechanism Reduction (Session A5 -- _APPS is now generated from
        #   mso_studio.launcher.catalog.CATALOG's RUNNER_SCIENCE entries, so
        #   adding a catalog entry adds a button here automatically) = 12.
        # Assert on labels (not just a bare count) so this degrades gracefully
        # the next time an app is added.
        labels = [label for label, _, _ in app._APPS]
        assert len(app._APPS) == 12
        for expected in (
            "Mechanism Health-Check",
            "Ignition-Delay Sensitivity",
            "CHEMKIN Mechanism Converter",
            "Target/Add/Opt Generator (full toolkit)",
            "Mechanism Reduction",
        ):
            assert expected in labels, f"expected app {expected!r} not registered"


class TestLaunch:
    def test_launch_spawns_real_subprocess(self, tmp_path, monkeypatch):
        """Verifies _launch() actually calls subprocess.Popen with the
        right script path, using --no-gui on a real app so the spawned
        process exits immediately instead of opening a window."""
        import subprocess

        captured = {}
        real_popen = subprocess.Popen

        def _fake_popen(args, **kwargs):
            captured["args"] = args
            # Actually run it (with --no-gui) so we get real subprocess
            # behavior, not just a recorded call.
            return real_popen(args + ["--no-gui"], **kwargs)

        monkeypatch.setattr(subprocess, "Popen", _fake_popen)

        class _FakeRoot:
            pass

        launcher = app.LauncherApp.__new__(app.LauncherApp)
        launcher.root = _FakeRoot()
        launcher._launch("brute_force_sa_gui.py", "Brute-Force Sensitivity Analysis")

        assert "args" in captured
        assert captured["args"][0] == sys.executable
        assert captured["args"][1].endswith("brute_force_sa_gui.py")

        # Let the spawned --no-gui process finish and reap it.
        time.sleep(1)
