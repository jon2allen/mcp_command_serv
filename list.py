import asyncio
from fastmcp import Client, FastMCP

import json
from typing import List, Any

# Assuming the structure of your Tool object is similar to a Pydantic model
# or a dict with the relevant keys ('name', 'description', 'inputSchema').
# For the purpose of this example, we treat the Tool object as having attribute access.

class Tool:
    """Mock Tool class based on the structure in the prompt."""
    def __init__(self, name: str, description: str, inputSchema: dict):
        self.name = name
        self.description = description
        self.inputSchema = inputSchema
    
    def __repr__(self):
        # A simple __repr__ for demonstration
        return f"Tool(name='{self.name}', description='{self.description[:30]}...')"


def format_tools_for_print(tools: List[Tool]) -> str:
    """
    Formats a list of Tool objects into a readable, structured string.

    Args:
        tools: A list of Tool objects (or objects with name, description, and inputSchema attributes).

    Returns:
        A single string with all tools formatted clearly.
    """
    formatted_output = "### Available Tools Summary ###\n\n"

    for i, tool in enumerate(tools):
        # 1. Tool Name and Separator
        tool_name = tool.name
        
        # 2. Extract and clean description
        # Replace multiple spaces/newlines with a single space for compactness
        description = ' '.join(tool.description.strip().split())

        # 3. Format Input Parameters
        # Get properties from the inputSchema
        properties = tool.inputSchema.get('properties', {})
        required = tool.inputSchema.get('required', [])
        
        params_list = []
        for param_name, schema in properties.items():
            param_type = schema.get('type', 'Any')
            is_required = '*' if param_name in required else ''
            
            # Get default value if available
            default_val = schema.get('default', None)
            default_str = f" (Default: {default_val})" if default_val is not None else ""
            
            # Handle complex types like 'anyOf'
            if 'anyOf' in schema:
                param_type = " | ".join([t.get('type') for t in schema['anyOf'] if 'type' in t])

            params_list.append(
                f"  - {param_name}{is_required}: <{param_type}>{default_str}"
            )

        params_str = "\n".join(params_list) if params_list else "  (None)"
        
        # Assemble the formatted block for the current tool
        tool_block = f"""
--- Tool {i + 1}/{len(tools)} ---
* **Name:** {tool_name}
* **Purpose:** {description}
* **Inputs:**
{params_str}
"""
        formatted_output += tool_block

    formatted_output += "\n##############################"
    return formatted_output.strip()

# --- Example Usage (Using data mocked from your prompt) ---

# Mock Tool data based on your output
mock_tools_data = [
    Tool(
        name='search_date',
        description="Searches receipts by a specific date using the pre-built date index. The date format is automatically normalized internally. :param date: The date to search for (e.g., '10/20/2023', '10/20/23'). :return: A string containing the concatenated content of all matching receipt files, separated by file headers (--- FILE: filename ---), or an error message if the date format is invalid.",
        inputSchema={'properties': {'date': {'type': 'string'}}, 'required': ['date'], 'type': 'object'}
    ),
    Tool(
        name='search_item',
        description="Searches all receipt files for a specific item, using either token-based indexing (default) or a slower, case-insensitive phrase search. :param query: The item name or partial item name to search for (e.g., 'bananas', 'milk'). :param phrase: If True, performs a literal, case-insensitive substring search (slower). If False (default), uses the token index to find exact matches or tokens starting with the query (e.g., 'app' matches 'apple'). :return: A string containing the concatenated content of all matching receipt files, separated by file headers (--- FILE: filename ---), or 'No matches found.'",
        inputSchema={'properties': {'query': {'type': 'string'}, 'phrase': {'default': False, 'type': 'boolean'}}, 'required': ['query'], 'type': 'object'}
    ),
    Tool(
        name='search_sequential',
        description="Performs a sequential, full-text search across all receipt files, up to a specified limit, in the order they were loaded (`file_order`). This is a slower, fallback method compared to index-based searches. :param query: The string to search for. If None, returns the first 'limit' receipts. :param mode: The search mode. 'date' performs a sequential date match (slower than search_date). Any other value ('location', 'item', 'all', or None) performs a sequential case-insensitive substring search on the text content. :param limit: The maximum number of matching receipts to return. Defaults to 50. :return: A string containing the concatenated content of the matching receipt files, separated by file headers (--- FILE: filename ---).",
        inputSchema={'properties': {'query': {'anyOf': [{'type': 'string'}, {'type': 'null'}], 'default': None}, 'mode': {'anyOf': [{'type': 'string'}, {'type': 'null'}], 'default': None}, 'limit': {'default': 50, 'type': 'integer'}}, 'type': 'object'}
    )
]

# Run the function
# print(format_tools_for_print(mock_tools_data))

# Local Python script
client = Client("mcp_command_server_enh.py")

async def main():
    async with client:
        # Basic server interaction
        await client.ping()
        
        # List available operations
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()
        
        # Execute operations
        #        print(tools)

        formatted_tools = format_tools_for_print(tools)
        print(formatted_tools)
        print("resouces: ")
        print(resources)

asyncio.run(main())
