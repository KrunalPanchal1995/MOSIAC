# Backlog — every problem mapped to a workstream + status

Mirrors the `bug.md`/`BUG.md` convention: one row per problem, its workstream, and
status. Update status as items ship (append module + test name).

Status key: **DONE** (already in the suite) · **PLAN** (scoped, not started) ·
**OUT** (out of scope, see `99_OUT_OF_SCOPE.md`).

| P# | One-line | WS | Status | Notes / module when shipped |
|----|----------|----|--------|-----------------------------|
| P1 | LLM stale keyword `stoichiometric` | W1 | **DONE** | `yaml_validator.py` + `schema_deprecation` check + `rmip migrate`; `test_yaml_validator.py` (10) |
| P2 | `ck2yaml` cryptic tracebacks on surface mech | W2 | **DONE** | `chemkin_preflight.py` + `rmip preflight`; `test_chemkin_preflight.py` (15) |
| P3 | `NONCON` no Cantera semantics | W2 | **DONE** | detected+flagged (preflight) |
| P4 | surface-site balancing manual | W2/W5 | **DONE** | `analysis/surface_sites.py::balance_surface_sites`; `test_multiphase_sanity.py` |
| P5 | OpenSmoke `LIQUID`/`MATERIAL` mapping | W3 | **DONE** | `io/importers/` + `rmip import`; `test_importers.py` (8); refuse-or-acknowledge contract |
| P6 | bulk phase = infinite reservoir | W5a | **DONE** | `simulation/finite_solid_reactor.py` + `rmip react-solid`; `test_finite_solid_reactor.py` (14) |
| P7 | clamping injects artificial mass | W5a | **DONE** | rates vanish with state (area model / mass action) + audited projection; element drift ~1e-15 |
| P8 | coverage Σθ=1 drift | W5a | **DONE** | extensive surface moles → Σθ=1 by construction + site-total audit |
| P9 | non-isothermal finite-solid fragile | W5a | **DONE** | adaptive-dt BDF ladder + isothermal fallback; both modes tested to burnout |
| P10 | Arkane K-salt thermo off vs JANAF | W4 | **DONE** | `thermo_provenance.py` + `rmip thermo-check` + `thermo_provenance` check; `test_thermo_provenance.py` (12) |
| P11 | `.asc` link files irreversible | — | OUT | detect+advise (W2) |
| P12 | polymer / large-molecule generation | W7e | **DONE** (spike) | `W7e_polymer_spike_memo.md` — conditional GO, scoped; no generator committed |
| P13 | `bulk` keyword unrecognised | W2 | **DONE** | detected+flagged (preflight) |
| P14 | encrypted mechanisms | — | OUT | detect+advise |
| P15 | RMG non-reproducible across versions | W7d/W8b | **DONE** | `generation/rmg_diff.py` + `rmip rmg-diff` (structural half); `analysis/version_regression.py::diff_result_sets` (behavioural half, generic over any two result sets); `test_version_regression.py` |
| P16 | RMG prune by count not memory | W7b | **DONE** (wrap) | `generation/rmg_supervisor.py` RSS budget via /proc; `test_rmg_w7.py` |
| P17 | why species promoted edge→core | W7a | **DONE** | `generation/rmg_explainer.py` + `rmip rmg-explain`; `test_rmg_w7.py` |
| P18 | no CHEMKIN structural preflight | W2 | **DONE** | `chemkin_preflight.py` (YAML preflight already DONE) |
| P19 | RMG no ionic species | W4 | OUT→detect | charge flag exists |
| P20 | IDT sensitivity not built-in | W6 | **DONE** | `idt_sensitivity.py` + `rmip idt-sens` + `idt_sensitivity_gui.py`; `test_idt_sensitivity.py` (12); brute≡cvodes |
| P21 | RMG vs Cantera surface solver differ | W5b | **DONE** (detector) | `simulation/surface_crosscheck.py` + `rmip surface-crosscheck`; `test_surface_crosscheck.py` (12) |
| P22 | multidentate Keq wrong (RMG) | W5b/W4 | OUT→detect | |
| P23 | bidentate sticking wrong (RMG) | — | OUT | fixed upstream |
| P24 | RMG can't do surface | — | OUT | document |
| P25 | liquid mole-fraction unphysical | W5c | **DONE** | `analysis/multiphase_sanity.py` + `multiphase_sanity` check; 10x gap reproduced+explained |
| P26 | can't inspect RMG edge (2007) | W7a | **DONE** | `inspect` via rmg-explain edge section (log + chem_edge merge) |
| P27 | O3 thermo dataset dispute | W4 | **DONE** | same module; discrepancy magnitude + systematic/distributed classifier; never auto-fixed |
| P28 | LFS shifts across Cantera versions | W8b | **DONE** | `analysis/version_regression.py` + `_regression_worker.py` (env-isolated, runs under any Cantera venv) + `rmip regression [--env --bless]`; committed goldens (Cantera 3.0.1); `test_version_regression.py` (11) |
| P29 | CTI→YAML renames silent trap | W1 | **DONE** | same as P1 (W1) |
| P30 | RMG never terminates | W7b | **DONE** (wrap) | supervisor stall/wall budgets + relaxation + partial report; `rmip rmg-supervise` |
| P31 | 8-carbon silent truncation | — | OUT | historical |
| P32 | ANSYS Chemkin generic errors | — | OUT | our linters embody fix |
| P33 | import succeeds, rates silently zero | W8a | **DONE** | `zero_rates` check in `mechanism_check.py` (dead reactions + decoupled species + all-rates-zero error); `test_silent_failure.py` (15) |
| P34 | Debug-vs-Release path bug | — | OUT | Cantera build |
| P35 | case-mismatch `AR`/`Ar` across sections | W2/W8a | **DONE** | CHEMKIN: preflight case-consistency + reaction-scoped fix; YAML analogue (W8a): `name_consistency` check (case-variant refs, case-twin species, undeclared refs; raw scan works pre-load) + `rename_species_ref` auto-fix; `test_silent_failure.py` |
| P36 | which example covers a task | W9b | **DONE** | `config/recipes.py` (21 curated recipes, fuzzy router) + `rmip how-do-i` + launcher Doctor/Recipes pane; `test_preflight_recipes.py` |
| P37 | platform install failures | — | OUT | `rmip doctor` reports only |
| P38 | toolchain prereqs undocumented | W9a | **DONE** | `config/preflight.py` (probes every isolated venv/binary with exact remediation) + `rmip doctor [--task --rmg-input]`; `test_preflight_recipes.py` (16) |
| P39 | duplicate library/reaction in RMG input | W7c/W9c | **DONE** | `generation/rmg_lint.py` + `rmip rmg-lint`; ast-static, #2979/#2882/#2485 |

## Rollup
- **DONE (shipped this program):** P1, P2, P3, P4, P5, P6, P7, P8, P9, P10, P12(spike), P13, P15, P16, P17, P18, P20, P21, P25, P26, P27, P28, P29, P30, P33, P35, P36, P38, P39 — **W1–W9 all shipped** (883 tests green).
- **PLAN (buildable, remaining):** none — the P1–P39 program is complete.
- **OUT (with detector/wrapper where noted):** remaining out-of-scope rows above.

## Already shipped this program (context — the prior phase)
The mechanism health-check engine (`mechanism_check.py` + `mechanism_fixer.py` +
`check` CLI + `mechanism_check_gui.py`, 17 tests) already covers the load/rate/
collision/thermo-discontinuity/duplicate/pdep/completeness/unit diagnostics — see
`MECHANISM_CHECK_RESEARCH.md`. W1/W2/W8 **extend** that engine rather than duplicate it.
