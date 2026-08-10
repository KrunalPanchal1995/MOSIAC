"""
Subprocess smoke tests for `python -m mso_project <subcommand>`, mirroring
tests/test_mso_compare_gui.py's --no-gui subprocess pattern.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_mso_project_cli.py -v
"""
import os
import subprocess
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_ROOT, "src")


def _run(args, cwd=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = _SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "mso_project"] + args,
        capture_output=True, text=True, timeout=60, cwd=cwd, env=env)


class TestNoArgs:
    def test_no_subcommand_prints_help(self):
        proc = _run([])
        assert proc.returncode == 0
        assert "subcommand" in proc.stdout.lower() or "usage" in proc.stdout.lower()


class TestInitRegisterListArtifacts:
    def test_full_cycle(self, tmp_path):
        proj_dir = str(tmp_path / "proj")
        proc = _run(["init", proj_dir, "--name", "CLIProj", "--description", "d"])
        assert proc.returncode == 0
        assert os.path.isfile(os.path.join(proj_dir, "project.yaml"))

        data_file = tmp_path / "data.csv"
        data_file.write_text("a,b\n1,2\n")
        proc = _run(["register", proj_dir, str(data_file), "--role", "test_data"])
        assert proc.returncode == 0
        assert "Registered artifact_id=1" in proc.stdout

        proc = _run(["list-artifacts", proj_dir])
        assert proc.returncode == 0
        assert "test_data" in proc.stdout
        assert str(data_file) in proc.stdout


class TestNote:
    def test_note_from_body_file(self, tmp_path):
        proj_dir = str(tmp_path / "proj")
        _run(["init", proj_dir, "--name", "P"])
        body_file = tmp_path / "body.md"
        body_file.write_text("Some note body.\n")
        proc = _run(["note", proj_dir, "My Title", "--body-file", str(body_file)])
        assert proc.returncode == 0
        assert "Added note" in proc.stdout


class TestScan:
    def test_scan_registers_files_in_directory(self, tmp_path):
        proj_dir = str(tmp_path / "proj")
        _run(["init", proj_dir, "--name", "P"])
        scan_dir = tmp_path / "existing_run"
        scan_dir.mkdir()
        (scan_dir / "unsrt.pkl").write_bytes(b"x")
        proc = _run(["scan", proj_dir, str(scan_dir), "--pipeline", "run_script"])
        assert proc.returncode == 0
        assert "Registered 1 artifact" in proc.stdout


class TestCapture:
    def test_capture_wraps_subprocess_and_registers_output(self, tmp_path):
        proj_dir = str(tmp_path / "proj")
        _run(["init", proj_dir, "--name", "P"])
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        proc = _run([
            "capture", proj_dir, "run_script", "case1", str(work_dir), "--",
            sys.executable, "-c",
            f"open(r'{work_dir / 'unsrt.pkl'}', 'wb').write(b'x')",
        ])
        assert proc.returncode == 0
        assert "Capturing run_id=" in proc.stdout

        proc = _run(["list-runs", proj_dir])
        assert "run_script" in proc.stdout
        assert "case1" in proc.stdout
        assert "done" in proc.stdout

    def test_capture_without_dashdash_command_errors(self, tmp_path):
        proj_dir = str(tmp_path / "proj")
        _run(["init", proj_dir, "--name", "P"])
        proc = _run(["capture", proj_dir, "run_script", "case1", str(tmp_path)])
        assert proc.returncode == 2
        assert "requires a command" in proc.stderr


class TestResume:
    def test_resume_materializes_files(self, tmp_path):
        proj_dir = str(tmp_path / "proj")
        _run(["init", proj_dir, "--name", "P"])
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        _run([
            "capture", proj_dir, "run_script", "case1", str(work_dir), "--",
            sys.executable, "-c",
            f"open(r'{work_dir / 'unsrt.pkl'}', 'wb').write(b'x')",
        ])
        proc = _run(["list-runs", proj_dir])
        run_id = proc.stdout.strip().split("\n")[0].split("\t")[0]

        target_dir = tmp_path / "resumed"
        proc = _run(["resume", proj_dir, run_id, str(target_dir)])
        assert proc.returncode == 0
        assert os.path.isfile(target_dir / "unsrt.pkl")


class TestReport:
    def test_report_builds_files(self, tmp_path):
        proj_dir = str(tmp_path / "proj")
        _run(["init", proj_dir, "--name", "P"])
        proc = _run(["report", proj_dir])
        assert proc.returncode == 0
        assert "Main report:" in proc.stdout
        assert "Notebook:" in proc.stdout
