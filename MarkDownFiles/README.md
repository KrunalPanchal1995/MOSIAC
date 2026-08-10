# RMIP + MUQ-SAC: Combustion Mechanism Intelligence Platform

A unified Python framework for combustion kinetic mechanism **analysis, fusion,
optimization, and uncertainty quantification**. One configuration file (`target.opt`)
drives the entire pipeline.

| Capability | Entry point | What it does |
|---|---|---|
| **GUI configuration editor** | `python generate_target_opt.py` | Create/edit `target.opt`, `.target`, `.add`, `.xml`, compile `.so` |
| **RMIP mechanism analysis** | `python rmip_cli.py <cmd>` | Parse, graph, compare, fuse, reduce, export mechanisms |
| **MUQ-SAC optimization** | `python src/MUQ-SAC/run_script.py target.opt` | PRS-based Arrhenius parameter optimization |
| **Sensitivity analysis (1-param)** | `python src/Sensitivity_Analysis/sens.py target.opt` | A-factor sensitivity sweep |
| **Sensitivity analysis (3-param)** | `python src/Sensitivity_Analysis/sens_3_params.py target.opt` | A, n, Ea sensitivity sweep |
| **SA graph visualization** | `python graph_sa_run.py target.opt` | Overlays SA results on reaction network graph |
| **Forward UQ** | `python forward_uq.py target.opt` | Monte Carlo / Sobol propagation through PRS surrogates |

---

## Repository layout

```
.
├── generate_target_opt.py      ← GUI: create target.opt + all input files + compile .so
├── rmip_cli.py                 ← RMIP CLI launcher (always run from repo root)
├── graph_sa_run.py             ← SA graph analysis driver
├── forward_uq.py               ← Forward UQ driver
├── conftest.py                 ← sys.path setup for pytest (append-only)
│
├── src/
│   ├── MUQ-SAC/                ← MUQ-SAC optimization core
│   │   ├── run_script.py           main optimization entry point
│   │   ├── run_nominal_sim.py      simulate only (no optimization)
│   │   ├── parallel_yaml_writer.so compiled C++ extension (must compile first)
│   │   └── shuffle.so              compiled C++ extension (must compile first)
│   ├── Sensitivity_Analysis/   ← A-factor and 3-parameter SA tools
│   │   ├── sens.py                 1-param SA (varies A-factor only)
│   │   └── sens_3_params.py        3-param SA (varies A, n, Ea)
│   ├── rmip/                   ← RMIP engine (15,700 lines, 38 source files)
│   │   ├── core/                   parsing, canonicalization, graph builder
│   │   ├── io/                     CHEMKIN reader/writer, Cantera reader/writer
│   │   ├── database/               SQLite schema (Phase 1–4)
│   │   ├── analysis/               comparison, fusion, reduction, sensitivity, visualization
│   │   ├── simulation/             IDT/LFS runners (Cantera), performance ranker
│   │   ├── optimization/           MSOInterface (JSON file contract)
│   │   ├── generation/             RMG interface, missing-species predictor
│   │   └── tests/                  298 tests covering all phases
│   ├── graph_sa/               ← SA pickle → RMIP graph bridge
│   ├── forward_uq/             ← Forward UQ utilities
│   └── modules/ io/ …          ← MSO support modules
│
├── config_tools/
│   ├── converters_io/          ← xlx2csv, xml2csv
│   ├── data_generators/        ← uncertainty XML generator, start-profile generator
│   └── parallel_native/        ← pybind11 C++ source for .so files
│       ├── PARALLEL_YAML_WRITER/   → parallel_yaml_writer.so
│       └── PARALLEL_YAML_GENERATOR/→ shuffle.so
│
├── DATASET/
│   ├── METHYL_BUTANOATE_2026/  ← reference MB dataset (target.opt + mechanism files)
│   └── H2_O2_TEST/             ← H2/O2 test dataset (ready-to-use target.opt)
│       ├── target.opt               full configuration (copy and edit)
│       ├── targets/                 .target experimental data files
│       ├── uncertainty/             .xml uncertainty factor files
│       ├── exp_data/                experimental CSV files
│       ├── graphs/, comparison/,    output directories (auto-created)
│       ├── fusion/, reduction/, …
│       └── export/
│
├── MECHANISM/
│   ├── Connaire/               h2_v1b_mech.txt + thermo + transport
│   ├── FFCM1/                  FFCM1.yaml
│   └── GRI3/                   GRI_CO.yaml (H2/CO submechanism)
│
├── outputs/                    ← all generated outputs (gitignored)
├── CLAUDE.md                   ← full design spec and API reference
├── QUICKSTART.md               ← copy-paste command reference
└── PLAN.md                     ← phase roadmap
```

