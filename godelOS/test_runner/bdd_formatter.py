"""
BDD-style Console Formatter for the GödelOS Test Runner.

This module provides clean, real-time BDD (Behavior-Driven Development) 
formatted output for test execution, presenting tests as executable specifications.
"""

import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from godelOS.test_runner.console_formatter import ConsoleFormatter
from godelOS.test_runner.output_manager import OutputLevel


class BDDFormatter(ConsoleFormatter):
    """
    BDD-style formatter that presents tests as executable specifications.
    
    Transforms test names and docstrings into readable Given/When/Then scenarios,
    providing clean, real-time output during test execution.
    """
    
    def __init__(self, config: Any):
        """Initialize the BDD formatter."""
        super().__init__(config)
        self.current_feature = None
        self.current_scenario = None
        self.step_count = 0
        self.feature_start_time = None
        self.scenario_start_time = None
        
    def _extract_feature_name(self, test_path: str) -> str:
        """Extract feature name from test file path."""
        # Extract module name from path
        # e.g., tests/spec_aligned/system_e2e/test_system_e2e_spec.py -> System E2E
        parts = test_path.split('/')
        for part in reversed(parts):
            if part.startswith('test_') and part.endswith('.py'):
                # Remove test_ prefix and .py suffix
                name = part[5:-3]
                # Convert snake_case to Title Case
                return self._humanize_name(name)
        return "Unknown Feature"
    
    def _extract_scenario_name(self, test_name: str) -> str:
        """Extract scenario name from test function name."""
        # Remove test_ prefix
        if test_name.startswith('test_'):
            name = test_name[5:]
        else:
            name = test_name
        
        # Convert snake_case to readable format
        return self._humanize_name(name)
    
    def _humanize_name(self, snake_case: str) -> str:
        """Convert snake_case to Human Readable Title."""
        # Replace underscores with spaces
        words = snake_case.replace('_', ' ')
        # Capitalize each word
        return ' '.join(word.capitalize() for word in words.split())
    
    def _parse_docstring_as_steps(self, docstring: str) -> List[Tuple[str, str]]:
        """
        Parse docstring into BDD steps.
        
        Returns:
            List of (step_type, step_text) tuples where step_type is 
            'given', 'when', 'then', 'and', or 'description'.
        """
        if not docstring:
            return []
        
        steps = []
        lines = docstring.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for BDD keywords (case-insensitive)
            lower_line = line.lower()
            if lower_line.startswith('given '):
                steps.append(('given', line[6:].strip()))
            elif lower_line.startswith('when '):
                steps.append(('when', line[5:].strip()))
            elif lower_line.startswith('then '):
                steps.append(('then', line[5:].strip()))
            elif lower_line.startswith('and '):
                steps.append(('and', line[4:].strip()))
            elif lower_line.startswith('but '):
                steps.append(('but', line[4:].strip()))
            elif ':' in line and not line.startswith(' '):
                # Looks like a roadmap reference or description
                steps.append(('description', line))
            else:
                # Regular description text
                steps.append(('description', line))
        
        return steps
    
    def print_feature_header(self, test_path: str) -> None:
        """Print feature header in BDD style."""
        feature_name = self._extract_feature_name(test_path)
        
        if feature_name != self.current_feature:
            if self.current_feature is not None:
                # Print feature summary
                self._print_feature_summary()
                print()  # Blank line between features
            
            self.current_feature = feature_name
            self.feature_start_time = time.time()
            self.step_count = 0
            
            # Print feature header
            border = "═" * 80
            print(self.colorize(border, 'cyan'))
            print(self.colorize(f"Feature: {feature_name}", 'bold'))
            print(self.colorize(f"  {test_path}", 'dim'))
            print(self.colorize(border, 'cyan'))
            print()
    
    def print_scenario_header(self, test_name: str, docstring: Optional[str] = None) -> None:
        """Print scenario header in BDD style."""
        scenario_name = self._extract_scenario_name(test_name)
        self.current_scenario = scenario_name
        self.scenario_start_time = time.time()
        
        # Print scenario name
        print(self.colorize(f"  Scenario: {scenario_name}", 'bold'))
        
        # Parse and print docstring as BDD steps
        if docstring:
            steps = self._parse_docstring_as_steps(docstring)
            for step_type, step_text in steps:
                self._print_step(step_type, step_text, status='pending')
        
        print()  # Blank line after scenario header
    
    def _print_step(self, step_type: str, step_text: str, status: str = 'pending') -> None:
        """Print a BDD step with appropriate formatting."""
        # Step type formatting
        type_colors = {
            'given': 'blue',
            'when': 'yellow',
            'then': 'green',
            'and': 'cyan',
            'but': 'magenta',
            'description': 'dim',
        }
        
        # Status symbols
        status_symbols = {
            'pending': '○',
            'running': '◐',
            'passed': '✓',
            'failed': '✗',
            'skipped': '⊘',
        }
        
        symbol = status_symbols.get(status, ' ')
        color = type_colors.get(step_type, 'reset')
        
        if step_type == 'description':
            # Description lines are indented and dimmed
            print(f"    {self.colorize(step_text, 'dim')}")
        else:
            # BDD steps get keyword highlighting
            keyword = step_type.capitalize()
            print(f"    {symbol} {self.colorize(keyword, color)} {step_text}")
    
    def print_test_result(self, test_name: str, status: str, duration: float, 
                         error_msg: Optional[str] = None) -> None:
        """Print test result in BDD style."""
        # Status formatting
        status_info = {
            'passed': ('✓', 'green', 'PASSED'),
            'failed': ('✗', 'red', 'FAILED'),
            'skipped': ('⊘', 'yellow', 'SKIPPED'),
            'xpassed': ('⚠', 'yellow', 'XPASS'),
            'xfailed': ('⚠', 'yellow', 'XFAIL'),
            'error': ('✗', 'red', 'ERROR'),
        }
        
        symbol, color, label = status_info.get(status, ('?', 'reset', status.upper()))
        
        # Print result
        duration_str = f"({duration:.2f}s)"
        result_line = f"    {symbol} {label} {duration_str}"
        print(self.colorize(result_line, color))
        
        # Print error message if present
        if error_msg and status in ('failed', 'error'):
            print()
            print(self.colorize("      Error Details:", 'red'))
            for line in error_msg.split('\n'):
                if line.strip():
                    print(f"      {self.colorize(line, 'red')}")
        
        print()  # Blank line after test result
    
    def _print_feature_summary(self) -> None:
        """Print summary for completed feature."""
        if self.feature_start_time is None:
            return
        
        duration = time.time() - self.feature_start_time
        print(self.colorize(f"  Feature completed in {duration:.2f}s", 'dim'))
    
    def print_final_summary(self, stats: Dict[str, Any]) -> None:
        """Print final BDD-style summary."""
        print()
        border = "═" * 80
        print(self.colorize(border, 'cyan'))
        print(self.colorize("Specification Execution Summary", 'bold'))
        print(self.colorize(border, 'cyan'))
        print()
        
        total = stats.get('total', 0)
        passed = stats.get('passed', 0)
        failed = stats.get('failed', 0)
        skipped = stats.get('skipped', 0)
        xpassed = stats.get('xpassed', 0)
        xfailed = stats.get('xfailed', 0)
        errors = stats.get('errors', 0)
        duration = stats.get('duration', 0)
        
        # Print counts with appropriate colors
        print(f"  Total Scenarios:    {total}")
        if passed > 0:
            print(self.colorize(f"  ✓ Passed:           {passed}", 'green'))
        if failed > 0:
            print(self.colorize(f"  ✗ Failed:           {failed}", 'red'))
        if errors > 0:
            print(self.colorize(f"  ✗ Errors:           {errors}", 'red'))
        if skipped > 0:
            print(self.colorize(f"  ⊘ Skipped:          {skipped}", 'yellow'))
        if xfailed > 0:
            print(self.colorize(f"  ⚠ Expected Fails:   {xfailed}", 'yellow'))
        if xpassed > 0:
            print(self.colorize(f"  ⚠ Unexpected Pass:  {xpassed}", 'yellow'))
        
        print()
        print(f"  Duration: {duration:.2f}s")
        print()
        
        # Success/failure indicator
        if failed == 0 and errors == 0:
            print(self.colorize("  ✓ All scenarios passed!", 'green'))
        else:
            print(self.colorize(f"  ✗ {failed + errors} scenario(s) failed", 'red'))
        
        print()
        print(self.colorize(border, 'cyan'))
    
    def print_streaming_update(self, test_name: str, status: str) -> None:
        """Print real-time streaming update during test execution."""
        status_symbols = {
            'running': '◐',
            'passed': '✓',
            'failed': '✗',
            'skipped': '⊘',
        }
        
        status_colors = {
            'running': 'blue',
            'passed': 'green',
            'failed': 'red',
            'skipped': 'yellow',
        }
        
        symbol = status_symbols.get(status, '○')
        color = status_colors.get(status, 'reset')
        
        # Clear current line and print update
        sys.stdout.write('\r\033[K')  # Clear line
        scenario = self._extract_scenario_name(test_name)
        update = f"    {symbol} {scenario}"
        sys.stdout.write(self.colorize(update, color))
        sys.stdout.flush()
        
        if status != 'running':
            print()  # New line after completion
