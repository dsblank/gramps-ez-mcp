# gramps-ez-mcp

An easy-to-use MCP (Model Context Protocol) server to interact with Gramps genealogy family trees. This package provides a bridge between AI assistants and your Gramps database, enabling natural language queries about your family tree.

## Installation

Install the package using pip:

```bash
pip install gramps-ez-mcp
```

## Overview

`gramps-ez-mcp` is an MCP server that exposes your Gramps genealogy database through a standardized protocol. It allows AI assistants and chatbots to query and explore your family tree data using natural language.

The server provides tools for:
- Searching for people by name
- Retrieving person details (birth, death, events, etc.)
- Navigating family relationships (parents, children, spouses)
- Accessing family and event information
- Querying the home person

## Configuration

### Setup

You will need the following:

1. An API key from a model provider (such as OpenAI, Anthropic, etc)
2. Gramps installed and working with a family tree (may also need `pip install gramps`)

For example, you might have in your environment:

```
export OPENAI_API_KEY="sk-..."
```

### Basic Configuration

The MCP server can be configured using command-line arguments or through MCP client configuration files.

#### Command-Line Usage

```bash
gramps-ez-mcp DBNAME [OPTIONS]
```

**Arguments:**
- `DBNAME`: Name of the Gramps database tree to open (required)

**Options:**
- `--transport {stdio,sse}`: Transport method to use (default: `stdio`)
- `--host HOST`: Host for SSE transport (default: `localhost`)
- `--port PORT`: Port for SSE transport (default: `8000`)

**Examples:**

```bash
# Use stdio transport with a database
gramps-ez-mcp "Gramps Example"

# Specify a custom database name
gramps-ez-mcp "My Family Tree"

# Use SSE transport on a custom port
gramps-ez-mcp "Gramps Example" --transport sse --port 9000
```

### MCP Client Configuration

For use with MCP-compatible clients (like `ez-mc-chatbot`, Cursor, etc), you will need a configuration file.

For example, for `ez-mcp-chatbot`:

**Example: `ez-config.json`**

```json
{
  "model": "openai/gpt-4o-mini",
  "model_parameters": {
    "temperature": 0.0
  },
  "mcp_servers": [
    {
      "name": "gramps-ez-mcp",
      "description": "Gramps EZ MCP server for genealogy chats",
      "command": "gramps-ez-mcp",
      "args": ["Gramps Example"]
    }
  ]
}
```

Replace `"Gramps Example"` with your actual Gramps database name.

## Usage Examples

### Using with ez-mc-chatbot

The `ez-mc-chatbot` is a command-line chatbot that can interact with MCP servers. Here's how to use it with `gramps-ez-mcp`:

1. **Install ez-mc-chatbot** (if not already installed):
   ```bash
   pip install ez-mcp-toolbox
   ```

2. **Create a configuration file** (e.g., `examples/ez-config.json`):
   ```json
   {
     "model": "openai/gpt-4o-mini",
     "model_parameters": {
       "temperature": 0.0
     },
     "mcp_servers": [
       {
         "name": "gramps-ez-mcp",
         "description": "Gramps EZ MCP server for genealogy chats",
         "command": "gramps-ez-mcp",
         "args": ["Gramps Example"]
       }
     ]
   }
   ```

3. **Run the chatbot**:
   ```bash
   ez-mc-chatbot --config examples/ez-config.json
   ```

4. **Example queries you can ask**:
   - "Who is the home person in my family tree?"
   - "Search for people named John Smith"
   - "What is his birth date?"
   - "Who are the children of John?"
   - "Find the mother of Sarah Anderson"

### LLM Logging, Debugging, and Observability

If you would like for the `ez-mcp-chatbot` to create a log of what the MCP server is doing, you can log the interactions
with the LLM by doing the following:

```
pip install opik
```
Then you can get an OPIK_API_KEY from https://www.comet.com/docs/opik/quickstart
and set it:

```
export OPIK_API_KEY="..."
```

<img width="1853" height="1048" alt="image" src="https://github.com/user-attachments/assets/13063484-8544-4464-ae5a-93d750cc67ae" />

### Example Conversation

```
You: Who is the home person in my family tree?

Assistant: I'll look up the home person for you.
[Uses get_home_person tool]
The home person is John Doe (born 1950-01-15).

You: Who are their children?

Assistant: Let me find the children of John Doe.
[Uses get_children_of_person tool]
John Doe has 2 children:
- Jane Doe (handle: abc123)
- Bob Doe (handle: def456)
```

## Available Tools

The following tools are available through the MCP server:

### Person Tools

- **`get_person(person_handle: str)`**
  - Get complete data dictionary for a person by their handle
  - Returns: Dictionary with all person data

- **`search_people_by_name(name: str, page: int = 1, page_size: int = 10)`**
  - Search for people by name (partial match, case-insensitive)
  - Supports pagination
  - Returns: List of matching person dictionaries

- **`get_home_person()`**
  - Get the home person data from the database
  - Returns: Dictionary with home person data

### Relationship Tools

- **`get_father_of_person(person_handle: str)`**
  - Get the father's data for a person
  - Returns: Dictionary with father's data

- **`get_mother_of_person(person_handle: str)`**
  - Get the mother's data for a person
  - Returns: Dictionary with mother's data

- **`get_children_of_person(person_handle: str)`**
  - Get list of children handles for a person's main family
  - Returns: List of child handles (strings)

### Date and Place Tools

- **`get_person_birth_date(person_handle: str)`**
  - Get birth date as a string
  - Returns: Birth date string

- **`get_person_death_date(person_handle: str)`**
  - Get death date as a string
  - Returns: Death date string

- **`get_person_birth_place(person_handle: str)`**
  - Get birth place as a string
  - Returns: Birth place string

- **`get_person_death_place(person_handle: str)`**
  - Get death place as a string
  - Returns: Death place string

### Family and Event Tools

- **`get_family(family_handle: str)`**
  - Get family data by family handle
  - Note: Family handles are different from person handles
  - Returns: Dictionary with family data

- **`get_person_event_list(person_handle: str)`**
  - Get list of event handles associated with a person
  - Returns: List of event handles (strings)

- **`get_event(event_handle: str)`**
  - Get event data by event handle
  - Returns: Dictionary with event data

- **`get_event_place(event_handle: str)`**
  - Get the place associated with an event
  - Returns: Place string

## Requirements

- Python 3.8 or higher
- Gramps (genealogy software)
- MCP-compatible client (for using the server)

## Troubleshooting

### Database Not Found

If you get an error that the database was not found:
- Verify the database name matches exactly (case-sensitive)
- Check that the database exists in your Gramps data directory
- Use the exact name as shown in Gramps

## License

This project is licensed under the GNU General Public License version 2 (GPL-2.0). See the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Links

- **Homepage**: https://github.com/dsblank/gramps-ez-mcp
- **Repository**: https://github.com/dsblank/gramps-ez-mcp
- **Bug Tracker**: https://github.com/dsblank/gramps-ez-mcp/issues
