# Roadmap & sequencing — community-gap implementation

Prioritised by the source doc's own "highest-signal" test: (a) unresolved in the
thread, (b) reported independently by >1 person/venue, or (c) open for years —
crossed with cheapness given the existing RMIP infrastructure.

## Priority order (recommended)

| Order | WS | Why now | Effort | Risk | Depends on |
|-------|----|---------|--------|------|-----------|
| 1 | **W1** YAML validator & migration linter | Closest to the stated goal ("AI-generated mechanisms need a second pair of eyes"); extends the shipped `mechanism_check`; cheap | S | Low | mechanism_check |
| 2 | **W2** CHEMKIN preflight & converter | Single biggest recurring pain (Cluster 2); reuses the converter GUI | M | Low-Med | — |
| 3 | **W6** IDT-sensitivity first-class | 8-year ask; **~70% already built** (`CanteraSensitivityRunner`); mostly polish + docs | S | Low | sensitivity_runner |
| 4 | **W4** Thermo/transport provenance | Cross-community trust issue; self-contained; needs a reference dataset (Burcat) | M | Med (data licensing) | thermo_fitter |
| 5 | **W8** Silent-failure & version regression | High-value cheap detectors (P33/P35) + a durable CI-style harness | M | Low | mechanism_check, simulation runners |
| 6 | **W5** Surface / heterogeneous support | The richest vein but the heaviest; phased (W5a reactor → W5b cross-solver → W5c liquid) | L | High | Cantera Interface API |
| 7 | **W3** OpenSmoke importer | Narrower audience; well-defined once W2 preflight exists | M | Med | W2 |
| 8 | **W7** RMG explainability & supervisor | Depends on an RMG install; wrapper-only (no RMG internals) | M-L | Med | rmg_interface, `/data/OPEN_CODE/RMG_py` |
| 9 | **W9** Onboarding / preflight | Lower severity, high frequency; polish layer | S | Low | all |

**Legend:** S ≈ days, M ≈ 1–2 weeks, L ≈ 3+ weeks of focused work (single dev).

## Phasing

**Phase A — "second pair of eyes" (validators & converters).** W1 → W2 → W3.
Delivers the linter/converter cluster the source doc flags as the closest match
to the user's framing. Each ships behind the existing `rmip check` / converter
GUI and the new `rmip migrate` / `rmip preflight` subcommands.

**Phase B — trust & correctness.** W4 → W8. Thermo provenance + the silent-failure
and version-regression harnesses. These make results *trustworthy*, complementing
Phase A's *loadable*.

**Phase C — heterogeneous & generation.** W5 → W7. The hard, high-ceiling work:
finite bulk-solid reactors and RMG explainability/supervision. Gated behind the
earlier phases because they are heavier and lower-frequency.

**Phase D — polish.** W9 and the P12 polymer exploration (kept as a spike, not a
committed deliverable — see `W7_rmg_explainability_supervisor.md §Polymer`).

## Cross-cutting conventions (apply to every workstream)

- **Env isolation.** Never `pip install` untested deps into the shared anaconda
  env. Heavy/optional backends (RMG, extra thermo DBs) live in dedicated venvs
  and are bridged by subprocess — mirror `simulation/subprocess_util.py` and the
  chaospy/cvxpy venv pattern.
- **One engine, two surfaces.** Every capability is a library module first, then
  a `rmip <cmd>` CLI subcommand, then (where interactive) a GUI registered in
  `launcher_gui.py`. The `mechanism_check`/`check`/`mechanism_check_gui` trio is
  the reference shape.
- **Structured findings.** Reuse the `Finding`/`FixOption`/`CheckReport` model
  from `mechanism_check.py` so every diagnostic emits JSON + coloured text and
  plugs into the existing report rendering. New checks should register into the
  `rmip check` battery where they fit, not spawn parallel report formats.
- **Detect → auto-fix-obvious → offer-choices-on-ambiguity.** The repair contract
  the shipped tool established (auto vs choice `FixOption`s) is the house style
  for every new fixer.
- **Fixtures + tests per item.** Each workstream ships deliberately-broken
  fixtures (mirror `src/rmip/tests/fixtures/_make_broken_mech.py`) and a
  `test_*.py`, and appends a Done row to the workstream doc.
- **Launcher path.** Everything runs via `python rmip_cli.py …` (never `cd src`).

## Definition of done (per workstream)

1. Library module(s) with docstrings tying each function to its P#.
2. CLI subcommand(s) + GUI surface where interactive.
3. Deliberately-broken fixtures + a green `test_*.py`.
4. A worked example on a real mechanism from `MECHANISM/`.
5. Doc updated: move the P# rows from GAP→DONE in `00_GAP_ANALYSIS.md` and
   `BACKLOG.md`, with module + test names (bug.md convention).
