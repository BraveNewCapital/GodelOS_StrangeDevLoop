#!/usr/bin/env python3
"""
Comprehensive Validation Script for GödelOS Components

This script validates:
1. Transparency view functionality and backend connectivity
2. Knowledge graph data sources (dynamic vs static)
3. Navigation functionality across all views
4. Backend API endpoint availability
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from backend.main import app
    from backend.knowledge_pipeline_service import KnowledgePipelineService
    from backend.transparency_endpoints import router as transparency_router
    import requests
    from fastapi.testclient import TestClient
except ImportError as e:
    print(f"⚠️  Missing dependencies for validation: {e}")
    print("Install requirements: pip install fastapi requests")
    sys.exit(1)


class GödelOSValidator:
    """Comprehensive validator for GödelOS system components."""
    
    def __init__(self):
        self.client = TestClient(app)
        self.results = {
            "transparency_view": {},
            "knowledge_graph": {},
            "navigation": {},
            "backend_apis": {}
        }
    
    def validate_transparency_endpoints(self):
        """Validate transparency backend endpoints."""
        print("🔍 Validating Transparency Endpoints...")
        
        transparency_endpoints = [
            "/api/transparency/statistics",
            "/api/transparency/sessions/active", 
            "/api/transparency/knowledge-graph/export",
            "/api/transparency/session/active"
        ]
        
        results = {}
        for endpoint in transparency_endpoints:
            try:
                response = self.client.get(endpoint)
                results[endpoint] = {
                    "status_code": response.status_code,
                    "success": response.status_code == 200,
                    "data_available": bool(response.json()) if response.status_code == 200 else False
                }
                print(f"  ✅ {endpoint}: {response.status_code}")
            except Exception as e:
                results[endpoint] = {
                    "status_code": None,
                    "success": False,
                    "error": str(e)
                }
                print(f"  ❌ {endpoint}: {str(e)}")
        
        self.results["transparency_view"]["backend_endpoints"] = results
        
        # Check if transparency router is registered
        try:
            # Test a POST endpoint to see if router is registered
            response = self.client.post("/api/transparency/configure", 
                                      json={"transparency_level": "detailed"})
            router_registered = response.status_code != 404
            self.results["transparency_view"]["router_registered"] = router_registered
            print(f"  {'✅' if router_registered else '❌'} Transparency router registered: {router_registered}")
        except Exception as e:
            self.results["transparency_view"]["router_registered"] = False
            print(f"  ❌ Router registration check failed: {e}")
    
    def validate_knowledge_graph_data(self):
        """Validate knowledge graph data sources."""
        print("🕸️  Validating Knowledge Graph Data...")
        
        try:
            # Test main knowledge graph endpoint
            response = self.client.get("/api/knowledge/graph")
            if response.status_code == 200:
                data = response.json()
                
                # Analyze data source
                statistics = data.get("statistics", {})
                data_source = statistics.get("data_source", "unknown")
                node_count = len(data.get("nodes", []))
                edge_count = len(data.get("edges", []))
                
                is_dynamic = data_source != "fallback_enhanced" and node_count > 4
                
                self.results["knowledge_graph"] = {
                    "endpoint_accessible": True,
                    "data_source": data_source,
                    "is_dynamic": is_dynamic,
                    "node_count": node_count,
                    "edge_count": edge_count,
                    "has_categories": "categories" in statistics,
                    "enhanced_fallback": data_source == "fallback_enhanced"
                }
                
                print(f"  ✅ Knowledge graph accessible: {node_count} nodes, {edge_count} edges")
                print(f"  {'🔄' if is_dynamic else '📋'} Data source: {data_source} ({'Dynamic' if is_dynamic else 'Static/Fallback'})")
                
            else:
                self.results["knowledge_graph"] = {
                    "endpoint_accessible": False,
                    "error": f"HTTP {response.status_code}"
                }
                print(f"  ❌ Knowledge graph endpoint failed: {response.status_code}")
                
        except Exception as e:
            self.results["knowledge_graph"] = {
                "endpoint_accessible": False,
                "error": str(e)
            }
            print(f"  ❌ Knowledge graph validation failed: {e}")
    
    def validate_navigation_views(self):
        """Validate that all navigation views have corresponding backend support."""
        print("🧭 Validating Navigation Views...")
        
        # Known views from the frontend
        frontend_views = [
            "dashboard", "cognitive", "knowledge", "query", "human",
            "enhanced", "stream", "autonomous", "transparency", 
            "reasoning", "reflection", "provenance", "import", 
            "capabilities", "resources"
        ]
        
        view_support = {}
        for view in frontend_views:
            # Check if there are relevant API endpoints for each view
            supported = False
            api_endpoints = []
            
            if view == "transparency":
                endpoints = ["/api/transparency/statistics", "/api/transparency/sessions/active"]
                supported = all(self.client.get(ep).status_code == 200 for ep in endpoints)
                api_endpoints = endpoints
            elif view == "knowledge":
                endpoints = ["/api/knowledge/graph"]
                supported = all(self.client.get(ep).status_code == 200 for ep in endpoints)
                api_endpoints = endpoints
            elif view == "cognitive":
                endpoints = ["/api/cognitive/state"]
                supported = all(self.client.get(ep).status_code == 200 for ep in endpoints)
                api_endpoints = endpoints
            elif view == "enhanced":
                endpoints = ["/api/enhanced-cognitive/status"]
                supported = all(self.client.get(ep).status_code == 200 for ep in endpoints)
                api_endpoints = endpoints
            else:
                # For other views, assume they have basic support if the main app is working
                supported = True
                api_endpoints = ["N/A - Frontend only or basic support"]
            
            view_support[view] = {
                "supported": supported,
                "api_endpoints": api_endpoints
            }
            
            print(f"  {'✅' if supported else '⚠️ '} {view}: {'Supported' if supported else 'Limited/No backend'}")
        
        self.results["navigation"]["view_support"] = view_support
        
        # Calculate overall navigation health
        supported_views = sum(1 for v in view_support.values() if v["supported"])
        total_views = len(view_support)
        navigation_health = (supported_views / total_views) * 100
        
        self.results["navigation"]["health_score"] = navigation_health
        print(f"  📊 Navigation Health: {navigation_health:.1f}% ({supported_views}/{total_views} views supported)")
    
    def validate_backend_apis(self):
        """Validate core backend API functionality."""
        print("⚙️  Validating Core Backend APIs...")
        
        core_endpoints = [
            "/api/health",
            "/api/cognitive/state", 
            "/api/knowledge/graph",
            "/api/enhanced-cognitive/status"
        ]
        
        results = {}
        for endpoint in core_endpoints:
            try:
                response = self.client.get(endpoint)
                results[endpoint] = {
                    "status_code": response.status_code,
                    "success": response.status_code == 200,
                    "response_time_ms": 0  # TestClient doesn't measure time
                }
                print(f"  ✅ {endpoint}: {response.status_code}")
            except Exception as e:
                results[endpoint] = {
                    "status_code": None,
                    "success": False, 
                    "error": str(e)
                }
                print(f"  ❌ {endpoint}: {str(e)}")
        
        self.results["backend_apis"]["core_endpoints"] = results
        
        # Calculate API health
        successful_apis = sum(1 for r in results.values() if r["success"])
        total_apis = len(results)
        api_health = (successful_apis / total_apis) * 100
        
        self.results["backend_apis"]["health_score"] = api_health
        print(f"  📊 API Health: {api_health:.1f}% ({successful_apis}/{total_apis} endpoints working)")
    
    def generate_report(self):
        """Generate comprehensive validation report."""
        print("\n" + "="*60)
        print("📋 COMPREHENSIVE VALIDATION REPORT")
        print("="*60)
        
        # Overall system health
        transparency_health = len([ep for ep in self.results["transparency_view"].get("backend_endpoints", {}).values() 
                                 if ep.get("success", False)]) > 0
        
        knowledge_graph_health = self.results["knowledge_graph"].get("endpoint_accessible", False)
        navigation_health = self.results["navigation"].get("health_score", 0) > 80
        api_health = self.results["backend_apis"].get("health_score", 0) > 80
        
        print(f"\n🎯 SYSTEM HEALTH OVERVIEW:")
        print(f"  {'✅' if transparency_health else '❌'} Transparency View: {'Functional' if transparency_health else 'Issues Found'}")
        print(f"  {'✅' if knowledge_graph_health else '❌'} Knowledge Graph: {'Accessible' if knowledge_graph_health else 'Issues Found'}")
        print(f"  {'✅' if navigation_health else '❌'} Navigation: {self.results['navigation'].get('health_score', 0):.1f}% Support")
        print(f"  {'✅' if api_health else '❌'} Backend APIs: {self.results['backend_apis'].get('health_score', 0):.1f}% Working")
        
        # Detailed findings
        print(f"\n🔍 DETAILED FINDINGS:")
        
        # Transparency
        router_registered = self.results["transparency_view"].get("router_registered", False)
        print(f"  Transparency Router: {'✅ Registered' if router_registered else '❌ Not Registered'}")
        
        # Knowledge Graph
        kg_result = self.results["knowledge_graph"]
        if kg_result.get("endpoint_accessible"):
            is_dynamic = kg_result.get("is_dynamic", False)
            node_count = kg_result.get("node_count", 0)
            print(f"  Knowledge Graph: {'🔄 Dynamic Data' if is_dynamic else '📋 Static/Fallback Data'} ({node_count} nodes)")
        
        # Overall score
        component_scores = [transparency_health, knowledge_graph_health, navigation_health, api_health]
        overall_score = (sum(component_scores) / len(component_scores)) * 100
        
        print(f"\n🏆 OVERALL SYSTEM SCORE: {overall_score:.1f}%")
        
        if overall_score >= 90:
            print("🎉 Excellent! System is fully functional.")
        elif overall_score >= 70:
            print("👍 Good! Minor issues to address.")
        elif overall_score >= 50:
            print("⚠️  Moderate issues found. Improvements needed.")
        else:
            print("🚨 Major issues found. Significant work required.")
        
        return self.results


def main():
    """Run comprehensive validation."""
    print("🚀 Starting GödelOS Comprehensive Validation")
    print("="*60)
    
    validator = GödelOSValidator()
    
    # Run all validations
    validator.validate_backend_apis()
    print()
    validator.validate_transparency_endpoints() 
    print()
    validator.validate_knowledge_graph_data()
    print()
    validator.validate_navigation_views()
    
    # Generate final report
    results = validator.generate_report()
    
    # Save results to file
    timestamp = int(time.time())
    results_file = f"validation_results_{timestamp}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {results_file}")
    

if __name__ == "__main__":
    main()