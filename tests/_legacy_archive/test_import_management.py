#!/usr/bin/env python3
"""
Test script for import management endpoints
Tests the new cancel, reset, and active import endpoints
"""

import asyncio
import aiohttp
import json
import time
from typing import List, Dict

API_BASE = "http://localhost:8000"

class ImportManagementTester:
    def __init__(self):
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_active_imports(self) -> Dict:
        """Get list of active imports"""
        try:
            async with self.session.get(f"{API_BASE}/api/knowledge/import/active") as response:
                result = await response.json()
                print(f"✅ Active Imports: {result}")
                return result
        except Exception as e:
            print(f"❌ Failed to get active imports: {e}")
            return {}
    
    async def cancel_import(self, import_id: str) -> Dict:
        """Cancel a specific import"""
        try:
            async with self.session.delete(f"{API_BASE}/api/knowledge/import/{import_id}") as response:
                result = await response.json()
                print(f"✅ Cancel Import {import_id}: {result}")
                return result
        except Exception as e:
            print(f"❌ Failed to cancel import {import_id}: {e}")
            return {}
    
    async def cancel_all_imports(self) -> Dict:
        """Cancel all active imports"""
        try:
            async with self.session.delete(f"{API_BASE}/api/knowledge/import/all") as response:
                result = await response.json()
                print(f"✅ Cancel All Imports: {result}")
                return result
        except Exception as e:
            print(f"❌ Failed to cancel all imports: {e}")
            return {}
    
    async def reset_stuck_imports(self) -> Dict:
        """Reset stuck imports"""
        try:
            async with self.session.delete(f"{API_BASE}/api/knowledge/import/stuck") as response:
                result = await response.json()
                print(f"✅ Reset Stuck Imports: {result}")
                return result
        except Exception as e:
            print(f"❌ Failed to reset stuck imports: {e}")
            return {}
    
    async def start_test_import(self) -> str:
        """Start a test import to have something to cancel"""
        try:
            test_data = {
                "text": "This is a test import for cancellation testing. " * 50,
                "title": "Test Import for Cancellation",
                "source": "test_script"
            }
            
            async with self.session.post(
                f"{API_BASE}/api/knowledge/import/text",
                json=test_data
            ) as response:
                result = await response.json()
                import_id = result.get("import_id")
                print(f"✅ Started Test Import: {import_id}")
                return import_id
        except Exception as e:
            print(f"❌ Failed to start test import: {e}")
            return None
    
    async def run_comprehensive_test(self):
        """Run comprehensive test of import management"""
        print("🚀 Starting Import Management API Test")
        print("=" * 50)
        
        # 1. Check initial active imports
        print("\n1. Getting initial active imports...")
        initial_active = await self.get_active_imports()
        
        # 2. Start a test import
        print("\n2. Starting test import...")
        test_import_id = await self.start_test_import()
        
        if test_import_id:
            # 3. Check active imports again
            print("\n3. Checking active imports after starting test...")
            await asyncio.sleep(1)  # Give it a moment to register
            active_with_test = await self.get_active_imports()
            
            # 4. Cancel the specific test import
            print("\n4. Cancelling test import...")
            await self.cancel_import(test_import_id)
            
            # 5. Check active imports after cancellation
            print("\n5. Checking active imports after cancellation...")
            await asyncio.sleep(1)
            active_after_cancel = await self.get_active_imports()
        
        # 6. Test cancel all (if any are still active)
        print("\n6. Testing cancel all imports...")
        cancel_all_result = await self.cancel_all_imports()
        
        # 7. Test reset stuck imports
        print("\n7. Testing reset stuck imports...")
        reset_result = await self.reset_stuck_imports()
        
        # 8. Final check of active imports
        print("\n8. Final check of active imports...")
        final_active = await self.get_active_imports()
        
        print("\n" + "=" * 50)
        print("🎉 Import Management API Test Complete!")
        print(f"Initial active imports: {initial_active.get('total_count', 0)}")
        print(f"Final active imports: {final_active.get('total_count', 0)}")

async def main():
    """Main test function"""
    async with ImportManagementTester() as tester:
        await tester.run_comprehensive_test()

if __name__ == "__main__":
    print("🧪 Import Management API Tester")
    print("Testing new cancel, reset, and active import endpoints")
    print("Make sure the backend server is running on localhost:8000")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed: {e}")
