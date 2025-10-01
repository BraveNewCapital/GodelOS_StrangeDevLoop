#!/usr/bin/env python3
"""
Test runner for self-modification system tests.

Usage:
    python run_metacognition_tests.py              # Run all tests
    python run_metacognition_tests.py --unit       # Unit tests only
    python run_metacognition_tests.py --integration # Integration tests only
    python run_metacognition_tests.py --coverage   # With coverage report
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and report results."""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}\n")
    
    # Set PYTHONPATH to include the project root
    import os
    env = os.environ.copy()
    project_root = str(Path(__file__).parent)
    env['PYTHONPATH'] = project_root + os.pathsep + env.get('PYTHONPATH', '')
    
    result = subprocess.run(cmd, shell=True, env=env)
    
    if result.returncode != 0:
        print(f"\n❌ {description} FAILED")
        return False
    else:
        print(f"\n✅ {description} PASSED")
        return True


def main():
    parser = argparse.ArgumentParser(description="Run self-modification system tests")
    parser.add_argument(
        "--unit",
        action="store_true",
        help="Run unit tests only",
    )
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Run integration tests only (requires running backend)",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip slow tests",
    )
    
    args = parser.parse_args()
    
    # Determine test path
    test_dir = Path(__file__).parent / "tests" / "backend"
    
    # Build pytest command
    pytest_cmd = ["pytest"]
    
    # Add verbosity
    if args.verbose:
        pytest_cmd.append("-v")
    else:
        pytest_cmd.append("-q")
    
    # Add coverage
    if args.coverage:
        pytest_cmd.extend([
            "--cov=backend.metacognition_service",
            "--cov-report=html:test_output/metacognition_coverage",
            "--cov-report=term-missing",
        ])
    
    # Add markers
    if args.unit:
        pytest_cmd.extend(["-m", '"not integration and not requires_backend"'])
    elif args.integration:
        pytest_cmd.extend(["-m", '"integration or requires_backend"'])
    
    # Skip slow tests if requested
    if args.fast:
        pytest_cmd.extend(["-m", '"not slow"'])
    
    # Add test files
    pytest_cmd.append(str(test_dir / "test_metacognition_service.py"))
    
    # Only add integration tests if explicitly requested or running all tests
    if args.integration or (not args.unit and not args.integration):
        pytest_cmd.append(str(test_dir / "test_metacognition_integration.py"))
    
    # Run tests
    cmd = " ".join(pytest_cmd)
    success = run_command(cmd, "Self-Modification System Tests")
    
    # Print summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    if success:
        print("\n✅ All tests PASSED!")
        if args.coverage:
            print(f"\n📊 Coverage report: test_output/metacognition_coverage/index.html")
    else:
        print("\n❌ Some tests FAILED")
        print("Check output above for details")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
