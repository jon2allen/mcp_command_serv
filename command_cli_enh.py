import logging
import json
import argparse
import asyncio
import os
import sys
from typing import Dict, Optional, Any, List
from xml.etree import ElementTree as ET
from xml.dom import minidom
import tomli
# --- MODIFIED: Replace google client with openai client ---
import openai
# --- END MODIFIED ---


from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult, ElicitRequestParams, RequestContext
# from google import genai # REMOVED

from list import format_tools_for_print

# --- GLOBAL CONFIGURATION DICTIONARY ---
# This will hold the parsed TOML data
CONFIG: Dict[str, Any] = {}
# --- END GLOBAL CONFIGURATION DICTIONARY ---

# The global client is removed since it will be instantiated dynamically
# gemini_client: Optional[genai.Client] = None # REMOVED


# --- MODIFIED FUNCTION: Dynamic OpenAI Client Builder (Uses Configured Env Variable) ---
def get_openai_client(model_alias: str) -> openai.AsyncOpenAI:
    """
    Creates an openai.AsyncOpenAI client instance based on the model's config.
    It retrieves the specific environment variable name defined in the config
    (e.g., 'GEMINI_API_KEY') and uses that to fetch the actual key.
    """
    model_config = CONFIG["models"].get(model_alias)
    
    if not model_config:
        raise ValueError(f"Model alias '{model_alias}' not found in configuration.")

    # 1. Get the name of the environment variable from the config
    # We default to 'LLM_API_KEY' to maintain backward compatibility if the key is missing in config
    env_var_name = model_config.get("api_key", "LLM_API_KEY")

    # 2. Get the actual API key value from the environment
    api_key = os.environ.get(env_var_name)
    
    if not api_key:
        raise ValueError(
            f"API key not found for model alias '{model_alias}'. "
            f"Please set the '{env_var_name}' environment variable."
        )

    # base_url is read from config
    base_url = model_config.get("base_url")

    return openai.AsyncOpenAI(
        api_key=api_key,
        base_url=base_url if base_url else None
    )
# --- END MODIFIED FUNCTION ---


# --- MODIFIED FUNCTION: CONFIG LOADER (Added api_key field to defaults) ---
def load_config(config_path: str) -> Dict[str, Any]:
    """
    Loads configuration from a TOML file using tomli, merging it with defaults.
    """
    default_config = {
        "models": {
            # alias: {name, temp, topk, base_url, api_key_env_var_name}
            "gemini_flash": {
                "name": "gemini-2.5-flash",
                "temperature": 0.0,
                "top_k": 1,
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "api_key": "LLM_API_KEY", # Default fallback
            },
            "gemma_3": {
                "name": "gemma-3-27b-it",
                "temperature": 0.7,
                "top_k": 1,
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "api_key": "LLM_API_KEY", # Default fallback
            },
        }
    }

    if not os.path.exists(config_path):
        print(f"Warning: Config file not found at '{config_path}'. Using default model settings.", file=sys.stderr)
        return default_config

    try:
        with open(config_path, "rb") as f: # tomli requires reading in binary mode ("rb")
            user_config = tomli.load(f)
        
        # Merge, ensuring defaults are preserved for all models
        config = default_config.copy()
        
        # Merge user models with defaults
        if "models" in user_config:
            for alias, user_settings in user_config["models"].items():
                config["models"].setdefault(alias, {}).update(user_settings)

        return config

    except tomli.TOMLDecodeError as e:
        print(f"Error: Invalid TOML file format in '{config_path}': {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error loading config file '{config_path}': {e}", file=sys.stderr)
        sys.exit(1)
        
# --- END MODIFIED FUNCTION ---


