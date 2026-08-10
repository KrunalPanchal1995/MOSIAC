# RMIP + MUQ-SAC Quick-Start

**Working directory:** repo root `/data/OPEN_CODE/PHASE-3/`  
**Python:** `/home/krithika/anaconda3/bin/python` (3.9, base conda)  
**Config file:** `target.opt` (one per project, in `DATASET/<name>/`)

---

## 0. First time — compile .so files

```bash
# Open the GUI and use tab ⑩ "Compile .so", OR run manually:

cd config_tools/parallel_native/PARALLEL_YAML_WRITER
python setup.py build_ext --inplace
cp parallel_yaml_writer*.so /data/OPEN_CODE/PHASE-3/src/MUQ-SAC/parallel_yaml_writer.so

cd ../PARALLEL_YAML_GENERATOR
python setup.py build_ext --inplace
cp shuffle*.so /data/OPEN_CODE/PHASE-3/src/MUQ-SAC/shuffle.so

cd /data/OPEN_CODE/PHASE-3
```

---

## 1. Create a new project configuration

```bash
# Open the full GUI (11 tabs)
python generate_target_opt.py

# OR start from the H2/O2 template
cp -r DATASET/H2_O2_TEST DATASET/MY_STUDY
# edit DATASET/MY_STUDY/target.opt with your file paths
```

The GUI creates all required input files:
- **target.opt** — main config (⑪ Preview tab for live YAML)
- **.target** — experimental data (⑦ Target Builder)
- **.add** — solver addendum (⑧ Addendum Builder)  
- **.xml** — reaction uncertainty factors (⑨ XML Builder)
- **.so** — compile C++ extensions (⑩ Compile .so)

---

## 2. Convert CHEMKIN mechanism to Cantera YAML (if needed)

```bash
ck2yaml --input=mech.inp --thermo=therm.dat --transport=tran.dat --permissive
# output: mech.yaml
```

---

## 3. RMIP: Parse mechanisms into DB

```bash
# CHEMKIN format (with thermo file)
python rmip_cli.py parse MECHANISM/Connaire/h2_v1b_mech.txt \
    --db DATASET/H2_O2_TEST/h2_project.db \
    --thermo MECHANISM/Connaire/h2_v1a_therm.txt

# Cantera YAML format
python rmip_cli.py parse MECHANISM/FFCM1/FFCM1.yaml \
    --db DATASET/H2_O2_TEST/h2_project.db

python rmip_cli.py parse MECHANISM/GRI3/GRI_CO.yaml \
    --db DATASET/H2_O2_TEST/h2_project.db

# Check what's loaded
python rmip_cli.py list --db DATASET/H2_O2_TEST/h2_project.db
python rmip_cli.py summary 1 --db DATASET/H2_O2_TEST/h2_project.db
```

---

## 4. RMIP: Visualize reaction network

```bash
# 2D interactive graph (opens browser)
python rmip_cli.py visualize 1 --db DATASET/H2_O2_TEST/h2_project.db

# 2D with SA edge coloring (4 bands: grey / green / orange / red)
python rmip_cli.py visualize 1 --db DATASET/H2_O2_TEST/h2_project.db \
    --sa-json outputs/sa/ffcm1_sa.json --threshold 0.1

# Side-by-side union comparison
python rmip_cli.py visualize 1 2 --union --db DATASET/H2_O2_TEST/h2_project.db

# 3D planetary layout (stacked carbon rings)
python rmip_cli.py visualize3d 1 --db DATASET/H2_O2_TEST/h2_project.db \
    --shell-gap 2.0 --layer-gap 1.0 --order alpha

# Export static HTML
python rmip_cli.py visualize3d 1 --db DATASET/H2_O2_TEST/h2_project.db \
    --export-html outputs/H2_O2_TEST/graphs/3d/mech1.html
```

---

## 5. RMIP: Compare mechanisms

```bash
# Numerical kinetics/thermo comparison
python rmip_cli.py compare --db DATASET/H2_O2_TEST/h2_project.db \
    -m 1 2 3 --out outputs/H2_O2_TEST/comparison/

# Graph-level comparison (produces union spec for fusion)
python rmip_cli.py compare-graph --db DATASET/H2_O2_TEST/h2_project.db \
    -m 1 2 3 --out outputs/H2_O2_TEST/comparison/

# Sparsity check (dead-end / orphan species)
python rmip_cli.py sparsity 1 --db DATASET/H2_O2_TEST/h2_project.db \
    --out outputs/H2_O2_TEST/sparsity/
```

