"""
Tests for the Target Workbench (VisualAid.py's TargetSet/TargetChecker/
DummyPointGenerator/TargetPruner/NominalParityAnalyzer + mso_io.target_add_io.
write_curated_set) and its generate_target_opt.py GUI tab.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_target_workbench.py -v
"""
import os
import sys
import shutil

import numpy as np
import pandas as pd
import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MUQSAC_DIR = os.path.join(_ROOT, "src", "MUQ-SAC")
_SRC_DIR = os.path.join(_ROOT, "src")
if _MUQSAC_DIR not in sys.path:
    sys.path.insert(0, _MUQSAC_DIR)
if _SRC_DIR not in sys.path:
    sys.path.append(_SRC_DIR)

import VisualAid as VA  # noqa: E402
from mso_io.target_add_io import write_curated_set  # noqa: E402
from mso_io.target_add_schema import NewCaseFields  # noqa: E402

AMMONIA_TARGET = os.path.join(_ROOT, "DATASET", "AMMONIA", "AMMONIA.target")
AMMONIA_ADD = os.path.join(_ROOT, "DATASET", "AMMONIA", "addundem.add")
MB_NO_DUMMY = os.path.join(_ROOT, "DATASET", "METHYL_BUTANOATE_2026", "MB_LTC_no_dummy.target")
MB_WITH_DUMMY = os.path.join(_ROOT, "DATASET", "METHYL_BUTANOATE_2026", "MB_LTC_DUMMY.target")


def _write_target(tmp_path, lines):
    p = tmp_path / "hand_built.target"
    p.write_text("\n".join(lines) + "\n")
    return str(p)


def _good_line(idx, dataset_id, T=1500.0, P=10.0, observed=500.0, deviation=50.0, weight=1):
    fuel = "x->{'a': 'NH3'} = {'a': 0.05}"
    ox = "x->O2 = 0.02"
    bath = "x->{'a': 'Ar'} = {'a': 0.93}"
    units = "{'conc': 'mol', 'P': 'atm', 'T': 'K', 'observed': 'us', 'flow': ''}"
    return (f"{idx}\t|{dataset_id}\t| target -- Tig\t| simulation -- Isochor Homo Reactor"
            f"\t| Fuel_type -- Multi\t| Fuel -- {fuel}\t| Oxidizer -- {ox}"
            f"\t| Bath_gas -- {bath}\t|T -- {T}\t| P -- {P}\t|Phi -- N/A"
            f"\t| observed -- {observed}\t| obs_unit --unitless \t| deviation -- {deviation}"
            f"\t|data_weight -- {weight}\t|units -- {units}")


def _bad_composition_line(idx, dataset_id):
    """Fuel+oxidizer+bath sums to ~2.0, not 1.0."""
    fuel = "x->{'a': 'NH3'} = {'a': 1.0}"
    ox = "x->O2 = 0.5"
    bath = "x->{'a': 'Ar'} = {'a': 0.5}"
    units = "{'conc': 'mol', 'P': 'atm', 'T': 'K', 'observed': 'us', 'flow': ''}"
    return (f"{idx}\t|{dataset_id}\t| target -- Tig\t| simulation -- Isochor Homo Reactor"
            f"\t| Fuel_type -- Multi\t| Fuel -- {fuel}\t| Oxidizer -- {ox}"
            f"\t| Bath_gas -- {bath}\t|T -- 1500.0\t| P -- 10.0\t|Phi -- N/A"
            f"\t| observed -- 500.0\t| obs_unit --unitless \t| deviation -- 50.0"
            f"\t|data_weight -- 1\t|units -- {units}")


def _zero_deviation_line(idx, dataset_id):
    return _good_line(idx, dataset_id, T=1400.0, deviation=0.0)


