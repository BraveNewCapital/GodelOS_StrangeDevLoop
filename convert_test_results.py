#!/usr/bin/env python3
"""
Convert unified test runner JSON format to test viewer compatible format
"""
import json
import sys
from pathlib import Path

def convert_unified_to_viewer_format(unified_data):
    """Convert unified test runner format to test viewer format"""
    converted_tests = []
    
    # Process each category in discovered_categories
    for category_key, category_data in unified_data.get("discovered_categories", {}).items():
        category_name = category_data.get("name", category_key)
        
        # Process each test file in this category
        for test_file in category_data.get("tests", []):
            test_name = test_file.get("name", "Unknown Test")
            file_path = test_file.get("file", "unknown")
            
            # Convert execution results if they exist
            execution_data = test_file.get("execution", {})
            passed = execution_data.get("passed", False)
            error_message = execution_data.get("error", "")
            duration = execution_data.get("duration", 0)
            
            # Determine status from execution data
            if "execution" in test_file:
                if passed:
                    status = "passed"
                elif error_message:
                    if "skip" in error_message.lower():
                        status = "skipped"
                    else:
                        status = "failed"
                else:
                    status = "failed"
            else:
                status = "unknown"
            
            # Create test entry compatible with viewer
            test_entry = {
                "name": test_name,
                "status": status,
                "duration": duration,
                "message": error_message,
                "file": file_path,
                "suite": category_name
            }
            
            converted_tests.append(test_entry)
            
            # Also process individual test functions if they exist
            for test_func in test_file.get("test_functions", []):
                func_name = test_func.get("name", "unknown_function")
                full_name = f"{test_name}::{func_name}"
                
                func_entry = {
                    "name": full_name,
                    "status": status,  # Use same status as parent file
                    "duration": duration / len(test_file.get("test_functions", [1])),  # Divide duration
                    "message": error_message,
                    "file": file_path,
                    "suite": category_name
                }
                
                converted_tests.append(func_entry)
    
    # Create summary
    total = len(converted_tests)
    passed = len([t for t in converted_tests if t["status"] == "passed"])
    failed = len([t for t in converted_tests if t["status"] == "failed"])
    skipped = len([t for t in converted_tests if t["status"] == "skipped"])
    error = len([t for t in converted_tests if t["status"] == "error"])
    unknown = len([t for t in converted_tests if t["status"] == "unknown"])
    total_duration = sum(t["duration"] for t in converted_tests)
    
    # Return in format compatible with test viewer
    return {
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "error": error,
            "unknown": unknown,
            "duration": total_duration
        },
        "tests": converted_tests,
        "metadata": {
            "converted_from": "unified_test_runner",
            "original_timestamp": unified_data.get("metadata", {}).get("timestamp"),
            "total_categories": len(unified_data.get("discovered_categories", {}))
        }
    }

def main():
    if len(sys.argv) != 3:
        print("Usage: python convert_test_results.py <input_file> <output_file>")
        print("Example: python convert_test_results.py test_output/dynamic_test_results_20250927_202746.json viewer_compatible_results.json")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        sys.exit(1)
    
    print(f"🔄 Converting {input_file} to viewer-compatible format...")
    
    try:
        # Read unified test runner format
        with open(input_file, 'r') as f:
            unified_data = json.load(f)
        
        # Convert to viewer format
        viewer_data = convert_unified_to_viewer_format(unified_data)
        
        # Write viewer-compatible format
        with open(output_file, 'w') as f:
            json.dump(viewer_data, f, indent=2)
        
        print(f"✅ Conversion complete!")
        print(f"📊 Summary:")
        print(f"  • Input: {input_file}")
        print(f"  • Output: {output_file}")
        print(f"  • Total tests: {viewer_data['summary']['total']}")
        print(f"  • Passed: {viewer_data['summary']['passed']}")
        print(f"  • Failed: {viewer_data['summary']['failed']}")
        print(f"  • Categories: {viewer_data['metadata']['total_categories']}")
        
        print(f"\n🌐 To view results:")
        print(f"  1. Open test_results_viewer.html in your browser")
        print(f"  2. Upload {output_file}")
        print(f"  3. Explore the interactive test results!")
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Conversion error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()