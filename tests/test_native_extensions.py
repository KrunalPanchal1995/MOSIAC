"""
Tests for src/mso_io/native_extensions.py (KRUNAL_JULY_23.md point 8 --
".so file generator"). The original plan assumed source might not exist at
all; it does (config_tools/), so this module discovers it + builds the
rebuild command rather than fabricating a build system from scratch.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_native_extensions.py -v
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from mso_io.native_extensions import (
    ExtensionInfo, copy_to_runtime_targets, find_built_artifact,
    inspect_all, inspect_extension,
)


class TestInspectExtension:
    def test_unknown_extension_raises(self):
        with pytest.raises(ValueError):
            inspect_extension("not_a_real_extension")

    @pytest.mark.parametrize("name", ["yamlwriter", "parallel_yaml_writer", "shuffle"])
    def test_known_extensions_have_real_source_in_this_checkout(self, name):
        info = inspect_extension(name)
        assert info.has_source, f"{name}: expected .cpp source under {info.source_dir}"
        assert info.has_build_script
        assert info.build_command
        assert os.path.isdir(info.source_dir)

    def test_yamlwriter_uses_build_sh(self):
        info = inspect_extension("yamlwriter")
        assert info.build_command[0:2] == ["bash", info.build_command[1]]
        assert info.build_command[1].endswith("build.sh")

    def test_shuffle_uses_setup_py_build_ext(self):
        info = inspect_extension("shuffle")
        assert "setup.py" in info.build_command[1]
        assert "build_ext" in info.build_command

    def test_installed_copies_found_in_real_checkout(self):
        info = inspect_extension("yamlwriter")
        # This repo ships prebuilt copies in these 3 runtime locations
        # (confirmed via `find`); at least one should be discoverable.
        assert len(info.installed_copies) >= 1
        assert all(p.endswith("yamlwriter.so") for p in info.installed_copies)


class TestInspectAll:
    def test_returns_all_three_known_extensions(self):
        infos = inspect_all()
        names = {i.name for i in infos}
        assert names == {"yamlwriter", "parallel_yaml_writer", "shuffle"}


class TestFindBuiltArtifact:
    def test_finds_artifact_in_source_dir(self, tmp_path):
        (tmp_path / "foo.so").write_bytes(b"fake")
        info = ExtensionInfo(name="foo", source_dir=str(tmp_path), has_source=True,
                              has_build_script=True, build_command=[],
                              built_artifact_glob="foo*.so")
        found = find_built_artifact(info)
        assert found == str(tmp_path / "foo.so")

    def test_finds_artifact_in_build_subdir(self, tmp_path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / "foo.so").write_bytes(b"fake")
        info = ExtensionInfo(name="foo", source_dir=str(tmp_path), has_source=True,
                              has_build_script=True, build_command=[],
                              built_artifact_glob="foo*.so")
        found = find_built_artifact(info)
        assert found == str(build_dir / "foo.so")

    def test_returns_none_when_nothing_built(self, tmp_path):
        info = ExtensionInfo(name="foo", source_dir=str(tmp_path), has_source=True,
                              has_build_script=True, build_command=[],
                              built_artifact_glob="foo*.so")
        assert find_built_artifact(info) is None


class TestCopyToRuntimeTargets:
    def test_copies_to_existing_target_dirs(self, tmp_path, monkeypatch):
        import mso_io.native_extensions as mod
        target1 = tmp_path / "runtime1"
        target1.mkdir()
        target2 = tmp_path / "runtime2_missing"  # deliberately not created
        monkeypatch.setattr(mod, "_RUNTIME_TARGETS", [target1, target2])

        built = tmp_path / "built.so"
        built.write_bytes(b"compiled-bytes")
        written = copy_to_runtime_targets(str(built), "myext")

        assert written == [str(target1 / "myext.so")]
        assert (target1 / "myext.so").read_bytes() == b"compiled-bytes"