class TestTargetSetRealData:
    def test_loads_ammonia_target(self):
        ts = VA.TargetSet(AMMONIA_TARGET, AMMONIA_ADD)
        assert len(ts) > 0
        assert len(ts.dataset_ids()) > 1

    def test_composition_parses_to_species_dict(self):
        ts = VA.TargetSet(AMMONIA_TARGET)
        row = ts.rows[0]
        assert isinstance(row.fuel, dict) and len(row.fuel) > 0
        assert isinstance(row.oxidizer, dict) and len(row.oxidizer) > 0
        assert isinstance(row.bath_gas, dict) and len(row.bath_gas) > 0

    def test_to_dataframe_has_expected_columns(self):
        ts = VA.TargetSet(AMMONIA_TARGET)
        df = ts.to_dataframe()
        for col in ("line_no", "dataset_id", "temperature_K", "pressure_atm",
                    "observed", "deviation", "composition_sum"):
            assert col in df.columns

    def test_by_line_and_rows_for(self):
        ts = VA.TargetSet(AMMONIA_TARGET)
        first = ts.rows[0]
        assert ts.by_line(first.line_no).dataset_id == first.dataset_id
        with pytest.raises(KeyError):
            ts.by_line(999999)
        assert len(ts.rows_for(first.dataset_id)) >= 1


class TestTargetCheckerHandBuilt:
    def test_composition_sum_flags_bad_row(self, tmp_path):
        path = _write_target(tmp_path, [_bad_composition_line(1, "bad1")])
        ts = VA.TargetSet(path)
        checker = VA.TargetChecker(ts)
        findings = checker.check_composition_sums(tol=0.02)
        assert len(findings) == 1
        assert findings[0].check == "composition_sum"
        assert findings[0].severity == "warning"

    def test_composition_sum_passes_good_row(self, tmp_path):
        path = _write_target(tmp_path, [_good_line(1, "good1")])
        ts = VA.TargetSet(path)
        checker = VA.TargetChecker(ts)
        findings = checker.check_composition_sums(tol=0.02)
        assert findings == []

    def test_zero_deviation_flagged(self, tmp_path):
        path = _write_target(tmp_path, [_zero_deviation_line(1, "zdev")])
        ts = VA.TargetSet(path)
        checker = VA.TargetChecker(ts)
        findings = checker.check_deviation_outliers()
        assert any(f.check == "deviation" and "exactly 0" in f.message for f in findings)

    def test_duplicate_conditions_flagged(self, tmp_path):
        lines = [_good_line(1, "dup", T=1500.0, P=10.0),
                 _good_line(2, "dup", T=1500.0, P=10.0)]
        path = _write_target(tmp_path, lines)
        ts = VA.TargetSet(path)
        checker = VA.TargetChecker(ts)
        findings = checker.check_duplicate_conditions()
        assert len(findings) == 2
        assert all(f.check == "duplicate_condition" for f in findings)

    def test_units_flags_implausible_temperature(self, tmp_path):
        path = _write_target(tmp_path, [_good_line(1, "hot", T=9000.0)])
        ts = VA.TargetSet(path)
        checker = VA.TargetChecker(ts)
        findings = checker.check_units()
        assert any(f.check == "units" and "T=" in f.message for f in findings)

    def test_check_parses_gate_passes_good_rows(self, tmp_path):
        path = _write_target(tmp_path, [_good_line(1, "good1"), _good_line(2, "good2")])
        ts = VA.TargetSet(path)
        checker = VA.TargetChecker(ts)
        findings = checker.check_parses()
        errors = [f for f in findings if f.severity == "error"]
        assert errors == []

    def test_check_parses_gate_catches_malformed_row(self, tmp_path):
        # Missing Oxidizer entirely -> combustion_target's ValueError on x_o2.
        bad = ("1\t|badrow\t| target -- Tig\t| simulation -- Isochor Homo Reactor"
               "\t| Fuel_type -- Multi\t| Fuel -- x->{'a': 'NH3'} = {'a': 0.05}"
               "\t| Bath_gas -- x->{'a': 'Ar'} = {'a': 0.95}\t|T -- 1500.0\t| P -- 10.0"
               "\t|Phi -- N/A\t| observed -- 500.0\t| obs_unit --unitless "
               "\t| deviation -- 50.0\t|data_weight -- 1"
               "\t|units -- {'conc': 'mol', 'P': 'atm', 'T': 'K', 'observed': 'us', 'flow': ''}")
        path = _write_target(tmp_path, [bad])
        ts = VA.TargetSet(path)
        checker = VA.TargetChecker(ts)
        findings = checker.check_parses()
        errors = [f for f in findings if f.severity == "error"]
        assert len(errors) == 1

    def test_run_all_against_real_ammonia_data(self):
        ts = VA.TargetSet(AMMONIA_TARGET, AMMONIA_ADD)
        checker = VA.TargetChecker(ts)
        findings = checker.run_all()
        errors = [f for f in findings if f.severity == "error"]
        assert errors == []  # real shipped data must parse cleanly


