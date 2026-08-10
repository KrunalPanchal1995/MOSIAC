"""
Tests for generate_target_opt.py's "Project Tracker" tab (mso_project
viewer, appended last at notebook index 13 -- 14 tabs total).

Headless construction + wiring only -- see test_target_workbench.py's
module docstring for why the Tk UI itself isn't exercised interactively
here. A leftover autosave checkpoint on disk pops a blocking
messagebox.askyesno on startup -- mocked out below so this stays
non-interactive regardless of local machine state.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_mso_project_gui.py -v
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


@pytest.fixture
def app(monkeypatch):
    tk = pytest.importorskip("tkinter")
    from tkinter import messagebox
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: None)
    import generate_target_opt as gto
    root = tk.Tk()
    root.withdraw()
    application = gto.App(root)
    yield application
    root.destroy()


class TestTabPresence:
    def test_14_tabs_total(self, app):
        titles = [app._nb.tab(i, "text") for i in range(len(app._nb.tabs()))]
        assert len(titles) == 14

    def test_project_tracker_tab_last_and_distinct_from_tab_0(self, app):
        titles = [app._nb.tab(i, "text") for i in range(len(app._nb.tabs()))]
        assert titles[13].startswith("Project Tracker")
        assert titles[0].startswith("Project") and not titles[0].startswith("Project Tracker")

    def test_num_tabs_and_locker_agree(self, app):
        assert app._num_tabs == 14
        assert app._tab_locker.num_tabs == 14

    def test_tab_13_needs_no_validation(self, app):
        assert app._validate_tab(13) == []


class TestProjectViewerFlow:
    def test_open_creates_project_if_absent(self, app, tmp_path):
        proj_dir = str(tmp_path / "new_project")
        app._proj_viewer_path.set(proj_dir)
        app._pv_open()
        assert app._proj_viewer_obj is not None
        assert os.path.isfile(os.path.join(proj_dir, "project.yaml"))

    def test_open_reopens_existing_project(self, app, tmp_path):
        proj_dir = str(tmp_path / "proj")
        app._mso_project_on_path()
        from mso_project import Project
        Project.create(proj_dir, name="Preexisting").close()

        app._proj_viewer_path.set(proj_dir)
        app._pv_open()
        assert app._proj_viewer_obj.info["name"] == "Preexisting"

    def test_refresh_populates_trees(self, app, tmp_path):
        proj_dir = str(tmp_path / "proj")
        app._proj_viewer_path.set(proj_dir)
        app._pv_open()

        f = tmp_path / "data.csv"
        f.write_text("a\n")
        app._proj_viewer_obj.register(str(f), role="test_role")
        app._pv_refresh()

        rows = app._pv_artifacts_tree.get_children()
        assert len(rows) == 1
        values = app._pv_artifacts_tree.item(rows[0], "values")
        assert values[1] == "test_role"

    def test_register_locations_uses_current_session_paths(self, app, tmp_path):
        proj_dir = str(tmp_path / "proj")
        app._proj_viewer_path.set(proj_dir)
        app._pv_open()

        mech_file = tmp_path / "mech.yaml"
        mech_file.write_text("phases: []\n")
        app.cfg.setdefault("Locations", {})["mechanism"] = str(mech_file)

        app._pv_register_locations()
        arts = app._proj_viewer_obj.list_artifacts()
        assert any(a["role"] == "gui_location_mechanism" for a in arts)

    def test_register_locations_without_open_project_warns_not_crashes(self, app):
        app._proj_viewer_obj = None
        app._pv_register_locations()  # must not raise

    def test_build_report_without_open_project_warns_not_crashes(self, app):
        app._proj_viewer_obj = None
        app._pv_build_report()  # must not raise

    def test_build_report_populates_status(self, app, tmp_path):
        proj_dir = str(tmp_path / "proj")
        app._proj_viewer_path.set(proj_dir)
        app._pv_open()
        app._pv_build_report()
        assert "Main:" in app._pv_report_status.get()
