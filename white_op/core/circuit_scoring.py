"""
Circuit scoring module (circuit_scoring)

Provides comprehensive scoring system, including white-box prediction accuracy and constraint satisfaction scoring.
"""

import re
from typing import Dict, Optional
from .data_models import CircuitData
from .config import DesignRequirements

# Score2 exponent weight configuration (only effective when all constraints are satisfied)
EXPONENT_WEIGHT_GAIN = 0.1   # Exponent weight for Gain
EXPONENT_WEIGHT_GBW = 0.7    # Exponent weight for GBW
EXPONENT_WEIGHT_PM = 1.0     # Exponent weight for PM
EXPONENT_WEIGHT_POWER = 0.7  # Exponent weight for Power


def _get_execution_log_string(execution_result) -> str:
    """
    Extract string content from execution_result (may be string or dict).
    
    Reuses logic from p2m/pipeline.py _get_execution_log_string.
    
    Args:
        execution_result: Can be string or dict (containing 'stdout' field)
    
    Returns:
        String content
    """
    if isinstance(execution_result, dict):
        # If dict, extract stdout field
        return execution_result.get('stdout', '')
    elif isinstance(execution_result, str):
        # If string, try to extract stdout portion
        if 'stdout:' in execution_result:
            parts = execution_result.split('stderr:', 1)
            return parts[0].replace('stdout:', '').strip()
        else:
            return execution_result
    else:
        return str(execution_result) if execution_result else ''


def extract_whitebox_performance(circuit_data: CircuitData) -> Optional[Dict[str, float]]:
    """
    Read white-box predicted values from CircuitData's whitebox_predicted_performance field.
    
    Args:
        circuit_data: CircuitData object
    
    Returns:
        White-box predicted performance dict, format: {'gain': float, 'gbw': float, 'pm': float, 'power': float}
        Returns None if field doesn't exist
        
    Note: All units are unified to SI units:
        - gain: dB
        - gbw: Hz (consistent with ugf unit in simulation_results)
        - pm: degrees
        - power: W (consistent with power unit in simulation_results)
    """
    if not circuit_data.whitebox_predicted_performance:
        return None
    
    # Convert field names (from whitebox_gain etc. to gain etc.)
    whitebox_perf = circuit_data.whitebox_predicted_performance
    result = {}
    if 'whitebox_gain' in whitebox_perf:
        result['gain'] = whitebox_perf['whitebox_gain']
    # Support old and new field names (backward compatible)
    if 'whitebox_gbw' in whitebox_perf:
        result['gbw'] = whitebox_perf['whitebox_gbw']  # Unit: Hz
    elif 'whitebox_gbw_mhz' in whitebox_perf:
        # Backward compatible: if old field name, convert units
        result['gbw'] = whitebox_perf['whitebox_gbw_mhz'] * 1e6  # MHz -> Hz
    if 'whitebox_pm' in whitebox_perf:
        result['pm'] = whitebox_perf['whitebox_pm']
    # Support old and new field names (backward compatible)
    if 'whitebox_power' in whitebox_perf:
        result['power'] = whitebox_perf['whitebox_power']  # Unit: W
    elif 'whitebox_power_uw' in whitebox_perf:
        # Backward compatible: if old field name, convert units
        result['power'] = whitebox_perf['whitebox_power_uw'] * 1e-6  # μW -> W
    
    return result if result else None


