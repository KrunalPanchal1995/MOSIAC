# Cantera / CHEMKIN / RMG community-gap implementation plan

Planning phase for turning the community problem inventory
(`mechanism_building_problems.md`) into an implementation program. This folder is
the plan; no feature code lives here.

**Scope.** Read the ~39 problems (P1–P39) reported across the Cantera Users' Group,
the ANSYS/Chemkin forum, and RMG-Py, classify each against the current RMIP suite
(including the just-shipped mechanism health-check engine), and design an
implementation plan for everything the codebase cannot yet address.

## How to read this folder

1. **`00_GAP_ANALYSIS.md`** — the core deliverable: every P# classified DONE /
   PARTIAL / GAP / OUT, with evidence, and the buildable-gap summary table.
2. **`01_ROADMAP.md`** — priority order, phasing (A–D), effort/risk, and the
   cross-cutting conventions every workstream must follow.
3. **`W1`…`W9`** — one design doc per workstream: problems closed, goal, concrete
   design (module paths, signatures, integration points, reuse), CLI/GUI surface,
   tests, acceptance criteria.
4. **`99_OUT_OF_SCOPE.md`** — problems we deliberately don't build, with rationale
   and the detector/wrapper angle where one exists.
5. **`BACKLOG.md`** — flat P#→workstream→status table (bug.md convention).

## Workstreams at a glance

| WS | Title | Closes | Phase |
|----|-------|--------|-------|
| W1 | YAML validator & migration linter | P1, P29 | A |
| W2 | CHEMKIN preflight & robust converter | P2, P3, P4, P13, P18, P35 | A |
| W3 | Foreign-format importers (OpenSmoke) | P5 | A |
| W4 | Thermo/transport provenance | P10, P27 | B |
| W5 | Surface / heterogeneous / finite-solid | P6–P9, P21, P25 | C |
| W6 | IDT-sensitivity first-class | P20 | A/B |
| W7 | RMG explainability & supervisor | P12, P15, P16, P17, P26, P30, P39 | C |
| W8 | Silent-failure & version regression | P15, P28, P33, P35 | B |
| W9 | Onboarding: doctor & recipe router | P36, P38, P39 | D |

## Guiding principles

- **Extend the shipped engine, don't fork it.** W1/W2/W8 plug new checks into the
  existing `mechanism_check` `Finding`/`FixOption`/`CheckReport` model and the
  `rmip check` battery; they don't invent parallel report formats.
- **Detectors & wrappers, never forks of others' internals.** Where a defect lives
  in RMG/Cantera/ANSYS, we detect and advise (or supervise), consistent with the
  env-isolation rule — heavy/optional backends stay in dedicated venvs bridged by
  subprocess.
- **One capability → library → CLI → GUI**, each with deliberately-broken fixtures
  and a green test, mirroring the mechanism-check reference shape.

## Recommended first step
**W1** (YAML validator & migration linter) — cheapest, highest alignment with the
"AI-generated mechanisms need a second pair of eyes" framing, and a direct extension
of the engine already in the tree.
