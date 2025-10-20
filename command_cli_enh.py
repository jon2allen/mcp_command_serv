#!/usr/local/bin/python3
import argparse
import asyncio
import os
import sys

from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult, ElicitRequestParams, RequestContext
from google import genai

async def handle_permission_elicitation(
    message: str,
    response_type: type,
    params: ElicitRequestParams,
    context: RequestContext
) -> ElicitResult:
    """
    Handles the elicitation request from the 'permission' tool.
    It prompts the user and returns an ElicitResult with the chosen action.
    """
   
    print(f"\n--- Permission Request ---")
    print(f"Server Message: {message}")
    print("--------------------------")
   
    # Use standard input for a CLI environment
    while True:
        # Use a non-blocking way to get input in an async function (simulated here)
        user_input = await asyncio.to_thread(
            input,
            "Enter 'accept', 'decline', or 'cancel': "
        )

        action = user_input.strip().lower()

        if action == "accept":
            # The server expects either an empty object or a structured response
            # upon acceptance. Since no specific schema was defined, we accept
            # with an empty content object to satisfy the protocol.
            return ElicitResult(action="accept", content={})

        elif action == "decline":
            # Decline action is sent with no content.
            return ElicitResult(action="decline")

        elif action == "cancel":
            # Cancel action is sent with no content.
            return ElicitResult(action="cancel")

        else:
            print(f"'{user_input}' is not a valid choice. Try again.")


# --- Initialization (Outside main) ---
mcp_client = Client("./mcp_command_server_enh.py", elicitation_handler=handle_permission_elicitation)
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
            
            # --- ADDED: Token Count Display ---
            # Access the usage metadata from the response to get token counts
            if response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count
                output_tokens = response.usage_metadata.candidates_token_count
                total_tokens = response.usage_metadata.total_token_count
                
                print("--- Token Usage ---")
                print(f"Input Tokens:  {input_tokens}")
                print(f"Output Tokens: {output_tokens}")
                print(f"Total Tokens:  {total_tokens}")
                print("-------------------")
            # --- END of ADDED section ---

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
