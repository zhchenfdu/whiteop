# Step 3: Unbiased Transfer Function Derivation

Based on the circuit equations above, solve for the transfer function $H(s) = V_o(s)/V_i(s)$ without bias.

## 1. Variables to Use
Continue using the original physically meaningful variables (such as: G, Rprs, Cprs, R, C, etc.). Do not substitute the actual design variables and parameters at this stage (such as: $Rprs=A/G$ and $Cprs=G_{{next}}/\omega_t$, etc.).

## 2. Whether to Reduce
Remain unbiased and do not consider reductions based on the order of magnitude of variables.

## 3. Expression Arrangement
Convert the original circuit equations into the transfer function form only, ensuring that each polynomial coefficient in the numerator/denominator is listed in detail and with precision. Do not neglect higher-order terms.
The transfer function format example is as follows:
$$H(s) = \frac{{N(s)}}{{D(s)}} = \frac{{a_n s^n + a_{{n-1}} s^{{n-1}} + ... + a_1 s + a_0}}{{b_m s^m + b_{{m-1}} s^{{m-1}} + ... + b_1 s + b_0}}$$

## 4. Format for Extracted Target Content
After completing the solution, please place the organized, complete transfer function (including the overall structure and the formula expansion of each coefficient) between the `<raw_hs>` and `</raw_hs>` tags at the end as the final answer for this step. This facilitates extraction and maintenance as a key field.

## 5. Additional Notes
All formulas should be written in standard LaTeX format, enclosed within `$$...$$` or `$...$`, to ensure proper rendering in .md files.
