#!/usr/bin/env python3
"""
P2M Parameter Design Script

Used for parameter design (parameter optimization) of given circuit topologies.
This is a simplified script specifically for running the P2M analysis flow independently.

Usage:
    # Use default netlist and default design requirements
    python3 scripts/run_p2m_design.py
    
    # Specify netlist file
    python3 scripts/run_p2m_design.py --netlist examples/tcasi2000/SMCNR.sp
    
    # Specify netlist file and design requirements
    python3 scripts/run_p2m_design.py \
        --netlist examples/tcasi2000/SMCNR.sp \
        --gain-min 60 \
        --gbw-min 0.5 \
        --pm-min 45 \
        --pm-max 90 \
        --power-max 250
    
    # Specify iteration count
    python3 scripts/run_p2m_design.py --netlist examples/tcasi2000/SMCNR.sp --iterations 5
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core import PipelineConfig, DesignRequirements, generate_output_dir, ResultFormatter
from p2m.pipeline import CircuitAnalysisPipeline


def load_netlist(filepath: str) -> str:
    """Load netlist from file"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Netlist file not found: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def extract_topology_name(netlist_path: str) -> str:
    """
    Extract topology name from netlist file path.
    
    Extracts the filename (without extension) from the netlist file path as the topology name.
    Example: Extract "DFCFC" from "examples/tcasi2000/DFCFC.sp"
    
    Args:
        netlist_path: Netlist file path
    
    Returns:
        Topology name (uppercase)
    """
    # Get filename (without path)
    filename = os.path.basename(netlist_path)
    # Remove extension
    topology_name = os.path.splitext(filename)[0]
    # Convert to uppercase for consistency
    return topology_name.upper()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="P2M Parameter Design Tool - Parameter optimization for given topology",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  # Use default netlist and design requirements
  python3 scripts/run_p2m_design.py
  
  # Specify netlist file
  python3 scripts/run_p2m_design.py --netlist examples/tcasi2000/SMCNR.sp
  
  # Complete parameter example
  python3 scripts/run_p2m_design.py \\
      --netlist examples/tcasi2000/SMCNR.sp \\
      --gain-min 60 \\
      --gbw-min 0.5 \\
      --pm-min 45 \\
      --pm-max 90 \\
      --power-max 250 \\
      --iterations 5
        """
    )
    
    # Netlist file parameter
    parser.add_argument(
        '--netlist',
        type=str,
        default='examples/tcasi2000/SMCNR.sp',
        help='Netlist file path (default: examples/tcasi2000/SMCNR.sp)'
    )
    
    # Design requirement parameters
    parser.add_argument(
        '--gain-min',
        type=float,
        default=60.0,
        help='Minimum gain (dB, default: 60.0)'
    )
    
    parser.add_argument(
        '--gbw-min',
        type=float,
        default=0.5,
        help='Minimum gain-bandwidth product (MHz, default: 0.5)'
    )
    
    parser.add_argument(
        '--pm-min',
        type=float,
        default=45.0,
        help='Minimum phase margin (degrees, default: 45.0)'
    )
    
    parser.add_argument(
        '--pm-max',
        type=float,
        default=90.0,
        help='Maximum phase margin (degrees, default: 90.0)'
    )
    
    parser.add_argument(
        '--pm-ideal',
        type=float,
        default=60.0,
        help='Ideal phase margin (degrees, default: 60.0)'
    )
    
    parser.add_argument(
        '--power-max',
        type=float,
        default=250.0,
        help='Maximum power consumption (μW, default: 250.0)'
    )
    
    # P2M configuration parameters
    parser.add_argument(
        '--iterations',
        type=int,
        default=3,
        help='P2M maximum iteration count (default: 3)'
    )
    
    parser.add_argument(
        '--no-python-execution',
        action='store_true',
        help='Disable Python code execution (default: enabled)'
    )
    
    parser.add_argument(
        '--no-thinking-separation',
        action='store_true',
        help='Disable thinking separation (default: enabled)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory (default: auto-generate timestamp directory)'
    )
    
    # API configuration (optional)
    parser.add_argument(
        '--api-key',
        type=str,
        default=None,
        help='API key (default: use value from config file)'
    )
    
    parser.add_argument(
        '--base-url',
        type=str,
        default=None,
        help='API base URL (default: use value from config file)'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='Model to use (default: use value from config file)'
    )
    
    # HSPICE configuration (optional)
    parser.add_argument(
        '--hspice-path',
        type=str,
        default=None,
        help='Path to HSPICE executable (default: use value from config file)'
    )
    
    # gmid_map base path (optional)
    parser.add_argument(
        '--gmid-map-base',
        type=str,
        default=None,
        help='Base path of gmid_map tool (default: use env GMID_MAP_BASE or auto-detected relative path)'
    )
    
    args = parser.parse_args()
    
    # 1. Load netlist
    print("="*80)
    print("📋 Loading Netlist")
    print("="*80)
    try:
        netlist = load_netlist(args.netlist)
        print(f"✅ Successfully loaded netlist: {args.netlist}")
        print(f"   Netlist length: {len(netlist)} characters")
    except Exception as e:
        print(f"❌ Failed to load netlist: {e}")
        sys.exit(1)
    
    # 2. Create design requirements
    design_req = DesignRequirements(
        gain_min_db=args.gain_min,
        gbw_min_mhz=args.gbw_min,
        pm_min_deg=args.pm_min,
        pm_max_deg=args.pm_max,
        pm_ideal_deg=args.pm_ideal,
        power_max_uw=args.power_max
    )
    
    # 3. Create configuration (including design requirements)
    print("\n" + "="*80)
    print("⚙️  System Configuration")
    print("="*80)
    config_kwargs = {
        'enable_python_execution': not args.no_python_execution,
        'enable_thinking_separation': not args.no_thinking_separation,
        'p2m_max_iterations': args.iterations,
        'full_pipeline_max_iterations': args.iterations,
        'error_threshold': 0.1,
        'enable_circuit_data_collection': True,
        'design_requirements': design_req  # Design requirements as part of config
    }
    
    if args.output_dir:
        config_kwargs['output_dir'] = args.output_dir
    else:
        # Extract topology name from netlist path
        topology_name = extract_topology_name(args.netlist)
        config_kwargs['output_dir'] = generate_output_dir(topology_suffix=topology_name)
    
    if args.api_key:
        config_kwargs['api_key'] = args.api_key
    
    if args.model:
        config_kwargs['model'] = args.model
    
    if args.base_url:
        config_kwargs['base_url'] = args.base_url
    
    if args.hspice_path:
        config_kwargs['hspice_path'] = args.hspice_path
    
    # Optional gmid_map base path (can also be provided via env in ResultFormatter)
    if args.gmid_map_base:
        config_kwargs['gmid_map_base'] = args.gmid_map_base
    
    # Add netlist_path to config for result formatter to identify circuit type
    config_kwargs['netlist_path'] = args.netlist
    
    config = PipelineConfig(**config_kwargs)
    
    # Display configuration information (including design requirements)
    print(f"   Output Directory: {config.output_dir}")
    print(f"   API: {config.base_url}")
    print(f"   Model: {config.model}")
    print(f"   P2M Max Iterations: {config.p2m_max_iterations}")
    print(f"   Python Code Execution: {'Enabled' if config.enable_python_execution else 'Disabled'}")
    print(f"   Thinking Separation: {'Enabled' if config.enable_thinking_separation else 'Disabled'}")
    print("\n📐 Design Requirements (Performance Boundaries):")
    print(f"   Minimum Gain: {config.design_requirements.gain_min_db} dB")
    print(f"   Minimum GBW: {config.design_requirements.gbw_min_mhz} MHz")
    print(f"   Phase Margin Range: {config.design_requirements.pm_min_deg}° - {config.design_requirements.pm_max_deg}° (Ideal: {config.design_requirements.pm_ideal_deg}°)")
    print(f"   Maximum Power: {config.design_requirements.power_max_uw} μW")
    
    # 4. Run P2M analysis
    print("\n" + "="*80)
    print("🚀 Starting P2M Parameter Design")
    print("="*80)
    print(f"   Netlist: {args.netlist}")
    print(f"   Iterations: {args.iterations}")
    print("="*80)
    
    # Record start time
    start_time = time.time()
    
    try:
        # Create pipeline (design requirements already included in config)
        pipeline = CircuitAnalysisPipeline(config)
        
        # Run P2M chain
        results = pipeline.run_p2m_chain(netlist)
        
        # Calculate total time
        total_time_minutes = (time.time() - start_time) / 60.0
        results['total_time_minutes'] = total_time_minutes
        
        # 5. Display results
        print("\n" + "="*80)
        print("📊 P2M Parameter Design Results")
        print("="*80)
        
        success = results.get('success', False)
        iteration_count = results.get('iteration_count', 0)
        satisfies_requirements = results.get('satisfies_requirements', False)
        
        print(f"Analysis Status: {'✅ Success' if success else '❌ Failed'}")
        print(f"Iteration Count: {iteration_count}")
        print(f"Satisfies Design Requirements: {'✅ Yes' if satisfies_requirements else '❌ No'}")
        
        # Display performance metrics of best iteration
        if results.get('best_iteration'):
            best_iter = results['best_iteration']
            print(f"\n📈 Best Iteration Performance Metrics:")
            print(f"   Iteration Number: {best_iter.get('iteration', 'N/A')}")
            
            quality_info = best_iter.get('quality_info', {})
            if quality_info.get('has_performance', False):
                perf = quality_info['performance']
                design_req = config.design_requirements
                print(f"\n   Performance Metrics:")
                print(f"     - FoM: {perf.get('fom', 0):.2f}")
                print(f"     - Gain: {perf.get('gain', 0):.2f} dB (Requirement: > {design_req.gain_min_db} dB)")
                print(f"     - GBW: {perf.get('ugf', 0)/1e6:.2f} MHz (Requirement: > {design_req.gbw_min_mhz} MHz)")
                print(f"     - Phase Margin: {perf.get('phase_margin', 0):.2f}° (Requirement: {design_req.pm_min_deg}° - {design_req.pm_max_deg}°)")
                print(f"     - Power: {perf.get('power', 0)*1e6:.2f} μW (Requirement: < {design_req.power_max_uw} μW)")
        
        # Display final decision
        if results.get('final_decision'):
            decision = results['final_decision']
            if isinstance(decision, dict):
                decision_str = decision.get('decision', 'N/A')
                reason = decision.get('reason', '')
            else:
                decision_str = decision
                reason = ''
            
            print(f"\n🎯 Final Decision: {decision_str}")
            if reason:
                print(f"   Reason: {reason}")
        
        # Display output directory
        print(f"\n📁 All result files saved to:")
        print(f"   {config.output_dir}")
        
        # Display thinking separation effect
        if config.enable_thinking_separation:
            final_stats = pipeline.monitor_context_size()
            print(f"\n💾 Context Management:")
            print(f"   Thinking Separation Space Saved: {final_stats.get('space_saved_percentage', 0):.1f}%")
        
        # 6. Save final results
        print("\n" + "="*80)
        print("📊 Saving Final Results")
        print("="*80)
        try:
            formatter = ResultFormatter(
                output_dir=config.output_dir,
                design_req=design_req,
                config=config
            )
            report_file, json_file = formatter.save_results(results)
            print(f"✅ Results saved:")
            print(f"   Report File: {report_file}")
            print(f"   JSON File: {json_file}")
        except Exception as e:
            print(f"⚠️  Warning: Error saving final results: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "="*80)
        print("🎉 P2M Parameter Design Complete!")
        print("="*80)
        
        return results
        
    except KeyboardInterrupt:
        print("\n⚠️  User interrupted analysis")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ P2M parameter design failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()




