#!/usr/bin/env python3
"""
GödelOS Dynamic Test Discovery Runner

Automatically discovers and categorizes all test files instead of hard-coding test lists.
Supports flexible test execution by pattern, directory, or category.
"""

import subprocess
import sys
import json
import asyncio
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set
import fnmatch
import re

# CRITICAL: Setup Python path for godelOS imports
godelos_root = Path(__file__).parent.absolute()
if str(godelos_root) not in sys.path:
    sys.path.insert(0, str(godelos_root))
    print(f"🔧 Added {godelos_root} to Python path for godelOS imports")

# Import test server manager for backend startup/shutdown
from test_server_manager import TestServerManager

try:
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.progress import (
        Progress, SpinnerColumn, TextColumn, BarColumn, 
        TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
    )
    from rich.live import Live
    from rich.layout import Layout
    from rich.table import Table
    from rich.text import Text
    from rich.prompt import Prompt, Confirm
    from rich.tree import Tree
    from rich.status import Status
    from rich.columns import Columns
    from rich.align import Align
    from rich.rule import Rule
    from rich.syntax import Syntax
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

console = Console() if RICH_AVAILABLE else None

class TestDiscovery:
    """Dynamically discover and categorize test files"""
    
    def __init__(self, test_root: Path = None):
        self.test_root = test_root or Path("tests")
        self.discovered_tests = {}
        self.test_patterns = [
            "test_*.py",
            "*_test.py", 
            "test*.py",
            "*test.py"
        ]
        
    def discover_all_tests(self) -> Dict[str, Dict]:
        """Discover all test files and categorize them"""
        if not self.test_root.exists():
            return {}
            
        tests_by_category = {}
        
        # Walk through all directories in tests/
        for path in self.test_root.rglob("*.py"):
            # Skip any archived test suites by convention
            if "_legacy_archive" in path.parts:
                continue
            if self._is_test_file(path):
                category = self._determine_category(path)
                test_info = self._extract_test_info(path)
                
                if category not in tests_by_category:
                    tests_by_category[category] = {
                        "name": self._format_category_name(category),
                        "description": self._generate_category_description(category),
                        "tests": [],
                        "path": str(path.parent)
                    }
                
                tests_by_category[category]["tests"].append({
                    "file": str(path),
                    "name": path.name,
                    "relative_path": str(path.relative_to(self.test_root)),
                    **test_info
                })
        
        self.discovered_tests = tests_by_category
        return tests_by_category
    
    def _is_test_file(self, path: Path) -> bool:
        """Check if a file is a test file"""
        if path.name.startswith("__"):
            return False
            
        for pattern in self.test_patterns:
            if fnmatch.fnmatch(path.name, pattern):
                return True
        return False
    
    def _determine_category(self, path: Path) -> str:
        """Determine test category based on directory structure"""
        relative_path = path.relative_to(self.test_root)
        parts = relative_path.parts[:-1]  # Exclude filename
        
        if not parts:
            return "root"
            
        # Use the first directory as primary category
        primary = parts[0]
        
        # Map common directory names to standardized categories
        category_mapping = {
            "e2e": "e2e",
            "end_to_end": "e2e", 
            "integration": "integration",
            "unit": "unit",
            "performance": "performance",
            "smoke": "smoke",
            "p5_core": "p5_core",
            "p5": "p5_core",
            "core": "core",
            "backend": "backend",
            "frontend": "frontend",
            "api": "api",
            "knowledge": "knowledge",
            "cognitive": "cognitive",
            "metacognition": "metacognition",
            "experiments": "experiments",
            "scalability": "scalability"
        }
        
        return category_mapping.get(primary, primary)
    
    def _extract_test_info(self, path: Path) -> Dict:
        """Extract test information from file content"""
        info = {
            "description": "",
            "test_purpose": "",
            "tags": [],
            "estimated_duration": "unknown",
            "requires_server": False,  # Keep for backward compatibility
            "requires_backend": False,
            "requires_frontend": False,
            "requires_db": False,
            "test_functions": []
        }
        
        try:
            content = path.read_text(encoding='utf-8')
            
            # Extract module docstring (first docstring in file)
            docstring_match = re.search(r'"""([^"]+?)"""', content, re.DOTALL)
            if docstring_match:
                docstring = docstring_match.group(1).strip()
                first_line = docstring.split('\n')[0].strip()
                if first_line:
                    info["description"] = first_line
                # Look for test purpose in docstring
                if "test" in docstring.lower():
                    purpose_lines = [line.strip() for line in docstring.split('\n') 
                                   if 'test' in line.lower() and len(line.strip()) > 20]
                    if purpose_lines:
                        info["test_purpose"] = purpose_lines[0]
            
            # Extract test function names and their purposes
            test_functions = re.findall(r'def (test_[^(]+)\([^)]*\):', content)
            for func_name in test_functions:
                # Look for function docstring
                func_pattern = rf'def {re.escape(func_name)}\([^)]*\):[^"]*"""([^"]+?)"""'
                func_match = re.search(func_pattern, content, re.DOTALL)
                if func_match:
                    func_desc = func_match.group(1).strip().split('\n')[0]
                    info["test_functions"].append({
                        "name": func_name,
                        "description": func_desc
                    })
                else:
                    # Infer purpose from function name
                    readable_name = func_name.replace('test_', '').replace('_', ' ').title()
                    info["test_functions"].append({
                        "name": func_name, 
                        "description": f"Tests {readable_name}"
                    })
            
            # Fallback: use filename if no description found
            if not info["description"] and not info["test_purpose"]:
                filename = path.stem.replace('test_', '').replace('_', ' ').title()
                info["description"] = f"Tests {filename} functionality"
            
            # Enhanced server requirement detection
            backend_indicators = [
                "localhost:8000", "8000", "/health", "/api/", "backend", 
                "fastapi", "uvicorn", "requests.get", "requests.post"
            ]
            
            frontend_indicators = [
                "localhost:3001", "3001", "frontend", "svelte", "npm", 
                "browser", "selenium", "playwright"
            ]
            
            if any(indicator in content.lower() for indicator in backend_indicators):
                info["requires_backend"] = True
                info["requires_server"] = True  # Backward compatibility
                
            if any(indicator in content.lower() for indicator in frontend_indicators):
                info["requires_frontend"] = True
                
            if "database" in content.lower() or "db" in content.lower() or "vector" in content:
                info["requires_db"] = True
                
            # Estimate duration based on content patterns
            if "performance" in content.lower() or "benchmark" in content.lower():
                info["estimated_duration"] = "long"
            elif "smoke" in content.lower() or "quick" in content.lower():
                info["estimated_duration"] = "short"
            else:
                info["estimated_duration"] = "medium"
                
        except Exception:
            pass
            
        return info
    
    def _format_category_name(self, category: str) -> str:
        """Format category name for display"""
        emoji_map = {
            "smoke": "🚨 Smoke Tests",
            "p5_core": "⚡ P5 Core Tests", 
            "e2e": "🔗 End-to-End Tests",
            "integration": "🔧 Integration Tests",
            "performance": "🚀 Performance Tests",
            "unit": "🧪 Unit Tests",
            "backend": "⚙️ Backend Tests",
            "frontend": "🎨 Frontend Tests",
            "api": "🌐 API Tests",
            "knowledge": "🧠 Knowledge Tests",
            "cognitive": "🤖 Cognitive Tests",
            "metacognition": "🎯 Metacognition Tests",
            "spec_aligned": "📜 Spec-Aligned Tests",
            "scalability": "📈 Scalability Tests",
            "experiments": "🔬 Experimental Tests",
            "core": "🔧 Core Tests",
            "root": "📁 Root Tests"
        }
        
        return emoji_map.get(category, f"📋 {category.title()} Tests")
    
    def _generate_category_description(self, category: str) -> str:
        """Generate description for category"""
        descriptions = {
            "smoke": "Critical system health and basic functionality validation",
            "p5_core": "P5 unification engine, logic architecture, and knowledge representation", 
            "e2e": "Complete end-to-end user workflow and system integration testing",
            "integration": "Cross-component integration and system interaction validation",
            "performance": "System performance, scalability, and benchmark testing",
            "unit": "Individual component and function-level unit testing",
            "backend": "Backend service, API, and server-side functionality testing",
            "frontend": "User interface, UX, and client-side functionality testing", 
            "api": "REST API endpoints, request/response, and API contract testing",
            "knowledge": "Knowledge representation, storage, and retrieval testing",
            "cognitive": "Cognitive architecture, consciousness, and AI reasoning testing",
            "metacognition": "Self-reflection, meta-learning, and introspective capability testing",
            "spec_aligned": "Formal specification conformance suites organized by architecture modules",
            "scalability": "System scalability, load handling, and distributed processing testing",
            "experiments": "Experimental features, research validation, and proof-of-concept testing",
            "core": "Core system functionality and fundamental component testing",
            "root": "General system tests and miscellaneous validation"
        }
        
        return descriptions.get(category, f"Tests related to {category} functionality")

