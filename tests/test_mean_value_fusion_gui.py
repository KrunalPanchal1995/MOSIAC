"""
Tests for mean_value_fusion_gui.py (Phase 3 of the GUI-separation split).

Covers the pure-logic helpers (_list_mechanisms, _run_fusion) directly --
these are exactly what the Tk worker thread calls, so testing them without
Tk gives real coverage of the actual fusion pipeline this app drives.
Reuses the H2-combustion DB fixture from
src/rmip/tests/test_stubs_fusion.py (same one used to verify
rmip.stubs.FusionEngine itself this session) rather than re-deriving one.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_mean_value_fusion_gui.py -v
"""
import os
import subprocess
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "src", "rmip", "tests"))

import mean_value_fusion_gui as app
from test_stubs_fusion import _build_h2_fixture  # noqa: E402


class TestNoGuiSmoke:
    def test_no_db_given(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "mean_value_fusion_gui.py"), "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "No --db given" in proc.stdout

    def test_reports_db_existence(self, tmp_path):
        db, _, _ = _build_h2_fixture(tmp_path)
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "mean_value_fusion_gui.py"),
             "--db", db, "--no-gui"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "exists=True" in proc.stdout


class TestListMechanisms:
    def test_lists_all_mechanisms(self, tmp_path):
        db, mid1, mid2 = _build_h2_fixture(tmp_path)
        rows = app._list_mechanisms(db)
        ids = {r[0] for r in rows}
        assert {mid1, mid2} <= ids


class TestRunFusion:
    def test_end_to_end_matches_stubs_fusionengine(self, tmp_path):
        """Same fixture/expectations as
        test_stubs_fusion.py::TestFusionEngineFuse::test_fuse_creates_new_mechanism_with_correct_counts
        -- this app's _run_fusion() is a thin wrapper, should match exactly."""
        db, mid1, mid2 = _build_h2_fixture(tmp_path)
        out_dir = str(tmp_path / "out")

        summary = app._run_fusion(
            db, [mid1, mid2], tol_A=0.01, tol_n=0.001, tol_Ea=100.0,
            output_name="Test_Fused", output_dir=out_dir, write_cantera=False,
        )

        assert summary["n_verbatim"] == 1  # CK_C
        assert summary["n_copy"] == 1      # CK_A
        assert summary["n_fuse"] == 1      # CK_B
        assert summary["n_species"] == 6
        assert summary["balanced"] is True
        assert summary["violations"] == []
        assert summary["fused_mech_id"] > mid2

        from pathlib import Path
        assert (Path(out_dir) / "Test_Fused.inp").exists()
        assert (Path(out_dir) / "Test_Fused.dat").exists()


class TestRunFusionUncertaintyCsv:
    """KRUNAL_JULY_23.md point 6 -- _run_fusion must also emit a per-
    reaction uncertainty classification CSV (Point 5's Uncertainty
    Quantification and File Generator's input contract), using the SAME
    H2-combustion fixture as the class above (CK_B is its one FUSE/
    SHARED_DIVERGENT reaction, the only kind FusionUncertaintyEngine bands)."""

    def test_writes_csv_for_every_shared_reaction_by_default(self, tmp_path):
        """FusionUncertaintyEngine bands every reaction present in >=2
        mechanisms with kinetics data, not just the FUSE/divergent bucket
        -- CK_A (identical, COPY bucket) gets a trivial f~=1.0 band, CK_B
        (divergent, FUSE bucket) gets a real one. Both are legitimate rows
        for the classification CSV."""
        db, mid1, mid2 = _build_h2_fixture(tmp_path)
        out_dir = str(tmp_path / "out")

        summary = app._run_fusion(
            db, [mid1, mid2], tol_A=0.01, tol_n=0.001, tol_Ea=100.0,
            output_name="Test_Fused", output_dir=out_dir, write_cantera=False,
        )

        assert summary["uncertainty_csv_path"] is not None
        assert summary["n_uncertainty_reactions"] == 2   # CK_A (identical) + CK_B (divergent)
        from pathlib import Path
        csv_path = Path(summary["uncertainty_csv_path"])
        assert csv_path.exists()
        assert csv_path.name == "Test_Fused_uncertainty_classification.csv"

        import csv as _csv
        with open(csv_path) as fh:
            rows = list(_csv.DictReader(fh))
        factors = [float(r["f"]) for r in rows]
        assert max(factors) > 10.0     # CK_B's real divergence survives
        assert min(factors) == pytest.approx(1.0, abs=1e-6)  # CK_A's trivial band

    def test_csv_loads_via_the_real_classification_loader(self, tmp_path):
        db, mid1, mid2 = _build_h2_fixture(tmp_path)
        out_dir = str(tmp_path / "out")
        summary = app._run_fusion(
            db, [mid1, mid2], tol_A=0.01, tol_n=0.001, tol_Ea=100.0,
            output_name="Test_Fused", output_dir=out_dir, write_cantera=False,
        )
        import sys as _sys
        _sys.path.insert(0, os.path.join(_ROOT, "src"))
        from modules.interfaces import load_classification_file
        df = load_classification_file(summary["uncertainty_csv_path"])
        assert len(df) >= 1
        assert "f" in df.columns

    def test_write_uncertainty_csv_false_skips_it(self, tmp_path):
        db, mid1, mid2 = _build_h2_fixture(tmp_path)
        out_dir = str(tmp_path / "out")
        summary = app._run_fusion(
            db, [mid1, mid2], tol_A=0.01, tol_n=0.001, tol_Ea=100.0,
            output_name="Test_Fused", output_dir=out_dir, write_cantera=False,
            write_uncertainty_csv=False,
        )
        assert summary["uncertainty_csv_path"] is None
        assert summary["n_uncertainty_reactions"] == 0

    def test_priority_mode_skips_uncertainty_csv(self, tmp_path):
        """priority_order copies one mechanism's kinetics verbatim per
        reaction -- there's no cross-mechanism divergence left to band."""
        db, mid1, mid2 = _build_h2_fixture(tmp_path)
        out_dir = str(tmp_path / "out")
        summary = app._run_fusion(
            db, [mid1, mid2], tol_A=0.01, tol_n=0.001, tol_Ea=100.0,
            output_name="Test_Fused", output_dir=out_dir, write_cantera=False,
            priority_order=[mid1, mid2],
        )
        assert summary["uncertainty_csv_path"] is None


