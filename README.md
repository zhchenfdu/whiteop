## White-Op

White-Op is a research project for **LLM-assisted white-box op-amp design**.  
The core pipeline lives in `white_op/` and supports:

- behavioral-level op-amp parameter design framework
- HSPICE-based behavioral-level simulation
- Optional gmid-based transistor-level mapping via the `gmid_map/` module

---

## 1. Environment Setup

- Recommended: **conda** with **Python 3.10**

```bash
conda create -n whiteop python=3.10
conda activate whiteop
```

- Install Python dependencies from the root `requirements.txt`:

```bash
pip install -r requirements.txt
```
---

## 2. Repository Structure

At the repository root:

- `white_op/` – **core White-Op pipeline**
  - `core/` – global configuration, design constraints, result formatting
    - `config.py` – defines `PipelineConfig` and `DesignRequirements`
    - `result_formatter.py` – post-processing and (optional) GMID mapping hook
  - `p2m/` – main physical-to-mathematical analysis and optimization pipeline
  - `scripts/`
    - `run_p2m_design.py` – CLI entry for running P2M parameter design
  - `examples/` – example HSPICE behavioral netlists
  - `prompts/` – step-wise LLM prompts (text templates)
  - `run_example.sh` – example run scripts
  - `experiments/` – **auto-generated** outputs (logs, netlists, reports)