---

## 6. RMIP: Fuse mechanisms

```bash
# Fuse (VERBATIM → COPY → FUSE with geometric mean A)
python rmip_cli.py fuse --db DATASET/H2_O2_TEST/h2_project.db \
    -m 1 2 3 --name "H2_fused" \
    --out outputs/H2_O2_TEST/fusion/
# → outputs/H2_O2_TEST/fusion/mso_bounds.json   (for MSOInterface)
# → outputs/H2_O2_TEST/fusion/union_spec.json

# Export fused mechanism as CHEMKIN
python rmip_cli.py export 4 --db DATASET/H2_O2_TEST/h2_project.db \
    --output outputs/H2_O2_TEST/export/h2_fused.inp

# Export as Cantera YAML
python rmip_cli.py export 4 --db DATASET/H2_O2_TEST/h2_project.db \
    --output outputs/H2_O2_TEST/export/h2_fused.yaml --format yaml
```

---

## 7. RMIP: Unified mechanism with T-dependent uncertainty bands

```bash
# Plan — classify every reaction, emit editable CSV
python rmip_cli.py unify-plan --db DATASET/H2_O2_TEST/h2_project.db \
    -m 1 2 3 --mode anchored --anchor 1 \
    --manifest outputs/H2_O2_TEST/unified/decisions.csv

# Edit decisions.csv if needed:
# Valid actions: KEEP_ANCHOR | IMPORT_SINGLE | OPTIMIZE | PICK_SOURCE | DROP
# PICK_SOURCE requires chosen_source_mech_id column to be filled.

# Build — compute per-T uncertainty bands (3σ: σ_lnk = ln(f)/3)
python rmip_cli.py unify-build --db DATASET/H2_O2_TEST/h2_project.db \
    --manifest outputs/H2_O2_TEST/unified/decisions.csv \
    --name "H2_unified" --tmin 500 --tmax 2500 --dt 20 \
    --out outputs/H2_O2_TEST/unified/

# Export unified YAML (with uncertainty metadata embedded as YAML notes)
python rmip_cli.py export 5 --db DATASET/H2_O2_TEST/h2_project.db \
    --output outputs/H2_O2_TEST/export/h2_unified.yaml --format yaml

# Find missing pathways vs contributing mechs → RMG seed JSON
python rmip_cli.py predict-missing --db DATASET/H2_O2_TEST/h2_project.db \
    --unified 5 -m 1 2 3 --out outputs/H2_O2_TEST/rmg_seed/
```

---

## 8. Sensitivity analysis

```bash
# Cantera-native SA → JSON (used for RMIP edge coloring and DRGPSA)
python rmip_cli.py sa-run MECHANISM/FFCM1/FFCM1.yaml \
    --T 1200 --P 1.0 --phi 1.0 --fuel H2 \
    --out outputs/H2_O2_TEST/sa/ffcm1_sa.json

# MUQ-SAC 1-param SA (varies A-factor only; writes sens_parameters.pkl)
python src/Sensitivity_Analysis/sens.py DATASET/H2_O2_TEST/target.opt

# MUQ-SAC 3-param SA (varies A, n, Ea simultaneously)
python src/Sensitivity_Analysis/sens_3_params.py DATASET/H2_O2_TEST/target.opt

# SA graph visualization (overlays SA results on RMIP network)
python graph_sa_run.py DATASET/H2_O2_TEST/target.opt
# → outputs/H2_O2_TEST/graphs/sensitive_subgraph.png
# → outputs/H2_O2_TEST/graphs/sensitive_reactions.csv
```

---

## 9. Mechanism reduction