def calculate_prediction_accuracy_score(circuit_data: CircuitData) -> float:
    """
    Calculate score1 (white-box prediction accuracy).
    
    alpha_i = 1 - abs(whitebox_i - blackbox_i) / max(blackbox_i, epsilon)
    score1 = alpha_gain × alpha_gbw × alpha_pm
    
    Args:
        circuit_data: CircuitData object
    
    Returns:
        score1 value, range [0, 1], higher means more accurate prediction
        Returns 1.0 if cannot calculate (indicates prediction accuracy unknown, doesn't affect scoring)
    """
    # Extract white-box predicted values
    whitebox_perf = extract_whitebox_performance(circuit_data)
    if not whitebox_perf:
        # If cannot extract white-box predicted values, return 1.0 (doesn't affect scoring)
        return 1.0
    
    # Get actual values from simulation_results
    if not circuit_data.simulation_results:
        return 1.0
    
    sim_results = circuit_data.simulation_results
    
    # Calculate accuracy for each metric
    epsilon = 1e-10  # Avoid division by zero
    
    # Gain accuracy (unit: dB)
    if 'gain' in whitebox_perf and 'gain' in sim_results:
        gain_whitebox = whitebox_perf['gain']
        gain_blackbox = sim_results.get('gain', 0)
        if gain_blackbox > epsilon:
            alpha_gain = 1.0 - abs(gain_whitebox - gain_blackbox) / max(abs(gain_blackbox), epsilon)
            alpha_gain = max(0.0, min(1.0, alpha_gain))  # Clamp to [0, 1]
        else:
            alpha_gain = 1.0 if abs(gain_whitebox - gain_blackbox) < epsilon else 0.0
    else:
        alpha_gain = 1.0
    
    # GBW accuracy (unit: Hz, unified to SI units, no conversion needed)
    if 'gbw' in whitebox_perf and 'ugf' in sim_results:
        gbw_whitebox_hz = whitebox_perf['gbw']  # Unit: Hz
        gbw_blackbox_hz = sim_results.get('ugf', 0)  # Unit: Hz
        if gbw_blackbox_hz > epsilon:
            alpha_gbw = 1.0 - abs(gbw_whitebox_hz - gbw_blackbox_hz) / max(gbw_blackbox_hz, epsilon)
            alpha_gbw = max(0.0, min(1.0, alpha_gbw))  # Clamp to [0, 1]
        else:
            alpha_gbw = 1.0 if abs(gbw_whitebox_hz - gbw_blackbox_hz) < epsilon else 0.0
    else:
        alpha_gbw = 1.0
    
    # PM accuracy (unit: degrees, unified, no conversion needed)
    if 'pm' in whitebox_perf and 'phase_margin' in sim_results:
        pm_whitebox = whitebox_perf['pm']  # Unit: degrees
        pm_blackbox = sim_results.get('phase_margin', 0)  # Unit: degrees
        if pm_blackbox > epsilon:
            alpha_pm = 1.0 - abs(pm_whitebox - pm_blackbox) / max(pm_blackbox, epsilon)
            alpha_pm = max(0.0, min(1.0, alpha_pm))  # Clamp to [0, 1]
        else:
            alpha_pm = 1.0 if abs(pm_whitebox - pm_blackbox) < epsilon else 0.0
    else:
        alpha_pm = 1.0
    
    # Power accuracy (unit: W, unified to SI units, no conversion needed)
    # Note: Power is not included in current score1 calculation, but keep this logic for future use
    if 'power' in whitebox_perf and 'power' in sim_results:
        power_whitebox_w = whitebox_perf['power']  # Unit: W
        power_blackbox_w = sim_results.get('power', 0)  # Unit: W
        # Currently not used in score1 calculation, but can be used for other analysis
    
    # score1 = alpha_gain × alpha_gbw × alpha_pm
    score1 = alpha_gain * alpha_gbw * alpha_pm
    return max(0.0, min(1.0, score1))  # Ensure in [0, 1] range


