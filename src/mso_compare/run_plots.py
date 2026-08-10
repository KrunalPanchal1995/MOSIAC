#!/usr/bin/env python
"""
run_plots.py
------------
Standalone CLI for generating IDT comparison plots from merged CSV outputs.

This script corresponds to Phase 4 of the MSO pipeline.  It reads the
merged CSV files produced by ``run_merge.py`` and generates publication-quality
PDF figures showing experimental data vs. nominal and optimised simulation results.

Each merged sub-folder (``all/``, ``nominal_s1/``, ``nominal_s2/``) is
processed independently, producing:

* **Per-φ PDF** — one figure per equivalence ratio, all pressures overlaid.
* **Combined PDF** — a multi-panel figure with one panel per φ value.

Usage
-----
Standard (both regimes, auto mode)::

    python scripts/run_plots.py --config mso_config.yaml

HTC only, all-stages mode::

    python scripts/run_plots.py --config mso_config.yaml \\
        --regime htc --mode all_stages

Regenerate only combined figures::

    python scripts/run_plots.py --config mso_config.yaml \\
        --no-per-phi

Two-threshold comparison (compare two optimisation parameter sets)::

    python scripts/run_plots.py --config mso_config.yaml \\
        --two-threshold \\
        --data-dir-set1 MERGE_OUTPUT/HTC/all \\
        --data-dir-set2 MERGE_OUTPUT_delta005/HTC/all \\
        --set1-label "delta=0.01" \\
        --set2-label "delta=0.05" \\
        --plot-dir PLOTS/HTC/threshold_comparison

Available plot modes
--------------------
  auto          — infer from CSV columns (recommended)
  nominal_only  — experimental data + nominal simulation
  nominal_vs_s1 — experimental data + nominal + Stage-1
  nominal_vs_s2 — experimental data + nominal + Stage-2
  all_stages    — experimental data + nominal + Stage-1 + Stage-2
"""

import argparse
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_SRC_DIR     = _SCRIPTS_DIR.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from mso_compare.config  import load_config
from mso_compare.plotter import plot_comparison, plot_two_threshold_comparison
from mso_compare.utils   import setup_logging

logger = setup_logging("run_plots")

# ── postprocess() -- "process the results" flag entry point ─────────────────
# Same shared CLI contract as src/MUQ-SAC/VisualAid.py's postprocess() (see
# that file's docstring for the full rationale) via mso_io.postprocess_base.
# run_plots.py is already, in effect, a post-processor (it reads merged CSVs
# produced by run_merge.py and turns them into PDFs) -- postprocess() is a
# thin wrapper that discovers phi_*/ sub-folders under an arbitrary run
# directory and calls the existing plot_comparison() on them, no
# reimplementation, plus the "always emit CSV" + --journal contract.
try:
    from mso_io.postprocess_base import (
        PostProcessResult, add_postprocess_args, default_out_dir, discover,
        formats_from_args, write_manifest, write_table,
    )
except ImportError:  # pragma: no cover
    PostProcessResult = None

import pandas as _pd