class TestRunFusionPriorityMode:
    """Feature gap closed 2026-07-17 (bug.md): this GUI could previously
    only ever call the mean/consensus fusion strategy -- priority-pick mode
    (verbatim from the highest-priority present mechanism for every shared
    reaction) existed only on the separate CLI-only fuse_kld.py-style
    driver, via analysis.fusion.FusionEngine.fuse(priority_order=...), which
    this app's underlying rmip.stubs.FusionEngine.fuse() had no parameter
    to reach at all."""

    def test_priority_order_picks_verbatim_not_mean_for_divergent_reaction(self, tmp_path):
        # CK_B is the divergent (FUSE-bucket) reaction in the fixture:
        # mid1's A_si=1e8, mid2's A_si=1e11. Consensus-mean would produce
        # neither value (geometric mean of the two); priority-pick with
        # mid2 first must produce EXACTLY mid2's verbatim 1e11.
        db, mid1, mid2 = _build_h2_fixture(tmp_path)
        out_dir = str(tmp_path / "out_priority")

        summary = app._run_fusion(
            db, [mid1, mid2], tol_A=0.01, tol_n=0.001, tol_Ea=100.0,
            output_name="Test_Fused_Priority", output_dir=out_dir, write_cantera=False,
            priority_order=[mid2, mid1],
        )

        assert summary["n_fuse"] == 0  # nothing averaged in priority mode
        assert summary["priority_order"] == [mid2, mid1]

        import sqlite3
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT A_si FROM reactions WHERE mechanism_id=? AND canonical_key='CK_B'",
            (summary["fused_mech_id"],),
        ).fetchone()
        assert row is not None
        assert row[0] == 1e11  # mid2's verbatim value, not a geometric mean

    def test_reversed_priority_order_picks_the_other_source(self, tmp_path):
        db, mid1, mid2 = _build_h2_fixture(tmp_path)
        out_dir = str(tmp_path / "out_priority_rev")

        summary = app._run_fusion(
            db, [mid1, mid2], tol_A=0.01, tol_n=0.001, tol_Ea=100.0,
            output_name="Test_Fused_Priority_Rev", output_dir=out_dir, write_cantera=False,
            priority_order=[mid1, mid2],
        )

        import sqlite3
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT A_si FROM reactions WHERE mechanism_id=? AND canonical_key='CK_B'",
            (summary["fused_mech_id"],),
        ).fetchone()
        assert row[0] == 1e8  # mid1's verbatim value now, since it's first in priority_order


