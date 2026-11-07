"""Fast checks of the end-to-end pipeline (mosiac_pipeline). The slow surrogate training is not exercised here."""
import numpy as np
import pytest

ct = pytest.importorskip("cantera")

from mosiac_pipeline import cfd1d as C
from mosiac_pipeline import mechanism as M


@pytest.fixture(scope="module")
def gas():
    g, rep = M.construct()
    assert rep["element_imbalance_max"] == 0.0
    return g


def test_sensitivity_has_the_textbook_sign(gas):
    ex = M.explain(gas)
    top = ex["top"][0]
    assert top["reaction"] == "H + O2 <=> O + OH"      # chain branching dominates ignition
    assert top["dln_tau_dln_k"] < -0.5                   # faster branching -> shorter delay


def test_calibration_recovers_the_synthetic_targets(gas):
    ex = M.explain(gas)
    cal = M.calibrate_twin(gas, ex["sensitivity"])
    assert cal["rms_log_error_after"] < 0.02 * max(cal["rms_log_error_before"], 1e-9) + 1e-3
    M.set_multipliers(gas, np.ones(gas.n_reactions))


def test_reduction_keeps_ignition_delay_within_tolerance(gas):
    M.set_multipliers(gas, np.ones(gas.n_reactions))
    red = M.reduce_reactions(gas, np.ones(gas.n_reactions))
    assert red["n_reduced"] < red["n_full"]
    assert red["max_rel_delay_error"] <= red["tolerance"]


def test_tiny_cfd_reduced_matches_full(gas):
    M.set_multipliers(gas, np.ones(gas.n_reactions))
    red = M.reduce_reactions(gas, np.ones(gas.n_reactions))["mechanism"]
    case = C.HotSpotCase("smoke", T_bg=1000.0, T_hot=1500.0, width_m=1.2e-3, phi=1.0, n_cells=30, t_end=1.0e-4)
    a = C.run(case, C.CanteraChemistry(gas), gas)
    b = C.run(case, C.CanteraChemistry(red), red)
    assert np.all(np.isfinite(a.T_final)) and np.all(np.isfinite(b.T_final))
    assert np.linalg.norm(a.T_final - b.T_final) / np.linalg.norm(a.T_final) < 0.02
    # diffusion + chemistry keep mass fractions a valid composition
    assert np.allclose(a.Y_final.sum(axis=1), 1.0)


def test_burned_gas_closure_leaves_an_equilibrated_cell_unchanged_and_conserves_enthalpy(gas):
    """A burned cell skips the network and is set to constant-H,P equilibrium: idempotent on an equilibrated state."""
    from mosiac_pipeline.surrogate import Surrogate

    g = ct.Solution("h2o2.yaml")
    g.set_equivalence_ratio(1.0, M.FUEL, M.OXIDIZER)
    g.TP = 1000.0, ct.one_atm
    g.equilibrate("HP")
    Y0, T0, h0 = g.Y.copy(), g.T, g.enthalpy_mass
    sur = Surrogate(list(g.species_names), 1.0e-5, closure_gas=g)          # untrained: the network is never used here
    Y2, T2 = sur.advance(Y0[None, :].copy(), np.array([T0]), 1.0e-5)
    assert sur.n_closure == 1
    assert np.isclose(Y2.sum(), 1.0) and np.all(Y2 >= 0)
    assert abs(T2[0] - T0) < 1.0
    g.TPY = T2[0], ct.one_atm, Y2[0]
    assert abs(g.enthalpy_mass - h0) < 5.0e3          # J/kg, rounding of the cache key
