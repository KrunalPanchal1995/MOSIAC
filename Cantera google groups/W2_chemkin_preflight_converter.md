# W2 — CHEMKIN preflight linter & robust converter

**Closes:** P2 (cryptic `ck2yaml` tracebacks), P3 (`NONCON` no semantics), P4
(manual surface-site balancing — shared with W5), P13 (`bulk` keyword), P18
(CHEMKIN structural preflight), P35 (case-mismatch `AR`/`Ar` across sections).
**Effort:** M · **Risk:** Low-Med · **Depends on:** existing `mechanism_converter_gui`.

## Problem
CHEMKIN→YAML conversion is the single biggest recurring pain. `ck2yaml` fails with
Python-level tracebacks ("cannot access local variable 'reversible'", "failed to
find reactant/product delimiter") on constructs that are common in third-party
mechanisms — odd whitespace, float-formatted elemental compositions, `NONCON`,
`bulk`, and case-inconsistent species names — and there is no self-service
"is my file even structured right?" preflight.

## Goal
A **line-numbered CHEMKIN structural linter** that runs *before* `ck2yaml`, gives
specific, actionable diagnostics (not tracebacks), auto-normalises the safe cases,
and explicitly flags the known-ambiguous constructs rather than dying on them.

## Design

New module `src/rmip/io/chemkin_preflight.py` — pure text/lexer level (does **not**
depend on a successful parse), emitting `Finding`s with `line`/`column`:

- **Block structure** — presence/closure of `ELEMENTS/ELEM`, `SPECIES/SPEC`,
  `THERMO`, `REACTIONS/REAC`, `END`; detect a `REACTIONS` block with no `END`.
- **Species name consistency (P35)** — collect every species token across the
  SPECIES block, thermo records, and reaction equations; flag case-variants of the
  same name (`AR` vs `Ar`) and tokens used in reactions but never declared. This is
  the "silent failure" class from Cluster 8 and is cheap + high-value.
- **Whitespace / delimiter hazards (P2)** — tabs inside/near numbers, missing
  reactant/product delimiter (`=`/`<=>`/`=>`), stray leading `+` on thermo coeffs,
  missing `e`/`E` in exponents (already fixed in the converter — reuse
  `mechanism_converter_gui.fix_fortran_exponents`), CRLF.
- **Float-formatted elemental composition (P2)** — element counts written as
  `C 2.0` rather than integer; auto-normalise to int where unambiguous, warn where
  not.
- **Ambiguous surface constructs (P3, P13)** — detect `NONCON` and `bulk`/`BULK`;
  emit an explicit "Cantera has no defined semantics for `NONCON`; this reaction
  will not convert — see W5" finding rather than letting `ck2yaml` throw.
- **Ea unit declaration** — REACTIONS line unit keywords (`CAL/MOLE`, `KELVINS`,
  `JOULES/MOLE`, …); flag missing/nonstandard so the J/kmol trap (W-shared with the
  shipped `unit_sanity`) is caught at source.

`class ChemkinPreflight` returns a `CheckReport`. Auto-normalisation writes a
cleaned `.inp` to a temp/next-to-source path (opt-in), then hands off to `ck2yaml`.

## Converter hardening
Extend `mechanism_converter_gui` / add `src/rmip/io/chemkin_convert.py`:
- Run `ChemkinPreflight` first; block conversion on ERRORs, warn-and-continue on
  WARNINGs (with `--permissive`).
- On `ck2yaml` failure, map its exception to the nearest preflight finding so the
  user sees a line number, not a traceback.
- Surface-site balancing helper (P4) — shared with W5: inject an empty-site
  placeholder species and balance surface-reaction stoichiometry (opt-in).

## CLI / GUI
- `rmip preflight <mech.inp> [--thermo …] [--transport …] [--fix] [--json]` —
  standalone CHEMKIN preflight.
- Wire the preflight report + auto-normalise into the **Mechanism Converter GUI**
  as a "Preflight" pane shown before "Convert".

## Tests (`src/rmip/tests/test_chemkin_preflight.py`)
- Fixtures under `fixtures/chemkin/`: `case_mismatch.inp` (AR/Ar), `float_comp.inp`,
  `noncon.inp`, `bulk.inp`, `no_end.inp`, `tab_delim.inp`.
- Each: preflight flags the specific line; `--fix` normalises the safe ones and the
  cleaned file converts via `ck2yaml`; `noncon`/`bulk` are flagged not-auto-fixed.
- Real-mechanism smoke: every `MECHANISM/*/*.inp` passes preflight or fails with a
  line-numbered reason (no traceback).

## Acceptance
A malformed third-party surface mech yields line-numbered findings instead of a
Python traceback; `AR`/`Ar` inconsistency is caught before import; `NONCON`/`bulk`
are named explicitly.

---

## ✅ DONE (core) — shipped 2026-07-19

- **Module:** `src/rmip/io/chemkin_preflight.py` — `ChemkinPreflight` (pure
  text-level lexer, no parse needed) emitting line-numbered `Finding`s reusing the
  shipped `CheckReport` model. Checks: block structure + `END` closure
  (missing-end), species case-consistency (P35, ERROR) + undeclared participants
  (WARNING), CRLF/tab/Fortran-exponent hazards (P2), NONCON/MATERIAL/BULK/SITE
  (P3/P13), REACTIONS Ea-unit declaration. `clean_text`/`write_clean` produce a
  cleaned `.inp`; species-case fix is **opt-in and scoped to reaction lines only**
  (cannot corrupt thermo/comments — verified against real Li_2015: 0 content diffs).
- **CLI:** `rmip preflight <mech.inp> [--thermo --transport --fix --fix-case
  --fixed-out --json]` (`cli.py:_cmd_preflight`).
- **Converter GUI:** `mechanism_converter_gui.convert()` now runs the preflight
  first, logs the line-numbered findings, and **blocks on structural errors unless
  `--permissive`**.
- **Fixtures:** `src/rmip/tests/fixtures/chemkin/` via `_make_chemkin_fixtures.py`
  (case_mismatch / fortran_exp / noncon / no_end / tab_delim).
- **Tests:** `src/rmip/tests/test_chemkin_preflight.py` — 15 tests, all green.
  Verified: every fixture flagged at the right line; **no false positives** on real
  Li_2015 / GRI-3.0; `--fix` output **converts via ck2yaml and loads**; case-fix
  reaction-scoped; converter gate blocks on errors.

Closes **P2, P18, P35**; flags (detect-not-fix) **P3, P13**.

## Deferred to W5 (surface workstream)
- **P4** surface-site balancing (the actual empty-site injection + stoichiometry
  balancing) — preflight *detects* the surface constructs and points at W5; the
  balancing helper itself ships with the finite-solid/interface work.