class TestDummyPointGenerator:
    def test_generates_points_in_three_zones(self):
        ts = VA.TargetSet(MB_NO_DUMMY)
        ds = ts.dataset_ids()[0]
        gen = VA.DummyPointGenerator(ts, ds)
        out = gen.generate(points_per_zone=5)
        assert len(out) == 15
        assert set(out["generated_zone"]) == {"before_ntc", "ntc", "after_ntc"}
        assert (out["is_dummy"] == True).all()
        assert out["observed"].min() > 0  # tau must stay positive

    def test_raises_on_too_few_points(self):
        ts = VA.TargetSet(MB_NO_DUMMY)
        # A dataset with < 4 Tig rows should raise, not silently misbehave.
        small_ds = [d for d in ts.dataset_ids() if len(ts.rows_for(d)) < 4]
        if not small_ds:
            pytest.skip("no small dataset in fixture to exercise this path")
        with pytest.raises(ValueError):
            VA.DummyPointGenerator(ts, small_ds[0])


class TestDummyDataGenerationRegression:
    """MB_LTC_DUMMY.target is the shipped, known-good output of the ORIGINAL
    (pre-refactor) Dummy_data_generation.py main() for this exact dataset
    pair. This doesn't re-run main() (its INPUT_CSV/OUTPUT_CSV are hardcoded
    absolute Windows paths from the original authoring machine, not portable
    here) -- it instead checks that the underlying primitives
    DummyPointGenerator now reuses (detect_ntc_region, build_equal_zone_grid,
    evaluate_logtau_with_linear_boundary_extrapolation) are untouched by the
    refactor, by re-deriving MB_LTC_DUMMY.target's own dummy rows from
    MB_LTC_no_dummy.target's real rows through DummyPointGenerator and
    checking they land in the same NTC-bounded temperature envelope the
    shipped file's dummy rows occupy."""

    def test_generated_envelope_matches_shipped_dummy_file(self):
        ts_src = VA.TargetSet(MB_NO_DUMMY)
        ds = "ing_Ethyl_Butanoate_PHI_1_P_30"
        assert ds in ts_src.dataset_ids()
        gen = VA.DummyPointGenerator(ts_src, ds)
        out = gen.generate(points_per_zone=15)

        ts_shipped = VA.TargetSet(MB_WITH_DUMMY)
        shipped_T = np.array([r.temperature_K for r in ts_shipped.rows
                               if "dummy_ing_Ethyl" in r.dataset_id
                               and r.temperature_K is not None])
        if len(shipped_T) == 0:
            pytest.skip("MB_LTC_DUMMY.target has no dummy_ing_Ethyl* rows to compare against")

        gen_T = out["Temperature_K"].to_numpy()
        # Same NTC-bounded temperature envelope (within a few K), not an
        # exact match -- point count/spacing legitimately differs between
        # the original hand-tuned run and this generalized generator.
        assert abs(gen_T.min() - shipped_T.min()) < 15.0
        assert abs(gen_T.max() - shipped_T.max()) < 15.0


