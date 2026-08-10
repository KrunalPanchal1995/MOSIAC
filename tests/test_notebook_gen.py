"""
Tests for src/mso_io/notebook_gen.py (KRUNAL_JULY_23.md point 8 -- Jupyter
notebook generation, previously missing entirely from this repo).

Validates generated notebooks against the real `nbformat` package (present
in the anaconda env this test suite runs under) to guarantee they're
genuinely openable in Jupyter, not just "looks like JSON".

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_notebook_gen.py -v
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

nbformat = pytest.importorskip("nbformat")

from mso_io.notebook_gen import (
    NotebookRequest, add_code_cell, add_markdown_cell, build_mechanism_notebook,
    generate_mechanism_notebook, new_notebook, save_notebook,
)


class TestLowLevelBuilders:
    def test_new_notebook_has_v4_schema_fields(self):
        nb = new_notebook()
        assert nb["nbformat"] == 4
        assert nb["cells"] == []
        assert nb["metadata"]["kernelspec"]["name"] == "python3"

    def test_add_cells_round_trip_through_nbformat(self, tmp_path):
        nb = new_notebook()
        add_markdown_cell(nb, "# Title\nSome text")
        add_code_cell(nb, "x = 1\nprint(x)")
        path = str(tmp_path / "t.ipynb")
        save_notebook(nb, path)

        loaded = nbformat.read(path, as_version=4)
        nbformat.validate(loaded)
        assert loaded.cells[0].cell_type == "markdown"
        assert loaded.cells[1].cell_type == "code"
        assert "x = 1" in "".join(loaded.cells[1].source)


class TestBuildMechanismNotebook:
    @pytest.mark.parametrize("kind", ["idt", "flame_speed", "load_only"])
    def test_each_kind_is_valid_nbformat(self, tmp_path, kind):
        req = NotebookRequest(mechanism_path="/some/mech.yaml", kind=kind, fuel="NC7H16")
        nb_dict = build_mechanism_notebook(req)
        path = str(tmp_path / f"{kind}.ipynb")
        save_notebook(nb_dict, path)

        loaded = nbformat.read(path, as_version=4)
        nbformat.validate(loaded)
        assert len(loaded.cells) >= 3

    def test_mechanism_path_embedded_in_load_cell(self):
        req = NotebookRequest(mechanism_path="/data/mech/128-957.yaml", kind="idt")
        nb = build_mechanism_notebook(req)
        code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
        assert any("128-957.yaml" in "".join(c["source"]) for c in code_cells)

    def test_idt_cells_mention_ignition_delay(self):
        req = NotebookRequest(mechanism_path="/m.yaml", kind="idt")
        nb = build_mechanism_notebook(req)
        joined = "".join(
            "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"
        )
        assert "IdealGasReactor" in joined
        assert "idt" in joined

    def test_flame_speed_cells_mention_free_flame(self):
        req = NotebookRequest(mechanism_path="/m.yaml", kind="flame_speed")
        nb = build_mechanism_notebook(req)
        joined = "".join(
            "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"
        )
        assert "FreeFlame" in joined

    def test_generate_mechanism_notebook_writes_file(self, tmp_path):
        req = NotebookRequest(mechanism_path="/m.yaml", kind="load_only")
        out = str(tmp_path / "out.ipynb")
        result_path = generate_mechanism_notebook(out, req)
        assert result_path == out
        assert os.path.exists(out)
        nbformat.validate(nbformat.read(out, as_version=4))
