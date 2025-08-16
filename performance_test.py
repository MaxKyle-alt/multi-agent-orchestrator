#!/usr/bin/env python3
"""
Performance Testing Suite for Multi-Agent Task Orchestration System

This test suite validates the performance claims made in the README:
- Task throughput and concurrency
- API response times  
- System resource usage
- Agent execution timing
- Worker pool scaling behavior
"""

import asyncio
import logging
import os
import statistics
import sys
import time
from datetime import datetime
from typing import Any, Dict, List

import psutil

# Add src to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import aiohttp

from src.agents import agent_registry
from src.models import TaskDefinition, TaskStatus
from src.orchestrator import TaskManager


class PerformanceMetrics:
    """Collect and analyze performance metrics"""
    
    def __init__(self):
        self.task_times: List[float] = []
        self.api_response_times: List[float] = []
        self.memory_usage: List[float] = []
        self.cpu_usage: List[float] = []
        self.concurrent_tasks = 0
        self.failed_tasks = 0
        self.completed_tasks = 0
        
    def add_task_time(self, duration: float):
        self.task_times.append(duration)
        
    def add_api_response_time(self, duration: float):
        self.api_response_times.append(duration)
        
    def record_system_metrics(self):
        process = psutil.Process()
        self.memory_usage.append(process.memory_info().rss / 1024 / 1024)  # MB
        self.cpu_usage.append(process.cpu_percent())
        
    def get_summary(self) -> Dict[str, Any]:
        return {
            "task_performance": {
                "total_tasks": len(self.task_times),
                "completed_tasks": self.completed_tasks,
                "failed_tasks": self.failed_tasks,
                "avg_task_duration": statistics.mean(self.task_times) if self.task_times else 0,
                "min_task_duration": min(self.task_times) if self.task_times else 0,
                "max_task_duration": max(self.task_times) if self.task_times else 0,
                "p95_task_duration": statistics.quantiles(self.task_times, n=20)[18] if len(self.task_times) > 20 else 0,
            },
            "api_performance": {
                "avg_response_time": statistics.mean(self.api_response_times) if self.api_response_times else 0,
                "min_response_time": min(self.api_response_times) if self.api_response_times else 0,
                "max_response_time": max(self.api_response_times) if self.api_response_times else 0,
                "p95_response_time": statistics.quantiles(self.api_response_times, n=20)[18] if len(self.api_response_times) > 20 else 0,
            },
            "system_resources": {
                "avg_memory_mb": statistics.mean(self.memory_usage) if self.memory_usage else 0,
                "max_memory_mb": max(self.memory_usage) if self.memory_usage else 0,
                "avg_cpu_percent": statistics.mean(self.cpu_usage) if self.cpu_usage else 0,
                "max_cpu_percent": max(self.cpu_usage) if self.cpu_usage else 0,
            }
        }


