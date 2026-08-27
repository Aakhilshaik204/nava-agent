from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from nava.core.schemas import RiskTier

class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    permissions_required: List[str]
    risk_level: RiskTier
    required_credentials: List[str] = Field(default_factory=list)
    reversible: bool
    rollback_strategy: Optional[str] = None
    rollback_cost: Optional[str] = None
    rollback_window: Optional[str] = None

class ToolRegistry:
    """
    Centralized interface for all capabilities (local and external MCP).
    """
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    @property
    def tools(self) -> Dict[str, ToolDefinition]:
        return self._tools

    def register_tool(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name} is already registered.")
        self._tools[tool.name] = tool

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def get_tool(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Tool {name} not found in registry.")
        return self._tools[name]
        
    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())
