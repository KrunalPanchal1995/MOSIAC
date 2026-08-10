"""
Tests for mso_studio.core.rmg -- the RMG-Py subprocess adapter (2026-08
workbench audit, helper-package gap #4). No Qt import here (core/ rule),
and no test requires rmg_env/RMG-Py to actually be installed -- every path
must degrade to a clear, non-raising (available, reason) instead.
"""
from mso_studio.core import rmg as rmg_core


def test_rmg_available_never_raises():
    available, reason = rmg_core.rmg_available()
    assert isinstance(available, bool)
    assert isinstance(reason, str) and reason


def test_default_rmg_python_env_override(monkeypatch, tmp_path):
    fake_python = tmp_path / "python"
    fake_python.write_text("#!/bin/sh\n")
    fake_python.chmod(0o755)
    monkeypatch.setenv("MSO_STUDIO_RMG_PYTHON", str(fake_python))
    assert rmg_core._default_rmg_python() == str(fake_python)


def test_default_rmg_python_missing_override_falls_through(monkeypatch):
    monkeypatch.setenv("MSO_STUDIO_RMG_PYTHON", "/no/such/interpreter")
    # Falls through to the real candidate search (may or may not find one
    # on this machine) -- must not raise or return the bogus override path.
    result = rmg_core._default_rmg_python()
    assert result != "/no/such/interpreter"


def test_default_rmg_script_env_override(monkeypatch, tmp_path):
    fake_script = tmp_path / "rmg.py"
    fake_script.write_text("# fake\n")
    monkeypatch.setenv("MSO_STUDIO_RMG_SCRIPT", str(fake_script))
    assert rmg_core._default_rmg_script() == str(fake_script)


def test_rmg_available_false_when_no_python_found(monkeypatch):
    monkeypatch.setattr(rmg_core, "_default_rmg_python", lambda: None)
    available, reason = rmg_core.rmg_available()
    assert available is False
    assert "rmg_env" in reason


def test_rmg_available_false_when_python_found_but_no_script(monkeypatch):
    monkeypatch.setattr(rmg_core, "_default_rmg_python", lambda: "/usr/bin/python3")
    monkeypatch.setattr(rmg_core, "_default_rmg_script", lambda: None)
    available, reason = rmg_core.rmg_available()
    assert available is False
    assert "rmg.py" in reason


def test_run_rmg_job_raises_cleanly_when_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(rmg_core, "_default_rmg_python", lambda: None)
    input_py = tmp_path / "input.py"
    input_py.write_text("# fake rmg input\n")
    try:
        rmg_core.run_rmg_job(str(input_py))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "not available" in str(exc)


def test_import_rmg_mechanism_missing_dir_returns_all_none(tmp_path):
    result = rmg_core.import_rmg_mechanism(str(tmp_path / "no_such_output"))
    assert result == {"mechanism": None, "species_dictionary": None, "cantera_yaml": None}


def test_import_rmg_mechanism_finds_real_files(tmp_path):
    chem_dir = tmp_path / "chemkin"
    chem_dir.mkdir()
    (chem_dir / "chem_annotated.inp").write_text("! fake mechanism\n")
    (chem_dir / "species_dictionary.txt").write_text("! fake species dict\n")
    result = rmg_core.import_rmg_mechanism(str(tmp_path))
    assert result["mechanism"] == str(chem_dir / "chem_annotated.inp")
    assert result["species_dictionary"] == str(chem_dir / "species_dictionary.txt")
    assert result["cantera_yaml"] is None


def test_rmgpy_version_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(rmg_core, "_default_rmg_python", lambda: None)
    assert rmg_core.rmgpy_version() is None
