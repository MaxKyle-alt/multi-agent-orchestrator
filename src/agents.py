import asyncio
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Type
from uuid import UUID, uuid4

from .exceptions import AgentExecutionError, TaskTimeoutError
from .models import AgentStatus, TaskDefinition

logger = logging.getLogger(__name__)


class Agent(ABC):
    
    def __init__(self, agent_type: str, capabilities: Optional[List[str]] = None, **kwargs: Any) -> None:
        self.agent_id = kwargs.get("agent_id", uuid4())
        self.agent_type = agent_type
        self.capabilities = capabilities or []
        self.status = AgentStatus.idle
        self.current_task_id: Optional[UUID] = None
        self.created_at = datetime.utcnow()

    @abstractmethod
    async def execute_task(self, task: TaskDefinition) -> Dict[str, Any]:
        pass

    async def handle_task(self, task: TaskDefinition) -> Dict[str, Any]:
        try:
            self.status = AgentStatus.busy
            self.current_task_id = task.task_id
            
            task.start(self.agent_id)
            logger.info(f"Agent {self.agent_type} started task {task.task_id}")
            
            result = await self.execute_task(task)
            
            task.complete(result)
            logger.info(f"Agent {self.agent_type} completed task {task.task_id}")
            
            return result
        except Exception as e:
            error_msg = f"Task execution failed: {str(e)}"
            task.fail(error_msg)
            logger.error(f"Agent {self.agent_type} failed task {task.task_id}: {str(e)}")
            
            if isinstance(e, (TaskTimeoutError, AgentExecutionError)):
                raise
            
            raise AgentExecutionError(
                f"Agent {self.agent_type} failed to execute task {task.task_id}: {str(e)}"
            ) from e
        finally:
            self.status = AgentStatus.idle
            self.current_task_id = None

    def can_handle(self, task: TaskDefinition) -> bool:
        return task.agent_type == self.agent_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": str(self.agent_id),
            "agent_type": self.agent_type,
            "capabilities": self.capabilities,
            "status": self.status.value,
            "current_task_id": str(self.current_task_id) if self.current_task_id else None,
            "created_at": self.created_at.isoformat(),
        }


class DataCollector(Agent):
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_type="data_fetcher", capabilities=["fetch_data"], **kwargs)

    async def execute_task(self, task: TaskDefinition) -> Dict[str, Any]:
        await asyncio.sleep(random.uniform(1.0, 2.5))
        params = task.task_params
        source = params.get("source", "api")
        url = params.get("url", "https://example.com/api/data")
        
        # Mock artificial failure for demonstration (10% failure rate)
        if random.random() < 0.1:
            logger.warning(f"Simulated failure: Failed to fetch data from {source}")
            raise Exception(f"Failed to fetch data from {source}")
        
        logger.debug(f"Data fetcher returning {source} data")
        return {
            "data": {"records": list(range(random.randint(5, 50)))},
            "source": source, 
            "url": url,
            "size_mb": round(random.uniform(0.1, 5.0), 2)
        }


class ChartMaker(Agent):
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_type="chart_generator", capabilities=["create_chart"], **kwargs)

    async def execute_task(self, task: TaskDefinition) -> Dict[str, Any]:
        await asyncio.sleep(random.uniform(0.5, 1.5))
        params = task.task_params
        chart_type = params.get("chart_type", "line")
        data_source = params.get("data_source", {})
        
        # Mock artificial failure for demonstration (10% failure rate)
        if random.random() < 0.1:
            logger.warning(f"Simulated failure: Chart generation failed for {chart_type}")
            raise Exception(f"Chart generation failed for {chart_type}")
            
        data_points = len(data_source.get("data", []))
        logger.debug(f"Chart generator creating {chart_type} chart with {data_points} points")
        return {
            "chart_url": f"/charts/{task.task_id}.png", 
            "chart_type": chart_type,
            "data_points": data_points if data_points > 0 else random.randint(10, 100), 
            "format": "png"
        }


class DataProcessor(Agent):
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_type="data_processor", capabilities=["transform_data"], **kwargs)

    async def execute_task(self, task: TaskDefinition) -> Dict[str, Any]:
        await asyncio.sleep(random.uniform(1.0, 2.0))
        params = task.task_params
        operation = params.get("operation", "aggregate")
        input_data = params.get("input_data", {})
        
        return {
            "processed_data": f"Processed {operation} operation",
            "input_records": len(input_data.get("records", [])), 
            "output_records": random.randint(20, 80), 
            "operation": operation
        }


class ScriptRunner(Agent):
    
    def __init__(self, agent_type: str, code: str, **kwargs: Any) -> None:
        super().__init__(agent_type=agent_type, **kwargs)
        self.code = code

    async def execute_task(self, task: TaskDefinition) -> Dict[str, Any]:
        try:
            safe_builtins = {
                "__builtins__": {
                    "len": len, "str": str, "int": int, "float": float, 
                    "dict": dict, "list": list, "min": min, "max": max, "round": round
                },
                "asyncio": asyncio,
                "task": task,
                "result": {},
                "time": __import__("time"),
            }
            
            exec(self.code, safe_builtins)
            logger.debug(f"Custom agent {self.agent_type} executed successfully")
            
            return safe_builtins.get("result", {"status": "completed", "agent_type": self.agent_type})
        except Exception as e:
            logger.error(f"Custom agent {self.agent_type} execution failed: {str(e)}")
            return {"status": "failed", "error": str(e), "agent_type": self.agent_type}


class AgentBuilder:
    
    def __init__(self) -> None:
        self.templates: Dict[str, Dict[str, Any]] = {}

    def save_template(self, agent_type: str, template: Dict[str, Any]) -> None:
        self.templates[agent_type] = template
        logger.info(f"Saved agent template: {agent_type}")

    def create_agent(self, agent_type: str, **overrides: Any) -> Agent:
        if agent_type not in self.templates:
            logger.error(f"No template found for agent type: {agent_type}")
            raise ValueError(f"No template for agent type: {agent_type}")
        
        template = self.templates[agent_type].copy()
        template.update(overrides)
        
        code = template.pop("code", template.pop("code_to_run", "result = {'status': 'completed'}"))
        template.pop("agent_type", None)
        
        logger.debug(f"Creating custom agent: {agent_type}")
        return ScriptRunner(agent_type=agent_type, code=code, **template)

    def get_templates(self) -> List[str]:
        return list(self.templates.keys())


class AgentManager:
    
    def __init__(self) -> None:
        self.agent_classes: Dict[str, Type[Agent]] = {}
        self.builder = AgentBuilder()
        self._setup_defaults()

    def _setup_defaults(self) -> None:
        self.add_agent("data_fetcher", DataCollector)
        self.add_agent("chart_generator", ChartMaker)
        self.add_agent("data_processor", DataProcessor)

    def add_agent(self, agent_type: str, agent_class: Type[Agent]) -> None:
        self.agent_classes[agent_type] = agent_class

    def save_template(self, agent_type: str, template: Dict[str, Any]) -> None:
        self.builder.save_template(agent_type, template)

    def create_agent(self, agent_type: str, **kwargs: Any) -> Agent:
        if agent_type in self.agent_classes:
            return self.agent_classes[agent_type](**kwargs)
        return self.builder.create_agent(agent_type, **kwargs)

    def get_available_types(self) -> List[str]:
        builtin = list(self.agent_classes.keys())
        custom = self.builder.get_templates()
        return builtin + custom


agent_registry = AgentManager()
