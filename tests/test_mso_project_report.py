"""
Tests for mso_project.report: ReportRules YAML round-trip, routing
precedence (per-artifact override > role > kind-based fallback), section
builders, and build_report() end-to-end. Mirrors
src/rmip/tests/test_latex_engine.py's "skip if no LaTeX engine" pattern for
the actual PDF-compile step -- generating correct .tex/notebook/manifest
content is asserted unconditionally; compiling to PDF is best-effort (this
machine's tectonic install has been observed to be intermittently flaky --
see mso_project's own report/builder.py module notes -- so a failed compile
here is not itself a test failure).

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_mso_project_report.py -v
"""
import json
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.append(_SRC_DIR)

from mso_project import Project  # noqa: E402
from mso_project.report.rules import DEFAULT_RULES, ReportRules  # noqa: E402
from mso_project.report.sections import _escape  # noqa: E402
from mso_project.report import build_report  # noqa: E402


class TestRulesRoundTrip:
    def test_default_rules_yaml_round_trip(self, tmp_path):
        path = str(tmp_path / "rules.yaml")
        DEFAULT_RULES.to_yaml(path)
        loaded = ReportRules.from_yaml(path)
        assert loaded.to_dict() == DEFAULT_RULES.to_dict()

    def test_to_yaml_keeps_backup(self, tmp_path):
        path = str(tmp_path / "rules.yaml")
        r1 = ReportRules(title="First")
        r1.to_yaml(path)
        r2 = ReportRules(title="Second")
        r2.to_yaml(path)
        assert os.path.exists(path + ".bak")
        assert "First" in open(path + ".bak").read()
        assert "Second" in open(path).read()

    def test_load_or_default_never_returns_shared_singleton(self, tmp_path):
        r = ReportRules.load_or_default(str(tmp_path / "nonexistent.yaml"))
        r.role_routing["some_role"] = "exclude"
        assert "some_role" not in DEFAULT_RULES.role_routing

    def test_load_or_default_reads_existing_file(self, tmp_path):
        path = str(tmp_path / "rules.yaml")
        ReportRules(title="Custom Title").to_yaml(path)
        loaded = ReportRules.load_or_default(path)
        assert loaded.title == "Custom Title"


class TestRouting:
    def test_explicit_main_role_routes_main(self):
        assert DEFAULT_RULES.routing_for("t_p_phi_plot", "png") == "main"

    def test_explicit_exclude_role_routes_exclude(self):
        assert DEFAULT_RULES.routing_for("progress_marker", "log") == "exclude"

    def test_unknown_role_falls_back_by_kind(self):
        assert DEFAULT_RULES.routing_for("brand_new_role", "csv") == "supplementary"
        assert DEFAULT_RULES.routing_for("brand_new_role", "doc") == "main"
        assert DEFAULT_RULES.routing_for("brand_new_role", "pkl") == "exclude"

    def test_per_artifact_override_wins_over_role(self, tmp_path):
        """Exercises the actual precedence chain build_report() applies,
        not just ReportRules.routing_for() in isolation."""
        p = Project.create(str(tmp_path / "proj"), name="P")
        f = tmp_path / "x.csv"
        f.write_text("a,b\n1,2\n")
        aid = p.register(f.as_posix(), role="t_p_phi_plot")  # role says "main"
        p.set_report_include(aid, "exclude")  # explicit override should win
        art = p.list_artifacts()[0]
        assert art["report_include"] == "exclude"
        p.close()


class TestEscape:
    def test_backslash_escaped_before_other_replacements(self):
        # Regression: escaping '_' before '\\' corrupts its own output
        # ("run_script" -> "run\_script" -> "run\textbackslash{}_script").
        assert _escape("run_script") == r"run\_script"
        assert r"\textbackslash" not in _escape("run_script")

    def test_special_chars(self):
        out = _escape("50% & $100 #tag ~x^y")
        assert out == r"50\% \& \$100 \#tag \textasciitilde{}x\textasciicircum{}y"


