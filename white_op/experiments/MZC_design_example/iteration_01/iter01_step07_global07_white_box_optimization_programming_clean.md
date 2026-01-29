# Step 7: white_box_optimization_programming

**Generated Time**: 2026-01-19 03:26:01

**Iteration Count**: 1

**Content Type**: Clean Response

---

## User Prompt

```text
# Step 7: White-Box Optimization

Based on the modeling above, perform white-box optimization to solve for the optimal design variables.

## 1. Independent Variables and Ranges
We work with the original designable independent variable vector $\mathbf{{x}}$ and design range $\mathcal{{D}}_{{var}}$, including:
- Transconductance G: [1e-5, 1e-3]; e.g., G_in_1=1e-4 S;
- Gain A: [40.0, 80.0]; e.g., A_in_1=50, actual input parasitic resistance=50/G_in_1 Ohm;
- Independent resistance R: [1e1, 1e6]; e.g., R_1_out=1e5 Ohm; specifically, load R_L=10M Ohm;
- Independent capacitance C: [1e-14, 1e-11]; e.g., C_2_out = 5e-12 F; specifically, load: C_L = 10 pF.

**Special Notes**:
- Independent variables are the variables in quotes at the end of each line in the netlist, while Rprs and Cprs are intermediate variables that will be automatically calculated and do not need to be printed.
- If there are equality dependencies between independent variables (such as dependencies between Cm and Rz), do not forget to substitute and eliminate in the actual optimization problem to reduce the number of variables.
- If substitution and elimination are performed, do not forget to also print the eliminated variables when printing independent variables at the end, because we need to read all independent variables in subsequent steps.

## 2. Objective Function
We use the **hard-constraint optimization** method, directly maximizing FoM (Figure of Merit):
$$FoM = \frac{{GBW[MHz] \times C_L[pF]}}{{Power[mW]}}$$
Note that in the FoM formula, the denominator unit is mW, not μW.

## 3. Design Requirements
- **Gain**: > 60 dB
- **GBW (Gain-Bandwidth Product)**: > 0.5 MHz
- **PM (Phase Margin)**: 55° < PM < 65° (ideal PM is about 60°; too low affects stability, too high sacrifices speed)
- **Power**: < 250 uW

## 4. Solver: GEKKO/IPOPT

Use GEKKO library with IPOPT solver for nonlinear constrained optimization. Key features:
- **Automatic Differentiation**: Provides exact gradients
- **Interior Point Method**: Stable constraint handling for narrow feasible regions (e.g., PM ∈ [55°, 65°])
- **Native Transcendental Functions**: `m.atan()`, `m.sqrt()`, `m.log10()` work seamlessly

**Important**: GEKKO/IPOPT is a **local optimizer**. Different initial points converge to different solutions. Therefore, **multi-start strategy is mandatory** to increase the probability of finding the global optimum.

## 5. Code Implementation Requirements

### 5.1 Basic Requirements
- **Use GEKKO library**: With IPOPT solver (solver option 3) for nonlinear constrained optimization
- **Inherit formulas derived above**: When handling **performance metrics**, **additional constraints**, and **zeros/poles** in the code, you must use the formulas derived in Step 6, not the formulas in the example code.
- **Formula consistency verification**: Before implementing constraints, carefully verify that the mathematical operations in your code match the formulas from Step 6.
- **Code must be actually executable**: After generating the Python optimization code, do not predict specific numerical results.

### 5.2 GEKKO-Specific Syntax Rules

#### 5.2.1 Variable Naming (Critical!)
```python
# ❌ WRONG: GEKKO is case-insensitive! These are the SAME variable:
A1 = m.Var(...)
a1 = m.Var(...)  # Conflicts with A1!

# ✅ CORRECT: Use distinct names
A_stage1 = m.Var(...)
A_stage2 = m.Var(...)

# ❌ WRONG: Don't use names that conflict with GEKKO functions
abs_p2 = m.Var(...)  # 'abs' is a GEKKO function!

# ✅ CORRECT: Use alternative names
p2_magnitude = m.Var(...)
```

#### 5.2.2 Intermediate Variables (Critical!)
**All expressions involving GEKKO functions MUST be wrapped in `m.Intermediate()`**:

```python
# ❌ WRONG: Direct use of GEKKO functions
phi_p2 = m.atan(GBW_rad / p2_mag)  # This will cause errors!
PM_deg = (np.pi/2 - phi_p2) * 180/np.pi

# ✅ CORRECT: Wrap in m.Intermediate()
phi_p2 = m.Intermediate(m.atan(GBW_rad / p2_mag))
PM_rad = m.Intermediate(np.pi/2 - phi_p2)
PM_deg = m.Intermediate(PM_rad * 180 / np.pi)
```

#### 5.2.3 Supported Mathematical Functions
| Function | GEKKO Syntax | Notes |
|----------|--------------|-------|
| Square root | `m.sqrt(x)` | Must wrap in Intermediate |
| Arctangent | `m.atan(x)` | **No atan2 support!** |
| Logarithm (base 10) | `m.log10(x)` | For dB calculations |
| Natural log | `m.log(x)` | |
| Exponential | `m.exp(x)` | |
| Absolute value | `m.abs(x)` or `m.abs2(x)` | abs2 is smoother |
| Sine/Cosine | `m.sin(x)`, `m.cos(x)` | |

#### 5.2.4 Constraint Definition
GEKKO uses direct equation syntax:

```python
# Performance constraints
m.Equation(Gain_lin >= 1000)      # Gain ≥ 60 dB
m.Equation(GBW_MHz >= 0.5)        # GBW ≥ 0.5 MHz
m.Equation(Power_uW <= 250)       # Power ≤ 250 μW
m.Equation(PM_deg >= 55)          # PM lower bound
m.Equation(PM_deg <= 65)          # PM upper bound

