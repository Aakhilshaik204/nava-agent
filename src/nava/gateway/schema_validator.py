from typing import Dict, Any, Optional
from nava.core.schemas import ToolRequest
from nava.gateway.pipeline import SchemaValidator
from nava.tools.registry import ToolRegistry

class DefaultSchemaValidator(SchemaValidator):
    """
    Validates tool requests against registered tool input schemas.
    Supports both JSON-Schema standard objects and flat parameter type maps.
    """
    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry

    def _check_type(self, value: Any, expected_type: str) -> bool:
        exp = expected_type.lower()
        if exp in ["string", "str"]:
            return isinstance(value, str)
        elif exp in ["integer", "int"]:
            return isinstance(value, int) and not isinstance(value, bool)
        elif exp in ["number", "float"]:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        elif exp in ["boolean", "bool"]:
            return isinstance(value, bool)
        elif exp in ["array", "list"]:
            return isinstance(value, list)
        elif exp in ["object", "dict"]:
            return isinstance(value, dict)
        elif exp in ["any"]:
            return True
        return True

    def validate(self, request: ToolRequest) -> bool:
        if not request.tool_name:
            return False
        if not isinstance(request.arguments, dict):
            return False

        if not self.registry:
            return True # Fallback if registry not injected

        try:
            tool_def = self.registry.get_tool(request.tool_name)
        except KeyError:
            # If tool is not registered, fail validation
            return False

        schema = tool_def.input_schema or {}
        args = request.arguments or {}

        # 1. Standard JSON Schema Object (e.g. {"type": "object", "properties": {...}, "required": [...]})
        if isinstance(schema, dict) and "properties" in schema:
            properties = schema.get("properties", {})
            required_fields = schema.get("required", [])

            for req in required_fields:
                if req not in args:
                    return False

            for param_name, val in args.items():
                if param_name in properties:
                    param_spec = properties[param_name]
                    if isinstance(param_spec, dict):
                        expected_type = param_spec.get("type", "any")
                        if not self._check_type(val, expected_type):
                            return False

        # 2. Flat Type Map (e.g. {"filename": "string", "content": "string"})
        elif isinstance(schema, dict):
            for param_name, type_spec in schema.items():
                if isinstance(type_spec, str):
                    if param_name in args:
                        if not self._check_type(args[param_name], type_spec):
                            return False

        return True
