# Step 2: Circuit Equation Formulation

Based on the circuit structure described above, formulate the complete set of circuit equations in the s-domain to prepare for solving the transfer function.

## 1. Formulation Principles
To solve for the transfer function $H(s) = V_o(s)/V_i(s)$, we systematically formulate the circuit equations using KCL (nodal voltage method).

## 2. Variables to Use
When formulating the circuit equations, use the original physically meaningful variables (i.e., the variable names at the beginning of each line in the netlist). Specifically:
- Use original variables such as: G, Rprs, Cprs, R, C, etc.
- Do not substitute the actual design variables and parameters at this stage, such as the relationships $R_{{prs}} = A/G$, $C_{{prs}} = G_{{next}}/\omega_t$, etc.
- The transconductance G itself is a positive value; the sign before G indicates the phase of that amplifier stage and must be carefully considered when formulating equations. More specifically, when reading the netlist, pay close attention to whether the current at each node is flowing in or out.
    - Example 1:
    `G_1 Node1 NodeGround NodeInput NodeGround 'G_1'`
    represents a transconductance stage with input at NodeInput, output at Node1, and a value of G_1. Since there is **no negative sign** before G_1, the output current flows from Node1 to NodeGround, making this an **inverting stage**.
    - Example 2:
    `G_1 Node1 NodeGround NodeInput NodeGround '-G_1'`
    represents a transconductance stage with input at NodeInput, output at Node1, and a value of G_1. Since there **is a negative sign** before G_1, negative current flows from Node1 to NodeGround, making this a **non-inverting stage**.

## 3. Whether to Reduce
During the process of formulating circuit equations, remain unbiased and do not consider reductions based on the order of magnitude of variables.

## 4. Format for Extracted Target Content
After carefully analyzing the circuit and formulating the equations for each node, please summarize the complete set of circuit equations at the end, placing them between the `<raw_eq>` and `</raw_eq>` tags as the final answer for this step. This facilitates extraction and maintenance as a key field.

## 5. Additional Notes
- All formulas should be written in standard LaTeX format, enclosed within `$$...$$` or `$...$`, to ensure proper rendering in .md files.
- Ensure completeness of the equation set, including KCL equations for all nodes.