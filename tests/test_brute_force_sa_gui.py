"""
Tests for brute_force_sa_gui.py (Phase 1 pilot of the GUI-separation split).

Covers the headless/non-Tk-dependent surface: argument parsing and the
--no-gui config-loading path. The actual Tk UI was verified manually (see
this file's module docstring in brute_force_sa_gui.py) -- a real display
was used to build/load the window and exercise PtyTerminal end-to-end
during development, not repeated here as an automated test since it needs
a live X display.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_brute_force_sa_gui.py -v
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import brute_force_sa_gui as app


class TestNoGuiSmoke:
    def test_no_target_opt_given(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "brute_force_sa_gui.py"), "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "No target.opt given" in proc.stdout

    def test_loads_real_target_opt(self, tmp_path):
        cfg = {
            "Locations": {"mechanism": "/fake/mech.yaml", "targets": "/fake.target",
                           "addendum": "/fake.add"},
            "Stats": {"SA_scheme": "central_difference"},
        }
        cfg_path = tmp_path / "target.opt"
        cfg_path.write_text(yaml.safe_dump(cfg))

        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "brute_force_sa_gui.py"),
             str(cfg_path), "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "/fake/mech.yaml" in proc.stdout

    def test_target_opt_flag_equivalent_to_positional(self, tmp_path):
        cfg = {"Locations": {"mechanism": "/flagged/mech.yaml"}}
        cfg_path = tmp_path / "target.opt"
        cfg_path.write_text(yaml.safe_dump(cfg))

        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "brute_force_sa_gui.py"),
             "--target-opt", str(cfg_path), "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "/flagged/mech.yaml" in proc.stdout


class TestRunSAConfigAssembly:
    """Exercises the same config-mutation logic _run_sa() does (mechanism
    override merge), without needing a live Tk root -- constructs the dict
    the same way and checks the override rule."""

    def test_mechanism_override_replaces_locations_mechanism(self):
        base_cfg = {"Locations": {"mechanism": "/original.yaml", "targets": "/t.target"}}
        cfg = dict(base_cfg)
        override = "/overridden.yaml"
        if override:
            cfg.setdefault("Locations", {})["mechanism"] = override
        assert cfg["Locations"]["mechanism"] == "/overridden.yaml"
        assert cfg["Locations"]["targets"] == "/t.target"  # untouched

    def test_no_override_keeps_original_mechanism(self):
        base_cfg = {"Locations": {"mechanism": "/original.yaml"}}
        cfg = dict(base_cfg)
        override = ""
        if override:
            cfg.setdefault("Locations", {})["mechanism"] = override
        assert cfg["Locations"]["mechanism"] == "/original.yaml"

    def test_deepcopy_override_does_not_mutate_source_cfg(self):
        """B27/M27 regression: `_run_sa()` used `dict(self._cfg)` (shallow
        copy) before mutating `cfg["Locations"]["mechanism"]`. Because the
        nested "Locations" dict object is shared between the shallow copy
        and self._cfg, one override "Run SA" click permanently poisoned
        self._cfg -- the override became sticky even after the override
        field was cleared. copy.deepcopy fixes this."""
        import copy
        base_cfg = {"Locations": {"mechanism": "/original.yaml"}}
        cfg = copy.deepcopy(base_cfg)
        cfg.setdefault("Locations", {})["mechanism"] = "/overridden.yaml"
        assert cfg["Locations"]["mechanism"] == "/overridden.yaml"
        assert base_cfg["Locations"]["mechanism"] == "/original.yaml"  # untouched


class TestRunSAPathResolution:
    """B12 regression: `_run_sa()` wrote target.opt to a *relative* out_dir
    and then passed that same relative path as argv while also setting
    cwd=out_dir -- the child process resolved it against its own cwd a
    second time (outputs/sa/outputs/sa/target.opt), so "Run SA" always
    crashed with defaults. The fix resolves out_dir to an absolute path
    before building either the file path or argv."""

    def test_relative_out_dir_resolves_to_absolute_target_opt(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        out_dir = "outputs/sa"
        out = Path(out_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        target_opt_path = out / "target.opt"
        assert target_opt_path.is_absolute()
        assert str(target_opt_path) == str(tmp_path / "outputs" / "sa" / "target.opt")
        # cwd=out plus an absolute argv must never double up "outputs/sa".
        assert str(target_opt_path).count("outputs/sa") == 1


def _real_dark_env():
    """Skip the live-Tk suite below when no X display is reachable."""
    return bool(os.environ.get("DISPLAY"))


@pytest.mark.skipif(not _real_dark_env(), reason="needs a real X display")
class TestTargetsTabLiveTk:
    """KRUNAL_JULY_23.md point 4 -- Targets/Manual-entry/Plot-style tabs.
    Uses a real (withdrawn) tk.Tk() root, same convention as
    src/rmip/tests/test_gui_stress_sweep.py, not synthetic-event driven."""

    @pytest.fixture
    def app_and_root(self, tmp_path, monkeypatch):
        # gui_common.settings persists to the real repo's .gui_settings/*.json
        # (see .gui_settings/brute_force_sa.json) -- redirect both the read
        # (app.load_settings, called in __init__) and every write this test
        # triggers (app.save_settings, called from _load_config) at a tmp
        # path so tests never pollute real on-disk GUI state.
        monkeypatch.setattr(app, "load_settings", lambda name: {})
        monkeypatch.setattr(app, "save_settings", lambda name, data: None)
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        gui = app.BruteForceSAApp(root)
        yield gui, root
        root.destroy()

    def _write_target_opt(self, tmp_path, targets_path, addendum_path):
        cfg = {
            "Locations": {"mechanism": "/fake/mech.yaml",
                           "targets": str(targets_path),
                           "addendum": str(addendum_path)},
            "Stats": {"SA_scheme": "central_difference"},
        }
        cfg_path = tmp_path / "target.opt"
        cfg_path.write_text(yaml.safe_dump(cfg))
        return cfg_path

    def test_loads_and_previews_real_target_file(self, tmp_path, app_and_root):
        gui, root = app_and_root
        target_path = tmp_path / "t.target"
        target_path.write_text(
            "1 |a| target -- Tig| simulation -- Isochor Homo Reactor| "
            "T -- 900| P -- 1| species -- OH\n"
        )
        add_path = tmp_path / "t.add"
        add_path.write_text(yaml.safe_dump({"a": {"solver": "cantera"}}))
        cfg_path = self._write_target_opt(tmp_path, target_path, add_path)

        gui._load_config(str(cfg_path))
        assert len(gui._targets) == 1
        assert gui._targets[0].dataset_id == "a"
        assert gui._targets[0].runnable is True
        assert len(gui._tree.get_children()) == 1

    def test_gates_zerork_solver_case_in_tree(self, tmp_path, app_and_root):
        gui, root = app_and_root
        target_path = tmp_path / "t.target"
        target_path.write_text("1 |zk| target -- Tig| T -- 900| P -- 1\n")
        add_path = tmp_path / "t.add"
        add_path.write_text(yaml.safe_dump({"zk": {"solver": "zerork"}}))
        cfg_path = self._write_target_opt(tmp_path, target_path, add_path)

        gui._load_config(str(cfg_path))
        assert gui._targets[0].runnable is False
        assert "not runnable" in gui._gate_label.cget("text")
        iid = gui._tree.get_children()[0]
        assert "blocked" in gui._tree.item(iid, "tags")

    def test_selecting_row_populates_add_option_form(self, tmp_path, app_and_root):
        gui, root = app_and_root
        target_path = tmp_path / "t.target"
        target_path.write_text("1 |a| target -- Tig| T -- 900| P -- 1\n")
        add_path = tmp_path / "t.add"
        add_path.write_text(yaml.safe_dump({"a": {"solver": "cantera", "ign_cond": "max"}}))
        cfg_path = self._write_target_opt(tmp_path, target_path, add_path)
        gui._load_config(str(cfg_path))

        iid = gui._tree.get_children()[0]
        gui._tree.selection_set(iid)
        gui._on_target_select()
        assert gui._current_target_id == "a"
        assert "ign_cond" in gui._field_vars
        assert gui._field_vars["ign_cond"].get() == "max"

        gui._field_vars["ign_cond"].set("onset")
        gui._apply_case_edits()
        assert gui._add_data["a"]["ign_cond"] == "onset"

    def test_manual_case_appends_and_merges_into_tree(self, tmp_path, app_and_root):
        gui, root = app_and_root
        gui._out_dir_var.set(str(tmp_path / "out"))
        gui._manual_vars["dataset_id"].set("manual1")
        gui._manual_vars["fuel"].set("H2:0.02")
        gui._manual_vars["bath_gas"].set("Ar:0.97")
        gui._add_manual_case()

        assert len(gui._targets) == 1
        assert gui._targets[0].dataset_id == "manual1"
        assert (tmp_path / "out" / "manual_cases.target").exists()
        assert (tmp_path / "out" / "manual_cases.add").exists()

    def test_run_selected_only_filters_by_row_not_dataset_id(self, tmp_path, app_and_root):
        """A dataset ID commonly spans several rows (one experimental
        series at different T/P). Selecting one row must not pull in its
        siblings -- see src/mso_io/target_add_io.py's
        write_filtered_target_file()."""
        gui, root = app_and_root
        target_path = tmp_path / "t.target"
        target_path.write_text(
            "1 |series1| target -- Tig| T -- 900| P -- 1\n"
            "2 |series1| target -- Tig| T -- 950| P -- 1\n"
        )
        add_path = tmp_path / "t.add"
        add_path.write_text(yaml.safe_dump({}))
        cfg_path = self._write_target_opt(tmp_path, target_path, add_path)
        gui._load_config(str(cfg_path))

        first_row = gui._tree.get_children()[0]
        gui._tree.selection_set(first_row)
        gui._on_target_select()
        gui._run_selected_only.set(True)
        gui._out_dir_var.set(str(tmp_path / "out"))

        calls = []
        gui._terminal.run = lambda cmd, cwd=None: calls.append((cmd, cwd))
        gui._run_sa()

        combined = (tmp_path / "out" / "targets_selected.target").read_text()
        assert combined.count("T -- 900") == 1
        assert "T -- 950" not in combined
        assert len(calls) == 1

    def test_plot_style_json_written_on_run(self, tmp_path, app_and_root):
        gui, root = app_and_root
        target_path = tmp_path / "t.target"
        target_path.write_text("1 |a| target -- Tig| T -- 900| P -- 1\n")
        add_path = tmp_path / "t.add"
        add_path.write_text(yaml.safe_dump({}))
        cfg_path = self._write_target_opt(tmp_path, target_path, add_path)
        gui._load_config(str(cfg_path))
        gui._out_dir_var.set(str(tmp_path / "out"))
        gui._style_vars["dpi"].set("300")
        gui._style_vars["export_format"].set("pdf")

        gui._terminal.run = lambda cmd, cwd=None: None
        gui._run_sa()

        style_path = tmp_path / "out" / "plot_style.json"
        assert style_path.exists()
        saved = app.PlotStyle.load(str(style_path))
        assert saved.dpi == 300
        assert saved.export_format == "pdf"
        assert os.environ.get("SENS3P_PLOT_STYLE_JSON") == str(style_path)
