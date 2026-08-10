"""
Tests for the per-repo postprocess() CLI contract (2026-08 workbench audit,
task 3): every one of these implements mso_io.postprocess_base's shared
--postprocess/--out/--journal/--csv-only/--formats/--intermediate flags and
never raises on an empty/partial run directory.

MUQ-SAC/ and Sensitivity_Analysis/ both name their module VisualAid.py --
imported here via importlib against an explicit file path (rather than
sys.path tricks that would collide the two same-named modules) the same way
run_script.py imports its own sibling VisualAid.py by bare name from its own
directory.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_repo_postprocessors.py -v
"""
import importlib.util
import os
import shutil
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.append(_SRC_DIR)

pd = pytest.importorskip("pandas")


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def muqsac_visualaid():
    path = os.path.join(_SRC_DIR, "MUQ-SAC", "VisualAid.py")
    sys.path.insert(0, os.path.dirname(path))
    try:
        yield _load_module("_test_muqsac_visualaid", path)
    finally:
        sys.path.remove(os.path.dirname(path))


@pytest.fixture
def sens_visualaid():
    path = os.path.join(_SRC_DIR, "Sensitivity_Analysis", "VisualAid.py")
    sys.path.insert(0, os.path.dirname(path))
    try:
        yield _load_module("_test_sens_visualaid", path)
    finally:
        sys.path.remove(os.path.dirname(path))


class TestMuqSacPostprocess:
    def test_empty_run_dir_degrades_cleanly(self, muqsac_visualaid, tmp_path):
        result = muqsac_visualaid.postprocess(str(tmp_path), journal=True)
        assert result.figures == []
        assert result.tables == []
        assert any("posterior plots" in s for s in result.skipped)
        assert os.path.isfile(result.manifest_path)

    def test_intermediate_flag_changes_skip_wording(self, muqsac_visualaid, tmp_path):
        result = muqsac_visualaid.postprocess(str(tmp_path), intermediate=True)
        assert result.partial is True
        assert any("not yet at that stage" in s for s in result.skipped)

    def test_prediction_errors_csv_always_relocated(self, muqsac_visualaid, tmp_path):
        pd.DataFrame({"case": [1, 2], "mre": [3.0, 4.0]}).to_csv(
            tmp_path / "Prediction_errors.csv", index=False)
        result = muqsac_visualaid.postprocess(str(tmp_path), journal=True)
        assert len(result.tables) == 1
        assert len(result.journal_tables) == 1
        assert os.path.isfile(result.tables[0])


class TestSensitivityAnalysisPostprocess:
    def test_empty_run_dir_degrades_cleanly(self, sens_visualaid, tmp_path):
        result = sens_visualaid.postprocess(str(tmp_path), journal=True)
        assert result.figures == []
        assert any("no sens_parameters.pkl" in s for s in result.skipped)


@pytest.fixture
def uq_plots():
    # NOT `from forward_uq import uq_plots` -- a top-level forward_uq.py
    # script at repo root shadows the src/forward_uq/ package whenever repo
    # root precedes src/ on sys.path (same class of collision as the
    # documented `io` package-shadowing risk this repo's root conftest.py
    # already works around; see MarkDownFiles workbench audit). Loading the
    # leaf module directly from its own directory sidesteps it, matching
    # how postprocess_dispatch.py's subprocess invocation (direct file
    # path, not a package import) is unaffected in production.
    pkg_dir = os.path.join(_SRC_DIR, "forward_uq")
    sys.path.insert(0, pkg_dir)
    try:
        yield _load_module("_test_uq_plots", os.path.join(pkg_dir, "uq_plots.py"))
    finally:
        sys.path.remove(pkg_dir)


class TestForwardUqPostprocess:
    def test_empty_and_populated_run_dir(self, uq_plots, tmp_path):
        result = uq_plots.postprocess(str(tmp_path))
        assert any("no forward_uq_statistics.csv" in s for s in result.skipped)

        pd.DataFrame([{"dataset_id": "ds1", "covered_90": 1}]).to_csv(
            tmp_path / "forward_uq_statistics.csv", index=False)
        result2 = uq_plots.postprocess(str(tmp_path), journal=True)
        assert len(result2.tables) == 1
        assert len(result2.journal_tables) == 1


class TestGraphSaPostprocess:
    def test_no_db_degrades_cleanly(self, tmp_path):
        from graph_sa import plots
        pd.DataFrame([{"formula": "H+O2=O+OH", "score_norm": 0.9}]).to_csv(
            tmp_path / "sensitive_reactions.csv", index=False)
        result = plots.postprocess(str(tmp_path), journal=True)
        assert len(result.tables) == 1
        assert any("no graph_sa.db" in s for s in result.skipped)


class TestMsoComparePostprocess:
    def test_no_phi_folders_degrades_cleanly(self, tmp_path):
        from mso_compare import run_plots
        result = run_plots.postprocess(str(tmp_path))
        assert any("no phi_*/" in s for s in result.skipped)

    def test_phi_folder_produces_real_plots(self, tmp_path):
        from mso_compare import run_plots
        phi_dir = tmp_path / "phi_1_0"
        phi_dir.mkdir()
        pd.DataFrame({"T_K": [900, 1000], "tau_exp": [500, 300],
                      "tau_nominal": [520, 310]}).to_csv(
            phi_dir / "Phi_1_0_P_10.csv", index=False)
        result = run_plots.postprocess(str(tmp_path), journal=True)
        assert len(result.tables) == 1
        assert len(result.figures) >= 1
        assert len(result.journal_tables) == 1


class TestRmipPostprocess:
    FIXTURE_DB = os.path.join(
        _SRC_DIR, "rmip", "tests", "fixtures", "gui_stress", "project.db")

    def test_no_db_degrades_cleanly(self, tmp_path):
        from rmip import postprocess as rmip_pp
        result = rmip_pp.postprocess(str(tmp_path))
        assert any("no *.db found" in s for s in result.skipped)

    @pytest.mark.skipif(not os.path.isfile(FIXTURE_DB), reason="gui_stress fixture DB not present")
    def test_real_fixture_db_produces_full_report(self, tmp_path):
        from rmip import postprocess as rmip_pp
        shutil.copy(self.FIXTURE_DB, tmp_path / "project.db")
        result = rmip_pp.postprocess(str(tmp_path), journal=True)
        assert not result.skipped
        table_names = {os.path.basename(t) for t in result.tables}
        assert "mechanisms.csv" in table_names
        assert "quality_score.csv" in table_names
        assert len(result.journal_tables) == len(result.tables)


class TestPrsReportPostprocess:
    def test_unknown_fuel_raises_valueerror(self):
        from automation import prs_report
        with pytest.raises(ValueError):
            prs_report.postprocess("not_a_real_fuel")
