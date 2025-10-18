#!/usr/bin/env python
"""
Standalone script to run the GödelOS test runner.

This script provides a convenient way to run the test runner from the command line.
It can be executed directly or through the Python interpreter.

Usage:
    ./run_tests.py [options]
    python run_tests.py [options]
"""

import sys
from pathlib import Path

# Add repo root to Python path so godelOS can be imported
repo_root = Path(__file__).parent.parent.absolute()
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from godelOS.test_runner.cli import main

if __name__ == "__main__":
    sys.exit(main())