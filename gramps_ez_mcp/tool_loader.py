#!/usr/bin/env python3
"""
Tool loader for Comet ML MCP server.
Dynamically loads and decorates functions from tools.py.
"""

import inspect
import importlib.util
import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from .utils import tool
from . import tools


def _load_tools():
    """Dynamically load and decorate all functions from tools module."""
    # Get all functions from the tools module
    for name, obj in inspect.getmembers(tools):
        if inspect.isfunction(obj) and not name.startswith('_'):
            # Check if this function should be decorated as a tool
            # Criteria: 
            # 1. Has a docstring (indicates it's a user-facing function)
            # 2. Is not a private function (doesn't start with _)
            # 3. Is not a built-in type or import (check module name)
            # 4. Is not a utility function (check if it's from a different module)
            if (obj.__doc__ and 
                not name.startswith('_') and 
                obj.__module__ == tools.__name__):
                # Apply the @tool decorator to the function
                decorated_func = tool(obj)
                # Make the decorated function available in this module's namespace
                globals()[name] = decorated_func


# Load all tools when this module is imported
_load_tools()