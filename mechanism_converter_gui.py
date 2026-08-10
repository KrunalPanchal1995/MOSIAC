#!/usr/bin/env python3
"""
mechanism_converter_gui.py — Standalone GUI for CHEMKIN mechanism conversion.

Restores the monolith's `convert_mechanism_files()` capability
(generate_target_opt.py:1193) that was not migrated in the 2026-07-12 GUI
split: take a CHEMKIN mechanism (.inp/.mech + thermo + transport), and
produce any of:

  1. Cantera YAML       — via ck2yaml (transport embedded when given)
  2. FlameMaster .pre   — via ScanMan
  3. RMIP database row  — via `python rmip_cli.py parse` on the CHEMKIN
                          input (NOT the generated YAML: the Cantera-3
                          reader path currently stores no kinetics — see
                          MarkDownFiles/REVIEW_EVIDENCE_ARCHIVE.md,
                          "report.md" section, cantera_reader BLOCKER)

Hardening based on the 2026-07-13 ck2yaml stress sweep over MECHANISM/:
  - all subprocess calls use list-form argv (paths with spaces, e.g.
    "SMM3_Reaction mechanism.inp", are safe)
  - every path is resolved to absolute before use (the doubled-relative-path
    class of bug in brute_force_sa_gui/forward_uq_gui cannot occur)
  - optional pre-fix pass writes repaired copies into the output dir:
      * Fortran exponents without E ("4.8749+04" -> "4.8749E+04" — breaks
        ck2yaml on Keromens line 113 and silently corrupts rmip's parser)
      * CRLF -> LF (KONNOV_2019 thermo)
  - full ck2yaml/ScanMan stdout+stderr is always shown in the output pane
  - conversion runs on a worker thread; the window never freezes

Usage:
    python mechanism_converter_gui.py             # open GUI
    python mechanism_converter_gui.py --no-gui    # headless smoke check
"""
from __future__ import annotations

import argparse
import queue
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

_REPO = Path(__file__).resolve().parent
_SRC = str(_REPO / "src")
if _SRC not in sys.path:
    sys.path.append(_SRC)   # append, not insert: src/io shadows stdlib io

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    _HAS_TK = True
except ImportError:
    _HAS_TK = False

from gui_common.theme import PALETTE, FONTS, apply_theme
from gui_common.settings import load_settings, save_settings
from gui_common.run_status_export import add_export_button
from mso_io.run_status import RunStatusReport

_APP_NAME = "mechanism_converter"
_DEFAULT_SCANMAN = "/home/krithika/FlameMaster/Bin/bin/ScanMan"
_DEFAULT_GLOSSARY = str(_REPO / "species_smiles.csv")

# "4.8749+04" -> "4.8749E+04": a bare sign+digits run at the very end of a
# token whose ENTIRE content (aside from that sign) is numeric -- digits and
# at most one '.'. Matched per whitespace-delimited token (see
# fix_fortran_exponents below), not via lookaround: a real Fortran-exponent
# field is always its own token (e.g. "...  4.8749+04" or "4.8749+04 ... /"
# in a PLOG/LOW line), so anchoring ^...$ on the token is both necessary and
# sufficient. This deliberately CANNOT match a species/element identifier
# that happens to contain digits and a hyphen -- e.g. the real ring-locant
# species name "C2H4O1-2" (KONNOV_2019 ammonia/hydrogen mechanism) -- because
# such a token also contains letters and therefore never matches this
# digits-and-dot-only pattern. The previous char-class regex
# (r"(?<=[0-9.])([+-])(\d{1,3})(?=[\s/]|$)") matched *inside* that token
# whenever the species name stood alone on a SPECIES-block declaration line
# (trailing whitespace looks identical to a genuine missing exponent to a
# lookaround match), rewriting it to "C2H4O1E-2" and desynchronising the
# declaration from every reaction that used the un-mangled spelling --
# ck2yaml then reports the (correctly-spelled) reaction usage as an
# undeclared/malformed token. Confirmed against the real mechanism: this was
# the ONLY thing the old regex "fixed" in 128-957.inp/.dat (52 corruptions,
# 0 genuine exponent repairs) -- see
# Test_run_23_JULY/mechanism_converter_gui/new_bug_species_name_corruption/repro.txt
# and KRUNAL_JULY_23.md. The same tightening is applied to the independent
# copy in rmip/io/chemkin_preflight.py (_FORTRAN_EXP_TOKEN / _fix_fortran).
_FORTRAN_EXP_TOKEN = re.compile(r"^([+-]?(?:\d+\.\d*|\.\d+|\d+))([+-])(\d{1,3})$")


