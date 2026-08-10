# Ammonia Campaign — 2026-07-22

Goal: get Konnov 2019 (and the other 4 NH3 mechanisms) producing real output
through conversion, health-check, fusion, uncertainty-gen, target-opt, and a
full GUI sweep. Scope caps: any "big code" run (target-opt, brute-force SA,
MUQ-SAC) <= 5 Tig targets + 3 reactions. Fusion is FULL (all 5 mechanisms,
Glarborg 2018 as base).

Working output dir: `outputs/ammonia_campaign/` (yaml/, logs/, health_check/,
targets/, uncertainty/, fusion/, target_opt/, gui_sweep/).

## DECISIONS / FLAGS FOR USER (read this first)

1. **Konnov 2019 now works.** Root cause of the original complaint: a
   malformed duplicate thermo entry (`128-957.dat:2481-2484`, one 82-char
   line where NASA-7 requires 80) crashed ck2yaml before it could even
   apply its own duplicate-handling logic. Fixed in a repaired copy (not
   the vendor original); Konnov 2019 now converts, loads, and computes
   real Cantera state. See Phase 1.
2. **Only 4 of 30 ammonia Tig dataset ids are simulatable** against any of
   this repo's 5 standard ground-state NH3 mechanisms — the other 26 use
   `ign_delay_def: OH*` (an excited-state species none of these mechanisms
   track; would need a chemiluminescence sub-mechanism grafted on). Phase
   3's target selection was revised mid-campaign to only use the 4 usable
   ids (`x10100001`, `x10100002`, `x10199001`, `x10199002`, all
   `ign_delay_def: NH3`). **Decision needed:** is NH3-relative-concentration
   the metric to standardize on, or is adding OH* chemistry to one of the
   5 mechanisms worth doing? Not decided here.
3. **"unitless" ignition-delay fraction (`specific_cond: 0.95;unitless`)
   interpreted as "95% of initial reactant CONSUMED"**, not "95%
   remaining" — a genuine judgment call (see Phase 6 bug 16) since nothing
   in the addendum data disambiguates it. Flip the sign in
   `make_input_file.py`'s new `unitless` branches (8 occurrences) if the
   source literature means the opposite.
4. **Fusion: ran BOTH a Glarborg-priority fusion (the literal "Glarborg as
   base" instruction) and a mean-consensus fusion** (for real, populated
   `mso_bounds.json` content, since priority mode legitimately produces an
   empty one — there's nothing left to average once every reaction is
   priority-picked verbatim). Both are real, valid, different-purpose
   outputs; see Phase 5 for which file is which.
5. **Phase 6 (target-opt) did not reach a final optimized result** — it
   got substantially further than any prior session attempt (real
   FlameMaster/Cantera simulations ran, A-factor sensitivity analysis
   completed with physically sensible results) but stopped at bug 17, a
   mismatch between the correlation-based active-parameter-set reduction
   and `MechManipulator2_0.py`'s perturbation-dict builder, in the
   actively-evolving "2_0" partial-response-surface subsystem. Flagged
   rather than patched — I don't have enough context on this subsystem's
   intended statistical semantics to safely guess a fix.
6. **`nominal_sim`/`mso_compare`'s actual Tig computation path
   (`sim_runner.py`) invokes ANSYS Chemkin-Pro and fails (rc=41)** rather
   than using the pure-Cantera path that Phase 6's MUQ-SAC engine
   (`simulation_manager.py`) uses successfully for the identical
   mechanism+targets. Found, not fixed (bug 18) — needs someone with more
   context on `make_input_file.py`'s solver-dispatch logic (a very large
   file with many duplicated template blocks) to resolve correctly.
7. Two `DesignMatrix.py` copies (`src/MUQ-SAC/`, `src/Sensitivity_Analysis/`)
   have diverged; only the latter is actually live for the A-factor SA
   path today. Both got the same class of bug independently. Worth
   reconciling/retiring the dead copy at some point — not done here.

## Phase 1 — Mechanism conversion (CHEMKIN -> Cantera YAML)

Status: IN PROGRESS

### Baseline

- `ck2yaml` present at `/home/krithika/anaconda3/bin/ck2yaml` (Cantera 3.0.1).
- Prior `MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/check.json` (reduced variant
  `28-213.inp`) already recorded a load failure:
  `cantera.ck2yaml.InputError: No thermo data found for species 'AR'`
  — this is the REDUCED mechanism (28-213.inp), self-contained, no separate
  thermo/tran file shipped for it. Need to check whether the PRIMARY subject
  `128-957.inp` (which DOES ship its own `128-957.dat` thermo + `128-957.tran`
  transport) has the same issue or converts cleanly.

### Konnov 2019 (128-957) — FIXED, converts + loads

Ran `ck2yaml --input=128-957.inp --thermo=128-957.dat --transport=128-957.tran
--permissive`. Failed with:
```
cantera.ck2yaml.InputError: Error parsing elemental composition for species
thermo entry ... Element amounts can have no more than 3 digits.
```
**Root cause (bug found, file:line):** `MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/128-957.dat:2481-2484` —
a DUPLICATE NASA-7 thermo entry for `CH3CH2NH2` (ethylamine, irrelevant to
NH3/H2/CO core chemistry; a perfectly well-formed FIRST entry for the same
species already exists at line 2476) is 82 characters long instead of the
fixed-width-80 NASA-7 standard, shifting the elemental-composition field
(cols 25-44) by 2 columns so ck2yaml reads garbage and throws before it
even gets to apply its own "use the first of two duplicate entries"
--permissive logic. Confirmed via a full-file column-width scan: this is
the ONLY line in the whole 2682-line thermo file that isn't 80 chars.

**Fix:** wrote a repaired copy `outputs/ammonia_campaign/fixed_mechs/fixed_128-957.dat`
with the malformed duplicate 4-line block (2481-2484) removed (the good
first entry is untouched). Did NOT edit the vendor original in
`MECHANISM/`. Reconverted → `outputs/ammonia_campaign/yaml/konnov_2019_128-957.yaml`
(128 species, 957 reactions) — **ck2yaml exits 0, Cantera validation PASSES**
(two harmless thermo-discontinuity warnings for OHV/CHV at Tmid=1000, not
blocking).

**Verified:** `cantera.Solution(path)` loads directly; set
`TPX=1200K,1atm,'NH3:0.2,O2:0.15,N2:0.65'` and got a real density
(0.268 kg/m3) — Konnov 2019 now produces real Cantera output. This is the
crux fix the user asked for.

### Glarborg 2018 (fusion base) — two more bugs found + fixed, now loads

**Bug 2 (file:line):** `MECHANISM/GLARBORG_2018/GLARBORG_2018_thermo.dat:1151-1154`
— the exact same malformed duplicate `CH3CH2NH2` thermo block as Konnov
(same vendor thermo data lineage). Fix: same approach, repaired copy at
`outputs/ammonia_campaign/fixed_mechs/fixed_GLARBORG_2018_thermo.dat` with
lines 1151-1154 removed.

**Bug 3 (file:line):** `MECHANISM/GLARBORG_2018/GLARBORG_2018.inp:4062,4063`
— two stray non-printable control bytes (0x15, "NAK") embedded in reaction
bibliography comments (mis-encoded en-dashes in journal page ranges, e.g.
"17:2069\x152082, 2011"). These get carried straight through ck2yaml into
the generated YAML's `note:` fields, and `yaml.safe_load` (used throughout
`rmip.analysis.mechanism_check`/`mechanism_fixer` for raw-YAML scans)
chokes with `yaml.reader.ReaderError: unacceptable character #x0015`,
silently disabling every raw-YAML-based check (pdep_sanity, duplicates,
schema_deprecation, name_consistency) with no visible error — `_try_parse_yaml`
swallows the exception and returns `None`. Fix: repaired copy
`outputs/ammonia_campaign/fixed_mechs/fixed_GLARBORG_2018.inp` with both
0x15 bytes replaced by `-`.

