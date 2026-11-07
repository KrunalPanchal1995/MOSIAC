"""Run the whole loop once:  construct -> explain -> calibrate (twin) -> reduce -> CFD -> Neural-ODE surrogate in CFD.

    python -m mosiac_pipeline.run_end_to_end [--out mosiac_pipeline/out] [--steps 4000]

Writes report.json, end_to_end.png and surrogate.pt to --out, and prints a summary table.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from . import cfd1d as C
from . import mechanism as M
from .surrogate import Surrogate

TRAIN_CASES = [
    C.HotSpotCase("train-A", T_bg=950.0, T_hot=1450.0, width_m=1.0e-3, phi=1.0),
    C.HotSpotCase("train-B", T_bg=1050.0, T_hot=1500.0, width_m=1.5e-3, phi=1.0),
    C.HotSpotCase("train-C", T_bg=1000.0, T_hot=1400.0, width_m=1.0e-3, phi=0.8),
    C.HotSpotCase("train-D", T_bg=1000.0, T_hot=1550.0, width_m=2.0e-3, phi=1.2),
    C.HotSpotCase("train-E", T_bg=1100.0, T_hot=1500.0, width_m=1.2e-3, phi=0.9),
]
TEST_CASE = C.HotSpotCase("held-out", T_bg=1000.0, T_hot=1500.0, width_m=1.2e-3, phi=1.0)


def element_mass_fractions(gas, Y: np.ndarray) -> np.ndarray:
    """Per-cell mass fraction of every element, from species mass fractions."""
    W = gas.molecular_weights
    atoms = np.array([[gas.n_atoms(k, m) for m in range(gas.n_elements)] for k in range(gas.n_species)], float)
    return (Y / W) @ (atoms * gas.atomic_weights)


def compare(ref: C.RunResult, other: C.RunResult, gas) -> dict:
    z0 = element_mass_fractions(gas, np.tile(C.initial_state(other.case, gas)[2][0], (1, 1)))[0]
    z1 = element_mass_fractions(gas, other.Y_final).mean(axis=0)
    h2o = gas.species_index("H2O")
    return {
        "t50_ms": C.time_to_fraction(other, 0.5) * 1e3,
        "t95_ms": C.time_to_fraction(other, 0.95) * 1e3,
        "T_mean_final_K": float(other.T_final.mean()),
        "final_T_profile_rel_L2": float(np.linalg.norm(other.T_final - ref.T_final) / np.linalg.norm(ref.T_final)),
        "final_H2O_profile_rel_L2": float(np.linalg.norm(other.Y_final[:, h2o] - ref.Y_final[:, h2o]) / np.linalg.norm(ref.Y_final[:, h2o])),
        "mean_T_trace_rms_K": float(np.sqrt(np.mean((other.T_mean - ref.T_mean) ** 2))),
        "element_drift_max_rel": float(np.max(np.abs(z1 - z0) / np.maximum(z0, 1e-30))),
        "chemistry_seconds": other.chem_seconds,
        "chemistry_speedup_vs_reference": ref.chem_seconds / max(other.chem_seconds, 1e-12),
    }


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).parent / "out"))
    ap.add_argument("--steps", type=int, default=4000, help="one-step surrogate training steps")
    ap.add_argument("--rollout-steps", type=int, default=2500, help="rollout surrogate training steps")
    ap.add_argument("--only", default="", help="comma-separated variant ids to run, e.g. V5,V6")
    ap.add_argument("--skip-rollout", action="store_true", help="skip the (slow) rollout-trained variant")
    ap.add_argument("--mechanism", default="h2o2.yaml")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rep: dict = {}
    t_all = time.perf_counter()

    print("[1/6] construct")
    gas, rep["construct"] = M.construct(a.mechanism)
    print(f"      {rep['construct']['n_reactions']} reactions, {len(rep['construct']['species'])} species, elements balanced")

    print("[2/6] explain: which reactions control ignition delay (T=1100 K, phi=1)")
    ex = M.explain(gas)
    rep["explain"] = {k: v for k, v in ex.items() if k != "sensitivity"}
    for r in ex["top"][:4]:
        print(f"      {r['reaction']:<28s} dln(tau)/dln(k) = {r['dln_tau_dln_k']:+.2f}")

    print("[3/6] calibrate (synthetic twin experiment)")
    cal = M.calibrate_twin(gas, ex["sensitivity"])
    mult = cal.pop("multipliers")
    rep["calibrate"] = cal
    print(f"      rms ln-error of ignition delays: {cal['rms_log_error_before']:.3f} -> {cal['rms_log_error_after']:.4f}")

    print("[4/6] reduce")
    M.set_multipliers(gas, mult)
    red = M.reduce_reactions(gas, mult)
    reduced = red.pop("mechanism")
    rep["reduce"] = red
    print(f"      {red['n_full']} -> {red['n_reduced']} reactions, max ignition-delay error {red['max_rel_delay_error']*100:.2f}%")

    print("[5/6] CFD on the held-out hot-spot case: full vs reduced mechanism")
    ref_chem = C.CanteraChemistry(gas)
    ref = C.run(TEST_CASE, ref_chem, gas)
    redr = C.run(TEST_CASE, C.CanteraChemistry(reduced), reduced)
    rep["cfd"] = {"case": TEST_CASE.__dict__, "reduced_vs_full": compare(ref, redr, gas),
                  "full": {"t50_ms": C.time_to_fraction(ref, 0.5) * 1e3, "t95_ms": C.time_to_fraction(ref, 0.95) * 1e3,
                           "chemistry_seconds": ref.chem_seconds}}
    print(f"      full: t50 = {rep['cfd']['full']['t50_ms']:.3f} ms; reduced: t50 = {rep['cfd']['reduced_vs_full']['t50_ms']:.3f} ms, "
          f"final-T error {rep['cfd']['reduced_vs_full']['final_T_profile_rel_L2']*100:.2f}%")

    print("[6/6] Neural-ODE surrogate: train on CFD states of other cases, then run it inside the CFD on the held-out case")
    ins, outs = [], []
    for case in TRAIN_CASES:
        r = C.run(case, C.CanteraChemistry(reduced), reduced, record=True)
        ins.append(r.pairs["in"]); outs.append(r.pairs["out"])
        print(f"      training CFD {case.name}: {len(r.pairs['in'])} chemistry-step samples")
    x_in, x_out = np.vstack(ins), np.vstack(outs)
    # rollout start states: stratified by temperature so the rare ignition states are not swamped by burned gas
    rng = np.random.default_rng(0)
    Tn = x_in[:, -1]
    starts = []
    for lo, hi in ((C.T_ACTIVE, 1150.0), (1150.0, 2000.0), (2000.0, 1e9)):
        pool = np.nonzero((Tn >= lo) & (Tn < hi))[0]
        starts.append(rng.choice(pool, size=min(len(pool), 1200), replace=len(pool) < 1200))
    x0 = x_in[np.concatenate(starts)]
    K = 12

    species = list(reduced.species_names)
    variants = [
        ("V1 one-step, linear state, mass-renormalised", dict(log_radicals=False, constrained=False, rollout=False)),
        ("V2 one-step, radicals in log10", dict(log_radicals=True, constrained=False, rollout=False)),
        ("V3 V2 + element projection, enthalpy T, fallback", dict(log_radicals=True, constrained=True, rollout=False)),
    ]
    if not a.skip_rollout:
        variants.append((f"V4 V3 trained on {K}-step rollouts", dict(log_radicals=True, constrained=True, rollout=True)))
    variants.append(("V5 V2 + burned-gas equilibrium closure", dict(log_radicals=True, constrained=False, rollout=False, closure=True)))
    if not a.skip_rollout:
        variants.append((f"V6 {K}-step rollouts, log radicals + burned-gas closure", dict(log_radicals=True, constrained=False, rollout=True, closure=True)))
    if a.only:
        wanted = tuple(a.only.split(","))
        variants = [v for v in variants if v[0].split()[0] in wanted]
    seq = None
    ablation, best = [], None
    for name, opt in variants:
        print(f"      variant {name}")
        sur = Surrogate(species, TEST_CASE.dt, gas=reduced if opt["constrained"] else None,
                        fallback=C.CanteraChemistry(reduced) if opt["constrained"] else None, log_radicals=opt["log_radicals"],
                        closure_gas=reduced if opt.get("closure") else None)
        t0 = time.perf_counter()
        if opt["rollout"]:
            if seq is None:
                seq = C.chemistry_rollouts(C.CanteraChemistry(reduced), x0, TEST_CASE.dt, K)
            hist = sur.fit_rollouts(seq, steps=a.rollout_steps, log=lambda *_: None)
        else:
            hist = sur.fit(x_in, x_out, steps=a.steps, log=lambda *_: None)
        train_s = time.perf_counter() - t0
        sres = C.run(TEST_CASE, sur, reduced)
        m = compare(ref, sres, gas)
        m.update({"variant": name, "training_seconds": train_s, "final_train_loss": hist["train"][-1], "final_val_loss": hist["val"][-1],
                  "fallback_cell_fraction": sur.n_fallback / max(sur.n_cells, 1) if opt["constrained"] else None,
                  "closure_cell_steps": sur.n_closure})
        ablation.append(m)
        print(f"         t50 {m['t50_ms']:.3f} ms (full {rep['cfd']['full']['t50_ms']:.3f}) | final-T err {m['final_T_profile_rel_L2']*100:.1f}% | "
              f"mean-T trace RMS {m['mean_T_trace_rms_K']:.0f} K | element drift {m['element_drift_max_rel']*100:.1f}% | "
              f"chemistry {m['chemistry_speedup_vs_reference']:.1f}x | fallback {m['fallback_cell_fraction']}")
        if best is None or m["mean_T_trace_rms_K"] < best[0]["mean_T_trace_rms_K"]:
            best = (m, sur, sres, hist)
    bm, bsur, bres, bhist = best
    bsur.save(str(out / "surrogate.pt"))
    rep["surrogate"] = {"training_start_states": int(len(x0)), "rollout_steps": K, "parameters": int(sum(p.numel() for p in bsur.f.parameters())),
                        "training_cases": [c.name for c in TRAIN_CASES], "test_case": TEST_CASE.name,
                        "ablation": ablation, "best_variant": bm["variant"], "reference_integrator_failures": int(ref_chem.n_failed),
                        "selection_rule": "lowest RMS error of the domain-mean temperature trace against the full-mechanism CFD"}
    sres = bres
    hist = bhist

    rep["total_seconds"] = time.perf_counter() - t_all
    (out / "report.json").write_text(json.dumps(rep, indent=2, default=float))
    _figure(out / "end_to_end.png", ref, redr, sres, hist)
    print(f"done in {rep['total_seconds']:.0f} s -> {out}")
    return rep


def _figure(path: Path, ref, redr, sres, hist) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 2, figsize=(11, 7.5))
    for res, lab, st in ((ref, "full mechanism", "-"), (redr, "reduced mechanism", "--"), (sres, "Neural-ODE surrogate", ":")):
        ax[0, 0].plot(res.t * 1e3, res.T_mean, st, lw=2, label=lab)
        ax[0, 1].plot(res.t * 1e3, res.active_frac, st, lw=2, label=lab)
        ax[1, 0].plot(res.x * 1e3, res.T_final, st, lw=2, label=lab)
    ax[0, 0].set(xlabel="time [ms]", ylabel="domain-mean T [K]", title="Held-out hot-spot case")
    ax[0, 1].set(xlabel="time [ms]", ylabel="fraction of domain ignited", title="Ignition spread")
    ax[1, 0].set(xlabel="x [mm]", ylabel="T at t_end [K]", title="Final temperature profile")
    ax[1, 1].semilogy(hist["step"], hist["train"], label="train"); ax[1, 1].semilogy(hist["step"], hist["val"], label="validation")
    ax[1, 1].set(xlabel="step", ylabel="normalised increment MSE", title="Neural-ODE training")
    for a_ in ax.ravel():
        a_.legend(frameon=False, fontsize=8); a_.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


if __name__ == "__main__":
    main()
