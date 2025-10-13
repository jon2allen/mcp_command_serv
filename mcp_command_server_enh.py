import os
import platform
import sys
import json
import base64
import asyncio
import logging
import argparse
import subprocess
from typing import Dict, Any, List, Optional
import tomli # Import tomli to load the config
import re    # Import re for robust command checking
from pexpect_auto import PexpectAutomator

# The user's template uses FastMCP, so we'll import that.
from fastmcp import FastMCP

# --- Logging setup (from template) ---
LOG_FILE = "mcp_command_server.log"
logging.basicConfig(
    level=logging.INFO,
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
    }
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
def is_command_blocked(command: str) -> bool:
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
    ...
    """
    logger.info("Received run_command request: command='%s', workdir='%s'", command, workdir)
    
    blocked_feedback = "This server is not authorized to run these commands"

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

 
if __name__ == "__main__":
    # Load configuration before starting the server
    load_config() 
    logger.info("Starting MCP Command Server")
    mcp.run()
