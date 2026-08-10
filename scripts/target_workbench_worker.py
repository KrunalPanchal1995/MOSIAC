#!/usr/bin/env python3
"""
target_workbench_worker.py — anaconda-side worker for MSO Studio's Target
Workbench module (part of the Optimize Workbench, Phase 2 of the 2026-08
GUI integration overhaul).

``src/MUQ-SAC/VisualAid.py``'s TargetSet/TargetChecker/DummyPointGenerator/
TargetPruner and ``combustion_target_class`` (imported by
TargetChecker.check_parses) need sklearn/scipy, neither of which is
installed in the light PySide6 GUI venv (env-isolation policy: never pip
install untested deps into a shared/light env, bridge via subprocess
instead) -- so every operation shells out here via
``mso_studio.core.target_workbench``'s ``_call_worker``, exactly like
``tools_worker.py``.

Every mode is stateless (reloads the ``.target``/``.add`` pair from disk on
every call) rather than keeping a ``TargetSet`` alive across subprocess
invocations -- simpler, and matches how the rest of this bridge works.

Usage:
    python3.9 target_workbench_worker.py <mode> <request.json> <response.json>

Modes
-----
load            {target_path, add_path}
check           {target_path, add_path}
generate_dummy  {target_path, add_path, dataset_id, points_per_zone}
coverage_prune  {target_path, add_path, n_drop, seed}
write_curated   {target_path, add_path, out_stem, out_dir, keep_line_nos,
                  dummy_rows: [{dataset_id, temperature_K, observed}],
                  add_updates: {dataset_id: {field: value}}, reason_log}
plot            {target_path, add_path, kind, dataset_id, dropped_line_nos,
                  out_png_path}

Writes {"ok": true, "result": {...}} or {"ok": false, "error": "..."} to
response.json and exits 0/1 accordingly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
_MUQSAC_SRC = _SRC / "MUQ-SAC"
if str(_MUQSAC_SRC) not in sys.path:
    sys.path.append(str(_MUQSAC_SRC))


def _load_target_set(req: dict):
    import VisualAid as VA

    add_path = req.get("add_path") or None
    ts = VA.TargetSet(req["target_path"], add_path)
    return VA, ts


def _load(req: dict) -> dict:
    _VA, ts = _load_target_set(req)
    return {
        "rows": [r.as_dict() for r in ts.rows],
        "dataset_ids": ts.dataset_ids(),
    }


def _check(req: dict) -> dict:
    import yaml

    VA, ts = _load_target_set(req)
    add_data = {}
    add_path = req.get("add_path")
    if add_path and Path(add_path).is_file():
        add_data = yaml.safe_load(open(add_path)) or {}
    checker = VA.TargetChecker(ts, add_data)
    findings = checker.run_all()
    return {"findings": [f.as_dict() for f in findings]}


def _generate_dummy(req: dict) -> dict:
    VA, ts = _load_target_set(req)
    gen = VA.DummyPointGenerator(ts, req["dataset_id"])
    out = gen.generate(points_per_zone=int(req.get("points_per_zone", 15)))
    template = gen.template_row
    return {
        "rows": out.to_dict(orient="records"),
        "template": {
            "dataset_id": template.dataset_id,
            "fuel": template.fuel,
            "oxidizer": template.oxidizer,
            "bath_gas": template.bath_gas,
            "solver": template.solver,
            "pressure_atm": template.pressure_atm,
            "data_weight": template.data_weight,
        },
    }


def _coverage_prune(req: dict) -> dict:
    VA, ts = _load_target_set(req)
    pruner = VA.TargetPruner(ts)
    keep, drop, coverage = pruner.coverage_prune(
        n_drop=int(req["n_drop"]), seed=int(req.get("seed", 0)))
    return {"keep_line_nos": keep, "drop_line_nos": drop, "coverage": coverage}


def _write_curated(req: dict) -> dict:
    from mso_io.target_add_io import write_curated_set
    from mso_io.target_add_schema import NewCaseFields

    VA, ts = _load_target_set(req)

    new_cases = []
    for row in req.get("dummy_rows", []):
        orig_ds = row["dataset_id"]
        ds_full = f"dummy_{orig_ds}"
        matches = ts.rows_for(orig_ds)
        template = matches[0] if matches else None
        fuel = dict(template.fuel) if template else {}
        oxidizer_items = list(template.oxidizer.items()) if template else [("O2", 1.0)]
        bath = dict(template.bath_gas) if template else {}
        solver = template.solver if template else "cantera"
        new_cases.append(NewCaseFields(
            dataset_id=ds_full, target_type="Tig",
            simulation="Isochor Homo Reactor", solver=solver,
            temperature_K=float(row["temperature_K"]),
            pressure_atm=(template.pressure_atm if template and template.pressure_atm else 1.0),
            fuel=fuel or {"H2": 1.0},
            oxidizer=oxidizer_items[0][0] if oxidizer_items else "O2",
            oxidizer_x=oxidizer_items[0][1] if oxidizer_items else 1.0,
            bath_gas=bath or {"Ar": 1.0},
            phi="N/A", observed=float(row["observed"]), deviation=0.0,
            data_weight=(template.data_weight if template and template.data_weight else 1.0),
            species="OH"))

    add_path = req.get("add_path") or str(Path(req["target_path"]).with_suffix(".add"))
    new_target, new_add, log_path = write_curated_set(
        req["target_path"], add_path, req["out_stem"],
        req["keep_line_nos"], new_cases=new_cases or None,
        add_updates=req.get("add_updates") or None,
        reason_log=req.get("reason_log") or None,
        out_dir=req.get("out_dir") or None,
    )

    gate_errors = []
    try:
        ts2 = VA.TargetSet(new_target, new_add)
        checker2 = VA.TargetChecker(ts2)
        gate_errors = [f.as_dict() for f in checker2.check_parses() if f.severity == "error"]
    except Exception as exc:  # noqa: BLE001 - report the gate failure itself
        gate_errors = [{"severity": "error", "line_no": None, "dataset_id": None,
                         "check": "reload_gate", "message": str(exc)}]

    return {
        "new_target_path": str(new_target), "new_add_path": str(new_add),
        "log_path": str(log_path), "gate_errors": gate_errors,
    }


def _plot(req: dict) -> dict:
    VA, ts = _load_target_set(req)
    plotter = VA.TargetSetPlotter(ts)
    kind = req["kind"]
    out_png_path = req["out_png_path"]
    Path(out_png_path).parent.mkdir(parents=True, exist_ok=True)
    if kind == "t_p_dataset":
        plotter.plot_t_p_phi(save_path=out_png_path)
    elif kind == "lntau_vs_invT":
        plotter.plot_lntau_vs_invT(
            req["dataset_id"], dropped_line_nos=req.get("dropped_line_nos", []),
            save_path=out_png_path)
    elif kind == "observed_vs_deviation":
        plotter.plot_observed_vs_deviation(save_path=out_png_path)
    elif kind == "condition_coverage":
        plotter.plot_condition_coverage(save_path=out_png_path)
    else:
        raise ValueError(f"unknown plot kind {kind!r}")
    return {"png_path": out_png_path}


_HANDLERS = {
    "load": _load,
    "check": _check,
    "generate_dummy": _generate_dummy,
    "coverage_prune": _coverage_prune,
    "write_curated": _write_curated,
    "plot": _plot,
}


def main() -> int:
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <mode> <request.json> <response.json>", file=sys.stderr)
        return 2
    mode, req_path, resp_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])

    handler = _HANDLERS.get(mode)
    if handler is None:
        resp_path.write_text(json.dumps({
            "ok": False,
            "error": f"Unknown mode '{mode}'. Available: {', '.join(sorted(_HANDLERS))}",
        }))
        return 1

    try:
        request = json.loads(req_path.read_text())
        result = handler(request)
        resp_path.write_text(json.dumps({"ok": True, "result": result}))
        return 0
    except Exception as exc:  # noqa: BLE001 - the GUI reads response.json either way
        resp_path.write_text(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