# Physical/stability constraints from Step 6
m.Equation(G2 >= 2 * G1)          # Example: pole separation
m.Equation(wn >= 2 * GBW_rad)     # Example: non-dominant pole location
```

### 5.3 Numerical Scaling

Scaling improves convergence:

| Original Variable | Original Range | Scaled Variable | Scaled Range | Scale Factor |
|------------------|----------------|-----------------|--------------|--------------|
| G [S] | 1e-5 ~ 1e-3 | G_uS [μS] | 10 ~ 1000 | ×1e6 |
| C [F] | 1e-14 ~ 1e-11 | C_pF [pF] | 0.01 ~ 10 | ×1e12 |
| R [Ω] | 1e1 ~ 1e6 | R_kOhm [kΩ] | 0.01 ~ 1000 | ×1e-3 |

**Inside the model, convert back to SI units for calculations**:
```python
# Scaled design variables
G1_uS = m.Var(value=100, lb=10, ub=1000)

# Convert to SI for calculations
G1 = m.Intermediate(G1_uS * 1e-6)  # Now in Siemens
```

**Numerical range check**: Before writing constraints, estimate the constraint expression value:
- **SI units**: $G \times C \approx 10^{-4} \times 10^{-12} = 10^{-16}$ (TOO SMALL, will cause solver issues)
- **Scaled units**: $G_{uS} \times C_{pF} \approx 100 \times 1 = 100$ (OK, in range 1e-3 to 1e3)
- If constraint value < 1e-3, multiply by appropriate scale factor; if > 1e3, divide by scale factor

**Constraint scaling**: Constraints involving products of scaled variables (e.g., $G \times C$) must also use scaled units in the constraint expression. **Constraint expression values should be in the range 1e-3 to 1e3**. If values are <1e-10, the solver may fail to handle them correctly.

**Example - WRONG (SI units, values too small)**:
```python
# ❌ WRONG: Using SI units produces values ~1e-16, causing solver failures
m.Equation(G2 * Cm >= 10 * (G1/A1) * CL_SI)  # Value: ~1e-19, TOO SMALL!
```

**Example - CORRECT (scaled units, values reasonable)**:
```python
# ✅ CORRECT: Using scaled units produces values ~100, in acceptable range
# Constraint A: G2 * Cm > 5 * (G1/A1) * CL
# Scaled: G2_uS * Cm_pF ~ 100 * 1 = 100 (reasonable range)
m.Equation(G2_uS * Cm_pF >= 5 * (G1_uS / A1) * CL_pF)  # Value: ~100, OK!

# For constraints with C^2 (e.g., G2 * Cm^2), also use scaled units:
Cprs1_pF = m.Intermediate(G2_uS * 1e6 / wt)  # Convert parasitic C to pF
m.Equation(G2_uS * Cm_pF**2 >= 1.5 * G1_uS * CL_pF * (Cm_pF + Cprs1_pF))
# LHS_scaled = G2_uS * Cm_pF^2 ~ 100 * 1^2 = 100 (reasonable range)
```

**Key principle**: All variables in constraint expressions must use scaled units (_uS, _pF, etc.), and intermediate variables (like parasitic capacitances) must also be converted to scaled units before use in constraints.

### 5.4 Multi-Start Optimization Strategy

Since GEKKO is a local optimizer, multi-start is essential:
- Simple problems (≤5 variables): 50-100 starts
- Complex problems (>5 variables): 100-200 starts

### 5.5 Solver Settings

```python
m = GEKKO(remote=False)
m.options.SOLVER = 3      # IPOPT
m.options.MAX_ITER = 500
m.options.OTOL = 1e-6     # Objective function tolerance
m.options.RTOL = 1e-6     # Constraint tolerance
```

## 6. Output Format Requirements

**⚠️ CRITICAL: You MUST strictly follow the output format shown in the code template below.** The output format is designed for automated parsing and extraction. Any deviation may cause parsing failures.

### 6.1 Required Output Sections

Your code output must include the following sections in **exact** order:

1. **Optimization Results header**: `"============================================================"` followed by `"Optimization Results"`
2. **Multi-start statistics**: `"Multi-start: {success_count}/{n_starts} successful, Time: {t_elapsed:.2f}s"`
3. **Optimal Design Variables section**: 
   - Header: `"Optimal Design Variables:"`
   - Format: `"  G1 = {value:.6e} S"` (exactly this format with spacing and precision)
4. **Performance Metrics section**:
   - Header: `"Performance Metrics:"`
   - Format: `"  Gain   = {value:.2f} dB (spec: >60 dB)"` (exactly this format with spacing and spec notes)
5. **Zeros and Poles section**:
   - Header: `"Zeros and Poles:"`
   - Format: `"  z1  = {value:.6e} rad/s ({value_MHz:.4f} MHz)"` (exactly this format)
6. **Constraint Verification section**:
   - Header: `"Constraint Verification:"`
   - Format: `"  Cons A1 (Model):   {lhs:.6e} >= {rhs:.6e}      {status}"` where status is one of: `PASS`, `BOUNDARY`, or `FAIL` (exactly this format with spacing)

### 6.2 Format Requirements Checklist

Before submitting your code, verify:
- [ ] All numeric values use `.6e` (scientific notation with 6 decimals) or `.2f`/.4f` as shown in template
- [ ] All section headers use **exact** text and spacing shown in template
- [ ] All lines start with 2 spaces for indentation (for subsections)
- [ ] Empty lines appear between sections as shown in template
- [ ] Constraint verification uses `.6e` format for all values
- [ ] Output includes "PASS", "BOUNDARY", or "FAIL" strings for constraint verification

