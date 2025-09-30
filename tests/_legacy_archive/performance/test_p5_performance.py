#!/usr/bin/env python3
"""
GödelOS Performance Tests - P5 Component Performance

Performance benchmarking specifically for P5 core architecture components.

Author: GödelOS Unified Testing Infrastructure  
Version: 1.0.0
"""

import asyncio
import time
import statistics
import sys
import tempfile
from pathlib import Path
import logging

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

class P5PerformanceBenchmark:
    """Performance benchmarking for P5 core components"""
    
    def __init__(self):
        self.benchmark_results = {}
        
    async def benchmark_ksi_adapter(self) -> dict:
        """Benchmark Enhanced KSI Adapter performance"""
        print("🧠 Benchmarking Enhanced KSI Adapter...")
        
        try:
            from backend.core.enhanced_ksi_adapter import create_enhanced_ksi_adapter
            from backend.core.ast_nodes import AST_Node
            
            # Create adapter  
            adapter = create_enhanced_ksi_adapter()
            await adapter.initialize()
            
            # Test data
            test_statements = [
                AST_Node(f"test_fact_{i}(value_{i})", "fact") 
                for i in range(100)
            ]
            
            # Benchmark statement addition
            start_time = time.time()
            for stmt in test_statements:
                await adapter.add_statement(stmt, "PERF_TEST")
            add_time = time.time() - start_time
            
            # Benchmark query
            start_time = time.time()
            query = AST_Node("test_query(?)", "query")
            for _ in range(50):
                results = await adapter.query_statements(query, ["PERF_TEST"])
            query_time = time.time() - start_time
            
            # Cleanup
            await adapter.shutdown()
            
            stats = {
                "component": "Enhanced KSI Adapter",
                "statements_added": len(test_statements),
                "add_time_total": add_time,
                "add_time_per_statement": add_time / len(test_statements),
                "queries_executed": 50,
                "query_time_total": query_time,
                "query_time_per_query": query_time / 50,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"KSI Adapter benchmark failed: {e}")
            stats = {"component": "Enhanced KSI Adapter", "success": False, "error": str(e)}
        
        return stats
    
    async def benchmark_persistent_backend(self) -> dict:
        """Benchmark Persistent KB Backend performance"""
        print("💾 Benchmarking Persistent KB Backend...")
        
        try:
            from backend.core.persistent_kb_backend import create_persistent_kb_backend
            from backend.core.ast_nodes import AST_Node
            
            # Create temporary database
            with tempfile.TemporaryDirectory() as temp_dir:
                db_path = Path(temp_dir) / "perf_test.db"
                
                backend = create_persistent_kb_backend(str(db_path))
                await backend.initialize()
                
                # Test data
                test_statements = [
                    AST_Node(f"persist_fact_{i}(data_{i})", "fact") 
                    for i in range(200)
                ]
                
                # Benchmark addition
                start_time = time.time()
                for stmt in test_statements:
                    await backend.add_statement(stmt, "PERF_TEST")
                add_time = time.time() - start_time
                
                # Benchmark retrieval
                start_time = time.time()
                for _ in range(100):
                    results = await backend.query_statements(
                        AST_Node("persist_query(?)", "query"), 
                        ["PERF_TEST"]
                    )
                query_time = time.time() - start_time
                
                # Get statistics
                backend_stats = backend.get_backend_stats()
                
                # Cleanup
                await backend.shutdown()
                
                stats = {
                    "component": "Persistent KB Backend",
                    "statements_added": len(test_statements),
                    "add_time_total": add_time,
                    "add_time_per_statement": add_time / len(test_statements),
                    "queries_executed": 100,
                    "query_time_total": query_time,
                    "query_time_per_query": query_time / 100,
                    "backend_stats": backend_stats,
                    "success": True
                }
                
        except Exception as e:
            logger.error(f"Persistent Backend benchmark failed: {e}")
            stats = {"component": "Persistent KB Backend", "success": False, "error": str(e)}
        
        return stats
    
    async def benchmark_query_optimization(self) -> dict:
        """Benchmark Query Optimization System performance"""
        print("🎯 Benchmarking Query Optimization System...")
        
        try:
            from backend.core.query_optimization_system import create_query_optimizer
            from backend.core.ast_nodes import AST_Node
            
            optimizer = create_query_optimizer()
            await optimizer.initialize()
            
            # Test queries
            test_queries = [
                AST_Node(f"optimize_query_{i}(?)", "query") 
                for i in range(50)
            ]
            
            # Benchmark query analysis
            start_time = time.time()
            for query in test_queries:
                analysis = await optimizer.analyze_query(query, ["OPT_TEST"])
            analysis_time = time.time() - start_time
            
            # Benchmark query execution with optimization
            start_time = time.time()
            for query in test_queries:
                results = await optimizer.execute_optimized_query(
                    query, ["OPT_TEST"], max_results=10
                )
            execution_time = time.time() - start_time
            
            # Get statistics
            opt_stats = optimizer.get_optimization_stats()
            
            # Cleanup
            await optimizer.shutdown()
            
            stats = {
                "component": "Query Optimization System",
                "queries_analyzed": len(test_queries),
                "analysis_time_total": analysis_time,
                "analysis_time_per_query": analysis_time / len(test_queries),
                "queries_executed": len(test_queries),
                "execution_time_total": execution_time,
                "execution_time_per_query": execution_time / len(test_queries),
                "optimization_stats": opt_stats,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Query Optimization benchmark failed: {e}")
            stats = {"component": "Query Optimization System", "success": False, "error": str(e)}
        
        return stats
    
    async def run_p5_benchmarks(self) -> bool:
        """Run all P5 performance benchmarks"""
        print("⚡ Running P5 Core Architecture Performance Benchmarks...")
        
        benchmarks = [
            self.benchmark_ksi_adapter,
            self.benchmark_persistent_backend,
            self.benchmark_query_optimization
        ]
        
        all_passed = True
        
        for benchmark_func in benchmarks:
            result = await benchmark_func()
            component_name = result.get("component", "Unknown")
            self.benchmark_results[component_name] = result
            
            if result.get("success"):
                print(f"\n📊 Results for {component_name}:")
                
                # Display relevant performance metrics
                if "add_time_per_statement" in result:
                    print(f"   Add Performance: {result['add_time_per_statement']*1000:.2f}ms per statement")
                if "query_time_per_query" in result:
                    print(f"   Query Performance: {result['query_time_per_query']*1000:.2f}ms per query")
                if "analysis_time_per_query" in result:
                    print(f"   Analysis Performance: {result['analysis_time_per_query']*1000:.2f}ms per query")
                
                # Performance thresholds
                if result.get("add_time_per_statement", 0) > 0.1:  # 100ms threshold
                    print(f"   ⚠️ Slow statement addition: {result['add_time_per_statement']:.3f}s")
                    all_passed = False
                if result.get("query_time_per_query", 0) > 0.5:  # 500ms threshold
                    print(f"   ⚠️ Slow query execution: {result['query_time_per_query']:.3f}s")
                    all_passed = False
                    
                print(f"   ✅ {component_name} performance acceptable")
            else:
                print(f"   ❌ {component_name} benchmark failed: {result.get('error', 'Unknown error')}")
                all_passed = False
        
        overall = "🎉 P5 PERFORMANCE ACCEPTABLE" if all_passed else "⚠️ P5 PERFORMANCE ISSUES"
        print(f"\n{overall}")
        
        return all_passed


async def main():
    """Main P5 performance test runner"""
    try:
        benchmark = P5PerformanceBenchmark()
        result = await benchmark.run_p5_benchmarks()
        
        # Save detailed results
        import json
        output_file = "test_output/p5_performance_results.json"
        Path(output_file).parent.mkdir(exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(benchmark.benchmark_results, f, indent=2, default=str)
        print(f"\n📄 Detailed results saved to {output_file}")
        
        sys.exit(0 if result else 1)
    except Exception as e:
        logger.error(f"P5 performance test execution failed: {e}")
        print(f"💥 P5 performance tests failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())