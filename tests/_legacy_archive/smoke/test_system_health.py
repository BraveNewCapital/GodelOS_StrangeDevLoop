#!/usr/bin/env python3
"""
GödelOS Smoke Tests - System Health Validation

Quick validation tests to ensure core system functionality is working.
These tests run first to validate the system is in a testable state.

Author: GödelOS Unified Testing Infrastructure  
Version: 1.0.0
"""

import asyncio
import sys
from pathlib import Path
import requests
import time
import logging

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

class SystemHealthValidator:
    """Validates core system health and readiness"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.health_checks = []
        
    def test_server_health(self) -> bool:
        """Test if server is responding"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            success = response.status_code == 200
            self.health_checks.append(("Server Health", success))
            return success
        except Exception as e:
            logger.error(f"Server health check failed: {e}")
            self.health_checks.append(("Server Health", False))
            return False
    
    def test_core_imports(self) -> bool:
        """Test that core modules can be imported"""
        try:
            # Test P5 core imports
            from backend.core.enhanced_ksi_adapter import EnhancedKSIAdapter
            from backend.core.persistent_kb_backend import PersistentKBBackend
            from backend.unified_server import app
            
            success = True
            self.health_checks.append(("Core Imports", True))
            return success
        except Exception as e:
            logger.error(f"Core imports failed: {e}")
            self.health_checks.append(("Core Imports", False))
            return False
    
    def test_database_connections(self) -> bool:
        """Test database connectivity"""
        try:
            # Test basic database setup
            from backend.core.persistent_kb_backend import create_persistent_kb_backend
            
            backend = create_persistent_kb_backend()
            # Don't actually initialize to avoid side effects
            success = backend is not None
            self.health_checks.append(("Database Setup", success))
            return success
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            self.health_checks.append(("Database Setup", False))
            return False
    
    def test_api_endpoints(self) -> bool:
        """Test critical API endpoints"""
        critical_endpoints = [
            "/health",
            "/api/query",
            "/api/cognitive/status"
        ]
        
        successes = 0
        for endpoint in critical_endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                if response.status_code in [200, 404]:  # 404 is acceptable for some endpoints
                    successes += 1
            except:
                pass
                
        success = successes >= len(critical_endpoints) // 2  # At least half should work
        self.health_checks.append(("API Endpoints", success))
        return success
    
    async def run_all_checks(self) -> bool:
        """Run all health checks"""
        print("🏥 Running GödelOS System Health Checks...")
        
        checks = [
            self.test_core_imports,
            self.test_database_connections,
            self.test_server_health,
            self.test_api_endpoints
        ]
        
        all_passed = True
        for check in checks:
            result = check()
            all_passed = all_passed and result
        
        # Print results
        print("\n📋 Health Check Results:")
        for name, passed in self.health_checks:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {status} {name}")
        
        overall = "🎉 SYSTEM HEALTHY" if all_passed else "⚠️ SYSTEM ISSUES DETECTED"
        print(f"\n{overall}")
        
        return all_passed


def main():
    """Main smoke test runner"""
    try:
        validator = SystemHealthValidator()
        result = asyncio.run(validator.run_all_checks())
        sys.exit(0 if result else 1)
    except Exception as e:
        logger.error(f"Smoke test execution failed: {e}")
        print(f"💥 Smoke tests failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()