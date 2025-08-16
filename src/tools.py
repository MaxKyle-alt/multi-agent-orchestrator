import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .exceptions import ToolExecutionError

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    
    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        pass


class WebClient(BaseTool):
    
    def __init__(self) -> None:
        super().__init__(
            name="http_client",
            description="Make HTTP requests to external APIs",
        )

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        url = kwargs.get("url", "")
        method = kwargs.get("method", "GET")
        headers = kwargs.get("headers", {})
        
        return {
            "status_code": 200,
            "data": f"Response from {method} {url}",
            "headers": headers,
        }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target URL"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                "headers": {"type": "object"},
                "data": {"type": "object"},
            },
            "required": ["url"],
        }


class FileReader(BaseTool):
    
    def __init__(self) -> None:
        super().__init__(
            name="file_reader",
            description="Read and parse files from filesystem",
        )

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        file_path = kwargs.get("file_path", "")
        file_format = kwargs.get("format", "json")
        
        return {
            "content": f"File content from {file_path}",
            "format": file_format,
            "size": 1024,
        }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to file"},
                "format": {"type": "string", "enum": ["json", "csv", "xml", "txt"]},
            },
            "required": ["file_path"],
        }


class ChartCreator(BaseTool):
    
    def __init__(self) -> None:
        super().__init__(
            name="chart_generator",
            description="Generate charts and visualizations",
        )

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        chart_type = kwargs.get("chart_type", "line")
        data = kwargs.get("data", [])
        output_path = kwargs.get("output_path", f"/tmp/chart_{uuid4()}.png")
        
        return {
            "chart_path": output_path,
            "chart_type": chart_type,
            "data_points": len(data),
        }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "chart_type": {"type": "string", "enum": ["line", "bar", "pie", "scatter"]},
                "data": {"type": "array"},
                "output_path": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["data"],
        }


class DataTransformer(BaseTool):
    
    def __init__(self) -> None:
        super().__init__(
            name="data_processor",
            description="Process and transform data",
        )

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        operation = kwargs.get("operation", "filter")
        data = kwargs.get("data", [])
        params = kwargs.get("params", {})
        
        return {
            "processed_data": f"Applied {operation} with {params}",
            "input_size": len(data),
            "output_size": max(0, len(data) - 10),
        }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["filter", "aggregate", "transform", "sort"]},
                "data": {"type": "array"},
                "params": {"type": "object"},
            },
            "required": ["operation", "data"],
        }


class ToolBox:
    
    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._setup_defaults()

    def _setup_defaults(self) -> None:
        tools = [
            WebClient(),
            FileReader(),
            ChartCreator(),
            DataTransformer(),
        ]
        for tool in tools:
            self.add_tool(tool)

    def add_tool(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    async def run_tool(self, name: str, **kwargs: Any) -> Dict[str, Any]:
        tool = self.get_tool(name)
        if not tool:
            logger.error(f"Tool not found: {name}")
            raise ToolExecutionError(f"Tool {name} not found")
        
        try:
            logger.debug(f"Executing tool: {name}")
            result = await tool.execute(**kwargs)
            logger.debug(f"Tool {name} executed successfully")
            return result
        except Exception as e:
            logger.error(f"Tool {name} execution failed: {e}")
            raise ToolExecutionError(f"Tool {name} execution failed: {e}") from e

    def get_available_tools(self) -> List[str]:
        return list(self._tools.keys())

    def get_tool_schema(self, name: str) -> Optional[Dict[str, Any]]:
        tool = self.get_tool(name)
        return tool.get_schema() if tool else None


tool_registry = ToolBox()
