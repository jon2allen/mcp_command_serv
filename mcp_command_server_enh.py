import os
import platform
import sys
import json
import base64
import asyncio
import logging
import argparse
import subprocess
from typing import Dict, Any, List, Tuple,Literal,  Optional
from typing_extensions import TypedDict
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET
from xml.dom import minidom
import tomli # Import tomli to load the config
import re    # Import re for robust command checking

# local imports
from pexpect_auto import PexpectAutomator
from fastmcp import FastMCP,Context
from fastmcp.server.context import AcceptedElicitation

from fastmcp.server.elicitation import (
    AcceptedElicitation, 
    DeclinedElicitation, 
    CancelledElicitation,
)

# --- Logging setup (from template) ---
LOG_FILE = "mcp_command_server.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr), # Log to stderr for visibility
        logging.FileHandler(LOG_FILE),
    ],
)
logger = logging.getLogger("mcp_command_server")

# --- Configuration Loading ---
CONFIG_FILE = "config.toml"
SERVER_CONFIG = {}
DEFAULT_CONFIG = {
    "command_blocking": {
        "prohibited_commands": ['rm ', 'mv ', 'sudo ', 'su '],
        "override": False
    },
    "restricted_files": [
        "mcp_command_server_enh.py",
        "mcp_command_server.log",
        "pexpect_auto.py",
        "config.toml"
    ]
}

def load_config():
    """Load configuration from the TOML file."""
    global SERVER_CONFIG
    try:
        with open(CONFIG_FILE, "rb") as f:
            SERVER_CONFIG = tomli.load(f)
        logger.info("Configuration loaded successfully from %s", CONFIG_FILE)
    except FileNotFoundError:
        logger.error("Configuration file '%s' not found. Using safe defaults.", CONFIG_FILE)
        SERVER_CONFIG = DEFAULT_CONFIG
    except Exception as e:
        logger.error("Failed to parse configuration file '%s': %s. Using safe defaults.", CONFIG_FILE, e)
        SERVER_CONFIG = DEFAULT_CONFIG

# --- Command Execution Logic (from mcp-server-commands) ---
class ExecResult:
    """A simple data class to hold the result of a command execution."""
    def __init__(self, stdout: str, stderr: str, code: Optional[int] = None):
        self.stdout = stdout
        self.stderr = stderr
        self.code = code

# --- FUNCTION FOR COMMAND BLOCKING ---
def is_command_blocked_old(command: str) -> bool:
    """Checks if a command contains prohibited substrings loaded from config."""
    prohibited_cmds = SERVER_CONFIG.get("command_blocking", {}).get("prohibited_commands", [])

    # 1. Prepare list for robust checking (e.g., just 'rm', 'mv')
    cleaned_prohibited = [cmd.strip() for cmd in prohibited_cmds]

    if not cleaned_prohibited:
        return False

    # Pattern to catch command followed by space or dash (e.g., 'rm -rf')
    pattern = r'\b(' + '|'.join(re.escape(cmd) for cmd in cleaned_prohibited) + r')[\s-]'

    # Check command parts (for 'command1 && command2')
    command_parts = re.split(r'[;&|]+', command)
    command_lower = command.lower()
    for part in command_parts:
        # Check against the robust regex pattern
        if re.search(pattern, part.strip().lower()):
            return True

    # 2. Check the original strict match
    for block in prohibited_cmds:
        if block in command_lower:
            return True

    return False

import re

def is_command_blocked(command: str) -> bool:
    """Checks if a command contains prohibited whole words loaded from config."""
    prohibited_cmds = SERVER_CONFIG.get("command_blocking", {}).get("prohibited_commands", [])
    if not prohibited_cmds:
        return False

    # Prepare list for robust checking (e.g., just 'rm', 'mv')
    cleaned_prohibited = [cmd.strip() for cmd in prohibited_cmds]
    if not cleaned_prohibited:
        return False

    # Pattern to catch whole words only, followed by space or dash (e.g., 'rm -rf')
    pattern = r'\b(' + '|'.join(re.escape(cmd) for cmd in cleaned_prohibited) + r')\b[\s-]'

    # Check command parts (for 'command1 && command2')
    command_parts = re.split(r'[;&|]+', command)
    command_lower = command.lower()

    for part in command_parts:
        # Check against the robust regex pattern
        if re.search(pattern, part.strip().lower()):
            return True

    # 2. Check the original strict match (whole words only)
    for block in prohibited_cmds:
        if re.search(rf'\b{re.escape(block)}\b', command_lower):
            return True

    return False


