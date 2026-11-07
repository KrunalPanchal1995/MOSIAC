# mosiac_pipeline: the whole loop, once, on H2/air

A small, runnable demonstration that takes a reaction mechanism through every stage of the MOSIAC story and uses it in a
CFD run, with a Neural-ODE surrogate standing in for the chemistry inside that same CFD.

```bash
python -m mosiac_pipeline.run_end_to_end            # about 12 minutes on CPU; --skip-rollout makes it about 5
pytest tests/test_mosiac_pipeline_smoke.py          # about 30 seconds
```

Needs Python 3.12 with `cantera`, `torch` (CPU is fine), `scipy`, `matplotlib`. Outputs: `out/report.json`, `out/end_to_end.png`, `out/surrogate.pt`.

## Stages, in Bloom's order, and what is real

| # | Stage (Bloom's level) | What the code does | Status |
|---|---|---|---|
| 1 | Construct (Remember) | Loads the published H2/O2 mechanism (Cantera `h2o2.yaml`) and checks every reaction conserves every element | Real. Mechanism *generation* with RMG-Py lives in `src/rmip/generation`; it is not run here |
| 2 | Explain (Understand) | Brute-force sensitivity of ignition delay to every reaction rate | Real. Top reaction is H + O2 <=> O + OH, negative sign, as chain-branching chemistry should give |
| 3 | Calibrate (Evaluate) | Recovers rate multipliers from ignition-delay targets | **Synthetic twin experiment**: targets come from a deliberately perturbed copy, since no experimental data is bundled. It recovers all four multipliers exactly. This is not MOSIAC's multi-stage optimiser; that stays in `src/MUQ-SAC` |
| 4 | Reduce (Analyze) | Drops reactions whose removal barely changes ignition delay | Real: 29 -> 14 reactions, worst ignition-delay error 1.2 %. Uncertainty quantification (MUQ-SAC) is not re-run here |
| 5 | Use in CFD (Apply) | 1-D reaction-diffusion solver, operator splitting, pluggable chemistry operator | Real but deliberately simple, see limits below. Reduced mechanism matches full: final temperature profile within 0.04 % |
| 6 | Surrogate in CFD (Create) | Neural ODE (`dx/ds = f(x)`, RK4) trained on states from five other hot-spot cases, then run in the same CFD on a held-out case | Real, **not CFD-grade yet** |

## Result of stage 6 (held-out case, identical conditions for every variant)

Reference: full mechanism, ignition of the whole domain at t = 0.200 ms. Selection rule: lowest RMS error of the domain-mean temperature trace.

| Variant | Ignition time | Final-T profile error | Mean-T trace RMS | Element drift | Chemistry speed-up |
|---|---|---|---|---|---|
| V1 one-step fit, linear state | 0.100 ms | 1.0 % | 263 K | 0.8 % | 20x |
| **V2 + radicals learned in log10 (selected)** | 0.250 ms | 3.5 % | **186 K** | 4.4 % | 19x |
| V3 + element projection, enthalpy temperature, fallback to the mechanism | 0.040 ms | 10.0 % | 427 K | 15.2 % | 3x (6 % of cells fall back) |
| V4 V3 trained on 12-step rollouts | 0.130 ms | 9.9 % | 258 K | 11.4 % | 10x (0.8 % fall back) |

What this says, plainly:

* The surrogate follows the shape of the ignition and lands within a few percent in final temperature (selected variant), and the
  chemistry step is about 19x faster. **It does not reproduce the ignition time (25 % late) or the final temperature profile
  (wrong shape, about 100 K off), so it is a demonstration, not a validated model.**
* Teacher-forced one-step errors are small in every regime (induction, ignition, burned). The failure is **free-running accumulation**:
  in the burned gas a tiny bias compounds over about 60 steps because nothing pulls the learned map back to equilibrium.
* Things that looked sensible did not help: the element projection made drift *worse* (15 % vs 4 %) instead of removing it, which I did not
  resolve; rollout training helped the final state but was slow to converge (7 minutes, loss still falling). Each of these is a
  starting point for the real research problem, not a finished answer.
* One bug found on the way and fixed: Cantera's integrator clock grew large over thousands of tiny advances and eventually failed on
  an ordinary state; the operator now resets it per cell.

## Limits of the CFD (so nobody mistakes it for a validated flame solver)

1-D, constant pressure, **no flow**: no pressure waves, no thermal expansion, no advection. Unity Lewis number and a single
temperature-dependent diffusivity for heat and all species. First-order operator splitting, 100 cells, 10 microsecond steps, hot spot
in uniform H2/air at 1 atm. It exists to exercise the chemistry-operator seam that a production solver would call.

## Not done

* A production CFD solver using a MOSIAC mechanism: PANSOPHIA (Julia) has no general mechanism importer yet, so this demo uses its own small solver.
* Training on a calibrated mechanism from *real* experimental targets, and re-running MUQ-SAC uncertainty on the reduced mechanism.
* A surrogate accurate enough to trust: more data, a larger network, longer rollouts, and a way to stop burned-gas drift.
* Variable time step: the surrogate is tied to the 10 microsecond step it was trained for.

## Files

`mechanism.py` stages 1-4 | `cfd1d.py` solver and Cantera chemistry operator | `surrogate.py` Neural ODE, training, operator | `run_end_to_end.py` driver, metrics, figure.
