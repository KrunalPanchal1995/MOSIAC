"""Stage 6: a Neural-ODE surrogate for the chemistry step, usable inside the CFD of cfd1d.py.

The network learns a vector field f(x) for the thermochemical state x = (reactive-species mass fractions, T):
dx/ds = f(x), s = t/dt in [0, 1].  Integrating it with fixed-step RK4 over one CFD time step gives the surrogate's
prediction of what the chemistry does in that step (a learned flow map), trained by back-propagating through the solver.

Honest scope (also in README.md):
* trained on states visited by the *reduced-mechanism CFD* in several hot-spot cases and evaluated on a held-out case;
* fixed CFD time step (the one it was trained for), fixed-step RK4 (not adaptive), CPU only;
* radical mass fractions (H, O, OH, HO2, H2O2) are learned in log10 space, major species and T linearly;
* the network's species output is projected onto the set that conserves the H and O element masses of the cell, and the
  temperature is then recovered from enthalpy conservation (exact at constant pressure) with Cantera's equation of state;
  the network's own temperature output is only an auxiliary training target.  Without this step the surrogate drifts off
  the element-conserving manifold inside the CFD and collapses (observed, see README).
"""
from __future__ import annotations

import cantera as ct
import numpy as np
import torch
from torch import nn

from .cfd1d import T_ACTIVE

INERT = ("N2", "AR")
RADICALS = ("H", "O", "OH", "HO2", "H2O2")  # span many decades during ignition, so they are learned in log10 space
Y_FLOOR = 1e-12


class VectorField(nn.Module):
    def __init__(self, dim: int, width: int = 64, depth: int = 3):
        super().__init__()
        layers, d = [], dim
        for _ in range(depth):
            layers += [nn.Linear(d, width), nn.Tanh()]
            d = width
        out = nn.Linear(d, dim)
        nn.init.zeros_(out.bias)
        out.weight.data *= 0.1
        layers.append(out)
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


def flow(f: nn.Module, x0: torch.Tensor, n_steps: int = 4) -> torch.Tensor:
    """RK4 integration of dx/ds = f(x) from s=0 to s=1 (differentiable, so training goes through the solver)."""
    h = 1.0 / n_steps
    x = x0
    for _ in range(n_steps):
        k1 = f(x)
        k2 = f(x + 0.5 * h * k1)
        k3 = f(x + 0.5 * h * k2)
        k4 = f(x + h * k3)
        x = x + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
    return x


