from gekko import GEKKO
import numpy as np
import time

def get_constraint_status(actual, required, constraint_type='>='):
    """
    Determine constraint status: PASS, BOUNDARY, FAIL
    """
    if constraint_type == '>=':
        if actual >= required:
            return 'PASS'
        rel_error = abs(actual - required) / abs(required) if abs(required) > 1e-10 else float('inf')
        abs_error = abs(actual - required)
        ratio = actual / required if abs(required) > 1e-10 else 0
        if rel_error < 0.01 or abs_error < 1e-3 or ratio >= 0.99:
            return 'BOUNDARY'
        return 'FAIL'
    
    elif constraint_type == '<=':
        if actual <= required:
            return 'PASS'
        rel_error = abs(actual - required) / abs(required) if abs(required) > 1e-10 else float('inf')
        abs_error = abs(actual - required)
        ratio = required / actual if abs(actual) > 1e-10 else float('inf')
        if rel_error < 0.01 or abs_error < 1e-3 or ratio <= 1.01:
            return 'BOUNDARY'
        return 'FAIL'
    
    elif constraint_type == 'range':
        low, high = required
        if low <= actual <= high:
            return 'PASS'
        if actual < low:
            rel_error = abs(actual - low) / abs(low) if abs(low) > 1e-10 else float('inf')
            abs_error = abs(actual - low)
            if rel_error < 0.01 or abs_error < 1e-3:
                return 'BOUNDARY'
        if actual > high:
            rel_error = abs(actual - high) / abs(high) if abs(high) > 1e-10 else float('inf')
            abs_error = abs(actual - high)
            if rel_error < 0.01 or abs_error < 1e-3:
                return 'BOUNDARY'
        return 'FAIL'

