# Command Line Interface Enhancer (command_cli_enh.py)

This script provides an enhanced command-line interface for interacting with the Gemini API, leveraging FastMCP for tool access.

## Usage

`python3 command_cli_enh.py [OPTIONS]`

### Parameters

*   `-p`, `--prompt <TEXT>`: Provide the prompt text directly from the command line.
*   `-f`, `--file <PATH>`: Specify the path to a text file containing the prompt.

**Note:** You must provide either `--prompt` or `--file`, but not both.

## Available MCP Tools

### Available Tools Summary ###


--- Tool 1/4 ---
* **Name:** run_command
* **Purpose:** Run a shell command on the local machine and get the output. Args: command: The shell command to execute. workdir: The working directory for the command. If None, uses the current directory. stdin: Optional stdin to pipe into the command. Returns: A dictionary containing the command's output, exit code, and error status.
* **Inputs:**
  - command*: <string>
  - workdir: <string | null>
  - stdin: <string | null>

--- Tool 2/4 ---
* **Name:** get_current_dir
* **Purpose:** Get the current working directory returns str -> directory ( ex "/home/user1"
* **Inputs:**
  (None)

--- Tool 3/4 ---
* **Name:** change_dir
* **Purpose:** Change the directory to specified string relative and absolute paths are supported If error - will return string "error: invalid directory"
* **Inputs:**
  - c_dir*: <string>

--- Tool 4/4 ---
* **Name:** run_expect_script
* **Purpose:** Run a program with a sequence of expect/send actions for programs that are interactive. Programs that require inputs. important: do not send carriage return or line feed with text on send. Args: program: The command to run (e.g. "python3 myscript.py"). Can be any command actions: A list of dicts, e.g. [{"action": "expect", "text": "foo"}, {"action":"send","text":"bar"}] Returns: The output from the interaction.
* **Inputs:**
  - program*: <string>
  - actions*: <array>

##############################
resouces: 
[Resource(name='system_info', title=None, uri=AnyUrl('resource://system_info'), description='Provides basic information about the host operating system.', mimeType='text/plain', size=None, icons=None, annotations=None, meta={'_fastmcp': {'tags': []}})]
