#!/usr/bin/env python3
import argparse
import asyncio
import os
import sys

from fastmcp import Client
from google import genai

# --- Initialization (Outside main) ---
mcp_client = Client("./mcp_command_server_enh.py")
# Assuming gemini_client initialization is safe outside the async function
# and that API key is set via environment variable (e.g., GEMINI_API_KEY)
try:
    gemini_client = genai.Client()
except Exception as e:
    # Handle the case where the client cannot be initialized (e.g., no API key)
    print(f"Error initializing Gemini client: {e}", file=sys.stderr)
    sys.exit(1)

async def run_query(prompt_content: str):
    """
    Core async function to interact with FastMCP and Gemini.
    Takes the prompt content as an argument.
    """
    if not prompt_content:
        print("Error: Prompt content is empty.", file=sys.stderr)
        return

    print(f"Sending prompt to Gemini/FastMCP: '{prompt_content[:80]}...'")

    try:
        async with mcp_client:
            # The only change here is replacing the hardcoded string with the variable
            response = await gemini_client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt_content,  # Use the dynamic prompt
                config=genai.types.GenerateContentConfig(
                    temperature=0,
                    tools=[mcp_client.session],  # Pass the FastMCP client session
                ),
            )
            print("--- Response ---")
            print(response.text)
            print("----------------")
    except Exception as e:
        print(f"An error occurred during the API call: {e}", file=sys.stderr)

# The original main function is now for argument parsing and setup
def main():
    parser = argparse.ArgumentParser(
        description="Run a prompt against the Gemini API using FastMCP for tool access."
    )
    # Mutually exclusive group for -p and -f
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "-p", "--prompt",
        type=str,
        help="Prompt text from the command line."
    )
    group.add_argument(
        "-f", "--file",
        type=str,
        help="Path to a text file containing the prompt."
    )

    args = parser.parse_args()
    prompt_content = None

    if args.prompt:
        prompt_content = args.prompt
    elif args.file:
        try:
            with open(args.file, 'r') as f:
                prompt_content = f.read().strip()
        except FileNotFoundError:
            print(f"Error: Prompt file not found at '{args.file}'", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file '{args.file}': {e}", file=sys.stderr)
            sys.exit(1)

    # Run the async core function
    # Note: It's better to wrap the asyncio.run in a try/except block for clean shutdown
    try:
        asyncio.run(run_query(prompt_content))
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
