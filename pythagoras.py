import math

def pythagorean_theorem():
    """
    Demonstrates the Pythagorean theorem by calculating the hypotenuse
    of a right triangle given the lengths of the other two sides.
    """
    print("Pythagorean Theorem: a² + b² = c²")
    print("Enter the lengths of the two legs of a right triangle:")

    try:
        a = float(input("Length of side a: "))
        b = float(input("Length of side b: "))

        if a <= 0 or b <= 0:
            print("Error: Lengths must be positive numbers.")
            return

        c = math.sqrt(a**2 + b**2)
        print(f"The length of the hypotenuse (c) is: {c:.2f}")

    except ValueError:
        print("Error: Please enter valid numbers.")

if __name__ == "__main__":
    pythagorean_theorem()

