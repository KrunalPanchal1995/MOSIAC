# External repo diff report: `/home/krithika/mechanism-optimization-suite` vs this repo

Compiled 2026-08-04, Phase 4 of the 2026-08 backlog program. Read-only investigation
(no merge performed) resolving the "STILL OPEN, resurfaced 2026-07-22: blocked
external-repo merge request" item in `bug.md` — the blocker was a path **typo**
(`mechanism-optimization-suit`, missing the trailing `e`); the real path exists, is
readable, and this report is the requested comparison before any merge decision.

## 1. Git history

No shared git ancestry — different initial commits, no common tree hash. This repo's
`.git` was a fresh `git init` on 2026-07-11 from a filesystem snapshot (a prior
targeted reconciliation already happened once: commit `6f21092`, 2026-07-12, "Merge
src/MUQ-SAC/ outlier-retraining work from mechanism-optimization-suite"). The older
repo's last commit is 2026-06-11, but its **working tree** has uncommitted changes
dated as late as 2026-07-30 — i.e. genuinely after this repo's fork point, so it kept
evolving independently for ~3 weeks after the one prior merge.

## 2. Confirmed superseded (safe to ignore)

- All 11 root `*_gui.py` apps + `src/mso_studio/` — the older repo predates the
  GUI-separation refactor entirely, as expected.
- `src/rmip/`, `src/Sensitivity_Analysis/`, `src/MUQ-SAC/` (except one item below) —
  this repo is a strict superset; shared-file diffs are overwhelmingly insertions
  (e.g. `cli.py` +3346/-26), not a divergent rewrite.
- `config_tools/` — near-identical (2 real diffs total, both trivially superseded).
- `src/io/` (older) = `src/mso_io/` (this repo) — every shared file byte-identical;
  this repo just has 7 additional modules on top.
- `MD/` docs, `LICENSE`, `BUGS_LIST` (empty), `requirnment.txt` (typo'd), `pipelines/`
  (empty) — trivial or superseded by this repo's root-level equivalents.
- `src/MUQ-SAC/OptimizationTool_vMinusOne.py` — an April-2025 stale backup, unimported.
- `MECHANISM/` filesystem contents — essentially identical.

## 3. Worth a second look

1. **`src/MUQ-SAC/IdentifiablePRS.py` + `DOptimalResampler` (added to
   `AdaptiveResampler.py`), older repo, dated 2026-07-30** — genuinely never ported
   (postdates the one prior merge). Real, well-documented algorithmic work: a "PAAR
   Stage 3" physics-aware D-optimal adaptive resampler that reparameterizes the PRS fit
   into an identifiable subspace (fixes a near-singular covariance / condition-number
   ~1e11 problem diagnosed via SVD) and replaces the geometric resampling heuristics
   with greedy D-optimal design augmentation, band-validity-gated. The older repo's
   `run_script.py` already wires this in as `sample_mode="d_optimal"`; this repo's
   `run_script.py` has no trace of `d_optimal`/`DOptimalResampler`/`IdentifiablePRS` at
   all. ~540 + ~300 new lines, documented in `README_AdaptiveResampler.md`'s "2026-07
   update" section. **The single most substantial piece of uncaptured work found.**
2. **`DATASET/` — 14 fuel-mechanism datasets (~230 MB)** not present in this repo:
   `BUTADIENE`, `1_3_BUTADIENE_Manikanta`, `3-HEXENE`, `GRI_MECH`,
   `LLNL_REDUCED_159_n_heptane_mech`, `n-HEPTANE`, `n-Pentanol`,
   `OLD_NHEPTANE_DATA_2023_ASPACC`, `OMEn_Manikanta`, `RP3`, `SYNGAS_COMPLETE` (247 MB,
   FFCM1 mech/thermo/trans + targets), `SYNGAS_DATASET`, `T124MBZ` (trimethylbenzene,
   incl. RCM supplementary data), `Test_NhEPTANE`, `Test_syngas_data`. Real working
   sets (mechanism/thermo/transport/target files + source-literature PDFs), not code —
   never at git-merge risk, just never copied over.
3. **`test/PRS_DIAGNOSTICS/prs_diagnostics.py` + `demo_run.py`** (June 2026,
   standalone, no simulator dependency) — a bias/variance diagnostic suite for PRS fits
   (full-PRS vs p-PRS). Lower priority (predates even the first merge, standalone
   analysis tool not integrated pipeline code) but useful if p-PRS accuracy issues
   resurface.

## 4. Recommendation

The "confirmed superseded" bucket covers the overwhelming majority of the code, as
expected given this repo is strictly ahead structurally and a prior targeted
reconciliation already happened. **Exactly one piece of real, uncaptured algorithmic
work is worth merging**: the D-optimal/`IdentifiablePRS` resampling upgrade — small,
self-contained (2 files + a `run_script.py` wiring change + README), not a broad
reconciliation. The 14 unique `DATASET/` fuel directories are worth a plain filesystem
copy (no code/merge involved) if/when work resumes on non-ammonia fuel systems.
Everything else can be safely ignored. **No merge performed as part of this
investigation** — this is the requested "diff report first" deliverable; whether/when
to act on items 1-3 above is a follow-up decision.
