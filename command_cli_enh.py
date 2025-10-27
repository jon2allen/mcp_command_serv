import argparse
import asyncio
import os
import sys
from typing import Dict
from xml.etree import ElementTree as ET
from xml.dom import minidom


from fastmcp import Client 
from fastmcp.client.elicitation import ElicitResult, ElicitRequestParams, RequestContext
from google import genai

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
