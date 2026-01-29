# Step 1: Circuit Topology Interpretation

Please read the following HSPICE netlist of a behavioral-level operational amplifier and describe its circuit structure in natural language.

## Netlist Content
<netlist>
{netlist_content}
</netlist>

## 1. Netlist Modeling Methodology

### 1.1 Transconductance Stage
A transconductance stage typically consists of an ideal transconductance element itself, along with the parasitic resistance and parasitic capacitance at its output:

- **G (Ideal Transconductance)**: Components prefixed with G represent ideal transconductance elements, which are independent design variables (the transconductance value itself is positive; the sign in the netlist indicates its phase).
    - Example 1: 
    `G_1 Node1 NodeGround NodeInput NodeGround 'G_1'`
    represents a transconductance stage with input at NodeInput, output at Node1, and a value of G_1. Since there is **no negative sign** before G_1, the output current flows from Node1 to NodeGround, making this an **inverting stage**.
    - Example 2: 
    `G_1 Node1 NodeGround NodeInput NodeGround '-G_1'` 
    represents a transconductance stage with input at NodeInput, output at Node1, and a value of G_1. Since there **is a negative sign** before G_1, negative current flows from Node1 to NodeGround, making this a **non-inverting stage**.

- **Rprs (Parasitic Resistance)**: Components prefixed with Rprs represent the parasitic resistance at the output of a transconductance stage G. It is derived indirectly from the stage gain A and the stage transconductance G:
$$R_{{prs}} = \frac{{A}}{{G}}$$

- **Cprs (Parasitic Capacitance)**: Components prefixed with Cprs represent the parasitic capacitance at the output of a transconductance stage G. Essentially, this is the input parasitic capacitance of the next transconductance stage $G_{{next}}$:$$C_{{prs}} = \frac{{G_{{next}}}}{{\omega_t}} = G_{{next}} \cdot \frac{{5n}}{{2\pi}}$$
    - Here, $\omega_t$ is an empirical value for the intrinsic frequency of transistors under the current process technology.
    - Specifically, we assume $f_t = 200\text{{M}}Hz$ (or equivalently $T = 5\text{{n}}s$), thus: $\omega_t = 2\pi f = 2 \times 3.14 \times 200\text{{M}}~\text{{rad/s}} = 1.256 \times 10^9~\text{{rad/s}}$.
    - **Important Note**: If a transconductance stage has no $G_{{next}}$ (i.e., it is already the output stage), then there is no $C_{{prs}}$ associated with it.

### 1.2 Independent Resistors R
Independent resistors are components prefixed with R but not Rprs. These include various compensation resistors and the load resistor $R_L$, among others.

### 1.3 Independent Capacitors C
Independent capacitors are components prefixed with C but not Cprs. These include various compensation capacitors and the load capacitor $C_L$, among others.

## 2. Structure Description Format
Provide a detailed natural language description of all signal paths from input to output (including all feedback paths), covering all circuit nodes and edges involved. This prepares for the next step of formulating circuit equations.

## 3. Additional Requirements
All formulas should be written in standard LaTeX format, enclosed within `$$...$$` or `$...$`, to ensure proper rendering in .md files.