def is_restricted_file_access(command: str) -> bool:
    """Checks if a command involves accessing restricted files."""
    restricted_files = SERVER_CONFIG.get("restricted_files", [])
    for restricted_file in restricted_files:
        # logger.info("restricted1 file %s", restricted_file )
        if command.find(restricted_file) > -1:
            return True
    return False

def check_override() -> bool:
    """Checks if the command execution override is enabled in the config."""
    # Returns False if 'command_blocking' or 'override' key is missing, maintaining default security.
    return SERVER_CONFIG.get("command_blocking", {}).get("override", False)

# ----------------------------------------------------
async def fish_workaround(interpreter: str, stdin: str, options: Dict[str, Any]) -> ExecResult:
    """A specific workaround for piping stdin to the fish shell."""
    base64_stdin = base64.b64encode(stdin.encode('utf-8')).decode('utf-8')
    command = f'{interpreter} -c "echo {base64_stdin} | base64 -d | fish"'
    logger.info("Using fish workaround command: %s", interpreter)

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **options
    )
    stdout, stderr = await proc.communicate()
    return ExecResult(stdout.decode('utf-8'), stderr.decode('utf-8'), proc.returncode)

async def exec_command(command: str, stdin: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> ExecResult:
    """Executes a shell command asynchronously, capturing its output."""
    options = options or {}
    try:
        # Apply the fish shell workaround if needed
        if command.split(" ")[0] == "fish" and stdin:
            return await fish_workaround(command, stdin, options)
        proc = await asyncio.create_subprocess_shell(
            command,
            stdin=asyncio.subprocess.PIPE if stdin else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **options
        )
        stdout_bytes, stderr_bytes = await proc.communicate(
            input=stdin.encode('utf-8') if stdin else None
        )
        return ExecResult(stdout_bytes.decode('utf-8'), stderr_bytes.decode('utf-8'), proc.returncode)
    except FileNotFoundError:
        return ExecResult("", f"Command not found: {command}\n", 127)
    except Exception as e:
        logger.error("exec_command failed unexpectedly for command '%s': %s", command, e)
        return ExecResult("", str(e), 1)

def format_result_messages(result: ExecResult) -> List[Dict[str, Any]]:
    """Formats the execution result into a list of MCP content dictionaries."""
    messages = []
    if result.code is not None:
        messages.append({"type": "text", "text": str(result.code), "name": "EXIT_CODE"})
    if result.stdout:
        messages.append({"type": "text", "text": result.stdout, "name": "STDOUT"})
    if result.stderr:
        messages.append({"type": "text", "text": result.stderr, "name": "STDERR"})
    return messages

# --- MCP Server Initialization ---
mcp = FastMCP("mcp-server-commands")

@mcp.resource("resource://system_info")
def system_info() -> Dict[str, str]:
    """Provides basic information about the host operating system."""
    logger.info("system_info() called")
    return {
        "os_name": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine()
    }

@mcp.tool
async def run_command(
    command: str,
    workdir: Optional[str] = None,
    stdin: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run a shell command on the local machine and get the output.

    Args:
        command: The shell command to execute.
        workdir: The working directory for the command. If None, uses the current directory.
        stdin: Optional stdin to pipe into the command.

    Returns:
        A dictionary containing the command's output, exit code, and error status.
    """
    logger.info("Received run_command request: command='%s', workdir='%s'", command, workdir)

    blocked_feedback = "This server is not authorized to run these commands"
    restricted_feedback = "This server is not authorized to access restricted files"

    # --- RESTRICTION BYPASS LOGIC ---
    if check_override():
        logger.warning("Command restrictions bypassed via config override.")
    elif is_command_blocked(command):
        logger.warning("Blocked command denied: '%s'", command)
        return {
            "content": [
                {"type": "text", "text": "1", "name": "EXIT_CODE"},
                {"type": "text", "text": blocked_feedback + "\n", "name": "STDERR"},
            ],
            "is_error": True
        }
    elif is_restricted_file_access(command):
        logger.warning("Restricted file access denied: '%s'", command)
        return {
            "content": [
                {"type": "text", "text": "1", "name": "EXIT_CODE"},
                {"type": "text", "text": restricted_feedback + "\n", "name": "STDERR"},
            ],
            "is_error": True
        }
    # --------------------------------
    options = {"cwd": workdir} if workdir else {}
    exec_result = await exec_command(command, stdin, options)

    is_error = exec_result.code != 0
    if is_error:
        logger.warning("Command '%s' failed with exit code %d", command, exec_result.code)

    return {
        "content": format_result_messages(exec_result),
        "is_error": is_error
    }


@mcp.tool
async def get_current_dir() -> str:
    """
    Get the current working directory

    returns str ->  directory ( ex "/home/user1"
    """
    current_dir = os.getcwd()
    logger.info("Received get_current_dir requst:  current dir is '%s'", current_dir )
    return current_dir

@mcp.tool
async def change_dir(c_dir: str) -> str:
    """Change the directory to specified string relative and absolute paths are supported

    If error - will return string "error: invalid directory"
    """
    logger.info("Received change_dir request: '%s'", c_dir)

    # Expand $HOME to the full home directory path
    if "$HOME" in c_dir:
        home_dir = os.environ.get('HOME', '')
        expanded_dir = c_dir.replace("$HOME", home_dir)
    else:
        expanded_dir = os.path.expanduser(c_dir)

    try:
        # Attempt to change the directory
        os.chdir(expanded_dir)
        return expanded_dir
    except Exception as e:
        # Log the error and return an error message
        logger.info("invalid dir: '%s'", expanded_dir)
        return "error: invalid directory"

@mcp.tool()
def run_expect_script(
    program: str,
    actions: list[dict[str, str]]
) -> str:
    """
    Run a program with a sequence of expect/send actions for programs that are interactive.
    Programs that require inputs.

    important:  do not send carriage return or line feed with text on send.

    Args:
        program: The command to run (e.g. "python3 myscript.py").  Can be any command
        actions: A list of dicts, e.g. [{"action": "expect", "text": "foo"}, {"action":"send","text":"bar"}]

    Returns:
        The output from the interaction.
    """

    logger.info("running pexpect for pgm : '%s'", program )
    logger.info("Actions: %s", json.dumps(actions, indent=2))
    # Translate from dicts to your internal format
    tuple_actions = []
    for act_d in actions:
        act = act_d.get("action")
        text = act_d.get("text")
        # maybe validate
        if act not in ("expect", "send"):
            raise ValueError(f"Invalid action {act}")
        tuple_actions.append((act, text))
    autom = PexpectAutomator(program, tuple_actions)
    output = autom.run()
    if output is None:
        # You could choose to raise, or return error info
        raise RuntimeError("PexpectAutomator failed")
    # Optionally log or return structured output
    return output

class FormField(TypedDict):
    """Defines the structure for a single field in the form."""
    name: str
    type: Literal["string", "date", "float", "decimal", "integer"]


@mcp.tool()
def create_form(
    form_name: str,
    #fields: List[Tuple[str, Literal["string", "date", "float", "decimal", "integer"]]]
    #fields: List[FormField]
    fields: list[dict[Literal["name", "type"], str]] 
) -> str:
    """
    Creates an XML form file based on the provided schema.

    schema definition:

<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Form">
    <xs:complexType>
      <xs:sequence>
        <!-- Generic Field element with name and type attributes -->
        <xs:element name="Field" minOccurs="0" maxOccurs="unbounded">
          <xs:complexType>
            <xs:simpleContent>
              <xs:extension base="xs:string">
                <xs:attribute name="name" type="xs:string" use="required"/>
                <xs:attribute name="type" use="required">
                  <xs:simpleType>
                    <xs:restriction base="xs:string">
                      <xs:enumeration value="string"/>
                      <xs:enumeration value="date"/>
                      <xs:enumeration value="float"/>
                      <xs:enumeration value="decimal"/>
                      <xs:enumeration value="integer"/>
                    </xs:restriction>
                  </xs:simpleType>
                </xs:attribute>
              </xs:extension>
            </xs:simpleContent>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
      <!-- Add a 'formName' attribute to the Form element -->
      <xs:attribute name="formName" type="xs:string" use="required"/>
    </xs:complexType>
  </xs:element>
</xs:schema>


    Args:
        form_name: Name of the form (without extension).
        fields: List of tuples, each containing (field_name, field_type).

    Returns:
        str: "Form <form_name> created" or "Error: form not created".
    """
    # Validate field types

    valid_types = {"string", "date", "float", "decimal", "integer"}
    for field_data in fields:
        name = field_data["name"]
        type_ = field_data["type"]
        
        if type_ not in valid_types:
            # 1. Log: Invalid Field Type
            logger.error(f"Validation failed for form '{form_name}'. Invalid field type: '{type_}' for field '{name}'.")
            return "Error: form not created"

    # 2. Log: Form Creation Start
    logger.info(f"Starting creation of form: '{form_name}' with {len(fields)} fields.")
    
    # Create the root element
    form = ET.Element("Form", {"formName": form_name})

    # Add fields
    for field_data in fields:
        name = field_data["name"]
        type_ = field_data["type"]
        
        field = ET.SubElement(form, "Field", {"name": name, "type": type_})
        
        # 3. Log: Successful Field Addition
        logger.debug(f"Added field '{name}' (Type: {type_}) to form '{form_name}'.")

    # Create the XML tree (This step doesn't usually require logging)
    tree = ET.ElementTree(form)

    # Convert to a pretty-printed XML string
    xml_str = ET.tostring(form, encoding="utf-8")
    xml_pretty = minidom.parseString(xml_str).toprettyxml(indent="  ")

    # Ensure the forms directory exists
    # os.makedirs will log an INFO message if a new directory is created
    try:
        os.makedirs("forms", exist_ok=True)
        # 4. Log: Successful Directory Creation (only logs if it was necessary)
        logger.info("Checked/created 'forms' output directory.")
    except Exception as e:
         # Optional: Log if os.makedirs fails for some permission reason
        logger.error(f"Failed to ensure 'forms' directory exists: {e}")
        return "Error: form not created"


    # Write to file
    filename = f"forms/{form_name}_form.xml"
    try:
        with open(filename, "w") as f:
            f.write(xml_pretty)
        
        # 5. Log: Successful File Write
        logger.info(f"Successfully saved XML form to file: {filename}")
        return f"Form {form_name} created"
        
    except Exception as e:
        # 6. Log: File Writing Error
        logger.error(f"Failed to write form '{form_name}' to file '{filename}'. Error: {e}")
        return "Error: form not created"

@mcp.tool() 
def list_forms() -> List[str]:
    """
    Lists the names of all forms found in the 'forms' directory. 
    The name is extracted from the 'formName' attribute within the XML file 
    rather than using the file name.

    Returns:
        List[str]: A list of human-readable form names. Returns an empty 
                   list if the 'forms' directory doesn't exist or is empty.
    """
    forms_dir = "forms"
    form_names = []
    logger.info("list_forms()")

    if not os.path.isdir(forms_dir):
        # The 'forms' directory doesn't exist, return an empty list
        return []

    # Iterate over all files in the 'forms' directory
    for filename in os.listdir(forms_dir):
        if filename.endswith(".xml"):
            file_path = os.path.join(forms_dir, filename)
            
            # Attempt to parse the XML file
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
                
                # Check for the required 'formName' attribute on the root element (<Form>)
                form_name = root.get("formName")
                
                if form_name:
                    form_names.append(form_name)
                # Note: We could log a warning if 'formName' is missing, but for simplicity, 
                # we just skip it if it's not found.

            except ET.ParseError:
                # Handle case where file is not valid XML
                # print(f"Warning: Could not parse XML file {filename}")
                continue
            except Exception:
                # Handle other file read errors
                # print(f"Warning: Error reading file {filename}")
                continue

    return form_names


@mcp.tool()
def get_form_xml(form_name: str) -> str:
    """
    Retrieves the raw XML content for a specific form name from the 'forms' directory.

    The function searches all XML files in the 'forms' directory and matches the 
    requested name against the 'formName' attribute inside the XML content.

    Args:
        form_name: The human-readable name of the form (e.g., "Vessel Registration").

    Returns:
        str: The raw XML content string if the form is found, otherwise 
             "Error: unable to find form name '<form_name>'."
    """
    forms_dir = "forms"
    logger.info("processing get_form_xml")

    if not os.path.isdir(forms_dir):
        # Forms directory doesn't exist, treat as not found
        return f"Error: unable to find form name '{form_name}'."

    # Iterate over all files in the 'forms' directory
    for filename in os.listdir(forms_dir):
        if filename.endswith(".xml"):
            file_path = os.path.join(forms_dir, filename)
            logger.debug( "processing filename: %s", file_path) 
            try:
                # 1. Parse the XML file
                tree = ET.parse(file_path)
                root = tree.getroot()

                # 2. Check for a match against the 'formName' attribute
                xml_form_name = root.get("formName")

                if xml_form_name == form_name:
                    # Found a match, read and return the full file content
                    with open(file_path, 'r') as f:
                        return f.read()

            except ET.ParseError:
                # Skip invalid XML files
                continue
            except Exception:
                # Skip files with other read errors
                continue

    # If the loop completes without finding a matching form
    return f"Error: unable to find form name '{form_name}'."

@mcp.tool
async def display_info( ctx: Context, info: str ) -> str:
   """
     Generic information display tool to force client to display content request
     Important - please format for terminal viewing.  Carriage returns
     and spaces

     parms:  
          ctx;  The FastMCP context
          info - the text to be displayed

   """
   logger.info("display_info")

   data1 = "Display: \n" + info

   result: AcceptedElicitation[dict] = await ctx.elicit( message=data1, response_type=Dict)

   if result.action == "accept":
       #return {"status": "success", "data": result.data}
       return "display_info is sucessful"  
   elif result.action == "decline":
       return {"status": "declined"}
   else:
       return {"status": "cancelled"}
 

@mcp.tool
async def elicit_dynamic_form(ctx: Context,  form_xml: str) -> dict:
    """
    A generic tool that elicits a response from the user
    using a provided XML form string.
    
    Args:
        ctx: The FastMCP context.
        form_xml: A string containing valid  form XML.
        
    Returns:
        an xml of the data collected from the form.
    """
    print(f"Eliciting with dynamically provided XML...")

    xml1  = form_xml if form_xml is not None else xml_form

    logger.info("elicit_dynamic_form - " )

    logger.info("form: %s ", xml1 )
    
    # 1. Elicit using the 'form_xml' argument

    result: AcceptedElicitation[dict] = await ctx.elicit( message=form_xml, response_type=Dict)


    # 2. Ensure action exists (fallback default)
    #action = getattr(result, "action", "submit")
    #result = await ctx.elicit(message=form_xml)
    #result = await ctx.elicit(message="type in accept")

    if result.action == "accept":
        #return {"status": "success", "data": result.data}
        return result.data 
    elif result.action == "decline":
        return {"status": "declined"}
    else:
        return {"status": "cancelled"}

if __name__ == "__main__":
    # Load configuration before starting the server
    load_config()
    logger.info("Starting MCP Command Server")
    mcp.run()