def postprocess(run_dir, out_dir=None, journal=False, csv_only=False,
                 formats=("png",), intermediate=False):
    """Regenerate mso_compare comparison plots from an existing (or
    still-running) ``run_merge.py`` output directory: any ``phi_*/`` folder
    of merged CSVs found under *run_dir*, at any depth. Never raises on
    missing files. Returns a :class:`mso_io.postprocess_base.PostProcessResult`."""
    if PostProcessResult is None:
        raise ImportError("mso_io.postprocess_base not importable -- is src/ on sys.path?")

    run_dir = str(Path(run_dir).resolve())
    out_dir = str(default_out_dir(run_dir, out_dir))
    found = discover(run_dir, {"phi_csvs": "**/phi_*/*.csv"})
    result = PostProcessResult(run_dir=run_dir, out_dir=out_dir, partial=bool(intermediate))
    figures_dir = Path(out_dir) / "figures"
    tables_dir = Path(out_dir) / "tables"

    phi_folders = sorted({p.parent for p in found["phi_csvs"]})  # the phi_*/ folders themselves
    data_dirs = sorted({p.parent for p in phi_folders})  # folders containing phi_*/ subfolders
    if not phi_folders:
        result.skipped.append(
            f"comparison plots: no phi_*/ merged-CSV folders found under {run_dir}"
            + (" (merge stage not yet complete)" if intermediate else ""))
    for data_dir in data_dirs:
        if not csv_only:
            try:
                plot_comparison(data_dir=data_dir, plot_dir=figures_dir, mode="auto")
                result.figures.extend(str(p) for p in figures_dir.rglob("*.pdf"))
            except Exception as exc:
                result.skipped.append(f"plot_comparison({data_dir}): {type(exc).__name__}: {exc}")

    for src_path in found["phi_csvs"]:
        try:
            df = _pd.read_csv(src_path)
            name = f"{src_path.parent.name}_{src_path.stem}"
            result.tables.append(write_table(df, name, tables_dir))
        except Exception as exc:
            result.skipped.append(f"{src_path}: {type(exc).__name__}: {exc}")

    if journal and result.tables:
        journal_dir = Path(out_dir) / "journal_data"
        combined = []
        for t in result.tables:
            df = _pd.read_csv(t)
            df["_source_table"] = Path(t).stem
            combined.append(df)
        if combined:
            result.journal_tables.append(
                write_table(_pd.concat(combined, ignore_index=True, sort=False),
                            "journal_all_comparisons", journal_dir))

    write_manifest(result, out_dir)
    return result


def _resolve_regime(regime: str):
    if regime == "both":
        return ["htc", "ltc"]
    if regime in ("htc", "ltc"):
        return [regime]
    raise ValueError(regime)


def _run_standard(cfg, regime: str, mode: str,
                  plot_per_phi: bool, plot_combined: bool) -> None:
    """Generate plots for all comparison sub-folders under each merge root."""
    for pfx in _resolve_regime(regime):
        merge_root = Path(getattr(cfg.merge, f"{pfx}_output_dir")).resolve()
        plot_root  = Path(getattr(cfg.plots, f"{pfx}_output_dir")).resolve()

        if not merge_root.exists():
            logger.warning(
                "Merge root not found for %s: %s  — skipping.",
                pfx.upper(), merge_root,
            )
            continue

        sub_dirs = sorted(d for d in merge_root.iterdir() if d.is_dir())
        if not sub_dirs:
            logger.warning("No comparison sub-folders in %s.", merge_root)
            continue

        for sub_dir in sub_dirs:
            out_sub = plot_root / sub_dir.name
            logger.info("Plotting %s / %s → %s", pfx.upper(), sub_dir.name, out_sub)
            plot_comparison(
                data_dir      = sub_dir,
                plot_dir      = out_sub,
                mode          = mode,
                unc_frac      = cfg.error_metrics.uncertainty_fraction,
                plot_per_phi  = plot_per_phi,
                plot_combined = plot_combined,
            )

    logger.info("✓  Plot generation complete.")


