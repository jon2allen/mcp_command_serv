import random

# Lists of fruits and vegetables
fruits = [
    "apple", "banana", "cherry", "date", "elderberry",
    "fig", "grape", "honeydew", "kiwi", "lemon",
    "mango", "nectarine", "orange", "peach", "quince",
    "raspberry", "strawberry", "tangerine", "watermelon", "blueberry"
]

vegetables = [
    "carrot", "broccoli", "spinach", "potato", "onion",
    "garlic", "cucumber", "lettuce", "tomato", "pepper",
    "zucchini", "eggplant", "celery", "radish", "beet",
    "asparagus", "cabbage", "cauliflower", "green bean", "peas"
]

# Ask user for input
user_choice = input("Do you want a 'vegetable' or a 'fruit'? ").strip().lower()

# Validate input
while user_choice not in ["vegetable", "fruit"]:
    print("Invalid choice. Please enter 'vegetable' or 'fruit'.")
    user_choice = input("Do you want a 'vegetable' or a 'fruit'? ").strip().lower()

# Generate random quantity and item
quantity = random.randint(10, 30)
if user_choice == "fruit":
    item = random.choice(fruits)
else:
    item = random.choice(vegetables)

# Output the result
print(f"You get {quantity} {item}(s)!")

