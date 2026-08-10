"""
Tests for KRUNAL_JULY_23.md point 4 -- target.opt/.target/.add option-surface
schema + IO helpers (src/mso_io/target_add_schema.py, target_add_io.py).

Round-trips format_target_line() through the REAL parser
(src/MUQ-SAC/combustion_target_class.combustion_target) to guarantee the
GUI's "manual entry" mode writes lines the live engine actually accepts.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_target_add_schema_io.py -v
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "src", "MUQ-SAC"))

from mso_io.target_add_schema import (
    NewCaseFields, is_runnable, fields_for, ADD_DEFAULTS,
    LIVE_ENGINE_SOLVERS, LIVE_ENGINE_TARGET_TYPES,
)
from mso_io.target_add_io import (
    format_target_line, preview_targets, load_add, save_add,
    set_case_options, append_case, write_filtered_target_file,
    update_line, delete_line,
)


class TestIsRunnable:
    def test_flamemaster_cantera_chemkinpro_runnable(self):
        for solver in ("cantera", "CHEMKIN_PRO", "FlameMaster"):
            ok, _ = is_runnable(solver, "Tig")
            assert ok, solver

    def test_zerork_solver_gated(self):
        ok, reason = is_runnable("zerork", "Tig")
        assert not ok
        assert "zerork" in reason

    def test_pfr_target_type_gated(self):
        ok, reason = is_runnable("cantera", "PFR")
        assert not ok
        assert "PFR" not in LIVE_ENGINE_TARGET_TYPES

    def test_flux_analysis_gated(self):
        ok, reason = is_runnable("cantera", "Tig", flux_analysis=True)
        assert not ok
        assert "flux_analysis" in reason


class TestFieldsFor:
    def test_common_plus_type_fields(self):
        fields = fields_for("Tig", "cantera")
        assert "ign_cond" in fields
        assert "dpdt" in fields
        assert "zerork_install_dir" not in fields

    def test_zerork_solver_adds_zerork_group(self):
        fields = fields_for("RCM", "zerork")
        assert "zerork_rcm_volume_mult" in fields


class TestFormatTargetLineRoundTrip:
    """format_target_line() must produce a line the REAL
    combustion_target_class parser (src/MUQ-SAC/combustion_target_class.py)
    accepts and decodes back to the same values."""

    def _round_trip(self, fields, addendum=None):
        from combustion_target_class import combustion_target
        line = format_target_line(1, fields)
        return combustion_target(line, addendum or {}, 0), line

    def test_multi_species_fuel_round_trips(self):
        fields = NewCaseFields(
            dataset_id="x_test001", target_type="Tig",
            simulation="Isochor Homo Reactor", solver="cantera",
            temperature_K=1200.0, pressure_atm=2.5,
            fuel={"H2": 0.02, "NH3": 0.01}, oxidizer="O2", oxidizer_x=0.03,
            bath_gas={"Ar": 0.94}, phi="N/A", observed=1500.0,
            deviation=100.0, data_weight=1.0, species="OH",
        )
        t, line = self._round_trip(fields)
        assert t.dataSet_id == "x_test001"
        assert t.target == "Tig"
        assert t.simulation == "Isochor Homo Reactor"
        assert t.temperature == 1200.0
        assert t.pressure == pytest.approx(2.5 * 101325)
        assert t.fuel_dict == {"H2": 0.02, "NH3": 0.01}
        assert t.BG_dict == {"Ar": 0.94}
        assert t.species_dict["O2"] == 0.03
        assert t.observed == 1500.0
        assert t.std_dvtn == 100.0
        assert t.species == "OH"

    def test_single_species_fuel_round_trips(self):
        fields = NewCaseFields(
            dataset_id="x_test002", target_type="RCM", solver="FlameMaster",
            temperature_K=900.0, pressure_atm=10.0, fuel={"NC7H16": 0.015},
            oxidizer="O2", oxidizer_x=0.15, bath_gas={"N2": 0.835},
        )
        t, line = self._round_trip(fields)
        assert t.fuel_dict == {"NC7H16": 0.015}

    def test_addendum_solver_carried_through(self):
        fields = NewCaseFields(dataset_id="x_test003", solver="CHEMKIN_PRO")
        line = format_target_line(1, fields)
        from combustion_target_class import combustion_target
        t = combustion_target(line, {"x_test003": {"solver": "CHEMKIN_PRO"}}, 0)
        assert t.add["solver"] == "CHEMKIN_PRO"


class TestPreviewTargets:
    def test_real_ammonia_target_file(self):
        path = os.path.join(_ROOT, "DATASET", "AMMONIA", "AMMONIA.target")
        add_path = os.path.join(_ROOT, "DATASET", "AMMONIA", "addundem.add")
        if not os.path.exists(path):
            pytest.skip("DATASET/AMMONIA/AMMONIA.target not present in this checkout")
        rows = preview_targets(path, add_path)
        assert len(rows) > 0
        assert all(r.dataset_id for r in rows)
        assert all(r.solver == "FlameMaster" for r in rows[:3])
        assert all(r.runnable for r in rows[:3])  # FlameMaster is live-supported

    def test_gates_pfr_and_zerork_in_preview(self, tmp_path):
        target_file = tmp_path / "t.target"
        target_file.write_text(
            "1 |case1| target -- PFR| T -- 900| P -- 1| species -- OH\n"
            "2 |case2| target -- Tig| T -- 900| P -- 1| species -- OH\n"
        )
        add_file = tmp_path / "t.add"
        save_add(str(add_file), {"case2": {"solver": "zerork"}})
        rows = preview_targets(str(target_file), str(add_file))
        by_id = {r.dataset_id: r for r in rows}
        assert not by_id["case1"].runnable  # PFR
        assert not by_id["case2"].runnable  # zerork


class TestAddIO:
    def test_load_save_round_trip(self, tmp_path):
        p = tmp_path / "x.add"
        save_add(str(p), {"case1": {"solver": "cantera", "ign_cond": "max"}})
        loaded = load_add(str(p))
        assert loaded == {"case1": {"solver": "cantera", "ign_cond": "max"}}

    def test_set_case_options_merges(self):
        data = {"case1": {"solver": "cantera"}}
        out = set_case_options(data, "case1", {"ign_cond": "onset"})
        assert out["case1"] == {"solver": "cantera", "ign_cond": "onset"}
        assert data["case1"] == {"solver": "cantera"}  # original untouched

    def test_set_case_options_new_dataset(self):
        out = set_case_options({}, "new_case", {"solver": "FlameMaster"})
        assert out == {"new_case": {"solver": "FlameMaster"}}


class TestAppendCase:
    def test_append_creates_files_and_is_parseable(self, tmp_path):
        target_path = tmp_path / "new.target"
        add_path = tmp_path / "new.add"
        fields = NewCaseFields(
            dataset_id="manual001", target_type="Tig", solver="cantera",
            temperature_K=1100.0, pressure_atm=5.0, fuel={"H2": 0.03},
            oxidizer="O2", oxidizer_x=0.015, bath_gas={"Ar": 0.955},
        )
        idx = append_case(str(target_path), str(add_path), fields)
        assert idx == 1
        assert target_path.exists() and add_path.exists()

        add_data = load_add(str(add_path))
        assert add_data["manual001"]["solver"] == "cantera"

        rows = preview_targets(str(target_path), str(add_path))
        assert len(rows) == 1
        assert rows[0].dataset_id == "manual001"
        assert rows[0].runnable

    def test_append_second_case_increments_index(self, tmp_path):
        target_path = tmp_path / "new.target"
        add_path = tmp_path / "new.add"
        f1 = NewCaseFields(dataset_id="c1", solver="cantera")
        f2 = NewCaseFields(dataset_id="c2", solver="cantera")
        i1 = append_case(str(target_path), str(add_path), f1)
        i2 = append_case(str(target_path), str(add_path), f2)
        assert i1 == 1 and i2 == 2
        rows = preview_targets(str(target_path), str(add_path))
        assert {r.dataset_id for r in rows} == {"c1", "c2"}


class TestUpdateLine:
    def test_replaces_the_target_row_in_place(self, tmp_path):
        target_path = tmp_path / "t.target"
        add_path = tmp_path / "t.add"
        f1 = NewCaseFields(dataset_id="c1", solver="cantera", temperature_K=900.0)
        f2 = NewCaseFields(dataset_id="c2", solver="cantera", temperature_K=950.0)
        append_case(str(target_path), str(add_path), f1)
        append_case(str(target_path), str(add_path), f2)

        updated = NewCaseFields(dataset_id="c1_edited", solver="CHEMKIN_PRO",
                                 temperature_K=1234.0)
        update_line(str(target_path), str(add_path), 1, updated)

        rows = preview_targets(str(target_path), str(add_path))
        assert len(rows) == 2   # row count unchanged -- in-place, not append
        assert rows[0].dataset_id == "c1_edited"
        assert rows[0].temperature_K == 1234.0
        assert rows[0].solver == "CHEMKIN_PRO"
        # Row 2 (c2) must be untouched.
        assert rows[1].dataset_id == "c2"
        assert rows[1].temperature_K == 950.0

    def test_updates_the_paired_add_entry(self, tmp_path):
        target_path = tmp_path / "t.target"
        add_path = tmp_path / "t.add"
        f1 = NewCaseFields(dataset_id="c1", solver="cantera")
        append_case(str(target_path), str(add_path), f1)

        updated = NewCaseFields(dataset_id="c1", solver="zerork",
                                 add_overrides={"flux_analysis": True})
        update_line(str(target_path), str(add_path), 1, updated)

        add_data = load_add(str(add_path))
        assert add_data["c1"]["solver"] == "zerork"
        assert add_data["c1"]["flux_analysis"] is True

    def test_line_written_is_still_parseable(self, tmp_path):
        """The updated line must round-trip through the real
        combustion_target_class parser, same guarantee as append_case."""
        from combustion_target_class import combustion_target

        target_path = tmp_path / "t.target"
        add_path = tmp_path / "t.add"
        f1 = NewCaseFields(dataset_id="c1", solver="cantera")
        append_case(str(target_path), str(add_path), f1)

        updated = NewCaseFields(
            dataset_id="c1_updated", target_type="Tig", solver="cantera",
            temperature_K=1100.0, pressure_atm=5.0, fuel={"H2": 0.03},
            oxidizer="O2", oxidizer_x=0.015, bath_gas={"Ar": 0.955},
        )
        update_line(str(target_path), str(add_path), 1, updated)

        line = target_path.read_text().splitlines()[0]
        add_data = load_add(str(add_path))
        t = combustion_target(line, add_data, 0)
        assert t.target == "Tig"
        assert t.temperature == pytest.approx(1100.0)

    def test_out_of_range_line_no_raises(self, tmp_path):
        target_path = tmp_path / "t.target"
        add_path = tmp_path / "t.add"
        f1 = NewCaseFields(dataset_id="c1", solver="cantera")
        append_case(str(target_path), str(add_path), f1)

        with pytest.raises(IndexError):
            update_line(str(target_path), str(add_path), 5, f1)
        with pytest.raises(IndexError):
            update_line(str(target_path), str(add_path), 0, f1)


class TestDeleteLine:
    def test_removes_only_the_targeted_row(self, tmp_path):
        target_path = tmp_path / "t.target"
        add_path = tmp_path / "t.add"
        for ds_id in ("c1", "c2", "c3"):
            append_case(str(target_path), str(add_path),
                        NewCaseFields(dataset_id=ds_id, solver="cantera"))

        delete_line(str(target_path), 2)

        rows = preview_targets(str(target_path), str(add_path))
        assert [r.dataset_id for r in rows] == ["c1", "c3"]

    def test_does_not_touch_the_add_file(self, tmp_path):
        """Deleting a .target row leaves the paired .add entry alone --
        .add is keyed by dataset ID, not line position, and other rows may
        still reference the same ID."""
        target_path = tmp_path / "t.target"
        add_path = tmp_path / "t.add"
        append_case(str(target_path), str(add_path),
                    NewCaseFields(dataset_id="c1", solver="cantera"))
        add_before = load_add(str(add_path))

        delete_line(str(target_path), 1)

        add_after = load_add(str(add_path))
        assert add_after == add_before
        assert "c1" in add_after   # orphaned but harmless, left alone

    def test_deleting_down_to_empty_file_leaves_it_readable(self, tmp_path):
        target_path = tmp_path / "t.target"
        add_path = tmp_path / "t.add"
        append_case(str(target_path), str(add_path),
                    NewCaseFields(dataset_id="c1", solver="cantera"))

        delete_line(str(target_path), 1)

        rows = preview_targets(str(target_path))
        assert rows == []

    def test_out_of_range_line_no_raises(self, tmp_path):
        target_path = tmp_path / "t.target"
        add_path = tmp_path / "t.add"
        append_case(str(target_path), str(add_path),
                    NewCaseFields(dataset_id="c1", solver="cantera"))

        with pytest.raises(IndexError):
            delete_line(str(target_path), 5)
        with pytest.raises(IndexError):
            delete_line(str(target_path), 0)


class TestWriteFilteredTargetFile:
    def test_keeps_only_selected_line_numbers(self, tmp_path):
        target_path = tmp_path / "t.target"
        target_path.write_text(
            "1 |a| target -- Tig| T -- 900| P -- 1\n"
            "2 |b| target -- Tig| T -- 950| P -- 1\n"
            "3 |c| target -- Tig| T -- 1000| P -- 1\n"
        )
        out_path = tmp_path / "filtered.target"
        n = write_filtered_target_file(str(target_path), [1, 3], str(out_path))
        assert n == 2
        rows = preview_targets(str(out_path))
        assert {r.dataset_id for r in rows} == {"a", "c"}

    def test_filters_by_line_not_dataset_id_when_id_repeats(self, tmp_path):
        """One dataset ID commonly spans many lines (a series at several
        T/P conditions) -- selecting a single row must not pull in its
        siblings sharing the same dataset ID."""
        target_path = tmp_path / "t.target"
        target_path.write_text(
            "1 |series1| target -- Tig| T -- 900| P -- 1\n"
            "2 |series1| target -- Tig| T -- 950| P -- 1\n"
            "3 |series1| target -- Tig| T -- 1000| P -- 1\n"
        )
        out_path = tmp_path / "filtered.target"
        n = write_filtered_target_file(str(target_path), [2], str(out_path))
        assert n == 1
        rows = preview_targets(str(out_path))
        assert len(rows) == 1
        assert rows[0].temperature_K == 950.0