class Surrogate:
    def __init__(self, species: list[str], dt: float, gas=None, P: float = 101325.0, fallback=None, log_radicals: bool = True, closure_gas=None):
        """gas: mechanism whose species/thermo the surrogate is consistent with (enables conservation projection);
        fallback: a chemistry operator (e.g. CanteraChemistry) used for any cell where the surrogate's output cannot
        be made thermodynamically consistent.  Counters n_cells / n_fallback report how often that happens."""
        self.species = list(species)
        self.P = P
        self.fallback = fallback
        self.n_cells = 0
        self.n_fallback = 0
        self.gas = None
        self.E = None
        # burned-gas closure: cells whose fuel is consumed are advanced to chemical equilibrium (constant enthalpy and
        # pressure) instead of by the network, which has no restoring force and drifts there. Results are cached because
        # burned cells in a uniform region share almost the same (enthalpy, element) key.
        self.closure = None
        self.n_closure = 0
        self._eq_cache = {}
        if closure_gas is not None:
            self.closure = ct.Solution(thermo="ideal-gas", kinetics="gas", species=closure_gas.species(), reactions=[])
            self._h2 = species.index("H2")
            self._H = [self.closure.n_atoms(k, self.closure.element_index("H")) * self.closure.atomic_weights[self.closure.element_index("H")]
                       / self.closure.molecular_weights[k] for k in range(self.closure.n_species)]
        if gas is not None:
            # private thermo-only phase, so enthalpy solves never disturb a reactor that shares `gas`
            self.gas = ct.Solution(thermo="ideal-gas", kinetics="gas", species=gas.species(), reactions=[])
            W = gas.molecular_weights
            rows = []
            for el in ("H", "O"):
                m = gas.element_index(el)
                rows.append([gas.n_atoms(k, m) * gas.atomic_weights[m] / W[k] for k in range(gas.n_species)])
            self.E = np.array(rows)[:, [i for i, sp in enumerate(species) if sp not in INERT]]
        self.react_idx = [i for i, s in enumerate(species) if s not in INERT]
        self.dim = len(self.react_idx) + 1
        self.log_mask = np.array([log_radicals and species[i] in RADICALS for i in self.react_idx] + [False])
        self.dt = dt
        self.f = VectorField(self.dim)
        self.lo = None
        self.hi = None

    # ---- packing / normalisation
    def pack(self, Y: np.ndarray, T: np.ndarray) -> np.ndarray:
        return np.column_stack([Y[:, self.react_idx], T])

    def _to_z(self, x: np.ndarray) -> np.ndarray:
        z = x.copy()
        z[:, self.log_mask] = np.log10(np.maximum(x[:, self.log_mask], Y_FLOOR))
        return z

    def _from_z(self, z: np.ndarray) -> np.ndarray:
        x = z.copy()
        x[:, self.log_mask] = 10.0 ** z[:, self.log_mask]
        return x

    def _norm(self, x: np.ndarray) -> np.ndarray:
        return (x - self.lo) / (self.hi - self.lo)

    def _denorm(self, xn: np.ndarray) -> np.ndarray:
        return xn * (self.hi - self.lo) + self.lo

    # ---- training
    def fit(self, x_in: np.ndarray, x_out: np.ndarray, steps: int = 4000, batch: int = 4096, lr: float = 3e-3,
            seed: int = 0, log=print) -> dict:
        torch.manual_seed(seed)
        rng = np.random.default_rng(seed)
        # recorded CFD pairs are (all species..., T); keep reactive species + T
        x_in, x_out = (self._to_z(np.column_stack([m[:, self.react_idx], m[:, -1]])) for m in (x_in, x_out))
        both = np.vstack([x_in, x_out])
        self.lo = both.min(axis=0)
        self.hi = np.where(both.max(axis=0) > self.lo, both.max(axis=0), self.lo + 1.0)
        a, b = self._norm(x_in), self._norm(x_out)
        scale = np.maximum((b - a).std(axis=0), 1e-6)  # per-channel increment scale: small radicals count too
        perm = rng.permutation(len(a))
        n_val = max(1, len(a) // 10)
        va, tr = perm[:n_val], perm[n_val:]
        A, B = torch.tensor(a, dtype=torch.float32), torch.tensor(b, dtype=torch.float32)
        S = torch.tensor(scale, dtype=torch.float32)
        opt = torch.optim.Adam(self.f.parameters(), lr=lr)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=steps, eta_min=lr * 1e-3)
        hist = {"step": [], "train": [], "val": []}
        for k in range(steps):
            idx = torch.tensor(rng.choice(tr, size=min(batch, len(tr)), replace=False))
            loss = (((flow(self.f, A[idx]) - B[idx]) / S) ** 2).mean()
            opt.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(self.f.parameters(), 1.0)
            opt.step(); sched.step()
            if k % 200 == 0 or k == steps - 1:
                with torch.no_grad():
                    v = (((flow(self.f, A[va]) - B[va]) / S) ** 2).mean().item()
                hist["step"].append(k); hist["train"].append(float(loss.detach())); hist["val"].append(v)
                log(f"  step {k:5d}  train {float(loss.detach()):.4e}  val {v:.4e}")
        return hist

    def fit_rollouts(self, seq: np.ndarray, steps: int = 2500, batch: int = 1024, lr: float = 3e-3, seed: int = 0,
                     log=print) -> dict:
        """Train on K-step rollouts: seq has shape (n, K+1, n_species+1) of pure-chemistry states (cfd1d.chemistry_rollouts).

        The loss is the mean over k = 1..K of the normalised error of the surrogate applied k times from x_0, so
        errors that compound over many CFD steps (e.g. slow drift in the burned gas) are penalised during training.
        """
        torch.manual_seed(seed)
        rng = np.random.default_rng(seed)
        n, k1, _ = seq.shape
        K = k1 - 1
        z = np.stack([self._to_z(np.column_stack([seq[:, k][:, self.react_idx], seq[:, k][:, -1]])) for k in range(k1)], axis=1)
        flat = z.reshape(-1, self.dim)
        self.lo = flat.min(axis=0)
        self.hi = np.where(flat.max(axis=0) > self.lo, flat.max(axis=0), self.lo + 1.0)
        zn = (z - self.lo) / (self.hi - self.lo)
        scale = np.maximum(np.diff(zn, axis=1).reshape(-1, self.dim).std(axis=0), 1e-6)
        perm = rng.permutation(n)
        n_val = max(1, n // 10)
        va, tr = perm[:n_val], perm[n_val:]
        Z = torch.tensor(zn, dtype=torch.float32)
        S = torch.tensor(scale, dtype=torch.float32)

        def rollout_loss(idx):
            x, loss = Z[idx, 0], 0.0
            for k in range(1, K + 1):
                x = flow(self.f, x)
                loss = loss + (((x - Z[idx, k]) / S) ** 2).mean()
            return loss / K

        opt = torch.optim.Adam(self.f.parameters(), lr=lr)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=steps, eta_min=lr * 1e-3)
        hist = {"step": [], "train": [], "val": []}
        for it in range(steps):
            idx = torch.tensor(rng.choice(tr, size=min(batch, len(tr)), replace=False))
            loss = rollout_loss(idx)
            opt.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(self.f.parameters(), 1.0)
            opt.step(); sched.step()
            if it % 200 == 0 or it == steps - 1:
                with torch.no_grad():
                    v = float(rollout_loss(torch.tensor(va)))
                hist["step"].append(it); hist["train"].append(float(loss.detach())); hist["val"].append(v)
                log(f"  step {it:5d}  train {float(loss.detach()):.4e}  val {v:.4e}   ({K}-step rollout loss)")
        return hist

    # ---- chemistry operator (same interface as CanteraChemistry)
    @torch.no_grad()
    def advance(self, Y: np.ndarray, T: np.ndarray, dt: float):
        assert abs(dt - self.dt) < 1e-12, "surrogate was trained for a fixed CFD time step"
        Y2, T2 = Y.copy(), T.copy()
        act = np.nonzero(T >= T_ACTIVE)[0]
        if self.closure is not None and act.size:
            burned = act[(T[act] >= 2000.0) & (Y[act, self._h2] < 0.02)]
            for i in burned:
                g = self.closure
                g.TPY = float(T[i]), self.P, Y[i]
                h0 = g.enthalpy_mass
                key = (round(h0 / 2.0e3), round(float(np.dot(self._H, Y[i])) * 1e4))
                hit = self._eq_cache.get(key)
                if hit is None:
                    g.equilibrate("HP")
                    hit = (g.Y.copy(), g.T)
                    self._eq_cache[key] = hit
                Y2[i], T2[i] = hit
            self.n_closure += len(burned)
            act = np.setdiff1d(act, burned, assume_unique=True)
        if act.size == 0:
            return Y2, T2
        x = self.pack(Y[act], T[act])
        xn = torch.tensor(self._norm(self._to_z(x)), dtype=torch.float32)
        out = self._from_z(self._denorm(flow(self.f, xn).numpy().astype(np.float64)))
        yr = np.clip(out[:, :-1], 0.0, None)
        Yin = Y[act]
        if self.E is not None:
            E = self.E
            target = Yin[:, self.react_idx] @ E.T                    # H, O element mass fractions to conserve
            G = E.T @ np.linalg.inv(E @ E.T)
            for _ in range(4):                                       # alternate projection and non-negativity
                yr = yr - (yr @ E.T - target) @ G.T
                yr = np.clip(yr, 0.0, None)
            yr = yr - (yr @ E.T - target) @ G.T
            yr = np.clip(yr, 0.0, None)
        else:                                                        # fallback: conserve total reactive mass only
            tot = Yin[:, self.react_idx].sum(axis=1)
            yr *= (tot / np.maximum(yr.sum(axis=1), 1e-30))[:, None]
        Ynew = Yin.copy()
        Ynew[:, self.react_idx] = yr
        Y2[act] = Ynew
        if self.gas is not None:                                     # T from enthalpy conservation
            g = self.gas
            bad = []
            for j, i in enumerate(act):
                try:
                    g.TPY = float(T[i]), self.P, Yin[j]
                    h0 = g.enthalpy_mass
                    g.HPY = h0, self.P, Ynew[j]
                    if not (250.0 < g.T < 4500.0):
                        raise ct.CanteraError("temperature out of range")
                    T2[i] = g.T
                except ct.CanteraError:
                    bad.append(i)
            self.n_cells += len(act)
            self.n_fallback += len(bad)
            if bad and self.fallback is not None:
                bad = np.array(bad)
                Yb, Tb = self.fallback.advance(Y[bad], T[bad], dt)
                Y2[bad], T2[bad] = Yb, Tb
            elif bad:
                raise RuntimeError(f"{len(bad)} cells could not be made thermodynamically consistent and no fallback was given")
        else:
            T2[act] = np.clip(out[:, -1], 200.0, 4000.0)
        return Y2, T2

    @classmethod
    def load(cls, path: str, gas=None, closure_gas=None, fallback=None) -> "Surrogate":
        ck = torch.load(path, weights_only=False)
        sur = cls(ck["species"], ck["dt"], gas=gas, fallback=fallback, closure_gas=closure_gas)
        sur.f.load_state_dict(ck["f"])
        sur.lo, sur.hi = ck["lo"], ck["hi"]
        sur.log_mask = np.asarray(ck["log_mask"])
        return sur

    def save(self, path: str) -> None:
        torch.save({"f": self.f.state_dict(), "lo": self.lo, "hi": self.hi, "species": self.species, "dt": self.dt,
                    "log_mask": self.log_mask}, path)
