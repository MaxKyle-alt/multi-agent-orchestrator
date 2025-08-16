import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agents import agent_registry
from .models import TaskDefinition
from .orchestrator import TaskManager
from .tools import tool_registry

logger = logging.getLogger(__name__)


class CreateTaskRequest(BaseModel):
    task_name: str
    agent_type: str
    task_params: Dict[str, Any] = {}


task_manager = TaskManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Starting task manager")
        await task_manager.start()
        yield
    finally:
        logger.info("Stopping task manager")
        await task_manager.stop()


app = FastAPI(
    title="Multi-Agent Task Solver",
    description="Simple multi-agent orchestration system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}


@app.get("/stats")
async def get_stats():
    stats = await task_manager.get_stats()
    return {
        "system": stats,
        "agents": agent_registry.get_available_types(),
        "tools": tool_registry.get_available_tools(),
        "timestamp": datetime.utcnow(),
    }


@app.post("/tasks", response_model=Dict[str, Any])
async def submit_task(request: CreateTaskRequest):
    if request.agent_type not in agent_registry.get_available_types():
        logger.warning(f"Task submission failed: Unknown agent type {request.agent_type}")
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent type: {request.agent_type}",
        )

    task_definition = TaskDefinition(
        task_name=request.task_name,
        agent_type=request.agent_type,
        task_params=request.task_params,
    )

    try:
        task_id = await task_manager.submit_task(task_definition)
        logger.info(f"Task submitted: {task_id} ({request.agent_type})")
        return {
            "task_id": str(task_id),
            "status": "submitted",
            "created_at": task_definition.created_at,
        }
    except Exception as e:
        logger.error(f"Task submission failed: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    try:
        task_uuid = UUID(task_id)
        task = await task_manager.get_task_status(task_uuid)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {
            "task_id": str(task.task_id),
            "task_name": task.task_name,
            "status": task.status,
            "result": task.result,
            "error_message": task.error_message,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")


@app.get("/agents")
async def list_agents():
    return {"agent_types": agent_registry.get_available_types(), "timestamp": datetime.utcnow()}


@app.post("/agents/add")
async def add_agent_template(agent_template: Dict[str, Any]):
    try:
        agent_type = agent_template.get("agent_type")
        if not agent_type:
            logger.warning("Agent template submission failed: missing agent_type")
            raise HTTPException(status_code=400, detail="agent_type is required")
        
        agent_registry.save_template(agent_type, agent_template)
        logger.info(f"Agent template added: {agent_type}")
        return {"status": "success", "message": f"Agent template '{agent_type}' saved"}
    except Exception as e:
        logger.error(f"Failed to add agent template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents/templates")
async def list_templates():
    return {"templates": agent_registry.builder.get_templates(), "timestamp": datetime.utcnow()}


@app.get("/tools")
async def list_tools():
    tools = {}
    for tool_name in tool_registry.get_available_tools():
        schema = tool_registry.get_tool_schema(tool_name)
        tools[tool_name] = schema
    
    return {
        "tools": tools,
        "timestamp": datetime.utcnow(),
    }


@app.post("/tools/{tool_name}/run")
async def run_tool(tool_name: str, parameters: Dict[str, Any]):
    try:
        result = await tool_registry.run_tool(tool_name, **parameters)
        return {
            "tool": tool_name,
            "result": result,
            "executed_at": datetime.utcnow(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