**DO NOT** modify the output format, add extra lines, change spacing, or use different precision. Follow the template **exactly**.

## 7. Constraint Status Determination

### 7.1 Boundary Status Function

You MUST implement a function to determine constraint status (PASS, BOUNDARY, or FAIL) based on the following criteria:

**BOUNDARY判定标准（满足任一即可）**:
1. **相对误差 < 1%**: `|actual - required| / |required| < 0.01`
2. **绝对误差 < 1e-3**: `|actual - required| < 1e-3`
3. **违反比例在合理范围内**: For `>=` constraints, `actual/required >= 0.99`; For `<=` constraints, `required/actual <= 1.01`

**Implementation**:
```python
def get_constraint_status(actual, required, constraint_type='>='):
    """
    判定约束状态：PASS, BOUNDARY, FAIL
    
    Args:
        actual: 实际值
        required: 要求值（对于范围约束，传入元组 (low, high)）
        constraint_type: '>=', '<=', or 'range'
    
    Returns:
        'PASS': 完全满足约束
        'BOUNDARY': 在边界范围内（1%以内，可接受）
        'FAIL': 违反约束（不可接受）
    """
    if constraint_type == '>=':
        if actual >= required:
            return 'PASS'
        # 计算相对误差、绝对误差、违反比例
        rel_error = abs(actual - required) / abs(required) if abs(required) > 1e-10 else float('inf')
        abs_error = abs(actual - required)
        ratio = actual / required if abs(required) > 1e-10 else 0
        
        # 边界判定：相对误差 < 1% OR 绝对误差 < 1e-3 OR 比例 >= 0.99
        if rel_error < 0.01 or abs_error < 1e-3 or ratio >= 0.99:
            return 'BOUNDARY'
        return 'FAIL'
    
    elif constraint_type == '<=':
        if actual <= required:
            return 'PASS'
        rel_error = abs(actual - required) / abs(required) if abs(required) > 1e-10 else float('inf')
        abs_error = abs(actual - required)
        ratio = required / actual if abs(actual) > 1e-10 else float('inf')
        
        # 边界判定：相对误差 < 1% OR 绝对误差 < 1e-3 OR 比例 <= 1.01
        if rel_error < 0.01 or abs_error < 1e-3 or ratio <= 1.01:
            return 'BOUNDARY'
        return 'FAIL'
    
    elif constraint_type == 'range':
        low, high = required
        if low <= actual <= high:
            return 'PASS'
        # 检查下界
        if actual < low:
            rel_error = abs(actual - low) / abs(low) if abs(low) > 1e-10 else float('inf')
            abs_error = abs(actual - low)
            # 相对误差 < 1% OR 绝对误差 < 1e-3
            if rel_error < 0.01 or abs_error < 1e-3:
                return 'BOUNDARY'
        # 检查上界
        if actual > high:
            rel_error = abs(actual - high) / abs(high) if abs(high) > 1e-10 else float('inf')
            abs_error = abs(actual - high)
            # 相对误差 < 1% OR 绝对误差 < 1e-3
            if rel_error < 0.01 or abs_error < 1e-3:
                return 'BOUNDARY'
        return 'FAIL'
```

**Important Notes**:
- Use this function for ALL constraint verifications in the output section
- BOUNDARY status indicates the constraint is within acceptable tolerance (1% relative error)
- This helps downstream analysis tools correctly interpret optimization results

## 8. Code Structure Template

