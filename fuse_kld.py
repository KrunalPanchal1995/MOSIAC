#!/usr/bin/env python3
"""
fuse_kld.py
===========
Driver for the Keromnes 2013 / Li 2015 / Davis 2005 fusion task
(2026-07-14 fusion-engine stress test session).

Builds ONE fused mechanism from mechanism ids [1 (Keromnes), 2 (Li), 3
(Davis)] in the given DB, using either priority-pick (--mode priority:
for every shared reaction, verbatim-copy from the highest-priority present
source, Keromnes > Li > Davis) or consensus-mean (--mode mean: geometric
mean A, arithmetic mean n/Ea across present sources -- FusionEngine's
existing default FUSE-bucket behavior) fusion strategy.

Usage
-----
    python3 fuse_kld.py --mode priority --db outputs/.../fusion_stress.db \\
        --out-dir outputs/.../priority --name Fused_priority_KLD
    python3 fuse_kld.py --mode mean --db outputs/.../fusion_stress.db \\
        --out-dir outputs/.../mean_unsrt --name Fused_mean_KLD
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent
_SRC = str(_REPO / "src")
if _SRC not in sys.path:
    sys.path.append(_SRC)

PRIORITY_ORDER = [1, 2, 3]  # Keromnes2013=1, Li2015=2, Davis2005=3


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--mode", choices=["priority", "mean"], required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--mech-ids", nargs="+", type=int, default=[1, 2, 3])
    args = ap.parse_args()

    from rmip.analysis.graph_comparator import GraphComparator
    from rmip.analysis.fusion import FusionEngine
    from rmip.io.chemkin_writer import ChemkinWriter

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmp = GraphComparator(args.db, tol_A=0.01, tol_n=0.001, tol_Ea=100.0)
    cmp_result = cmp.compare(args.mech_ids)

    engine = FusionEngine(args.db)
    priority_order = PRIORITY_ORDER if args.mode == "priority" else None
    result = engine.fuse(cmp_result, name=args.name, priority_order=priority_order)

    print(result.summary())
    print(f"provenance: {json.dumps(result.provenance, indent=2)}")

    # ── Write CHEMKIN + Cantera YAML ────────────────────────────────────
    chemkin_path = str(out_dir / f"{args.name}.inp")
    thermo_path  = str(out_dir / f"{args.name}.dat")
    writer = ChemkinWriter(args.db, use_original_units=True)
    writer.write(result.fused_mechanism_id, chemkin_path,
                 thermo_path=thermo_path, include_thermo_in_mech=True)
    try:
        yaml_path = writer.convert_to_cantera_yaml(
            chemkin_path, output_yaml=str(out_dir / f"{args.name}.yaml"),
        )
        print(f"✓ Cantera YAML → {yaml_path}")
    except Exception as exc:
        print(f"⚠ ck2yaml conversion failed (CHEMKIN files still written): {exc}")

    # ── Union spec + MSO bounds ─────────────────────────────────────────
    engine.export_union_spec(result, str(out_dir / f"{args.name}_union_spec.json"))
    engine.export_mso_bounds(result, str(out_dir / f"{args.name}_mso_bounds.json"))

    # ── Element balance check ───────────────────────────────────────────
    from rmip.stubs import FusionEngine as StubFusionEngine
    balance_checker = StubFusionEngine.__new__(StubFusionEngine)
    balance_checker._db_path = args.db
    balance = balance_checker.validate_element_balance(result.fused_mechanism_id)
    print(f"Element balance: {balance['balanced']}, violations: {len(balance['violations'])}")
    if balance["violations"]:
        print(f"  {balance['violations'][:10]}")

    # ── Priority/mean-specific provenance ───────────────────────────────
    if args.mode == "priority":
        per_reaction = []
        for r in result.reaction_records:
            chosen = None
            if r.treatment.value == "PRIORITY":
                chosen = next((m for m in PRIORITY_ORDER if m in r.source_mech_ids), r.source_mech_ids[0])
            per_reaction.append({
                "canonical_key": r.canonical_key,
                "occurrence_index": r.occurrence_index,
                "formula_string": r.formula_string,
                "treatment": r.treatment.value,
                "source_mech_ids_present": r.source_mech_ids,
                "chosen_source_mech_id": chosen,
                "A_si": r.A_si, "n": r.n, "Ea_si": r.Ea_si,
            })
        with open(out_dir / f"{args.name}_priority_provenance.json", "w") as fh:
            json.dump({
                "priority_order": PRIORITY_ORDER,
                "priority_order_names": {1: "Keromnes2013", 2: "Li2015", 3: "Davis2005"},
                "reactions": per_reaction,
            }, fh, indent=2)
        n_from = {mid: sum(1 for pr in per_reaction if pr["chosen_source_mech_id"] == mid)
                  for mid in PRIORITY_ORDER}
        print(f"Priority-pick source counts (shared reactions only): {n_from}")

    with open(out_dir / f"{args.name}_fusion_summary.json", "w") as fh:
        json.dump(result.to_dict(), fh, indent=2, default=str)

    print(f"\n✓ Fused mechanism id={result.fused_mechanism_id} written to {out_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
