#!/usr/bin/env python3
"""
Model Context Protocol server for Gramps Database.
"""

# CRITICAL: Set environment variables BEFORE any other imports
# This must happen before Gramps or GTK modules are imported
import os
import sys
import threading

# Suppress GTK warnings in headless mode
os.environ.setdefault("GDK_BACKEND", "x11")
os.environ.setdefault("NO_AT_BRIDGE", "1")
os.environ.setdefault("GTK_USE_PORTAL", "0")
os.environ.setdefault("G_MESSAGES_DEBUG", "")


# Redirect stderr at file descriptor level to filter GTK warnings
# This intercepts C-level output that bypasses Python's stderr
def setup_stderr_filter():
    """Set up file descriptor-level stderr filtering for GTK warnings."""
    # Save original stderr file descriptor by duplicating it
    original_stderr_fd = sys.stderr.fileno()
    saved_stderr_fd = os.dup(original_stderr_fd)

    # Create a pipe
    read_fd, write_fd = os.pipe()

    # Redirect stderr to the write end of the pipe
    os.dup2(write_fd, original_stderr_fd)
    os.close(write_fd)

    # Create a thread to read from the pipe and filter
    def filter_thread():
        gtk_patterns = [
            b"Gtk-CRITICAL",
            b"gtk_icon_theme_get_for_screen",
            b"GDK_IS_SCREEN",
            b"Gtk-WARNING",
        ]

        # Use the saved file descriptor for writing
        original_stderr = os.fdopen(saved_stderr_fd, "wb", buffering=0)

        try:
            buffer = b""
            while True:
                try:
                    # Read from pipe (blocking)
                    data = os.read(read_fd, 4096)
                    if not data:
                        break

                    buffer += data
                    # Process complete lines
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        line += b"\n"

                        # Filter out GTK warnings
                        if not any(pattern in line for pattern in gtk_patterns):
                            original_stderr.write(line)
                            original_stderr.flush()
                except (OSError, ValueError, BrokenPipeError):
                    break

            # Write any remaining buffer
            if buffer:
                if not any(pattern in buffer for pattern in gtk_patterns):
                    original_stderr.write(buffer)
                    original_stderr.flush()
        finally:
            original_stderr.close()
            os.close(read_fd)

    # Start the filter thread as a daemon so it doesn't block exit
    thread = threading.Thread(target=filter_thread, daemon=True)
    thread.start()


# Set up the filter
setup_stderr_filter()

import argparse
import asyncio
import json
import signal
from typing import Any, Dict, List

from mcp import Tool
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Import our tools module and registry
from . import tool_loader  # This ensures tools are registered
from .utils import registry
from .session import initialize_session

# SSE transport imports
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn

# Create the server
server = Server("gramps-ez-mcp")

# Global variable to track server state for clean shutdown
_server_task = None


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Gramps EZ MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport method to use (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host for SSE transport (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)",
    )
    parser.add_argument(
        "--dbname",
        default=None,
        help="Name of the Gramps database tree to open (default: 'Gramps Example')",
    )
    return parser.parse_args()


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools."""
    return registry.get_tools()


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Handle tool calls."""
    return registry.call_tool(name, arguments)


# SSE transport implementation
app = FastAPI(title="Gramps EZ MCP Server", version="1.0.0")

# Global variables for SSE communication
_sse_clients = set()
_message_queue = asyncio.Queue()


@app.get("/sse")
async def sse_endpoint():
    """SSE endpoint for server-to-client communication."""

    async def event_generator():
        # Add client to the set
        client_id = id(asyncio.current_task())
        _sse_clients.add(client_id)
        print(f"🔌 SSE client connected: {client_id}")

        try:
            while True:
                # Wait for messages from the message queue
                try:
                    message = await asyncio.wait_for(_message_queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(message)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
        except asyncio.CancelledError:
            print(f"🔌 SSE client disconnected: {client_id}")
        finally:
            _sse_clients.discard(client_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        },
    )


@app.post("/messages")
async def message_endpoint(request: Request):
    """HTTP POST endpoint for client-to-server communication."""
    try:
        data = await request.json()
        print(f"📨 Received message: {data}")

        # Process the message through the MCP server
        # This is a simplified implementation - in a real scenario,
        # you'd need to properly handle MCP protocol messages
        response = {"status": "received", "data": data}

        # Send response back via SSE
        await _message_queue.put(response)

        return {"status": "success", "message": "Message processed"}
    except Exception as e:
        print(f"❌ Error processing message: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "transport": "sse"}


async def start_sse_server(host: str, port: int):
    """Start the SSE server."""
    print(f"🚀 Starting SSE server on {host}:{port}")
    print(f"📡 SSE endpoint: http://{host}:{port}/sse")
    print(f"📨 Messages endpoint: http://{host}:{port}/messages")
    print(f"🏥 Health check: http://{host}:{port}/health")

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server_instance = uvicorn.Server(config)
    await server_instance.serve()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    print("\n🛑 Received shutdown signal, cleaning up...")
    if _server_task and not _server_task.done():
        _server_task.cancel()
    # Force immediate exit to avoid waiting for stdin
    os._exit(0)


async def main():
    """Run the server."""
    global _server_task

    # Parse command line arguments
    args = parse_args()

    print("🚀 Gramps EZ MCP Server Starting...")
    print(f"🚌 Transport: {args.transport}")

    # Set up signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        initialize_session(args.dbname)
        dbname_used = args.dbname if args.dbname else "Gramps Example"
        print(f"✓ Gramps EZ MCP session initialized with database: {dbname_used}")
    except Exception as e:
        print(f"⚠️  Gramps EZ MCP session initialization failed: {e}")

    print(
        f"🔧 Available Gramps EZ MCP tools: {[tool.name for tool in registry.get_tools()]}"
    )

    try:
        if args.transport == "stdio":
            # Use stdio transport (default)
            async with stdio_server() as (read_stream, write_stream):
                _server_task = asyncio.create_task(
                    server.run(
                        read_stream,
                        write_stream,
                        server.create_initialization_options(),
                    )
                )
                await _server_task
        elif args.transport == "sse":
            # Use SSE transport
            await start_sse_server(args.host, args.port)
        else:
            print(f"❌ Unknown transport: {args.transport}")
            sys.exit(1)
    except asyncio.CancelledError:
        print("🛑 Server shutdown completed")
        # Force immediate exit to avoid waiting for stdin
        os._exit(0)
    except KeyboardInterrupt:
        print("\n🛑 Received keyboard interrupt, shutting down...")
        # Force immediate exit to avoid waiting for stdin
        os._exit(0)
    except Exception as e:
        print(f"❌ Server error: {e}")
        raise


def main_sync():
    """Synchronous entry point for the gramps-ez-mcp command."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