---

## Installation

```bash
# Core dependencies
pip install networkx numpy scipy pandas pyyaml matplotlib pytest --break-system-packages

# For mechanism simulation and Cantera YAML parsing
pip install cantera --break-system-packages

# For SMILES/InChIKey resolution (optional — RMIP works without it)
conda install -c conda-forge rdkit   # or: pip install rdkit

# For pybind11 .so compilation
pip install pybind11 --break-system-packages
```

**Python 3.9** (base conda at `/home/krithika/anaconda3/bin/python`) is the reference interpreter.

---

## Step 0 — Compile shared-object files

MUQ-SAC requires two compiled `.so` files. Either use the GUI (⑩ Compile .so tab)
or run these commands once:

```bash
# parallel_yaml_writer.so
cd config_tools/parallel_native/PARALLEL_YAML_WRITER
python setup.py build_ext --inplace
cp parallel_yaml_writer*.so /data/OPEN_CODE/PHASE-3/src/MUQ-SAC/parallel_yaml_writer.so

# shuffle.so
cd config_tools/parallel_native/PARALLEL_YAML_GENERATOR
python setup.py build_ext --inplace
cp shuffle*.so /data/OPEN_CODE/PHASE-3/src/MUQ-SAC/shuffle.so
```

---

## Step 1 — Create your configuration

```bash
# Open the GUI (11 tabs — edit all settings visually)
python generate_target_opt.py

# Or start from the H2/O2 template
cp DATASET/H2_O2_TEST/target.opt my_study/target.opt
# then edit the paths
```

### What the GUI can create

| Tab | Creates |
|-----|---------|
| ① Project | `target.opt` — project name, fuel, output directories |
| ② Locations | Paths to mechanism, thermo, targets, addendum, binaries |
| ③ Mechanisms | RMIP mechanism list (CHEMKIN + Cantera YAML) |
| ④ Optimization | PRS design, objective function, GA settings |
| ⑤ RMIP Analysis | Graph, comparison, fusion, reduction, unified tree settings |
| ⑥ Forward UQ | Monte Carlo / Sobol propagation settings |
| **⑦ Target Builder** | **Generates `.target` file** — experimental data (T, P, φ, observed) |
| **⑧ Addendum Builder** | **Generates `.add` file** — per-dataset solver config (Cantera/FlameMaster) |
| **⑨ XML Builder** | **Generates `.xml` file** — reaction uncertainty factors (σ_ln k vs T) |
| **⑩ Compile .so** | **Compiles C++ extensions** — `parallel_yaml_writer.so`, `shuffle.so` |
| ⑪ Preview | Live `target.opt` YAML preview |

---

## Step 2 — Convert mechanism to YAML (if CHEMKIN format)

```bash
ck2yaml --input=mech.inp --thermo=therm.dat --transport=tran.dat --permissive
```

---

## Step 3 — Run the pipeline

### 3a. RMIP multi-mechanism analysis

```bash
# Parse mechanisms into SQLite DB
python rmip_cli.py parse MECHANISM/Connaire/h2_v1b_mech.txt \
    --db h2_project.db \
    --thermo MECHANISM/Connaire/h2_v1a_therm.txt

python rmip_cli.py parse MECHANISM/FFCM1/FFCM1.yaml --db h2_project.db

# Graph comparison (export GraphML + PNG)
python rmip_cli.py compare-graph --db h2_project.db -m 1 2 --out outputs/comparison/

# Fuse mechanisms (geometric mean A, arithmetic mean n/Ea for divergent reactions)
python rmip_cli.py fuse --db h2_project.db -m 1 2 --name "H2_fused" --out outputs/fusion/

# Unified mechanism with T-dependent uncertainty bands (3σ convention)
python rmip_cli.py unify-plan --db h2_project.db -m 1 2 \
    --mode anchored --anchor 1 --manifest decisions.csv
python rmip_cli.py unify-build --db h2_project.db \
    --manifest decisions.csv --name "H2_unified" --out outputs/unified/

# Export to YAML (with embedded uncertainty metadata)
python rmip_cli.py export 3 --db h2_project.db \
    --output outputs/export/h2_unified.yaml --format yaml
```

### 3b. Sensitivity analysis

```bash
# A-factor only (fast — 1 param per reaction)
python src/Sensitivity_Analysis/sens.py DATASET/H2_O2_TEST/target.opt

# 3-parameter A, n, Ea
python src/Sensitivity_Analysis/sens_3_params.py DATASET/H2_O2_TEST/target.opt

# Cantera-native SA (generates JSON for RMIP edge coloring)
python rmip_cli.py sa-run MECHANISM/FFCM1/FFCM1.yaml \
    --T 1200 --P 1.0 --phi 1.0 --fuel H2 --out outputs/sa/ffcm1_sa.json
```