def optimize_opamp_gekko():
    """
    Op-amp optimization using GEKKO/IPOPT
    Topology: Two-stage Miller with Feedforward
    """
    
    # ========== 1. Constants ==========
    PI = np.pi
    CL_pF = 10.0
    RL_MOhm = 10.0
    wt = 1.256e9  # 2 * pi * 200 MHz
    VDD = 1.8
    
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
        # G: 10uS ~ 1000uS
        G1_init = np.exp(np.random.uniform(np.log(10), np.log(1000)))
        G2_init = np.exp(np.random.uniform(np.log(10), np.log(1000)))
        Gf_init = np.exp(np.random.uniform(np.log(10), np.log(1000)))
        
        # A: 40 ~ 80
        A1_init = np.random.uniform(40, 80)
        A2_init = np.random.uniform(40, 80)
        Af_init = np.random.uniform(40, 80)
        
        # C: 0.01pF ~ 10pF
        Cm_init = np.exp(np.random.uniform(np.log(0.01), np.log(10)))
        
        G1_uS = m.Var(value=G1_init, lb=10, ub=1000, name='G1_uS')
        G2_uS = m.Var(value=G2_init, lb=10, ub=1000, name='G2_uS')
        Gf_uS = m.Var(value=Gf_init, lb=10, ub=1000, name='Gf_uS')
        
        A1 = m.Var(value=A1_init, lb=40, ub=80, name='A1')
        A2 = m.Var(value=A2_init, lb=40, ub=80, name='A2')
        Af = m.Var(value=Af_init, lb=40, ub=80, name='Af')
        
        Cm_pF = m.Var(value=Cm_init, lb=0.01, ub=10, name='Cm_pF')
        
        # ========== 4. Intermediate Variables ==========
        # 4.1 Unit Conversions for Calculation
        G1 = m.Intermediate(G1_uS * 1e-6)
        G2 = m.Intermediate(G2_uS * 1e-6)
        Gf = m.Intermediate(Gf_uS * 1e-6)
        Cm = m.Intermediate(Cm_pF * 1e-12)
        
        # 4.2 Circuit Parameters
        # Parasitic Capacitance (Stage 2 Input)
        Cprs1 = m.Intermediate(G2 / wt)
        Cprs1_pF = m.Intermediate(Cprs1 * 1e12)
        
        # Output Conductances
        go1 = m.Intermediate(G1 / A1)
        go2 = m.Intermediate(G2 / A2 + Gf / Af + 1 / RL_SI)
        
        # 4.3 Poles and Zeros (Formulas from Step 6)
        # Dominant Pole p1 (Low frequency)
        p1 = m.Intermediate(- (go1 * go2) / (G2 * Cm))
        
        # Non-Dominant Pole p2 (High frequency)
        # p2 = - (G2 * Cm) / (CL * (Cm + Cprs1))
        # Use absolute value for magnitude calculations
        p2_mag = m.Intermediate((G2 * Cm) / (CL_SI * (Cm + Cprs1)))
        
        # Feedforward Zero z1
        # z1 = - (G1 * G2) / (Gf * (Cprs1 + Cm) - G1 * Cm)
        # Denominator term
        z1_denom = m.Intermediate(Gf * (Cprs1 + Cm) - G1 * Cm)
        # We enforce LHP zero via Constraint C2, so z1_denom should be positive
        z1_mag = m.Intermediate((G1 * G2) / m.max2(z1_denom, 1e-20)) # Avoid div by zero
        
        # 4.4 Performance Metrics
        # Gain
        Av0 = m.Intermediate((G1 * G2) / (go1 * go2))
        Gain_dB = m.Intermediate(20 * m.log10(Av0))
        
        # GBW
        GBW_rad = m.Intermediate(G1 / Cm)
        GBW_MHz = m.Intermediate(GBW_rad / (2 * PI * 1e6))
        
        # Power
        # Power = VDD/20 * (sum of |G|)
        Power_W = m.Intermediate((VDD / 20.0) * (G1 + G2 + Gf))
        Power_uW = m.Intermediate(Power_W * 1e6)
        Power_mW = m.Intermediate(Power_W * 1e3)
        
        # Phase Margin
        # PM = 90 + atan(GBW/|z1|) - atan(GBW/|p2|)
        # Note: z1 is LHP (Constraint C2), p2 is LHP
        phi_z = m.Intermediate(m.atan(GBW_rad / z1_mag))
        phi_p2 = m.Intermediate(m.atan(GBW_rad / p2_mag))
        PM_deg = m.Intermediate(90 + (180/PI) * (phi_z - phi_p2))
        
        # FoM
        FoM = m.Intermediate(GBW_MHz * CL_pF / Power_mW)
        
        # ========== 5. Constraints ==========
        # 5.1 Design Specs
        m.Equation(Gain_dB >= 60)
        m.Equation(GBW_MHz >= 0.5)
        m.Equation(Power_uW <= 250)
        m.Equation(PM_deg >= 55)
        m.Equation(PM_deg <= 65)
        
        # 5.2 Additional Constraints (Step 6)
        # Use SCALED variables for robustness
        
        # A2: Cm > G1 * CL / (G2 * A1)
        # Scaled: Cm_pF > G1_uS * CL_pF / (G2_uS * A1)
        m.Equation(Cm_pF * G2_uS * A1 >= G1_uS * CL_pF)
        
        # B1: Real Poles (Widely separated)
        # (G2 * Cm)^2 > 4 * go1 * go2 * CL * (Cm + Cprs1)
        # This is usually satisfied by design, simplified check:
        # G2 * Cm >> go1 * CL -> satisfied by A2 roughly
        # We implement it anyway. Note go1, go2 are intermediate SI variables.
        # Let's scale the whole equation to approx 1e12 range or similar.
        # LHS_SI = (G2*Cm)^2 ~ (1e-4 * 1e-12)^2 = 1e-32 (Too small!)
        # Scaled check: (G2_uS * Cm_pF)**2 ~ (100 * 1)**2 = 1e4
        # Need to express RHS in scaled units.
        # go1_scaled = G1_uS / A1
        # go2_scaled = (G2_uS/A2 + Gf_uS/Af + 1e6/RL_MOhm)
        # RHS_scaled = 4 * go1_scaled * go2_scaled * CL_pF * (Cm_pF + Cprs1_pF)
        # LHS ~ 1e4. RHS ~ 4 * 1 * 1 * 10 * 1 = 40. OK range.
        go1_sc = m.Intermediate(G1_uS / A1)
        go2_sc = m.Intermediate(G2_uS / A2 + Gf_uS / Af + 1000.0 / RL_MOhm) # 1/R_L(MOhm) * 1e3 to get uS ? No.
        # 1/R_L_SI = 1/(RL_MOhm * 1e6) S. In uS: 1e6 / (RL_MOhm * 1e6) * 1e6 = 1e6 / RL_MOhm.
        # Correct go2_sc in uS:
        go2_sc_uS = m.Intermediate(G2_uS / A2 + Gf_uS / Af + 1.0 / (RL_MOhm * 1e-6)) # Wait.
        # R_L = 10 MOhm = 10e6 Ohm. G_L = 0.1 uS.
        # Scaled eq: (G2_uS * Cm_pF)**2 >= 4 * go1_sc * (G2_uS/A2 + Gf_uS/Af + 0.1) * CL_pF * (Cm_pF + Cprs1_pF)
        m.Equation((G2_uS * Cm_pF)**2 >= 4 * (G1_uS/A1) * (G2_uS/A2 + Gf_uS/Af + 0.1) * CL_pF * (Cm_pF + Cprs1_pF))
        
        # C1: |p2| >= 2 * GBW
        # Formula: G2 * Cm / (CL * (Cm + Cprs1)) >= 2 * G1 / Cm
        # Rearranged: G2 * Cm^2 >= 2 * G1 * CL * (Cm + Cprs1)
        # Scaled: G2_uS * Cm_pF**2 >= 2 * G1_uS * CL_pF * (Cm_pF + Cprs1_pF)
        m.Equation(G2_uS * Cm_pF**2 >= 2 * G1_uS * CL_pF * (Cm_pF + Cprs1_pF))
        
        # C2: LHP Zero Enforcement
        # Gf * (Cprs1 + Cm) > 1.1 * G1 * Cm
        # Scaled:
        m.Equation(Gf_uS * (Cprs1_pF + Cm_pF) >= 1.1 * G1_uS * Cm_pF)
        
        # C3: |z1| >= 1.0 * GBW
        # Formula: |z1| = G1 * G2 / (Gf*(Cprs1+Cm) - G1*Cm) >= G1/Cm
        # Rearranged: G2 * Cm >= Gf*(Cprs1+Cm) - G1*Cm
        # Scaled:
        m.Equation(G2_uS * Cm_pF >= Gf_uS * (Cprs1_pF + Cm_pF) - G1_uS * Cm_pF)
        
        # ========== 6. Objective ==========
        m.Maximize(FoM)
        
        # ========== 7. Solver Settings ==========
        m.options.SOLVER = 3      # IPOPT
        m.options.MAX_ITER = 500
        
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
                        'Cprs1_pF': Cprs1_pF.value[0],
                        'GBW_MHz': GBW_MHz.value[0],
                        'Power_uW': Power_uW.value[0],
                        'Gain_dB': Gain_dB.value[0],
                        'PM_deg': PM_deg.value[0],
                        'FoM': fom_val,
                        'z1': z1_mag.value[0],
                        'p2_mag': p2_mag.value[0],
                        'seed': seed
                    }
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
        return None
    
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
    
    z1_MHz = best_result['z1'] / (2 * np.pi * 1e6)
    p2_MHz = best_result['p2_mag'] / (2 * np.pi * 1e6)
    
    print("Zeros and Poles:")
    print(f"  z1  = {best_result['z1']:.6e} rad/s ({z1_MHz:.4f} MHz)")
    print(f"  p2  = {best_result['p2_mag']:.6e} rad/s ({p2_MHz:.4f} MHz)")
    print()
    
    print("Constraint Verification:")
    
    # Metrics
    s_gain = get_constraint_status(best_result['Gain_dB'], 60.0, '>=')
    print(f"  Gain >= 60 dB:     {best_result['Gain_dB']:.2f} >= 60      {s_gain}")
    
    s_gbw = get_constraint_status(best_result['GBW_MHz'], 0.5, '>=')
    print(f"  GBW >= 0.5 MHz:    {best_result['GBW_MHz']:.4f} >= 0.5    {s_gbw}")
    
    s_pm = get_constraint_status(best_result['PM_deg'], (55.0, 65.0), 'range')
    print(f"  PM in [55, 65]:    {best_result['PM_deg']:.2f} in [55,65] {s_pm}")
    
    s_pwr = get_constraint_status(best_result['Power_uW'], 250.0, '<=')
    print(f"  Power <= 250 uW:   {best_result['Power_uW']:.2f} <= 250    {s_pwr}")
    
    # Extra Constraints Data
    G1 = best_result['G1_uS'] * 1e-6
    G2 = best_result['G2_uS'] * 1e-6
    Gf = best_result['Gf_uS'] * 1e-6
    Cm = best_result['Cm_pF'] * 1e-12
    Cprs1 = best_result['Cprs1_pF'] * 1e-12
    GBW_rad = best_result['GBW_MHz'] * 2 * np.pi * 1e6
    p2_mag = best_result['p2_mag']
    z1_mag = best_result['z1']
    
    # A2: Cm > G1 * CL / (G2 * A1)
    lhs_a2 = Cm
    rhs_a2 = G1 * CL_SI / (G2 * best_result['A1'])
    s_a2 = get_constraint_status(lhs_a2, rhs_a2, '>=')
    print(f"  Cons A2 (Miller):  {lhs_a2:.6e} >= {rhs_a2:.6e}      {s_a2}")
    
    # C1: |p2| >= 2 * GBW
    lhs_c1 = p2_mag
    rhs_c1 = 2 * GBW_rad
    s_c1 = get_constraint_status(lhs_c1, rhs_c1, '>=')
    print(f"  Cons C1 (p2>2GBW): {lhs_c1:.6e} >= {rhs_c1:.6e}      {s_c1}")
    
    # C2: LHP Zero (Gf term > G1 term)
    lhs_c2 = Gf * (Cprs1 + Cm)
    rhs_c2 = 1.1 * G1 * Cm
    s_c2 = get_constraint_status(lhs_c2, rhs_c2, '>=')
    print(f"  Cons C2 (LHP Zero):{lhs_c2:.6e} >= {rhs_c2:.6e}      {s_c2}")
    
    # C3: |z1| >= GBW
    lhs_c3 = z1_mag
    rhs_c3 = GBW_rad
    s_c3 = get_constraint_status(lhs_c3, rhs_c3, '>=')
    print(f"  Cons C3 (z1>GBW):  {lhs_c3:.6e} >= {rhs_c3:.6e}      {s_c3}")
    
    print("=" * 60)
    
    return best_result

if __name__ == '__main__':
    optimize_opamp_gekko()
