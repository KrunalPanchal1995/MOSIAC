"""
Tests for src/gui_common/ -- shared infrastructure extracted from
generate_target_opt.py during the GUI-separation split (see
MarkDownFiles/GUI_SEPARATION_AND_IMPROVEMENT_PLAN_2026-07-12_142230.md).

Covers the pure-logic modules (fuel_data, variable_map, target_types,
settings, autosave). theme.py/pty_terminal.py need a real Tk/display and are
exercised manually (see brute_force_sa_gui.py's own smoke test), not here.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_gui_common.py -v
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from gui_common.fuel_data import FuelNormalizer
from gui_common.variable_map import VariableNameMapper
from gui_common.target_types import TARGET_TYPES, TARGET_TYPE_FIELDS, TARGET_ROW_COLUMNS
from gui_common.settings import load_settings, save_settings
from gui_common.autosave import AutoSaveManager


# ===========================================================================
# fuel_data.FuelNormalizer
# ===========================================================================

class TestFuelNormalizer:
    def test_normalize_alias(self):
        assert FuelNormalizer.normalize("n-heptane") == "NC7H16"
        assert FuelNormalizer.normalize("nheptane") == "NC7H16"
        assert FuelNormalizer.normalize("h2") == "H2"

    def test_normalize_unknown_passthrough(self):
        assert FuelNormalizer.normalize("some_unknown_species") == "some_unknown_species"

    def test_get_mw_delegates_to_chem_data(self):
        """MW must come from chem_data.py (single source of truth), not a
        second duplicated table -- this is the dedup this module made
        during extraction from generate_target_opt.py's original
        FuelNormalizer (see this module's own docstring)."""
        import chem_data
        assert FuelNormalizer.get_mw("NC7H16") == chem_data.DEFAULT_FUEL_MW["NC7H16"]
        assert FuelNormalizer.get_mw("h2") == pytest.approx(2.016)

    def test_get_nu_o2_delegates_to_chem_data(self):
        import chem_data
        assert FuelNormalizer.get_nu_o2("CH4") == chem_data.compute_nu_o2("CH4")

    def test_get_smiles_known_and_unknown(self):
        assert FuelNormalizer.get_smiles("NC7H16") == "CCCCCCC"
        assert FuelNormalizer.get_smiles("IC16H34") is None  # uncertain isomer, by design

    def test_is_known_fuel(self):
        assert FuelNormalizer.is_known_fuel("nheptane") is True
        assert FuelNormalizer.is_known_fuel("totally_not_a_fuel") is False

    def test_validate_fuel_against_mechanism_found(self):
        ok, msg, suggestions = FuelNormalizer.validate_fuel_against_mechanism(
            "h2", ["H2", "O2", "N2"])
        assert ok is True
        assert suggestions == []

    def test_validate_fuel_against_mechanism_not_found_with_suggestion(self):
        ok, msg, suggestions = FuelNormalizer.validate_fuel_against_mechanism(
            "nc7h16", ["NC7H16OH", "O2"])
        assert ok is False
        assert suggestions  # fuzzy match should find NC7H16OH


# ===========================================================================
# variable_map.VariableNameMapper
# ===========================================================================

class TestVariableNameMapper:
    def test_known_mapping(self):
        assert VariableNameMapper.get_codebase_name("proj_name") == "project.name"
        assert "identifier" in VariableNameMapper.get_comment("proj_name").lower()

    def test_unknown_key_passthrough(self):
        assert VariableNameMapper.get_codebase_name("not_a_real_key") == "not_a_real_key"
        assert VariableNameMapper.get_comment("not_a_real_key") == ""


# ===========================================================================
# target_types
# ===========================================================================

class TestTargetTypes:
    def test_every_target_type_has_fields_entry(self):
        assert set(TARGET_TYPES.keys()) == set(TARGET_TYPE_FIELDS.keys())

    def test_expected_codes_present(self):
        # KP's existing vocabulary -- must never silently drift.
        assert set(TARGET_TYPES.keys()) == {
            "Tig", "Fls", "Flf", "Flf_a", "JSR", "PFR", "RCM", "Flw",
        }

    def test_target_row_columns_nonempty(self):
        assert "dataset_id" in TARGET_ROW_COLUMNS
        assert "target_type" in TARGET_ROW_COLUMNS


# ===========================================================================
# settings (per-app JSON persistence)
# ===========================================================================

class TestSettings:
    def test_roundtrip(self, tmp_path, monkeypatch):
        import gui_common.settings as settings_mod
        monkeypatch.setattr(settings_mod, "_SETTINGS_DIR", tmp_path)

        settings_mod.save_settings("unit_test_app", {"last_target_opt": "/x/target.opt"})
        loaded = settings_mod.load_settings("unit_test_app")
        assert loaded == {"last_target_opt": "/x/target.opt"}

    def test_load_missing_returns_empty_dict(self, tmp_path, monkeypatch):
        import gui_common.settings as settings_mod
        monkeypatch.setattr(settings_mod, "_SETTINGS_DIR", tmp_path)
        assert settings_mod.load_settings("never_saved_app") == {}

    def test_separate_apps_do_not_collide(self, tmp_path, monkeypatch):
        import gui_common.settings as settings_mod
        monkeypatch.setattr(settings_mod, "_SETTINGS_DIR", tmp_path)

        settings_mod.save_settings("app_a", {"k": "a"})
        settings_mod.save_settings("app_b", {"k": "b"})
        assert settings_mod.load_settings("app_a") == {"k": "a"}
        assert settings_mod.load_settings("app_b") == {"k": "b"}


# ===========================================================================
# autosave.AutoSaveManager (fake root, no real Tk needed)
# ===========================================================================

class _FakeRoot:
    """Minimal stand-in for tk.Tk's .after()/.after_cancel(), synchronous
    (calls the callback immediately) so tests don't need a Tk mainloop."""
    def __init__(self):
        self.cancelled = []

    def after(self, ms, callback):
        callback()
        return "fake-timer-id"

    def after_cancel(self, timer_id):
        self.cancelled.append(timer_id)


class TestAutoSaveManager:
    def test_mark_dirty_triggers_save(self):
        root = _FakeRoot()
        calls = []
        mgr = AutoSaveManager(root, save_callback=lambda: calls.append(1))
        mgr.mark_dirty()
        assert calls == [1]
        assert mgr.dirty is False  # cleared after successful save

    def test_save_error_does_not_raise(self):
        root = _FakeRoot()
        def _boom():
            raise RuntimeError("disk full")
        mgr = AutoSaveManager(root, save_callback=_boom)
        mgr.mark_dirty()  # must not raise
        assert mgr.dirty is True  # save failed, still dirty

    def test_on_close_flushes_if_dirty(self):
        root = _FakeRoot()
        calls = []
        mgr = AutoSaveManager(root, save_callback=lambda: calls.append(1))
        mgr.dirty = True
        mgr.timer_id = "pending"
        mgr.on_close()
        assert calls == [1]
        assert "pending" in root.cancelled


# ===========================================================================
# Autosave wiring smoke tests (Phase-3 follow-on Part B --
# FEATURE_GAPS_FROM_MONOLITH.md ranked candidate #3): the 4 places
# AutoSaveManager was actually wired into a real app --
#   1. uncertainty_generator_gui.py (existing _add_gen_row/_remove_gen_row)
#   2. mean_value_fusion_gui.py (traced persisted form fields)
#   3. rmip_suite_gui.py's TargetBuilderTab fuel-blend row editor
#   4. rmip_suite_gui.py's ReductionTab multi-condition row editor
# (3) and (4) share ONE AutoSaveManager/checkpoint file at the RMIPSuiteApp
# level, per gui_common/autosave.py's "each split-out APP gets its own file"
# rule (rmip_suite_gui.py is one app with two row editors, not two apps).
#
# These instantiate the real Tk app classes (a live Tk() root is available
# in this environment -- see tests/test_rmip_suite_gui.py) and call
# .mark_dirty()/on_close() through the actual wiring rather than reimplementing
# it against a fake root; the timer itself is bypassed by calling
# AutoSaveManager._do_save()/on_close() directly (advancing/flushing) instead
# of waiting on root.after(), matching how a real close/idle flush behaves.
# ===========================================================================

import json as _json
import sys as _sys

import tkinter as _tk

_sys.path.insert(0, _ROOT)


class TestAutosaveWiredUncertaintyGenerator:
    def test_mark_dirty_then_flush_writes_checkpoint(self, tmp_path, monkeypatch):
        import uncertainty_generator_gui as ug_app
        monkeypatch.setattr(ug_app, "_CHECKPOINT_PATH", tmp_path / "ckpt.json")

        root = _tk.Tk()
        try:
            app = ug_app.UncertaintyGeneratorApp(root)
            assert app._autosave.dirty is False

            app._gen_rxn_var.set("H+O2<=>O+OH")
            app._add_gen_row()  # existing row-add callback -- must mark_dirty()
            assert app._autosave.dirty is True

            app._autosave._do_save()  # advance/flush without waiting on the timer
            assert app._autosave.dirty is False
            assert (tmp_path / "ckpt.json").is_file()
            state = _json.loads((tmp_path / "ckpt.json").read_text())
            assert state["gen_rows"]
        finally:
            root.destroy()

    def test_on_close_flushes_final_state(self, tmp_path, monkeypatch):
        import uncertainty_generator_gui as ug_app
        monkeypatch.setattr(ug_app, "_CHECKPOINT_PATH", tmp_path / "ckpt2.json")

        root = _tk.Tk()
        app = ug_app.UncertaintyGeneratorApp(root)
        app._gen_rxn_var.set("O+H2<=>H+OH")
        app._add_gen_row()
        assert app._autosave.dirty is True
        app._on_close()  # simulates WM_DELETE_WINDOW -- flush then destroy
        assert (tmp_path / "ckpt2.json").is_file()


class TestAutosaveWiredMeanValueFusion:
    def test_mark_dirty_then_flush_writes_checkpoint(self, tmp_path, monkeypatch):
        import mean_value_fusion_gui as mvf_app
        monkeypatch.setattr(mvf_app, "_CHECKPOINT_PATH", tmp_path / "ckpt.json")

        root = _tk.Tk()
        try:
            app = mvf_app.MeanValueFusionApp(root)
            assert app._autosave.dirty is False

            app._mech_ids_var.set("1,2,3")  # traced persisted field -> mark_dirty()
            assert app._autosave.dirty is True

            app._autosave._do_save()
            assert app._autosave.dirty is False
            assert (tmp_path / "ckpt.json").is_file()
            state = _json.loads((tmp_path / "ckpt.json").read_text())
            assert state["mech_ids"] == "1,2,3"
        finally:
            root.destroy()

    def test_on_close_flushes_final_state(self, tmp_path, monkeypatch):
        import mean_value_fusion_gui as mvf_app
        monkeypatch.setattr(mvf_app, "_CHECKPOINT_PATH", tmp_path / "ckpt2.json")

        root = _tk.Tk()
        app = mvf_app.MeanValueFusionApp(root)
        app._tol_A_var.set("0.05")
        assert app._autosave.dirty is True
        app._on_close()
        assert (tmp_path / "ckpt2.json").is_file()


class TestAutosaveWiredRmipSuite:
    """Covers both of rmip_suite_gui.py's row editors (TargetBuilderTab's
    fuel blend, ReductionTab's conditions) -- they share the one
    RMIPSuiteApp-level AutoSaveManager/checkpoint file."""

    def test_target_builder_fuel_row_marks_dirty_and_flushes(self, tmp_path, monkeypatch):
        import rmip_suite_gui as rs_app
        monkeypatch.setattr(rs_app, "_CHECKPOINT_PATH", tmp_path / "ckpt.json")

        root = _tk.Tk()
        try:
            app = rs_app.RMIPSuiteApp(root)
            assert app._autosave.dirty is False

            tb = app._target_builder_tab
            tb._fuel_sp_var.set("H2")
            tb._fuel_frac_var.set("1.0")
            tb._add_fuel_row()  # existing row-add callback -- must mark_dirty()
            assert app._autosave.dirty is True

            app._autosave._do_save()
            assert app._autosave.dirty is False
            assert (tmp_path / "ckpt.json").is_file()
            state = _json.loads((tmp_path / "ckpt.json").read_text())
            assert state["target_builder_fuel_rows"]
        finally:
            root.destroy()

    def test_reduction_condition_row_marks_dirty_and_flushes(self, tmp_path, monkeypatch):
        import rmip_suite_gui as rs_app
        monkeypatch.setattr(rs_app, "_CHECKPOINT_PATH", tmp_path / "ckpt.json")

        root = _tk.Tk()
        try:
            app = rs_app.RMIPSuiteApp(root)
            red = app._reduction_tab
            red._cond_T_var.set("1000")
            red._cond_P_var.set("1.0")
            red._cond_phi_var.set("1.0")
            red._cond_fuel_var.set("H2:1.0")
            red._add_cond_row()  # existing row-add callback -- must mark_dirty()
            assert app._autosave.dirty is True

            app._autosave._do_save()
            state = _json.loads((tmp_path / "ckpt.json").read_text())
            assert state["reduction_condition_rows"]
        finally:
            root.destroy()

    def test_on_close_flushes_final_state(self, tmp_path, monkeypatch):
        import rmip_suite_gui as rs_app
        monkeypatch.setattr(rs_app, "_CHECKPOINT_PATH", tmp_path / "ckpt2.json")

        root = _tk.Tk()
        app = rs_app.RMIPSuiteApp(root)
        tb = app._target_builder_tab
        tb._fuel_sp_var.set("H2")
        tb._fuel_frac_var.set("1.0")
        tb._add_fuel_row()
        assert app._autosave.dirty is True
        app._on_close()
        assert (tmp_path / "ckpt2.json").is_file()
