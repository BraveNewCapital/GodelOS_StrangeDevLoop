#!/usr/bin/env python3
"""
Test script to validate that our component initialization fixes are working.
"""

import sys
import os
import asyncio
import traceback
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(current_dir))

async def test_component_initialization():
    """Test that all components initialize correctly."""
    print("🔍 Testing GödelOS Component Initialization Fixes...")
    print("=" * 60)
    
    try:
        # Import the integration module
        print("📦 Importing GödelOS integration...")
        from backend.godelos_integration import GödelOSIntegration
        print("✅ Import successful")
        
        # Create integration instance
        print("🏗️  Creating integration instance...")
        integration = GödelOSIntegration()
        print("✅ Instance created")
        
        # Initialize all components
        print("🚀 Initializing all components...")
        await integration.initialize()
        print("✅ All components initialized successfully!")
        
        # Check health status
        print("🏥 Checking health status...")
        health = await integration.get_health_status()
        
        print("\n📊 HEALTH STATUS REPORT:")
        print(f"   Overall Healthy: {health['healthy']}")
        print(f"   Status: {health['status']}")
        print(f"   Error Count: {health['error_count']}")
        print(f"   Knowledge Items: {health['knowledge_items']}")
        print(f"   Uptime: {health['uptime_seconds']:.1f} seconds")
        
        print("\n🔧 COMPONENT STATUS:")
        for service, status in health['services'].items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {service}: {status}")
        
        # Test a simple query to verify functionality
        print("\n🧠 Testing natural language processing...")
        query_result = await integration.process_natural_language_query(
            "Where is John?", 
            include_reasoning=False
        )
        print(f"   Query Response: {query_result['response']}")
        print(f"   Confidence: {query_result['confidence']}")
        
        # Shutdown
        print("\n🛑 Shutting down integration...")
        await integration.shutdown()
        print("✅ Shutdown complete")
        
        # Final assessment
        print("\n" + "=" * 60)
        if health['healthy']:
            print("🎉 SUCCESS: All component initialization fixes are working!")
            print("   The backend should now report healthy status to the frontend.")
            return True
        else:
            print("⚠️  PARTIAL SUCCESS: Components initialized but some issues remain.")
            failed_services = [name for name, status in health['services'].items() if not status]
            if failed_services:
                print(f"   Failed services: {failed_services}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR during testing: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Run the test
    success = asyncio.run(test_component_initialization())
    
    if success:
        print("\n✅ CONCLUSION: The backend component initialization fixes are working correctly!")
        print("   The 'essential_components_ready: false' issue should now be resolved.")
        sys.exit(0)
    else:
        print("\n❌ CONCLUSION: There are still issues that need to be addressed.")
        sys.exit(1)
