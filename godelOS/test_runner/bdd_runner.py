#!/usr/bin/env python3
"""
BDD Test Runner for GödelOS - Clean real-time specification execution.

This runner executes tests with BDD-style formatting, presenting them
as executable specifications with Given/When/Then structure.
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add repo root to path
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from godelOS.test_runner.bdd_formatter import BDDFormatter
from godelOS.test_runner.config_manager import ConfigurationManager
from godelOS.test_runner.test_discovery import TestDiscovery
from godelOS.test_runner.docstring_extractor import DocstringExtractor
import pytest


class BDDTestRunner:
    """BDD-style test runner with clean real-time output."""
    
    def __init__(self, config: Any):
        """Initialize the BDD test runner."""
        self.config = config
        self.formatter = BDDFormatter(config)
        self.discovery = TestDiscovery(config)
        self.docstring_extractor = DocstringExtractor(config)
        self.stats = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'xpassed': 0,
            'xfailed': 0,
            'errors': 0,
            'duration': 0,
        }
        self.start_time = None
    
    def run(self, pattern: Optional[str] = None, specific_tests: Optional[List[str]] = None) -> int:
        """
        Run tests with BDD formatting.
        
        Args:
            pattern: Glob pattern for test files
            specific_tests: List of specific test node IDs to run
            
        Returns:
            Exit code (0 for success, 1 for failures)
        """
        self.start_time = time.time()
        
        # Discover tests
        test_files = self.discovery.discover_test_files()
        
        # Filter by pattern if provided
        if pattern:
            import fnmatch
            test_files = [f for f in test_files if fnmatch.fnmatch(f, pattern)]
        
        if not test_files:
            print(self.formatter.colorize("No tests found matching criteria", 'yellow'))
            return 0
        
        # Parse test files to get metadata
        parsed_tests = []
        for test_file in test_files:
            try:
                file_test_info = self.discovery.parse_test_file(test_file)
                # Check if parsing was successful and has test items
                if file_test_info and 'test_items' in file_test_info and file_test_info['test_items']:
                    parsed_tests.append(file_test_info)
            except Exception as e:
                print(self.formatter.colorize(f"Error parsing {test_file}: {e}", 'red'))
        
        # Run tests file by file for clean BDD output
        exit_code = 0
        for test_file_info in parsed_tests:
            test_path = test_file_info['file_path']
            
            # Print feature header
            self.formatter.print_feature_header(test_path)
            
            # Run each test in the file
            for test_item in test_file_info['test_items']:
                test_node_id = test_item['full_name']
                
                # Skip if specific tests provided and this isn't one
                if specific_tests and test_node_id not in specific_tests:
                    continue
                
                # Extract docstring
                docstring = test_item.get('doc', '')
                
                # Print scenario header
                self.formatter.print_scenario_header(test_item['name'], docstring)
                
                # Show running status
                self.formatter.print_streaming_update(test_item['name'], 'running')
                
                # Run the test
                result = self._run_single_test(test_node_id)
                
                # Update stats
                self.stats['total'] += 1
                status = result['status']
                if status in self.stats:
                    self.stats[status] += 1
                
                # Print result
                self.formatter.print_test_result(
                    test_item['name'],
                    status,
                    result['duration'],
                    result.get('error_msg')
                )
                
                if status in ('failed', 'error'):
                    exit_code = 1
        
        # Print final summary
        self.stats['duration'] = time.time() - self.start_time
        self.formatter.print_final_summary(self.stats)
        
        return exit_code
    
    def _run_single_test(self, node_id: str) -> Dict[str, Any]:
        """
        Run a single test and capture its result.
        
        Args:
            node_id: Full pytest node ID
            
        Returns:
            Dictionary with status, duration, and optional error_msg
        """
        start_time = time.time()
        
        # Custom pytest plugin to capture results
        class ResultCapture:
            def __init__(self):
                self.status = 'passed'
                self.error_msg = None
                
            def pytest_runtest_logreport(self, report):
                # Debug: print what we're getting
                # print(f"DEBUG: when={report.when}, outcome={report.outcome}, hasattr(wasxfail)={hasattr(report, 'wasxfail')}")
                
                if report.when == 'call' or (report.when == 'setup' and report.outcome != 'passed'):
                    if report.outcome == 'failed':
                        self.status = 'failed'
                        if hasattr(report, 'longreprtext'):
                            self.error_msg = report.longreprtext
                        elif hasattr(report, 'longrepr'):
                            self.error_msg = str(report.longrepr)
                    elif report.outcome == 'skipped':
                        # Check if this is an xfail before marking as skipped
                        if hasattr(report, 'wasxfail'):
                            self.status = 'xfailed'
                            self.error_msg = report.wasxfail if report.wasxfail else None
                        else:
                            self.status = 'skipped'
                            if hasattr(report, 'longrepr') and len(report.longrepr) > 2:
                                self.error_msg = report.longrepr[2]
                    elif report.outcome == 'passed' and hasattr(report, 'wasxfail'):
                        self.status = 'xpassed'
        
        capture = ResultCapture()
        
        # Run pytest with minimal output
        pytest_args = [
            node_id,
            '-v',
            '--tb=short',
            '-p', 'no:warnings',
            '--no-header',
            '--no-summary',
            '-q',
            '--quiet',
            '--capture=no',  # Don't capture output
        ]
        
        try:
            # Suppress pytest output completely
            import os
            import sys
            from io import StringIO
            
            # Redirect stdout and stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = StringIO()
            sys.stderr = StringIO()
            
            pytest.main(pytest_args, plugins=[capture])
            
            # Restore stdout and stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        except Exception as e:
            capture.status = 'error'
            capture.error_msg = str(e)
        
        duration = time.time() - start_time
        
        return {
            'status': capture.status,
            'duration': duration,
            'error_msg': capture.error_msg,
        }


def main():
    """Main entry point for BDD test runner."""
    parser = argparse.ArgumentParser(
        description="GödelOS BDD Test Runner - Specification execution with clean output",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--pattern', '-p',
        help='Glob pattern for test files (e.g., "tests/spec_aligned/**")'
    )
    parser.add_argument(
        '--test', '-t',
        action='append',
        dest='tests',
        help='Specific test node ID to run (can be specified multiple times)'
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )
    parser.add_argument(
        '--no-emoji',
        action='store_true',
        help='Disable emoji in output'
    )
    parser.add_argument(
        '--silent',
        action='store_true',
        help='Suppress test logging output (cleaner BDD view)'
    )
    
    args = parser.parse_args()
    
    # Suppress test logging if requested
    if args.silent:
        import logging
        logging.getLogger('tests').setLevel(logging.CRITICAL)
        logging.getLogger('godelOS').setLevel(logging.CRITICAL)
        logging.getLogger('backend').setLevel(logging.CRITICAL)
        logging.getLogger('httpx').setLevel(logging.CRITICAL)
    
    # Create config
    config = ConfigurationManager()
    config.custom_options = {
        'no_color': args.no_color,
        'no_emoji': args.no_emoji,
    }
    
    # Run tests
    runner = BDDTestRunner(config)
    exit_code = runner.run(pattern=args.pattern, specific_tests=args.tests)
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