def fix_fortran_exponents(text: str) -> tuple[str, int]:
    """Insert the missing E in Fortran-style float exponents. Only touches
    lines that are not pure comments, and only whitespace-delimited tokens
    that are entirely numeric (see _FORTRAN_EXP_TOKEN) -- never a species
    name that merely contains digits and a hyphen. Returns
    (fixed_text, n_fixes)."""
    out_lines, n = [], 0
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("!"):
            out_lines.append(line)
            continue
        code, bang, comment = line.partition("!")
        # split on whitespace runs, keeping them (capturing group) so the
        # line reassembles byte-for-byte except for the tokens we rewrite
        parts = re.split(r"(\s+)", code)
        for i, part in enumerate(parts):
            fixed, k = _FORTRAN_EXP_TOKEN.subn(r"\1E\2\3", part)
            if k:
                parts[i] = fixed
                n += k
        out_lines.append("".join(parts) + bang + comment)
    return "\n".join(out_lines) + "\n", n


def preprocess_copy(src: Path, out_dir: Path, fix_exp: bool, fix_crlf: bool,
                    log) -> Path:
    """Write a repaired copy of `src` into out_dir if any fix applies;
    otherwise return `src` unchanged."""
    raw = src.read_bytes()
    changed = False
    if fix_crlf and b"\r" in raw:
        raw = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        changed = True
        log(f"  [fix] CRLF -> LF: {src.name}")
    text = raw.decode("utf-8", errors="replace")
    if fix_exp:
        text, n = fix_fortran_exponents(text)
        if n:
            changed = True
            log(f"  [fix] {n} Fortran exponent(s) repaired in {src.name}")
    if not changed:
        return src
    dst = out_dir / f"fixed_{src.name}"
    dst.write_text(text)
    return dst


def run_tool(cmd: list, log, timeout: int = 300, cwd: str | None = None) -> tuple[int, str]:
    log("$ " + " ".join(str(c) for c in cmd))
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True,
                           text=True, timeout=timeout, cwd=cwd)
    except FileNotFoundError:
        log(f"  ERROR: executable not found: {cmd[0]}")
        return 127, ""
    except subprocess.TimeoutExpired:
        log(f"  ERROR: timed out after {timeout}s")
        return 124, ""
    out = (r.stdout or "") + (r.stderr or "")
    for line in out.strip().splitlines():
        log("  " + line)
    return r.returncode, out