- `gmid_map/` – **GMID-based transistor-level mapping module**
  - Adapted from the schematic mapping module of [OPAMP-Generator](https://github.com/jialinlu/OPAMP-Generator)
  - Spectre-based transistor-level evaluation without further sizing for the mapped circuits

---

## 3. Quick Start (Core Pipeline)

### 3.1 Change into core directory

```bash
cd white_op
```

### 3.2 Run example script

The simplest way to run the full pipeline is:

```bash
bash run_example.sh
```

`run_example.sh` is a thin wrapper around:

```bash
python3 scripts/run_p2m_design.py \
    --netlist <HSPICE_NETLIST> \
    --gain-min <GAIN_DB_MIN> \
    --gbw-min <GBW_MHZ_MIN> \
    --pm-min <PM_DEG_MIN> \
    --pm-max <PM_DEG_MAX> \
    --power-max <POWER_uW_MAX> \
    --iterations <N_ITER> \
    --gmid-map-base <PATH_TO_GMID_MAP> \
    --hspice-path <PATH_TO_HSPICE> \
    --base-url <LLM_API_BASE_URL> \
    --api-key <LLM_API_KEY> \
    --model <LLM_MODEL_NAME>
```

You should adapt all placeholder values to your local environment.

---

## 4. Command-Line Hyperparameters

All of the following flags are accepted by `scripts/run_p2m_design.py` and wired into `PipelineConfig` and `DesignRequirements`.

### 4.1 Circuit & performance specifications

- **`--netlist`** (`str`)
  - Path to the **behavioral-level HSPICE netlist** to be analyzed.
  - Example: `examples/tcasi2000/SMC.sp`

- **`--gain-min`** (`float`, dB)
  - Minimum DC gain requirement in dB.
  - Example: `60` → require gain ≥ 60 dB.

- **`--gbw-min`** (`float`, MHz)
  - Minimum gain-bandwidth product (GBW) requirement in MHz.
  - Example: `0.5` → require GBW ≥ 0.5 MHz.

- **`--pm-min`, `--pm-max`** (`float`, degrees)
  - Allowed phase margin range in degrees.
  - Example: `--pm-min 55 --pm-max 65` → require 55° < PM < 65°.

- **`--power-max`** (`float`, μW)
  - Maximum power consumption limit in micro‑watts.
  - Example: `250` → require power ≤ 250 μW.

- **`--iterations`** (`int`)
  - Maximum number of iterations for the P2M pipeline.

> Internally, these values are also used to construct a `DesignRequirements` instance:
> - `gain_min_db`, `gbw_min_mhz`, `pm_min_deg`, `pm_max_deg`, `pm_ideal_deg`, `power_max_uw`.

### 4.2 HSPICE and simulation configuration

- **`--hspice-path`** (`str`)
  - Absolute path to the **HSPICE executable** on your machine.
  - Example:
    - `/opt/synopsys/HSPICE/T-2022.03/bin/hspice`
  - This overrides the placeholder `hspice_path` in `core/config.py`.

### 4.3 LLM / API configuration

All LLM-related parameters are funneled into `PipelineConfig` and used by the HTTP client in `p2m/pipeline.py`.

- **`--base-url`** (`str`)
  - Base URL of your OpenAI-compatible LLM endpoint.
  - Example: `http://YOUR_API_SERVER:PORT/v1`
  - Overrides `PipelineConfig.base_url`.

- **`--api-key`** (`str`)
  - API key for the above endpoint.
  - Passed as `Authorization: Bearer <api_key>` in HTTP headers.
  - **Never commit a real key to a public repository**.

- **`--model`** (`str`)
  - Name of the deployed model to use.
  - Example: `gemini-3-pro-preview`, etc.
  - Overrides `PipelineConfig.model`.

### 4.4 GMID mapping configuration

- **`--gmid-map-base`** (`str`)
  - Base directory of the `gmid_map` tool.
  - Example: `../gmid_map` (relative to `white_op/`)
  - This value is stored as `PipelineConfig.gmid_map_base` and used by `ResultFormatter` to:
    - Locate `gmid_map/main.py`
    - Locate `gmid_map/spectre_netlist_template`
    - Create and manage mapping outputs (e.g. `tl_spectre/`)
---

## 6. GMID Mapping Module (`gmid_map/`)

### 6.1 Origin and role

The `gmid_map/` folder is adapted from the **schematic mapping** module of  
[OPAMP-Generator](https://github.com/jialinlu/OPAMP-Generator), we use:

- Behavioral‑level op-amp parsing
- Transistor-level netlist generation
- Spectre-based transistor-level simulation and metric extraction

In this repository, we use `gmid_map` purely as a **post-processing and verification step**:
  1. Take the behavioral‑level design from `white_op`.
  2. Map it to transistor level using GMID LUTs.
  3. Run Spectre simulations and extract performance metrics.

### 6.2 Required external configuration

Users must configure the following paths in `gmid_map/netlist_generator.py`:

- **`model_path`**: Path to your PDK model file (e.g. `rf018.scs`)
  - Example: `"/path/to/model_path/like/rf018.scs"`
  
- **`nmos_lut_path`**: Path to NMOS LUT directory
  - Example: `'/path/to/lut/nmos2v/'`
  
- **`pmos_lut_path`**: Path to PMOS LUT directory
  - Example: `'/path/to/lut/pmos2v/'`

Additionally, users must provide:

- A working **Cadence Spectre** environment, configured via some shell script (e.g. `eda.bash`). 
  - Set the `EDA_BASH_PATH` environment variable, or modify the `eda_bash_path` in `white_op/core/result_formatter.py` (line ~801).
  - Alternatively, you can source the EDA environment manually before running the pipeline.

Please refer to the original [OPAMP-Generator README](https://github.com/jialinlu/OPAMP-Generator/blob/main/README.md) for more detailed Spectre/PDK setup instructions, as the flow is conceptually the same.

---

## 7. Where to Change Performance Specs (Important)

Currently, **performance specifications live in two places** and must be updated consistently:

1. **Code / configuration**
   - CLI arguments:
     - `--gain-min`, `--gbw-min`, `--pm-min`, `--pm-max`, `--power-max`
   - `core/config.py` → `DesignRequirements` defaults (if not overridden by CLI)

2. **Prompt templates (`white_op/prompts/`)**
   - Several Markdown prompt files verbally describe the same specs, e.g.:
     - “gain ≥ 60 dB, GBW ≥ 0.7 MHz, PM between 55° and 65°, power ≤ 250 μW”
   - When you change a spec numerically in the config/CLI, you should also:
     - Search in `prompts/` for the old values,
     - Update the text to match the new constraints.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Citation

If you use White-Op in your research, we would appreciate a citation. Preprint paper and BibTeX citation information will be provided soon.