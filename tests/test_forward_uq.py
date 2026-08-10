"""
Smoke tests for the forward_uq package.

Tests the core math without requiring a real target.opt or trained PRS files.
All tests run in < 5 s on a laptop CPU.

Run:
    cd /data/OPEN_CODE/PHASE-3
    python -m pytest tests/test_forward_uq.py -v
"""

import sys
import os
import types
import math

import numpy as np
import pytest

# Make the forward_uq package importable regardless of CWD
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from forward_uq.mc_propagator import _build_feature_matrix, MCPropagator
from forward_uq.sobol_prs import AnalyticalSobolPRS


# ===========================================================================
# _build_feature_matrix
# ===========================================================================

class TestBuildFeatureMatrix:

    def test_order1_shape(self):
        Z = np.ones((10, 3))
        B = _build_feature_matrix(Z, order=1)
        assert B.shape == (10, 4)          # 1 + 3 = 4 features

    def test_order2_shape(self):
        Z = np.ones((10, 3))
        B = _build_feature_matrix(Z, order=2)
        # 1 + 3 + 3*(3+1)/2 = 1 + 3 + 6 = 10
        assert B.shape == (10, 10)

    def test_order1_constant_column(self):
        Z = np.random.randn(20, 4)
        B = _build_feature_matrix(Z, order=1)
        np.testing.assert_array_equal(B[:, 0], np.ones(20))

    def test_order2_constant_column(self):
        Z = np.random.randn(20, 4)
        B = _build_feature_matrix(Z, order=2)
        np.testing.assert_array_equal(B[:, 0], np.ones(20))

    def test_order2_linear_block(self):
        Z = np.arange(6, dtype=float).reshape(2, 3)
        B = _build_feature_matrix(Z, order=2)
        # columns 1..3 must equal Z
        np.testing.assert_array_equal(B[:, 1:4], Z)

    def test_order2_diagonal_quadratic(self):
        # For n=2, B has columns [1, z0, z1, z0*z0, z0*z1, z1*z1]
        Z = np.array([[2.0, 3.0]])
        B = _build_feature_matrix(Z, order=2)
        assert B.shape == (1, 6)
        assert B[0, 0] == 1.0        # constant
        assert B[0, 1] == 2.0        # z0
        assert B[0, 2] == 3.0        # z1
        assert B[0, 3] == 4.0        # z0^2
        assert B[0, 4] == 6.0        # z0*z1
        assert B[0, 5] == 9.0        # z1^2

    def test_n1_scalar(self):
        Z = np.array([[0.5]])
        B = _build_feature_matrix(Z, order=2)
        # 1 + 1 + 1 = 3 features
        assert B.shape == (1, 3)
        assert B[0, 0] == 1.0
        assert B[0, 1] == 0.5
        assert B[0, 2] == pytest.approx(0.25)


# ===========================================================================
# AnalyticalSobolPRS
# ===========================================================================

def _make_mock_prs(n_comp: int, a_vals=None, b_diag=None):
    """
    Build a minimal mock ResponseSurface compatible with AnalyticalSobolPRS.
    coeff ordering: [c0, a1..an, b11, b12, b13..., b22, b23..., bnn]
    """
    prs = types.SimpleNamespace()
    prs.n_comp = n_comp
    n = n_comp
    n_quad = n * (n + 1) // 2
    n_feat = 1 + n + n_quad
    coeff = np.zeros(n_feat)
    coeff[0] = 0.0                   # constant
    if a_vals is not None:
        coeff[1:1 + n] = a_vals
    if b_diag is not None:
        # put diagonal b values in the correct quadratic positions
        count = 1 + n
        for i in range(n):
            for j in range(i, n):
                if i == j and b_diag is not None and i < len(b_diag):
                    coeff[count] = b_diag[i]
                count += 1
    prs.coeff = coeff
    return prs


