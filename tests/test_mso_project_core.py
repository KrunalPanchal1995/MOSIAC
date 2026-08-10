"""
Tests for mso_project.project.Project: create/open/register/capture/scan/
list, and the "remembers on restart" contract (close + reopen).

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_mso_project_core.py -v
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.append(_SRC_DIR)

from mso_project import Project  # noqa: E402


class TestCreateOpen:
    def test_create_writes_manifest_and_db(self, tmp_path):
        proj_dir = tmp_path / "proj1"
        p = Project.create(str(proj_dir), name="Proj1", description="desc", tags=["a", "b"])
        assert (proj_dir / "project.yaml").is_file()
        assert (proj_dir / "artifacts.db").is_file()
        assert (proj_dir / "notes").is_dir()
        assert (proj_dir / "runs").is_dir()
        p.close()

    def test_create_twice_raises(self, tmp_path):
        proj_dir = tmp_path / "proj1"
        Project.create(str(proj_dir), name="Proj1").close()
        with pytest.raises(FileExistsError):
            Project.create(str(proj_dir), name="Proj1")

    def test_open_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            Project.open(str(tmp_path / "nope"))

    def test_remembers_on_restart(self, tmp_path):
        """The core contract: close the process (simulated by close()+
        Project.open() as a fresh object, no shared state), reopen, and
        every registered artifact is still there."""
        proj_dir = tmp_path / "proj1"
        p = Project.create(str(proj_dir), name="Proj1")
        f = tmp_path / "data.csv"
        f.write_text("a,b\n1,2\n")
        aid = p.register(str(f), role="test_data")
        p.close()

        p2 = Project.open(str(proj_dir))
        assert p2.info["name"] == "Proj1"
        arts = p2.list_artifacts()
        assert len(arts) == 1
        assert arts[0]["artifact_id"] == aid
        assert arts[0]["role"] == "test_data"
        p2.close()

    def test_context_manager(self, tmp_path):
        proj_dir = tmp_path / "proj1"
        with Project.create(str(proj_dir), name="Proj1") as p:
            f = tmp_path / "x.csv"
            f.write_text("a\n")
            p.register(str(f))
        # closed now; reopening must still see the artifact
        with Project.open(str(proj_dir)) as p2:
            assert len(p2.list_artifacts()) == 1


class TestRegister:
    def test_register_missing_file_raises(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="P")
        with pytest.raises(FileNotFoundError):
            p.register(str(tmp_path / "nope.csv"))
        p.close()

    def test_register_infers_kind_from_extension(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="P")
        f = tmp_path / "x.pkl"
        f.write_bytes(b"abc")
        aid = p.register(str(f))
        art = p.list_artifacts()[0]
        assert art["kind"] == "pkl"
        assert art["role"] == "unclassified"
        p.close()

    def test_register_same_path_updates_not_duplicates(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="P")
        f = tmp_path / "x.csv"
        f.write_text("a\n")
        id1 = p.register(str(f), role="role1")
        id2 = p.register(str(f), role="role2")
        assert id1 == id2
        arts = p.list_artifacts()
        assert len(arts) == 1
        assert arts[0]["role"] == "role2"
        p.close()

    def test_register_many_skips_missing(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="P")
        f1 = tmp_path / "a.csv"; f1.write_text("1\n")
        ids = p.register_many([str(f1), str(tmp_path / "missing.csv")])
        assert len(ids) == 1
        p.close()

    def test_set_report_include(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="P")
        f = tmp_path / "x.csv"; f.write_text("a\n")
        aid = p.register(str(f))
        p.set_report_include(aid, "exclude")
        assert p.list_artifacts()[0]["report_include"] == "exclude"
        with pytest.raises(ValueError):
            p.set_report_include(aid, "bogus")
        p.close()

    def test_list_artifacts_filters(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="P")
        f1 = tmp_path / "a.csv"; f1.write_text("1\n")
        f2 = tmp_path / "b.png"; f2.write_bytes(b"\x89PNG")
        p.register(str(f1), role="roleA", kind="csv")
        p.register(str(f2), role="roleB", kind="png")
        assert len(p.list_artifacts(role="roleA")) == 1
        assert len(p.list_artifacts(kind="png")) == 1
        assert len(p.list_artifacts()) == 2
        p.close()


class TestNotes:
    def test_add_note_writes_and_registers(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="P")
        aid = p.add_note("My Note", "Body **text**.")
        arts = p.list_artifacts()
        assert len(arts) == 1
        assert arts[0]["artifact_id"] == aid
        assert arts[0]["role"] == "user_note"
        assert os.path.isfile(arts[0]["path"])
        assert "Body **text**." in open(arts[0]["path"]).read()
        p.close()

    def test_add_note_dedup_slug(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="P")
        p.add_note("Same Title", "first")
        p.add_note("Same Title", "second")
        arts = p.list_artifacts()
        assert len(arts) == 2  # two distinct files, not overwritten
        p.close()


class TestCaptureAndScan:
    def test_capture_registers_new_files_with_roles(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="P")
        run_dir = tmp_path / "run1"
        run_dir.mkdir()
        with p.capture("run_script", "case1", str(run_dir)) as run_id:
            (run_dir / "unsrt.pkl").write_bytes(b"x")
            rs_dir = run_dir / "Opt" / "Data" / "ResponseSurface"
            rs_dir.mkdir(parents=True)
            (rs_dir / "responsecoef_case-0.csv").write_text("1.0\n")

        runs = p.list_runs()
        assert len(runs) == 1
        assert runs[0]["status"] == "done"
        assert runs[0]["run_id"] == run_id

        arts = {a["role"]: a for a in p.list_artifacts(run_id=run_id)}
        assert "uncertainty_cache" in arts
        assert "response_surface_coeff" in arts
        assert arts["uncertainty_cache"]["kind"] == "pkl"
        p.close()

    def test_capture_marks_failed_and_keeps_partial_artifacts(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="P")
        run_dir = tmp_path / "run_fail"
        run_dir.mkdir()
        with pytest.raises(RuntimeError):
            with p.capture("run_script", "will_fail", str(run_dir)) as run_id:
                (run_dir / "unsrt.pkl").write_bytes(b"partial")
                raise RuntimeError("boom")
        run = [r for r in p.list_runs() if r["run_id"] == run_id][0]
        assert run["status"] == "failed"
        assert len(p.list_artifacts(run_id=run_id)) == 1
        p.close()

    def test_capture_unrecognized_pipeline_falls_back_generic(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="P")
        run_dir = tmp_path / "run_unknown"
        run_dir.mkdir()
        with p.capture("totally_unknown_pipeline", "x", str(run_dir)):
            (run_dir / "something.csv").write_text("a\n")
        arts = p.list_artifacts()
        assert arts[0]["role"] == "unclassified"
        assert arts[0]["kind"] == "csv"
        p.close()

    def test_scan_retro_imports_with_unknown_status(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="P")
        pre_existing = tmp_path / "pre_existing_run"
        pre_existing.mkdir()
        (pre_existing / "Opt" / "Data" / "Simulations").mkdir(parents=True)
        (pre_existing / "Opt" / "Data" / "Simulations" / "sim_data_case-1.lst").write_text("x\n")

        ids = p.scan(str(pre_existing), pipeline="run_script")
        assert len(ids) == 1
        runs = p.list_runs()
        assert len(runs) == 1
        assert runs[0]["status"] == "unknown"
        p.close()

    def test_scan_with_existing_run_id_attaches_no_new_run_row(self, tmp_path):
        p = Project.create(str(tmp_path / "proj"), name="P")
        run_dir = tmp_path / "run1"
        run_dir.mkdir()
        with p.capture("run_script", "case1", str(run_dir)) as run_id:
            (run_dir / "unsrt.pkl").write_bytes(b"x")
        (run_dir / "targets.csv").write_text("a\n")
        p.scan(str(run_dir), pipeline="run_script", run_id=run_id)
        assert len(p.list_runs()) == 1  # no second run row created
        assert len(p.list_artifacts(run_id=run_id)) == 2
        p.close()
