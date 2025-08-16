from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class AgentStatus(str, Enum):
    idle = "idle"
    busy = "busy"


class TaskDefinition(BaseModel):
    task_id: UUID = Field(default_factory=uuid4)
    task_name: str
    agent_type: str
    task_params: Dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.pending
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_agent_id: Optional[UUID] = None
    
    def start(self, agent_id: UUID) -> None:
        self.status = TaskStatus.running
        self.assigned_agent_id = agent_id
        self.started_at = datetime.utcnow()
    
    def complete(self, result: Dict[str, Any]) -> None:
        self.status = TaskStatus.completed
        self.result = result
        self.completed_at = datetime.utcnow()
    
    def fail(self, error_message: str) -> None:
        self.status = TaskStatus.failed
        self.error_message = error_message
        self.completed_at = datetime.utcnow()
