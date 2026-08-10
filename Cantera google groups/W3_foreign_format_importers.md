# W3 — Foreign-format importers (OpenSmoke → Cantera YAML)

**Closes:** P5 (OpenSmoke `LIQUID`/`MATERIAL` heterogeneous model doesn't map onto
Cantera's site/interface model). Extensible to other third-party formats.
**Effort:** M · **Risk:** Med · **Depends on:** W2 preflight, W5 surface model.

## Problem
Converting third-party kinetics (OpenSmoke shown; also RMG-Chemkin variants) fails
not on syntax but on **modeling assumptions**: OpenSmoke's `LIQUID`/`MATERIAL`
keywords encode a bulk-liquid-reactant → gas-product heterogeneous model with an
implicit transport assumption that has no direct analogue in Cantera's
site/interface model. This needs re-derivation, not translation — and today there
is no importer at all.

## Goal
A pluggable importer framework with a first concrete backend for OpenSmoke that
(a) translates the syntax, (b) **maps the heterogeneous modeling assumptions
explicitly** onto Cantera's Interface/bulk model (or a documented approximation),
and (c) refuses silently-wrong conversions — emitting a modeling-assumption report
the user must acknowledge.

## Design

New package `src/rmip/io/importers/`:
- `base.py` — `class MechanismImporter` ABC: `sniff(path) -> bool`,
  `to_cantera_dict(path) -> (dict, ImportReport)`. `ImportReport` is a
  `CheckReport` carrying the assumption-mapping decisions as `info`/`warning`
  findings (e.g. "OpenSmoke `LIQUID CH2` mapped to bulk phase `liquid` with
  unit activity — verify").
- `opensmoke.py` — parser for OpenSmoke kinetics/thermo/transport; maps:
  - `LIQUID`/`MATERIAL` species → a Cantera bulk/condensed phase (ties into W5's
    finite-solid/bulk handling).
  - heterogeneous reactions → `ct.Interface` reactions with an explicit site model,
    or a flagged approximation when the transport assumption can't be preserved.
  - unit conventions → Cantera `units:` block.
- `registry.py` — `import_mechanism(path)` dispatches by `sniff`; the CLI/GUI use
  this so new formats drop in without touching callers.

Where a construct **cannot** be faithfully represented (the honest P5 outcome), the
importer emits an ERROR finding naming the exact modeling gap and points at the W5
surface docs — never a silent lossy conversion.

## CLI / GUI
- `rmip import <mech> [--format auto|opensmoke] --out fixed.yaml [--json]`.
- Add an "Import (foreign format)" option to the Mechanism Converter GUI.

## Tests (`src/rmip/tests/test_importers.py`)
- Small hand-built OpenSmoke fixtures: a gas-only subset (should convert cleanly)
  and a `LIQUID`/`MATERIAL` subset (should convert *with* explicit assumption
  findings, or fail with a specific modeling-gap message).
- `sniff` correctly routes OpenSmoke vs CHEMKIN vs YAML.

## Acceptance
A gas-phase OpenSmoke mechanism round-trips to a loadable YAML; a heterogeneous one
produces an explicit, acknowledgeable modeling-assumption report rather than a
silent or crashing conversion.

## Note
Scope OpenSmoke first (a real fixture is in the source thread `chlJWiEaMHQ`). Other
formats (Chemkin-surface variants) reuse the same ABC; do not build them
speculatively.

---

## ✅ DONE — shipped 2026-07-19

- **Package:** `src/rmip/io/importers/` — `base.py` (`MechanismImporter` ABC +
  shared `convert_chemkin_to_yaml` = W2 preflight → ck2yaml → load-verify),
  `opensmoke.py` (`OpenSmokeImporter`), `registry.py` (`detect_format` /
  `import_mechanism` dispatch: cantera-yaml / opensmoke / chemkin / unknown).
- **The honest-P5 contract, implemented:** condensed content (MATERIAL headers,
  LIQUID/SOLID-block species, reactions referencing them) is analysed and the
  import is **refused** with an ERROR finding naming every unrepresentable
  construct — unless `--gas-only` explicitly acknowledges the approximation, in
  which case the content is stripped, **every dropped species/reaction is a
  WARNING finding** (dropped reactions stay in the file as comments, auditable),
  and the gas subset is converted + load-verified. Never a silent lossy
  conversion.
- **CLI:** `rmip import <mech> [--format auto|opensmoke|chemkin --out --thermo
  --transport --gas-only --json]`.
- **Converter GUI:** new "OpenSmoke: gas-only import" checkbox — sniffs, strips,
  logs each drop, then continues the normal pipeline.
- **Fixture:** `tests/fixtures/chemkin/opensmoke_pe.inp` via
  `_make_opensmoke_fixture.py` — valid H2/O2 gas subset (NASA-7 cards generated
  from Cantera's h2o2.yaml by a column-exact card formatter) + `MATERIAL PE`,
  `LIQUID PE END`, and a `PE=>H2+H2` pyrolysis reaction.
- **Tests:** `src/rmip/tests/test_importers.py` — 8 tests, all green. Verified:
  sniff routing (opensmoke vs plain-CHEMKIN Li_2015 vs YAML); refusal contract;
  gas-only import → 7-species YAML loads, PE absent, drop reported with its
  equation; plain-CHEMKIN path (real Li_2015 converts); CLI exit codes.

Closes **P5** (as the honest detect/acknowledge/report outcome the plan
specified). Full bulk-phase representation remains W5's job.