class TestGlossaryBackfillAndDegenerateGuard:
    """KRUNAL_JULY_23.md point 6: fusing Davis-2005 + Keromenes-2013 +
    Li-2015 produced "Fused_Mech (fused, 0 sp / 0 rxn)" silently. Root
    cause: those mechanisms were parsed without --glossary. _run_fusion now
    (a) backfills the glossary automatically before comparing, and
    (b) refuses to report an empty union instead of silently succeeding."""

    @staticmethod
    def _build_unglossaried_h2_fixture(tmp_path):
        """Same shared H2+O2<=>H2O2 reaction in two mechanisms, but with
        NO inchi_key/canonical_smiles/canonical_key at all -- exactly the
        state `rmip parse` (no --glossary) leaves a mechanism in, and
        exactly the state mechanisms 2/3/4 were found in against the real
        DB."""
        from test_glossary_backfill import (   # local test helper (path
            _make_db, _insert_mechanism, _build_unglossaried_mech,   # already on sys.path, see top of file)
        )
        db = str(tmp_path / "unglossaried.db")
        conn = _make_db(db)
        m1 = _insert_mechanism(conn, "M1")
        m2 = _insert_mechanism(conn, "M2")
        _build_unglossaried_mech(conn, m1)
        _build_unglossaried_mech(conn, m2)
        conn.commit()
        conn.close()
        return db, m1, m2

    @staticmethod
    def _glossary_csv(tmp_path):
        import csv
        path = tmp_path / "glossary.csv"
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["name", "smiles"])
            w.writerow(["H2", "[H][H]"])
            w.writerow(["O2", "[O][O]"])
        return str(path)

    def test_run_fusion_with_no_glossary_path_is_the_krunal_bug_reproduced(self, tmp_path):
        """Sanity check that this fixture genuinely reproduces the reported
        shape when NO glossary is applied (glossary_path=None): fusion must
        now raise FusionDegenerateError rather than silently succeed with an
        empty mechanism, since B4's per-mechanism-UNIQUE fallback still
        leaves nothing to actually classify as shared without any resolved
        keys at all... except this fixture's species/reactions DO still
        classify UNIQUE-per-mechanism (never vanish, per B4), so the union
        is non-empty even unglossaried. The true 0/0 degenerate case (both
        species AND reactions counts genuinely zero) is covered directly in
        test_run_fusion_raises_on_degenerate_empty_union below."""
        db, mid1, mid2 = self._build_unglossaried_h2_fixture(tmp_path)
        out_dir = str(tmp_path / "out_unglossaried")
        summary = app._run_fusion(
            db, [mid1, mid2], tol_A=0.01, tol_n=0.001, tol_Ea=100.0,
            output_name="Test_Unglossaried", output_dir=out_dir, write_cantera=False,
            glossary_path=None,
        )
        # concatenation, not real dedup: both copies of H2/O2 survive as
        # separate UNIQUE species, and the "same" reaction appears twice
        assert summary["n_species"] == 4
        assert summary["n_verbatim"] == 2

    def test_run_fusion_backfills_glossary_and_dedups_for_real(self, tmp_path):
        db, mid1, mid2 = self._build_unglossaried_h2_fixture(tmp_path)
        glossary_path = self._glossary_csv(tmp_path)
        out_dir = str(tmp_path / "out_backfilled")

        summary = app._run_fusion(
            db, [mid1, mid2], tol_A=0.01, tol_n=0.001, tol_Ea=100.0,
            output_name="Test_Backfilled", output_dir=out_dir, write_cantera=False,
            glossary_path=glossary_path,
        )

        assert summary["glossary_summary"] is not None
        assert summary["glossary_summary"][mid1]["species_resolved"] == 2
        assert summary["glossary_summary"][mid2]["species_resolved"] == 2
        # real dedup this time: H2 + O2 = 2 species (not 4), one shared
        # reaction (not two independent unique ones)
        assert summary["n_species"] == 2
        assert (summary["n_verbatim"] + summary["n_copy"] + summary["n_fuse"]) == 1

    def test_run_fusion_raises_on_degenerate_empty_union(self, tmp_path):
        """Two mechanisms with genuinely NO species/reactions at all (a
        stand-in for whatever produced the literal "0 sp / 0 rxn" the user
        saw) must raise, not report a hollow "success"."""
        from rmip.database.schema import init_db
        from rmip.database.schema_phase3 import upgrade_db
        db = str(tmp_path / "empty.db")
        conn = init_db(db)
        upgrade_db(conn)
        conn.execute(
            "INSERT INTO mechanisms (name, format, filepath, description, "
            "n_species, n_reactions, loaded_at, metadata_json) VALUES "
            "('E1','chemkin','/x.inp','',0,0,'2024-01-01T00:00:00Z','{}')")
        mid1 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO mechanisms (name, format, filepath, description, "
            "n_species, n_reactions, loaded_at, metadata_json) VALUES "
            "('E2','chemkin','/x.inp','',0,0,'2024-01-01T00:00:00Z','{}')")
        mid2 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()

        with pytest.raises(app.FusionDegenerateError):
            app._run_fusion(
                db, [mid1, mid2], tol_A=0.01, tol_n=0.001, tol_Ea=100.0,
                output_name="Test_Empty", output_dir=str(tmp_path / "out_empty"),
                write_cantera=False, glossary_path=None,
            )