class PerformanceTester:
    """Main performance testing class"""
    
    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.task_manager = TaskManager(max_workers=10)
        self.base_url = "http://localhost:8000"
        
        # Configure logging for performance testing
        logging.basicConfig(
            level=logging.WARNING,  # Reduce noise during testing
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
    async def setup(self):
        """Initialize the task manager"""
        await self.task_manager.start()
        print("✅ Task manager started for performance testing")
        
    async def teardown(self):
        """Clean up resources"""
        await self.task_manager.stop()
        print("✅ Task manager stopped")
        
    async def test_task_throughput(self, num_tasks: int = 100, batch_size: int = 10) -> Dict[str, Any]:
        """Test how many tasks can be processed concurrently"""
        print(f"\n🚀 Testing task throughput: {num_tasks} tasks in batches of {batch_size}")
        
        start_time = time.time()
        task_ids = []
        
        # Submit tasks in batches to avoid overwhelming the system
        for batch in range(0, num_tasks, batch_size):
            batch_tasks = []
            batch_end = min(batch + batch_size, num_tasks)
            
            for i in range(batch, batch_end):
                task = TaskDefinition(
                    task_name=f"perf_test_{i}",
                    agent_type="data_fetcher",
                    task_params={"test_id": i, "batch": batch // batch_size}
                )
                batch_tasks.append(self.task_manager.submit_task(task))
                
            # Submit batch and collect task IDs
            batch_ids = await asyncio.gather(*batch_tasks)
            task_ids.extend(batch_ids)
            
            # Small delay between batches to prevent overwhelming
            await asyncio.sleep(0.1)
            
        submission_time = time.time() - start_time
        print(f"📤 Submitted {num_tasks} tasks in {submission_time:.2f}s")
        
        # Wait for all tasks to complete
        await self._wait_for_tasks_completion(task_ids)
        
        total_time = time.time() - start_time
        throughput = num_tasks / total_time
        
        print(f"✅ Completed {num_tasks} tasks in {total_time:.2f}s")
        print(f"📊 Throughput: {throughput:.2f} tasks/second")
        
        return {
            "num_tasks": num_tasks,
            "total_time": total_time,
            "submission_time": submission_time,
            "throughput": throughput,
            "tasks_per_second": throughput
        }
        
    async def test_concurrent_execution(self, concurrency_levels: List[int] = [1, 5, 10, 20]) -> Dict[str, Any]:
        """Test system behavior under different concurrency levels"""
        print(f"\n⚡ Testing concurrent execution at levels: {concurrency_levels}")
        
        results = {}
        
        for concurrency in concurrency_levels:
            print(f"\n🔄 Testing {concurrency} concurrent tasks...")
            
            # Create tasks
            tasks = []
            for i in range(concurrency):
                task = TaskDefinition(
                    task_name=f"concurrent_test_{i}",
                    agent_type="data_processor",
                    task_params={"operation": "test", "concurrency": concurrency}
                )
                tasks.append(self.task_manager.submit_task(task))
                
            start_time = time.time()
            task_ids = await asyncio.gather(*tasks)
            
            # Wait for completion
            await self._wait_for_tasks_completion(task_ids)
            
            execution_time = time.time() - start_time
            effective_concurrency = concurrency / execution_time
            
            results[f"concurrency_{concurrency}"] = {
                "tasks": concurrency,
                "execution_time": execution_time,
                "effective_concurrency": effective_concurrency,
                "avg_time_per_task": execution_time / concurrency
            }
            
            print(f"✅ {concurrency} tasks completed in {execution_time:.2f}s (effective: {effective_concurrency:.2f} tasks/s)")
            
        return results
        
    async def test_api_response_times(self, num_requests: int = 50) -> Dict[str, Any]:
        """Test API endpoint response times"""
        print(f"\n🌐 Testing API response times with {num_requests} requests")
        
        async with aiohttp.ClientSession() as session:
            # Test health endpoint
            health_times = await self._benchmark_endpoint(session, "/health", num_requests)
            
            # Test stats endpoint  
            stats_times = await self._benchmark_endpoint(session, "/stats", num_requests)
            
            # Test agents endpoint
            agents_times = await self._benchmark_endpoint(session, "/agents", num_requests)
            
        return {
            "health_endpoint": {
                "avg_response_time": statistics.mean(health_times),
                "min_response_time": min(health_times),
                "max_response_time": max(health_times),
                "p95_response_time": statistics.quantiles(health_times, n=20)[18] if len(health_times) > 20 else max(health_times)
            },
            "stats_endpoint": {
                "avg_response_time": statistics.mean(stats_times),
                "min_response_time": min(stats_times), 
                "max_response_time": max(stats_times),
                "p95_response_time": statistics.quantiles(stats_times, n=20)[18] if len(stats_times) > 20 else max(stats_times)
            },
            "agents_endpoint": {
                "avg_response_time": statistics.mean(agents_times),
                "min_response_time": min(agents_times),
                "max_response_time": max(agents_times), 
                "p95_response_time": statistics.quantiles(agents_times, n=20)[18] if len(agents_times) > 20 else max(agents_times)
            }
        }
        
    async def test_agent_execution_times(self, agent_types: List[str] = None) -> Dict[str, Any]:
        """Test execution times for different agent types"""
        if agent_types is None:
            agent_types = ["data_fetcher", "chart_generator", "data_processor"]
            
        print(f"\n🤖 Testing agent execution times for: {agent_types}")
        
        results = {}
        
        for agent_type in agent_types:
            print(f"Testing {agent_type}...")
            execution_times = []
            
            # Run multiple tasks for each agent type
            for i in range(10):
                task = TaskDefinition(
                    task_name=f"timing_test_{agent_type}_{i}",
                    agent_type=agent_type,
                    task_params={"test_run": i}
                )
                
                start_time = time.time()
                task_id = await self.task_manager.submit_task(task)
                await self._wait_for_tasks_completion([task_id])
                execution_time = time.time() - start_time
                
                execution_times.append(execution_time)
                
            results[agent_type] = {
                "avg_execution_time": statistics.mean(execution_times),
                "min_execution_time": min(execution_times),
                "max_execution_time": max(execution_times),
                "std_deviation": statistics.stdev(execution_times) if len(execution_times) > 1 else 0
            }
            
        return results
        
    async def test_system_resource_usage(self, duration_seconds: int = 30) -> Dict[str, Any]:
        """Monitor system resource usage during load"""
        print(f"\n📊 Monitoring system resources for {duration_seconds} seconds under load")
        
        # Start resource monitoring
        monitoring_task = asyncio.create_task(self._monitor_resources(duration_seconds))
        
        # Generate load during monitoring
        load_task = asyncio.create_task(self._generate_continuous_load(duration_seconds))
        
        # Wait for both to complete
        await asyncio.gather(monitoring_task, load_task)
        
        return {
            "monitoring_duration": duration_seconds,
            "avg_memory_mb": statistics.mean(self.metrics.memory_usage),
            "max_memory_mb": max(self.metrics.memory_usage),
            "avg_cpu_percent": statistics.mean(self.metrics.cpu_usage),
            "max_cpu_percent": max(self.metrics.cpu_usage),
            "memory_growth": max(self.metrics.memory_usage) - min(self.metrics.memory_usage) if self.metrics.memory_usage else 0
        }
        
    async def _benchmark_endpoint(self, session: aiohttp.ClientSession, endpoint: str, num_requests: int) -> List[float]:
        """Benchmark a specific API endpoint"""
        response_times = []
        
        for _ in range(num_requests):
            start_time = time.time()
            try:
                async with session.get(f"{self.base_url}{endpoint}") as response:
                    await response.read()
                    response_time = time.time() - start_time
                    response_times.append(response_time)
            except Exception as e:
                print(f"❌ Request failed: {e}")
                
        return response_times
        
    async def _wait_for_tasks_completion(self, task_ids: List[str]):
        """Wait for all tasks to complete"""
        while True:
            completed = 0
            failed = 0
            
            for task_id in task_ids:
                task = await self.task_manager.get_task_status(task_id)
                if task:
                    if task.status == TaskStatus.completed:
                        completed += 1
                    elif task.status == TaskStatus.failed:
                        failed += 1
                        
            if completed + failed >= len(task_ids):
                self.metrics.completed_tasks += completed
                self.metrics.failed_tasks += failed
                break
                
            await asyncio.sleep(0.1)
            
    async def _monitor_resources(self, duration: int):
        """Monitor system resources for specified duration"""
        end_time = time.time() + duration
        
        while time.time() < end_time:
            self.metrics.record_system_metrics()
            await asyncio.sleep(1)  # Sample every second
            
    async def _generate_continuous_load(self, duration: int):
        """Generate continuous load for resource testing"""
        end_time = time.time() + duration
        task_counter = 0
        
        while time.time() < end_time:
            # Submit a task every 100ms
            task = TaskDefinition(
                task_name=f"load_test_{task_counter}",
                agent_type="data_fetcher",
                task_params={"load_test": True}
            )
            await self.task_manager.submit_task(task)
            task_counter += 1
            await asyncio.sleep(0.1)
            
    async def run_full_performance_suite(self) -> Dict[str, Any]:
        """Run the complete performance test suite"""
        print("🚀 Starting Full Performance Test Suite")
        print("=" * 50)
        
        await self.setup()
        
        try:
            results = {}
            
            # Test 1: Task throughput
            results["throughput"] = await self.test_task_throughput(100, 10)
            
            # Test 2: Concurrent execution
            results["concurrency"] = await self.test_concurrent_execution([1, 5, 10, 15])
            
            # Test 3: API response times
            results["api_performance"] = await self.test_api_response_times(50)
            
            # Test 4: Agent execution times
            results["agent_performance"] = await self.test_agent_execution_times()
            
            # Test 5: Resource usage
            results["resource_usage"] = await self.test_system_resource_usage(30)
            
            # Overall metrics
            results["overall_metrics"] = self.metrics.get_summary()
            
            return results
            
        finally:
            await self.teardown()


def print_performance_report(results: Dict[str, Any]):
    """Print a formatted performance report"""
    print("\n" + "="*70)
    print("📊 PERFORMANCE TEST RESULTS")
    print("="*70)
    
    # Throughput results
    throughput = results.get("throughput", {})
    print(f"\n🚀 THROUGHPUT PERFORMANCE:")
    print(f"   • Tasks processed: {throughput.get('num_tasks', 'N/A')}")
    print(f"   • Total time: {throughput.get('total_time', 0):.2f}s")
    print(f"   • Throughput: {throughput.get('throughput', 0):.2f} tasks/second")
    
    # API performance
    api_perf = results.get("api_performance", {})
    print(f"\n🌐 API RESPONSE TIMES:")
    for endpoint, metrics in api_perf.items():
        print(f"   • {endpoint}:")
        print(f"     - Average: {metrics.get('avg_response_time', 0)*1000:.2f}ms")
        print(f"     - P95: {metrics.get('p95_response_time', 0)*1000:.2f}ms")
    
    # Agent performance
    agent_perf = results.get("agent_performance", {})
    print(f"\n🤖 AGENT EXECUTION TIMES:")
    for agent_type, metrics in agent_perf.items():
        print(f"   • {agent_type}:")
        print(f"     - Average: {metrics.get('avg_execution_time', 0):.2f}s")
        print(f"     - Range: {metrics.get('min_execution_time', 0):.2f}s - {metrics.get('max_execution_time', 0):.2f}s")
    
    # Resource usage
    resources = results.get("resource_usage", {})
    print(f"\n📊 SYSTEM RESOURCE USAGE:")
    print(f"   • Average Memory: {resources.get('avg_memory_mb', 0):.1f}MB")
    print(f"   • Peak Memory: {resources.get('max_memory_mb', 0):.1f}MB")
    print(f"   • Average CPU: {resources.get('avg_cpu_percent', 0):.1f}%")
    print(f"   • Peak CPU: {resources.get('max_cpu_percent', 0):.1f}%")
    
    print("\n" + "="*70)
    print("✅ Performance testing completed successfully!")


async def main():
    """Main entry point for performance testing"""
    tester = PerformanceTester()
    
    try:
        results = await tester.run_full_performance_suite()
        print_performance_report(results)
        
        # Verify README claims
        throughput = results.get("throughput", {}).get("throughput", 0)
        api_avg = results.get("api_performance", {}).get("health_endpoint", {}).get("avg_response_time", 0) * 1000
        
        print(f"\n🎯 README CLAIMS VERIFICATION:")
        print(f"   • Task throughput: {throughput:.1f} tasks/sec (README: Variable based on load)")
        print(f"   • API response: {api_avg:.1f}ms (README: <50ms) {'✅' if api_avg < 50 else '⚠️'}")
        
    except Exception as e:
        print(f"❌ Performance testing failed: {e}")
        return 1
        
    return 0


if __name__ == "__main__":
    # Install required package if not available
    try:
        import psutil
    except ImportError:
        print("Installing psutil for system monitoring...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
        import psutil
        
    try:
        import aiohttp
    except ImportError:
        print("Installing aiohttp for API testing...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
        import aiohttp
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
