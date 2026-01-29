# Step 4: Design Variable Substitution and Simplification

Consider the modeling approach for each transconductance stage in the behavioral-level operational amplifier. In the transfer function, substitute the original physical variables and perform unbiased simplification.

## 1. Substitution Method
For a given transconductance G:
- Parasitic resistance at the output: $R_{{prs}} = A/G$, where A is the gain of that stage, and G is the transconductance value of that stage (always positive). **Please note** that the transconductance G value is always positive, but the sign of the transconductance in the netlist affects the phase relationship.
- Parasitic capacitance at the output: $C_{{prs}} = G_{{next}}/\omega_t$, which is essentially the input parasitic capacitance of the next transconductance stage $G_{{next}}$, where $\omega_t = 2\pi f_t$, $f_t = 200 \text{{M}}Hz$ (or equivalently $T = 5 \text{{n}}s$).
- If a transconductance stage has no $G_{{next}}$ (i.e., it is already the output stage), then there is no $C_{{prs}}$ associated with it.

## 2. Whether to Reduce
The above substitutions often produce terms that can be further simplified. Please perform unbiased simplification, but do not perform reductions based on the order of magnitude of variables.

## 3. Expression Arrangement
Use purely symbolic methods to simplify the numerator and denominator of the formula. If natural factorization is possible, proceed with factorization directly. If factorization is not possible, do not force it—maintain the standard polynomial form of the numerator and denominator as is.

## 4. Format for Extracted Target Content
After completing the simplification, please place the organized, complete transfer function (including the overall structure and the values of each coefficient) between the `<real_hs>` and `</real_hs>` tags at the end as the final answer for this step. This facilitates extraction and maintenance as a key field.

## 5. Additional Notes
All formulas should be written in standard LaTeX format, enclosed within `$$...$$` or `$...$`, to ensure proper rendering in .md files.