#!/usr/bin/env python3
"""
Utility module for MCP server with automatic parameter generation from Python functions.
"""

import inspect
import json
from datetime import datetime
from typing import Any, Dict, List, Callable, Optional, Union
from mcp import Tool

import requests


class ToolRegistry:
    """Registry for managing MCP tools with automatic parameter generation."""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def tool(self, func_or_name=None, description: Optional[str] = None):
        """
        Decorator to register a function as an MCP tool.

        Can be used in two ways:
        1. @tool - uses function name and docstring
        2. @tool("custom_name") or @tool(description="custom description")
        """

        def decorator(func: Callable) -> Callable:
            # Determine if first argument is a function (no parentheses) or name/description
            if callable(func_or_name):
                # Used as @tool (no parentheses)
                tool_name = func_or_name.__name__
                tool_description = func_or_name.__doc__ or f"Tool: {tool_name}"
                func = func_or_name
            else:
                # Used as @tool("name") or @tool(description="desc")
                tool_name = (
                    func_or_name if isinstance(func_or_name, str) else func.__name__
                )
                tool_description = description or func.__doc__ or f"Tool: {tool_name}"

            # Generate input schema from function signature
            input_schema = self._generate_input_schema(func)

            self._tools[tool_name] = {
                "function": func,
                "description": tool_description,
                "input_schema": input_schema,
            }

            return func

        # If called without parentheses (@tool), func_or_name is the function
        if callable(func_or_name):
            return decorator(func_or_name)
        else:
            # If called with parentheses (@tool(...)), return the decorator
            return decorator

    def _generate_input_schema(self, func: Callable) -> Dict[str, Any]:
        """Generate JSON schema from function signature."""
        sig = inspect.signature(func)
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name == "self":  # Skip self parameter
                continue

            # Determine parameter type
            param_type = self._get_json_type(param.annotation)

            # Get parameter description from docstring or default
            description = self._get_param_description(func, param_name)

            # Create the property schema
            property_schema = {"type": param_type, "description": description}

            # Handle array types - add items schema
            if param_type == "array":
                property_schema["items"] = self._get_array_items_schema(
                    param.annotation
                )

            properties[param_name] = property_schema

            # Add to required if no default value
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        return {"type": "object", "properties": properties, "required": required}

    def _get_json_type(self, annotation: Any) -> str:
        """Convert Python type annotation to JSON schema type."""
        if annotation == inspect.Parameter.empty:
            return "string"  # Default type

        # Handle typing types
        if hasattr(annotation, "__origin__"):
            if annotation.__origin__ is Union:
                # For Union types, use the first non-None type
                args = annotation.__args__
                non_none_args = [arg for arg in args if arg != type(None)]
                if non_none_args:
                    return self._get_json_type(non_none_args[0])
                return "string"
            elif annotation.__origin__ is list:
                # Handle List[str], List[int], etc.
                return "array"

        # Handle basic types
        type_mapping = {
            int: "number",
            float: "number",
            str: "string",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        return type_mapping.get(annotation, "string")

    def _get_array_items_schema(self, annotation: Any) -> Dict[str, Any]:
        """Generate items schema for array types."""
        if hasattr(annotation, "__args__") and annotation.__args__:
            # Handle List[SomeType] - get the type of items
            item_type = annotation.__args__[0]

            # Handle nested List types like List[List[float]]
            if hasattr(item_type, "__origin__") and item_type.__origin__ is list:
                # For List[List[SomeType]], return array of arrays
                if item_type.__args__:
                    inner_type = self._get_json_type(item_type.__args__[0])
                    return {"type": "array", "items": {"type": inner_type}}
                else:
                    return {"type": "array", "items": {"type": "string"}}
            else:
                # For List[SomeType], return the type of items
                inner_type = self._get_json_type(item_type)
                return {"type": inner_type}
        else:
            # Fallback for generic List
            return {"type": "string"}

    def _get_param_description(self, func: Callable, param_name: str) -> str:
        """Extract parameter description from function docstring."""
        doc = func.__doc__
        if not doc:
            return f"Parameter: {param_name}"

        # Simple parsing of docstring for parameter descriptions
        lines = doc.strip().split("\n")
        for line in lines:
            line = line.strip()
            if (
                line.startswith(f"{param_name}:")
                or line.startswith(f"Args:")
                and param_name in line
            ):
                # Extract description after colon
                if ":" in line:
                    return line.split(":", 1)[1].strip()

        return f"Parameter: {param_name}"

    def get_tools(self) -> List[Tool]:
        """Get list of MCP Tool objects."""
        tools = []
        for name, tool_info in self._tools.items():
            tools.append(
                Tool(
                    name=name,
                    description=tool_info["description"],
                    inputSchema=tool_info["input_schema"],
                )
            )
        return tools

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Call a tool by name with given arguments."""
        if name not in self._tools:
            return [{"type": "text", "text": f"Unknown tool: {name}"}]

        try:
            func = self._tools[name]["function"]
            result = func(**arguments)

            # Convert result to MCP format
            if isinstance(result, str):
                return [{"type": "text", "text": result}]
            elif isinstance(result, (dict, list)):
                # For structured data, return as JSON
                return [{"type": "text", "text": json.dumps(result, indent=2)}]
            else:
                return [{"type": "text", "text": str(result)}]

        except Exception as e:
            return [{"type": "text", "text": f"Error calling tool {name}: {str(e)}"}]


# Global registry instance
registry = ToolRegistry()


# Tool decorator for easy registration
def tool(func_or_name=None, description: Optional[str] = None):
    """Decorator to register a function as an MCP tool."""
    return registry.tool(func_or_name, description)


def format_datetime(dt) -> str:
    """
    Format a datetime object, timestamp, or other date-like object as a readable ISO string.

    Args:
        dt: The datetime object, timestamp (int/float), or other date-like object to format

    Returns:
        A formatted string representation of the datetime
    """
    if dt is None:
        return "Unknown"

    # Handle datetime objects
    if isinstance(dt, datetime):
        return dt.isoformat()

    # Handle Unix timestamps (int or float)
    if isinstance(dt, (int, float)):
        try:
            # Check if timestamp is in milliseconds (13 digits) or seconds (10 digits)
            if dt > 1e12:  # Likely milliseconds
                dt = dt / 1000.0
            # Convert Unix timestamp to datetime
            dt_obj = datetime.fromtimestamp(dt)
            return dt_obj.isoformat()
        except (ValueError, OSError):
            # If timestamp conversion fails, return the raw value
            return str(dt)

    # Handle string representations
    if isinstance(dt, str):
        return dt

    # Fallback: convert to string
    return str(dt)
