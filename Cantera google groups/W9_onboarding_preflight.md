# W9 — Onboarding: dependency preflight & task→recipe router

**Closes:** P38 (toolchain prereqs discovered by trial-and-error), P36 (users don't
know which example/command covers a task), P39-input (input-mistake nudges).
**Effort:** S · **Risk:** Low · **Depends on:** all (it's a discoverability layer).

## Problem
Lower-severity but very high-frequency friction: people don't know a prerequisite
is needed until a job fails (e.g. Gaussian before certain RMG runs), and they can't
find which of several Cantera examples/commands maps to their task (IDT sensitivity
vs reduction vs reaction-path).

## W9a — Dependency preflight (P38)
New module `src/rmip/config/preflight.py`:
- `check_environment(task) -> Report` — verifies the toolchain a given task needs is
  present and reachable **before** the job starts: Cantera version, `ck2yaml`, the
  RMG venv, optional backends (chaospy/cvxpy/SciPy), external binaries (ScanMan,
  Gaussian for RMG QM). Reports each as present/missing with the exact remediation
  (which venv, which command) — the env-isolation map made self-service.
- `rmip doctor [--task rmg|convert|uq|check]` prints the report; a green run means
  "this task will not fail on a missing prereq."

## W9b — Task→recipe router (P36)
New `src/rmip/config/recipes.py`:
- A curated `RECIPES` table mapping a plain-language task ("ignition delay
  sensitivity", "reduce a mechanism", "reaction path diagram", "check my file")
  to the exact `rmip` subcommand / example, with a one-line description.
- `rmip how-do-i "<task>"` fuzzy-matches and prints the recommended command(s) —
  directly answering the P36 "which example script?" recurring question, and tying
  in W6's IDT-sensitivity recipe.

## W9c — Input-mistake nudges (P39-input)
- Fold the cheap input-hygiene checks (duplicate library, dual-listed seed) from
  W7c into `rmip doctor`/`rmip rmg-lint` so they surface at onboarding time, not
  after a multi-hour run.

## CLI / GUI
- `rmip doctor`, `rmip how-do-i "<task>"`.
- Add a "Doctor / Recipes" pane to `launcher_gui.py` so the GUI is self-describing.

## Tests (`src/rmip/tests/test_preflight_recipes.py`)
- `check_environment` correctly reports a present vs (simulated) missing backend.
- `how-do-i "idt sensitivity"` routes to the W6 command; a few known tasks map
  deterministically.

## Acceptance
`rmip doctor --task rmg` lists every prereq with present/missing + fix; `rmip
how-do-i` answers the "which command?" question for the common tasks.

---

## DONE (shipped 2026-07-20, uncommitted)

- `rmip.config` converted module→package (git mv `config.py` →
  `config/__init__.py`; all existing `from rmip.config import …` intact).
- **W9a — `config/preflight.py`**: `check_environment(task) →
  PreflightReport`; probes the shared env (cantera/numpy/yaml/networkx/
  tkinter/ck2yaml) and every isolated backend by actually importing its
  module *inside its venv* (chaospy_gpc, cvxpy_sdp, salib_gsa), plus
  RMG env+repo, Gaussian (optional), Zero-RK binaries (optional). Each
  missing row carries the **exact remediation** — including the
  numpy/numpoly pin gotcha for the chaospy venv and the "never SALib into
  the shared env" rule. Task map: check/convert/uq/gsa/b2bdc/rmg/
  regression/reduce/gui/all; optional absences never fail a report.
  CLI: `rmip doctor [--task] [--rmg-input] [--json]` (exit 1 when not
  ready). Verified live: `--task uq` → READY (found all three venvs);
  `--task rmg` → correctly reports the missing rmg_env with the conda fix.
- **W9b — `config/recipes.py`**: 21 curated recipes (task phrase, exact
  command via the `rmip_cli.py` launcher — never `src/rmip/cli.py` —,
  one-liner, GUI app when one exists); `find_recipes` ranks by keyword
  hits + phrase hits + difflib, always answers with the closest match.
  CLI: `rmip how-do-i "<task>" [--all]`.
- **W9c** — `rmip doctor --rmg-input input.py` folds the W7c static lint
  (duplicate library, dual-listed seed, tolerance inversion) into the
  onboarding report; lint errors flip the verdict to NOT READY. Verified
  on `fixtures/rmg_input_dual.py` (all three pathologies surface).
- **GUI**: launcher_gui.py grew a "Doctor / Recipes" row → Toplevel with
  two tabs (task-picker doctor run on a worker thread; recipe search with
  Enter-to-search + show-all).
- **Tests:** `test_preflight_recipes.py` (16) — present backend reported
  with version, simulated-missing venv carries remediation + NOT READY,
  optional absence ≠ failure, every task prereq registered, dual-listed
  fixture surfaces through doctor, 8 deterministic routing cases
  (idt-sens/reduce/check/flux/preflight/regression/doctor), launcher-only
  commands, CLI smoke for both commands.

**Acceptance met:** `rmip doctor --task rmg` lists every prereq with
present/missing + fix; `rmip how-do-i` answers "which command?" for the
common tasks (incl. the W6 IDT-sensitivity recipe).
