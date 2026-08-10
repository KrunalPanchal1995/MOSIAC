# GUI Separation + Broader Improvement Plan

**Generated: 2026-07-12 14:22:30.** Written via Claude's Plan Mode (`/model opusplan`, per KP's
explicit invocation in `prompt.txt`) — this is the planning deliverable KP asked for ("Dump these
plans, progress etc into appropriate files with date as well as time stamp"), not implementation.

**Update, same day: all 7 apps in Part 1 are now built** (KP asked to execute the plan
phase-wise immediately after it was approved). Phases 1-6 complete: `brute_force_sa_gui.py`,
`forward_uq_gui.py`, `nominal_sim_gui.py`, `mso_compare_gui.py`, `rmip_suite_gui.py`,
`mean_value_fusion_gui.py`, `uncertainty_generator_gui.py`, plus the shared `src/gui_common/`
package and `launcher_gui.py`. See `RESUME.md`'s §1 items 9-10 and §2f for the full build log,
verification notes, and 4 real bugs found and fixed along the way (a `ChemkinWriter` double-`END`
bug, and two missing-attribute bugs in `generate_uncertainty_xml()`). Part 1 below is left as
originally written (the approved plan) — Part 2's broader-improvement findings are still current
and mostly still open, see `RESUME.md` for which have since been addressed.

**Context.** KP's original ask (`prompt.txt`, line 5): the single GUI app `generate_target_opt.py`
(6080 lines, one `App` class spanning 12 tabs) has become cluttered trying to fit every workflow
into one window. KP wants each task type split into its own dedicated, higher-quality GUI, plus a
broader look at what else in the combustion-kinetics development/comparison/validation pipeline
could be improved. This plan covers both halves and proposes a phased build order for the GUI
split, to be executed as separate, explicitly-scoped follow-up work.

This plan was built from two Explore passes over the live codebase (not assumed from memory) plus
four clarifying answers from KP (recorded inline below where they resolve an ambiguity).

---

## Part 1 — GUI separation architecture

### 1.1 What's actually splitting apart

`generate_target_opt.py`'s 12 tabs are NOT cleanly file-decoupled today — they share one giant
`self.cfg` dict plus several other cross-tab attributes (`self._mech_rows`, `self._fuel_registry`,
`self._target_df`, shared SA condition StringVars) funneled through a ~170-line `_collect()`
God-method (line 4257) that alone knows about every tab's fields. But the actual **computation**
is already mostly GUI-independent — most tabs are thin forms wrapping standalone CLI scripts or
importable library modules (`forward_uq.py`, `sens_3_params.py`, `rmip_cli.py`, `rmip.reduction.*`,
`rmip.analysis.fusion`). This is the load-bearing fact making the split tractable: **each new app is
"a thin Tk form + subprocess/import call into an already-existing, already-working CLI or library,"
not new business logic**, in every case except the deliberately-new symmetric-bound simplification
in Part 1.2 item G.

### 1.2 The 7 target apps (resolved from KP's 10 named items + 4 clarifying answers)

KP confirmed: RMIP is the umbrella app for Global Sens Analysis + Active Param Selection (folded in
as tabs, not separate apps) — collapsing 10 named items to 7 apps. KP also confirmed which backend
each ambiguous item wraps (Nominal Sim → `mso_compare`; Active Param Selection → the just-discovered
`src/ActiveParameterScreen.py` framework; Mean Value Generator → `ParameterEstimator`/
`FusionEngine`, not the unimplemented `UQFusion`).

| # | App | Wraps (backend, already exists) | Status | GUI today |
|---|-----|------|--------|-----------|
| A | **Forward UQ** | `forward_uq.py` CLI + `src/forward_uq/` (`MCPropagator`, `AnalyticalSobolPRS`) | Mature, 19/19 tests | Tab exists (`_tab_forwarduq`) |
| B | **Brute-Force Sensitivity Analysis** | `src/Sensitivity_Analysis/sens_3_params.py` | Mature | Tab exists (`_tab_reaction_screening`, partial) |
| C | **Nominal Simulation (parallel)** | `src/mso_compare/run_nominal_sim.py` (`template_nominal_only.yaml`) | Mature | None |
| D | **MSO Compare** | `src/mso_compare/` full pipeline (`run_mso_pipeline.py`: simulate→merge→error-metrics→plots) | Mature, has its own README | None |
| E | **RMIP Suite** (umbrella) | `rmip_cli.py` + `src/rmip/` — graph viz/comparison, **Mechanism Reduction**, **Global Sens Analysis** (`gsa-run`, 2026-07-12 session), **Active Parameter Selection** (`src/ActiveParameterScreen.py`) as its 4 internal tabs | Mature (390+ tests) | Partial — today's "RMIP Analysis" tab covers viz/comparison/reduction only; GSA and Active-Param-Selection have zero GUI |
| F | **Mean Value / Mechanism Fusion Generator** | `rmip.analysis.parameter_estimator.ParameterEstimator` + `rmip.analysis.fusion.FusionEngine` / `rmip.stubs.FusionEngine` (2026-07-12 session) | Mature, tested | Partial — buried inside today's RMIP Analysis tab as a "fusion" sub-section; **moves out to its own app** (see 1.3 decision) |
| G | **Uncertainty Generator** (temp-dependent + temp-independent) | `src/MUQ-SAC/Uncertainty.py` (treat as canonical over the diverged `Sensitivity_Analysis/` copy) | Mature extraction/bound machinery; KP's specific ask (collapse T-dependent deviations to **one global max-abs symmetric bound**) is genuinely new code layered on top, not already implemented | Tab exists (`_tab_xml_builder`) but only builds input rows, never runs the bound computation |

### 1.3 Scope decision: Mechanism Fusion moves out of RMIP Suite into App F

Today's single "RMIP Analysis" tab bundles graph viz + comparison + **fusion** + reduction + SA +
unified-tree + export. Since KP separately named "Mean value generator" (→ `ParameterEstimator`/
`FusionEngine`, i.e. mechanism fusion) as its own top-level item, App F takes over the fusion
workflow entirely; RMIP Suite (App E) keeps graph viz/3D, kinetics/thermo comparison, Mechanism
Reduction, Global Sens Analysis, and Active Parameter Selection. This avoids the same feature living
in two different windows.

### 1.4 Shared infrastructure — extract once, reuse across all 7 apps

From the current file, these are already self-contained (don't reach into `App` internals) and
should move to a new `src/gui_common/` package rather than be copy-pasted 7 times:

- **`theme.py`** ← `_apply_theme` (line 1375) + `PALETTE`/`FONTS` dicts. One dark theme exists today,
  no light mode — keep as-is, just centralize so all 7 apps look consistent and theme fixes land
  once.
- **`pty_terminal.py`** ← `PtyTerminal` (line 328). Today used in exactly **one** place
  (Reaction Screening's SA button) while Forward UQ instead shells out to an external OS terminal
  window and Compile does a blocking `subprocess.run`. **Standardize on `PtyTerminal` as the one
  long-job launch mechanism across all 7 new apps** — this was already a recorded recommendation
  (`PLAN.md` #5 / `ZERORK_GSA_PLAN.md` Phase 5) and the split is a natural point to actually do it,
  fixing the "GUI freezes during Compile" bug as a side effect.
- **`autosave.py`** ← `AutoSaveManager` (line 441). Reusable as-is; each app gets its own checkpoint
  file (see below).
- **`fuel_data.py`** ← `FuelNormalizer` (line 56). **Flagged overlap to resolve during extraction,
  not defer**: its embedded MW table duplicates data `chem_data.py`'s `compute_mw` already provides
  — de-duplicate onto one source of truth while extracting, don't just relocate the duplication.
- **`variable_map.py`** ← `VariableNameMapper` (line 246). Low-coupling reference data, trivial move.
- **`target_types.py`** ← the `TARGET_TYPES`/`TARGET_TYPE_FIELDS` dicts (line 693) — **this is KP's
  existing target-type vocabulary** (`Tig`/`Fls`/`Flf`/`Flf_a`/`JSR`/`PFR`/`RCM`/`Flw`) and the only
  place it's currently defined. Every new app that touches `.target`/`.add` files must import this,
  never re-invent target-type strings.

**Dropped, not extracted**: `TabLockingManager` (line 160) — its guided-wizard-across-12-tabs
concept doesn't apply once each task is its own standalone window. If an individual app (e.g. RMIP
Suite, which keeps its own internal 4-tab structure) wants a lighter internal step-sequencing
affordance, that's a per-app decision to make at implementation time, not a shared component to
force everywhere.

**Per-app settings**: today's single `.rmip_gui_settings.json` (line 312, lives next to the script,
stores one key) becomes `.gui_settings/{app_name}.json` per app — avoids collision once multiple
apps import the same helper.

### 1.5 Each app's data contract

Every app is a standalone script with its own `argparse` entry point (`--target-opt PATH`,
`--db PATH`, etc., matching how `forward_uq.py`/`rmip_cli.py` already work) — not a tab requiring a
parent `App` object. On startup each app loads only the slice of `target.opt`/`.target`/`.add`/DB
state it actually needs and re-derives the rest by reading the relevant files directly (mechanism
list from `target.opt`'s `RMIP.mechanisms`, target rows from `.target`, addendum from `.add`) —
this is exactly the file-based interchange the non-GUI toolchain already uses, it's just never been
exercised as the *internal* hand-off mechanism before. A small `_collect()`-equivalent per app
(scoped to only that app's own config section) replaces the current one God-method.

### 1.6 Optional: a launcher

Splitting into 7 windows means KP loses the single "one script to run" entry point. Propose a
lightweight `launcher.py` — a small Tk window listing all 7 apps as buttons, each spawning the
corresponding script as a subprocess. Not mandatory for Phase 1; cheap to add once ≥2 apps exist.

### 1.7 Phased build order (recommended, adjustable)

Building all 7 apps + the shared package in one shot is multi-week work. Recommend:

1. **Phase 1 — `gui_common/` package + one pilot app.** Build the shared modules (1.4) first, then
   port **App B (Brute-Force SA)** as the pilot — it has the cleanest existing CLI contract
   (`sens_3_params.py <target.opt>`) and already-embedded `PtyTerminal` usage to lift-and-shift,
   making it the lowest-risk validation of the whole pattern before committing to the rest.
2. **Phase 2 — App A (Forward UQ)** and **App C (Nominal Simulation)** — both already have clean,
   fully-decoupled CLI backends (`forward_uq.py`, `mso_compare/run_nominal_sim.py`); no new backend
   work needed, same pattern as Phase 1.
3. **Phase 3 — App D (MSO Compare)** and **App F (Mean Value/Fusion Generator)** — slightly more
   involved UIs (multi-run comparison, and the new `FusionEngine`/`validate_element_balance`
   surfaced for the first time this session).
4. **Phase 4 — App E (RMIP Suite)** — the biggest lift (4 internal tabs: viz/comparison, reduction,
   the brand-new GSA (`gsa-run`) which has *zero* GUI today, and Active Parameter Selection which
   also has zero GUI today) — do this once the pattern is proven on simpler apps.
5. **Phase 5 — App G (Uncertainty Generator)** — needs the new symmetric-max-bound logic designed
   and confirmed with KP before UI work starts (see Part 2 item 8).
6. **Phase 6 — optional launcher** (1.6).

Each phase is independently shippable and reviewable — don't block later phases on earlier ones
being "perfect."

---

## Part 2 — Broader improvement recommendations

Grounded in gaps actually found during the 2026-07-12 session (not speculative), ranked by how much
they block real workflows:

1. **Glossary-matching gap blocks `GraphComparator`/`FusionEngine`/`unify-*` on every real mechanism
   in `outputs/project.db` today.** Every species in every mechanism (chemkin- and cantera_yaml-
   parsed alike) has `inchi_key`/`canonical_key` NULL (`glossary_matched=0` everywhere) — the
   name→SMILES→InChI resolution in `core/parser.py` was never exercised with a glossary covering
   common species (H2/O2/H2O/etc.) at parse time. Until this is fixed, `compare-graph`/`fuse`/
   `unify-plan`/`unify-build`/the new `FusionEngine`/App F above all produce empty results on real
   data — this is the single highest-leverage fix in this list. Needs: a glossary file covering at
   least the common small-molecule combustion species, then a re-parse of mechanisms 8-11 with
   `--glossary`.
2. **`ChemkinWriter` double-`END` bug (found + fixed 2026-07-12).** `write()` was unconditionally
   appending a second `"END"` after `_write_reactions()`'s own terminator — every CHEMKIN file this
   writer ever produced had a duplicate terminator. Cantera's `ck2yaml` rejects it outright; Zero-RK
   silently tolerated the extra content, so it was never caught until `FusionEngine.fuse(write_cantera=
   True)` piped writer output through `ck2yaml` for the first time. Fixed. Flags a broader risk:
   writer output has apparently never been round-tripped through *both* real consumers in one test
   before — recommend a standing regression test piping every mechanism in the DB through both.
3. **Two stale duplicated-and-diverged file pairs**: `MUQ-SAC/ResponseSurface.py` vs.
   `Sensitivity_Analysis/ResponseSurface.py` (already flagged in `ZERORK_GSA_PLAN.md` — treat
   MUQ-SAC's as canonical), and `MUQ-SAC/Uncertainty.py` vs. `Sensitivity_Analysis/Uncertainty.py`
   (same relationship, confirmed this session, not previously documented).
   **Acknowledged, not tracked as an open item — user explicitly decided not to act on this
   duplication (2026-07-20).** Kept here for factual reference only; no cleanup planned.
4. **`sens.py` (legacy single-A-factor OAT) vs. `sens_3_params.py`** — already documented as
   superseded; confirm nothing still imports `sens.py` and delete it, rather than carrying dead code
   into the new Brute-Force SA app (Phase 1).
5. **A `CLAUDE.md` is referenced** (by `stubs.py`, `PLAN.md`, `RESUME.md`, as "§11 MUQ-SAC Bridge")
   **but does not exist anywhere in this repo** — only a same-named, likely-unrelated file exists in
   a sibling directory (`/data/OPEN_CODE/CLAUDE.md`). This is a stale cross-repo reference from
   before this repo was split out. Either author the missing section for real, or scrub the dead
   references (`UQFusion`'s docstring depends on it) so the next session doesn't chase a ghost file.
6. **Remaining `stubs.py` modules** (`PathwayCompleter`/M5 needs RMG-Py, `UQFusion`/M13 blocked on
   item 5 above, `AIRecommender`/M10, `ChangeLog`/M11, `ReportEngine`/M12) are still unimplemented.
   None of these were on the path to the GUI plan and none were touched this session — recommend
   triaging which (if any) actually block a real near-term workflow vs. which are speculative
   Phase-6 scope, before investing further implementation time.
7. **Test-coverage asymmetry**: `src/rmip/` has 390+ automated tests; `src/MUQ-SAC/`,
   `src/Sensitivity_Analysis/`, `src/mso_compare/`, and `src/ActiveParameterScreen.py`+`modules/`
   (all described as "mature/production" in this session's research) have little to no visible
   automated test coverage by comparison. Worth flagging as a due-diligence gap, especially before
   building new GUIs on top of them in Part 1 — a thin GUI over an untested backend just makes the
   backend's bugs more visible, not more correct.
8. **Open item needing KP's confirmation before Phase 5 (App G) starts**: KP's literal ask for the
   Uncertainty Generator — "take max unsrt values from the mean values on either side, use as
   symmetric bounds for A-factor optimization" — is a real simplification of `Uncertainty.py`'s
   existing full per-anchor-temperature Class B/C curve-fit machinery (collapsing all T-dependent
   deviations to one global max-abs symmetric scalar). The general extraction/bounding machinery
   already exists and is mature; this specific collapse is new code, not a lift-and-shift. Confirm
   the exact intended formula (which max — max over |P_max−P|/|P−P_min| across all anchor
   temperatures? per-reaction or per-mechanism?) before implementing App G's backend call.

---

## Verification (for the actual build phases, once started)

- Each new app: run it standalone (`python <app>.py --target-opt <real .opt file> ...`), confirm it
  produces the same output the existing tab currently produces for the same input, via a live run
  against a real fixture (mirroring how JSR/GSA/FusionEngine work was verified this session — real
  binary/CLI runs, not just unit tests).
- Shared `gui_common/` modules: unit-testable in isolation (they already don't depend on `App`).
- Regression check after each phase: the corresponding tab/feature still works in
  `generate_target_opt.py` until it's formally deprecated from the monolith (don't rip out the old
  tab until its replacement app is confirmed working, to avoid a KP-facing capability gap mid-split).
