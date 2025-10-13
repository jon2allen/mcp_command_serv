import pexpect

class PexpectAutomator:
    def __init__(self, program, actions):
        """
        Initialize the PexpectAutomator.

        :param program: The command or script to run (e.g., 'python3 pythagoras.py').
        :param actions: A list of tuples, where each tuple is ('expect', text) or ('send', text).
        """
        self.program = program
        self.actions = actions
        self.child = None
        self.output = None

    def run(self):
        """
        Run the program and execute the specified expect/send actions.
        Returns the captured output as a string.
        """
        try:
            # Start the program
            self.child = pexpect.spawn(self.program)

            for action, text in self.actions:
                if action == 'expect':
                    self.child.expect(text)
                elif action == 'send':
                    self.child.sendline(text)
                else:
                    raise ValueError(f"Unknown action: {action}")

            # Capture the remaining output
            self.output = self.child.read().decode()
            return self.output

        except pexpect.ExceptionPexpect as e:
            print(f"Error: {e}")
            return None
        finally:
            if self.child and self.child.isalive():
                self.child.close()

# Example usage
def run_pythagorean_with_pexpect():
    actions = [
        ('expect', "Length of side a: "),
        ('send', "3"),
        ('expect', "Length of side b: "),
        ('send', "4"),
        ('expect', "The length of the hypotenuse"),
    ]
    automator = PexpectAutomator('python3 pythagoras.py', actions)
    output = automator.run()
    if output is not None:
        print(output)
    return output

# Uncomment to test
#result = run_pythagorean_with_pexpect()
#print("Captured output:", result)

