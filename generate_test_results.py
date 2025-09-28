#!/usr/bin/env python3
"""
Generate test results JSON from pytest for the test results viewer
"""
import json
import subprocess
import sys
from pathlib import Path

def generate_test_results():
    """Generate test results JSON by running pytest with json output"""
    output_file = Path("godelos_test_results.json")
    
    # Try to run pytest with JSON report plugin
    try:
        print("🧪 Running tests to generate JSON results...")
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/unit/test_component_fixes.py",
            "--tb=short", 
            "-v",
            "--json-report", 
            f"--json-report-file={output_file}"
        ], capture_output=True, text=True, timeout=60)
        
        if output_file.exists():
            print(f"✅ Test results saved to {output_file}")
            return str(output_file)
        else:
            print("❌ JSON report plugin not available. Please install with: pip install pytest-json-report")
            return None
            
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"❌ pytest failed: {e}")
        return None

def main():
    print("🧠 GödelOS Test Results Generator")
    print("=" * 40)
    
    results_file = generate_test_results()
    
    if results_file:
        viewer_file = Path("test_results_viewer.html")
        
        if viewer_file.exists():
            print(f"\n📊 Files created:")
            print(f"  • Test Results: {results_file}")
            print(f"  • HTML Viewer: {viewer_file}")
            print(f"\n🌐 To view results:")
            print(f"  1. Open {viewer_file} in your browser")
            print(f"  2. Upload {results_file}")
            print(f"  3. Explore the interactive test results!")
        else:
            print("❌ HTML viewer not found. Please create test_results_viewer.html first.")
    else:
        print("\n❌ Failed to generate test results.")
        print("💡 Make sure pytest-json-report is installed: pip install pytest-json-report")
        print("💡 And that tests exist in the specified directory.")

if __name__ == "__main__":
    main()