"""
Tests for mso_project.restore.resume(): copy-vs-link materialization, and
the safety property the "copy by default" decision exists for -- a
run_script.py-style in-place rewrite/rmtree on the materialized COPY must
never touch the project's own stored original.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_mso_project_restore.py -v
"""
import os
import shutil
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.append(_SRC_DIR)

from mso_project import Project  # noqa: E402
from mso_project.restore import UNSAFE_TO_LINK_ROLES  # noqa: E402


def _make_captured_run(tmp_path):
    p = Project.create(str(tmp_path / "proj"), name="P")
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    with p.capture("run_script", "case1", str(run_dir)) as run_id:
        (run_dir / "unsrt.pkl").write_bytes(b"pickled")
        rs_dir = run_dir / "Opt" / "Data" / "ResponseSurface"
        rs_dir.mkdir(parents=True)
        (rs_dir / "responsecoef_case-0.csv").write_text("1.0\n2.0\n")
    return p, run_id, run_dir


class TestResumeCopy:
    def test_materializes_at_same_relative_layout(self, tmp_path):
        p, run_id, run_dir = _make_captured_run(tmp_path)
        target = tmp_path / "resumed"
        materialized = p.resume(run_id, str(target), mode="copy")
        assert "unsrt.pkl" in materialized
        assert "Opt/Data/ResponseSurface/responsecoef_case-0.csv" in materialized
        assert (target / "unsrt.pkl").is_file()
        assert (target / "Opt" / "Data" / "ResponseSurface" / "responsecoef_case-0.csv").is_file()
        p.close()

    def test_copy_protects_original_from_in_place_rewrite(self, tmp_path):
        """The core safety property copy-by-default exists for."""
        p, run_id, run_dir = _make_captured_run(tmp_path)
        target = tmp_path / "resumed"
        p.resume(run_id, str(target), mode="copy")

        rs_file = target / "Opt" / "Data" / "ResponseSurface" / "responsecoef_case-0.csv"
        rs_file.unlink()
        rs_file.write_text("REWRITTEN\n")

        original = run_dir / "Opt" / "Data" / "ResponseSurface" / "responsecoef_case-0.csv"
        assert original.read_text() == "1.0\n2.0\n"
        p.close()

    def test_copy_protects_original_from_rmtree(self, tmp_path):
        """run_script.py's Bug-4 completeness check can shutil.rmtree() the
        whole Perturbed_Mech directory -- confirm that surviving even a
        directory-level deletion on the copy leaves the original alone."""
        p = Project.create(str(tmp_path / "proj"), name="P")
        run_dir = tmp_path / "run1"
        run_dir.mkdir()
        pm_dir = run_dir / "Perturbed_Mech"
        pm_dir.mkdir()
        (pm_dir / "mechanism_0.yaml").write_text("nominal: true\n")
        with p.capture("run_script", "case1", str(run_dir)) as run_id:
            pass  # files already exist before capture -- use scan semantics instead
        p.scan(str(run_dir), pipeline="run_script", run_id=run_id)

        target = tmp_path / "resumed"
        p.resume(run_id, str(target), mode="copy")
        shutil.rmtree(target / "Perturbed_Mech")

        assert (pm_dir / "mechanism_0.yaml").is_file()
        assert (pm_dir / "mechanism_0.yaml").read_text() == "nominal: true\n"
        p.close()


class TestResumeLink:
    def test_link_creates_symlinks(self, tmp_path):
        p, run_id, run_dir = _make_captured_run(tmp_path)
        target = tmp_path / "resumed_link"
        p.resume(run_id, str(target), mode="link")
        assert (target / "unsrt.pkl").is_symlink()
        p.close()

    def test_link_warns_for_unsafe_roles(self, tmp_path, capsys):
        p, run_id, run_dir = _make_captured_run(tmp_path)
        target = tmp_path / "resumed_link"
        p.resume(run_id, str(target), mode="link")
        captured = capsys.readouterr()
        assert "response_surface_coeff" in captured.err
        assert "rewritten/deleted in place" in captured.err
        p.close()

    def test_unsafe_roles_set_matches_known_run_script_roles(self):
        assert "response_surface_coeff" in UNSAFE_TO_LINK_ROLES
        assert "perturbed_mechanism" in UNSAFE_TO_LINK_ROLES


class TestResumeErrors:
    def test_unknown_run_id_raises(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="P")
        with pytest.raises(ValueError):
            p.resume("nonexistent-run-id", str(tmp_path / "out"))
        p.close()

    def test_invalid_mode_raises(self, tmp_path):
        p, run_id, run_dir = _make_captured_run(tmp_path)
        with pytest.raises(ValueError):
            p.resume(run_id, str(tmp_path / "out"), mode="bogus")
        p.close()

    def test_missing_source_file_skipped_not_fatal(self, tmp_path):
        p, run_id, run_dir = _make_captured_run(tmp_path)
        (run_dir / "unsrt.pkl").unlink()  # delete after capture, before resume
        materialized = p.resume(run_id, str(tmp_path / "resumed"))
        assert "unsrt.pkl" not in materialized
        p.close()
