#!/usr/bin/env python3
"""
Demo script to showcase the interactive TUI features
"""

import subprocess
import sys
from pathlib import Path

def demo_interactive_runner():
    """Demo the interactive test runner features"""
    
    print("🎯 GödelOS Interactive Test Runner Demo")
    print("="*50)
    
    print("\n1. Command line mode (non-interactive):")
    result = subprocess.run([sys.executable, "unified_test_runner.py", "--suite", "smoke", "--non-interactive"], 
                          capture_output=True, text=True)
    print(result.stdout[:200] + "..." if len(result.stdout) > 200 else result.stdout)
    
    print("\n2. Interactive features available:")
    print("   ✅ Beautiful Rich TUI with progress bars")
    print("   ✅ Interactive suite selection menu")
    print("   ✅ Real-time progress tracking")
    print("   ✅ Detailed results tables")
    print("   ✅ Error output highlighting")
    print("   ✅ Custom test suite selection")
    print("   ✅ Enhanced JSON results with metadata")
    
    print("\n3. Available test suites:")
    suites = ["smoke", "p5", "integration", "performance"]
    for suite in suites:
        status = "✅ Ready" if suite in ["smoke", "p5"] else "❌ Missing"
        print(f"   • {suite}: {status}")
    
    print("\n4. Interactive mode usage:")
    print("   python unified_test_runner.py                    # Full interactive menu")
    print("   python unified_test_runner.py --suite smoke     # Direct suite selection")
    print("   python unified_test_runner.py --non-interactive # Skip interactive prompts")
    
    print(f"\n📊 Last test results saved to: {max(Path('test_output').glob('*.json'), key=lambda x: x.stat().st_mtime)}")

if __name__ == "__main__":
    demo_interactive_runner()