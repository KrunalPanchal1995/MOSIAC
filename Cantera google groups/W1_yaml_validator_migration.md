# W1 — Cantera YAML validator & version-migration linter

**Closes:** P1 (LLM stale keyword `stoichiometric`→`fixed-stoichiometry`), P29
(CTI→YAML rename traps); strengthens P18 (YAML preflight) and feeds P33 hooks.
**Effort:** S · **Risk:** Low · **Depends on:** `mechanism_check.py`.

## Problem
AI- and human-authored Cantera YAML routinely uses deprecated CTI-era keywords
and renamed fields. Cantera only fails at *runtime* with an opaque `CanteraError`,
and "ask the model to check it" doesn't catch it. There is no schema/deprecation
linter and no migration pass in the codebase — `mechanism_check` currently just
surfaces the load error verbatim.

## Goal
A validator that checks a YAML mechanism against the **current Cantera schema**,
names each deprecated/renamed construct with a specific message and a one-click
migration, independent of who wrote the file — and does it **without needing the
file to load** (so it can explain *why* it won't load).

## Design

New module `src/rmip/analysis/yaml_validator.py`:

- `KNOWN_RENAMES: dict` — curated map of deprecated → current constructs, keyed by
  location (phase `thermo:` value, reaction `type:` value, field names). Seed from
  the Cantera CTI→YAML migration guide. Examples:
  - phase thermo `stoichiometric` → `fixed-stoichiometry`
  - `ideal-gas` legacy spellings, `Motz-Wise`, `Elementary`/`elementary` casing,
    `falloff`/`chemically-activated` field renames, `efficiencies` unit forms,
    `activation-energy` unit keys, `element`/`elements` casing.
  Structured as `{context, deprecated, current, since_version, note}`.
- `class YamlValidator` — parses the YAML **as text/dict** (`yaml.safe_load`, like
  `mechanism_check._try_parse_yaml`), walks phases/species/reactions, and emits
  `Finding`s (reuse `mechanism_check.Finding`/`FixOption`) for:
  - deprecated keyword present → `FixOption(kind="auto", id="migrate_keyword")`
  - unknown `type:`/`model:` not in the current Cantera enum → warning
  - missing required schema fields (phase `kinetics`, `transport` when species
    carry transport, `state` block) → warning
  - `units:` block sanity (e.g. `activation-energy` present, recognised)
- `migrate(data) -> (data, changes)` — applies the rename map to the dict; the
  fixer writes it back (extend `mechanism_fixer.MechanismFixer` with a
  `migrate_keyword` handler, or add a thin `apply_migrations`).

Schema source of truth: probe the installed Cantera at runtime for the valid enum
of phase/thermo/reaction types (`cantera` exposes these), so the linter tracks the
*installed* version rather than a hardcoded list — this is what makes it a real
"migrate to the current version" tool (P29).

## CLI / GUI
- `rmip migrate <mech.yaml> [--in-place|--out fixed.yaml] [--dry-run]` — reports
  and applies migrations.
- Fold the deprecation lint into the existing `rmip check` battery as a new check
  id `schema_deprecation` (runs on the raw YAML even when load fails), so the
  shipped GUI shows it with its migrate `FixOption` automatically.

## Tests (`src/rmip/tests/test_yaml_validator.py`)
- Fixture: a copy of `h2o2.yaml` with `thermo: ideal-gas` phase edited to a
  deprecated spelling + a reaction `type:` renamed → validator flags both, migrate
  produces a file that now loads in `ct.Solution`.
- Round-trip: migrating an already-current file is a no-op.
- The `k6vrgNep1Wg`-style case: `stoichiometric` phase → flagged + fixed.

## Acceptance
`rmip check bad_ai_mech.yaml` names the deprecated keyword and offers migration;
`rmip migrate` yields a loadable file; migrating GRI-3.0 changes nothing.

---

## ✅ DONE — shipped 2026-07-19

- **Module:** `src/rmip/analysis/yaml_validator.py` — `YamlValidator` +
  `KNOWN_RENAMES` (reaction-type & phase-thermo renames verified against Cantera
  3.0.1) + `RenameRule` + `migrate()`.
- **Engine integration:** new `schema_deprecation` check in
  `mechanism_check.py` (`ALL_CHECKS`, `check_schema_deprecation`), runs on the raw
  YAML **pre-load** so a file that won't load because of a stale keyword is still
  diagnosed and fixable.
- **Fixer:** `mechanism_fixer.MechanismFixer._fix_migrate_keyword` (auto fix).
- **CLI:** `rmip migrate <mech.yaml> [--out|--in-place|--dry-run|--json]`
  (`cli.py:_cmd_migrate`), with a post-migration load re-check.
- **GUI:** surfaces automatically — the shipped `mechanism_check_gui` is
  data-driven off the `check` battery + auto `FixOption`s, so the migrate action
  appears pre-selected with no GUI code change.
- **Fixture:** `broken_deprecated.yaml` via
  `tests/fixtures/_make_broken_mech.py:build_deprecated_dict` (thermo `ideal_gas`
  + reaction `PLOG` + `three_body`).
- **Tests:** `src/rmip/tests/test_yaml_validator.py` — 10 tests, all green.
  Verified: detection, `migrate()` → loadable, fixer → loadable, no false
  positives on GRI-3.0, unrecognised-type is INFO not error, CLI end-to-end.

Closes **P1** and **P29**.
