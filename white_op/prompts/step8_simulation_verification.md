# Step 8: Generate Parameterized Netlist

Based on the optimization results from Step 7, extract all independent variables and generate a `.param` file usable in HSPICE simulation.

**Core Requirement**: All independent variables referenced in quotes at the end of each line in the original netlist must be defined, otherwise the HSPICE simulation will fail.

## 1. Variable Extraction

### 1.1 Intelligent Variable Name Extraction
In practice, variable names in the optimization code may not have underscores (e.g., `G1`, `Cf`), while the netlist may have underscore versions (e.g., `G_1`, `C_f`).
Therefore, we must first perform **intelligent matching** with the following rules:
- `Xdigit` or `Xletter` → `X_digit` or `X_letter` (e.g., `G1`→`G_1`, `Gf`→`G_f`)
- Of course, there are other cases, such as `XY` may also correspond to `X_Ydigit` or `X_Yletter` (e.g., `Cm` may correspond to `C_m1`)
- Please infer based on the physical meaning of variable names, match flexibly, and extrapolate accordingly.

### 1.2 Intelligent Variable Value Extraction
After successful matching, directly use the numerical values from the optimization results; no need to search for formulas or infer

### 1.3 Exception Handling
- **Formula inference**: If matching fails, check whether it can be inferred from formulas, variable relationships, or context in the optimization results.
- **Default handling**: If neither matching nor inference is possible, use reasonable default values or guessed values

## 2. Output Format Requirements
The core output of this step is the content of the netlist parameter file, enclosed between `<param>` and `</param>` tags.
Each line contains one `.param` statement, with the format: `.param parameter_name = parameter_value`; for example:
<param>
.param G_1 = 0.0100e-3
</param>

## 3. Special Notes
Before generating the `.param` file, please ensure:
- Name consistency: Variable names are exactly the same as those in the netlist (including case and underscores)
- Avoid comments: The `<param>` tags **can only contain `.param` statements**, no comments, explanatory text, blank lines, or other content
- Unit conversion: For example: mS → e-3 (e.g., 0.1 mS = 0.1e-3), pF → e-12 (e.g., 1.0 pF = 1.0e-12), kΩ → e3 (e.g., 100 kΩ = 100e3).