class TestRunStatusExport:
    """KRUNAL_JULY_23.md point 1. Real tk.Tk() root, no synthetic clicks --
    same convention as this file's other Tk-backed checks."""

    def test_build_run_status_before_any_run(self):
        import tkinter as tk
        root = tk.Tk()
        try:
            gui_app = app.MeanValueFusionApp(root)
            gui_app._db_var.set("/data/project.db")
            gui_app._mech_ids_var.set("2,3,4")
            report = gui_app._build_run_status()
            assert report.tool == "Mean Value / Mechanism Fusion Generator"
            assert report.inputs["mechanism IDs"] == "2,3,4"
            assert report.status == "unknown"
        finally:
            root.destroy()

    def test_build_run_status_after_successful_fusion(self, tmp_path):
        import tkinter as tk
        db, mid1, mid2 = _build_h2_fixture(tmp_path)
        root = tk.Tk()
        try:
            gui_app = app.MeanValueFusionApp(root)
            gui_app._db_var.set(db)
            gui_app._mech_ids_var.set(f"{mid1},{mid2}")
            summary = app._run_fusion(
                db, [mid1, mid2], tol_A=0.01, tol_n=0.001, tol_Ea=100.0,
                output_name="Test_Status", output_dir=str(tmp_path / "out"),
                write_cantera=False,
            )
            gui_app._on_fusion_done(summary)

            report = gui_app._build_run_status()
            assert report.status == "success"
            assert str(summary["fused_mech_id"]) in report.summary
            assert "Fused mechanism DB id" in report.log
        finally:
            root.destroy()

    def test_build_run_status_after_failed_fusion(self, monkeypatch):
        import tkinter as tk
        # _on_fusion_error pops a real messagebox.showerror dialog, which
        # blocks forever waiting for a click on a live display -- stub it
        # out, same as any other test exercising an error-reporting path
        # that isn't itself under test here.
        monkeypatch.setattr(app.messagebox, "showerror", lambda *a, **k: None)
        root = tk.Tk()
        try:
            gui_app = app.MeanValueFusionApp(root)
            gui_app._on_fusion_error(app.FusionDegenerateError("empty union"))
            report = gui_app._build_run_status()
            assert report.status == "failed"
            assert report.summary == "empty union"
        finally:
            root.destroy()


class TestFuseHeadlessCli:
    """The --fuse headless CLI mode (KRUNAL_JULY_23.md PySide6 port):
    mso_studio.core.fusion shells out to this instead of importing
    rmip/Cantera into the PySide6 venv."""

    def test_fuse_cli_succeeds_and_prints_summary(self, tmp_path):
        db, mid1, mid2 = _build_h2_fixture(tmp_path)
        out_dir = tmp_path / "out"
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "mean_value_fusion_gui.py"),
             "--fuse", "--db", db, "--mechs", str(mid1), str(mid2),
             "--output-name", "CliFused", "--output-dir", str(out_dir),
             "--glossary", ""],
            capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "fused_mech_id=" in proc.stdout
        assert "n_species=6" in proc.stdout
        assert (out_dir / "CliFused.inp").exists()

    def test_fuse_cli_requires_two_mechs(self, tmp_path):
        db, mid1, _mid2 = _build_h2_fixture(tmp_path)
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "mean_value_fusion_gui.py"),
             "--fuse", "--db", db, "--mechs", str(mid1)],
            capture_output=True, text=True, timeout=30)
        assert proc.returncode == 1
        assert "--mechs" in proc.stdout

    def test_fuse_cli_reports_degenerate_union_via_exit_code(self, tmp_path):
        from rmip.database.schema import init_db
        from rmip.database.schema_phase3 import upgrade_db
        db = str(tmp_path / "empty.db")
        conn = init_db(db)
        upgrade_db(conn)
        ids = []
        for name in ("E1", "E2"):
            conn.execute(
                "INSERT INTO mechanisms (name, format, filepath, description, "
                "n_species, n_reactions, loaded_at, metadata_json) VALUES "
                "(?,'chemkin','/x.inp','',0,0,'2024-01-01T00:00:00Z','{}')", (name,))
            ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.commit()
        conn.close()

        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, "mean_value_fusion_gui.py"),
             "--fuse", "--db", db, "--mechs", *[str(i) for i in ids],
             "--output-dir", str(tmp_path / "out"), "--glossary", ""],
            capture_output=True, text=True, timeout=30)
        assert proc.returncode == 1
        assert "ERROR" in proc.stdout