```python
from gekko import GEKKO
import numpy as np
import time

def optimize_opamp_gekko():
    """
    Op-amp optimization using GEKKO/IPOPT
    """
    
    # ========== 1. Constants ==========
    PI = np.pi
    CL_pF = 10.0
    RL_MOhm = 10.0
    wt = 2 * PI * 200e6  # ft = 200 MHz
    VDD = 1.8  # or other supply voltage
    
    # SI unit constants
    CL_SI = CL_pF * 1e-12
    RL_SI = RL_MOhm * 1e6
    
    # ========== 2. Multi-Start Optimization ==========
    n_starts = 200 # we revonmend 200 starts
    best_result = None
    best_fom = -np.inf
    success_count = 0
    
    t_start = time.time()
    
    for seed in range(n_starts):
        np.random.seed(seed)
        
        # Create fresh model
        m = GEKKO(remote=False)
        
        # ========== 3. Design Variables (Scaled) ==========
        # Random initial values (log-uniform for G and C)
        G1_init = np.exp(np.random.uniform(np.log(10), np.log(1000)))
        G2_init = np.exp(np.random.uniform(np.log(10), np.log(1000)))
        A1_init = np.random.uniform(40, 80)
        A2_init = np.random.uniform(40, 80)
        Cm_init = np.exp(np.random.uniform(np.log(0.01), np.log(10)))
        
        G1_uS = m.Var(value=G1_init, lb=10, ub=1000, name='G1_uS')
        G2_uS = m.Var(value=G2_init, lb=10, ub=1000, name='G2_uS')
        A1 = m.Var(value=A1_init, lb=40, ub=80, name='A1')
        A2 = m.Var(value=A2_init, lb=40, ub=80, name='A2')
        Cm_pF = m.Var(value=Cm_init, lb=0.01, ub=10, name='Cm_pF')
        
        # ========== 4. Intermediate Variables ==========
        # Convert to SI units
        G1 = m.Intermediate(G1_uS * 1e-6)
        G2 = m.Intermediate(G2_uS * 1e-6)
        Cm = m.Intermediate(Cm_pF * 1e-12)
        
        # ⚠️ USE FORMULAS FROM STEP 6 - Examples below may not be correct!
        
        # Parasitic capacitances (example)
        Cprs1 = m.Intermediate(G2 / wt)
        
        # Zeros and poles (⚠️ Replace with Step 6 formulas!)
        z1 = m.Intermediate(G2 / Cm)  # Example only
        p2_mag = m.Intermediate(G2 / CL_SI)  # Example only
        
        # Performance metrics (⚠️ Replace with Step 6 formulas!)
        GBW_rad = m.Intermediate(G1 / Cm)
        GBW_MHz = m.Intermediate(GBW_rad / (2 * PI * 1e6))
        
        Power_uW = m.Intermediate(VDD / 20 * (G1 + G2) * 1e6)  # Example
        Power_mW = m.Intermediate(Power_uW / 1000)
        
        Gain_lin = m.Intermediate(A1 * A2)  # Example - use actual formula
        
        # PM calculation (⚠️ Replace with Step 6 formula!)
        r_p2 = m.Intermediate(GBW_rad / p2_mag)
        r_z = m.Intermediate(GBW_rad / z1)
        phi_p2 = m.Intermediate(m.atan(r_p2))
        phi_z = m.Intermediate(m.atan(r_z))
        PM_deg = m.Intermediate(90 - (180/PI) * (phi_p2 - phi_z))  # Example
        # **Phase quadrant handling**: When computing phase using `m.atan()`, remember that `atan(Im/Re)` returns values in $[-\pi/2, \pi/2]$. For transfer functions where the denominator's real part may be negative at GBW (common when $\omega \gg p_1$), you must handle quadrant explicitly. Use the sign of real and imaginary parts to determine the correct quadrant, or restructure the PM formula to avoid quadrant ambiguity.
        
        # FoM
        FoM = m.Intermediate(GBW_MHz * CL_pF / Power_mW)
        
        # ========== 5. Constraints ==========
        # Performance constraints
        m.Equation(Gain_lin >= 1000)      # Gain ≥ 60 dB
        m.Equation(GBW_MHz >= 0.5)        # GBW ≥ 0.5 MHz
        m.Equation(Power_uW <= 250)       # Power ≤ 250 μW
        m.Equation(PM_deg >= 55)          # PM ≥ 55°
        m.Equation(PM_deg <= 65)          # PM ≤ 65°
        
        # Additional constraints from Step 6
        # ⚠️ IMPORTANT: Use scaled units in ALL constraint expressions to avoid numerical issues!
        # Example constraints (replace with your actual Step 6 constraints):
        
        # Constraint A: G2 * Cm > 5 * (G1/A1) * CL (Miller dominance)
        # ❌ WRONG: m.Equation(G2 * Cm >= 5 * (G1/A1) * CL_SI)  # Value ~1e-19, TOO SMALL!
        # ✅ CORRECT: Use scaled units - G2_uS * Cm_pF ~ 100 * 1 = 100 (reasonable range)
        # m.Equation(G2_uS * Cm_pF >= 5 * (G1_uS / A1) * CL_pF)  # Replace with your constraint
        
        # Constraint B: G2 > 1.5 * G1 (RHP zero positioning)
        # ✅ CORRECT: Simple comparison, use scaled units
        # m.Equation(G2_uS >= 1.5 * G1_uS)  # Replace with your constraint
        
        # Constraint C: G2 * Cm^2 > 1.5 * G1 * CL * (Cm + Cprs1) (stability)
        # For C^2 constraints, also use scaled units. Convert parasitic C to pF:
        # Cprs1_pF = m.Intermediate(G2_uS * 1e6 / wt)  # Convert to pF
        # ✅ CORRECT: m.Equation(G2_uS * Cm_pF**2 >= 1.5 * G1_uS * CL_pF * (Cm_pF + Cprs1_pF))
        # Replace above examples with your actual constraints from Step 6, using scaled units!
        
        # ========== 6. Objective ==========
        m.Maximize(FoM)
        
        # ========== 7. Solver Settings ==========
        m.options.SOLVER = 3      # IPOPT
        m.options.MAX_ITER = 500
        
        # ========== 8. Solve ==========
        try:
            m.solve(disp=False)
            # Check solver status: APPSTATUS == 1 means optimal solution found
            if m.options.APPSTATUS == 1:
                success_count += 1
                
                fom_val = FoM.value[0]
                if fom_val > best_fom:
                    best_fom = fom_val
                    best_result = {
                        'G1_uS': G1_uS.value[0],
                        'G2_uS': G2_uS.value[0],
                        'A1': A1.value[0],
                        'A2': A2.value[0],
                        'Cm_pF': Cm_pF.value[0],
                        'GBW_MHz': GBW_MHz.value[0],
                        'Power_uW': Power_uW.value[0],
                        'Gain_lin': Gain_lin.value[0],
                        'PM_deg': PM_deg.value[0],
                        'FoM': fom_val,
                        'z1': z1.value[0],
                        'p2_mag': p2_mag.value[0],
                        'seed': seed
                    }
            else:
                # Solver did not find feasible solution
                pass
        except:
            pass
        finally:
            m.cleanup()
    
    t_elapsed = time.time() - t_start
    
    # ========== 9. Print Results ==========
    if best_result is None:
        print("Optimization failed: No feasible solution found!")
        print("Suggestions:")
        print("  1. Check if constraints from Step 6 are too strict")
        print("  2. Verify formulas match Step 6 derivations")
        print("  3. Increase number of starting points")
        return None
    
    # Calculate derived quantities
    Gain_dB = 20 * np.log10(best_result['Gain_lin'])
    z1_MHz = best_result['z1'] / (2 * np.pi) / 1e6
    p2_MHz = best_result['p2_mag'] / (2 * np.pi) / 1e6
    
    print("=" * 60)
    print("Optimization Results")
    print("=" * 60)
    print(f"Multi-start: {success_count}/{n_starts} successful, Time: {t_elapsed:.2f}s")
    print()
    
    # --- Design Variables (Standard Format for Extraction) ---
    print("Optimal Design Variables:")
    print(f"  G1 = {best_result['G1_uS']*1e-6:.6e} S")
    print(f"  G2 = {best_result['G2_uS']*1e-6:.6e} S")
    print(f"  A1 = {best_result['A1']:.6f}")
    print(f"  A2 = {best_result['A2']:.6f}")
    print(f"  Cm = {best_result['Cm_pF']*1e-12:.6e} F")
    # ⚠️ Print any eliminated variables here (e.g., Rz = 1/G3)
    print()
    
    # --- Performance Metrics ---
    print("Performance Metrics:")
    print(f"  Gain   = {Gain_dB:.2f} dB (spec: >60 dB)")
    print(f"  GBW    = {best_result['GBW_MHz']:.6f} MHz (spec: >0.5 MHz)")
    print(f"  PM     = {best_result['PM_deg']:.2f} deg (spec: 55-65 deg)")
    print(f"  Power  = {best_result['Power_uW']:.2f} uW (spec: <250 uW)")
    print(f"  FoM    = {best_result['FoM']:.4f}")
    print()
    
    # --- Zeros and Poles ---
    print("Zeros and Poles:")
    print(f"  z1  = {best_result['z1']:.6e} rad/s ({z1_MHz:.4f} MHz)")
    print(f"  p2  = {best_result['p2_mag']:.6e} rad/s ({p2_MHz:.4f} MHz)")
    print()
    
    # --- Constraint Check ---
    print("Constraint Verification:")
    
    # Performance Constraints (Must satisfy - all must pass or be BOUNDARY)
    status_gain = get_constraint_status(Gain_dB, 60.0, '>=')
    print(f"  Gain >= 60 dB:     {Gain_dB:.2f} >= 60      {status_gain}")
    
    status_gbw = get_constraint_status(best_result['GBW_MHz'], 0.5, '>=')
    print(f"  GBW >= 0.5 MHz:    {best_result['GBW_MHz']:.4f} >= 0.5    {status_gbw}")
    
    status_pm = get_constraint_status(best_result['PM_deg'], (55.0, 65.0), 'range')
    print(f"  PM in [55, 65]:    {best_result['PM_deg']:.2f} in [55,65] {status_pm}")
    
    status_power = get_constraint_status(best_result['Power_uW'], 250.0, '<=')
    print(f"  Power <= 250 uW:   {best_result['Power_uW']:.2f} <= 250    {status_power}")
    
    # Check Extra Constraints
    G1 = best_result['G1_uS']*1e-6
    G2 = best_result['G2_uS']*1e-6
    A1 = best_result['A1']
    A2 = best_result['A2']
    Cm = best_result['Cm_pF']*1e-12
    
    # Use p2_abs or p2_mag depending on variable name in your code
    p2_abs = best_result.get('p2_abs', best_result.get('p2_mag', 0))
    
    # Model Validity Constraints (Critical - severe violations should reject)
    # A1: G2 * Cm >= 5 * (G1/A1) * CL (ensures simplification assumption is valid)
    lhs_a1 = G2 * Cm
    rhs_a1 = 5 * (G1/A1) * CL_SI
    status_a1 = get_constraint_status(lhs_a1, rhs_a1, '>=')
    print(f"  Cons A1 (Model):   {lhs_a1:.6e} >= {rhs_a1:.6e}      {status_a1}")
    
    # Stability Constraints (Critical - severe violations should reject)
    # C1: p2 >= 2 * GBW (ensures non-dominant pole is far enough for stability)
    lhs_c1 = p2_abs
    rhs_c1 = 2 * (G1/Cm)
    status_c1 = get_constraint_status(lhs_c1, rhs_c1, '>=')
    print(f"  Cons C1 (Stability): {lhs_c1:.6e} >= {rhs_c1:.6e}      {status_c1}")
    
    # D1: G2 >= 1.5 G1 (ensures RHP zero is far enough from GBW)
    status_d1 = get_constraint_status(G2, 1.5*G1, '>=')
    print(f"  Cons D1 (Stability):{G2:.6e} >= {1.5*G1:.6e}      {status_d1}")
    
    print("=" * 60)
    
    return best_result


if __name__ == '__main__':
    result = optimize_opamp_gekko()
```

