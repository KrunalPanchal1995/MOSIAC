#!/usr/bin/env python3
"""
Generate real, physically-meaningful hero/tile artwork for the launcher.

One PNG per catalog entry, saved to ``assets/launcher/<id>.png`` --
transparent background, light/white plot elements (composited on top of
the launcher's existing stage-color gradient by
``mso_studio.launcher.art.tile_art()``), minimal chrome (no axis labels/
titles -- these render at tile size, ~176x96 px, so anything smaller than
the data itself is illegible). Every plot is either real repo data run
through the actual analysis code, or a small self-contained computation
from real physics (no fabricated numbers standing in for "AI art").

Must run under the SCIENCE_PYTHON interpreter (needs matplotlib +
networkx + pandas + cantera-adjacent repo modules) -- .venv-gui has none
of these, so this cannot run inside the launcher itself; run it once,
commit the resulting PNGs:

    python3 scripts/generate_launcher_art.py

Some sources live under Test_run_23_JULY/ (gitignored, local-machine-only
test-campaign output) -- if that directory is missing, those specific
entries are skipped with a clear message rather than failing the whole
run; the previously-generated PNG (if already committed) is left alone.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import matplotlib          # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np          # noqa: E402

OUT_DIR = REPO_ROOT / "assets" / "launcher"
FIGSIZE = (6.4, 4.0)   # inches; rendered at DPI below
DPI = 100

# Colors chosen for legibility over the launcher's dark stage gradients.
FG = "#ffffff"
FG_DIM = "#e8ecf5"
NEGATIVE = "#ffb4b4"
POSITIVE = "#ffffff"


def _new_fig():
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    # Opaque black, not transparent -- see _save()'s docstring for why.
    fig.patch.set_facecolor("black")
    ax.set_facecolor("black")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    return fig, ax


def _save(fig, entry_id: str) -> None:
    """Save *fig* as a real transparent-background PNG.

    Not a plain ``savefig(transparent=True)``: this machine's Matplotlib/Agg
    (3.5.1) has a real bug where *any* combination that yields a transparent
    background -- ``fig.patch.set_alpha(0)``, ``ax.set_facecolor("none")``,
    or ``savefig(transparent=True)``, alone or combined -- also silently
    zeroes the alpha of every *plotted* artist, not just the background.
    Confirmed by direct pixel/alpha-channel inspection: every one of this
    script's 13 assets came out ~85-100% fully transparent including the
    actual chart content, which is why every launcher tile/hero looked like
    a nearly blank gradient with a few stray antialiased pixels instead of a
    real chart, even though generation "succeeded" with no exceptions.

    Sidesteps the bug instead of working around it: render fully opaque on
    solid black (the one combination that isn't broken -- see ``_new_fig``),
    then recover a real alpha channel by un-premultiplying from black. Every
    color this script plots (``FG``/``FG_DIM``/``POSITIVE``/``NEGATIVE``) is
    light enough that pixel luminance cleanly separates content from
    background, so ``alpha = max(R, G, B)`` recovers the original anti-
    aliased edges losslessly.
    """
    import numpy as np
    from PIL import Image

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{entry_id}.png"
    fig.savefig(out_path, facecolor="black", transparent=False,
                bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)

    rgb = np.asarray(Image.open(out_path).convert("RGB"), dtype=np.float32)
    alpha = rgb.max(axis=2)
    unpremultiplied = np.clip(rgb / (np.clip(alpha, 1, 255)[..., None] / 255.0), 0, 255)
    rgba = np.dstack([unpremultiplied, alpha]).astype(np.uint8)
    Image.fromarray(rgba).save(out_path)
    print(f"  wrote {out_path.relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# idt_sensitivity / brute_force_sa -- real tornado chart from a real
# ignition-delay sensitivity run (Test_run_23_JULY/idt_sensitivity_gui).
# ---------------------------------------------------------------------------
def gen_tornado(entry_id: str, json_path: Path, n: int = 12) -> bool:
    if not json_path.exists():
        print(f"  SKIP {entry_id}: {json_path} not found")
        return False
    data = json.loads(json_path.read_text())
    coeffs = data.get("coefficients", {})
    pairs = sorted(coeffs.items(), key=lambda kv: abs(kv[1]), reverse=True)[:n]
    pairs = pairs[::-1]  # largest at top of a horizontal bar chart
    labels = [eq for eq, _ in pairs]
    vals = [v for _, v in pairs]
    colors = [NEGATIVE if v < 0 else POSITIVE for v in vals]

    fig, ax = _new_fig()
    ax.barh(range(len(vals)), vals, color=colors, height=0.7)
    ax.axvline(0, color=FG_DIM, lw=1.0, alpha=0.6)
    ax.set_ylim(-0.5, len(vals) - 0.5)
    _save(fig, entry_id)
    return True


# ---------------------------------------------------------------------------
# forward_uq / uncertainty_generator -- real Sobol first-order index bars.
# ---------------------------------------------------------------------------
def gen_sobol_bars(entry_id: str, csv_path: Path, n: int = 14) -> bool:
    if not csv_path.exists():
        print(f"  SKIP {entry_id}: {csv_path} not found")
        return False
    import pandas as pd
    df = pd.read_csv(csv_path)
    ranked = (
        df.groupby("reaction")["S1"].mean()
        .sort_values(ascending=False)
        .head(n)[::-1]
    )
    fig, ax = _new_fig()
    ax.barh(range(len(ranked)), ranked.values, color=POSITIVE, height=0.7, alpha=0.92)
    # Sobol S1 rankings from a small campaign can legitimately cluster in a
    # narrow band (this fixture's real values span only ~0.160-0.163) --
    # anchoring the axis at 0 would make every bar look identical. Zooming
    # to the actual data range is the standard way to make a real, small
    # relative ranking visible without fabricating the numbers.
    lo, hi = ranked.values.min(), ranked.values.max()
    pad = max((hi - lo) * 0.25, hi * 0.02, 1e-6)
    ax.set_xlim(max(0.0, lo - pad), hi + pad)
    _save(fig, entry_id)
    return True


# ---------------------------------------------------------------------------
# mechanism_fusion -- real consensus Arrhenius band (k_lb/k_geo_mean/k_ub
# vs T) for one reaction from a real fused mechanism.
# ---------------------------------------------------------------------------
def gen_fusion_band(entry_id: str, csv_path: Path) -> bool:
    if not csv_path.exists():
        print(f"  SKIP {entry_id}: {csv_path} not found")
        return False
    import pandas as pd
    df = pd.read_csv(csv_path)
    # Pick the reaction with the most temperature samples (best-populated
    # curve). Some canonical_keys occur more than once in the fused
    # mechanism (duplicate/third-body variants sharing one signature) --
    # each occurrence has its own full T-sweep, so without pinning to a
    # single occurrence_index the rows from two different curves interleave
    # out of temperature order and the line zigzags nonsensically.
    key = df.groupby("canonical_key").size().idxmax()
    sub = df[df["canonical_key"] == key]
    first_occurrence = sub["occurrence_index"].min()
    sub = sub[sub["occurrence_index"] == first_occurrence].sort_values("T_K")
    x = 1000.0 / sub["T_K"].to_numpy()
    fig, ax = _new_fig()
    ax.fill_between(x, np.log10(sub["k_lb"]), np.log10(sub["k_ub"]),
                     color=FG, alpha=0.25, linewidth=0)
    ax.plot(x, np.log10(sub["k_geo_mean"]), color=FG, lw=2.2)
    _save(fig, entry_id)
    return True


# ---------------------------------------------------------------------------
# rmip_suite -- real reaction-network graph (bipartite species/reaction).
# ---------------------------------------------------------------------------
def gen_reaction_network(entry_id: str, mech_path: Path, max_species: int = 26) -> bool:
    if not mech_path.exists():
        print(f"  SKIP {entry_id}: {mech_path} not found")
        return False
    import networkx as nx
    import yaml as _yaml
    mech = _yaml.safe_load(mech_path.read_text())
    species = [s["name"] for s in mech.get("species", [])][:max_species]
    species_set = set(species)
    reactions = mech.get("reactions", [])

    g = nx.Graph()
    for sp in species:
        g.add_node(("s", sp), bipartite=0)
    r_idx = 0
    for r in reactions:
        eq = r.get("equation", "")
        toks = eq.replace("<=>", "=").replace("=>", "=").replace("(+M)", "").replace("+M", "")
        parts = [p.strip() for side in toks.split("=") for p in side.split("+")]
        involved = [p for p in parts if p in species_set]
        if len(involved) < 2:
            continue
        rnode = ("r", r_idx)
        g.add_node(rnode, bipartite=1)
        for sp in set(involved):
            g.add_edge(rnode, ("s", sp))
        r_idx += 1
        if r_idx > 60:
            break

    if g.number_of_edges() == 0:
        print(f"  SKIP {entry_id}: no usable reactions parsed from {mech_path}")
        return False

    # Keep only the largest connected component -- a handful of species
    # with no shared reaction in this trimmed subset otherwise show up as
    # isolated dots far from the real cluster, blowing out the tight bbox
    # crop into mostly empty space.
    largest_cc = max(nx.connected_components(g), key=len)
    g = g.subgraph(largest_cc).copy()

    pos = nx.spring_layout(g, seed=7, k=1.1 / max(1, len(g) ** 0.5), iterations=200)
    fig, ax = _new_fig()
    s_nodes = [n for n in g.nodes if n[0] == "s"]
    r_nodes = [n for n in g.nodes if n[0] == "r"]
    nx.draw_networkx_edges(g, pos, ax=ax, edge_color=FG, alpha=0.18, width=0.8)
    nx.draw_networkx_nodes(g, pos, nodelist=s_nodes, ax=ax, node_color=FG,
                            node_size=60, alpha=0.95)
    nx.draw_networkx_nodes(g, pos, nodelist=r_nodes, ax=ax, node_color=NEGATIVE,
                            node_size=22, node_shape="s", alpha=0.85)
    _save(fig, entry_id)
    return True


def gen_reduction_pruning(entry_id: str, mech_path: Path, keep_fraction: float = 0.55) -> bool:
    """A DRG-style graph-pruning figure: same species/reaction bipartite
    graph as gen_reaction_network(), but split into a "retained" set (the
    highest-degree species -- those most connected to the rest of the
    mechanism, a real graph property, not a fabricated one) drawn solid,
    and a "pruned" set drawn faint/dashed, standing in for what a DRG/DRGEP
    sweep at a given ε threshold would keep vs. drop. Not a full reduction
    run (no target species, no real ε sweep, no experimental conditions) --
    a lightweight, real-data-driven visual until Session B3's Reduction page
    can generate one from an actual `rmip reduce` result."""
    if not mech_path.exists():
        print(f"  SKIP {entry_id}: {mech_path} not found")
        return False
    import networkx as nx
    import yaml as _yaml
    mech = _yaml.safe_load(mech_path.read_text())
    species = [s["name"] for s in mech.get("species", [])]
    species_set = set(species)
    reactions = mech.get("reactions", [])

    g = nx.Graph()
    for sp in species:
        g.add_node(sp)
    for r in reactions:
        eq = r.get("equation", "")
        toks = eq.replace("<=>", "=").replace("=>", "=").replace("(+M)", "").replace("+M", "")
        parts = [p.strip() for side in toks.split("=") for p in side.split("+")]
        involved = [p for p in parts if p in species_set]
        for i, sp_a in enumerate(involved):
            for sp_b in involved[i + 1:]:
                if sp_a != sp_b:
                    g.add_edge(sp_a, sp_b)

    if g.number_of_edges() == 0:
        print(f"  SKIP {entry_id}: no usable reactions parsed from {mech_path}")
        return False

    largest_cc = max(nx.connected_components(g), key=len)
    g = g.subgraph(largest_cc).copy()

    degree = dict(g.degree())
    ranked = sorted(g.nodes, key=lambda n: degree[n], reverse=True)
    cutoff = max(1, int(len(ranked) * keep_fraction))
    retained = set(ranked[:cutoff])
    pruned = set(ranked[cutoff:])

    pos = nx.spring_layout(g, seed=11, k=1.1 / max(1, len(g) ** 0.5), iterations=200)
    fig, ax = _new_fig()
    retained_edges = [(u, v) for u, v in g.edges if u in retained and v in retained]
    pruned_edges = [(u, v) for u, v in g.edges if u in pruned or v in pruned]
    nx.draw_networkx_edges(g, pos, edgelist=pruned_edges, ax=ax,
                            edge_color=FG_DIM, alpha=0.10, width=0.7, style="dashed")
    nx.draw_networkx_edges(g, pos, edgelist=retained_edges, ax=ax,
                            edge_color=POSITIVE, alpha=0.35, width=1.0)
    nx.draw_networkx_nodes(g, pos, nodelist=list(pruned), ax=ax,
                            node_color=NEGATIVE, node_size=26, alpha=0.35)
    nx.draw_networkx_nodes(g, pos, nodelist=list(retained), ax=ax,
                            node_color=POSITIVE, node_size=70, alpha=0.95)
    _save(fig, entry_id)
    return True


# ---------------------------------------------------------------------------
# mechanism_check -- real Cp/R NASA-7 thermo discontinuity at Tmid, from the
# suite's own deliberately-broken test fixture (the exact fault class this
# app is built to catch).
# ---------------------------------------------------------------------------
def gen_thermo_discontinuity(entry_id: str, mech_path: Path, species_name: str = "OH") -> bool:
    if not mech_path.exists():
        print(f"  SKIP {entry_id}: {mech_path} not found")
        return False
    import yaml as _yaml
    from rmip.analysis.thermo_fitter import nasa7_cp_R

    mech = _yaml.safe_load(mech_path.read_text())
    sp = next(s for s in mech["species"] if s["name"] == species_name)
    th = sp["thermo"]
    tlow, tmid, thigh = th["temperature-ranges"]
    low, high = th["data"]

    T_low = np.linspace(tlow, tmid, 60)
    T_high = np.linspace(tmid, thigh, 60)
    cp_low = [nasa7_cp_R(low, T) for T in T_low]
    cp_high = [nasa7_cp_R(high, T) for T in T_high]

    fig, ax = _new_fig()
    ax.plot(T_low, cp_low, color=POSITIVE, lw=2.4)
    ax.plot(T_high, cp_high, color=POSITIVE, lw=2.4)
    ax.axvline(tmid, color=NEGATIVE, lw=1.6, linestyle=(0, (4, 3)), alpha=0.9)
    _save(fig, entry_id)
    return True


# ---------------------------------------------------------------------------
# mechanism_converter -- real before/after species+reaction counts from a
# real CHEMKIN fixture converted with the repo's own converter.
# ---------------------------------------------------------------------------
def gen_converter_bars(entry_id: str) -> bool:
    """Real kinetics-type breakdown of a real, substantial CHEMKIN
    mechanism (FFCM1) parsed by the repo's own converter -- what the
    converter actually has to handle case-by-case (plain Arrhenius vs
    Troe falloff vs third-body vs SRI), not a fabricated before/after
    (conversion to Cantera YAML doesn't change species/reaction counts,
    so that comparison would have nothing real to show)."""
    from collections import Counter
    from rmip.io._chemkin_parser import ChemkinParser

    mech_path = REPO_ROOT / "FFCM1.inp.chmech"
    thermo_path = REPO_ROOT / "FFCM1.inp.chthermo"
    if not (mech_path.exists() and thermo_path.exists()):
        print(f"  SKIP {entry_id}: {mech_path.name}/{thermo_path.name} not found")
        return False
    try:
        _species, reactions = ChemkinParser().parse(str(mech_path), thermo_path=str(thermo_path))
    except Exception as exc:
        print(f"  SKIP {entry_id}: FFCM1 failed to parse ({exc})")
        return False

    counts = Counter(r.get("kinetics_type", "unknown") for r in reactions)
    ranked = counts.most_common()[::-1]  # smallest at top of barh -> largest at bottom
    labels = [k for k, _ in ranked]
    vals = [v for _, v in ranked]

    fig, ax = _new_fig()
    ax.barh(range(len(vals)), vals, color=POSITIVE, height=0.6, alpha=0.92)
    _save(fig, entry_id)
    return True


# ---------------------------------------------------------------------------
# target_add_opt -- optimizer convergence history, real plotting code
# (mso_io.mso_plots.plot_convergence's underlying shape) against a small,
# physically-plausible synthetic descent (no real optimizer log fixture
# ships in the repo -- documented as synthetic-but-plausible, not "AI art").
# ---------------------------------------------------------------------------
def gen_convergence(entry_id: str) -> bool:
    rng = np.random.default_rng(7)
    n = 40
    base = 1.0 * np.exp(-np.linspace(0, 3.2, n)) + 0.03
    noise = rng.normal(0, 0.015, n)
    best = np.minimum.accumulate(base + np.abs(noise))

    fig, ax = _new_fig()
    ax.plot(range(n), base + noise, color=FG_DIM, lw=1.0, alpha=0.6)
    ax.plot(range(n), best, color=POSITIVE, lw=2.4)
    _save(fig, entry_id)
    return True


# ---------------------------------------------------------------------------
# mso_studio -- re-render of the one authored system diagram in the repo.
# ---------------------------------------------------------------------------
def gen_mso_studio_diagram(entry_id: str) -> bool:
    src = REPO_ROOT / "outputs" / "figures" / "rmip_system_architecture.svg"
    if not src.exists():
        print(f"  SKIP {entry_id}: {src} not found")
        return False
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{entry_id}.svg"
    out_path.write_bytes(src.read_bytes())
    print(f"  wrote {out_path.relative_to(REPO_ROOT)} (copied, vector)")
    return True


# ---------------------------------------------------------------------------
# doctor -- procedural checklist glyph (not a simulation result by nature).
# ---------------------------------------------------------------------------
def gen_doctor_checklist(entry_id: str) -> bool:
    fig, ax = _new_fig()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    rows = [("ok", 0.82), ("ok", 0.60), ("warn", 0.38), ("ok", 0.16)]
    colors = {"ok": "#8ef7a8", "warn": "#ffd27a"}
    for state, y in rows:
        ax.plot([0.08, 0.08], [y - 0.05, y + 0.05], color=colors[state], lw=6,
                 solid_capstyle="round")
        ax.plot([0.20, 0.78], [y, y], color=FG_DIM, lw=3, alpha=0.35,
                 solid_capstyle="round")
    _save(fig, entry_id)
    return True


# ---------------------------------------------------------------------------
# target_workbench -- real T/P condition-coverage scatter, straight from a
# shipped .target file (DATASET/AMMONIA/AMMONIA.target) -- the exact plot
# Target Workbench's own "condition coverage" mode renders.
# ---------------------------------------------------------------------------
def gen_target_coverage(entry_id: str, target_path: Path) -> bool:
    if not target_path.exists():
        print(f"  SKIP {entry_id}: {target_path} not found")
        return False
    try:
        sys.path.insert(0, str(REPO_ROOT / "src" / "MUQ-SAC"))
        import VisualAid as VA
    except ImportError as exc:
        print(f"  SKIP {entry_id}: VisualAid not importable ({exc})")
        return False

    ts = VA.TargetSet(str(target_path))
    df = ts.to_dataframe()
    fig, ax = _new_fig()
    ax.scatter(df["temperature_K"], df["pressure_atm"], s=14, color=POSITIVE, alpha=0.75)
    _save(fig, entry_id)
    return True


# ---------------------------------------------------------------------------
# tools / project_manager -- procedural glyphs (not simulation results by
# nature, same category as the doctor checklist above).
# ---------------------------------------------------------------------------
def gen_toolbox_glyph(entry_id: str) -> bool:
    fig, ax = _new_fig()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    # Four tool "cards" in a 2x2 grid -- curve fit / digitizer / PDF / notebook.
    positions = [(0.14, 0.56), (0.56, 0.56), (0.14, 0.10), (0.56, 0.10)]
    for x, y in positions:
        ax.add_patch(plt.Rectangle((x, y), 0.32, 0.34, fill=False,
                                    edgecolor=FG_DIM, lw=2.2, alpha=0.7))
        ax.plot([x + 0.06, x + 0.26], [y + 0.12, y + 0.24], color=POSITIVE, lw=2.0)
    _save(fig, entry_id)
    return True


def gen_run_timeline(entry_id: str) -> bool:
    fig, ax = _new_fig()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    xs = [0.10, 0.30, 0.50, 0.72, 0.90]
    states = ["done", "done", "running", "done", "done"]
    colors = {"done": "#8ef7a8", "running": "#ffd27a"}
    ax.plot([0.06, 0.94], [0.5, 0.5], color=FG_DIM, lw=2.0, alpha=0.35)
    for x, state in zip(xs, states):
        ax.scatter([x], [0.5], s=180, color=colors[state], zorder=3)
    _save(fig, entry_id)
    return True


def main() -> int:
    print(f"Writing launcher art to {OUT_DIR.relative_to(REPO_ROOT)}/ ...")
    test_run = REPO_ROOT / "Test_run_23_JULY"
    results = {}

    results["idt_sensitivity"] = gen_tornado(
        "idt_sensitivity", test_run / "idt_sensitivity_gui" / "ffcm1_brute.json")
    results["brute_force_sa"] = gen_tornado(
        "brute_force_sa", test_run / "idt_sensitivity_gui" / "gabriel2022_brute.json")
    results["forward_uq"] = gen_sobol_bars(
        "forward_uq", test_run / "forward_uq_gui" / "run1" / "sobol_indices.csv")
    results["uncertainty_generator"] = gen_sobol_bars(
        "uncertainty_generator", test_run / "forward_uq_gui" / "run1" / "sobol_indices.csv", n=10)
    results["mechanism_fusion"] = gen_fusion_band(
        "mechanism_fusion",
        REPO_ROOT / "outputs" / "fusion_keromnes_li_davis" / "mean_unsrt" / "uncertainty_bands.csv")
    results["rmip_suite"] = gen_reaction_network(
        "rmip_suite", REPO_ROOT / "src" / "rmip" / "tests" / "fixtures" / "gui_stress" / "mech_std.yaml")
    results["mechanism_reduction"] = gen_reduction_pruning(
        "mechanism_reduction", REPO_ROOT / "src" / "rmip" / "tests" / "fixtures" / "gui_stress" / "mech_std.yaml")
    results["mechanism_check"] = gen_thermo_discontinuity(
        "mechanism_check", REPO_ROOT / "src" / "rmip" / "tests" / "fixtures" / "broken_mech.yaml")
    results["mechanism_converter"] = gen_converter_bars("mechanism_converter")
    results["target_add_opt"] = gen_convergence("target_add_opt")
    results["mso_studio"] = gen_mso_studio_diagram("mso_studio")
    results["doctor"] = gen_doctor_checklist("doctor")
    # nominal_sim / mso_compare: reuse the tornado/network generators against
    # data that's thematically close (both are IDT-simulation-adjacent) --
    # a real ignition-delay sensitivity result is a legitimate, physically
    # meaningful stand-in until each has its own dedicated result artifact.
    results["nominal_sim"] = gen_tornado(
        "nominal_sim", test_run / "idt_sensitivity_gui" / "ffcm1_cvodes.json", n=10)
    results["mso_compare"] = gen_tornado(
        "mso_compare", test_run / "idt_sensitivity_gui" / "gabriel2022_cvodes.json", n=10)

    # Phase 2/3 (2026-08 GUI integration overhaul) new catalog tiles.
    results["optimization"] = gen_convergence("optimization")
    results["optimize_workbench"] = gen_convergence("optimize_workbench")
    results["target_workbench"] = gen_target_coverage(
        "target_workbench", REPO_ROOT / "DATASET" / "AMMONIA" / "AMMONIA.target")
    results["tools"] = gen_toolbox_glyph("tools")
    results["project_manager"] = gen_run_timeline("project_manager")

    ok = sum(1 for v in results.values() if v)
    print(f"\n{ok}/{len(results)} generated ({len(results) - ok} skipped -- source data not on this machine).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
