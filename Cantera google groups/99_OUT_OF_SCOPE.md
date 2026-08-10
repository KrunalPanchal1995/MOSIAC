# Out of scope — with rationale and the detector/wrapper angle where one exists

These problems are **not** implementable as features in this codebase because they
are bugs inside another project's internals, physically impossible, or environment
issues we don't own. Listed for completeness so nothing is silently dropped. Where
we can still offer a *detector* or *wrapper* (rather than a fix), that angle is
called out and routed to a workstream.

| P# | Problem | Why out of scope | What we CAN do |
|----|---------|------------------|----------------|
| P11 | Chemkin `.asc` link files can't be reverse-converted | Undocumented internal binary; no path to source without the original `.inp`/`.dat` | **Detect** an `.asc` input and advise (the original source is required) — a one-liner in W2 preflight |
| P14 | Encrypted CHEMKIN mechanisms | Cryptographically unreadable without the vendor key — even the vendor's support can't inspect them | **Detect** encryption and say so plainly — W2 preflight |
| P16 | RMG prunes by species-count, not memory | Fix belongs in RMG's core generation loop | **Wrap** with a memory-budget supervisor (W7b) that stops before OOM |
| P22 | Multidentate adsorbate Keq wrong in RMG | RMG-internal thermodynamics bug | **Detect** via the surface cross-solver validator (W5b) and thermo cross-check (W4) |
| P23 | Bidentate sticking coefficients wrong | Already fixed upstream in RMG | Nothing to build (regression-guard only if we touch surface thermo) |
| P24 | RMG can't generate surface mechanisms at all | RMG structural limitation (gas + partial liquid only) | Document the limitation in W3/W5; no workaround exists |
| P19 | RMG doesn't represent charged/ionic species | RMG database/representation gap | **Surface** the symptom: flag ionic species + charge balance (already in `mechanism_check`; cross-linked in W4) |
| P31 | Undocumented 8-carbon truncation | Historical RMG bug, long fixed | Nothing |
| P32 | ANSYS Chemkin preprocessor errors too generic | ANSYS commercial product we don't control | Our linters (W1/W2/W8) embody the fix — specific, line-numbered diagnostics — for the Cantera/CHEMKIN path |
| P34 | Debug-vs-Release input-file-not-found | Cantera C++ build-configuration bug | Nothing (upstream build issue) |
| P37 | Platform install failures (Windows MATLAB, Linux `.exe`, Ubuntu pkg) | Environment/packaging, not mechanism tooling | `rmip doctor` (W9) reports a broken environment clearly, but can't fix platform packaging |

## Principle
Where the underlying defect lives in RMG/Cantera/ANSYS, we build **detectors and
wrappers**, never forks of their internals — consistent with the env-isolation rule.
Several "OUT" rows therefore still contribute a small, honest capability (detect +
advise) inside an existing workstream, rather than a feature that pretends to fix
something we cannot.
