"""
Tests for KRUNAL_JULY_23.md point 1 -- run-status export.

Covers the framework-free core (mso_io.run_status.RunStatusReport) fully,
and a light smoke test of the shared Tkinter button
(gui_common.run_status_export.add_export_button) -- same "real tk.Tk()
root, no synthetic clicks" convention already used by
src/rmip/tests/test_gui_stress_sweep.py for widget-construction checks.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_run_status.py -v
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from mso_io.run_status import RunStatusReport


class TestRunStatusReportText:
    def test_to_text_includes_all_sections(self):
        report = RunStatusReport(
            tool="Mechanism Converter",
            inputs={"mechanism (.inp)": "/data/128-957.inp",
                    "thermo (.dat)": "/data/128-957.dat"},
            output_dir="/data/outputs/converted",
            options={"Auto-fix Fortran exponents": True, "--permissive": True},
            status="failed",
            summary="ck2yaml failed (exit 1)",
            log="ERROR: Unable to parse ...\nline 484: ...",
        )
        text = report.to_text()
        assert "Mechanism Converter" in text
        assert "/data/128-957.inp" in text
        assert "/data/outputs/converted" in text
        assert "Auto-fix Fortran exponents" in text and "True" in text
        assert "ck2yaml failed (exit 1)" in text
        assert "ERROR: Unable to parse" in text
        assert "Status" in text and "failed" in text

    def test_to_text_omits_empty_sections(self):
        report = RunStatusReport(tool="X", status="unknown")
        text = report.to_text()
        assert "Inputs" not in text
        assert "Output location" not in text
        assert "Options selected" not in text
        assert "Output / errors" not in text
        # header/status always present
        assert "X — run status" in text
        assert "Status    : unknown" in text

    def test_generated_at_defaults_to_now_iso(self):
        r1 = RunStatusReport(tool="X")
        assert r1.generated_at  # non-empty
        assert "T" in r1.generated_at  # ISO-8601 date/time separator

    def test_write_txt_creates_parent_dirs_and_file(self, tmp_path):
        report = RunStatusReport(tool="X", status="success")
        out = tmp_path / "sub" / "dir" / "status.txt"
        written = report.write_txt(str(out))
        assert written == out
        assert out.exists()
        assert "X — run status" in out.read_text()


class TestFromRunRecord:
    """Duck-typed against mso_studio.core.runrecord.RunRecord's real shape --
    imports it directly here (test-only) to prove the duck-typing actually
    matches the real class, without mso_io.run_status itself depending on
    mso_studio (it must stay importable from the plain-anaconda Tkinter
    apps, which never have PySide6/mso_studio on their path)."""

    def test_from_real_run_record(self, tmp_path):
        pytest.importorskip("mso_studio")
        from mso_studio.core.runrecord import RunConfig, new_record

        cfg = RunConfig(
            module="nominal_sim", label="htc_case",
            inputs={"mechanism": "/data/mech.yaml"},
            parameters={"solver": "cantera"},
            working_dir=str(tmp_path),
        )
        record = new_record(cfg)
        record.mark_finished("done", return_code=0)
        record.log_tail = ["line 1", "line 2"]

        report = RunStatusReport.from_run_record(record)
        assert report.tool == "nominal_sim"
        assert report.inputs == {"mechanism": "/data/mech.yaml"}
        assert report.output_dir == str(tmp_path)
        assert report.options["solver"] == "cantera"
        assert "wall_time_s" in report.options
        assert report.status == "done"
        assert report.summary is None                # no error on success
        assert "line 1" in report.log and "line 2" in report.log

    def test_from_real_run_record_failed_includes_error_summary(self, tmp_path):
        pytest.importorskip("mso_studio")
        from mso_studio.core.runrecord import RunConfig, new_record

        cfg = RunConfig(module="sensitivity", label="case1", working_dir=str(tmp_path))
        record = new_record(cfg)
        record.mark_finished("failed", return_code=1, error="solver crashed")

        report = RunStatusReport.from_run_record(record)
        assert report.status == "failed"
        assert report.summary == "solver crashed"


class TestAddExportButtonSmoke:
    """Real tk.Tk() root, no synthetic clicks -- same convention as
    test_gui_stress_sweep.py's widget-construction checks."""

    def test_button_constructed_with_expected_text(self):
        tk = pytest.importorskip("tkinter")
        from gui_common.run_status_export import add_export_button

        root = tk.Tk()
        try:
            btn = add_export_button(root, lambda: RunStatusReport(tool="X"))
            assert btn.cget("text") == "Export run status…"
        finally:
            root.destroy()

    def test_custom_button_text(self):
        tk = pytest.importorskip("tkinter")
        from gui_common.run_status_export import add_export_button

        root = tk.Tk()
        try:
            btn = add_export_button(root, lambda: RunStatusReport(tool="X"),
                                    text="Save status…")
            assert btn.cget("text") == "Save status…"
        finally:
            root.destroy()