## 9. Common Issues and Solutions

### 8.1 "Solution Not Found" Error
1. **Infeasible constraints**: Temporarily relax constraints to verify feasibility
2. **Poor initial point**: Increase `n_starts` or adjust initial value ranges
3. **Formula errors**: Double-check formulas against Step 6
4. **Numerical issues**: Check for division by zero, negative sqrt arguments

### 8.2 Low Success Rate (<50%)
1. Increase number of starting points to 200-500
2. Check if constraint set is internally consistent
3. Verify that variable bounds are reasonable
4. **Diagnosis**: If success rate remains low after increasing starts, this may indicate: (1) constraints are infeasible—verify constraint compatibility and power budget; (2) numerical scaling issues—check if constraint expressions use appropriate scaled units; (3) model errors—verify formulas match Step 6 derivations.

### 8.3 GEKKO Syntax Errors
```python
# ❌ Using numpy functions instead of GEKKO functions
PM = np.arctan(x)  # Wrong!
# ✅ Correct
PM = m.Intermediate(m.atan(x))

# ❌ Missing Intermediate wrapper
result = m.sqrt(a) + m.atan(b)  # May cause issues
# ✅ Correct
temp1 = m.Intermediate(m.sqrt(a))
temp2 = m.Intermediate(m.atan(b))
result = m.Intermediate(temp1 + temp2)

# ❌ Variable name conflicts (case-insensitive!)
A1 = m.Var(...)
a1 = m.Var(...)  # Conflicts with A1!
```
```

## Model Response

```python
from gekko import GEKKO
import numpy as np
import time