class TestAnalyticalSobolPRS:

    def _comp_to_rxn(self, n):
        return {i: (f"R{i}", "A-facto") for i in range(n)}

    def _rxn_keys(self, n):
        return [f"R{i}" for i in range(n)]

    def test_total_variance_linear_only(self):
        # η(ζ) = a*ζ  →  Var = a² / 3
        prs = _make_mock_prs(1, a_vals=[2.0])
        sp = AnalyticalSobolPRS(prs, self._comp_to_rxn(1), self._rxn_keys(1))
        expected = 4.0 / 3.0
        assert sp.total_variance() == pytest.approx(expected, rel=1e-6)

    def test_first_order_sums_to_one_pure_linear(self):
        # pure linear model: all variance attributable to first-order indices
        n = 4
        a = np.array([1.0, 2.0, 3.0, 4.0])
        prs = _make_mock_prs(n, a_vals=a)
        sp = AnalyticalSobolPRS(prs, self._comp_to_rxn(n), self._rxn_keys(n))
        result = sp.compute()
        # sum of S_i should be 1.0 (no interactions)
        total_s = sum(result[k]["S1"] for k in result)
        assert total_s == pytest.approx(1.0, abs=1e-6)

    def test_compute_returns_all_reactions(self):
        n = 3
        prs = _make_mock_prs(n, a_vals=[1.0, 2.0, 3.0])
        sp = AnalyticalSobolPRS(prs, self._comp_to_rxn(n), self._rxn_keys(n))
        result = sp.compute()
        assert set(result.keys()) == {f"R{i}" for i in range(n)}

    def test_total_order_geq_first_order(self):
        # ST_i >= S_i always
        n = 3
        a = np.array([1.0, 2.0, 3.0])
        b_diag = np.array([0.5, 0.3, 0.1])
        prs = _make_mock_prs(n, a_vals=a, b_diag=b_diag)
        sp = AnalyticalSobolPRS(prs, self._comp_to_rxn(n), self._rxn_keys(n))
        result = sp.compute()
        for k in result:
            assert result[k]["ST"] >= result[k]["S1"] - 1e-12

    def test_zero_model_gives_zero_variance(self):
        prs = _make_mock_prs(2, a_vals=[0.0, 0.0])
        sp = AnalyticalSobolPRS(prs, self._comp_to_rxn(2), self._rxn_keys(2))
        assert sp.total_variance() == pytest.approx(0.0, abs=1e-12)

    def test_sobol_indices_nonnegative(self):
        n = 5
        rng = np.random.default_rng(0)
        a = rng.uniform(-3, 3, n)
        b_diag = rng.uniform(-1, 1, n)
        prs = _make_mock_prs(n, a_vals=a, b_diag=b_diag)
        sp = AnalyticalSobolPRS(prs, self._comp_to_rxn(n), self._rxn_keys(n))
        result = sp.compute()
        for k in result:
            assert result[k]["S1"]  >= -1e-9
            assert result[k]["ST"]  >= -1e-9

    def test_to_dataframe_shape(self):
        n = 3
        prs = _make_mock_prs(n, a_vals=[1.0, 2.0, 3.0])
        sp = AnalyticalSobolPRS(prs, self._comp_to_rxn(n), self._rxn_keys(n))
        df = sp.to_dataframe(case_index=7)
        assert len(df) == n
        assert "reaction" in df.columns
        assert "S1" in df.columns
        assert "ST" in df.columns
        assert (df["case_index"] == 7).all()


# ===========================================================================
# MCPropagator — synthetic PRS propagation (no file I/O)
# ===========================================================================

def _make_identity_prs(n_comp: int):
    """
    A mock PRS that returns η = sum(ζ) for every sample.
    Used to validate that MCPropagator.propagate dispatches correctly.
    """
    class _FakePRS:
        def __init__(self, n):
            self.n_comp = n
            self.order  = 2
            self._active_idx = list(range(n))
            # coeff: η = 0 + 1*ζ_1 + 1*ζ_2 + ...  (linear, a_i=1, b=0)
            n_quad = n * (n + 1) // 2
            c = np.zeros(1 + n + n_quad)
            c[1:1 + n] = 1.0
            self.coeff = c

        def evaluate_prs(self, zeta_vec):
            return float(np.sum(zeta_vec[:self.n_comp]))

    return _FakePRS(n_comp)


