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

--- Tool 1/10 ---
* **Name:** run_command
* **Purpose:** Run a shell command on the local machine and get the output. Args: command: The shell command to execute. workdir: The working directory for the command. If None, uses the current directory. stdin: Optional stdin to pipe into the command. Returns: A dictionary containing the command's output, exit code, and error status.
* **Inputs:**
  - command*: <string>
  - workdir: <string | null>
  - stdin: <string | null>

--- Tool 2/10 ---
* **Name:** get_current_dir
* **Purpose:** Get the current working directory returns str -> directory ( ex "/home/user1"
* **Inputs:**
  (None)

--- Tool 3/10 ---
* **Name:** change_dir
* **Purpose:** Change the directory to specified string relative and absolute paths are supported If error - will return string "error: invalid directory"
* **Inputs:**
  - c_dir*: <string>

--- Tool 4/10 ---
* **Name:** run_expect_script
* **Purpose:** Run a program with a sequence of expect/send actions for programs that are interactive. Programs that require inputs. important: do not send carriage return or line feed with text on send. Args: program: The command to run (e.g. "python3 myscript.py"). Can be any command actions: A list of dicts, e.g. [{"action": "expect", "text": "foo"}, {"action":"send","text":"bar"}] Returns: The output from the interaction.
* **Inputs:**
  - program*: <string>
  - actions*: <array>

--- Tool 5/10 ---
* **Name:** create_form
* **Purpose:** Creates an XML form file based on the provided schema. schema definition: <?xml version="1.0" encoding="UTF-8"?> <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"> <xs:element name="Form"> <xs:complexType> <xs:sequence> <xs:element name="Field" minOccurs="0" maxOccurs="unbounded"> <xs:complexType> <xs:simpleContent> <xs:extension base="xs:string"> <xs:attribute name="name" type="xs:string" use="required"/> <xs:attribute name="type" use="required"> <xs:simpleType> <xs:restriction base="xs:string"> <xs:enumeration value="string"/> <xs:enumeration value="date"/> <xs:enumeration value="float"/> <xs:enumeration value="decimal"/> <xs:enumeration value="integer"/> </xs:restriction> </xs:simpleType> </xs:attribute> </xs:extension> </xs:simpleContent> </xs:complexType> </xs:element> </xs:sequence> <xs:attribute name="formName" type="xs:string" use="required"/> </xs:complexType> </xs:element> </xs:schema> Args: form_name: Name of the form (without extension). fields: List of tuples, each containing (field_name, field_type). Returns: str: "Form <form_name> created" or "Error: form not created".
* **Inputs:**
  - form_name*: <string>
  - fields*: <array>

--- Tool 6/10 ---
* **Name:** list_forms
* **Purpose:** Lists the names of all forms found in the 'forms' directory. The name is extracted from the 'formName' attribute within the XML file rather than using the file name. Returns: List[str]: A list of human-readable form names. Returns an empty list if the 'forms' directory doesn't exist or is empty.
* **Inputs:**
  (None)

--- Tool 7/10 ---
* **Name:** get_form_xml
* **Purpose:** Retrieves the raw XML content for a specific form name from the 'forms' directory. The function searches all XML files in the 'forms' directory and matches the requested name against the 'formName' attribute inside the XML content. Args: form_name: The human-readable name of the form (e.g., "Vessel Registration"). Returns: str: The raw XML content string if the form is found, otherwise "Error: unable to find form name '<form_name>'."
* **Inputs:**
  - form_name*: <string>

--- Tool 8/10 ---
* **Name:** display_info
* **Purpose:** Generic information display tool to force client to display content request Important - please format for terminal viewing. Carriage returns and spaces parms: ctx; The FastMCP context info - the text to be displayed
* **Inputs:**
  - info*: <string>

--- Tool 9/10 ---
* **Name:** elicit_dynamic_form
* **Purpose:** A generic tool that elicits a response from the user using a provided XML form string. Args: ctx: The FastMCP context. form_xml: A string containing valid form XML. Returns: an xml of the data collected from the form.
* **Inputs:**
  - form_xml*: <string>

--- Tool 10/10 ---
* **Name:** file_write
* **Purpose:** Write a string to a text file. This tool writes the provided text content to a specific file. It is intended for text files only (no binary). The content is written 'as is' and is expected to be pre-formatted. Args: file_path: The path to the file to write. content: The text string to write. override: If True, overwrite existing files. If False, returns error if file exists. Returns: str: Success message or error message (e.g., "file exists").
* **Inputs:**
  - file_path*: <string>
  - content*: <string>
  - override: <boolean> (Default: False)

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