def convert(inp: str, thermo: str, trans: str, out_dir: str, *,
            make_yaml: bool, make_pre: bool, make_db: bool,
            scanman: str, db_path: str, glossary: str,
            permissive: bool, no_validate: bool,
            fix_exp: bool, fix_crlf: bool, log,
            opensmoke_gas: bool = False) -> list:
    """Run the selected conversions. Returns a list of error strings
    (empty == full success). All paths are resolved to absolute here."""
    errors = []
    inp_p = Path(inp).expanduser().resolve()
    if not inp_p.is_file():
        return [f"mechanism file not found: {inp_p}"]
    thermo_p = Path(thermo).expanduser().resolve() if thermo.strip() else None
    trans_p = Path(trans).expanduser().resolve() if trans.strip() else None
    for label, p in (("thermo", thermo_p), ("transport", trans_p)):
        if p is not None and not p.is_file():
            return [f"{label} file not found: {p}"]
    if thermo_p is not None and thermo_p == inp_p:
        # A self-contained CHEMKIN file (its own inline THERMO ALL block --
        # e.g. any fused/merged mechanism export, which always embeds
        # thermo this way) that ALSO gets passed as its own --thermo file
        # makes ck2yaml re-parse the same REACTIONS section a second time
        # while processing the "additional thermo" file, silently doubling
        # every reaction in the output YAML -- or, if two of the doubled
        # reactions happen to collide, crashing outright with "Undeclared
        # duplicate reaction" instead of a clean conversion. Found
        # 2026-07-17 stress-testing against the real Fused_mean_KLD
        # mechanism (exactly this self-contained shape); dummy fixtures
        # never exercised it since they always use a separate thermo file.
        # Never correct to pass the same file twice -- drop the redundant
        # thermo argument rather than forward it.
        log("  (thermo file is identical to the mechanism file -- its THERMO "
            "block is already inline; ignoring the redundant --thermo to "
            "avoid ck2yaml double-counting reactions)")
        thermo_p = None
    out_p = Path(out_dir).expanduser().resolve()
    out_p.mkdir(parents=True, exist_ok=True)

    # W3: OpenSmoke gas-only import — strip LIQUID/MATERIAL/SOLID content and
    # the reactions referencing it, logging each drop, before the normal
    # CHEMKIN pipeline (P5; needs the checkbox as explicit acknowledgement).
    if opensmoke_gas:
        try:
            from rmip.io.importers.opensmoke import OpenSmokeImporter
            if OpenSmokeImporter.sniff(str(inp_p)):
                log("\n=== OpenSmoke gas-only import (stripping condensed "
                    "content) ===")
                imp = OpenSmokeImporter()
                text = inp_p.read_text(errors="replace")
                gas_text, condensed, findings = imp.strip_to_gas(text)
                for f in findings:
                    log(f"  ▲ {f.location}: {f.message}")
                stripped = out_p / f"gasonly_{inp_p.name}"
                stripped.write_text(gas_text)
                log(f"  ✓ gas-phase subset → {stripped} "
                    f"(dropped species: {sorted(condensed) or 'none'})")
                inp_p = stripped
            else:
                log("  (OpenSmoke gas-only ticked, but no LIQUID/MATERIAL "
                    "content detected — proceeding unchanged)")
        except Exception as e:
            log(f"  (OpenSmoke strip skipped: {e})")

    # W2: line-numbered CHEMKIN preflight before ck2yaml (P2/P3/P13/P18/P35).
    # Surfaces structural problems with a line number instead of a ck2yaml
    # traceback; blocks the conversion on hard errors unless --permissive.
    pf_obj = None                     # ChemkinPreflight instance, kept for the
                                       # undeclared-species auto-fix below
    try:
        from rmip.io.chemkin_preflight import ChemkinPreflight
        pf_obj = ChemkinPreflight(
            str(inp_p),
            thermo=str(thermo_p) if thermo_p else None,
            transport=None if trans_p is None else str(trans_p),
        )
        pf = pf_obj.run()
        c = pf.counts()
        log(f"\n=== CHEMKIN preflight: {c['error']} error(s), "
            f"{c['warning']} warning(s), {c['info']} info ===")
        for f in pf.sorted_findings():
            icon = {"error": "✗", "warning": "▲", "info": "•"}.get(f.severity, "•")
            log(f"  {icon} [{f.severity}] {f.location}: {f.message}")
        if c["error"] and not permissive:
            errors.append(
                f"CHEMKIN preflight found {c['error']} structural error(s) — see "
                "the line-numbered findings above. Enable the auto-fix options, "
                "correct the file, or tick --permissive to convert anyway.")
            return errors
    except Exception as e:            # never let the linter block a valid convert
        log(f"  (preflight skipped: {e})")

    if fix_exp or fix_crlf:
        log("Preprocessing input files…")
        inp_p = preprocess_copy(inp_p, out_p, fix_exp, fix_crlf, log)
        if thermo_p is not None:
            thermo_p = preprocess_copy(thermo_p, out_p, fix_exp, fix_crlf, log)

    # W2b: auto-repair genuinely-undeclared species (KRUNAL_JULY_23.md point 2
    # -- "deploy a code that fixes this automatically without user input").
    # Reuses the ChemkinPreflight instance from the preflight scan above: its
    # SPECIES-block line numbers still apply because none of the CRLF/tab/
    # Fortran-exponent fixes insert or delete lines. Unconditional, no
    # checkbox -- safe by construction, since a token only qualifies if it
    # never matches a declared species case-insensitively, and known
    # bookkeeping placeholders (e.g. "HV") are excluded (see
    # rmip.io.chemkin_preflight._PSEUDO_SPECIES).
    if pf_obj is not None and pf_obj._undeclared_species:
        text = inp_p.read_text(encoding="utf-8", errors="replace")
        text, n_added = pf_obj._insert_missing_species(text)
        if n_added:
            dst = inp_p if inp_p.name.startswith("fixed_") \
                else out_p / f"fixed_{inp_p.name}"
            dst.write_text(text)
            inp_p = dst
            log(f"  [fix] {n_added} undeclared species added to the SPECIES "
                f"block: {', '.join(pf_obj._undeclared_species)}")

    stem = inp_p.stem.replace("fixed_", "")
    yaml_out = out_p / f"{stem}.yaml"

    if make_yaml:
        log("\n=== ck2yaml -> Cantera YAML ===")
        ck2yaml = shutil.which("ck2yaml") or "ck2yaml"
        cmd = [ck2yaml, f"--input={inp_p}"]
        if thermo_p is not None:
            cmd.append(f"--thermo={thermo_p}")
        if trans_p is not None:
            cmd.append(f"--transport={trans_p}")
        cmd.append(f"--output={yaml_out}")
        if permissive:
            cmd.append("--permissive")
        if no_validate:
            cmd.append("--no-validate")
        code, _ = run_tool(cmd, log)
        if code == 0 and yaml_out.exists():
            log(f"✓ YAML written: {yaml_out}")
        else:
            errors.append(f"ck2yaml failed (exit {code}) — full output above. "
                          "Common causes: Fortran exponents without E (enable "
                          "the auto-fix), undeclared species used in reactions "
                          "(vendor lumping comments), miswritten thermo columns, "
                          "non-standard REACTIONS-line tokens, undeclared "
                          "DUPLICATE reactions.")

    if make_pre:
        log("\n=== ScanMan -> FlameMaster .pre ===")
        scan_p = Path(scanman).expanduser()
        if scan_p.is_dir():
            scan_p = scan_p / "ScanMan"
        if not scan_p.exists():
            errors.append(f"ScanMan not found: {scanman}")
        elif thermo_p is None or trans_p is None:
            errors.append(".pre generation needs both thermo and transport files")
        else:
            pre_out = out_p / f"{stem}.pre"
            cmd = [scan_p, "-i", inp_p, "-t", thermo_p, "-m", trans_p,
                   "-f", "chemkin", "-E", "-c", "-N", "0.05",
                   "-o", pre_out]
            # ScanMan writes several intermediate/debug files (.chmech/
            # .chthermo/.chtrans/.h, named after the input file's basename)
            # to its OWN cwd regardless of -o -- without cwd=out_p here they
            # scatter into whatever directory happened to launch this GUI
            # (or a test process), not the user's chosen output directory.
            # Found while running the GUI stress-test sweep (2026-07-17).
            code, _ = run_tool(cmd, log, cwd=str(out_p))
            if code == 0 and pre_out.exists():
                log(f"✓ .pre written: {pre_out}")
            else:
                errors.append(f"ScanMan failed (exit {code}) — full output above.")

    if make_db:
        log("\n=== rmip parse -> database ===")
        if not db_path.strip():
            errors.append("DB ingest selected but no database path given")
        else:
            db_p = Path(db_path).expanduser().resolve()
            db_p.parent.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, str(_REPO / "rmip_cli.py"), "parse",
                   str(inp_p), "--db", str(db_p), "--name", stem]
            if thermo_p is not None:
                cmd += ["--thermo", str(thermo_p)]
            g = glossary.strip()
            if g and Path(g).is_file():
                cmd += ["--glossary", str(Path(g).resolve())]
            else:
                log("  (no glossary — note: compare/fuse currently require "
                    "glossary-resolved species; see review report)")
            code, _ = run_tool(cmd, log, timeout=600)
            if code == 0:
                log(f"✓ mechanism ingested into {db_p}")
            else:
                errors.append(f"rmip parse failed (exit {code}) — output above.")

    return errors