def calculate_constraint_satisfaction_score(
    circuit_data: CircuitData, 
    design_requirements: DesignRequirements
) -> float:
    """
    Calculate score2 (constraint satisfaction).
    
    For single-ended constraints (gain, gbw, power): beta_i = actual / required
    For double-ended constraint (PM): beta_pm = min(actual/pm_min, pm_max/actual)
    
    When all beta_i ≥ 1: score2 = (beta_gain^0.1) × (beta_gbw^0.7) × (beta_pm^1.0) × (beta_power^0.7)
    When any beta_i < 1: score2 = min(beta_i) (short board effect)
    
    Args:
        circuit_data: CircuitData object
        design_requirements: DesignRequirements object
    
    Returns:
        score2 value, range [0, +∞), higher means better constraint satisfaction
        Returns 0.0 if cannot calculate
    """
    if not circuit_data.simulation_results:
        return 0.0
    
    sim_results = circuit_data.simulation_results
    req = design_requirements
    
    # Extract actual values
    gain_actual = sim_results.get('gain', 0)  # dB
    ugf_actual = sim_results.get('ugf', 0)  # Hz
    gbw_actual_mhz = ugf_actual / 1e6  # Convert to MHz
    pm_actual = sim_results.get('phase_margin', 0)  # degrees
    power_actual_w = sim_results.get('power', 0)  # W
    power_actual_uw = power_actual_w * 1e6  # Convert to μW
    
    # Calculate satisfaction for each metric
    beta_values = {}
    
    # Gain satisfaction (single-ended constraint: actual / required)
    if req.gain_min_db > 0:
        beta_gain = gain_actual / req.gain_min_db
        beta_values['gain'] = beta_gain
    else:
        beta_values['gain'] = 1.0 if gain_actual >= 0 else 0.0
    
    # GBW satisfaction (single-ended constraint: actual / required)
    if req.gbw_min_mhz > 0:
        beta_gbw = gbw_actual_mhz / req.gbw_min_mhz
        beta_values['gbw'] = beta_gbw
    else:
        beta_values['gbw'] = 1.0 if gbw_actual_mhz >= 0 else 0.0
    
    # PM satisfaction (double-ended constraint: min(actual/pm_min, pm_max/actual))
    if req.pm_min_deg > 0 and req.pm_max_deg > req.pm_min_deg:
        if pm_actual < req.pm_min_deg:
            # Below minimum
            beta_pm = pm_actual / req.pm_min_deg
        elif pm_actual > req.pm_max_deg:
            # Above maximum
            beta_pm = req.pm_max_deg / pm_actual
        else:
            # Within range, calculate satisfaction (closer to ideal is better)
            # Use min(actual/pm_min, pm_max/actual) to ensure ≥1 when in range
            beta_pm = min(pm_actual / req.pm_min_deg, req.pm_max_deg / pm_actual)
        beta_values['pm'] = beta_pm
    else:
        beta_values['pm'] = 1.0 if req.pm_min_deg <= pm_actual <= req.pm_max_deg else 0.0
    
    # Power satisfaction (single-ended constraint: actual / required, note power is better when lower, so required / actual)
    if req.power_max_uw > 0:
        if power_actual_uw > 0:
            beta_power = req.power_max_uw / power_actual_uw  # Lower power, higher beta
        else:
            beta_power = 0.0
        beta_values['power'] = beta_power
    else:
        beta_values['power'] = 1.0 if power_actual_uw >= 0 else 0.0
    
    # Calculate score2
    beta_list = list(beta_values.values())
    if not beta_list:
        return 0.0
    
    # Check if any beta_i < 1
    min_beta = min(beta_list)
    if min_beta < 1.0:
        # Some constraints not satisfied, use short board effect
        score2 = min_beta
    else:
        # All constraints satisfied, use exponent-weighted product
        # score2 = (beta_gain^w_gain) × (beta_gbw^w_gbw) × (beta_pm^w_pm) × (beta_power^w_power)
        score2 = (beta_values['gain'] ** EXPONENT_WEIGHT_GAIN) * \
                 (beta_values['gbw'] ** EXPONENT_WEIGHT_GBW) * \
                 (beta_values['pm'] ** EXPONENT_WEIGHT_PM) * \
                 (beta_values['power'] ** EXPONENT_WEIGHT_POWER)
    
    return max(0.0, score2)  # Ensure non-negative


def calculate_comprehensive_score(
    circuit_data: CircuitData,
    design_requirements: DesignRequirements
) -> Dict[str, float]:
    """
    Calculate comprehensive score Score = score1 × score2.
    
    Args:
        circuit_data: CircuitData object
        design_requirements: DesignRequirements object
    
    Returns:
        Dict containing the following fields:
        - 'comprehensive_score': Comprehensive score (score1 × score2)
        - 'prediction_accuracy_score': score1 (white-box prediction accuracy)
        - 'constraint_satisfaction_score': score2 (constraint satisfaction)
        - 'score1': Alias for score1
        - 'score2': Alias for score2
    """
    score1 = calculate_prediction_accuracy_score(circuit_data)
    score2 = calculate_constraint_satisfaction_score(circuit_data, design_requirements)
    
    comprehensive_score = score1 * score2
    
    return {
        'comprehensive_score': comprehensive_score,
        'prediction_accuracy_score': score1,
        'constraint_satisfaction_score': score2,
        'score1': score1,
        'score2': score2
    }