class TestTargetPruner:
    def test_coverage_prune_monotonic_with_drop_count(self):
        ts = VA.TargetSet(AMMONIA_TARGET)
        pruner = VA.TargetPruner(ts)
        _, _, cov_small_drop = pruner.coverage_prune(n_drop=5, seed=0)
        _, _, cov_large_drop = pruner.coverage_prune(n_drop=100, seed=0)
        # Dropping more rows should never IMPROVE coverage of what remains.
        assert cov_large_drop <= cov_small_drop + 1e-9

    def test_coverage_prune_keep_drop_partition(self):
        ts = VA.TargetSet(AMMONIA_TARGET)
        pruner = VA.TargetPruner(ts)
        keep, drop, cov = pruner.coverage_prune(n_drop=20, seed=1)
        assert len(keep) + len(drop) == len(ts)
        assert set(keep).isdisjoint(set(drop))
        assert 0.0 <= cov <= 1.0

    def test_coverage_prune_rejects_bad_n_drop(self):
        ts = VA.TargetSet(AMMONIA_TARGET)
        pruner = VA.TargetPruner(ts)
        with pytest.raises(ValueError):
            pruner.coverage_prune(n_drop=0)
        with pytest.raises(ValueError):
            pruner.coverage_prune(n_drop=len(ts))

    def test_information_prune_det_ratio_in_unit_interval(self):
        ts = VA.TargetSet(AMMONIA_TARGET)
        pruner = VA.TargetPruner(ts)
        rng = np.random.default_rng(0)
        line_nos = [r.line_no for r in ts.rows[:20]]
        B = rng.normal(size=(20, 4))
        keep, drop, log = pruner.information_prune(B, line_nos, n_drop=5)
        assert len(keep) == 15 and len(drop) == 5
        assert all(0.0 <= e["det_ratio"] <= 1.0 + 1e-9 for e in log)
        # Ratios should be non-decreasing in badness order is NOT guaranteed,
        # but every ratio must be <= 1 (removing a row can't increase det).
        assert set(keep).isdisjoint(set(drop))


class TestNominalParityAnalyzer:
    def test_flags_high_leverage_rows(self):
        ts = VA.TargetSet(AMMONIA_TARGET)
        nominal = {}
        for i, r in enumerate(ts.rows):
            if r.observed is None:
                continue
            # Every 10th row gets a deliberately bad nominal prediction.
            factor = 5.0 if i % 10 == 0 else 1.01
            nominal[r.line_no] = r.observed * factor
        npa = VA.NominalParityAnalyzer(ts, nominal)
        flagged = npa.flag_leverage(n_sigma=1.0)
        assert len(flagged) > 0

    def test_parity_table_shape(self):
        ts = VA.TargetSet(AMMONIA_TARGET)
        nominal = {r.line_no: (r.observed or 0) * 1.05 for r in ts.rows if r.observed}
        npa = VA.NominalParityAnalyzer(ts, nominal)
        df = npa.parity_table()
        assert set(["line_no", "dataset_id", "observed", "model",
                     "residual", "leverage_sigma"]).issubset(df.columns)
        assert len(df) == len(nominal)


class TestWriteCuratedSetRoundTrip:
    def test_round_trip_write_and_reparse(self, tmp_path):
        src_target = tmp_path / "src.target"
        src_add = tmp_path / "src.add"
        shutil.copy(AMMONIA_TARGET, src_target)
        shutil.copy(AMMONIA_ADD, src_add)

        ts = VA.TargetSet(str(src_target), str(src_add))
        pruner = VA.TargetPruner(ts)
        keep, drop, cov = pruner.coverage_prune(n_drop=10, seed=0)

        new_case = NewCaseFields(
            dataset_id="dummy_round_trip", target_type="Tig",
            temperature_K=1600.0, pressure_atm=10.0,
            fuel={"NH3": 0.05}, oxidizer="O2", oxidizer_x=0.02,
            bath_gas={"Ar": 0.93}, observed=400.0, deviation=40.0)

        new_target, new_add, log_path = write_curated_set(
            str(src_target), str(src_add), "curated", keep,
            new_cases=[new_case],
            reason_log=[{"action": "test", "coverage": cov}],
            out_dir=str(tmp_path))

        assert os.path.isfile(new_target)
        assert os.path.isfile(new_add)
        assert os.path.isfile(log_path)

        ts2 = VA.TargetSet(new_target, new_add)
        assert len(ts2) == len(keep) + 1
        assert ts2.rows[-1].dataset_id == "dummy_round_trip"

        checker = VA.TargetChecker(ts2)
        errors = [f for f in checker.check_parses() if f.severity == "error"]
        assert errors == []

    def test_never_overwrites_source(self, tmp_path):
        src_target = tmp_path / "src.target"
        src_add = tmp_path / "src.add"
        shutil.copy(AMMONIA_TARGET, src_target)
        shutil.copy(AMMONIA_ADD, src_add)
        before = src_target.read_text()

        ts = VA.TargetSet(str(src_target), str(src_add))
        keep = [r.line_no for r in ts.rows]
        write_curated_set(str(src_target), str(src_add), "curated", keep,
                           out_dir=str(tmp_path))

        assert src_target.read_text() == before  # source untouched

    def test_versioning_never_clobbers_prior_version(self, tmp_path):
        src_target = tmp_path / "src.target"
        src_add = tmp_path / "src.add"
        shutil.copy(AMMONIA_TARGET, src_target)
        shutil.copy(AMMONIA_ADD, src_add)
        ts = VA.TargetSet(str(src_target), str(src_add))
        keep = [r.line_no for r in ts.rows]

        t1, a1, l1 = write_curated_set(str(src_target), str(src_add), "curated",
                                        keep, out_dir=str(tmp_path))
        t2, a2, l2 = write_curated_set(str(src_target), str(src_add), "curated",
                                        keep, out_dir=str(tmp_path))
        assert t1 != t2
        assert t1.endswith("_v1.target")
        assert t2.endswith("_v2.target")
        assert os.path.isfile(t1)  # first version still on disk


