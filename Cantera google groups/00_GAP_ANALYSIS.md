# Gap Analysis — community problem inventory vs. the current codebase

**Source:** `mechanism_building_problems.md` (Cantera Users' Group + ANSYS/Chemkin
forum + RMG-Py Discussions/Issues + rmg-users list), ~39 numbered problems (P1–P39).
**Baseline:** the RMIP suite as of 2026-07-19, including the just-shipped
mechanism health-check engine (`src/rmip/analysis/mechanism_check.py` +
`mechanism_fixer.py` + `check` CLI + `mechanism_check_gui.py`).

Each problem is classified:

- **DONE** — the codebase already addresses it (evidence cited).
- **PARTIAL** — partially covered; a concrete extension closes it.
- **GAP** — not addressed at all; this is what the plan builds.
- **OUT** — out of scope (a bug inside ANSYS/Cantera/RMG internals, physically
  impossible, or an install/environment issue we don't own). Where we can still
  offer a *detector* or *wrapper*, that angle is noted.

The **GAP** and **PARTIAL** rows are "the things the codebase is not able to
address" — the deliverable list the plan implements. Each is tagged with the
workstream (W1–W9) that owns it (see `01_ROADMAP.md`).

---

## Cluster 1 — AI-assisted / automated generation is unreliable

| P# | Problem | Status | Evidence / Extension | WS |
|----|---------|--------|----------------------|----|
| P1 | LLM-generated YAML uses stale keyword (`stoichiometric` vs `fixed-stoichiometry`); "check" didn't catch it | **PARTIAL** | `mechanism_check` surfaces the raw `CanteraError` on load, but does **not** recognise it as a deprecated CTI keyword nor auto-migrate. Needs a schema/deprecation linter. | **W1** |
| P29 | CTI→YAML keyword renames are a recurring silent trap | **GAP** | No rename map, no migration pass anywhere. | **W1** |

## Cluster 2 — CHEMKIN ↔ Cantera YAML conversion (biggest recurring pain)

| P# | Problem | Status | Evidence / Extension | WS |
|----|---------|--------|----------------------|----|
| P2 | `ck2yaml` chokes on real surface mechs; cryptic Python tracebacks from odd whitespace / float-formatted compositions | **PARTIAL** | We wrap `ck2yaml` (`mechanism_converter_gui`, `MechanismChecker._convert_chemkin`) and clean the error tail, but give **no line-numbered CHEMKIN diagnostics** and don't pre-normalise the malformed constructs. | **W2** |
| P3 | `NONCON` (non-site-conserving surface reaction) has no Cantera semantics | **GAP** | Not detected; must flag rather than silently fail. | **W2** |
| P4 | Surface-site balancing is manual (empty-site placeholder, hand-edited stoichiometry) | **GAP** | No surface-site balancer. | **W2/W5** |
| P5 | OpenSmoke `LIQUID`/`MATERIAL` heterogeneous model doesn't map onto Cantera's site/interface model | **GAP** | No OpenSmoke importer; needs modeling-assumption mapping, not just syntax. | **W3** |
| P11 | Chemkin `.asc` link files can't be reverse-converted (undocumented binary) | **OUT** | Confirmed dead end without original source. Document as unsupported; detect + advise. | 99 |
| P13 | `bulk` keyword unrecognised by `ck2yaml`, hand-added every time | **GAP** | Converter enhancement + preflight flag. | **W2** |
| P14 | Encrypted CHEMKIN mechanisms unfixable by anyone without the vendor key | **OUT** | Physically impossible. Detect encryption, advise. | 99 |
| P18 | No general "is my mechanism file even structured correctly" pre-flight | **PARTIAL** | `mechanism_check` covers **YAML** preflight well; a **CHEMKIN** structural preflight (before `ck2yaml`) is missing. | **W2** |

## Cluster 3 — Surface / heterogeneous / catalytic / multi-phase (richest vein)

| P# | Problem | Status | Evidence / Extension | WS |
|----|---------|--------|----------------------|----|
| P6 | Bulk (solid) phases are infinite reservoirs; bulk mass isn't an ODE state | **GAP** | No `ct.Interface`/`ReactorSurface`/bulk-mass handling anywhere in `src/rmip` (verified). Buildable as a custom finite-solid reactor. | **W5** |
| P7 | Manual finite-solid workaround injects artificial mass when clamping negatives | **GAP** | Part of the finite-solid formulation (non-negativity w/o mass injection). | **W5** |
| P8 | Surface coverage sums drift; Σθ=1 must be renormalised by hand each step | **GAP** | Coverage renormalisation in the reactor loop. | **W5** |
| P9 | Non-isothermal finite-solid reactors are numerically fragile (100× smaller dt) | **GAP** | Adaptive stepping / stiffness guard in the reactor driver. | **W5** |
| P21 | RMG's surface solver and Cantera's disagree for the same mechanism | **GAP** | No cross-solver validator. | **W5** |
| P22 | Multidentate adsorbate Keq computed wrong in RMG | **OUT** | RMG-internal correctness bug; but **detectable** via cross-solver/thermo cross-check. | 99/W5 |
| P23 | Bidentate sticking coefficients wrong (fixed upstream) | **OUT** | Historical RMG bug. | 99 |
| P24 | RMG cannot generate surface mechanisms at all | **OUT** | RMG structural limitation; note in docs. | 99 |
| P25 | Liquid-phase species unphysical when set by mole fraction | **GAP** | No liquid/multiphase composition sanity diagnostic. | **W5** |

## Cluster 4 — Sensitivity / IDT / reduction tooling

| P# | Problem | Status | Evidence / Extension | WS |
|----|---------|--------|----------------------|----|
| P20 | No built-in ignition-delay sensitivity (8-yr recurring ask) | **PARTIAL→DONE-ish** | We **already have** `CanteraSensitivityRunner.run_idt` (CVODES IDT SA, `sa-run` CLI). Needs first-class polish: **logarithmic normalisation**, brute-force + central-difference options, worked example, doc, GUI surface. | **W6** |
| P17 | No visibility into *why* a species was promoted RMG edge→core | **GAP** | `RMGInterface` diffs missing pathways but has no flux-attribution/promotion explainer. | **W7** |
| P26 | (2007, same as P17) can't inspect the RMG "model edge" | **GAP** | Edge-inspection wrapper. | **W7** |

## Cluster 5 — Thermo / kinetic data trust & correctness

| P# | Problem | Status | Evidence / Extension | WS |
|----|---------|--------|----------------------|----|
| P10 | Arkane thermochem for K-salts off vs JANAF (systematic ΔHf/ΔG error) | **GAP** | No JANAF/Burcat/ATcT cross-check (verified: no provenance module). | **W4** |
| P19 | RMG doesn't handle charged/ionic species (structural) | **OUT** (symptom detectable) | RMG-internal; but our checker can **flag charged species + non-integer charge balance** (charge check already exists in `check_element_balance`). | 99/W4 |
| P27 | Community dispute over the "correct" O3 NASA thermo dataset | **GAP** | Provenance/cross-reference tool with discrepancy magnitude. | **W4** |

## Cluster 6 — Version breakage & reproducibility

| P# | Problem | Status | Evidence / Extension | WS |
|----|---------|--------|----------------------|----|
| P15 | Identical RMG input → non-reproducible results across 3.0.0 vs 3.2.0 | **GAP** | No reproducibility diff harness. | **W7/W8** |
| P28 | Laminar flame speed shifts across Cantera 2.5→3.1→3.2 (documented algo change) | **GAP** | No version-behaviour regression harness. | **W8** |
| P29 | CTI→YAML renames a silent trap (see Cluster 1) | **GAP** | Migration linter. | **W1** |

## Cluster 7 — Performance / "it never finishes"

| P# | Problem | Status | Evidence / Extension | WS |
|----|---------|--------|----------------------|----|
| P16 | RMG prunes by species-count, not memory budget | **OUT** (wrapper possible) | RMG-internal; a memory-budget **supervisor wrapper** is buildable. | W7 |
| P30 | RMG jobs never terminate on large systems | **OUT** (wrapper possible) | RMG-internal; **generation supervisor** (timeouts, staged T/P, tolerance) is buildable around it. | **W7** |
| P12 | No practical path for polymer / large-molecule (polyethylene pyrolysis) generation | **GAP** (hard) | Requested twice across two communities. Buildable via lumped-family / template generation; genuinely a research problem — scoped as an exploratory workstream. | **W7** |
| P31 | Undocumented 8-carbon truncation (historical) | **OUT** | Fixed long ago. | 99 |

## Cluster 8 — Diagnostics / silent failures

| P# | Problem | Status | Evidence / Extension | WS |
|----|---------|--------|----------------------|----|
| P32 | ANSYS Chemkin preprocessor errors too generic | **OUT** (philosophy) | ANSYS product; our linters embody the fix (specific, line-numbered). | 99 |
| P33 | Import "succeeds" but every reaction rate silently zero | **PARTIAL** | `check_rate_sweep` sees NaN/neg but not the **all-zero-rate-with-species-consumed** class. Add a zero-rate/decoupled-species detector. | **W8** |
| P34 | Debug-vs-Release input-file-not-found (build-config path bug) | **OUT** | Cantera build issue. | 99 |
| P35 | Case-mismatch (`AR` vs `Ar`) across CHEMKIN file sections | **GAP** | No cross-section name-consistency linter. High value, cheap. | **W2/W8** |

## Cluster 9 — Onboarding / workflow friction

| P# | Problem | Status | Evidence / Extension | WS |
|----|---------|--------|----------------------|----|
| P36 | Users don't know which Cantera example covers a task | **GAP** (low) | A task→recipe router. | **W9** |
| P37 | Platform install failures (Windows MATLAB, Linux `.exe`, Ubuntu pkg) | **OUT** | Environment; document. | 99 |
| P38 | Toolchain prereqs (e.g. Gaussian before RMG) discovered by trial-and-error | **PARTIAL** | Our env-isolation discipline helps; add a **dependency preflight checker**. | **W9** |
| P39 | Duplicate library / duplicate reaction undetected in RMG **input** | **PARTIAL** | Output-side duplicate detection exists (`check_duplicates`); RMG **input**-file duplicate-library linter is missing. | **W7/W9** |

---

## Summary — the buildable gap list (what the plan implements)

| Workstream | Problems closed | One-line |
|-----------|-----------------|----------|
| **W1** YAML validator & migration linter | P1, P29 (+P18 YAML, P33 hooks) | Schema/deprecation lint + CTI→YAML auto-migrate |
| **W2** CHEMKIN preflight & robust converter | P2, P3, P4, P13, P18, P35 | Line-numbered CHEMKIN diagnostics before `ck2yaml`; flag NONCON/bulk; case-consistency |
| **W3** Foreign-format importers | P5 | OpenSmoke→YAML with modeling-assumption mapping |
| **W4** Thermo/transport provenance | P10, P27 (+P19 symptom) | Cross-check thermo vs Burcat/ATcT/JANAF; flag outliers |
| **W5** Surface / heterogeneous support | P6, P7, P8, P9, P21, P25 (+P4) | Finite bulk-solid reactor; coverage renorm; cross-solver + liquid sanity |
| **W6** IDT-sensitivity first-class | P20, P36-partial | Polish existing SA: log-norm, brute-force/central-diff, docs, GUI |
| **W7** RMG explainability & supervisor | P12, P15, P16, P17, P26, P30, P39 | Edge/core explainer, generation supervisor, reproducibility diff, input linter |
| **W8** Silent-failure & version regression | P15, P28, P33, P35 | Zero-rate/decoupled detectors; version-behaviour regression harness |
| **W9** Onboarding / preflight | P36, P38, P39-input | Dependency preflight; task→recipe router |

**Out of scope** (documented in `99_OUT_OF_SCOPE.md`, with detector/wrapper angles
where they exist): P11, P14, P22, P23, P24, P31, P32, P34, P37, and the
RMG-internal correctness bugs.