def get_constraint_status(actual, required, constraint_type='>='):
    """
    判定约束状态：PASS, BOUNDARY, FAIL
    
    Args:
        actual: 实际值
        required: 要求值（对于范围约束，传入元组 (low, high)）
        constraint_type: '>=', '<=', or 'range'
    
    Returns:
        'PASS': 完全满足约束
        'BOUNDARY': 在边界范围内（1%以内，可接受）
        'FAIL': 违反约束（不可接受）
    """
    if constraint_type == '>=':
        if actual >= required:
            return 'PASS'
        # 计算相对误差、绝对误差、违反比例
        rel_error = abs(actual - required) / abs(required) if abs(required) > 1e-10 else float('inf')
        abs_error = abs(actual - required)
        ratio = actual / required if abs(required) > 1e-10 else 0
        
        # 边界判定：相对误差 < 1% OR 绝对误差 < 1e-3 OR 比例 >= 0.99
        if rel_error < 0.01 or abs_error < 1e-3 or ratio >= 0.99:
            return 'BOUNDARY'
        return 'FAIL'
    
    elif constraint_type == '<=':
        if actual <= required:
            return 'PASS'
        rel_error = abs(actual - required) / abs(required) if abs(required) > 1e-10 else float('inf')
        abs_error = abs(actual - required)
        ratio = required / actual if abs(actual) > 1e-10 else float('inf')
        
        # 边界判定：相对误差 < 1% OR 绝对误差 < 1e-3 OR 比例 <= 1.01
        if rel_error < 0.01 or abs_error < 1e-3 or ratio <= 1.01:
            return 'BOUNDARY'
        return 'FAIL'
    
    elif constraint_type == 'range':
        low, high = required
        if low <= actual <= high:
            return 'PASS'
        # 检查下界
        if actual < low:
            rel_error = abs(actual - low) / abs(low) if abs(low) > 1e-10 else float('inf')
            abs_error = abs(actual - low)
            # 相对误差 < 1% OR 绝对误差 < 1e-3
            if rel_error < 0.01 or abs_error < 1e-3:
                return 'BOUNDARY'
        # 检查上界
        if actual > high:
            rel_error = abs(actual - high) / abs(high) if abs(high) > 1e-10 else float('inf')
            abs_error = abs(actual - high)
            # 相对误差 < 1% OR 绝对误差 < 1e-3
            if rel_error < 0.01 or abs_error < 1e-3:
                return 'BOUNDARY'
        return 'FAIL'