class TestMCPropagatorPropagation:

    def _make_propagator(self, n_comp: int, n_cases: int = 2):
        prs_dict = {i: _make_identity_prs(n_comp) for i in range(n_cases)}
        # Minimal stubs — propagate only uses prs_dict and n_full
        prop = MCPropagator(
            prs_dict=prs_dict,
            unsrt_data={},
            target_list=[None] * n_cases,
            n_full=n_comp,
            design_type="A-facto",
        )
        return prop

    def test_propagate_shape(self):
        n_comp, n_samples, n_cases = 4, 100, 3
        prop = self._make_propagator(n_comp, n_cases)
        Z = np.random.uniform(-1, 1, (n_samples, n_comp))
        preds = prop.propagate(Z)
        assert len(preds) == n_cases
        for v in preds.values():
            assert len(v) == n_samples

    def test_propagate_identity_prs(self):
        """
        With η = sum(ζ), predictions should match np.sum(Z, axis=1).
        """
        n_comp = 3
        prop = self._make_propagator(n_comp, n_cases=1)
        Z = np.array([[1.0, 2.0, 3.0],
                      [0.0, 0.0, 0.0],
                      [-1.0, -1.0, -1.0]])
        preds = prop.propagate(Z)
        expected = np.sum(Z, axis=1)
        np.testing.assert_allclose(preds[0], expected, rtol=1e-9)

    def test_statistics_mean_sums_to_zero_for_symmetric(self):
        """
        η = sum(ζ), ζ ~ U(-1,1) symmetric → E[predictions[0]] ≈ 0 for large N.
        compute_statistics needs real target objects; test raw preds instead.
        """
        n_comp = 5
        prop = self._make_propagator(n_comp, n_cases=1)
        rng = np.random.default_rng(42)
        Z = rng.uniform(-1, 1, (100_000, n_comp))
        preds = prop.propagate(Z)
        # η = sum(ζ_i) where each ζ_i ~ U(-1,1): E[η] = 0
        assert abs(preds[0].mean()) < 0.05

    def test_propagate_variance_linear_model(self):
        """
        η = sum(ζ_i), each ζ_i ~ U(-1,1) → Var(η) = n / 3.
        """
        n_comp = 4
        prop = self._make_propagator(n_comp, n_cases=1)
        rng = np.random.default_rng(99)
        Z = rng.uniform(-1, 1, (200_000, n_comp))
        preds = prop.propagate(Z)
        expected_var = n_comp / 3.0
        assert abs(preds[0].var() - expected_var) < 0.05


# ===========================================================================
# Round-trip: feature matrix → manual dot vs AnalyticalSobolPRS
# ===========================================================================

class TestFeatureMatrixConsistency:

    def test_feature_matrix_matches_manual_eval(self):
        """
        Verify that B @ coeff gives the same result as manual polynomial eval.
        η = c0 + a1*z1 + a2*z2 + b11*z1^2 + b12*z1*z2 + b22*z2^2
        """
        a1, a2 = 2.0, -1.0
        b11, b12, b22 = 0.5, 0.3, -0.4
        c0 = 1.0

        # coeff order: [c0, a1, a2, b11, b12, b22]
        coeff = np.array([c0, a1, a2, b11, b12, b22])

        rng = np.random.default_rng(7)
        Z = rng.uniform(-1, 1, (50, 2))
        B = _build_feature_matrix(Z, order=2)
        prs_vals = B @ coeff

        manual = (c0
                  + a1  * Z[:, 0]
                  + a2  * Z[:, 1]
                  + b11 * Z[:, 0]**2
                  + b12 * Z[:, 0] * Z[:, 1]
                  + b22 * Z[:, 1]**2)

        np.testing.assert_allclose(prs_vals, manual, rtol=1e-10)