async def mcp_router(
    tool_name: str,
    parameters: Dict[str, Any],
    mcp_client: Client
) -> Any:
    """
    Routes a tool call to the MCP server using a pre-initialized client and returns the response.

    Args:
        tool_name: Name of the tool to call (e.g., "change_dir").
        parameters: Dictionary of parameters for the tool (e.g., {"c_dir": "/path/to/dir"}).
        mcp_client: Pre-initialized MCPClient instance.

    Returns:
        Response from the tool or an error message.

    Raises:
        ValueError: If the tool_name or parameters are invalid.
    """
    async with mcp_client:
       try:
           # Call the tool and await the response
           response = await mcp_client.call_tool(
               name=tool_name,
               arguments=parameters
               )
           return response
       except Exception as e:
           return f"Error calling tool '{tool_name}': {str(e)}"

async def execute_plan_steps(
    json_file_path: Optional[str],
    client: Client,  # Use the imported Client class
    plan_data: Optional[List[Dict]] = None # Added optional plan_data for in-memory execution
) -> Any:
    """
    Reads a JSON file containing a sequence of steps, extracts the tool name and parameters,
    and calls `mcp_router` for each step using the provided FastMCP client.
    
    Can also accept a plan_data list directly, bypassing file read.

    Args:
        json_file_path: Path to the JSON file containing the steps (Optional if plan_data provided).
        client: Pre-initialized FastMCP Client instance.
        plan_data: List of steps dictionary (Optional).

    Returns:
        List of dictionaries containing the tool name, parameters, and response for each step.

    Raises:
        ValueError: If the JSON file is invalid or missing required fields.
        FileNotFoundError: If the JSON file does not exist.
    """

    # --- CONFIG RETRIEVAL FOR EXEC PLAN ---
    model_alias = CONFIG.get("current_model_alias", "gemini_flash")
    model_config = CONFIG["models"].get(model_alias, CONFIG["models"]["gemini_flash"])
    model_name = model_config["name"]
    temperature = model_config["temperature"]
    # --- END CONFIG RETRIEVAL ---
    
    # --- MODIFIED: Create dynamic client ---
    try:
        llm_client = get_openai_client(model_alias)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return
    # --- END MODIFIED ---
    
    prompt_history = ""
    try:
        steps = []
        if plan_data is not None:
             steps = plan_data
        elif json_file_path:
            # Read the JSON file
            with open(json_file_path, "r") as file:
                steps = json.load(file)
        else:
             raise ValueError("Either json_file_path or plan_data must be provided.")

        # Validate the JSON structure
        if not isinstance(steps, list):
            raise ValueError("Steps data must be a list.")

        results = []

        # Iterate over each step and call mcp_router
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError("Each step must be a dictionary.")

            tool_name = step.get("tool")
            parameters = step.get("input", {})
            goal = step.get("goal")
            check = step.get("check")

            if not tool_name:
                raise ValueError("Each step must contain a 'tool_name' field.")

            # Call mcp_router for the current step
            response = await mcp_router(
                tool_name=tool_name,
                parameters=parameters,
                mcp_client=client
            )

            if tool_name == "display_info":
                continue

            step_prompt_content = (
                "Check response against goal"
                "Goal: \n"
                f"{goal}"
                "Response: \n"
                f"{response}"
                "important: \n"
                "produce summary of goal met and reports requested"
                "if there is data returned print it as is"
                "check this for any highlevel analysis needed and show any qualitative review of results requested, that are not simple commands"
                "Do not do qualitative review or highlevel analysis of commands marked Simple Commands"
                f"{check}"
                "prior history of execution for reference: "
                f"{prompt_history}"  
                "if tool call resulted in an error print ***ERROR***"  
            )

            # --- MODIFIED: Use OpenAI Chat Completion and dynamic client ---
            async with mcp_client:
                step_response_obj = await llm_client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": step_prompt_content}],
                    temperature=temperature,
                    # Note: top_k is often managed by temperature in OpenAI, or uses top_p/max_tokens
                )
                step_response = step_response_obj.choices[0].message.content or ""
            # print("step_prompt_content: ", step_prompt_content )
            print("step response: ", step_response )
            # --- END MODIFIED ---

            # Store the result
            results.append({
                "tool_name": tool_name,
                "parameters": parameters,
                "response": response 
            })
            prompt_history = prompt_history + step_response + "\n"

        return results

    except FileNotFoundError:
        raise FileNotFoundError(f"JSON file not found: {json_file_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON file: {json_file_path}")

