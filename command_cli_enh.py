import logging
import json
import argparse
import asyncio
import os
import sys
from typing import Dict, Optional, Any
from xml.etree import ElementTree as ET
from xml.dom import minidom


from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult, ElicitRequestParams, RequestContext
from google import genai


# suppress warnting
# Define a filter class to check the message content
class NoNonTextPartWarning(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        # Return False if the message contains the specific warning text
        if "there are non-text parts in the response" in message:
            return False
        return True

# Apply the filter to the logger used by the Gemini SDK (google_genai.types)
logging.getLogger("google_genai.types").addFilter(NoNonTextPartWarning())


def _handle_display_request( msg: str ):
    """
      subroutine to format message request
    """

    print(msg)


def _handle_form_interaction_and_serialization(form_xml_string: str) -> (Dict[str, str], str):
    """
    (The full implementation of the blocking user input and XML serialization logic)
    ...
    """
    # (The function body from the previous accepted answer goes here)

    #  print("_handle " )
    try:
        form_root = ET.fromstring(form_xml_string)
        form_name = form_root.get("formName", "Unnamed Form")

    except ET.ParseError:
        print(f"Error: Could not parse XML file '{args.form}'.")

    #print(" post ET ")

    captured_values = update_form_std(form_root, form_name)
 
    data_xml = convert_dict_to_xml(captured_values)

    return captured_values, data_xml

async def handle_form_elicitation(
    message: str,
    response_type: type,
    params: ElicitRequestParams,
    context: RequestContext
) -> ElicitResult:
    """
    Handles the elicitation request from the 'permission' tool.
    It prompts the user and returns an ElicitResult with the chosen action.
    """
    if message.startswith("Display: "):
        print("Display request" )
        _handle_display_request( message )

        return ElicitResult(action="accept", content={"printed": True} )

    print(f"\n--- form  Request ---")
    #  debug - print(f"Server Message: {message}")
    print("--------------------------")

            
    captured_values, final_xml_string = await asyncio.to_thread(
        _handle_form_interaction_and_serialization, message
    )  

    # print("_acttion")
    # action = user_input.strip().lower()
    action = "accept"

    if action == "accept":
            # The server expects either an empty object or a structured response
            # upon acceptance. Since no specific schema was defined, we accept
            # with an empty content object to satisfy the protocol.
            print("return accept" )
            return ElicitResult(action="accept", content=captured_values)

    elif action == "decline":
            # Decline action is sent with no content.
            return ElicitResult(action="decline")

    elif action == "cancel":
        # Cancel action is sent with no content.
            return ElicitResult(action="cancel")

    else:
            print(f"'{user_input}' is no")


# --- Initialization (Outside main) ---
mcp_client = Client("./mcp_command_server_enh.py",  elicitation_handler=handle_form_elicitation)
# Assuming gemini_client initialization is safe outside the async function
# and that API key is set via environment variable (e.g., GEMINI_API_KEY)
try:
    gemini_client = genai.Client()
except Exception as e:
    # Handle the case where the client cannot be initialized (e.g., no API key)
    print(f"Error initializing Gemini client: {e}", file=sys.stderr)
    sys.exit(1)

def format_prompt_old(field_name, field_type):
    # Calculate the number of '=' signs needed to reach the 30th character
    prompt_text = f"Enter value for {field_name} ({field_type}) "
    num_equals = 30 - len(prompt_text) - len(" => ")
    equals_signs = '=' * num_equals
    return f"{prompt_text}{equals_signs} => "


def format_prompt(field_name, field_type):
    prompt_text = f"Enter value for {field_name} ({field_type})"
    num_equals = 50 - len(prompt_text) - 1  # -1 for the '>'
    equals_signs = '=' * num_equals
    return f"{prompt_text}{equals_signs}>" 

def prompt_for_value(field_name, field_type, current_value):
    """
    Prompts the user for a single value using standard input.
    """
    default = current_value if current_value else ""
    # prompt = f"Enter value for {field_name} ({field_type}) [{default}]: "
    # prompt = f"Enter value for {field_name} ({field_type}) ===> "
    
    #prompt = f"Enter value for {field_name} ({field_type}) ===> {'' :<30}"

    #prompt = f"Enter value for {field_name} ({field_type})".ljust(30) + " ===> "

    prompt = format_prompt( field_name, field_type ) 

 
    user_input = input(prompt).strip()
    
    if not user_input:
        return current_value
    
    if field_type == "date":
        try:
            datetime.strptime(user_input, "%Y-%m-%d")
            return user_input
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
            return prompt_for_value(field_name, field_type, current_value)
            
    return user_input

def update_form_std(form_root, form_name):
    """
    Iterates over an XML form root, prompting for each field
    using standard text input.
    Returns a dictionary of the captured values.
    """
    print("\n" + "-" * (len(form_name) + 4))
    print(f" {form_name} ")
    print("-" * (len(form_name) + 4))
 
    print("=" * 50)
    
    captured_values = {}
    for field in form_root.findall("Field"):
        field_name = field.get("name")
        field_type = field.get("type")
        current_value = field.text if field.text else ""
        
        new_value = prompt_for_value(field_name, field_type, current_value)
        
        field.text = new_value
        captured_values[field_name] = new_value

    print("=" * 50)
        
    print(f"Form '{form_name}' complete.")
    return captured_values

def convert_dict_to_xml(data: dict) -> str:
    """
    Converts the captured_values dictionary into the
    XML string the server tool expects.
    """
    result_root = ET.Element("result")
    for key, value in data.items():
        field_el = ET.SubElement(result_root, key)
        field_el.text = str(value)
    
    return ET.tostring(result_root, encoding="unicode")


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
                model="gemini-2.0-flash",
                contents=prompt_content,  # Use the dynamic prompt
                config=genai.types.GenerateContentConfig(
                    temperature=0,
                    tools=[mcp_client.session],  # Pass the FastMCP client session
                ),
            )
            print("--- Response ---")
            print(response.text)
            print("----------------")

            full_content_parts = response.candidates[0].content.parts

            # uncomment to get full repsonse or view it in json format 
            try:
                response_dict = response.to_dict() 
    
                #pretty_json = json.dumps(response_dict, indent=4)
    
                #print("\n--- FULL RESPONSE OBJECT (Pretty Printed) ---")
                #print(pretty_json)
    
            except AttributeError:
                # Fallback if the object doesn't have a .to_dict() method
                #print("\n--- FULL RESPONSE OBJECT (Direct Print Fallback) ---")
                # This might not be as clean, but shows the structure
                pass
                #print(response)

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