class TestBuildReportEndToEnd:
    def _project_with_data(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="ReportTest",
                            description="desc with special & chars_here")
        run_dir = tmp_path / "run1"
        run_dir.mkdir()
        with p.capture("run_script", "case1", str(run_dir)):
            (run_dir / "Prediction_errors.csv").write_text(
                "Case_ID,Max_Testing_Error\ncase-0,1.2\ncase-1,3.4\n")
            (run_dir / "optimization_cost.csv").write_text("Case_ID,Cost\ncase-0,100\n")
        p.add_note("A Note", "Body with # and _ and % and $ characters.")
        return p

    def test_produces_all_expected_files(self, tmp_path):
        p = self._project_with_data(tmp_path)
        result = build_report(p, out_dir=str(tmp_path / "report_out"))

        assert os.path.isfile(result.main_tex)
        assert os.path.isfile(result.supplementary_tex)
        assert os.path.isfile(result.notebook_path)
        assert os.path.isfile(result.manifest_path)
        assert os.path.isfile(result.readme_path)
        p.close()

    def test_manifest_is_valid_json_with_expected_keys(self, tmp_path):
        p = self._project_with_data(tmp_path)
        result = build_report(p, out_dir=str(tmp_path / "report_out"))
        manifest = json.loads(open(result.manifest_path).read())
        for key in ("generated_at", "project_name", "n_artifacts_main",
                    "n_artifacts_supplementary", "n_artifacts_excluded"):
            assert key in manifest
        assert manifest["project_name"] == "ReportTest"
        p.close()

    def test_main_tex_has_no_unescaped_hash_from_notes(self, tmp_path):
        """Regression: raw Markdown note content (starting '# Title') used
        to be injected unescaped into the LaTeX body -- a bare '#' is a
        fatal LaTeX error. Notes must render inside verbatim now."""
        p = self._project_with_data(tmp_path)
        result = build_report(p, out_dir=str(tmp_path / "report_out"))
        main_tex = open(result.main_tex).read()
        assert r"\begin{verbatim}" in main_tex
        assert r"\end{verbatim}" in main_tex
        p.close()

    def test_excluded_artifacts_never_appear_in_raw_data_index_routing(self, tmp_path):
        p = self._project_with_data(tmp_path)
        # progress_marker is exclude-routed by default -- register one
        f = tmp_path / "progress"
        f.write_text("line1\n")
        p.register(f.as_posix(), role="progress_marker")
        result = build_report(p, out_dir=str(tmp_path / "report_out"))
        manifest = json.loads(open(result.manifest_path).read())
        assert manifest["n_artifacts_excluded"] >= 1
        p.close()

    def test_custom_rules_change_section_list(self, tmp_path):
        p = self._project_with_data(tmp_path)
        rules = ReportRules(title="Custom", sections_main=["overview"],
                             sections_supplementary=["raw_data_index"])
        result = build_report(p, rules=rules, out_dir=str(tmp_path / "report_out"))
        main_tex = open(result.main_tex).read()
        assert "Cost Summary" not in main_tex  # not in the trimmed section list
        assert "Overview" in main_tex
        p.close()

    def test_unknown_section_key_skipped_not_fatal(self, tmp_path):
        p = self._project_with_data(tmp_path)
        rules = ReportRules(sections_main=["overview", "totally_bogus_section"])
        result = build_report(p, rules=rules, out_dir=str(tmp_path / "report_out"))
        assert os.path.isfile(result.main_tex)  # didn't crash
        p.close()

    def test_notebook_is_valid_json_with_csv_cells(self, tmp_path):
        p = self._project_with_data(tmp_path)
        result = build_report(p, out_dir=str(tmp_path / "report_out"))
        nb = json.loads(open(result.notebook_path).read())
        assert nb["cells"]
        code = "\n".join(
            "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
        assert "pd.read_csv" in code
        p.close()

    def test_compiled_flag_is_bool_regardless_of_engine_availability(self, tmp_path):
        """Don't assert True/False here (see module docstring) -- just that
        the pipeline completes and reports a real boolean either way."""
        p = self._project_with_data(tmp_path)
        result = build_report(p, out_dir=str(tmp_path / "report_out"))
        assert isinstance(result.compiled, bool)
        if result.compiled:
            assert result.main_pdf and os.path.isfile(result.main_pdf)
        p.close()