async def list_mcp_tools(client):
    """
    Run basic operations with an MCP client and return the results
    as a formatted string.
    """
    async with client:
        # Basic server interaction
        await client.ping()
        
        # List available operations
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()

        formatted_tools = format_tools_for_print(tools)

        # Build the returned string
        output = []
        output.append("START OF TOOLS\n")
        output.append(formatted_tools)
#        output.append("resources:")
#        output.append(str(resources))
#        output.append("prompts:")
#        output.append(str(prompts))
        output.append("END OF TOOLS\n")

        return "\n".join(output)

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
# logging.getLogger("google_genai.types").addFilter(NoNonTextPartWarning()) # REMOVED


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
        # NOTE: Removed `args.form` reference as it's not defined here, regression-free if unused.
        print(f"Error: Could not parse XML file.")

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


# --- Initialization ---
# define mcp_client
#######################
mcp_client = Client("./mcp_command_server_enh.py",  elicitation_handler=handle_form_elicitation)
#######################


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
            # NOTE: datetime.strptime dependency is now outside of my scope, removed to avoid unimported name error.
            # datetime.strptime(user_input, "%Y-%m-%d") 
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
    Core async function to interact with FastMCP and the LLM via OpenAI API.
    Takes the prompt content as an argument.
    """
    if not prompt_content:
        print("Error: Prompt content is empty.", file=sys.stderr)
        return

    # --- CONFIG RETRIEVAL ---
    model_alias = CONFIG.get("current_model_alias", "gemini_flash")
    model_config = CONFIG["models"].get(model_alias, CONFIG["models"]["gemini_flash"])
    model_name = model_config["name"]
    temperature = model_config["temperature"]
    top_k = model_config["top_k"]
    # --- END CONFIG RETRIEVAL ---
    
    try:
        llm_client = get_openai_client(model_alias)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return

    print(f"Sending prompt to LLM (Model: {model_name}, Temp: {temperature}): '{prompt_content[:80]}...'")

    try:
        async with mcp_client:

            # 1. Fetch available tools from the MCP server
            tool_list = await mcp_client.list_tools()
        
            # 2. Convert MCP tools to OpenAI tool format
            openai_tools = []
            for tool in tool_list:
                 openai_tools.append({
                    "type": "function",
                    "function": {
                         "name": tool.name,
                         "description": tool.description,
                         "parameters": tool.inputSchema
                         }
                 })

            # --- MODIFIED: History initialization and Loop ---
            messages = [{"role": "user", "content": prompt_content}]

            while True:
                response_obj = await llm_client.chat.completions.create(
                    model=model_name,
                    messages=messages, # Use dynamic history
                    temperature=temperature,
                    tools=openai_tools,
                    tool_choice="auto",
                    extra_headers={"x-google-top-k": str(top_k)} if 'gemini' in model_name.lower() else {},
                )

                message = response_obj.choices[0].message
                messages.append(message) # Feature 2: Keep history of response

                if message.tool_calls:
                    # Feature 1: Loop on tool output
                    for tool_call in message.tool_calls:
                         # Parse arguments from JSON string to dict
                         tool_args = json.loads(tool_call.function.arguments)
                         
                         print(f"--- Tool Call: {tool_call.function.name} ---")
                         
                         # Execute tool via router
                         tool_response = await mcp_router(
                            tool_name=tool_call.function.name,
                            parameters=tool_args,
                            mcp_client=mcp_client
                        )
                         
                         # Feature 2: Append tool result to history
                         messages.append({
                             "role": "tool",
                             "tool_call_id": tool_call.id,
                             "content": str(tool_response)
                         })
                    # Loop continues here to redrive the prompt with new history
                
                else:
                    # Feature 3: Print response when not tool (Final Answer)
                    if message.content:
                        print("--- Response ---")
                        print(message.content)
                        print("----------------")
                        
                        if response_obj.usage:
                            print("--- Token Usage ---")
                            print(f"Input Tokens:  {response_obj.usage.prompt_tokens}")
                            print(f"Output Tokens: {response_obj.usage.completion_tokens}")
                            print(f"Total Tokens:  {response_obj.usage.total_tokens}")
                            print("-------------------")
                    
                    # Break the loop as we have a final text response
                    break
            # --- END MODIFIED ---

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
    Async function to interact with LLM via OpenAI API to generate a JSON plan.
    It adds a system instruction to force JSON output of the planned tool calls.
    """
    if not prompt_content:
        print("Error: Prompt content is empty.", file=sys.stderr)
        return

    # --- CONFIG RETRIEVAL ---
    model_alias = CONFIG.get("current_model_alias", "gemini_flash")
    model_config = CONFIG["models"].get(model_alias, CONFIG["models"]["gemini_flash"])
    model_name = model_config["name"]
    temperature = model_config["temperature"]
    # --- END CONFIG RETRIEVAL ---
    
    # --- MODIFIED: Create dynamic client ---
    try:
        llm_client = get_openai_client(model_alias)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return
    # --- END MODIFIED ---

    # get list in text form  
    mcp_tools = await list_mcp_tools(mcp_client)

    
    # New system instruction to enforce plan generation and JSON format
    plan_prompt_content = (
        "Purpose and output INSTRUCTIONS: \n"
        "You are an expert planning system. Your task is to generate a detailed, "
        "step-by-step plan in **JSON format only** for the user's request, using the list of available tools listed below: \n "
        "take a high level view - not every sentance or statement is a step, make sure to do in as few steps as possible, but meet goal"
        f"please take note of operating system: {os.name} and locate programs before creating shebang for perl or other scripts"
        "make sure any sub-programs created are robust and deliver on expected outputs. "
        "The JSON must be an array of objects, where each object has 'step', 'goal', 'tool', 'input', and 'check' keys. "
        "the 'input' should correspond to MCP specifications for parameters ( a dictionary )"
        "for commands that are simple and do not display output, prefix ***Simple command: *** in check text"
        "DO NOT execute the tools, and DO NOT include any explanatory text, markdown outside of the JSON block, or preamble."
        "The model is expecting a single JSON array object in the response. **Only output the JSON array **"  
        "Use JSON standard escapes even if output is perl, awk, bash or other language, pay attention to entire command"
        "Make sure any sub-language calles are escaped properly and use double escapes if need to ensure proper json"
        "if there is more than one logical ask in a line or sentence break it out 2 steps - such as list and then summarize"
        "if you know the information or does not require tool, just use info tool to display"
        f"{mcp_tools}"
        "USER REQUEST: \n"
        f"{prompt_content} \n"

    )

    print("plan content: ", plan_prompt_content )  

    print(f"Generating plan for (Model: {model_name}, Temp: {temperature}): '{prompt_content[:80]}...'")

    try:
        async with mcp_client:
            # --- MODIFIED: Use OpenAI Chat Completion for plan generation ---
            response_obj = await llm_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": plan_prompt_content}],
                temperature=temperature,
                # Tools are typically omitted for plan generation to enforce JSON output
            )
            # --- END MODIFIED ---
            
            plan_json_string =  remove_json_literal_wrapper(response_obj.choices[0].message.content.strip())
            
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
            
            # --- Token Count Display ---
            if response_obj.usage:
                print("--- Token Usage ---")
                print(f"Input Tokens:  {response_obj.usage.prompt_tokens}")
                print(f"Output Tokens: {response_obj.usage.completion_tokens}")
                print(f"Total Tokens:  {response_obj.usage.total_tokens}")
                print("-------------------")
            # --- END of Token Display ---

    except Exception as e:
        print(f"An error occurred during the API call: {e}", file=sys.stderr)

