import logging
import pexpect

class PexpectAutomator:
    """
    A class to automate interactions with command-line programs using the `pexpect` library.
    """

    def __init__(self, program, actions):
        """
        Initialize the PexpectAutomator.

        Args:
            program (str): The command or script to run (e.g., 'python3 pythagoras.py').
            actions (list[tuple]): A list of tuples, where each tuple is ('expect', text) or ('send', text).
        """
        self.program = program
        self.actions = actions
        self.child = None
        self.output = None
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing PexpectAutomator for program: '%s'", program)
        self.logger.debug("Actions: %s", actions)

    def run(self):
        """
        Run the program and execute the specified expect/send actions.

        Returns:
            str: The captured output as a string, or None if an error occurs.
        """
        self.logger.info("Starting program: '%s'", self.program)
        try:
            # Start the program
            self.child = pexpect.spawn(self.program, encoding='utf-8')
            self.logger.info("Program spawned with PID: %d", self.child.pid)

            for action, text in self.actions:
                self.logger.debug("Processing action: %s, text: %s", action, text)
                if action == 'expect':
                    self.logger.info("Waiting for text: '%s'", text)
                    self.child.expect(text)
                elif action == 'send':
                    self.logger.info("Sending text: '%s'", text)
                    self.child.sendline(text)
                else:
                    raise ValueError(f"Unknown action: {action}")

            # Capture the remaining output
            self.output = self.child.read()
            self.logger.info("Captured output: %s", self.output)
            return self.output

        except pexpect.ExceptionPexpect as e:
            self.logger.error("Pexpect error: %s", e, exc_info=True)
            return None
        except ValueError as e:
            self.logger.error("Value error: %s", e, exc_info=True)
            return None
        except Exception as e:
            self.logger.error("Unexpected error: %s", e, exc_info=True)
            return None
        finally:
            if self.child and self.child.isalive():
                self.logger.info("Closing child process (PID: %d)", self.child.pid)
                self.child.close()

