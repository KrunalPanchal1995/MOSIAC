"""
Tests for src/rmip/analysis/fusion_uncertainty_classification.py --
KRUNAL_JULY_23.md point 6's "emit per-reaction uncertainty output in the
format Point 5's generator consumes" requirement, plus a real end-to-end
check that the written CSV round-trips through
src/modules/interfaces.py::load_classification_file (the exact function
src/ActiveParameterScreen.py uses to read it).

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_fusion_uncertainty_classification.py -v
"""
import csv
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from rmip.analysis.fusion_uncertainty import FusionUncertaintyRecord
from rmip.analysis.fusion_uncertainty_classification import (
    build_classification_rows, write_classification_csv,
)


def _make_record(canonical_key, formula, T_grid, f_T, high_p_limit_only=False):
    n = len(T_grid)
    return FusionUncertaintyRecord(
        canonical_key=canonical_key, occurrence_index=0, formula_string=formula,
        source_mech_ids=[1, 2], high_p_limit_only=high_p_limit_only,
        T_grid_K=T_grid, k_by_source={1: [1.0] * n, 2: [1.0] * n},
        k_geo_mean=[1.0] * n, f_T=f_T, k_lb=[1.0] * n, k_ub=[1.0] * n,
        params_mean=(1e13, 0.0, 1e4),
        uf_A=max(f_T), A_bounds_uf=(1e13 / max(f_T), 1e13 * max(f_T)),
        envelope_lower=None, envelope_upper=None,
    )


class TestBuildClassificationRows:
    def test_splits_into_ltc_and_htc_groups(self):
        rec = _make_record(
            "k1", "H+O2<=>O+OH",
            T_grid=[500, 700, 900, 1200, 1800, 2400],
            f_T=[1.5, 1.6, 1.4, 1.2, 1.1, 1.05],
        )
        rows = build_classification_rows([rec], split_K=1000.0)
        groups = {r["Group"] for r in rows}
        assert groups == {"LTC", "HTC"}
        ltc = next(r for r in rows if r["Group"] == "LTC")
        htc = next(r for r in rows if r["Group"] == "HTC")
        assert ltc["f"] == 1.6   # max of [1.5, 1.6, 1.4] (T < 1000)
        assert htc["f"] == 1.2   # max of [1.2, 1.1, 1.05] (T >= 1000)

    def test_reaction_id_is_sequential_and_unique(self):
        rec1 = _make_record("k1", "A<=>B", [500, 1500], [1.1, 1.2])
        rec2 = _make_record("k2", "C<=>D", [500, 1500], [1.3, 1.4])
        rows = build_classification_rows([rec1, rec2])
        ids = [r["Reaction_ID"] for r in rows]
        assert ids == list(range(1, len(rows) + 1))
        assert len(set(ids)) == len(ids)

    def test_falloff_reaction_type_tagged(self):
        rec = _make_record("k1", "H2O2(+M)<=>2OH(+M)", [500, 1500], [1.1, 1.2],
                            high_p_limit_only=True)
        rows = build_classification_rows([rec])
        assert all(r["Reaction_Type"] == "Falloff/PLOG" for r in rows)

    def test_grid_entirely_below_split_only_produces_ltc(self):
        rec = _make_record("k1", "A<=>B", [500, 700, 900], [1.1, 1.2, 1.15])
        rows = build_classification_rows([rec], split_K=1000.0)
        assert {r["Group"] for r in rows} == {"LTC"}

    def test_required_columns_present(self):
        rec = _make_record("k1", "A<=>B", [500, 1500], [1.1, 1.2])
        rows = build_classification_rows([rec])
        for row in rows:
            assert set(row.keys()) == {"Reaction_ID", "Reaction", "Reaction_Type", "Group", "f"}


class TestWriteClassificationCsv:
    def test_writes_real_csv_file(self, tmp_path):
        rec = _make_record("k1", "H+O2<=>O+OH", [500, 1500], [1.3, 1.15])
        out = str(tmp_path / "classification.csv")
        result_path = write_classification_csv([rec], out)
        assert result_path == out
        with open(out) as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 2
        assert rows[0]["Reaction"] == "H+O2<=>O+OH"

    def test_round_trips_through_load_classification_file(self, tmp_path):
        """The real consumer: src/ActiveParameterScreen.py reads this CSV
        via interfaces.load_classification_file. Must not raise, and must
        produce the required columns."""
        from modules.interfaces import load_classification_file

        rec1 = _make_record("k1", "H+O2<=>O+OH", [500, 900, 1500], [1.4, 1.3, 1.1])
        rec2 = _make_record("k2", "H2O2(+M)<=>2OH(+M)", [500, 1500], [2.0, 1.5],
                             high_p_limit_only=True)
        out = str(tmp_path / "classification.csv")
        write_classification_csv([rec1, rec2], out)

        df = load_classification_file(out)
        assert "Reaction_ID" in df.columns
        assert "f" in df.columns
        assert len(df) > 0
        assert df["Reaction_ID"].is_unique