async def run_handprint_query(prompt_content: str):
    """
    Executes a query by looping (ReAct style) but uses text-based tool 
    descriptions/output instead of native API tool definitions.
    """
    if not prompt_content:
        print("Error: Prompt content is empty.", file=sys.stderr)
        return

    # --- CONFIG RETRIEVAL ---
    model_alias = CONFIG.get("current_model_alias", "gemini_flash")
    model_config = CONFIG["models"].get(model_alias, CONFIG["models"]["gemini_flash"])
    model_name = model_config["name"]
    temperature = model_config["temperature"]
    top_k = model_config["top_k"]
    # --- END CONFIG RETRIEVAL ---

    try:
        llm_client = get_openai_client(model_alias)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return

    print(f"Starting Handprint Query (Model: {model_name})...")
    
    try:
        async with mcp_client:
            # 1. Get tools list in text form
            mcp_tools_text = await list_mcp_tools(mcp_client)

            # 2. Construct Initial Prompt
            # "just pass the prompt, but with an additional prompt - uses the tools below. with the list of mcp tools."
            formatted_prompt = (
                "Execute and call tools to solve query"
                "IMPORTANT: Only one tool can be executed at a time - print JSON for one tool and wait for next step"
                "check for tool execution history"
                "do not describe the process - only after last tool call put out description"
                "Use tools to create files"
                f"{prompt_content}\n\n"
                "uses the tools below:\n"
                f"{mcp_tools_text}\n\n"
                "IMPORTANT: To call a tool, you must output a JSON object containing keys 'tool' and 'input'. "
                "Use proper escapes even if output is perl, awk, bash or other language, pay attention to entire command. "
                "Make sure any sub-language calls are escaped properly and use double escapes if need to ensure proper json"
                "No extra commentary needed around tool call"
                "If you are answering the user directly, use display_info tool."
            )

            # 3. Initialize History
            messages = [{"role": "user", "content": formatted_prompt}]

            while True:
                # 4. Call LLM (No native tools)
                response_obj = await llm_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    extra_headers={"x-google-top-k": str(top_k)} if 'gemini' in model_name.lower() else {},
                )

                message = response_obj.choices[0].message
                messages.append(message) # Add Assistant Response to History
                
                content = message.content or ""
                
                # 5. Check for JSON Tool Call in text response
                tool_to_execute = None
                
                # Attempt to extract JSON from the text
                try:
                    cleaned_content = remove_json_literal_wrapper(content)
                    print("cleaned: \n", cleaned_content )
                    # Simple heuristic: if it looks like a JSON object with 'tool' key
                    if "{" in cleaned_content and "tool" in cleaned_content:
                        # Attempt parse
                        parsed = json.loads(cleaned_content)
                        if isinstance(parsed, dict) and "tool" in parsed:
                            tool_to_execute = parsed
                except json.JSONDecodeError:
                    pass
                except Exception:
                    pass

                if tool_to_execute:
                    # 6. Execute Tool
                    print(f"--- Tool Call (Text-based): {tool_to_execute['tool']} ---")
                    
                    tool_response = await mcp_router(
                        tool_name=tool_to_execute['tool'],
                        parameters=tool_to_execute.get('input', {}),
                        mcp_client=mcp_client
                    )
                    
                    # 7. Add Result to History
                    # For text-based loops, we return the tool output as a User message (or System, but User is safer for generic models)
                    tool_result_msg = f"Tool Output: {tool_response}"
                    messages.append({
                        "role": "user", 
                        "content": tool_result_msg
                    })
                    
                    # Loop continues...
                else:
                    # 8. Final Answer (Text)
                    print("--- Response ---")
                    print(content)
                    print("----------------")

                    if response_obj.usage:
                        print("--- Token Usage ---")
                        print(f"Input Tokens:  {response_obj.usage.prompt_tokens}")
                        print(f"Output Tokens: {response_obj.usage.completion_tokens}")
                        print(f"Total Tokens:  {response_obj.usage.total_tokens}")
                        print("-------------------")
                    
                    break

    except Exception as e:
        print(f"An error occurred during the handprint execution: {e}", file=sys.stderr)