class TestTargetWorkbenchGUI:
    """Headless construction + wiring only -- see test_mso_compare_gui.py's
    module docstring for why the Tk UI itself isn't exercised interactively
    here. A leftover autosave checkpoint on disk pops a blocking
    messagebox.askyesno on startup -- mocked out below so this stays
    non-interactive regardless of local machine state."""

    @pytest.fixture
    def app(self, monkeypatch):
        tk = pytest.importorskip("tkinter")
        from tkinter import messagebox
        # All of these can pop a REAL blocking dialog under a live X display
        # (askyesno on startup if a stale autosave checkpoint exists on this
        # machine; showinfo/showwarning/showerror from the write/load/check
        # flows exercised below) -- mock every one so this stays
        # non-interactive regardless of local machine state.
        monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)
        monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: None)
        monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: None)
        monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: None)
        sys.path.insert(0, _ROOT)
        import generate_target_opt as gto
        root = tk.Tk()
        root.withdraw()
        app = gto.App(root)
        yield app
        root.destroy()

    def test_target_workbench_tab_present_at_index_3(self, app):
        nb = app._nb
        titles = [nb.tab(i, "text") for i in range(len(nb.tabs()))]
        # 14, not 13: a "Project Tracker" tab was appended LAST (index 13)
        # by the later mso_project work -- Target Workbench's own position
        # at index 3 is unaffected (it was never touched), only the total
        # count grew. See tests/test_mso_project_gui.py for that tab's own
        # coverage.
        assert len(titles) == 14
        assert titles[3].startswith("Target Workbench")

    def test_num_tabs_and_locker_agree(self, app):
        assert app._num_tabs == 14
        assert app._tab_locker.num_tabs == 14

    def test_load_check_drop_cycle_against_real_data(self, app):
        app._twb_target_path.set(AMMONIA_TARGET)
        app._twb_add_path.set(AMMONIA_ADD)
        app._twb_do_load()
        assert len(app._twb_tree.get_children()) == len(app._twb_ts)

        app._twb_run_checks()
        assert len(app._twb_findings) > 0
        assert len(app._twb_findings_tree.get_children()) == len(app._twb_findings)

        first_line = str(app._twb_ts.rows[0].line_no)
        app._twb_tree.selection_set(first_line)
        app._twb_mark_dropped()
        assert app._twb_ts.rows[0].line_no in app._twb_dropped

        app._twb_tree.selection_set(first_line)
        app._twb_undrop()
        assert app._twb_ts.rows[0].line_no not in app._twb_dropped

    def test_write_flow_through_gui(self, app, tmp_path):
        src = tmp_path / "src.target"
        shutil.copy(MB_NO_DUMMY, src)
        app._twb_target_path.set(str(src))
        app._twb_add_path.set("")
        app._twb_do_load()

        ds = app._twb_ts.dataset_ids()[0]
        gen = app._twb_VA.DummyPointGenerator(app._twb_ts, ds)
        out = gen.generate(points_per_zone=3)
        app._twb_dummy_template[out["dataset_ID"].iloc[0]] = gen.template_row
        for _, row in out.iterrows():
            app._twb_dummy_rows.append(row)
        app._twb_refresh_tree()

        app._twb_out_stem.set("gui_test")
        app._twb_write()

        written = list(tmp_path.glob("gui_test_v1.target"))
        assert len(written) == 1
        assert "combustion_target parser gate" in app._twb_write_status.get()
        assert "failed" not in app._twb_write_status.get()
