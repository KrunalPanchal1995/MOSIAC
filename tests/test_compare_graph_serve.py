"""
Tests for KRUNAL_JULY_23.md point 7 -- `rmip compare-graph --serve` launching
a real localhost viewer for the comparison graph (previously compare-graph
only wrote JSON files with no way to look at the result).

Covers rmip.cli._serve_comparison_graph's wiring via monkeypatched
GraphBuilder/NetworkVisualizer (no real Dash server bound -- that path was
verified manually end-to-end: `rmip_cli.py compare-graph --mechs 2 3 4 --db
outputs/project.db --serve --port 8077` served a real 200 on
http://localhost:8077/). This test only guards the argument-assembly logic
from silently drifting.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_compare_graph_serve.py -v
"""
import os
import sys
import types

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from rmip import cli as rmip_cli


class _FakeGraphBuilder:
    def __init__(self, db):
        self.db = db
        self.build_union_graphs_called_with = None

    def build_union_graphs(self, mech_ids):
        self.build_union_graphs_called_with = list(mech_ids)
        return [f"graph-{m}" for m in mech_ids]


class _FakeVisualizer:
    instances = []

    def __init__(self, graphs, title=None):
        self.graphs = graphs
        self.title = title
        self.run_called_with = None
        _FakeVisualizer.instances.append(self)

    def run(self, port=8050, label_mode="formula"):
        self.run_called_with = {"port": port, "label_mode": label_mode}


@pytest.fixture(autouse=True)
def _reset_fake_visualizer():
    _FakeVisualizer.instances.clear()
    yield
    _FakeVisualizer.instances.clear()


@pytest.fixture
def patched_backend(monkeypatch):
    fake_gb_module = types.SimpleNamespace(GraphBuilder=_FakeGraphBuilder)
    fake_viz_module = types.SimpleNamespace(NetworkVisualizer=_FakeVisualizer)
    monkeypatch.setitem(sys.modules, "rmip.core.graph_builder", fake_gb_module)
    monkeypatch.setitem(sys.modules, "rmip.analysis.visualization", fake_viz_module)
    yield


class Args:
    def __init__(self, mechs, db, port=8050, label="formula"):
        self.mechs = mechs
        self.db = db
        self.port = port
        self.label = label


class TestServeComparisonGraph:
    def test_two_mechanisms_shown_directly(self, patched_backend, capsys):
        args = Args(mechs=[2, 3], db="project.db", port=8123)
        rmip_cli._serve_comparison_graph(args)

        viz = _FakeVisualizer.instances[0]
        assert viz.run_called_with == {"port": 8123, "label_mode": "formula"}
        assert "http://localhost:8123" in capsys.readouterr().out

    def test_more_than_two_mechanisms_truncated_with_note(self, patched_backend, capsys):
        args = Args(mechs=[2, 3, 4], db="project.db", port=8050)
        rmip_cli._serve_comparison_graph(args)

        viz = _FakeVisualizer.instances[0]
        assert len(viz.graphs) == 2   # only the first 2 mechanisms get a live panel
        assert viz.graphs == ["graph-2", "graph-3"]
        out = capsys.readouterr().out
        assert "first 2 of 3" in out

    def test_label_mode_passed_through(self, patched_backend):
        args = Args(mechs=[2, 3], db="project.db", port=8050, label="id")
        rmip_cli._serve_comparison_graph(args)
        assert _FakeVisualizer.instances[0].run_called_with["label_mode"] == "id"

    def test_titles_reference_full_compared_set(self, patched_backend):
        args = Args(mechs=[2, 3, 4], db="project.db")
        rmip_cli._serve_comparison_graph(args)
        viz = _FakeVisualizer.instances[0]
        assert all("[2, 3, 4]" in t for t in viz.title)