def optimize_opamp_gekko():
    """
    Op-amp optimization using GEKKO/IPOPT
    """
    
    # ========== 1. Constants ==========
    PI = np.pi
    CL_pF = 10.0
    RL_MOhm = 10.0
    wt = 1.256e9  # ft = 200 MHz, wt = 1.256e9 rad/s
    VDD = 1.8  # Supply voltage
    
    # SI unit constants
    CL_SI = CL_pF * 1e-12
    RL_SI = RL_MOhm * 1e6
    
    # ========== 2. Multi-Start Optimization ==========
    n_starts = 200 
    best_result = None
    best_fom = -np.inf
    success_count = 0
    
    t_start = time.time()
    
    for seed in range(n_starts):
        np.random.seed(seed)
        
        # Create fresh model
        m = GEKKO(remote=False)
        
        # ========== 3. Design Variables (Scaled) ==========
        # G ranges: [1e-5, 1e-3] S -> [10, 1000] uS
        # A ranges: [40, 80]
        # Cm range: [1e-14, 1e-11] F -> [0.01, 10] pF
        
        G1_init = np.exp(np.random.uniform(np.log(10), np.log(1000)))
        G2_init = np.exp(np.random.uniform(np.log(10), np.log(1000)))
        Gf_init = np.exp(np.random.uniform(np.log(10), np.log(1000)))
        
        A1_init = np.random.uniform(40, 80)
        A2_init = np.random.uniform(40, 80)
        Af_init = np.random.uniform(40, 80)
        
        Cm_init = np.exp(np.random.uniform(np.log(0.01), np.log(10)))
        
        G1_uS = m.Var(value=G1_init, lb=10, ub=1000, name='G1_uS')
        G2_uS = m.Var(value=G2_init, lb=10, ub=1000, name='G2_uS')
        Gf_uS = m.Var(value=Gf_init, lb=10, ub=1000, name='Gf_uS')
        
        A1 = m.Var(value=A1_init, lb=40, ub=80, name='A1')
        A2 = m.Var(value=A2_init, lb=40, ub=80, name='A2')
        Af = m.Var(value=Af_init, lb=40, ub=80, name='Af')
        
        Cm_pF = m.Var(value=Cm_init, lb=0.01, ub=10, name='Cm_pF')
        
        # ========== 4. Intermediate Variables ==========
        # Convert to SI units for physical calculations
        G1 = m.Intermediate(G1_uS * 1e-6)
        G2 = m.Intermediate(G2_uS * 1e-6)
        Gf = m.Intermediate(Gf_uS * 1e-6)
        Cm = m.Intermediate(Cm_pF * 1e-12)
        
        # --- Derived Parasitics (Step 6 Formulas) ---
        # g_o1 = G1 / A1
        g_o1 = m.Intermediate(G1 / A1)
        # g_o2 = G2 / A2 + Gf / Af + 1 / RL
        g_o2 = m.Intermediate(G2 / A2 + Gf / Af + 1 / RL_SI)
        # Cprs1 = G2 / wt
        Cprs1 = m.Intermediate(G2 / wt)
        Cprs1_pF = m.Intermediate(Cprs1 * 1e12) # For scaled constraints
        
        # --- Poles and Zeros (Step 6 Formulas) ---
        # w_gbw = G1 / Cm
        w_gbw = m.Intermediate(G1 / Cm)
        
        # w_p2 = (G2 * Cm) / (CL * (Cm + Cprs1))
        w_p2 = m.Intermediate((G2 * Cm) / (CL_SI * (Cm + Cprs1)))
        
        # w_z1 = (G1 * G2) / (Gf * Cprs1 + Cm * (Gf - G1))
        # Note: Denominator must be > 0. Constraint C1 (Gf > 1.1 G1) ensures this.
        z1_denom = m.Intermediate(Gf * Cprs1 + Cm * (Gf - G1))
        w_z1 = m.Intermediate((G1 * G2) / z1_denom)
        
        # --- Performance Metrics ---
        # Gain = (G1 * G2) / (g_o1 * g_o2)
        Gain_lin = m.Intermediate((G1 * G2) / (g_o1 * g_o2))
        Gain_dB = m.Intermediate(20 * m.log10(Gain_lin))
        
        # GBW (MHz)
        GBW_MHz = m.Intermediate(w_gbw / (2 * PI * 1e6))
        
        # Power (uW)
        # Formula: Power = 0.09 * (G1 + G2 + Gf)  (Watts) -> *1e6 for uW
        Power_uW = m.Intermediate(0.09 * (G1 + G2 + Gf) * 1e6)
        Power_mW = m.Intermediate(Power_uW / 1000.0)
        
        # Phase Margin (degrees)
        # PM = 90 - atan(w_gbw/w_p2) + atan(w_gbw/w_z1)
        # Note: w_p2 is LHP pole (lag), w_z1 is LHP zero (lead)
        phi_p2 = m.Intermediate(m.atan(w_gbw / w_p2))
        phi_z1 = m.Intermediate(m.atan(w_gbw / w_z1))
        PM_deg = m.Intermediate(90 - (phi_p2 * 180/PI) + (phi_z1 * 180/PI))
        
        # Figure of Merit
        FoM = m.Intermediate(GBW_MHz * CL_pF / Power_mW)
        
        # ========== 5. Constraints ==========
        
        # --- Performance Specs ---
        m.Equation(Gain_dB >= 60)
        m.Equation(GBW_MHz >= 0.5)
        m.Equation(Power_uW <= 250)
        m.Equation(PM_deg >= 55)
        m.Equation(PM_deg <= 65)
        
        # --- Extra Constraints from Step 6 (Using Scaled Units) ---
        
        # A1: A_1 > 10 (Implicit in bounds [40, 80])
        
        # A2: C_m > (G_1 * C_L) / (G_2 * A_1)
        # Scaled: Cm_pF > (G1_uS * CL_pF) / (G2_uS * A1)
        m.Equation(Cm_pF * G2_uS * A1 >= G1_uS * CL_pF)
        
        # B1: (G_2 * C_m)**2 > 4 * (g_o1 * g_o2) * C_L * (C_m + Cprs1)
        # LHS Scaled: (G2_uS * Cm_pF)**2
        # RHS Scaled: We need to be careful with units.
        # Let's derive a unit-independent check or carefully scale.
        # (S * F)^2 = S^2 * F^2.
        # RHS = S * S * F * F = S^2 * F^2. Units match.
        # Let's use SI for B1 to be safe, but scale values to avoid underflow.
        # Actually, let's construct it using the intermediate variables but multiplied by 1e12 or 1e6.
        # Better: Use the simplified condition form in scaled units:
        # g_o1 ~ G1/A1 (S), g_o2 ~ G2/A2 (S).
        # It's robust to do this in log domain or just use the scaled variable forms if units align.
        # Let's use the explicit constraint equation with variables.
        # Since this is an inequality constraint for real poles, we can just ensure the discriminant is positive.
        # (G2*Cm)^2 > 4 * (G1/A1)*(G2/A2 + Gf/Af + 1/RL)*(CL)*(Cm + Cprs1)
        # Let's use the SI intermediates but multiply both sides by 1e24 (to bring to ~1 range).
        term_LHS = m.Intermediate((G2 * Cm * 1e12)**2) # ~ (100u * 1p * 1e12)^2 = 100^2 = 10000
        term_RHS = m.Intermediate(4 * g_o1 * g_o2 * CL_SI * (Cm + Cprs1) * 1e24)
        m.Equation(term_LHS >= term_RHS)
        
        # C1: G_f > 1.1 * G_1
        # Scaled: Gf_uS > 1.1 * G1_uS
        m.Equation(Gf_uS >= 1.1 * G1_uS)
        
        # ========== 6. Objective ==========
        m.Maximize(FoM)
        
        # ========== 7. Solver Settings ==========
        m.options.SOLVER = 3      # IPOPT
        m.options.MAX_ITER = 500
        m.options.OTOL = 1e-4
        m.options.RTOL = 1e-4
        
        # ========== 8. Solve ==========
        try:
            m.solve(disp=False)
            if m.options.APPSTATUS == 1:
                success_count += 1
                
                fom_val = FoM.value[0]
                if fom_val > best_fom:
                    best_fom = fom_val
                    best_result = {
                        'G1_uS': G1_uS.value[0],
                        'G2_uS': G2_uS.value[0],
                        'Gf_uS': Gf_uS.value[0],
                        'A1': A1.value[0],
                        'A2': A2.value[0],
                        'Af': Af.value[0],
                        'Cm_pF': Cm_pF.value[0],
                        
                        'GBW_MHz': GBW_MHz.value[0],
                        'Power_uW': Power_uW.value[0],
                        'Gain_dB': Gain_dB.value[0],
                        'PM_deg': PM_deg.value[0],
                        'FoM': fom_val,
                        
                        'z1': w_z1.value[0],
                        'p2': w_p2.value[0],
                        
                        # Auxiliary for constraint checking
                        'LHS_A2': Cm_pF.value[0],
                        'RHS_A2': (G1_uS.value[0] * CL_pF) / (G2_uS.value[0] * A1.value[0]),
                        'LHS_C1': Gf_uS.value[0],
                        'RHS_C1': 1.1 * G1_uS.value[0],
                        'LHS_B1': term_LHS.value[0],
                        'RHS_B1': term_RHS.value[0]
                    }
        except:
            pass
        finally:
            m.cleanup()
    
    t_elapsed = time.time() - t_start
    
    # ========== 9. Print Results ==========
    if best_result is None:
        print("Optimization failed: No feasible solution found!")
        return None
    
    # Derived quantities for display
    z1_MHz = best_result['z1'] / (2 * PI * 1e6)
    p2_MHz = best_result['p2'] / (2 * PI * 1e6)
    
    print("=" * 60)
    print("Optimization Results")
    print("=" * 60)
    print(f"Multi-start: {success_count}/{n_starts} successful, Time: {t_elapsed:.2f}s")
    print()
    
    print("Optimal Design Variables:")
    print(f"  G1 = {best_result['G1_uS']*1e-6:.6e} S")
    print(f"  G2 = {best_result['G2_uS']*1e-6:.6e} S")
    print(f"  Gf = {best_result['Gf_uS']*1e-6:.6e} S")
    print(f"  A1 = {best_result['A1']:.6f}")
    print(f"  A2 = {best_result['A2']:.6f}")
    print(f"  Af = {best_result['Af']:.6f}")
    print(f"  Cm = {best_result['Cm_pF']*1e-12:.6e} F")
    print()
    
    print("Performance Metrics:")
    print(f"  Gain   = {best_result['Gain_dB']:.2f} dB (spec: >60 dB)")
    print(f"  GBW    = {best_result['GBW_MHz']:.6f} MHz (spec: >0.5 MHz)")
    print(f"  PM     = {best_result['PM_deg']:.2f} deg (spec: 55-65 deg)")
    print(f"  Power  = {best_result['Power_uW']:.2f} uW (spec: <250 uW)")
    print(f"  FoM    = {best_result['FoM']:.4f}")
    print()
    
    print("Zeros and Poles:")
    print(f"  z1  = {best_result['z1']:.6e} rad/s ({z1_MHz:.4f} MHz)")
    print(f"  p2  = {best_result['p2']:.6e} rad/s ({p2_MHz:.4f} MHz)")
    print()
    
    print("Constraint Verification:")
    # Performance
    status_gain = get_constraint_status(best_result['Gain_dB'], 60.0, '>=')
    print(f"  Gain >= 60 dB:     {best_result['Gain_dB']:.2f} >= 60      {status_gain}")
    
    status_gbw = get_constraint_status(best_result['GBW_MHz'], 0.5, '>=')
    print(f"  GBW >= 0.5 MHz:    {best_result['GBW_MHz']:.4f} >= 0.5    {status_gbw}")
    
    status_pm = get_constraint_status(best_result['PM_deg'], (55.0, 65.0), 'range')
    print(f"  PM in [55, 65]:    {best_result['PM_deg']:.2f} in [55,65] {status_pm}")
    
    status_power = get_constraint_status(best_result['Power_uW'], 250.0, '<=')
    print(f"  Power <= 250 uW:   {best_result['Power_uW']:.2f} <= 250    {status_power}")
    
    # Extra Constraints
    # A2: Cm > (G1 * CL) / (G2 * A1)
    status_a2 = get_constraint_status(best_result['LHS_A2'], best_result['RHS_A2'], '>=')
    print(f"  Cons A2 (Miller):  {best_result['LHS_A2']:.6e} >= {best_result['RHS_A2']:.6e}      {status_a2}")
    
    # B1: Real Poles
    status_b1 = get_constraint_status(best_result['LHS_B1'], best_result['RHS_B1'], '>=')
    print(f"  Cons B1 (Real P):  {best_result['LHS_B1']:.6e} >= {best_result['RHS_B1']:.6e}      {status_b1}")
    
    # C1: Gf > 1.1 * G1
    status_c1 = get_constraint_status(best_result['LHS_C1'], best_result['RHS_C1'], '>=')
    print(f"  Cons C1 (LHP z1):  {best_result['LHS_C1']:.6e} >= {best_result['RHS_C1']:.6e}      {status_c1}")

    print("=" * 60)
    
    return best_result

if __name__ == '__main__':
    optimize_opamp_gekko()
```

---

*File path: experiments/pipeline_outputs_20260119_031945_MZC/iteration_01/iter01_step07_global07_white_box_optimization_programming_clean.md*