class DynamicTestRunner:
    """Enhanced test runner with dynamic discovery and rich output"""
    
    def __init__(self):
        self.discovery = TestDiscovery()
        self.console = Console() if RICH_AVAILABLE else None
        self.verbose = True  # Default to verbose
        self.concise_mode = False  # Default to normal mode
        
    def create_header(self) -> Panel:
        """Create an attractive header panel"""
        header_text = Text()
        header_text.append("🧠 GödelOS ", style="bold cyan")
        header_text.append("Dynamic Test Runner", style="bold white") 
        header_text.append("\nAutomatically discovers and executes all tests", style="italic dim")
        
        return Panel(
            Align.center(header_text),
            title="[bold magenta]Dynamic Test Discovery System[/]",
            border_style="magenta",
            box=box.DOUBLE
        )

    def show_discovered_tests(self, discovered_tests: Dict) -> Table:
        """Show all discovered tests in a table"""
        table = Table(
            title="🔍 Discovered Test Suites",
            box=box.ROUNDED,
            header_style="bold cyan"
        )
        
        table.add_column("Category", style="bold")
        table.add_column("Name", style="cyan") 
        table.add_column("Description", style="dim")
        table.add_column("Tests", justify="center")
        table.add_column("Path", style="dim")
        
        for category_id, category_info in discovered_tests.items():
            test_count = len(category_info["tests"])
            
            # Determine status based on test count
            if test_count > 0:
                status_style = "green"
                count_display = f"[{status_style}]{test_count}[/]"
            else:
                status_style = "red"
                count_display = f"[{status_style}]0[/]"
            
            table.add_row(
                f"[bold]{category_id}[/]",
                category_info["name"],
                category_info["description"][:60] + "..." if len(category_info["description"]) > 60 else category_info["description"],
                count_display,
                category_info.get("path", "")
            )
        
        return table

    def show_concise_discovery_summary(self, discovered_tests: Dict) -> None:
        """Show a concise summary of discovered tests"""
        total_tests = sum(len(cat["tests"]) for cat in discovered_tests.values())
        total_categories = len(discovered_tests)
        
        # Group categories by test count
        major_categories = [(k, v) for k, v in discovered_tests.items() if len(v["tests"]) >= 5]
        minor_categories = [(k, v) for k, v in discovered_tests.items() if len(v["tests"]) < 5 and len(v["tests"]) > 0]
        empty_categories = [(k, v) for k, v in discovered_tests.items() if len(v["tests"]) == 0]
        
        self.console.print(f"[bold cyan]📊 Discovered {total_tests} tests across {total_categories} categories[/]")
        
        if major_categories:
            self.console.print("\n[bold]Major test suites (5+ tests):[/]")
            for category_id, category_info in major_categories:
                test_count = len(category_info["tests"])
                self.console.print(f"  • {category_info['name']}: [green]{test_count} tests[/]")
        
        if minor_categories and not self.concise_mode:
            self.console.print("\n[bold]Other available suites:[/]")
            minor_summary = ", ".join([f"{cat_info['name'].split()[1] if ' ' in cat_info['name'] else cat_info['name']} ({len(cat_info['tests'])})" 
                                     for _, cat_info in minor_categories])
            self.console.print(f"  {minor_summary}")
        elif minor_categories:
            # Ultra concise for minor categories
            total_minor = sum(len(cat_info['tests']) for _, cat_info in minor_categories)
            self.console.print(f"\n[dim]Plus {len(minor_categories)} other suites with {total_minor} tests total[/]")
        
        if empty_categories and self.verbose:
            empty_names = [cat_info['name'].split()[1] if ' ' in cat_info['name'] else cat_info['name'] 
                          for _, cat_info in empty_categories]
            self.console.print(f"\n[dim]Empty suites: {', '.join(empty_names)}[/]")

    def interactive_test_selection(self, discovered_tests: Dict) -> List[str]:
        """Interactive test selection with appropriate verbosity"""
        if not RICH_AVAILABLE:
            return self._fallback_selection(discovered_tests)
            
        self.console.print(self.create_header())
        self.console.print()
        
        # Show summary appropriate to verbosity mode
        if self.verbose:
            self.console.print(self.show_discovered_tests(discovered_tests))
        else:
            self.show_concise_discovery_summary(discovered_tests)
            
            # Only ask for details if not in concise mode
            if not self.concise_mode:
                show_details = Confirm.ask("\nShow detailed test suite breakdown?", default=False)
                if show_details:
                    self.console.print(self.show_discovered_tests(discovered_tests))
        
        self.console.print()
        
        # Interactive selection with better prompts
        popular_choices = []
        for cat_id, cat_info in discovered_tests.items():
            if len(cat_info["tests"]) > 0:
                popular_choices.append(cat_id)
        
        # Limit choices shown in prompt to avoid overwhelming
        main_choices = popular_choices[:8] if len(popular_choices) > 8 else popular_choices
        other_choices = ["all", "pattern", "quit"]
        
        self.console.print("[bold]Popular choices:[/] " + ", ".join([f"[cyan]{c}[/]" for c in main_choices]))
        self.console.print("[bold]Other options:[/] all, pattern, quit")
        
        choice = Prompt.ask(
            "Select test suite",
            choices=list(discovered_tests.keys()) + other_choices,
            default="smoke" if "smoke" in main_choices else main_choices[0] if main_choices else "all"
        )
        
        if choice == "quit":
            self.console.print("[yellow]👋 Goodbye![/]")
            sys.exit(0)
        elif choice == "all":
            return list(discovered_tests.keys())
        elif choice == "pattern":
            return self._pattern_selection(discovered_tests)
        else:
            return [choice]

    def _pattern_selection(self, discovered_tests: Dict) -> List[str]:
        """Allow pattern-based test selection"""
        self.console.print("\n[bold cyan]Pattern Selection Mode[/]")
        self.console.print("Enter patterns to match test files (e.g., '*performance*', 'test_api_*')")
        
        pattern = Prompt.ask("Test file pattern", default="*")
        
        matched_categories = set()
        for category_id, category_info in discovered_tests.items():
            for test in category_info["tests"]:
                if fnmatch.fnmatch(test["name"], pattern) or fnmatch.fnmatch(test["relative_path"], pattern):
                    matched_categories.add(category_id)
        
        if matched_categories:
            self.console.print(f"[green]Found matches in categories: {', '.join(matched_categories)}[/]")
            return list(matched_categories)
        else:
            self.console.print("[yellow]No matches found, running all tests[/]")
            return list(discovered_tests.keys())

    def _fallback_selection(self, discovered_tests: Dict) -> List[str]:
        """Fallback selection without Rich"""
        print("\n🔍 Discovered Test Categories:")
        for i, (category_id, category_info) in enumerate(discovered_tests.items(), 1):
            test_count = len(category_info["tests"])
            print(f"{i}. {category_id}: {category_info['name']} ({test_count} tests)")
        
        print(f"{len(discovered_tests) + 1}. all: Run all categories")
        
        while True:
            try:
                choice = input("\nEnter choice (number or name): ").strip().lower()
                if choice == "all":
                    return list(discovered_tests.keys())
                elif choice in discovered_tests:
                    return [choice]
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(discovered_tests):
                        return [list(discovered_tests.keys())[idx]]
                    elif idx == len(discovered_tests):
                        return list(discovered_tests.keys())
                print("Invalid choice, please try again.")
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                sys.exit(0)

    def run_discovered_tests(self, categories_to_run: List[str], discovered_tests: Dict) -> Dict:
        """Run tests from discovered categories"""
        all_results = {}
        
        for category in categories_to_run:
            if category in discovered_tests:
                category_info = discovered_tests[category]
                if category_info["tests"]:
                    if RICH_AVAILABLE:
                        self.console.print(f"\n[bold]Starting {category_info['name']}...[/]")
                        results = self._run_category_with_progress(category, category_info)
                    else:
                        print(f"\n🧪 Running {category} tests...")
                        results = self._run_category_fallback(category, category_info)
                    
                    all_results[category] = results
                else:
                    if RICH_AVAILABLE:
                        self.console.print(f"[yellow]⚠️ No tests found in category: {category}[/]")
                    else:
                        print(f"⚠️ No tests found in category: {category}")
        
        return all_results

    def _run_category_with_progress(self, category: str, category_info: Dict) -> Dict:
        """Run category tests with Rich progress"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console
        ) as progress:
            
            tests = category_info["tests"]
            main_task = progress.add_task(
                f"[bold green]{category_info['name']}[/]",
                total=len(tests)
            )
            
            results = {}
            
            for test_info in tests:
                test_file = test_info["file"]
                test_task = progress.add_task(f"Running {test_info['name']}", total=1)
                
                start_time = time.time()
                success, stdout, stderr = self._run_single_test(test_file, progress, test_task)
                end_time = time.time()
                
                duration = f"{end_time - start_time:.1f}s"
                
                results[test_file] = {
                    "passed": success,
                    "stdout": stdout,
                    "stderr": stderr,
                    "duration": duration,
                    "timestamp": datetime.now().isoformat(),
                    "test_info": test_info
                }
                
                progress.advance(main_task)
                progress.remove_task(test_task)
                time.sleep(0.05)  # Small delay for visual effect
        
        return results

    def _run_category_fallback(self, category: str, category_info: Dict) -> Dict:
        """Run category tests without Rich"""
        results = {}
        tests = category_info["tests"]
        
        for test_info in tests:
            test_file = test_info["file"]
            print(f"  Running {test_info['name']}...")
            
            start_time = time.time()
            success, stdout, stderr = self._run_single_test(test_file)
            end_time = time.time()
            
            duration = f"{end_time - start_time:.1f}s"
            
            results[test_file] = {
                "passed": success,
                "stdout": stdout,
                "stderr": stderr, 
                "duration": duration,
                "timestamp": datetime.now().isoformat(),
                "test_info": test_info
            }
            
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"    {status} ({duration})")
        
        return results

    def _run_single_test(self, test_file: str, progress=None, task_id=None) -> Tuple[bool, str, str]:
        """Run a single test file"""
        try:
            if progress and task_id:
                progress.update(task_id, description=f"[cyan]Running {Path(test_file).name}[/]")
            
            # Setup environment with correct PYTHONPATH for godelOS imports
            test_env = os.environ.copy()
            godelos_root = str(Path.cwd())
            current_pythonpath = test_env.get('PYTHONPATH', '')
            if current_pythonpath:
                test_env['PYTHONPATH'] = f"{godelos_root}:{current_pythonpath}"
            else:
                test_env['PYTHONPATH'] = godelos_root
            
            # Always run from the project root directory, not the test subdirectory
            result = subprocess.run(
                [sys.executable, test_file],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=Path.cwd(),  # Use current working directory (project root)
                env=test_env  # Include PYTHONPATH for godelOS imports
            )
            
            # Improved success detection - don't mark as passed if it has connectivity errors
            success = result.returncode == 0
            stdout = result.stdout
            stderr = result.stderr
            
            # Check for backend connectivity issues in output
            error_indicators = [
                "Connection refused",
                "HTTPConnectionPool",
                "Failed to establish a new connection",
                "Backend not accessible",
                "Max retries exceeded"
            ]
            
            # If test claims success but has connectivity errors, mark as failed
            if success and any(indicator in stdout + stderr for indicator in error_indicators):
                success = False
                if "Backend not accessible" not in stderr:
                    stderr += "\n❌ Test marked as failed due to backend connectivity issues"
            
            if progress and task_id:
                progress.update(task_id, completed=True)
            
            return success, stdout, stderr
            
        except subprocess.TimeoutExpired:
            if progress and task_id:
                progress.update(task_id, description=f"[red]Timeout: {Path(test_file).name}[/]")
            return False, "", f"Test timeout after 5 minutes"
        except Exception as e:
            if progress and task_id:
                progress.update(task_id, description=f"[red]Error: {Path(test_file).name}[/]")
            return False, "", str(e)

    def display_results(self, all_results: Dict, discovered_tests: Dict):
        """Display test results with appropriate verbosity"""
        if not RICH_AVAILABLE:
            return self._fallback_results_display(all_results)
        
        # Calculate summary statistics
        total_tests = sum(len(results) for results in all_results.values())
        passed_tests = sum(
            sum(1 for test in results.values() if test["passed"]) 
            for results in all_results.values()
        )
        failed_tests = total_tests - passed_tests
        
        if total_tests == 0:
            self.console.print("[yellow]⚠️ No tests were executed[/]")
            return
        
        # In concise mode, only show failures and summary
        if self.concise_mode and failed_tests == 0:
            self.console.print(f"\n[bold green]🎉 All {total_tests} tests passed![/]")
            return
        
        # Always show summary
        if failed_tests > 0:
            self.console.print(f"\n[bold red]❌ {failed_tests} of {total_tests} tests failed ({(failed_tests/total_tests*100):.1f}% failure rate)[/]")
        else:
            self.console.print(f"\n[bold green]✅ All {total_tests} tests passed[/]")
        
        # Always show failed tests with details
        if failed_tests > 0:
            self.console.print(Rule("[bold red]Failed Tests - Details[/]"))
            
            for category, results in all_results.items():
                failed_in_category = {k: v for k, v in results.items() if not v["passed"]}
                if failed_in_category:
                    category_info = discovered_tests.get(category, {"name": category})
                    self.console.print(f"\n[bold red]{category_info.get('name', category)}[/]")
                    
                    for test_file, result in failed_in_category.items():
                        test_info = result.get("test_info", {})
                        test_name = Path(test_file).name
                        description = test_info.get("description", "No description")
                        
                        self.console.print(f"  [bold]{test_name}[/] - {description}")
                        
                        # Show what this test is testing
                        if test_info.get("test_functions"):
                            self.console.print("    [dim]Test Functions:[/]")
                            for func in test_info["test_functions"][:3]:  # Limit to first 3
                                self.console.print(f"      • {func['description']}")
                        
                        # Show concise error information
                        if result["stderr"]:
                            error_lines = result["stderr"].strip().split('\n')
                            # Find the most relevant error line
                            relevant_errors = [line for line in error_lines 
                                             if any(keyword in line.lower() for keyword in 
                                                   ['error', 'failed', 'exception', 'traceback'])]
                            
                            if relevant_errors:
                                self.console.print(f"    [red]Error:[/] {relevant_errors[-1].strip()}")
                            elif error_lines:
                                self.console.print(f"    [red]Error:[/] {error_lines[-1].strip()}")
                        
                        # Show stdout if it contains useful info and stderr is empty
                        elif result["stdout"]:
                            stdout_lines = result["stdout"].strip().split('\n')
                            failure_lines = [line for line in stdout_lines 
                                           if any(keyword in line.lower() for keyword in 
                                                 ['fail', 'error', 'assert', 'exception'])]
                            if failure_lines:
                                self.console.print(f"    [yellow]Output:[/] {failure_lines[-1].strip()}")
                        
                        self.console.print()  # Add spacing between failed tests
        
        # Show passed categories based on verbosity
        if not self.concise_mode or failed_tests > 0:
            passed_categories = []
            for category, results in all_results.items():
                passed_in_category = sum(1 for result in results.values() if result["passed"])
                total_in_category = len(results)
                if passed_in_category > 0:
                    category_info = discovered_tests.get(category, {"name": category})
                    if passed_in_category == total_in_category:
                        passed_categories.append(f"{category_info.get('name', category)}: {passed_in_category}/{total_in_category}")
                    else:
                        passed_categories.append(f"{category_info.get('name', category)}: {passed_in_category}/{total_in_category} passed")
            
            if passed_categories:
                if failed_tests == 0:
                    self.console.print(Rule("[bold green]Test Categories[/]"))
                else:
                    self.console.print(Rule("[bold blue]Passed Test Categories[/]"))
                
                for category_summary in passed_categories:
                    if failed_tests == 0 or not self.concise_mode:
                        self.console.print(f"  ✅ {category_summary}")
                    else:
                        # In concise mode with failures, only show fully passing categories
                        parts = category_summary.split(": ")
                        if "/" in parts[1] and "passed" not in parts[1]:  # All passed
                            self.console.print(f"  ✅ {category_summary}")

    def _create_category_results_table(self, results: Dict) -> Table:
        """Create results table for a category"""
        table = Table(box=box.ROUNDED, header_style="bold cyan")
        
        table.add_column("Test", style="bold")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="center") 
        table.add_column("Path", style="dim")
        
        for test_file, result in results.items():
            status = "[green]✅ PASSED[/]" if result["passed"] else "[red]❌ FAILED[/]"
            duration = result.get("duration", "0.0s")
            
            # Get relative path for display
            test_path = result.get("test_info", {}).get("relative_path", Path(test_file).name)
            
            table.add_row(
                Path(test_file).name,
                status,
                duration,
                test_path
            )
        
        return table

    def save_results(self, results: Dict, discovered_tests: Dict) -> str:
        """Save results with discovery metadata"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = Path("test_output") / f"dynamic_test_results_{timestamp}.json"
        output_file.parent.mkdir(exist_ok=True)
        
        enhanced_results = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "runner_version": "3.0.0-dynamic-discovery",
                "discovery_info": {
                    "total_categories": len(discovered_tests),
                    "total_discovered_tests": sum(len(cat["tests"]) for cat in discovered_tests.values()),
                    "categories_run": len(results),
                    "tests_executed": sum(len(cat_results) for cat_results in results.values())
                },
                "test_root": str(self.discovery.test_root)
            },
            "discovered_categories": discovered_tests,
            "execution_results": results
        }
        
        with open(output_file, "w") as f:
            json.dump(enhanced_results, f, indent=2)
            
        return str(output_file)

    def run(self, categories: Optional[List[str]] = None):
        """Main run method with dynamic discovery"""
        
        # Discover all tests
        if RICH_AVAILABLE:
            with Status("🔍 Discovering tests...", console=self.console):
                discovered_tests = self.discovery.discover_all_tests()
        else:
            print("🔍 Discovering tests...")
            discovered_tests = self.discovery.discover_all_tests()
        
        if not discovered_tests:
            msg = f"[red]❌ No tests discovered in {self.discovery.test_root}[/]"
            if RICH_AVAILABLE:
                self.console.print(msg)
            else:
                print("❌ No tests discovered")
            return 1
        
        # Enhanced server management - detect what servers are needed
        requires_backend = any(
            any(test.get("requires_backend", False) or test.get("requires_server", False) for test in cat_info["tests"])
            for cat_info in discovered_tests.values()
        )
        
        requires_frontend = any(
            any(test.get("requires_frontend", False) for test in cat_info["tests"])
            for cat_info in discovered_tests.values()
        )
        
        server_manager = None
        
        if requires_backend or requires_frontend:
            servers_needed = []
            if requires_backend:
                servers_needed.append("backend")
            if requires_frontend:
                servers_needed.append("frontend")
            
            server_list = " and ".join(servers_needed)
            
            if RICH_AVAILABLE:
                self.console.print(f"[yellow]🔧 Some tests require {server_list} server(s)...[/]")
            else:
                print(f"🔧 Some tests require {server_list} server(s)...")
            
            server_manager = TestServerManager()
            
            # Start required servers
            success = True
            
            if requires_backend:
                if RICH_AVAILABLE:
                    with Status("🚀 Starting backend server...", console=self.console):
                        backend_started = server_manager.start_backend()
                else:
                    backend_started = server_manager.start_backend()
                
                if not backend_started:
                    success = False
                    if RICH_AVAILABLE:
                        self.console.print("[red]❌ Failed to start backend server[/]")
                    else:
                        print("❌ Failed to start backend server")
            
            if requires_frontend and success:
                if RICH_AVAILABLE:
                    with Status("🎨 Starting frontend server...", console=self.console):
                        frontend_started = server_manager.start_frontend()
                else:
                    frontend_started = server_manager.start_frontend()
                
                if not frontend_started:
                    success = False
                    if RICH_AVAILABLE:
                        self.console.print("[red]❌ Failed to start frontend server[/]")
                    else:
                        print("❌ Failed to start frontend server")
            
            if not success:
                if RICH_AVAILABLE:
                    self.console.print("[yellow]💡 Tests requiring servers will be marked as failed[/]")
                else:
                    print("💡 Tests requiring servers will be marked as failed")
            else:
                if RICH_AVAILABLE:
                    self.console.print(f"[green]✅ {server_list.title()} server(s) started successfully[/]")
                else:
                    print(f"✅ {server_list.title()} server(s) started successfully")
        
        try:
            # Select tests to run
            if categories:
                selected_categories = [c for c in categories if c in discovered_tests]
            else:
                selected_categories = self.interactive_test_selection(discovered_tests)
            
            if not selected_categories:
                if RICH_AVAILABLE:
                    self.console.print("[yellow]No categories selected[/]")
                else:
                    print("No categories selected")
                return 1
            
            # Run selected tests
            if RICH_AVAILABLE:
                self.console.print(f"\n[bold green]🚀 Running categories:[/] [cyan]{', '.join(selected_categories)}[/]")
            else:
                print(f"\n🚀 Running categories: {', '.join(selected_categories)}")
            
            all_results = self.run_discovered_tests(selected_categories, discovered_tests)
            
            # Display and save results
            self.display_results(all_results, discovered_tests)
            output_file = self.save_results(all_results, discovered_tests)
            
            if RICH_AVAILABLE:
                self.console.print(f"\n[green]📄 Results saved to:[/] [cyan]{output_file}[/]")
            else:
                print(f"\n📄 Results saved to: {output_file}")
            
            # Determine exit code
            total_tests = sum(len(results) for results in all_results.values())
            passed_tests = sum(
                sum(1 for test in results.values() if test["passed"]) 
                for results in all_results.values()
            )
            
            all_passed = total_tests > 0 and passed_tests == total_tests
            
            status_msg = "🎉 ALL TESTS PASSED" if all_passed else f"⚠️ {total_tests - passed_tests} TESTS FAILED"
            if RICH_AVAILABLE:
                style = "bold green" if all_passed else "bold red"
                self.console.print(f"\n[{style}]{status_msg}[/]")
            else:
                print(f"\n{status_msg}")
            
            return 0 if all_passed else 1
            
        finally:
            # Always stop servers when done
            if server_manager:
                if RICH_AVAILABLE:
                    self.console.print("[yellow]🛑 Stopping all servers...[/]")
                else:
                    print("🛑 Stopping all servers...")
                server_manager.stop_all_servers()
                if RICH_AVAILABLE:
                    self.console.print("[green]✅ All servers stopped[/]")
                else:
                    print("✅ All servers stopped")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="GödelOS Dynamic Test Discovery Runner")
    parser.add_argument("--categories", nargs="+", 
                        help="Test categories to run (discovered automatically)")
    parser.add_argument("--pattern", 
                        help="Run tests matching pattern (e.g., '*performance*')")
    parser.add_argument("--list-only", action="store_true",
                        help="Only list discovered tests, don't run them")
    parser.add_argument("--test-root", default="tests",
                        help="Root directory for test discovery (default: tests)")
    parser.add_argument("--concise", action="store_true",
                        help="Ultra-minimal output: only show failures and final status (perfect for CI/CD)")
    parser.add_argument("--verbose", action="store_true",
                        help="Detailed output: show all test information, discovery details, and comprehensive results")
    
    args = parser.parse_args()
    
    runner = DynamicTestRunner()
    runner.discovery.test_root = Path(args.test_root)
    
    # Set verbosity mode
    if args.concise:
        runner.verbose = False
        runner.concise_mode = True
    elif args.verbose:
        runner.verbose = True
        runner.concise_mode = False
    
    try:
        if args.list_only:
            # Just list discovered tests
            discovered = runner.discovery.discover_all_tests()
            if RICH_AVAILABLE:
                runner.console.print(runner.create_header())
                runner.console.print()
                runner.console.print(runner.show_discovered_tests(discovered))
            else:
                print("🔍 Discovered Tests:")
                for cat, info in discovered.items():
                    print(f"\n{cat}: {len(info['tests'])} tests")
                    for test in info['tests']:
                        print(f"  - {test['relative_path']}")
            return 0
        
        exit_code = runner.run(args.categories)
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        if RICH_AVAILABLE:
            runner.console.print("\n[yellow]👋 Test discovery interrupted by user[/]")
        else:
            print("\n👋 Test discovery interrupted by user")
        sys.exit(1)

if __name__ == "__main__":
    main()