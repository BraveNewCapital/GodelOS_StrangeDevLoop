#!/usr/bin/env python3
"""
GödelOS Performance Tests - System Resource Monitoring

Performance monitoring and resource utilization analysis for the entire system.

Author: GödelOS Unified Testing Infrastructure  
Version: 1.0.0
"""

import asyncio
import time
import psutil
import threading
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

class SystemResourceMonitor:
    """Monitor system resources during testing"""
    
    def __init__(self):
        self.monitoring = False
        self.resource_data = []
        self.monitor_thread = None
        
    def start_monitoring(self):
        """Start resource monitoring in background thread"""
        self.monitoring = True
        self.resource_data = []
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("📊 Started system resource monitoring...")
        
    def stop_monitoring(self) -> Dict:
        """Stop monitoring and return statistics"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        
        if not self.resource_data:
            return {"error": "No monitoring data collected"}
        
        # Calculate statistics
        cpu_values = [d['cpu_percent'] for d in self.resource_data]
        memory_values = [d['memory_percent'] for d in self.resource_data]
        
        stats = {
            "monitoring_duration_seconds": len(self.resource_data),
            "samples_collected": len(self.resource_data),
            "cpu_stats": {
                "avg": sum(cpu_values) / len(cpu_values),
                "max": max(cpu_values),
                "min": min(cpu_values)
            },
            "memory_stats": {
                "avg": sum(memory_values) / len(memory_values),
                "max": max(memory_values),
                "min": min(memory_values)
            },
            "raw_data": self.resource_data
        }
        
        print(f"📈 Resource monitoring stopped. Collected {len(self.resource_data)} samples.")
        return stats
        
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.monitoring:
            try:
                data_point = {
                    "timestamp": datetime.now().isoformat(),
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_io": dict(psutil.disk_io_counters()._asdict()) if psutil.disk_io_counters() else {},
                    "network_io": dict(psutil.net_io_counters()._asdict()) if psutil.net_io_counters() else {}
                }
                self.resource_data.append(data_point)
            except Exception as e:
                print(f"⚠️ Error collecting resource data: {e}")
            
            time.sleep(1)  # Sample every second


class ComprehensiveSystemBenchmark:
    """Comprehensive system-wide performance benchmarking"""
    
    def __init__(self):
        self.results = {}
        self.monitor = SystemResourceMonitor()
        
    async def benchmark_server_startup(self) -> Dict:
        """Benchmark server startup time and resource usage"""
        print("🚀 Benchmarking server startup performance...")
        
        try:
            import subprocess
            from pathlib import Path
            
            # Start resource monitoring
            self.monitor.start_monitoring()
            
            # Benchmark server startup
            start_time = time.time()
            
            # Use the unified server startup
            server_script = Path(__file__).parent.parent.parent / "backend" / "unified_server.py"
            
            # Start server as subprocess (non-blocking)
            process = subprocess.Popen([
                sys.executable, str(server_script)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for server to be ready (check health endpoint)
            import requests
            max_wait = 30  # seconds
            server_ready = False
            
            for _ in range(max_wait):
                try:
                    response = requests.get("http://localhost:8000/health", timeout=1)
                    if response.status_code == 200:
                        server_ready = True
                        break
                except:
                    pass
                time.sleep(1)
            
            startup_time = time.time() - start_time
            
            # Stop monitoring and collect stats
            resource_stats = self.monitor.stop_monitoring()
            
            # Shutdown server
            process.terminate()
            process.wait(timeout=5)
            
            if server_ready:
                result = {
                    "startup_time_seconds": startup_time,
                    "server_ready": True,
                    "resource_usage": resource_stats,
                    "success": True
                }
                print(f"   ✅ Server started in {startup_time:.2f} seconds")
            else:
                result = {
                    "startup_time_seconds": startup_time,
                    "server_ready": False,
                    "timeout_reached": True,
                    "success": False
                }
                print(f"   ❌ Server startup timeout after {startup_time:.2f} seconds")
                
        except Exception as e:
            result = {"success": False, "error": str(e)}
            print(f"   ❌ Server startup benchmark failed: {e}")
        
        return result
    
    async def benchmark_cognitive_pipeline(self) -> Dict:
        """Benchmark the complete cognitive processing pipeline"""
        print("🧠 Benchmarking cognitive processing pipeline...")
        
        try:
            from backend.core.cognitive_manager import CognitiveManager
            
            # Initialize cognitive manager
            cognitive_manager = CognitiveManager()
            await cognitive_manager.initialize()
            
            # Test queries of varying complexity
            test_queries = [
                "What is the capital of France?",
                "Explain the relationship between consciousness and AI systems",
                "How does knowledge graph evolution work in cognitive architectures?",
                "Process this complex multi-step reasoning task involving temporal logic and causal inference"
            ]
            
            query_results = []
            
            # Start resource monitoring
            self.monitor.start_monitoring()
            
            for i, query in enumerate(test_queries):
                start_time = time.time()
                
                try:
                    response = await cognitive_manager.process_query(query)
                    processing_time = time.time() - start_time
                    
                    query_result = {
                        "query_index": i,
                        "query_complexity": len(query.split()),
                        "processing_time": processing_time,
                        "response_length": len(str(response)),
                        "success": True
                    }
                    
                except Exception as e:
                    query_result = {
                        "query_index": i,
                        "query_complexity": len(query.split()),
                        "processing_time": time.time() - start_time,
                        "success": False,
                        "error": str(e)
                    }
                
                query_results.append(query_result)
            
            # Stop resource monitoring
            resource_stats = self.monitor.stop_monitoring()
            
            # Calculate statistics
            successful_queries = [r for r in query_results if r["success"]]
            
            if successful_queries:
                avg_time = sum(r["processing_time"] for r in successful_queries) / len(successful_queries)
                max_time = max(r["processing_time"] for r in successful_queries)
                min_time = min(r["processing_time"] for r in successful_queries)
                
                result = {
                    "total_queries": len(test_queries),
                    "successful_queries": len(successful_queries),
                    "success_rate": len(successful_queries) / len(test_queries),
                    "avg_processing_time": avg_time,
                    "max_processing_time": max_time,
                    "min_processing_time": min_time,
                    "detailed_results": query_results,
                    "resource_usage": resource_stats,
                    "success": True
                }
                
                print(f"   ✅ Processed {len(successful_queries)}/{len(test_queries)} queries")
                print(f"   📊 Average processing time: {avg_time:.2f}s")
                
            else:
                result = {
                    "total_queries": len(test_queries),
                    "successful_queries": 0,
                    "success_rate": 0,
                    "detailed_results": query_results,
                    "success": False
                }
                print("   ❌ No queries processed successfully")
            
            # Cleanup
            await cognitive_manager.shutdown()
            
        except Exception as e:
            result = {"success": False, "error": str(e)}
            print(f"   ❌ Cognitive pipeline benchmark failed: {e}")
        
        return result
    
    async def benchmark_concurrent_load(self) -> Dict:
        """Benchmark system performance under concurrent load"""
        print("⚡ Benchmarking concurrent load handling...")
        
        try:
            import asyncio
            import aiohttp
            
            # Configuration
            concurrent_requests = 20
            requests_per_client = 5
            
            async def make_requests(session, client_id):
                """Make requests from a single client"""
                client_results = []
                
                for i in range(requests_per_client):
                    start_time = time.time()
                    try:
                        async with session.get("http://localhost:8000/health") as response:
                            response_time = time.time() - start_time
                            client_results.append({
                                "client_id": client_id,
                                "request_id": i,
                                "response_time": response_time,
                                "status_code": response.status,
                                "success": response.status == 200
                            })
                    except Exception as e:
                        client_results.append({
                            "client_id": client_id,
                            "request_id": i,
                            "response_time": time.time() - start_time,
                            "success": False,
                            "error": str(e)
                        })
                
                return client_results
            
            # Start resource monitoring
            self.monitor.start_monitoring()
            
            # Execute concurrent load test
            start_time = time.time()
            
            async with aiohttp.ClientSession() as session:
                tasks = [
                    make_requests(session, client_id) 
                    for client_id in range(concurrent_requests)
                ]
                
                all_results = await asyncio.gather(*tasks)
            
            total_time = time.time() - start_time
            
            # Stop resource monitoring
            resource_stats = self.monitor.stop_monitoring()
            
            # Flatten results
            flat_results = [result for client_results in all_results for result in client_results]
            
            # Calculate statistics
            successful_requests = [r for r in flat_results if r["success"]]
            
            if successful_requests:
                response_times = [r["response_time"] for r in successful_requests]
                
                result = {
                    "concurrent_clients": concurrent_requests,
                    "requests_per_client": requests_per_client,
                    "total_requests": len(flat_results),
                    "successful_requests": len(successful_requests),
                    "success_rate": len(successful_requests) / len(flat_results),
                    "total_test_time": total_time,
                    "avg_response_time": sum(response_times) / len(response_times),
                    "max_response_time": max(response_times),
                    "min_response_time": min(response_times),
                    "requests_per_second": len(successful_requests) / total_time,
                    "resource_usage": resource_stats,
                    "detailed_results": flat_results,
                    "success": True
                }
                
                print(f"   ✅ Completed {len(successful_requests)}/{len(flat_results)} requests")
                print(f"   📊 {result['requests_per_second']:.1f} requests/second")
                print(f"   ⏱️ Average response time: {result['avg_response_time']*1000:.1f}ms")
                
            else:
                result = {
                    "total_requests": len(flat_results),
                    "successful_requests": 0,
                    "success_rate": 0,
                    "success": False
                }
                print("   ❌ No requests completed successfully")
                
        except Exception as e:
            result = {"success": False, "error": str(e)}
            print(f"   ❌ Concurrent load benchmark failed: {e}")
        
        return result
    
    async def run_comprehensive_benchmarks(self) -> bool:
        """Run all comprehensive system benchmarks"""
        print("🔥 Running Comprehensive System Performance Benchmarks...")
        
        benchmarks = [
            ("Server Startup", self.benchmark_server_startup),
            ("Cognitive Pipeline", self.benchmark_cognitive_pipeline),
            ("Concurrent Load", self.benchmark_concurrent_load)
        ]
        
        all_passed = True
        
        for name, benchmark_func in benchmarks:
            print(f"\n{'='*50}")
            result = await benchmark_func()
            self.results[name] = result
            
            if not result.get("success"):
                all_passed = False
        
        print(f"\n{'='*50}")
        overall = "🏆 SYSTEM PERFORMANCE EXCELLENT" if all_passed else "⚠️ SYSTEM PERFORMANCE ISSUES"
        print(f"{overall}")
        
        return all_passed


async def main():
    """Main system performance benchmark runner"""
    try:
        benchmark = ComprehensiveSystemBenchmark()
        result = await benchmark.run_comprehensive_benchmarks()
        
        # Save detailed results
        output_file = "test_output/system_performance_results.json"
        Path(output_file).parent.mkdir(exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(benchmark.results, f, indent=2, default=str)
        print(f"\n📄 Detailed results saved to {output_file}")
        
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"💥 System performance tests failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())