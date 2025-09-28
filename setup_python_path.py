#!/usr/bin/env python3
"""
Fix Python path for GödelOS imports
This script adds the current directory to Python path so godelOS module can be imported
"""
import sys
import os
from pathlib import Path

def setup_godelos_path():
    """Add the GödelOS root directory to Python path"""
    # Get the directory containing this script (should be GödelOS root)
    godelos_root = Path(__file__).parent.absolute()
    
    # Add to Python path if not already present
    godelos_root_str = str(godelos_root)
    if godelos_root_str not in sys.path:
        sys.path.insert(0, godelos_root_str)
        print(f"✅ Added {godelos_root_str} to Python path")
    else:
        print(f"📍 {godelos_root_str} already in Python path")
    
    # Verify the godelOS module can be imported
    try:
        import godelOS
        print(f"✅ godelOS module successfully imported from {godelOS.__file__}")
        return True
    except ImportError as e:
        print(f"❌ Failed to import godelOS: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Setting up GödelOS Python path...")
    success = setup_godelos_path()
    
    if success:
        print("🎉 GödelOS import path setup complete!")
    else:
        print("💥 GödelOS import path setup failed!")
        sys.exit(1)