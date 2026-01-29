"""
P2M Analysis Steps Module

Contains implementations of 9 analysis steps:
1. Circuit topology interpretation
2. Circuit equation formulation
3. Unbiased transfer function derivation
4. Design variable substitution and simplification
5. Pole and zero extraction
6. Pole and zero positioning and metric derivation
7. White-box optimization programming
8. Simulation verification
9. Design result analysis and decision-making
"""

from .step1_circuit_topology_interpretation import step1_read_netlist
from .step2_circuit_equation_formulation import step2_list_equations
from .step3_unbiased_transfer_function_derivation import step3_solve_transfer_function
from .step4_design_variable_substitution_and_simplification import step4_substitute_simplify
from .step5_pole_and_zero_extraction import step5_factorize_reduce
from .step6_pole_and_zero_positioning_and_metric_derivation import step6_functional_implementation
from .step7_white_box_optimization_programming import step7_white_box_optimization
from .step8_simulation_verification import step8_generate_numerical_netlist
from .step9_design_result_analysis_and_decision_making import step9_intelligent_comparison

__all__ = [
    'step1_read_netlist',
    'step2_list_equations',
    'step3_solve_transfer_function',
    'step4_substitute_simplify',
    'step5_factorize_reduce',
    'step6_functional_implementation',
    'step7_white_box_optimization',
    'step8_generate_numerical_netlist',
    'step9_intelligent_comparison',
]
