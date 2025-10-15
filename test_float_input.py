try:
    x = float(input("Enter a float: "))
    print(f"You entered: {x}")
except ValueError:
    print("Invalid float")
