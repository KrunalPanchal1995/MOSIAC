"""
Tests for mso_io.postprocess_base -- the shared "process the results" CLI
contract every repo's postprocess() (VisualAid.py, uq_plots.py, plots.py,
run_plots.py, prs_report.py, rmip/postprocess.py) builds on.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_postprocess_base.py -v
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.append(_SRC_DIR)

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from mso_io.postprocess_base import (  # noqa: E402
    PostProcessResult, add_postprocess_args, default_out_dir, discover,
    formats_from_args, save_figure, write_manifest, write_table,
)


class TestCliContract:
    def test_add_postprocess_args_registers_all_shared_flags(self):
        import argparse
        parser = argparse.ArgumentParser()
        add_postprocess_args(parser)
        args = parser.parse_args([
            "--postprocess", "/some/run", "--out", "/some/out",
            "--journal", "--csv-only", "--formats", "png,pdf", "--intermediate",
        ])
        assert args.postprocess == "/some/run"
        assert args.out == "/some/out"
        assert args.journal is True
        assert args.csv_only is True
        assert args.intermediate is True
        assert formats_from_args(args) == ["png", "pdf"]

    def test_flags_default_off(self):
        import argparse
        parser = argparse.ArgumentParser()
        add_postprocess_args(parser)
        args = parser.parse_args([])
        assert args.postprocess is None
        assert args.journal is False
        assert args.csv_only is False
        assert args.intermediate is False
        assert formats_from_args(args) == ["png"]


class TestSaveFigure:
    def test_csv_always_written_even_without_explicit_dataframe(self, tmp_path):
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [4, 5, 6], label="y")
        written = save_figure(fig, "test", tmp_path, formats=["png"])
        assert "csv" in written
        assert os.path.isfile(written["csv"])
        assert os.path.isfile(written["png"])
        plt.close(fig)

    def test_csv_written_from_explicit_dataframe(self, tmp_path):
        fig, ax = plt.subplots()
        df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
        written = save_figure(fig, "explicit", tmp_path, formats=["png"], df=df)
        loaded = pd.read_csv(written["csv"])
        assert list(loaded["x"]) == [1, 2]
        plt.close(fig)

    def test_csv_only_skips_image_but_not_csv(self, tmp_path):
        fig, ax = plt.subplots()
        ax.plot([1, 2], [3, 4])
        written = save_figure(fig, "test", tmp_path, formats=["png"], csv_only=True)
        assert "csv" in written and os.path.isfile(written["csv"])
        assert "png" not in written
        assert not os.path.isfile(tmp_path / "test.png")
        plt.close(fig)


class TestDiscover:
    def test_returns_empty_list_not_error_for_missing_pattern(self, tmp_path):
        (tmp_path / "a.csv").write_text("x\n1\n")
        found = discover(tmp_path, {"csvs": "*.csv", "missing": "*.doesnotexist"})
        assert len(found["csvs"]) == 1
        assert found["missing"] == []

    def test_tolerant_of_nonexistent_run_dir(self, tmp_path):
        """The --intermediate contract: a run directory that doesn't exist
        yet (pipeline hasn't started writing) must not raise."""
        found = discover(tmp_path / "does_not_exist_yet", {"csvs": "*.csv"})
        assert found["csvs"] == []


class TestManifestAndTable:
    def test_write_manifest_round_trips(self, tmp_path):
        result = PostProcessResult(run_dir=str(tmp_path), out_dir=str(tmp_path),
                                    figures=["a.png"], tables=["b.csv"], partial=True)
        path = write_manifest(result, tmp_path)
        assert os.path.isfile(path)
        import json
        data = json.loads(open(path).read())
        assert data["partial"] is True
        assert data["figures"] == ["a.png"]

    def test_write_table_creates_csv(self, tmp_path):
        df = pd.DataFrame({"a": [1, 2, 3]})
        path = write_table(df, "mytable", tmp_path)
        assert os.path.isfile(path)
        assert path.endswith("mytable.csv")


def test_default_out_dir_falls_back_to_postprocess_subdir(tmp_path):
    assert str(default_out_dir(tmp_path, None)) == str(tmp_path / "postprocess")
    assert str(default_out_dir(tmp_path, "/explicit/out")) == "/explicit/out"
