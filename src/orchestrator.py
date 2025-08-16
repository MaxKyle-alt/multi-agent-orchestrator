import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from .agents import Agent, agent_registry
from .models import TaskDefinition

logger = logging.getLogger(__name__)


class TaskQueue:
    
    def __init__(self) -> None:
        self.tasks: deque[TaskDefinition] = deque()
        self.completed: Dict[UUID, TaskDefinition] = {}
        self.lock = asyncio.Lock()

    async def add_task(self, task: TaskDefinition) -> None:
        async with self.lock:
            self.tasks.append(task)

    async def get_next_task(self) -> Optional[TaskDefinition]:
        async with self.lock:
            if self.tasks:
                return self.tasks.popleft()
            return None

    async def complete_task(self, task: TaskDefinition) -> None:
        async with self.lock:
            self.completed[task.task_id] = task

    async def get_task(self, task_id: UUID) -> Optional[TaskDefinition]:
        async with self.lock:
            for task in self.tasks:
                if task.task_id == task_id:
                    return task
            return self.completed.get(task_id)

    async def size(self) -> int:
        return len(self.tasks)


class WorkerPool:
    
    def __init__(self) -> None:
        self.agents: Dict[str, List[Agent]] = defaultdict(list)

    async def get_agent(self, agent_type: str) -> Optional[Agent]:
        for agent in self.agents.get(agent_type, []):
            if agent.status.value == "idle":
                return agent
        
        try:
            new_agent = agent_registry.create_agent(agent_type)
            self.agents[agent_type].append(new_agent)
            return new_agent
        except ValueError as e:
            raise ValueError(f"Unknown agent type '{agent_type}': {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Failed to create agent of type '{agent_type}': {str(e)}")

    async def get_stats(self) -> Dict[str, Any]:
        stats = {}
        for agent_type, agents in self.agents.items():
            total = len(agents)
            available = sum(1 for agent in agents if agent.status.value == "idle")
            stats[agent_type] = {
                "total": total, 
                "available": available, 
                "busy": total - available
            }
        return stats


class TaskManager:
    
    def __init__(self, max_workers: int = 10) -> None:
        self.task_queue = TaskQueue()
        self.worker_pool = WorkerPool()
        self.max_workers = max_workers
        self.running = False
        self.workers: List[asyncio.Task] = []

    async def submit_task(self, task: TaskDefinition) -> UUID:
        await self.task_queue.add_task(task)
        return task.task_id

    async def get_task_status(self, task_id: UUID) -> Optional[TaskDefinition]:
        return await self.task_queue.get_task(task_id)

    async def start(self) -> None:
        if self.running:
            return
        
        self.running = True
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)

    async def stop(self) -> None:
        self.running = False
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()

    async def _worker(self, name: str) -> None:
        while self.running:
            try:
                task = await self.task_queue.get_next_task()
                if not task:
                    await asyncio.sleep(0.1)
                    continue

                try:
                    agent = await self.worker_pool.get_agent(task.agent_type)
                    await self._execute_task(agent, task)
                except ValueError as e:
                    task.fail(f"Invalid agent type: {str(e)}")
                    await self.task_queue.complete_task(task)
                except RuntimeError as e:
                    task.fail(f"Agent creation failed: {str(e)}")
                    await self.task_queue.complete_task(task)
                
            except Exception as e:
                logger.error(f"Worker {name} error: {str(e)}")
                await asyncio.sleep(1)

    async def _execute_task(self, agent: Agent, task: TaskDefinition) -> None:
        try:
            await agent.handle_task(task)
            await self.task_queue.complete_task(task)
        except Exception as e:
            task.fail(str(e))
            await self.task_queue.complete_task(task)

    async def get_stats(self) -> Dict[str, Any]:
        queue_size = await self.task_queue.size()
        agent_stats = await self.worker_pool.get_stats()
        
        return {
            "queue_size": queue_size,
            "agents": agent_stats,
            "workers": len(self.workers),
            "running": self.running,
            "timestamp": datetime.utcnow()
        }