def remove_json_literal_wrapper(text: str) -> str:
    """
    Removes Markdown code fences (e.g., ```json...```) that wrap 
    the intended JSON content in the model's response.
    """
    # 1. Strip leading/trailing whitespace
    stripped_text = text.strip()

    # 2. Check for starting code fence
    if stripped_text.startswith("```"):
        # Find the end of the language identifier (e.g., "```json\n")
        first_newline_index = stripped_text.find('\n')
        
        # Determine the start of the actual JSON content
        if first_newline_index != -1:
            # Start after the first newline following the ```json
            json_start = first_newline_index + 1
        else:
            # Fallback: assume the fence ends right after "```json"
            json_start = stripped_text.find('```') + 3 # Should be at least 3
            # A more robust check might look for "```json" and start after it.
            if stripped_text.lower().startswith("```json"):
                 json_start = 7 # Length of "```json\n"

        # 3. Find the closing code fence (```) from the end
        if stripped_text.endswith("```"):
            json_end = stripped_text.rfind("```")
            
            # 4. Extract the content between the fences
            return stripped_text[json_start:json_end].strip()

    # If no wrapper is found, return the stripped text as is
    return stripped_text

async def run_plan_query(prompt_content: str, plan_file: str):
    """
    Async function to interact with Gemini to generate a JSON plan.
    It adds a system instruction to force JSON output of the planned tool calls.
    """
    if not prompt_content:
        print("Error: Prompt content is empty.", file=sys.stderr)
        return

    # New system instruction to enforce plan generation and JSON format
    system_instruction = (
        "You are an expert planning system. Your task is to generate a detailed, "
        "step-by-step plan in **JSON format only** for the user's request, using the available tools. "
        "The JSON must be an array of objects, where each object has 'step', 'goal', 'tool', 'input', and 'check' keys. "
        "DO NOT execute the tools, and DO NOT include any explanatory text, markdown outside of the JSON block, or preamble."
        "The model is expecting a single JSON array object in the response. **Only output the JSON array **"
    )

    print(f"Generating plan for: '{prompt_content[:80]}...'")

    try:
        async with mcp_client:
            response = await gemini_client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt_content,
                config=genai.types.GenerateContentConfig(
                    temperature=0,
                    tools=[mcp_client.session],
                    system_instruction=system_instruction, # Add the new instruction
                ),
            )
            
            # The response.text should be the pure JSON string
            plan_json_string =  remove_json_literal_wrapper(response.text.strip())
            
            # Sanity check and parse the JSON
            try:
                plan_data = json.loads(plan_json_string)
            except json.JSONDecodeError as e:
                print(f"Error: Could not decode JSON plan from model response: {e}", file=sys.stderr)
                # Print the raw text for debugging
                print("\n--- RAW MODEL RESPONSE (for debugging) ---")
                print(plan_json_string)
                print("------------------------------------------")
                return

            # Write the plan to the specified file
            with open(plan_file, 'w') as f:
                json.dump(plan_data, f, indent=4)
            
            print(f"Plan successfully generated and saved to **{plan_file}**")
            
            # --- ADDED: Token Count Display (similar to run_query) ---
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
    
    # --- ADDED: The new --plan argument ---
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Generate a JSON execution plan (.plan extension) without executing the tools."
    )
    # --- END of ADDED argument ---

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

    # --- ADDED: Logic to handle --plan or normal execution ---
    try:
        if args.plan:
            # Determine the output file name
            if args.prompt:
                # Use a simplified name based on the prompt content
                plan_file_name = "cli_plan.plan"
            elif args.file:
                # Use the prompt filename with a .plan extension
                base_name = os.path.splitext(args.file)[0]
                plan_file_name = f"{base_name}.plan"
                
            asyncio.run(run_plan_query(prompt_content, plan_file_name))
        else:
            # Normal execution
            asyncio.run(run_query(prompt_content))
    # --- END of ADDED logic ---
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