class ConverterApp:
    def __init__(self, root: "tk.Tk"):
        self.root = root
        root.title("CHEMKIN Mechanism Converter")
        apply_theme(root)
        self._q: "queue.Queue[str]" = queue.Queue()
        self._worker = None
        # last-run state, for "Export run status…" (KRUNAL_JULY_23.md pt. 1)
        self._last_vals: dict = {}
        self._last_flags: dict = {}
        self._last_status = "unknown"
        self._last_errors: list = []
        s = load_settings(_APP_NAME)

        frm = ttk.Frame(root, padding=10)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        header = ttk.Label(frm, text="CHEMKIN Mechanism Converter",
                           font=FONTS.get("heading", None))
        header.grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(frm, text="CHEMKIN .inp/.mech + thermo + transport → "
                            "Cantera YAML (ck2yaml), FlameMaster .pre (ScanMan), "
                            "and/or RMIP database.",
                  wraplength=680).grid(row=1, column=0, columnspan=3,
                                       sticky="w", pady=(0, 8))

        self._vars = {}

        def row(r, label, key, default="", browse="file"):
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w")
            v = tk.StringVar(value=s.get(key, default))
            self._vars[key] = v
            e = ttk.Entry(frm, textvariable=v)
            e.grid(row=r, column=1, sticky="ew", padx=4)
            if browse:
                def cb(v=v, browse=browse):
                    p = (filedialog.askdirectory() if browse == "dir"
                         else filedialog.askopenfilename())
                    if p:
                        v.set(p)
                ttk.Button(frm, text="Browse…", command=cb).grid(row=r, column=2)

        row(2, "Mechanism (.inp/.mech)", "inp")
        row(3, "Thermo file (optional)", "thermo")
        row(4, "Transport file (optional)", "trans")
        row(5, "Output directory", "out_dir",
            default=str(_REPO / "outputs" / "converted"), browse="dir")
        row(6, "ScanMan binary", "scanman", default=_DEFAULT_SCANMAN)
        row(7, "RMIP database (.db)", "db_path",
            default=str(_REPO / "outputs" / "project.db"))
        row(8, "Species glossary CSV", "glossary", default=_DEFAULT_GLOSSARY)

        optf = ttk.Frame(frm)
        optf.grid(row=9, column=0, columnspan=3, sticky="w", pady=6)
        self._flags = {}
        for i, (key, label, default) in enumerate([
                ("make_yaml", "Cantera YAML", True),
                ("make_pre", "FlameMaster .pre", True),
                ("make_db", "Ingest into RMIP DB", True),
                ("permissive", "--permissive", True),
                ("no_validate", "--no-validate", True),
                ("fix_exp", "Auto-fix Fortran exponents", True),
                ("fix_crlf", "Normalize CRLF", True),
                ("opensmoke_gas", "OpenSmoke: gas-only import", False)]):
            bv = tk.BooleanVar(value=bool(s.get(key, default)))
            self._flags[key] = bv
            ttk.Checkbutton(optf, text=label, variable=bv).grid(
                row=i // 4, column=i % 4, sticky="w", padx=(0, 12))

        self._run_btn = ttk.Button(frm, text="▶  Convert", command=self._run)
        self._run_btn.grid(row=10, column=0, sticky="w", pady=(4, 6))
        add_export_button(frm, self._build_run_status).grid(
            row=10, column=1, sticky="w", pady=(4, 6))
        self._status = ttk.Label(frm, text="")
        self._status.grid(row=10, column=2, sticky="w")

        self._out = tk.Text(frm, height=18, bg=PALETTE["entry_bg"],
                            fg=PALETTE["text"], wrap="none")
        self._out.grid(row=11, column=0, columnspan=3, sticky="nsew")
        frm.rowconfigure(11, weight=1)

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(100, self._drain)

    # -- worker plumbing ----------------------------------------------------
    def _log(self, msg: str):
        self._q.put(msg)

    def _drain(self):
        try:
            while True:
                line = self._q.get_nowait()
                if line.startswith("__STATUS__"):
                    ok = line.endswith("done")
                    self._status.config(
                        text="✓ Conversion finished" if ok
                        else "✗ Finished with errors — see output")
                    self._run_btn.state(["!disabled"])
                    continue
                self._out.insert("end", line + "\n")
                self._out.see("end")
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    def _on_close(self):
        if self._worker is not None and self._worker.is_alive():
            if not messagebox.askyesno(
                    "Conversion running",
                    "A conversion is still running. Quit anyway?"):
                return
        self.root.destroy()

    # -- run-status export (KRUNAL_JULY_23.md point 1) ----------------------
    def _build_run_status(self) -> RunStatusReport:
        vals, flags = self._last_vals, self._last_flags
        return RunStatusReport(
            tool="CHEMKIN Mechanism Converter",
            inputs={
                "mechanism (.inp/.mech)": vals.get("inp", ""),
                "thermo file": vals.get("thermo", ""),
                "transport file": vals.get("trans", ""),
                "ScanMan binary": vals.get("scanman", ""),
                "RMIP database (.db)": vals.get("db_path", ""),
                "species glossary CSV": vals.get("glossary", ""),
            },
            output_dir=vals.get("out_dir", ""),
            options=dict(flags),
            status=self._last_status,
            summary=self._last_errors[0] if self._last_errors else None,
            log=self._out.get("1.0", "end"),
        )

    # -- actions ------------------------------------------------------------
    def _run(self):
        if self._worker is not None and self._worker.is_alive():
            messagebox.showinfo("Busy", "A conversion is already running.")
            return
        vals = {k: v.get() for k, v in self._vars.items()}
        flags = {k: v.get() for k, v in self._flags.items()}
        if not vals["inp"].strip():
            messagebox.showerror("Missing input",
                                 "Choose a CHEMKIN mechanism file first.")
            return
        if not any((flags["make_yaml"], flags["make_pre"], flags["make_db"])):
            messagebox.showerror("Nothing to do",
                                 "Select at least one output (YAML/.pre/DB).")
            return
        save_settings(_APP_NAME, {**vals, **flags})
        self._out.delete("1.0", "end")
        self._status.config(text="Running…")
        self._run_btn.state(["disabled"])
        self._last_vals, self._last_flags = vals, flags
        self._last_status, self._last_errors = "unknown", []

        def work():
            try:
                errs = convert(
                    vals["inp"], vals["thermo"], vals["trans"], vals["out_dir"],
                    make_yaml=flags["make_yaml"], make_pre=flags["make_pre"],
                    make_db=flags["make_db"], scanman=vals["scanman"],
                    db_path=vals["db_path"], glossary=vals["glossary"],
                    permissive=flags["permissive"],
                    no_validate=flags["no_validate"],
                    fix_exp=flags["fix_exp"], fix_crlf=flags["fix_crlf"],
                    opensmoke_gas=flags.get("opensmoke_gas", False),
                    log=self._log)
            except Exception as e:            # defensive: never die silently
                errs = [f"internal error: {e!r}"]
            self._log("")
            self._last_errors = errs
            self._last_status = "failed" if errs else "success"
            if errs:
                for e in errs:
                    self._log("ERROR: " + e)
                self._q.put("__STATUS__failed")
            else:
                self._q.put("__STATUS__done")

        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--no-gui", action="store_true",
                   help="Headless smoke check: verify tool availability, exit")
    # Headless conversion mode (KRUNAL_JULY_23.md PySide6 conversion): runs the
    # SAME convert() the Tk GUI calls, so mso_studio.core.converter can shell
    # out to this script (via backends.science_command) rather than importing
    # rmip/cantera into the PySide6 venv, which never has them. All flags
    # mirror convert()'s keyword-only parameters 1:1.
    p.add_argument("--convert", action="store_true",
                   help="Headless conversion: run convert() with the flags below")
    p.add_argument("--input", help="CHEMKIN mechanism file (.inp/.mech)")
    p.add_argument("--thermo", default="", help="Thermo file (optional)")
    p.add_argument("--transport", default="", help="Transport file (optional)")
    p.add_argument("--out-dir", default="", help="Output directory")
    p.add_argument("--make-yaml", action="store_true", default=True,
                   help="Produce Cantera YAML (default on)")
    p.add_argument("--no-make-yaml", dest="make_yaml", action="store_false")
    p.add_argument("--make-pre", action="store_true", help="Produce FlameMaster .pre")
    p.add_argument("--make-db", action="store_true", help="Ingest into RMIP DB")
    p.add_argument("--scanman", default="", help="ScanMan binary path")
    p.add_argument("--db-path", default="", help="RMIP database (.db) path")
    p.add_argument("--glossary", default="", help="Species glossary CSV")
    p.add_argument("--permissive", action="store_true", help="ck2yaml --permissive")
    p.add_argument("--no-validate", action="store_true", help="ck2yaml --no-validate")
    p.add_argument("--fix-exp", action="store_true", default=True,
                   help="Auto-fix Fortran exponents (default on)")
    p.add_argument("--no-fix-exp", dest="fix_exp", action="store_false")
    p.add_argument("--fix-crlf", action="store_true", default=True,
                   help="Normalize CRLF (default on)")
    p.add_argument("--no-fix-crlf", dest="fix_crlf", action="store_false")
    p.add_argument("--opensmoke-gas", action="store_true",
                   help="OpenSmoke: gas-only import")
    args = p.parse_args()

    if args.convert:
        if not args.input:
            print("ERROR: --convert requires --input")
            return 1
        errs = convert(
            args.input, args.thermo, args.transport, args.out_dir or "outputs/converted",
            make_yaml=args.make_yaml, make_pre=args.make_pre, make_db=args.make_db,
            scanman=args.scanman, db_path=args.db_path, glossary=args.glossary,
            permissive=args.permissive, no_validate=args.no_validate,
            fix_exp=args.fix_exp, fix_crlf=args.fix_crlf,
            opensmoke_gas=args.opensmoke_gas, log=print,
        )
        if errs:
            for e in errs:
                print("ERROR: " + e)
            return 1
        return 0

    if args.no_gui or not _HAS_TK:
        ck = shutil.which("ck2yaml")
        scan = Path(_DEFAULT_SCANMAN)
        print(f"ck2yaml: {ck or 'NOT FOUND'}")
        print(f"ScanMan: {scan if scan.exists() else 'NOT FOUND at ' + str(scan)}")
        print(f"rmip_cli: {_REPO / 'rmip_cli.py'}")
        smoke = fix_fortran_exponents("K1 1.865E+25 -2.30 4.8749+04 !c\n")
        assert "4.8749E+04" in smoke[0] and smoke[1] == 1, smoke
        print("fortran-exponent fixer: OK")
        return 0
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
