"""Stage 5: a small reacting-flow solver whose chemistry step is a pluggable operator.

What this is: a 1-D, constant-pressure *reaction-diffusion* solver with first-order (Lie) operator splitting:

    for each time step dt:   chemistry(dt) in every cell   ->   diffusion(dt) of temperature and species

* chemistry operator = a Cantera constant-pressure reactor per cell (full or reduced mechanism), OR a surrogate
  with the same interface (see surrogate.py), so the two are compared in exactly the same solver;
* transport is deliberately simple: unity Lewis number, one temperature-dependent diffusivity
  alpha(T) = 2e-5 (T/300)^1.7 m^2/s for heat and all species (conserves sum(Y) = 1);
* no flow: no pressure waves, no thermal expansion, no advection.

What it is not: a validated flame solver. It exists to exercise the chemistry-operator seam that a production CFD
code (e.g. PANSOPHIA's reacting Navier-Stokes) would call, and to measure what changing that operator does.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import cantera as ct

from .mechanism import FUEL, OXIDIZER, P0, make_reactor

T_ACTIVE = 800.0  # cells colder than this are chemically frozen over one step (no reaction in ~10 us)


@dataclass
class HotSpotCase:
    """A hot spot in a uniform H2/air mixture; heat spreads and ignition propagates."""
    name: str
    T_bg: float
    T_hot: float
    width_m: float
    phi: float
    length_m: float = 0.02
    n_cells: int = 100
    dt: float = 1.0e-5
    t_end: float = 1.0e-3
    P: float = P0


@dataclass
class RunResult:
    case: HotSpotCase
    t: np.ndarray
    T_mean: np.ndarray
    T_max: np.ndarray
    active_frac: np.ndarray
    x: np.ndarray
    T_final: np.ndarray
    Y_final: np.ndarray
    species: list
    chem_seconds: float
    pairs: dict = field(default_factory=dict)  # (state_in, state_out) per active cell, when recording


class CanteraChemistry:
    """Advance every active cell by dt with a constant-pressure reactor of `gas`."""

    def __init__(self, gas: ct.Solution, P: float = P0):
        self.gas = gas
        self.P = P
        self.reactor = make_reactor(gas)
        self.net = ct.ReactorNet([self.reactor])
        self.net.rtol, self.net.atol = 1e-8, 1e-14
        self.species = list(gas.species_names)
        self.n_failed = 0

    def advance(self, Y: np.ndarray, T: np.ndarray, dt: float):
        Y2, T2 = Y.copy(), T.copy()
        ph = self.reactor.phase
        for i in np.nonzero(T >= T_ACTIVE)[0]:
            for rtol, atol in ((1e-8, 1e-14), (1e-10, 1e-16)):       # retry once with tighter tolerances
                try:
                    self.net.rtol, self.net.atol = rtol, atol
                    ph.TPY = float(T[i]), self.P, Y[i]
                    self.reactor.syncState()
                    self.net.initial_time = 0.0                    # integrator clock never grows large
                    self.net.reinitialize()
                    self.net.advance(dt)
                    Y2[i], T2[i] = ph.Y, ph.T
                    break
                except ct.CanteraError:
                    continue
            else:
                self.n_failed += 1                                    # leave the cell unchanged and count it
        self.net.rtol, self.net.atol = 1e-8, 1e-14
        return Y2, T2


def alpha(T: np.ndarray) -> np.ndarray:
    return 2.0e-5 * (T / 300.0) ** 1.7


def _diffuse(phi: np.ndarray, T: np.ndarray, dx: float, dt: float) -> np.ndarray:
    """One explicit conservative diffusion update with zero-flux ends (sub-cycled to stay stable)."""
    a_max = float(alpha(T).max())
    n_sub = max(1, int(np.ceil(dt * a_max / (0.4 * dx * dx))))
    h = dt / n_sub
    a_face = 0.5 * (alpha(T)[:-1] + alpha(T)[1:])
    out = phi.copy()
    for _ in range(n_sub):
        flux = -(a_face.reshape((-1,) + (1,) * (out.ndim - 1))) * (out[1:] - out[:-1]) / dx
        d = np.zeros_like(out)
        d[:-1] -= flux / dx
        d[1:] += flux / dx
        out = out + h * d
    return out


def initial_state(case: HotSpotCase, gas: ct.Solution):
    gas.set_equivalence_ratio(case.phi, FUEL, OXIDIZER)
    Y0 = gas.Y.copy()
    dx = case.length_m / case.n_cells
    x = (np.arange(case.n_cells) + 0.5) * dx
    T = case.T_bg + (case.T_hot - case.T_bg) * np.exp(-(((x - 0.5 * case.length_m) / case.width_m) ** 2))
    Y = np.tile(Y0, (case.n_cells, 1))
    return x, dx, Y, T


def run(case: HotSpotCase, chem, gas_for_init: ct.Solution, record: bool = False) -> RunResult:
    x, dx, Y, T = initial_state(case, gas_for_init)
    n_steps = int(round(case.t_end / case.dt))
    ts, Tm, Tx, af = [0.0], [T.mean()], [T.max()], [float(np.mean(T > case.T_bg + 300.0))]
    pairs_in, pairs_out = [], []
    chem_s = 0.0
    for step in range(n_steps):
        t0 = time.perf_counter()
        Yn, Tn = chem.advance(Y, T, case.dt)
        chem_s += time.perf_counter() - t0
        if record:
            act = T >= T_ACTIVE
            pairs_in.append(np.column_stack([Y[act], T[act]]))
            pairs_out.append(np.column_stack([Yn[act], Tn[act]]))
        Y, T = Yn, Tn
        T = _diffuse(T, T, dx, case.dt)
        Y = _diffuse(Y, T, dx, case.dt)
        Y = np.clip(Y, 0.0, 1.0)
        Y /= Y.sum(axis=1, keepdims=True)
        ts.append((step + 1) * case.dt)
        Tm.append(T.mean()); Tx.append(T.max()); af.append(float(np.mean(T > case.T_bg + 300.0)))
    pairs = {"in": np.vstack(pairs_in), "out": np.vstack(pairs_out)} if record else {}
    return RunResult(case, np.array(ts), np.array(Tm), np.array(Tx), np.array(af), x, T, Y,
                     list(gas_for_init.species_names), chem_s, pairs)


def time_to_fraction(res: RunResult, frac: float = 0.5) -> float:
    """First time at which `frac` of the domain is hotter than T_bg + 300 K (NaN if never)."""
    idx = np.nonzero(res.active_frac >= frac)[0]
    return float(res.t[idx[0]]) if idx.size else float("nan")


def chemistry_rollouts(chem, x0: np.ndarray, dt: float, n_steps: int) -> np.ndarray:
    """Pure-chemistry sequences (no transport) from CFD-visited states x0 = (Y..., T): array (n, n_steps+1, n_species+1).

    Used to train a surrogate on multi-step rollouts, which penalises the slow drift a one-step fit cannot see.
    """
    Y, T = x0[:, :-1].copy(), x0[:, -1].copy()
    seq = [x0.copy()]
    for _ in range(n_steps):
        Y, T = chem.advance(Y, T, dt)
        seq.append(np.column_stack([Y, T]))
    return np.stack(seq, axis=1)
