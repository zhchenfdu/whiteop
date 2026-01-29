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
