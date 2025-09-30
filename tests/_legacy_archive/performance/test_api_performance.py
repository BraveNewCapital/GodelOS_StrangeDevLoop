#!/usr/bin/env python3
"""
GödelOS Performance Tests - API Performance Benchmarking

Performance benchmarking for core API endpoints and system responsiveness.

Author: GödelOS Unified Testing Infrastructure
Version: 1.0.0
"""

import asyncio
import time
import statistics
import sys
from pathlib import Path
import requests
import concurrent.futures
import logging

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

class APIPerformanceBenchmark:
    """Performance benchmarking for API endpoints"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.benchmark_results = {}
        
    def benchmark_endpoint(self, endpoint: str, method: str = "GET", payload: dict = None, 
                          iterations: int = 50, concurrent: int = 5) -> dict:
        """Benchmark a specific endpoint"""
        print(f"🏁 Benchmarking {method} {endpoint} ({iterations} iterations, {concurrent} concurrent)")
        
        def make_request():
            start_time = time.time()
            try:
                if method == "GET":
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=30)
                else:
                    response = requests.post(f"{self.base_url}{endpoint}", json=payload, timeout=30)
                end_time = time.time()
                return {
                    "duration": end_time - start_time,
                    "status_code": response.status_code,
                    "success": response.status_code < 400
                }
            except Exception as e:
                end_time = time.time()
                return {
                    "duration": end_time - start_time,
                    "status_code": 0,
                    "success": False,
                    "error": str(e)
                }
        
        # Run benchmark
        start_total = time.time()
        results = []
        
        # Use thread pool for concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = [executor.submit(make_request) for _ in range(iterations)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        end_total = time.time()
        
        # Calculate statistics
        durations = [r["duration"] for r in results if r["success"]]
        success_count = sum(1 for r in results if r["success"])
        
        if not durations:
            return {
                "endpoint": endpoint,
                "method": method,
                "total_requests": iterations,
                "successful_requests": 0,
                "failed_requests": iterations,
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "min_duration": 0.0,
                "max_duration": 0.0,
                "median_duration": 0.0,
                "p95_duration": 0.0,
                "total_time": end_total - start_total,
                "requests_per_second": 0.0
            }
        
        stats = {
            "endpoint": endpoint,
            "method": method,
            "total_requests": iterations,
            "successful_requests": success_count,
            "failed_requests": iterations - success_count,
            "success_rate": success_count / iterations * 100,
            "avg_duration": statistics.mean(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "median_duration": statistics.median(durations),
            "p95_duration": sorted(durations)[int(len(durations) * 0.95)],
            "total_time": end_total - start_total,
            "requests_per_second": success_count / (end_total - start_total)
        }
        
        return stats
    
    def run_api_benchmarks(self) -> bool:
        """Run performance benchmarks on key API endpoints"""
        print("⚡ Running API Performance Benchmarks...")
        
        # Define endpoints to benchmark
        benchmarks = [
            {
                "endpoint": "/health",
                "method": "GET",
                "iterations": 100,
                "concurrent": 10
            },
            {
                "endpoint": "/api/query",
                "method": "POST",
                "payload": {"query": "test performance query", "context": "PERF_TEST"},
                "iterations": 50,
                "concurrent": 5
            },
            {
                "endpoint": "/api/cognitive/status", 
                "method": "GET",
                "iterations": 30,
                "concurrent": 3
            },
            {
                "endpoint": "/api/knowledge/add",
                "method": "POST",
                "payload": {"statement": "perf_test_fact(fast)", "context": "PERF_TEST"},
                "iterations": 30,
                "concurrent": 3
            }
        ]
        
        all_passed = True
        
        for benchmark_config in benchmarks:
            result = self.benchmark_endpoint(**benchmark_config)
            self.benchmark_results[result["endpoint"]] = result
            
            # Print results
            print(f"\n📊 Results for {result['method']} {result['endpoint']}:")
            print(f"   Success Rate: {result['success_rate']:.1f}%")
            print(f"   Avg Response: {result['avg_duration']*1000:.1f}ms")
            print(f"   95th Percentile: {result['p95_duration']*1000:.1f}ms")
            print(f"   Requests/sec: {result['requests_per_second']:.1f}")
            
            # Performance thresholds
            if result['success_rate'] < 90:
                print(f"   ⚠️ Low success rate: {result['success_rate']:.1f}%")
                all_passed = False
            if result['avg_duration'] > 2.0:  # 2 second threshold
                print(f"   ⚠️ Slow average response: {result['avg_duration']:.2f}s")
                all_passed = False
        
        overall = "🎉 PERFORMANCE ACCEPTABLE" if all_passed else "⚠️ PERFORMANCE ISSUES"
        print(f"\n{overall}")
        
        return all_passed


def main():
    """Main performance test runner"""
    try:
        benchmark = APIPerformanceBenchmark()
        result = benchmark.run_api_benchmarks()
        
        # Save detailed results
        import json
        output_file = "test_output/api_performance_results.json"
        Path(output_file).parent.mkdir(exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(benchmark.benchmark_results, f, indent=2)
        print(f"\n📄 Detailed results saved to {output_file}")
        
        sys.exit(0 if result else 1)
    except Exception as e:
        logger.error(f"Performance test execution failed: {e}")
        print(f"💥 Performance tests failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()