def _run_two_threshold(
    data_dir_set1: str,
    data_dir_set2: str,
    plot_dir:      str,
    set1_label:    str,
    set2_label:    str,
    unc_frac:      float,
    plot_combined: bool,
) -> None:
    """Generate two-threshold comparison plots."""
    logger.info("Two-threshold comparison:")
    logger.info("  Set-1 : %s  (%s)", data_dir_set1, set1_label)
    logger.info("  Set-2 : %s  (%s)", data_dir_set2, set2_label)
    logger.info("  Output: %s",        plot_dir)

    plot_two_threshold_comparison(
        data_dir_set1 = Path(data_dir_set1),
        data_dir_set2 = Path(data_dir_set2),
        plot_dir      = Path(plot_dir),
        set1_label    = set1_label,
        set2_label    = set2_label,
        unc_frac      = unc_frac,
        plot_combined = plot_combined,
    )
    logger.info("✓  Two-threshold plot complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="run_plots.py",
        description="Generate IDT comparison plots from merged CSV outputs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Standard-mode arguments
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to the YAML pipeline config file.",
    )
    parser.add_argument(
        "--regime",
        choices=["htc", "ltc", "both"],
        default="both",
        help="Which regime to plot (default: both).",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "nominal_only", "nominal_vs_s1", "nominal_vs_s2", "all_stages"],
        default=None,
        help="Plot mode (default: from config, or 'auto').",
    )
    parser.add_argument(
        "--no-per-phi",
        action="store_true",
        help="Skip per-φ PDFs (generate only the combined figure).",
    )
    parser.add_argument(
        "--no-combined",
        action="store_true",
        help="Skip the combined multi-panel PDF.",
    )
    parser.add_argument(
        "--unc-frac",
        type=float,
        default=None,
        help="Uncertainty fraction σ/obs (e.g. 0.10 for 10 %%).  "
             "Default: from config.",
    )

    # Two-threshold mode
    tt_group = parser.add_argument_group("Two-threshold comparison")
    tt_group.add_argument(
        "--two-threshold",
        action="store_true",
        help="Run two-threshold comparison mode.",
    )
    tt_group.add_argument(
        "--data-dir-set1",
        type=str,
        metavar="DIR",
        help="Merged data directory for parameter set 1.",
    )
    tt_group.add_argument(
        "--data-dir-set2",
        type=str,
        metavar="DIR",
        help="Merged data directory for parameter set 2.",
    )
    tt_group.add_argument(
        "--set1-label",
        type=str,
        default="Set-1",
        help="Display label for set 1.",
    )
    tt_group.add_argument(
        "--set2-label",
        type=str,
        default="Set-2",
        help="Display label for set 2.",
    )
    tt_group.add_argument(
        "--plot-dir",
        type=str,
        default="./PLOTS/two_threshold",
        help="Output directory for two-threshold plots.",
    )

    if PostProcessResult is not None:
        add_postprocess_args(parser)

    args = parser.parse_args()

    # ── Post-process mode (arbitrary run directory, no --config needed) ─────
    if getattr(args, "postprocess", None):
        result = postprocess(
            args.postprocess, out_dir=args.out, journal=args.journal,
            csv_only=args.csv_only, formats=formats_from_args(args),
            intermediate=args.intermediate,
        )
        print(f"[run_plots.postprocess] {len(result.figures)} figure(s), "
              f"{len(result.tables)} table(s), {len(result.journal_tables)} journal table(s) "
              f"-> {result.out_dir}")
        for note in result.skipped:
            print(f"  skipped: {note}")
        return

    # ── Two-threshold mode ─────────────────────────────────────────────────
    if args.two_threshold:
        if not (args.data_dir_set1 and args.data_dir_set2):
            parser.error(
                "--two-threshold requires --data-dir-set1 and --data-dir-set2."
            )
        unc_frac = args.unc_frac or 0.10
        _run_two_threshold(
            data_dir_set1 = args.data_dir_set1,
            data_dir_set2 = args.data_dir_set2,
            plot_dir      = args.plot_dir,
            set1_label    = args.set1_label,
            set2_label    = args.set2_label,
            unc_frac      = unc_frac,
            plot_combined = not args.no_combined,
        )
        return

    # ── Standard mode ──────────────────────────────────────────────────────
    if not args.config:
        parser.error("--config is required (or use --two-threshold).")

    raw, cfg = load_config(args.config)
    mode     = args.mode     or cfg.plots.mode
    unc_frac = args.unc_frac or cfg.error_metrics.uncertainty_fraction

    _run_standard(
        cfg          = cfg,
        regime       = args.regime,
        mode         = mode,
        plot_per_phi = not args.no_per_phi,
        plot_combined= not args.no_combined,
    )


if __name__ == "__main__":
    main()
