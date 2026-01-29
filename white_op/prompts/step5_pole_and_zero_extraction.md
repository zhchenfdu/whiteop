# Step 5: Extraction of Poles and Zeros

Now, consider the design variable ranges and extract analytical formulas for zeros and poles from the transfer function polynomials. This step focuses on the mathematical extraction of roots; the regulation of pole-zero positions for function implementation and performance optimization will be handled in Step 6.


This step is highly dependent on the predefined design variable range $\mathcal{{D}}_{{var}}$:
- Transconductance G: [1e-5, 1e-3]; e.g., G_in_1 = 5e-4 S.
- Gain A: [40.0, 80.0]; e.g., A_in_1 = 70, actual input parasitic resistance = 70/G_in_1 Ohm.
- Independent resistance R: [1e1, 1e6]; e.g., R_1_out = 5e5 Ohm; specifically, load: R_L = 10M Ohm.
- Independent capacitance C: [1e-14, 1e-11]; e.g., C_2_out = 5e-12 F; specifically, load: C_L = 10 pF.

## 1. Polynomial Coefficient Simplification

Before solving for zeros and poles, perform necessary simplifications on the polynomial coefficients based on $\mathcal{{D}}_{{var}}$ to facilitate subsequent root-finding.

When simplifying, balance necessity (whether the term's complexity hinders subsequent derivation) against feasibility (whether the simplification is robustly valid within $\mathcal{{D}}_{{var}}$). If additional constraints are needed to justify a simplification, record them as **Additional Constraints A**.

**Important Reminders**:
- Precisely examine value ranges according to $\mathcal{{D}}_{{var}}$; do not rely solely on typical-value substitution.
- **Parasitic capacitances are often significant**: In multi-stage amplifiers, parasitic capacitances (e.g., $C_{prs} = G/\omega_t$ at transistor inputs) can be comparable to or even larger than compensation capacitances, especially when the optimizer minimizes compensation capacitors. **Prefer total node capacitance**: When parasitic capacitances are significant (common in low-power designs), use total capacitance $C_{total} = C_{explicit} + C_{parasitic}$ in pole/zero formulas rather than relying solely on constraints. This provides model robustness across the optimization space. Only add constraints (e.g., $C_m > 2-3 \times C_{prs}$) if explicit inclusion is impractical.
- Prefer inequality constraints over equality constraints, as equality constraints may significantly reduce the feasible solution space.
- It is recommended to perform only necessary reductions; many formula details can retain their original form.

**Output requirement for Constraint A**:
For each simplification introduced, briefly document:
- The specific term(s) being simplified and the resulting simplified form
- The physical/mathematical rationale and motivation of this Constraint

## 2. Approximate Solution of Zeros and Poles

We need to solve for the roots of the transfer function numerator and denominator polynomials, thereby naturally performing factorization to obtain the standard form of the transfer function: Gain × (zero distribution factorization) / (pole distribution factorization).

### 2.1 Approach to Solving for Zeros and Poles

- Some polynomials can be naturally factorized, which is of course the most desirable situation.
- Some polynomials cannot be factorized without bias. In such cases, you need to fully utilize your mathematical talent, introducing additional constraints (recorded as **Additional Constraints B**) for formula reduction, thereby enabling approximate solution of the equations.
    - People often introduce root separation / dominant-root assumptions. However, be aware that such assumptions may not always hold—especially in multi-stage amplifiers with complex compensation networks where poles and zeros may exhibit more intricate distributions (e.g., closely spaced poles, complex conjugate pairs, or roots in different half-planes). You should first assess whether these assumptions are appropriate for the specific circuit topology before adopting them.
    - Of course, we also encourage you to propose better root-finding approaches tailored to the actual pole-zero distribution characteristics of the circuit.

**Important Reminders**:
- Do not blindly reduce terms to simplify the problem, or reduce based solely on habit, experience, or intuition; this may introduce feasibility risks.
- Do not blindly discard higher-order terms; the impact of higher-order terms on transfer function zeros and poles may not be negligible.
- **Discriminant check is mandatory**: If the quadratic formula is used, you must thoroughly examine the discriminant of the equation to clarify whether the roots are real or complex conjugate pairs. For multi-stage amplifiers with Miller compensation, complex conjugate pole pairs are common and should be expressed in appropriate form (e.g., natural frequency $\omega_n$ and damping ratio $\zeta$). Do not assume poles are always real.
- Pay attention to the sign of roots—the location of poles and zeros (left-half-plane vs. right-half-plane) has significant implications for system stability and phase characteristics.
- Record all Additional Constraints B, to serve as constraints for the subsequent optimization problem.
- Prefer inequality constraints over equality constraints, as equality constraints may significantly reduce the feasible solution space.

**Output requirement for Constraint B**:
For each root-solving assumption introduced, briefly document:
- The specific assumption and its mathematical form
- The physical/mathematical rationale and motivation of this Constraint

## 3. Validity Check

- Constraint omission detection: Verify whether any additional constraints were omitted during the entire reduction-solving process.
- Constraint conflict detection: Verify whether there are incompatibilities among the introduced additional constraints, or between the additional constraints and the original design variable ranges.
- Pole-zero sanity check: Verify that the extracted poles and zeros are physically reasonable for the given circuit topology.
- **Optimizer behavior awareness**: Remember that the optimizer will seek to maximize FoM, which often drives compensation capacitances to their lower bounds. The optimizer may simultaneously maximize some variables (e.g., transconductance $G$ for drive capability) while minimizing others (e.g., compensation capacitance $C_m$ for bandwidth). This combination can make parasitic effects dominant at optimal points, invalidating assumptions based on typical values. Simplification assumptions based on "typical" values (e.g., $C_m \gg C_{prs}$) may become invalid at optimal design points. Verify that your simplification assumptions remain valid even when variables are pushed to their boundaries by the optimizer.
- Iterate through the above steps until all are satisfied; do not cut corners.


## 4. Final Output Format

### 4.1 Output Structure Requirement

The response must include **both the derivation process and the final results**, following the logical flow of this step:

1. **Polynomial Coefficient Simplification**: Present simplifications with their justifying analysis (e.g., order-of-magnitude comparisons), and explicitly state each Constraint A introduced.

2. **Root Extraction Process**: Show the approach, key reasoning steps (e.g., discriminant analysis), extracted root expressions, and explicitly state each Constraint B introduced.

3. **Validity Check**: Verify constraint compatibility and physical reasonableness.

**Important**: Intermediate algebraic steps may be omitted, but the logical basis for each simplification and assumption must be shown—not just the conclusions. Responses that skip directly to results without demonstrating the reasoning chain are incomplete.

### 4.2 Key Deliverables in Tags

After the derivation, provide tagged summaries for extraction:

- `<cooked_hs>` ... `</cooked_hs>`: Final transfer function in factored form.

- `<extra_cons>` ... `</extra_cons>`: All constraints, formatted as:
  - **Constraints A**: A1: [expression] — [rationale]; A2: ...
  - **Constraints B**: B1: [expression] — [rationale]; B2: ...

Note: The tagged content summarizes the derivation; it does not replace it.

## 5. Additional Notes

All formulas should be written in standard LaTeX format, enclosed within `$$...$$` or `$...$`, to ensure proper rendering in .md files.