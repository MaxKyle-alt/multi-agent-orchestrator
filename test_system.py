#!/usr/bin/env python3

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agents import agent_registry
from src.models import TaskDefinition
from src.orchestrator import TaskOrchestrator


async def test_system():
    print("🔧 Testing multi-agent system...")
    
    print(f"📋 Available agents: {agent_registry.get_available_types()}")
    
    orch = TaskOrchestrator()
    await orch.start()
    print("✅ Orchestrator started")
    
    task = TaskDefinition(
        task_name='test_data_fetch',
        agent_type='data_fetcher',
        task_params={'url': 'https://api.example.com', 'source_type': 'api'}
    )
    
    task_id = await orch.submit_task(task)
    print(f"📤 Task submitted with ID: {task_id}")
    
    print("⏳ Waiting for task completion...")
    await asyncio.sleep(3)
    
    result_task = await orch.get_task_status(task_id)
    print(f"✅ Task completed with status: {result_task.status}")
    if result_task.result:
        print(f"📊 Result: {result_task.result}")
    if result_task.error_message:
        print(f"❌ Error: {result_task.error_message}")
    
    stats = await orch.get_stats()
    print(f"📈 System stats: {stats}")
    
    await orch.stop()
    print("🎉 Test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_system())