```bash
# DRG sweep (fast, topology-only)
python rmip_cli.py reduce 1 --db DATASET/H2_O2_TEST/h2_project.db \
    --method DRG --target "H2,O2,H2O" --eps-max 0.5 \
    --out outputs/H2_O2_TEST/reduction/drg.json

# DRGEP (more conservative than DRG)
python rmip_cli.py reduce 1 --db DATASET/H2_O2_TEST/h2_project.db \
    --method DRGEP --target "H2,O2,H2O" --eps-max 0.3 \
    --out outputs/H2_O2_TEST/reduction/drgep.json

# DRGPSA — SA-weighted (best for SA-guided reduction)
python rmip_cli.py reduce 1 --db DATASET/H2_O2_TEST/h2_project.db \
    --method DRGPSA --target "H2,O2,H2O" \
    --sa-json outputs/H2_O2_TEST/sa/ffcm1_sa.json \
    --eps-max 0.5 --out outputs/H2_O2_TEST/reduction/drgpsa.json

# Interactive ε slider visualizer
python rmip_cli.py visualize 1 --db DATASET/H2_O2_TEST/h2_project.db \
    --reduction-json outputs/H2_O2_TEST/reduction/drg.json

# Coefficient heatmap + BFS propagation + trim animation
python rmip_cli.py reduce-viz 1 --db DATASET/H2_O2_TEST/h2_project.db \
    --reduction-json outputs/H2_O2_TEST/reduction/drg.json --mode both
```

---

## 10. MUQ-SAC optimization

```bash
# Full PRS-based optimization (reads target.opt for all settings)
python src/MUQ-SAC/run_script.py DATASET/H2_O2_TEST/target.opt

# Nominal simulation only (no optimization — checks mechanism vs experiment)
python src/MUQ-SAC/run_nominal_sim.py DATASET/H2_O2_TEST/target.opt
```

**Design_of_PRS options in target.opt:**
- `A-facto` → optimize only A-factors (fast, 1 parameter per reaction)
- `Monte-Carlo-All` → optimize A, n, Ea (full 3-parameter)
- `LHS-maximin` → Latin Hypercube sampling of A, n, Ea

---

## 11. Benchmark mechanisms vs experiment

```bash
# Load experimental CSV
python rmip_cli.py exp-load outputs/H2_O2_TEST/exp_data/h2_idt.csv \
    --db DATASET/H2_O2_TEST/h2_project.db --sim-type IDT

# Simulate + score all mechanisms
python rmip_cli.py bench --db DATASET/H2_O2_TEST/h2_project.db \
    -m 1 2 3 --dataset 1 --sim-type IDT \
    --out outputs/H2_O2_TEST/benchmarking/

# Rank by MRE/RMSE per regime (LTC/NTC/HTC)
python rmip_cli.py rank --db DATASET/H2_O2_TEST/h2_project.db \
    -m 1 2 3 --dataset 1 --sim-type IDT \
    --out outputs/H2_O2_TEST/benchmarking/ranking.json
```

---

## 12. Forward UQ

```bash
# Propagate Arrhenius uncertainty through PRS surrogates → MC + Sobol
python forward_uq.py DATASET/H2_O2_TEST/target.opt
# → outputs/H2_O2_TEST/forward_uq/histogram_Tig_dataset_001.png
# → outputs/H2_O2_TEST/forward_uq/sobol_indices.json
```

---

## 13. Run all tests

```bash
python -m pytest src/rmip/tests/ -v      # 298/298 expected
python -m pytest src/rmip/tests/test_chemkin_parser.py -v
python -m pytest src/rmip/tests/test_phase4.py -v
```

---

## Key file locations

| What | Path |
|------|------|
| Repo root | `/data/OPEN_CODE/PHASE-3/` |
| CLI launcher | `python rmip_cli.py` (always from repo root) |
| GUI | `python generate_target_opt.py` |
| H2/O2 template | `DATASET/H2_O2_TEST/target.opt` |
| MB reference | `DATASET/METHYL_BUTANOATE_2026/target.opt` |
| Mechanisms | `MECHANISM/` |
| Full spec | `CLAUDE.md` |
| Roadmap | `PLAN.md` |

---

## Live project DB (`project.db` — reference mechanisms)

| ID | Name | Species | Reactions | Format |
|----|------|---------|-----------|--------|
| 1  | GRI-3.0 | 15 | 48 | chemkin |
| 2  | Davis-2005 | 14 | 38 | chemkin |
| 3  | Keromenes-2013 | 17 | 49 | chemkin |
| 4  | Li-2015 | 14 | 37 | chemkin |
| 5  | FFCM1 | 38 | 291 | cantera_yaml |
| 6  | MB-MB2D (base) | 608 | 3984 | cantera_yaml |
| 7  | MB-MB2D Lalit-2024 | 623 | 4050 | cantera_yaml |
