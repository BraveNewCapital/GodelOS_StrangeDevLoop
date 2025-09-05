#!/usr/bin/env python3
"""
Simple validation script for GödelOS fixes
"""

import sys
import json
from pathlib import Path

# Add project root to path  
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_transparency_router_registration():
    """Check if transparency router is properly registered."""
    try:
        from backend.main import app
        
        # Check if transparency endpoints are in the app routes
        routes = [route.path for route in app.routes]
        transparency_routes = [r for r in routes if '/api/transparency/' in r]
        
        print(f"🔍 Found {len(transparency_routes)} transparency routes:")
        for route in transparency_routes[:5]:  # Show first 5
            print(f"  - {route}")
        if len(transparency_routes) > 5:
            print(f"  ... and {len(transparency_routes) - 5} more")
        
        return len(transparency_routes) > 0
        
    except Exception as e:
        print(f"❌ Error checking transparency router: {e}")
        return False

def check_knowledge_graph_improvement():
    """Check if knowledge graph endpoint returns enhanced data."""
    try:
        from backend.main import get_knowledge_graph
        import asyncio
        
        # Get the knowledge graph data
        result = asyncio.run(get_knowledge_graph())
        
        nodes = result.get('nodes', [])
        edges = result.get('edges', [])
        stats = result.get('statistics', {})
        
        print(f"🕸️  Knowledge Graph Analysis:")
        print(f"  - Nodes: {len(nodes)}")
        print(f"  - Edges: {len(edges)}")
        print(f"  - Data source: {stats.get('data_source', 'unknown')}")
        
        # Check if it's the enhanced fallback (not the old simple test data)
        is_enhanced = len(nodes) >= 10 and 'categories' in stats
        
        print(f"  - Enhanced data: {'✅ Yes' if is_enhanced else '❌ No'}")
        
        return is_enhanced
        
    except Exception as e:
        print(f"❌ Error checking knowledge graph: {e}")
        return False

def check_frontend_transparency_view():
    """Check if transparency view component exists and looks functional."""
    try:
        transparency_component = project_root / "svelte-frontend/src/components/transparency/TransparencyDashboard.svelte"
        
        if not transparency_component.exists():
            print("❌ TransparencyDashboard.svelte not found")
            return False
        
        # Read the component to check for key features
        content = transparency_component.read_text()
        
        features = {
            "API calls": "/api/transparency/" in content,
            "WebSocket streams": "WebSocket" in content,
            "Statistics display": "transparencyStats" in content,
            "Session management": "activeSessions" in content,
            "Error handling": "catch" in content and "error" in content
        }
        
        print(f"🎨 Transparency View Features:")
        for feature, present in features.items():
            print(f"  - {feature}: {'✅' if present else '❌'}")
        
        functionality_score = sum(features.values()) / len(features)
        return functionality_score >= 0.8
        
    except Exception as e:
        print(f"❌ Error checking transparency view: {e}")
        return False

def main():
    """Run validation checks."""
    print("🧪 GödelOS Component Validation")
    print("="*40)
    
    checks = [
        ("Transparency Router Registration", check_transparency_router_registration),
        ("Knowledge Graph Enhancement", check_knowledge_graph_improvement), 
        ("Transparency View Frontend", check_frontend_transparency_view)
    ]
    
    results = {}
    for name, check_func in checks:
        print(f"\n{name}:")
        try:
            result = check_func()
            results[name] = result
        except Exception as e:
            print(f"❌ Check failed: {e}")
            results[name] = False
    
    # Summary
    print(f"\n{'='*40}")
    print("📊 VALIDATION SUMMARY:")
    
    passed = sum(results.values())
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")
    
    score = (passed / total) * 100
    print(f"\nOverall Score: {score:.1f}% ({passed}/{total} checks passed)")
    
    if score == 100:
        print("🎉 All checks passed! System improvements successful.")
    elif score >= 66:
        print("👍 Most checks passed. Minor issues remain.")  
    else:
        print("⚠️  Multiple issues found. Further work needed.")

if __name__ == "__main__":
    main()