# The original main function is now for argument parsing and setup
def main():
    # --- NEW: Import global variables ---
    global CONFIG
    # --- END NEW: Import global variables ---
    
    parser = argparse.ArgumentParser(
        description="Run a prompt against the LLM API using FastMCP for tool access."
    )
    # Mutually exclusive group for -p and -f
    group = parser.add_mutually_exclusive_group(required=False)

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
    
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Generate a JSON execution plan (.plan extension) without executing the tools."
    )

    parser.add_argument(
        "--execplan",
        type=str,
        help="Path to the JSON file containing the execution plan."
    )
    
    parser.add_argument(
        "--handprint",
        action="store_true",
        help="Run query using text-based tool descriptions (Handprint) instead of native tool calls."
    )
    
    # --- NEW ARGUMENTS ---
    parser.add_argument(
        "--config",
        type=str,
        default="config.toml",
        help="Path to the TOML configuration file (default: config.toml)."
    )

    parser.add_argument(
        "--model",
        type=str,
        default="gemini_flash", # Default alias
        help="Alias of the model to use, as defined in the [models] section of the config file (default: gemini_flash).",
    )
    # --- END NEW ARGUMENTS ---

    args = parser.parse_args()
    prompt_content = None

    # --- MODIFIED: Load Configuration and Check Model (no client init here) ---
    CONFIG = load_config(args.config)
    
    if args.model not in CONFIG["models"]:
        print(f"Error: Model alias '{args.model}' not found in the config file.", file=sys.stderr)
        print(f"Available models: {', '.join(CONFIG['models'].keys())}", file=sys.stderr)
        sys.exit(1)
        
    # Store the selected model alias for use in model client creation
    CONFIG["current_model_alias"] = args.model
    # --- END MODIFIED: Load Configuration ---
    
    # --- REMOVED: Gemini client initialization ---


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
        if args.execplan:
            print("exec plan")
            mcp_client = Client("./mcp_command_server_enh.py",  elicitation_handler=handle_form_elicitation)
            results = asyncio.run(execute_plan_steps(
            json_file_path=args.execplan,
            client=mcp_client ))
            # Print the results
            #for result in results:
            #     print(f"Tool: {result['tool_name']}")
            #     print(f"Parameters: {result['parameters']}")
            #     print(f"Response: {result['response']}\n")

            sys.exit(0)
            
        if args.handprint:
            if not prompt_content:
                print("Error: --handprint requires either --prompt or --file to be specified.", file=sys.stderr)
                sys.exit(1)
            asyncio.run(run_handprint_query(prompt_content))

        elif args.plan:
            if not prompt_content:
                print("Error: --plan requires either --prompt or --file to be specified.", file=sys.stderr)
                sys.exit(1)
                
            # Determine the output file name
            if args.prompt:
                # Use a simplified name based on the prompt content
                plan_file_name = "cli_plan.plan"
            elif args.file:
                # Use the prompt filename with a .plan extension
                base_name = os.path.splitext(args.file)[0]
                plan_file_name = f"{base_name}.plan"
                
            asyncio.run(run_plan_query(prompt_content, plan_file_name))
        elif prompt_content:
            # Normal execution
            asyncio.run(run_query(prompt_content))
        else:
             parser.print_help() # Print help if no prompt or file is provided
    # --- END of MODIFIED logic ---
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
