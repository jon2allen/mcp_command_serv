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

##

| File                     | Purpose                                                                                     |
|--------------------------|---------------------------------------------------------------------------------------------|
| LICENSE                  | Contains the MIT License, granting permission to use, copy, modify, and distribute the software. |
| README.md                | Provides a general overview of the project, its purpose, and usage instructions.             |
| command_cli_enh.py       | A command-line interface (CLI) for interacting with the mcp_command_server_enh.py script.     |
| config.toml              | Configuration file for the project, likely containing settings for the server and CLI.      |
| item.py                  | random vegetable and fruit generator - used for demonstrarion.                              |
| list.py                  | command to list mcp tools using list tools                            .                     |
| mcp_command_server_enh.py| The main command server script that listens for and executes commands.                      |
| orig.py                  | Appears to be an earlier version or a related script.                                       |
| pexpect_auto.py          | Uses the pexpect library to automate interactions with another program.                      |
| pythagoras.py            | A script related to the Pythagorean theorem, possibly for testing or demonstration.          |
| test1.txt - test7.txt    | Test promptSs  used for testing the functionality of the scripts.                          |
| test_float_input.py      | A script for testing floating-point number input.                                           |
| test_input.py            | A script for testing general input.                                                         |