### 3c. Mechanism reduction

```bash
python rmip_cli.py reduce 1 --db h2_project.db \
    --method DRGPSA --target "H2,O2,H2O" \
    --sa-json outputs/sa/ffcm1_sa.json --eps-max 0.5 --out outputs/reduction/
```

### 3d. MUQ-SAC optimization

```bash
python src/MUQ-SAC/run_script.py DATASET/H2_O2_TEST/target.opt
```

Outputs written to `outputs/H2_O2_TEST/` (or wherever `RMIP.*.out_dir` fields point).

### 3e. Forward UQ

```bash
python forward_uq.py DATASET/H2_O2_TEST/target.opt
# → outputs/H2_O2_TEST/forward_uq/histogram_Tig_*.png
# → outputs/H2_O2_TEST/forward_uq/sobol_indices.json
```

### 3f. SA graph analysis

```bash
python graph_sa_run.py DATASET/H2_O2_TEST/target.opt
# → outputs/H2_O2_TEST/graphs/sensitive_subgraph.png
# → outputs/H2_O2_TEST/graphs/sensitive_reactions.csv
```

---

## Conference paper workflow

For publishing a new validated mechanism from multiple literature mechanisms:

```
Step 1: Parse mechanisms → RMIP DB
Step 2: Graph-level comparison (union graph, reaction classification)
Step 3: Fuse kinetics (geometric mean A for divergent reactions)
Step 4: Unified tree → T-dependent uncertainty bands → export Cantera YAML
Step 5: Sensitivity analysis → select top-N reactions
Step 6: MUQ-SAC optimization (A-factor: Design_of_PRS=A-facto, or 3-param: Monte-Carlo-All)
Step 7: Export optimized mechanism → Cantera YAML
Step 8: Forward UQ → uncertainty bounds on IDT/LFS predictions
```

All settings for steps 2–8 live in one `target.opt` file.

---

## All output directories

Every tool writes into named subdirectories — no loose files at repo root.

| Tool | Output directory (default) |
|------|-----------------------------|
| RMIP graphs | `outputs/<project>/graphs/` |
| RMIP 3D graphs | `outputs/<project>/graphs/3d/` |
| Comparison | `outputs/<project>/comparison/` |
| Fusion | `outputs/<project>/fusion/` |
| Benchmarking | `outputs/<project>/benchmarking/` |
| Reduction | `outputs/<project>/reduction/` |
| SA analysis | `outputs/<project>/sa/` |
| Unified mechanism | `outputs/<project>/unified/` |
| Export | `outputs/<project>/export/` |
| MUQ-SAC | `outputs/<project>/` (configured in run_script.py) |
| Forward UQ | `outputs/<project>/forward_uq/` |
| SA graph | `outputs/<project>/graphs/` |

---

## Input file formats

### target.opt (master config)

Full-commented template at `DATASET/H2_O2_TEST/target.opt`.
Created and edited via GUI: `python generate_target_opt.py`.

### .target (experimental data)

Pipe-delimited format, one data point per line:
```
|dataset_001  | target -- Tig | simulation -- Isochor Homo Reactor | ...
|T -- 1200.0  | P -- 1.0 | Phi -- N/A | observed -- 100.0 | ...
```
Use **⑦ Target Builder** tab in GUI, or import a CSV.

### .add (solver addendum)

YAML keyed by dataset ID:
```yaml
dataset_001:
  solver: cantera
  ign_delay_def: OH*
  ign_cond: onset
  mol_wt: 2
```
Use **⑧ Addendum Builder** tab in GUI.

### .xml (uncertainty factors)

```xml
<uncertainty>
  <reaction rxn="H+O2&lt;=&gt;O+OH">
    <type>pressure_independent</type>
    <data_type>constant;array</data_type>
    <temp>500,750,1000,...,2500</temp>
    <unsrt>0.3,0.3,0.25,...,0.2</unsrt>
  </reaction>
</uncertainty>
```
Use **⑨ XML Builder** tab in GUI.

---

## Important: sys.path note

`src/io/` is a package literally named `io`. If `src/` is prepended to `sys.path`,
it shadows the stdlib `io` and crashes Python. All launchers in this repo **append**
`src/` to `sys.path`. Always run `python rmip_cli.py …` from the repo root, never
`cd src && python -m rmip.cli`.

---

## Tests

```bash
python -m pytest src/rmip/tests/ -v    # 298/298 expected
```
