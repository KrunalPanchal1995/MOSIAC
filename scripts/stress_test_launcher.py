#!/usr/bin/env python3
"""
Stress-test every launcher catalog entry's actual launch path.

Exercises ``mso_studio.launcher.process.build_argv`` / ``missing_prerequisite``
and ``mso_studio.core.backends.sanitized_subprocess_env`` -- the real code
the launcher itself uses -- so this validates the SAME code path a user
clicking LAUNCH exercises, not a separate ad-hoc check.

Deliberately keeps every child OFF the shared live X display (see
Test_run_23_JULY/TESTING_CONVENTIONS.md rule 1: never drive a GUI on a live
X display -- a prior session collided with another agent's window there,
and $DISPLAY is set in this environment). Tkinter children get DISPLAY
unset (matching the 2026-07-23 campaign's methodology: the well-understood,
all-imports-sound signal is failing *only* at ``root = tk.Tk()`` with
TclError, not any import/setup error). The PySide6 MSO Studio child gets
QT_QPA_PLATFORM=offscreen instead, so it can actually construct its full
window headlessly -- a strictly stronger check than the Tk approach.

Run under the anaconda interpreter (needs mso_studio.launcher, which is
Qt-free and importable there):
    python3 scripts/stress_test_launcher.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mso_studio.core.backends import sanitized_subprocess_env  # noqa: E402
from mso_studio.launcher.catalog import (  # noqa: E402
    CATALOG, RUNNER_GUI_VENV, RUNNER_INTERNAL, RUNNER_SCIENCE,
)
from mso_studio.launcher.process import build_argv, missing_prerequisite  # noqa: E402

TK_DISPLAY_ERROR = "no display name and no $DISPLAY environment variable"
_BAD_MARKERS = ("ImportError", "ModuleNotFoundError", "SyntaxError", "AttributeError")
DEFAULT_TIMEOUT_S = 8.0


def _child_env(entry) -> dict:
    env = sanitized_subprocess_env()
    if entry.runner == RUNNER_SCIENCE:
        env.pop("DISPLAY", None)
    elif entry.runner == RUNNER_GUI_VENV:
        env["QT_QPA_PLATFORM"] = "offscreen"
    return env


def stress_test_entry(entry, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    if entry.runner == RUNNER_INTERNAL:
        return {"id": entry.id, "status": "skipped", "detail": "runs in-window, not a subprocess"}

    reason = missing_prerequisite(entry)
    if reason:
        return {"id": entry.id, "status": "fail", "detail": f"prerequisite missing: {reason}"}

    argv = build_argv(entry)
    env = _child_env(entry)
    try:
        proc = subprocess.run(
            argv, cwd=str(REPO_ROOT), env=env,
            capture_output=True, text=True, timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        # A real GUI app under offscreen (MSO Studio) SHOULD still be
        # running after the window -- its event loop never exits on its
        # own -- so timeout there means success. A Tk app should die
        # almost instantly with no DISPLAY, so a timeout there is a hang.
        status = "pass" if entry.runner == RUNNER_GUI_VENV else "fail"
        detail = f"still running after {timeout_s:.0f}s (event loop alive)" \
            if status == "pass" else f"hung past {timeout_s:.0f}s -- expected instant TclError"
        return {"id": entry.id, "status": status, "detail": detail}

    stderr = proc.stderr or ""
    if entry.runner == RUNNER_SCIENCE:
        if TK_DISPLAY_ERROR in stderr:
            tb_lines = [line for line in stderr.splitlines() if line.strip()]
            offenders = [line for line in tb_lines if any(m in line for m in _BAD_MARKERS)]
            if offenders:
                return {"id": entry.id, "status": "fail", "detail": "; ".join(offenders[:3])}
            return {"id": entry.id, "status": "pass",
                     "detail": "reached tk.Tk() cleanly (no DISPLAY here by design -- expected)"}
        if proc.returncode == 0:
            return {"id": entry.id, "status": "pass", "detail": "exited 0"}
        return {"id": entry.id, "status": "fail", "detail": (stderr[-500:] or f"exit {proc.returncode}")}

    # RUNNER_GUI_VENV, exited within the timeout (didn't stay running):
    # a real GUI app entering its event loop shouldn't exit this fast.
    if proc.returncode != 0 or "Traceback" in stderr:
        return {"id": entry.id, "status": "fail", "detail": (stderr[-500:] or f"exit {proc.returncode}")}
    return {"id": entry.id, "status": "fail", "detail": f"exited 0 in <{timeout_s:.0f}s -- window closed itself?"}


def main() -> int:
    results = []
    for entry in CATALOG:
        result = stress_test_entry(entry)
        result["title"] = entry.title
        results.append(result)
        print(f"{result['status'].upper():8s} {entry.id:24s} {result['detail'][:90]}")

    out_path = REPO_ROOT / "outputs" / "launcher_stress_test.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_path}")

    failures = [r for r in results if r["status"] == "fail"]
    passed = len(results) - len(failures) - sum(1 for r in results if r["status"] == "skipped")
    total = len(results) - sum(1 for r in results if r["status"] == "skipped")
    print(f"\n{passed}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
