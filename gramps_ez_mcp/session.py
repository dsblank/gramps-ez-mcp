#!/usr/bin/env python3
"""
Session management for MCP server with Gramps db singleton access.
"""

import os
from contextlib import contextmanager
from typing import Optional, Generator

from gramps.gen.db import Database
from gramps.gen.db.utils import open_database
from gramps.gen.simple import SimpleAccess


class SessionContext:
    """Context manager for Gramps database singleton access."""

    def __init__(self):
        self._db: Optional[Database] = None
        self._initialized = False

    def initialize(self, dbname: Optional[str] = None):
        """Initialize the Gramps database instance with configuration.

        Args:
            dbname: Name of the Gramps database tree to open. If None, defaults to "Gramps Example".
        """
        if self._initialized:
            return

        if dbname is None:
            dbname = "Gramps Example"

        self._db = open_database(dbname, force_unlock=True)
        if self._db is None:
            raise Exception(f"Gramps database '{dbname}' was not found")

        self._db.sa = SimpleAccess(self._db)
        self._initialized = True

    @property
    def database(self) -> Database:
        if not self._initialized or self._db is None:
            raise RuntimeError("Session not initialized. Call initialize() first.")
        return self._db

    def is_initialized(self) -> bool:
        """Check if the session is initialized."""
        return self._initialized

    def reset(self):
        """Reset the session (useful for testing or reconfiguration)."""
        self._db = None
        self._initialized = False


# Global session context instance
session_context = SessionContext()


@contextmanager
def gramps_database() -> Generator[Database, None, None]:
    """
    Context manager to get the Gramps database instance.
    """
    if not session_context.is_initialized():
        raise RuntimeError(
            "Session not initialized. Call session_context.initialize() first."
        )

    yield session_context.database


def initialize_session(dbname: Optional[str] = None):
    """Initialize the global session context.

    Args:
        dbname: Name of the Gramps database tree to open. If None, defaults to "Gramps Example".
    """
    session_context.initialize(dbname)


def get_session_context() -> SessionContext:
    """Get the global session context instance."""
    return session_context
