"""Check a trained surrogate on hot-spot cases that were in neither the training set nor the main held-out case.

    python -m mosiac_pipeline.evaluate_extra [--surrogate mosiac_pipeline/out/surrogate.pt]

Rebuilds the calibrated, reduced mechanism (stages 1-4, about 10 s), runs each case with the full mechanism and with the
surrogate (burned-gas closure on), and prints / saves the comparison. All cases lie inside the training range of
background temperature (950-1100 K) and equivalence ratio (0.8-1.2): this tests interpolation, not extrapolation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import cfd1d as C
from . import mechanism as M
from .run_end_to_end import compare
from .surrogate import Surrogate

EXTRA_CASES = [
    C.HotSpotCase("extra-1", T_bg=1080.0, T_hot=1480.0, width_m=1.4e-3, phi=0.95),
    C.HotSpotCase("extra-2", T_bg=960.0, T_hot=1520.0, width_m=1.1e-3, phi=1.10),
    C.HotSpotCase("extra-3", T_bg=1020.0, T_hot=1500.0, width_m=1.2e-3, phi=0.85),
]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--surrogate", default=str(Path(__file__).parent / "out" / "surrogate.pt"))
    ap.add_argument("--out", default=str(Path(__file__).parent / "out" / "extra_cases.json"))
    a = ap.parse_args(argv)
    gas, _ = M.construct()
    ex = M.explain(gas)
    mult = M.calibrate_twin(gas, ex["sensitivity"]).pop("multipliers")
    M.set_multipliers(gas, mult)
    reduced = M.reduce_reactions(gas, mult)["mechanism"]
    sur = Surrogate.load(a.surrogate, closure_gas=reduced)
    rows = []
    for case in EXTRA_CASES:
        ref = C.run(case, C.CanteraChemistry(reduced), reduced)
        res = C.run(case, sur, reduced)
        m = compare(ref, res, reduced)
        m.update({"case": case.name, "T_bg": case.T_bg, "phi": case.phi, "t50_reference_ms": C.time_to_fraction(ref, 0.5) * 1e3})
        rows.append(m)
        print(f"{case.name}: T_bg={case.T_bg:.0f} phi={case.phi:.2f} | ignition {m['t50_ms']:.3f} ms (reference {m['t50_reference_ms']:.3f}) | "
              f"final-T error {m['final_T_profile_rel_L2']*100:.1f}% | mean-T trace RMS {m['mean_T_trace_rms_K']:.0f} K | "
              f"chemistry {m['chemistry_speedup_vs_reference']:.1f}x faster")
    Path(a.out).write_text(json.dumps(rows, indent=2, default=float))
    return rows


if __name__ == "__main__":
    main()
