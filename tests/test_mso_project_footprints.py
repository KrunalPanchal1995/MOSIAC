"""
Tests for mso_project.footprints: glob matching, extension-based kind
inference, and every registered pipeline's footprint against real repo
fixtures where they exist.

Run:
    cd /data/MECHANISM_OPTIMIZATION_SUITE
    python -m pytest tests/test_mso_project_footprints.py -v
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.append(_SRC_DIR)

from mso_project.footprints import FOOTPRINTS, classify  # noqa: E402
from mso_project.footprints._generic import glob_match, kind_of  # noqa: E402


EXPECTED_PIPELINES = {
    "run_script", "forward_uq", "graph_sa", "mso_compare", "fuse_kld",
    "mean_value_fusion", "brute_force_sa", "idt_sensitivity", "nominal_sim",
    "uncertainty_generator", "mechanism_converter", "mechanism_check", "rmip_suite",
}


class TestRegistry:
    def test_all_12_pipelines_registered(self):
        assert EXPECTED_PIPELINES <= set(FOOTPRINTS.keys())

    def test_every_entry_has_role_and_pattern(self):
        for pipeline, entries in FOOTPRINTS.items():
            assert entries, f"{pipeline} footprint is empty"
            for e in entries:
                assert e.pattern
                assert e.role


class TestGlobMatch:
    def test_exact(self):
        assert glob_match("unsrt.pkl", "unsrt.pkl")
        assert not glob_match("other.pkl", "unsrt.pkl")

    def test_single_star_within_segment(self):
        assert glob_match("Opt/Data/Simulations/sim_data_case-3.lst",
                           "Opt/Data/Simulations/sim_data_case-*.lst")
        assert not glob_match("Opt/Data/Simulations/sim_data_case-3.csv",
                               "Opt/Data/Simulations/sim_data_case-*.lst")

    def test_recursive_double_star(self):
        assert glob_match(
            "Opt/Outlier_Resample/case-3/pass-1/Perturbed_Mech/mechanism_5.yaml",
            "Opt/Outlier_Resample/**/mechanism_*.yaml")
        assert glob_match(
            "Opt/Outlier_Resample/mechanism_0.yaml",  # ** can match zero components
            "Opt/Outlier_Resample/**/mechanism_*.yaml")

    def test_kind_of_by_extension(self):
        assert kind_of("x.pkl") == "pkl"
        assert kind_of("x.CSV") == "csv"
        assert kind_of("x.unknown_ext") == "other"


class TestClassify:
    def test_run_script_response_surface_coeff(self):
        role, kind = classify(
            "Opt/Data/ResponseSurface/responsecoef_case-3.csv", "run_script",
            "/x/Opt/Data/ResponseSurface/responsecoef_case-3.csv")
        assert role == "response_surface_coeff"
        assert kind == "csv"

    def test_run_script_perturbed_mechanism(self):
        role, kind = classify(
            "Perturbed_Mech/mechanism_10.yaml", "run_script",
            "/x/Perturbed_Mech/mechanism_10.yaml")
        assert role == "perturbed_mechanism"

    def test_unmatched_falls_back_to_generic(self):
        role, kind = classify("weird_file.zzz", "run_script", "/x/weird_file.zzz")
        assert role == "unclassified"
        assert kind == "other"

    def test_no_pipeline_falls_back_to_generic(self):
        role, kind = classify("data.csv", None, "/x/data.csv")
        assert role == "unclassified"
        assert kind == "csv"

    def test_unknown_pipeline_falls_back_to_generic(self):
        role, kind = classify("data.csv", "nonexistent_pipeline", "/x/data.csv")
        assert role == "unclassified"
        assert kind == "csv"

    @pytest.mark.parametrize("pipeline", sorted(EXPECTED_PIPELINES))
    def test_first_entry_of_each_footprint_is_self_consistent(self, pipeline):
        """Each footprint's own first pattern, matched against itself
        (pattern used as if it were a literal relpath with wildcards
        stripped to something concrete), should classify to that entry's
        own declared role -- a basic self-consistency smoke check that
        catches a typo'd pattern that could never match anything."""
        entry = FOOTPRINTS[pipeline][0]
        concrete = entry.pattern.replace("*", "X").replace("?", "Y")
        role, _ = classify(concrete, pipeline, f"/x/{concrete}")
        assert role == entry.role


class TestRealFixtures:
    """Spot-check footprints against real files already in this repo."""

    def test_ammonia_target_file_not_run_script_shaped(self):
        # Sanity: a real .target file itself isn't part of run_script's own
        # OUTPUT footprint (it's an INPUT, Locations-configurable, never
        # CWD-relative) -- classify() should not mis-tag it as a known role.
        path = "AMMONIA.target"
        role, kind = classify(path, "run_script", f"/x/{path}")
        assert role == "unclassified"

    def test_methyl_butanoate_sens_parameters_pkl(self):
        fixture = os.path.join(_ROOT, "DATASET", "METHYL_BUTANOATE_2026", "sens_parameters.pkl")
        if not os.path.isfile(fixture):
            pytest.skip("fixture not present in this checkout")
        role, kind = classify("sens_parameters.pkl", "run_script", fixture)
        assert role == "sensitivity_cache"
        assert kind == "pkl"

    def test_methyl_butanoate_unsrt_pkl(self):
        fixture = os.path.join(_ROOT, "DATASET", "METHYL_BUTANOATE_2026", "unsrt.pkl")
        if not os.path.isfile(fixture):
            pytest.skip("fixture not present in this checkout")
        role, kind = classify("unsrt.pkl", "run_script", fixture)
        assert role == "uncertainty_cache"
        assert kind == "pkl"