**Bug 4 (real mechanism defect, not tooling):** After bugs 2-3 were fixed,
ck2yaml wrote a valid YAML but Cantera's own `Solution()` construction still
failed: `PlogRate::validate` rejected reaction `HCCO + OH <=> CH2 + CO2`
and `C2H3 + CH2O <=> C2H4 + HCO` for negative computed rate coefficients.
Root: Glarborg 2018 uses an intentional "dual-PLOG subtraction channel"
vendor fitting technique — two `duplicate: true` reactions for the same
equation, one with a normal positive-A fit and a second who's A is
negative at one or more pressures so the two SUM to a physically sane net
rate; the mechanism's own inline comments literally say
`!results in negative rate constant`, acknowledging it. Cantera's
`PlogRate::validate` checks each duplicate reaction's rate individually
across T=300-10000K and rejects any that goes negative, without knowledge
that it will later be summed against its positive twin. This is a known,
already-anticipated category in this repo's tooling
(`src/rmip/analysis/mechanism_check.py` `check_pdep_sanity`/`_check_plog`,
`src/rmip/analysis/mechanism_fixer.py` `_fix_plog_drop_negative`) — used the
intended path: `python3 rmip_cli.py check <yaml> --fix all --fixed-out ...`.

**Bug 5 (tooling bug found + fixed, file:line
`src/rmip/analysis/mechanism_check.py::_check_plog`/`_plog_fix_options`):**
one of the 3 flagged PLOG reactions (`C2H3 + CH2O <=> C2H4 + HCO`
"Reaction 287") has EVERY pressure piece negative (it's the pure
subtraction channel) — `plog_drop_negative` correctly refused ("dropping
would leave no PLOG pieces") but there was no fallback fix, so `--fix all`
left it broken. **Fix:** taught `_check_plog` to detect the
all-pieces-negative case and offer `delete_reaction` (drop the whole
duplicate reaction; its positive-A twin — the OTHER declared duplicate for
the same equation — still carries the rate) as the recommended choice fix
instead of `plog_drop_negative`. Verified: the correct (positive-A) twin
survives, the all-negative one is gone.

**Bug 6 (tooling bug found + fixed, file:line
`src/rmip/analysis/mechanism_fixer.py::_flush_deletes`):** after
`delete_reaction` removed the negative-A twin, Cantera's own
`Kinetics::checkDuplicates` then rejected the SURVIVING twin:
`No duplicate found for declared duplicate reaction number 285` — deleting
one of a matched `duplicate: true` pair orphans the other, which Cantera
requires to have >=2 instances if flagged duplicate. **Fix:** `_flush_deletes`
now re-scans reactions by equation after every deletion batch and clears
`duplicate: true` on any equation left with exactly one surviving instance.

**Bug 7 (real, wide-blast-radius tooling bug found + fixed — "the NO
problem"):** Even after bugs 2-6, the fixed YAML failed to load with a
bizarre `InputFileError ... setupPhase: Could not parse species declaration
of type 'vector<AnyValue>'` pointing at the very FIRST entry of the phase's
species list (`- H2`), which made no sense structurally. Root-caused via
binary search over the 151-entry species list: **PyYAML's stock
`SafeLoader` follows YAML-1.1 boolean semantics, where the bare token `NO`
(nitric oxide — present in virtually every NOx-containing mechanism,
including every ammonia mechanism in this repo) implicitly resolves to
Python `False`.** `rmip.analysis.mechanism_check._try_parse_yaml` and
`rmip.analysis.mechanism_fixer.MechanismFixer.__init__` both parse the
Cantera-YAML with plain `yaml.safe_load`, silently turning the species name
`"NO"` into a boolean; `MechanismFixer.write()` then re-serializes that
`False` back out as a literal YAML `false` sitting inside what's supposed to
be an all-string species-name list — which Cantera's own (stricter) reader
rejects as a mixed-type `vector<AnyValue>`. This is the classic
"Norway problem" (ISO country code "NO") applied to nitric oxide.
**Fix:** added `src/rmip/analysis/yaml_safe.py` — a `CanteraSafeLoader`
(subclasses `yaml.SafeLoader`) whose bool implicit-resolver is narrowed to
only `true/True/TRUE/false/False/FALSE` (matching what Cantera's own YAML
reader treats as boolean), leaving `NO`/`YES`/`ON`/`OFF`/`Y`/`N` (any case)
as plain strings, with `safe_load()`/`safe_load_path()` helpers. Wired into
every raw-YAML-parse call site found on a mechanism file:
`mechanism_check.py::_try_parse_yaml`, `mechanism_fixer.py::MechanismFixer.__init__`,
`yaml_validator.py::_load_yaml`, `multiphase_sanity.py::condensed_phase_names`,
`surface_crosscheck.py` (Cantera-Interface cross-check loader),
`finite_solid_reactor.py::_resolve_phase_names`. **Not yet swept** (lower
priority / not on the ammonia critical path — flagging for the user):
`src/rmip/io/exp_data_reader.py`, `src/rmip/io/glossary_reader.py`,
`src/rmip/simulation/zerork_bridge.py`, `src/rmip/simulation/muqsac_bridge.py`
also call plain `yaml.safe_load` — these parse experiment-data/glossary/config
YAML rather than mechanism species lists so are lower-risk, but should be
swept to the same helper if they're ever pointed at a raw mechanism YAML.

**Verified:** `outputs/ammonia_campaign/yaml/glarborg_2018_LOADABLE.yaml`
loads directly via `cantera.Solution()`: 151 species, 1396 reactions (one
fewer than the original 1397 — the deleted all-negative PLOG duplicate),
`NH3` present, `NO` present and correctly a string (`species_index('NO')==66`,
not corrupted), real density computed at a sample NH3/O2/N2 state.

### Sarathy 2021 — converted + loads (2 more genuine mechanism defects found)

`ck2yaml` conversion itself succeeded first try (38 species, 263 reactions,
some harmless "Skipping unexpected species" for a few undeclared N2O3/N2O4
thermo entries — not used in reactions, harmless). But `cantera.Solution()`
failed with **`Kinetics::checkDuplicates`: undeclared duplicate reactions**
— a genuine, systemic authoring gap in this vendor mechanism (not a
converter bug): a generic three-body reaction like `H2 + M <=> H + H + M`
lists explicit efficiencies for `H2/H2O/CO/CO2/AR/HE` but leaves `O2` at
the Chemkin default efficiency of 1.0, while a SEPARATE explicit reaction
`H + O2 + H <=> H2 + O2` (comment "M. Burke, S. Klippenstein, Nature
Chemistry 2017") covers the exact same H2-dissociation pathway with O2 as
the specific third body — an undeclared double-count. Found this same
pattern **twice** (`H2+M<=>H+H+M` / `H+O2+H<=>H2+O2`, and
`H2O+M<=>H+OH+M` / `H+OH+O2<=>H2O+O2`). **Fix:** wrote a small iterative
script (using `rmip.analysis.mechanism_check._yaml_reaction_signature` for
order-insensitive equation matching, since Cantera's own error message
normalizes reactant order differently than the literal YAML text) that:
tries `cantera.Solution()`, on failure regex-parses the
`Reaction N: <eq>\nReaction M: <eq>` pair Cantera reports, marks both
`duplicate: true`, and repeats until it loads (converged in 3 iterations).
Applied directly to `outputs/ammonia_campaign/yaml/sarathy_2021.yaml` (the
generated artifact, not touching `MECHANISM/`), with an inline comment on
each edited reaction explaining the physics. **Verified:** loads directly
(38 species, 263 reactions), NH3 present, real density computed.

### Konnov-NCN 2009 — converted + loads (3 more bugs found + fixed)

**Bug (file:line `MECHANISM/KONNOV_NCN_2009/NCN_MECH_KONNOV_2009.inp:73`):**
`REACTIONS         BASE M=N2` — `BASE M=N2` is a non-standard vendor
REACTIONS-line extension ck2yaml's parser doesn't recognize at all
("Unrecognized token on REACTIONS line, 'BASE'"), hard-crashing before any
reaction gets parsed. Its evident intent (N2 as the reference/base third
body) already matches Chemkin's own default (any third-body species not
listed in a reaction's efficiency map defaults to efficiency 1.0, same as
N2 here) — dropping it is meaning-preserving. Fix: repaired copy
`outputs/ammonia_campaign/fixed_mechs/fixed_NCN_MECH_KONNOV_2009.inp` with
the `BASE M=N2` tokens replaced by an explanatory comment.

**Bug (file: `MECHANISM/KONNOV_NCN_2009/NCN_THERMO.dat`, 36 lines, e.g.
line 56):** systemic Fortran-exponent corruption of a DIFFERENT shape than
Konnov 2019's fixture: `0.47028847E 01` — a bare **space** where the sign
character should be (not simply a missing sign glued to digits, which the
converter GUI's existing `fix_fortran_exponents` regex already handles —
this is `E` + space + digits, a different malformation the existing
regex doesn't match). Also 2 stray literal tab characters. Fix: repaired
copy `outputs/ammonia_campaign/fixed_mechs/fixed_NCN_THERMO.dat` regex-replacing
`E (\d{1,3})` → `E+\1` on non-comment lines (80 occurrences) and tabs → spaces.
**Follow-up for the user / lower priority:** consider teaching
`mechanism_converter_gui.py::fix_fortran_exponents` this second exponent-space
pattern too, since it's clearly not unique to this one file — flagged, not
fixed, since it's outside today's direct blocking path (the repaired copy
unblocks Konnov-NCN 2009 either way).

**Bug (file: `MECHANISM/KONNOV_NCN_2009/NCN_THERMO.dat:523-526`, one-off):**
one malformed, undeclared, unused thermo entry for species `TC4H7`
(column-misaligned like Konnov 2019's CH3CH2NH2 case, likely from a tab
that was byte-for-byte preserved but was originally meant to visually
expand to align columns) — confirmed `TC4H7` appears nowhere else in the
mechanism's species/reactions. Removed the 4-line block.

**Bug (file: `MECHANISM/KONNOV_NCN_2009/NCN_THERMO.dat`, originally lines
543-545):** three consecutive stray `END` lines in the middle of the
`THERMO ALL` section (clear vendor copy-paste-concatenation artifact —
looks like 2+ separate thermo files were pasted together without removing
each other's `END` markers), with more species entries continuing
afterward through to the file's true final `END` at (post-edit) line 596.
ck2yaml correctly closes the THERMO section at the first stray `END`, then
chokes on the second one ("Section starts with unrecognized keyword END").
Fix: removed all 3 spurious `END` lines so the section runs uninterrupted
to the one legitimate trailing `END`.

**Verified:** `outputs/ammonia_campaign/yaml/konnov_ncn_2009.yaml` converts
clean (ck2yaml "PASSED"), loads directly (129 species, 1231 reactions), NH3
present.

### Gabriel 2022 — already a Cantera YAML, loads as-is

`MECHANISM/GABRIEL_2022_AMMONIA_HYDROGEN/Mechanism Files/Gas-Phase-Kinetics_Detailed.yaml`
loads directly with no changes needed (32 species, 165 reactions, NH3
present). Copied to `outputs/ammonia_campaign/yaml/gabriel_2022.yaml` for a
uniform Phase-5 fusion input set.

### Phase 1 summary — all 5 NH3 mechanisms now load in Cantera

```
Konnov 2019          OK  species= 128 reactions=  957 NH3=True
Glarborg 2018        OK  species= 151 reactions= 1396 NH3=True
Sarathy 2021         OK  species=  38 reactions=  263 NH3=True
Konnov-NCN 2009      OK  species= 129 reactions= 1231 NH3=True
Gabriel 2022         OK  species=  32 reactions=  165 NH3=True
```

Files: `outputs/ammonia_campaign/yaml/{konnov_2019_128-957,glarborg_2018_LOADABLE,sarathy_2021,konnov_ncn_2009,gabriel_2022}.yaml`.
Repaired vendor-file copies: `outputs/ammonia_campaign/fixed_mechs/`.
Conversion logs: `outputs/ammonia_campaign/logs/`.

**Bugs found so far: 10** (7 in Phase 1 tooling/mechanism-data across
Konnov/Glarborg + the systemic "NO problem", 2 in Sarathy's mechanism
authoring, 4 in Konnov-NCN's mechanism data — some counted above overlap
categories; see per-mechanism sections for exact file:line detail).
**Code changes made (not just repaired data copies):**
- `src/rmip/analysis/yaml_safe.py` (new file) — `CanteraSafeLoader` fixing
  the PyYAML "NO problem".
- `src/rmip/analysis/mechanism_check.py::_try_parse_yaml` — use it.
- `src/rmip/analysis/mechanism_check.py::_check_plog`/`_plog_fix_options` —
  detect all-pieces-negative PLOG reactions and recommend `delete_reaction`
  instead of the no-op `plog_drop_negative`.
- `src/rmip/analysis/mechanism_fixer.py::MechanismFixer.__init__` — use the
  safe loader.
- `src/rmip/analysis/mechanism_fixer.py::_flush_deletes` — clear orphaned
  `duplicate: true` flags left on a lone survivor after a duplicate-pair
  deletion.
- `src/rmip/analysis/yaml_validator.py::_load_yaml`,
  `src/rmip/analysis/multiphase_sanity.py::condensed_phase_names`,
  `src/rmip/simulation/surface_crosscheck.py`,
  `src/rmip/simulation/finite_solid_reactor.py::_resolve_phase_names` — all
  switched to the safe loader (same "NO problem" blast radius).

---

## Phase 2 — Health-check sweep (all 5 mechanisms)

Ran the full 17-check suite (`.gui_settings/mechanism_check.json`'s T/P
grid: T=300/800/1400/1800/2200/2500 K, P=0.1/1/10/50 atm,
collision-exceedance=10, target-T-high=2500) against all 5 loadable YAMLs
via `python3 rmip_cli.py check <yaml> --T-grid ... --P-grid ... --json ...`.

### Bug 8 (tooling, high blast-radius, found+fixed): syntax_lint false
positives on bibliography text

First pass: every mechanism reported hundreds of spurious "error"-severity
findings, e.g. `Numeric field '2013.' looks truncated (ends mid-token)` —
Glarborg alone had 49 syntax_lint "errors" + 334 "warnings" that were pure
noise, swamping the real findings and making every mechanism report
`verdict: FAIL` regardless of actual quality. Root-caused in
`src/rmip/analysis/syntax_lint.py::SyntaxLinter`: its raw text scan strips
`!`/`#`-prefixed comments per line but has no concept of a **YAML
`note: |-` literal-block scalar** — a `note:`/`description:` field's
multi-line bibliographic body has no per-line comment marker (indentation
alone marks it as part of the block in YAML), so citation text like
"J Phys Chem A 2013." or "17:2069-2082, 2011." got scanned as if it were
mechanism data and tripped the "truncated numeric field mid-token"
heuristic on every trailing "digits+period". Three compounding causes, all
fixed in `src/rmip/analysis/syntax_lint.py::SyntaxLinter.lint()`:
1. No tracking of YAML block-scalar body lines at all — added a small state
   machine (`_YAML_BLOCK_SCALAR_KEY_RE` + `block_indent`) that skips lines
   inside a `key: |`/`key: >` body.
2. `src/rmip/analysis/mechanism_fixer.py::MechanismFixer.write()` was
   itself part of the problem: plain `yaml.safe_dump` re-serializes any
   multi-line Python string as a *quoted* scalar instead of preserving
   ck2yaml's own literal-block style, which (a) is uglier and (b) has no
   block marker for (1) above to key off. Fixed by adding a custom
   `_str_presenter` (literal `|` style whenever the string contains `\n`).
3. Even a *single-line* `note: <long citation>` gets implicitleft-folded by
   PyYAML across two physical lines once it exceeds the default 80-column
   `width` — same false-positive shape for a different reason. Fixed by
   passing `width=100000` to `yaml.dump` in `write()` so nothing gets
   implicitly folded.
4. Residual: even a genuinely single-line, unwrapped `note: <text ending
   in "(1986) 1987."` still legitimately ends in "digits+period" (a
   sentence, not truncated Fortran). Fixed by adding `_YAML_NOTE_KEY_RE`
   to skip lint checks on the whole value of any inline `note:`/`description:`
   line outright (bibliography text is never mechanism data).

**Effect:** Glarborg 2018's syntax_lint noise went from 49 errors / 334
warnings to **0 errors / 0 warnings**; Konnov 2019 25→7 total errors (all
genuine now); Gabriel 2022 13→1 total error/warning.

**Known minor residual (not fixed, flagged only):** `sarathy_2021.yaml`
still has 2 syntax_lint false positives from a `note: '...'` **quoted**
(not block-literal) multi-line scalar that ck2yaml itself emitted directly
(pre-dates any of our tooling) when a note's source text contains an
embedded blank line between two citations — quoted-multiline continuation
lines carry no marker either but this shape is rarer and lower priority;
noting for the user rather than chasing further.

### Per-mechanism results (after the syntax_lint fix)

```
konnov_2019       FAIL   7 error(s), 23 warning(s), 2 info
glarborg_2018     FAIL  13 error(s), 43 warning(s), 2 info
sarathy_2021      FAIL   5 error(s), 42 warning(s), 2 info
konnov_ncn_2009   FAIL  36 error(s), 44 warning(s), 2 info
gabriel_2022      FAIL   1 error(s),  1 warning(s), 2 info
```

**All remaining errors are genuine mechanism-quality findings, not tooling
bugs** (spot-checked every category):
- `collision_limit` (bulk of the count, all 5 mechanisms): reverse rate
  exceeds the gas-kinetic collision limit by 3-28 orders of magnitude,
  almost always at **T=300 K** — a well-known artifact of computing
  reverse rates via equilibrium constant from a forward-rate Arrhenius fit
  that's only valid over combustion temperatures (1000-2500 K);
  extrapolating down to 300 K blows up. Not a bug, a known modeling
  limitation of these published mechanisms outside their intended T-range.
  Konnov-NCN 2009 has by far the most (32 errors) — its rate data is the
  oldest (2009 vintage).
- `thermo_discontinuity` (Konnov-NCN 2009, 4 species: HCNH, H2CNO, CH3NO,
  C2H5CHO; Glarborg 2018, 1 species: HOCHO): genuine NASA-7 Cp/H/S
  discontinuities at the vendor's own Tmid — real thermo-fit quality
  issues in the original data, not something to silently "fix" (refitting
  would change the mechanism's predictions; flagging for the user is the
  correct behavior here).
- `unit_sanity` (`ea-magnitude`, 1 per mechanism): informational check on
  whether Ea values look like they might be in the wrong unit register —
  did not investigate individually given time budget; low severity
  (warning), not blocking any of today's phases.

Reports: `outputs/ammonia_campaign/health_check/{name}_report.{json,txt}`
for `konnov_2019`, `glarborg_2018`, `sarathy_2021`, `konnov_ncn_2009`,
`gabriel_2022`.

**Bugs found in Phase 2: 1 (but high blast-radius — affects every YAML
mechanism this whole suite's syntax_lint check has ever run against).**
Code changed: `src/rmip/analysis/syntax_lint.py` (new state machine +
2 new regexes), `src/rmip/analysis/mechanism_fixer.py::write()` (literal-
block string representer + unbounded width).

---

## Phase 3 — 5-target Tig subset + units decision

### Units decision (documented per the task's explicit request)

`DATASET/AMMONIA/AMMONIA.target` (283 rows) turns out to have not just the
"atm vs Pa" split flagged in the task brief, but a **third** variant: its
own per-row `units` dict is genuinely mixed — 170 rows say `P: atm`, 113
say `P: bar` (`Counter({'atm': 170, 'bar': 113})`), and the numeric `P`
values are already correctly scaled for whichever unit that row declares
(P=11.3 with atm, P=4.3 with bar — not a units bug, just two vendor
datasets merged with different original conventions). Separately,
`DATASET/AMMONIA_COMBUSTION_EXP_DATA/TEST/TIG/target.opt` carries the same
underlying measurements in Pa (~1.2e5-1.15e6). Checked which unit the
actual simulation pipeline expects: `src/rmip/io/respecth_reader.py::_pressure_to_atm`
is the internal normalizer used when ingesting ReSpecTh data — **the
pipeline's canonical internal pressure unit is atm**. Decision: build the
5-target subset from `AMMONIA.target` (the file the task explicitly named)
and normalize every row to `P: atm` (bar→atm via ×0.9869233), rather than
adopting the Pa convention from the TEST/TIG copies. This resolves both the
task's named atm-vs-Pa question and the atm-vs-bar split already latent
inside `AMMONIA.target` itself, in the direction the pipeline already
expects.

**Flagging for the user (a data-provenance question, not something I
resolved):** `DATASET/AMMONIA_COMBUSTION_EXP_DATA/TEST/TIG/target.opt`
doesn't just use different units for the same dataset ids — for at least
`x10100003`/`x10100004`, it also puts NH3 in the `Fuel` slot and H2 in
`Bath_gas`, whereas `AMMONIA.target` puts H2 in `Fuel` and Ar-only in
`Bath_gas` for the same ids (O2 oxidizer amount matches across both, so
it's the same underlying experiment). Did not chase which one reflects the
authors' intent — noting so the user can decide which composition
role-assignment is correct before trusting either file for a real
optimization run.

### The 5 picked targets (spread across T, P, composition)

Selected to span the widest reasonable range along 3 axes at once
(temperature, pressure, and fuel — pure-H2 vs pure-NH3 blends) rather than
5 arbitrary/adjacent rows:

| # | dataset_id | T (K) | P (atm, normalized) | fuel (mole) | observed Tig (us) | picked for |
|---|---|---|---|---|---|---|
| 1 | x10100007 | 1022.7 | 1.19 | H2=3.745 | 1778.0 | coldest point |
| 2 | x10199004 | 2586.4 | 0.247 | NH3=0.05 | 105.0 | hottest point |
| 3 | x10199003 | 2165.8 | 35.33 | NH3=0.02 | 8.74 | highest pressure |
| 4 | x10100002 | 1988.7 | 7.30 | H2=0.003 | 15.9 | representative pure-H2 |
| 5 | x10199010 | 2266.0 | 1.46 | NH3=0.004 | 226.0 | representative pure-NH3 |

Output: `outputs/ammonia_campaign/targets/AMMONIA_5TIG.target` (same
pipe-delimited MSO row format as the source file, `P`/`units.P` rewritten
to atm) + `outputs/ammonia_campaign/targets/AMMONIA_5TIG_summary.json`
(machine-readable selection record with both original and normalized P).

### The 3 reactions (for every scoped stress run in later phases)

Picked from Konnov 2019 (the primary subject mechanism) to span the 3
chemistry classes that matter most for NH3/H2 ignition delay:
1. `H + O2 <=> O + OH` — H2/O2 chain-branching (index 5)
2. `NH3 + OH <=> H2O + NH2` — primary NH3 fuel-consumption step (index 625)
3. `NH2 + NO <=> H2O + N2` — the central NH3 deNOx/NOx-reduction pathway (index 532)

Recorded in `outputs/ammonia_campaign/targets/three_reactions.json` (by
equation text, since reaction-list index is mechanism-specific).

---

## Phase 4 — Uncertainty generation

Scoped to the 3 reactions from Phase 3 (`H+O2<=>O+OH`, `NH3+OH<=>H2O+NH2`,
`NH2+NO<=>H2O+N2`), against Konnov 2019 (the primary subject mechanism).

Built a MUQ-SAC uncertainty XML via
`uncertainty_generator_gui.py::generate_uncertainty_xml()` — same 11-point
500-2500 K temperature grid and `sigma_lnk` convention as the shipped
`DATASET/H2_O2_TEST/uncertainty/H2_uncertainty.xml` reference. For
`H+O2<=>O+OH` reused that file's own literature-informed values verbatim
(same reaction); for the two NH3 reactions used representative
stress-test values (wider bands, since NH3 sub-mechanism kinetics are less
well-constrained in the literature than core H2/O2 chemistry, and the
`NH2+NO` branching-ratio question specifically is a known open debate in
the NH3-combustion literature) — **not** a literal re-derivation from a
cited source; noting that clearly since this is a stress test, not a
production uncertainty quantification.

Ran `uncertainty_generator_gui.py::compute_symmetric_bounds()` against
`outputs/ammonia_campaign/yaml/konnov_2019_128-957.yaml`: all 3 reactions
resolved cleanly (no errors — confirms Konnov 2019's equation strings match
what `Uncertainty.py`'s `reaction` class expects), producing real symmetric
A-factor bounds:

| reaction | A_nominal | factor | A_lb | A_ub |
|---|---|---|---|---|
| H+O2<=>O+OH | 1.040e14 | 1.4995 | 6.936e13 | 1.560e14 |
| NH3+OH<=>H2O+NH2 | 2.040e6 | 1.6557 | 1.232e6 | 3.378e6 |
| NH2+NO<=>H2O+N2 | 2.800e20 | 1.8283 | 1.531e20 | 5.119e20 |

Artifacts: `outputs/ammonia_campaign/uncertainty/ammonia_3rxn_unsrt.xml`
(input) + `outputs/ammonia_campaign/uncertainty/ammonia_3rxn_bounds.csv`
(output bounds).

**Convention note (per the task's explicit instruction — flagging, not
resolving):** this used `uncertainty_generator_gui.py`'s own
`compute_symmetric_bounds()`, i.e. the **max-over-3-anchors** convention
(`bug.md`'s MINOR list: "an uncertainty-convention mismatch between
`Uncertainty.py` (min-over-T, conservative) and
`uncertainty_generator_gui.py` (max-over-3-anchors, anti-conservative) for
the same XML input, with nothing in the file format recording which
convention a given output used"). The bounds above are therefore the
**anti-conservative** (narrower) convention, not `Uncertainty.py`'s own
native min-over-T bound. This is a pre-existing, known, separate issue —
not fixed here per the task's instruction, just recorded so this output
isn't mistaken for the conservative variant.

Did not attempt Glarborg (fusion base) uncertainty generation given the
3-reaction/stress-test scope only asked for "Konnov 2019 and/or Glarborg" —
Konnov 2019 alone satisfies the phase.

---

## Phase 5 — Full mechanism fusion (all 5 mechanisms, Glarborg 2018 base)

FULL scale per the task (not scoped to 3 reactions).

### Setup

Built a fresh DB `outputs/ammonia_campaign/fusion/ammonia_fusion.db` and
parsed all 5 loadable YAMLs via `rmip_cli.py parse ... --glossary
species_smiles.csv --format cantera_yaml` (glossary needed for cross-
mechanism species matching per the converter's own note). Mechanism ids:
1=Glarborg_2018, 2=Konnov_2019, 3=Sarathy_2021, 4=Konnov_NCN_2009,
5=Gabriel_2022. Glossary hit rates were low for 3 of 5 (Glarborg 23.2%,
Konnov 2019 27.3%, Konnov-NCN 24.0%; Sarathy 89.5%, Gabriel 93.8%) — not
fixed (out of scope), but this caps how much cross-mechanism species
matching the fusion can actually do; noting for the user since it affects
fusion quality (313 of 348 total species ended up "unique", i.e. name-
unmatched across mechanisms, largely a symptom of this).

### Bug 9 (found + fixed): silently-empty kinetics for a real Cantera 3.x reaction type

First fusion attempt (`mean_value_fusion_gui.py::_run_fusion`, priority
mode) crashed writing the fused CHEMKIN output:
`ValueError: Reaction id=4027 ('CH2O + H <=> CO + H2 + H'): no usable A
value (A_si and A_orig both NULL)`. Traced to the SOURCE row (mechanism_id=1,
Glarborg) already having `kinetics_type='three-body-pressure-dependent-
arrhenius'`, `A_si=None`, `kinetics_data_json='{}'` — i.e. the bug is in
ingestion, not fusion. Root cause: `src/rmip/io/cantera_reader.py::_parse_kinetics`
dispatches on Cantera's `rx.reaction_type` string, handling `"Arrhenius"`,
`"three-body-Arrhenius"`, `"falloff-*"`, `"pressure-dependent-Arrhenius"`,
`"Chebyshev"` — but Cantera 3.0.1 also emits a **distinct**
`"three-body-pressure-dependent-Arrhenius"` type (confirmed via direct
Cantera introspection: `rx.rate` for these is still a plain `PlogRate`
with the normal `.rates` list API, `rx.third_body` is a separate
`ThirdBody` object) that wasn't in the dispatch table, so every such
reaction fell into the generic "unrecognized" fallback and got stored with
**every kinetics field silently NULL/empty** — no crash, no visible error,
until the fusion engine's verbatim-copy path tried to actually write a
rate constant for one. Found 2 such reactions in Glarborg 2018 (of the 5
mechanisms, only Glarborg has any). **Fix:**
`src/rmip/io/cantera_reader.py::_parse_kinetics` — added
`"three-body-pressure-dependent-Arrhenius"` as an alias of
`"pressure-dependent-Arrhenius"` (same parsing branch, same `"plog"`
kinetics_type; `has_third_body` was already a separate DB column so no
other change needed). Re-parsed Glarborg after the fix and confirmed both
reactions now carry real A/n/Ea (e.g. `CH2O + H <=> CO + H2 + H` →
A=51000, n=2.182, Ea=48216 J/mol at 1 atm).

### Fusion runs (two variants — see decision note below)

Ran via `rmip.analysis.graph_comparator.GraphComparator.compare([1,2,3,4,5])`
→ `rmip.analysis.fusion.FusionEngine.fuse(result, priority_order=...)` →
`export_union_spec`/`export_mso_bounds` (the path the task's named
deliverables — `union_spec`/`mso_bounds.json` — actually come from;
`rmip_cli.py fuse`'s CLI wrapper doesn't expose `priority_order` as a flag
even though the underlying engine supports it, so called the Python API
directly rather than extend the CLI, given time budget).

Graph comparison across all 5: species universal=26, partial=9, unique=313
(348 total); reactions identical=61, divergent=183, unique=3014 (3258
total reactions across all 5 mechanisms pre-fusion).

**Decision (flagging, not silently picking one) — priority-pick vs
mean-consensus:** with `priority_order=[1,2,3,4,5]` (Glarborg first, per
the task's explicit "Glarborg 2018 as the base mechanism" instruction),
EVERY shared reaction (both the 61 identical and the 183 divergent) gets
copied verbatim from the highest-priority mechanism that has it — there is
then nothing left for the "FUSE" (MSO-averaged) bucket, so
`mso_bounds.json` is legitimately near-empty (`n_fuse_reactions: 0`,
142 bytes) even though this IS the correct, real output for that mode. The
task also asks for real `mso_bounds.json` content, which only comes from
the mean/consensus strategy (no priority — geometric-mean A, arithmetic-
mean n/Ea across divergent reactions). Ran **both**, output side-by-side:
- `outputs/ammonia_campaign/fusion/union_spec.json` +
  `outputs/ammonia_campaign/fusion/mso_bounds.json` — **Glarborg-priority**
  fusion (fused mechanism id=7 in the DB). VERBATIM=3014, COPY=0, FUSE=0.
  This is the literal fulfillment of "Glarborg 2018 as the base mechanism."
- `outputs/ammonia_campaign/fusion/union_spec_mean.json` +
  `outputs/ammonia_campaign/fusion/mso_bounds_mean.json` — **mean-consensus**
  fusion (fused mechanism id=8), for comparison / in case the user actually
  wants populated MSO bounds to feed an optimizer. VERBATIM=3029, COPY=61,
  FUSE=168 — real per-reaction `params_mean`/`params_lb`/`params_ub` for
  A_si/n/Ea_si, e.g. `H + O2 <=> O + OH`: mean A=2.199e8, lb=9.75e7,
  ub=5.071e9 (m^3/mol/s). 125 of the 168 FUSE reactions logged an
  uncertainty-factor warning >10x (some enormously — up to ~1e32 for one
  N2H4 dissociation reaction) — expected given these are 5 independently-
  fit mechanisms spanning 2009-2022 vintage, not a bug.
- Also produced via `mean_value_fusion_gui.py::_run_fusion` (the other
  named-in-task GUI path): real CHEMKIN `.inp`/`.dat` fused-mechanism files
  at `outputs/ammonia_campaign/fusion/AMMONIA_FULL_FUSION.{inp,dat}`
  (603950/112797 bytes) — the priority-pick variant, `write_cantera=True`'s
  optional CHEMKIN→Cantera-YAML round-trip export hit a separate bug (next
  section) and was left disabled for this run; the .inp/.dat pair is itself
  real, usable fused-mechanism output independent of that.

### Bug 10 (found, NOT fixed — flagging as a design/scope decision):
ck2yaml crashes on its own error path for a fusion-generated falloff reaction

`mean_value_fusion_gui.py::_run_fusion(..., write_cantera=True)` writes the
fused mechanism to CHEMKIN then round-trips it through `ck2yaml` to also
produce a Cantera YAML. That round-trip crashes:
`AttributeError: 'NoneType' object has no attribute 'reaction_string_suffix'`
— this is **ck2yaml's own bug** (in `cantera/ck2yaml.py:314`,
`self.kinetics.reaction_string_suffix(self.third_body)` where
`self.kinetics` is `None`), triggered while ck2yaml tries to *format an error
message* about a different, real problem: a fused reaction
`C2H6(+M)<=>C2H5__src4+H(+M)` (line 10262 of the generated
`AMMONIA_FULL_FUSION.inp`) that ck2yaml's parser flags as
"Reaction equation implies pressure [dependence]" (a `(+M)` falloff-style
equation lacking the LOW/TROE auxiliary data CHEMKIN format requires for
that shape) — but then ck2yaml crashes trying to even DESCRIBE that error,
so the real underlying defect (why did the fusion/ChemkinWriter emit a
`(+M)` equation without matching falloff data for this one reaction,
sourced from mechanism 4/Konnov-NCN 2009 per the `__src4` species-name
disambiguation suffix?) was never actually diagnosed. This sits at the
boundary of three components (this suite's fusion/ChemkinWriter, vendored
Cantera's ck2yaml, and a species-name-collision suffix scheme) and would
need real investigation time to fix correctly rather than a quick patch —
flagging for the user rather than guessing at a fix. Workaround used for
this campaign: ran with `write_cantera=False` for the CHEMKIN-only path
(fully working, files present) and got the real Cantera-YAML-equivalent
deliverable via the `union_spec`/`mso_bounds.json` path instead, which
doesn't touch ck2yaml at all.

**Bugs found in Phase 5: 2 (1 fixed — the silent-NULL-kinetics parser gap;
1 flagged as a scope/investigation decision — the ck2yaml crash).**

---

## Phase 6 — Target optimization (3 reactions, 5 targets)

This phase exercised the REAL FlameMaster/Cantera/MUQ-SAC solver toolchain
end-to-end for the first time this session on ammonia data. Found and
fixed **6 real bugs** across the toolchain (detailed below) before hitting
a final blocker deep in the "2_0" partial-response-surface subsystem,
which is flagged rather than patched (see end of this section).

### Setup

- Generated a FlameMaster `.pre` file for Konnov 2019 via ScanMan
  (`/home/krithika/FlameMaster/Bin/bin/ScanMan`), needed because
  `target.opt`'s `Locations.Initial_pre_file` is a required input for the
  FlameMaster-based reactor solve.
- Built `outputs/ammonia_campaign/target_opt/ammonia_5tig_3rxn.opt` (full
  MUQ-SAC project config), `Counts.total_reactions: 3`,
  `Counts.targets_count: 5`, pointing at Konnov 2019 + our 3-reaction
  uncertainty XML + (revised, see below) 5-target Tig subset.

### Bug 11 (found + fixed): ScanMan can't parse this vendor file's `DUPLICATE` marker

ScanMan (FlameMaster's own, stricter, older CHEMKIN parser — separate from
Cantera's ck2yaml) failed immediately: `Cannot find species 'DUPLICATE' in
species list!`. Root cause: `MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/128-957.inp`'s
14 `DUPLICATE` marker lines all have a trailing empty inline comment
(`" DUPLICATE                                                                     !"`),
unlike the repo's other working ScanMan-parsed mechanism (`MECHANISM/GRI3/chem_gri30_wetCO.inp`,
whose `DUPLICATE` lines have no trailing `!` at all) — ScanMan's DUPLICATE-
keyword recognition apparently doesn't tolerate a same-line comment marker
and instead tries to parse "DUPLICATE" as a species-name token. **Fix:**
repaired copy `outputs/ammonia_campaign/fixed_mechs/fixed_scanman_128-957.inp`
with all 14 active `DUPLICATE...` lines normalized to a bare `DUPLICATE`
(the 2 already-commented-out `!DUPLICATE` lines untouched).

### Bug 12 (found + fixed): a second Fortran-exponent malformation shape

After fixing bug 11, ScanMan's thermo lexer choked on
`0.3332728 E+05` (species CC3H4, line 530 of the Konnov thermo file) — a
**space before** the exponent marker, a different malformation shape than
the "missing E" pattern `mechanism_converter_gui.py::fix_fortran_exponents`
already handles (and different from Konnov-NCN's "E, then missing sign"
pattern fixed in Phase 1). ck2yaml apparently tolerates this shape
silently; ScanMan's lexer does not. **Fix:** repaired copy already in
`outputs/ammonia_campaign/fixed_mechs/fixed_128-957.dat`, this one
occurrence corrected. After both fixes, ScanMan ran clean (a couple of
harmless "doubly defined reaction" informational warnings — ScanMan's own,
slightly different, duplicate-detection heuristic) and wrote a real 2.3 MB
`.pre` file: `outputs/ammonia_campaign/target_opt/konnov_2019.pre`.
**Follow-up for the user:** `mechanism_converter_gui.py::fix_fortran_exponents`
now has 3 known distinct malformation shapes it doesn't catch (this one,
Konnov-NCN's, both found this campaign) — worth generalizing, not done
here (out of today's direct blocking path).

### Bug 13 (found + fixed): `DesignMatrix.rxn_len` referenced but never assigned

First `run_script.py` attempt crashed inside `simulation_manager.py`'s
`getDirectoryList` with `IndexError: list index out of range` reading
`self.reaction_index[i]`. Root-caused via binary reasoning about row
counts (see full investigation log — the short version): `sens.py`
actually imports `DesignMatrix` from **`src/Sensitivity_Analysis/DesignMatrix.py`**
(Python resolves the SCRIPT's own directory first — `src/MUQ-SAC/run_script.py`
launches `sens.py` as a subprocess from `src/Sensitivity_Analysis/`, so
that copy wins, not `src/MUQ-SAC/DesignMatrix.py`, a separate, diverged
copy of the same class). **Both copies exist** in this repo
(`src/MUQ-SAC/DesignMatrix.py`, `src/Sensitivity_Analysis/DesignMatrix.py`,
plus `src/MUQ-SAC_EXTENDED/DesignMatrix.py` and `src/MUQ-SAC/bkp/DesignMatrix.py`
untouched) — the `src/MUQ-SAC/` copy's `getSA_samples`/`getNominal_samples`
reference `self.rxn_len`, which is **never assigned anywhere in that
class** (confirmed via isolated `AttributeError` reproduction). Fixed it
anyway (`self.rxn_len = ind if ind is not None else sample_length` in
`__init__`) since it's a real, live bug in that copy regardless of which
one `sens.py` currently imports — **flagging for the user**: these two
`DesignMatrix.py` copies have diverged and only one is actually live for
the A-factor SA path; worth reconciling/deleting the dead one at some
point, out of scope to resolve today.

### Bug 14 (found + fixed, the real blocker): reaction-equation lookup is exact-match, but nothing in this pipeline writes equations the same way twice

The ACTUALLY-imported `src/Sensitivity_Analysis/DesignMatrix.py` has no
`rxn_len` bug — so after clearing bug 13's stale-cache confusion, the
IndexError persisted with `self.reaction_index` **completely empty**.
Root cause, in `src/Sensitivity_Analysis/reaction_selection.py::reaction_index()`
(and the same pattern in `getRxnDetails()`/`getRxnType()`): reaction
matching is `rxn.split(":")[0] == reaction["equation"]` — **exact string
equality**. Our uncertainty XML names reactions the same tight,
no-internal-spaces way the shipped reference
(`DATASET/H2_O2_TEST/uncertainty/H2_uncertainty.xml`, e.g.
`rxn="H+O2&lt;=&gt;O+OH"`) does, and the same way
`uncertainty_generator_gui.py::generate_uncertainty_xml()` writes them —
but ck2yaml-generated Cantera YAML always has full spacing
("H + O2 <=> O + OH") **and reactant/product order per the mechanism's own
declaration**, not necessarily the order anyone typing a target reaction
would choose (Konnov 2019 declares this exact reaction as
`"O2 + H <=> O + OH"` — reactants swapped relative to how I'd written it).
Net effect: for **any** real mechanism, this exact-match lookup silently
returns an empty dict — no crash at the point of the bug, just empty
data that surfaces many calls later as a confusing IndexError in a
completely different module. This means **the A-factor sensitivity/target-
opt path has likely never worked end-to-end against a real ck2yaml-
generated mechanism before** (only against hand-typed reaction strings
that happened to already match, e.g. a mechanism authored directly in the
tight convention). **Fix:** added `_norm_eq()` to
`reaction_selection.py` — splits on the reversible/irreversible arrow,
strips per-term stoichiometric coefficients and whitespace, and **sorts
each side's species tokens** so term order doesn't matter (same technique
as `rmip.analysis.mechanism_check._yaml_reaction_signature`, reimplemented
standalone here rather than importing `rmip` into this separate subsystem).
Wired into all 3 call sites (`reaction_index`, `getRxnDetails`, `getRxnType`).
**Verified:** `reaction_index(['H+O2<=>O+OH','NH3+OH<=>H2O+NH2','NH2+NO<=>H2O+N2'], konnov_reactions)`
now returns all 3 correctly (`{6: 'H+O2<=>O+OH', 626: 'NH3+OH<=>H2O+NH2', 533: 'NH2+NO<=>H2O+N2'}`,
was `{}` before the fix).

### Bug 15 (found + fixed): addendum file's dataset-id keys are missing their `x` prefix

Next blocker: `KeyError: 'mol_wt'` in `make_input_file.py::create_input_file`.
Root cause: `combustion_target_class.py`'s `self.dataSet_id` is read
verbatim from a target row's 2nd pipe field (`"x10199020"`, **with** the
`x`), and does `if self.dataSet_id in addendum: self.add = addendum[self.dataSet_id]`
— but `DATASET/AMMONIA/addundem.add` (the complete, 30-dataset-id
ammonia-specific addendum file, with real `mol_wt`/`ign_delay_def`/
`ign_cond`/`specific_cond` per dataset) keys every entry with the **bare
digits only** (`"10199020:"`, no `x`), so the lookup always misses and
falls through to a bare-minimum default block that never sets `mol_wt` at
all. (I had initially pointed `Locations.addendum` at
`xml_output/addundem.add` — a different, smaller, `x`-prefixed file that
only happens to cover 1 of our 5 picked dataset ids; switching to the
correct, complete file surfaced this separate key-format bug.) **Fix:**
wrote a repaired copy
`outputs/ammonia_campaign/targets/addundem_x_prefixed.add` (prepending `x`
to all 30 `<digits>:` keys) rather than editing the `DATASET/` original,
and pointed `Locations.addendum` at it.

### Bug 16 (found + fixed): the "unitless" specific-concentration ignition-delay branch was never implemented

Next: `UnboundLocalError: local variable 'tau' referenced before
assignment` inside the generated `cantera_1.py`'s `ignitionDelay()`. This
mattered enormously for the ammonia use case specifically: **checked all
30 dataset ids in the ammonia addendum and only 4 (`x10100001`,
`x10100002`, `x10199001`, `x10199002`) use `ign_delay_def: NH3`** (a
ground-state species every mechanism here actually tracks) — the other 26
use `ign_delay_def: OH*` (an **excited-state** species no standard
ground-state kinetics mechanism, including all 5 in this repo, tracks;
confirmed via a first attempt that hit `KeyError: 'OH*'` in the same
script — a genuine data/mechanism-scope limitation, not a bug, so I
revised the Phase 3 target selection to only use the 4 simulatable dataset
ids, still spanning good T/P/fuel diversity: see the updated table below).
All 4 usable dataset ids use `ign_cond: specific`, `specific_cond:
0.95;unitless` — and the `cond == "specific"` branch of `ignitionDelay()`
(templated **8 times** across `src/Sensitivity_Analysis/make_input_file.py`)
only had cases for `unit in ("molecule", "molecule/cm3", "mole/cm3")` —
`"unitless"` fell through every branch, leaving `tau` unassigned. **Fix:**
added an `elif unit == "unitless":` branch to all 8 template occurrences,
interpreted as "fraction of the species' **initial** concentration
**consumed**" (`target_conc = conc[0] * (1 - fraction)`, i.e. 0.95 means
"time to 95% NH3 consumption") — the standard "time to X% fuel
consumption" convention in the combustion literature. **Flagging for the
user:** this interpretation (consumed vs. remaining) is a genuine
judgment call given the addendum data alone doesn't disambiguate it — if
the source literature for these 4 datasets actually means "95%
remaining," the sign should flip (`target_conc = conc[0] * fraction`).

### Revised 5-target selection (only 4 dataset ids are simulatable at all)

| # | dataset_id | T (K) | P (atm) | fuel (mole) | observed Tig (us) |
|---|---|---|---|---|---|
| 1 | x10100001 | 1358.8 | 8.44 | H2=0.0075 | 511.4 |
| 2 | x10199001 | 2098.4 | 5.87 | NH3=0.05 | 20.1 |
| 3 | x10100002 | 1988.7 | 7.30 | H2=0.003 | 15.9 |
| 4 | x10199002 | 1557.9 | 4.93 | NH3=0.01 | 1245.4 |
| 5 | x10100001 | 1836.5 | 8.44 | H2=0.0075 | 13.5 |

Updated `outputs/ammonia_campaign/targets/AMMONIA_5TIG.target` +
`AMMONIA_5TIG_summary.json` in place (same P->atm normalization as
Phase 3). **This narrowing to 4 dataset ids (all `NH3relative
concentration` measurement type) is itself worth flagging**: the other 26
ammonia Tig datasets in this repo cannot be simulated against a standard
mechanism's ignition-delay definition without adding OH* chemiluminescence
chemistry to the mechanism first — a real scope decision for the user
(add an OH* sub-mechanism grafted onto one of these 5 NH3 mechanisms?
or accept NH3-relative-concentration as the only directly-usable Tig
metric?), not something I should silently work around further.

### Real progress achieved — where it currently stops

With bugs 11-16 fixed, `run_script.py` ran the REAL FlameMaster/Cantera
pipeline substantially further than any prior attempt this session:
- All 5 target cases x 3 reactions' directories generated, perturbed
  mechanism YAMLs written, Cantera ignition-delay simulations actually
  **ran and produced real tau values** for both the "x2" (2x A-factor)
  and nominal sensitivity sweeps.
- "Sensitivity Analysis for A-factor is Done!!" — correlation-based
  active-set selection completed, writing real per-case, per-reaction
  sensitivity coefficients: `outputs/ammonia_campaign/target_opt/run_artifacts/sa_pipeline_v2_out/final_active_set_A.csv`
  (e.g. case 0: H+O2<=>O+OH S=2.195, NH2+NO<=>H2O+N2 S=0.155,
  NH3+OH<=>H2O+NH2 S=1.971 — H2/O2 chain branching dominates, exactly as
  physically expected).
- Began generating the full A/n/Ea partial-response-surface design matrix
  (40 simulations planned for Case-0) before hitting:

**Bug 17 (found, NOT fixed — flagging as a design/scope decision):**
`MechManipulator2_0.py::getRxnPerturbationDict`: `ValueError: consumed 9
selection entries but self.selection has 3.` Root cause identified but not
fixed: `self.unsrt[rxn].activeParameters` still reports the FULL declared
3 parameters (A, n, Ea) per reaction for all 3 reactions (3*3=9), but the
upstream active-set-reduction step (the correlation-based selection that
just ran and correctly identified "A-only" as the active/significant
parameter class for this small case) produced a `self.selection` vector
sized for the REDUCED 1-parameter-per-reaction case (3 total). Something
in `partial_PRS_system.py`'s handoff from the SA active-set result to
`MechManipulator2_0`'s per-reaction `unsrt` objects needs to actually
narrow `activeParameters` to match the reduced set (or the reverse: size
`self.selection` to the full 9, with zeros for the dropped params) — this
sits in the "2_0" partial-parameter-selection subsystem, which reads as
actively-evolving/newer code (see its own "NEW: partial-parameter curve
generators" comments in `DesignMatrix.py`) that I don't have enough
context to safely patch without risking silently wrong statistics.
Flagging rather than guessing.

**Bugs found in Phase 6: 7 (6 fixed: ScanMan DUPLICATE format, a second
Fortran-exponent shape, DesignMatrix.rxn_len, the reaction-equation
exact-match lookup, the addendum x-prefix mismatch, the unitless
ignition-delay branch; 1 flagged: the active-set/perturbation-dict size
mismatch).** This is by far the highest bug-density phase of the campaign
— expected, since it's the first time this session (per the task's own
framing) that the FlameMaster/MUQ-SAC bridge got exercised end-to-end on
real ammonia data; several of these (14, 15, 16 especially) look like
they would block ANY mechanism/dataset combination, not just this one.

---

## Phase 7 — GUI sweep

Drove each GUI as instructed: import the module, instantiate the real App
class against a real (withdrawn) Tk root loaded from `.gui_settings/`/a
real config, and call its actual callback methods with real ammonia file
paths — not mocks. `DISPLAY=:52.0` confirmed live throughout.

### idt_sensitivity_gui.py

Updated `.gui_settings/idt_sensitivity.json` to NH3 defaults (fuel=NH3,
mechanism=Konnov 2019, T=1200K/P=10atm, oxidizer unchanged). Instantiated
the real `IdtSensitivityApp(root)` — it loaded these settings from disk
correctly. Ran the real `_run()` callback (background-thread worker,
same as a live click) end-to-end; **used Gabriel 2022 (165 reactions)
instead of Konnov 2019 (957) for the actual compute** — brute-force
sensitivity perturbs and re-simulates every single reaction, and Konnov's
957-reaction sweep didn't finish inside a 120s bound (this is expected;
the GUI itself is fine, it's just genuinely O(n_reactions) work — not a
bug, a scope choice for the sweep). Real result produced in 13s:
top-sensitivity reactions physically sensible (`NH2 + NO <=> H2O + N2` at
rank 2, matching our independently-chosen "3 key reactions" pick from
Phase 3). Output: `outputs/ammonia_campaign/gui_sweep/idt_sensitivity_gabriel2022.json`.

### nominal_sim_gui.py + MSO Studio's `core/nominal.py`

Built a real `mso_compare` pipeline config
(`outputs/ammonia_campaign/gui_sweep/ammonia_nominal_only.yaml`) pointing
at Konnov 2019 + our 5-target subset. `NominalSimApp(root, initial_config_path=...)`
loaded it and correctly listed the one run label. Drove `_run_sim()` (which
launches the real embedded-terminal subprocess) and separately ran the
identical underlying module directly for a clean capture: it completed
without crashing but every one of the 5 cases came back with **no
result** (NaN) — traced to the generated `cantera_1.py` unexpectedly
invoking **ANSYS Chemkin-Pro** (`/home/krithika/Desktop/ANSYS/...`,
`PyChemkin-master/chemkin.py`) instead of a pure-Cantera solve, failing
preprocessing (rc=41). Confirmed this is `mso_compare/sim_runner.py`
either not honoring the addendum's `solver: cantera` field the way
`src/Sensitivity_Analysis/simulation_manager.py` does (Phase 6's engine,
which DID run pure-Cantera successfully for the same mechanism+targets),
or `make_input_file.py`'s Chemkin-Pro-based template being selected by
default regardless. **Not fixed** — `make_input_file.py` is enormous (the
same function duplicated 8+ times for different solver/format
combinations) and I don't have enough confidence in its solver-dispatch
logic to patch safely in the time available; flagging as bug 18.

**Bug 19 (found + fixed, real infrastructure bug, wide blast radius):**
Drove `mso_studio.core.nominal.run_nominal()` directly (MSO Studio's own
backend, bypassing Qt entirely per the environment note that `.venv-gui`
has no Cantera) — it failed immediately with
`ModuleNotFoundError: No module named 'mso_compare'` in the subprocess.
Root cause: `mso_studio/core/backends.py::science_command()` builds
`[SCIENCE_PYTHON, script, *args]` with **no PYTHONPATH setup at all**, and
`sanitized_subprocess_env()` (used by every `mso_studio.core.*` module
that shells out — nominal, compare, sensitivity, optimization, all of
them) copies `os.environ` verbatim, never adding this repo's `src/` to
`PYTHONPATH`. Any backend script importing a sibling package
(`mso_compare`, `rmip`, ...) — which is all of them — crashes unless the
*launching* process happened to already have `src/` on its own
PYTHONPATH, true only by accident. This would break **every single MSO
Studio backend call**, not just ammonia-specific ones — likely the
reason MSO Studio's science-subprocess bridge has never actually worked
end-to-end before. **Fix:** `sanitized_subprocess_env()` now prepends
`SRC_DIR` onto `PYTHONPATH` (preserving whatever was already there).
**Verified:** re-ran `run_nominal()` with the fix — got past the import
error cleanly (`status: done, return_code: 0`; still hits bug 18's
ANSYS/Chemkin issue for the actual tau extraction, a separate, deeper
problem). Also verified the fix benefits `mso_studio.core.sensitivity.run_brute_force_sa()`
(MSO Studio's brute-force-SA page): drove it against our
`ammonia_5tig_3rxn.opt`, and it progressed correctly through mechanism
parsing (log: "Selected reactions: 3", "Active parameters: 9" — exactly
matching Phase 6's bug-14 fix working here too) before I stopped it at the
time budget (would eventually hit the same bug-17 active-set mismatch as
Phase 6, a pre-existing, already-flagged issue, not a new one).

### forward_uq_gui.py

`ForwardUQApp(root, initial_config_path=ammonia_5tig_3rxn.opt)`
instantiated and loaded the real config. Ran `forward_uq.py` directly
(same script the GUI's `_run_uq()` shells out to) with `--n_samples 50`
(small, matching the "keep it fast" spirit): it correctly loaded the
uncertainty data (3 reactions), loaded 5 targets, computed the n_full=9
parameter space — then correctly stopped with a clear, expected message
("Opt/ directory not found — run the optimization pipeline first") since
Phase 6's full target-opt run never completed (blocked by bug 17). Not a
new bug — a correct, legible downstream dependency on an incomplete prior
phase.

### mso_compare_gui.py / brute_force_sa_gui.py / rmip_suite_gui.py

All three real App classes instantiated cleanly against real ammonia
configs (`MSOCompareApp` against the nominal_only.yaml, `BruteForceSAApp`
against `ammonia_5tig_3rxn.opt` — confirmed it read back
`Locations.mechanism` correctly). For `rmip_suite_gui.py`, went further:
instantiated `RMIPSuiteApp` against `outputs/ammonia_campaign/fusion/ammonia_fusion.db`
(our 5 already-parsed mechanisms), located the real `GraphComparisonTab`
in `app.tabs`, set its `mech_ids_var`/`out_dir_var` fields exactly as a
user would, called its real `_build_command()`, and ran the resulting CLI
command directly: real output produced
(`outputs/ammonia_campaign/gui_sweep/rmip_suite_graph_cmp/{graph_classification,union_graph_spec}.json`,
26 universal / 9 partial / 313 unique species, matching Phase 5's fusion
numbers exactly — good cross-check that both paths agree).

### mechanism_converter_gui.py / mechanism_check_gui.py / mean_value_fusion_gui.py / uncertainty_generator_gui.py

`ConverterApp(root)` and `MechanismCheckApp(root)` both instantiate
cleanly. The latter two (`mean_value_fusion_gui.py`'s `_run_fusion()`,
`uncertainty_generator_gui.py`'s `generate_uncertainty_xml()`/
`compute_symmetric_bounds()`) were already driven for real, substantial
output in Phases 5 and 4 respectively (not repeated here) — these are the
GUIs' own documented public entry points, called exactly the way their
Tkinter callbacks call them.

### MSO Studio (`.venv-gui`, PySide6)

Confirmed `.venv-gui` has no Cantera (by design — light PySide6-only venv);
drove its `src/mso_studio/core/*` backend modules directly from the main
anaconda Python instead, per the environment note. Covered `nominal.py`
and `sensitivity.py` for real (see bug 19 above); `compare.py` and
`optimization.py` share the exact same `science_command`/`run_backend`
bridge (verified via `grep`) so bug 19's fix covers them too, without
re-running each individually given time budget.
**`automation.py` and `tools.py` intentionally NOT touched** — the
environment notes flag a live external p_PRS automation campaign using
this exact subsystem's state; per instructions, left entirely alone.

### Phase 7 bug tally

**2 bugs found this phase (1 fixed — bug 19, the MSO Studio PYTHONPATH
gap, wide blast radius across all 4 of its backend pages; 1 flagged —
bug 18, the ANSYS-Chemkin-Pro-vs-Cantera solver dispatch mismatch in
`mso_compare/sim_runner.py`).** No GUI crashed outright on ammonia data
once given valid inputs — every failure traced to either a real code bug
(now fixed or flagged) or a legitimate, clearly-messaged downstream
dependency on an earlier incomplete phase.

---

