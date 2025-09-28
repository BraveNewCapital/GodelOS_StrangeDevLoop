#!/usr/bin/env python3
"""
Demo script showcasing the different modes of the unified test runner.

This script demonstrates the various verbosity modes available in the test runner:
- Concise mode: Only shows failures and brief success messages
- Default mode: Balanced output with category summaries
- Verbose mode: Detailed test information and discovery details

Usage:
    python demo_test_runner_modes.py
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd: str, description: str) -> None:
    """Run a command and display its output with a description."""
    print(f"\n{'='*80}")
    print(f"🔍 {description}")
    print(f"{'='*80}")
    print(f"Command: {cmd}")
    print("-" * 80)
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        print(f"Exit code: {result.returncode}")
    except subprocess.TimeoutExpired:
        print("⚠️ Command timed out after 60 seconds")
    except Exception as e:
        print(f"❌ Error running command: {e}")

def main():
    """Demonstrate different test runner modes."""
    print("🚀 GödelOS Test Runner Mode Demonstration")
    print("This will showcase different verbosity levels with smoke tests.\n")
    
    # Ensure we're in the right directory
    if not Path("unified_test_runner.py").exists():
        print("❌ Please run this script from the GödelOS root directory")
        sys.exit(1)
    
    # Base command setup
    base_cmd = "source godelos_venv/bin/activate && python unified_test_runner.py --categories smoke"
    
    # Demo 1: Concise Mode
    run_command(
        f"{base_cmd} --concise",
        "CONCISE MODE: Minimal output - only failures and success message"
    )
    
    # Demo 2: Default Mode  
    run_command(
        base_cmd,
        "DEFAULT MODE: Balanced output with category summaries"
    )
    
    # Demo 3: Verbose Mode
    run_command(
        f"{base_cmd} --verbose",
        "VERBOSE MODE: Detailed output with all test information"
    )
    
    # Demo 4: List Only Mode
    run_command(
        f"source godelos_venv/bin/activate && python unified_test_runner.py --list-only | head -20",
        "LIST-ONLY MODE: Discovery without execution"
    )
    
    print(f"\n{'='*80}")
    print("🎯 Summary of Test Runner Modes:")
    print("• --concise: Ultra-minimal, perfect for CI/CD")
    print("• (default): Balanced information for development")  
    print("• --verbose: Full details for debugging")
    print("• --list-only: Discovery without execution")
    print("• Interactive mode: Dynamic selection with appropriate verbosity")
    print("=" * 80)

if __name__ == "__main__":
    main()