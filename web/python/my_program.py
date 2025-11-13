import sys

if len(sys.argv) > 1:
    user_input = sys.argv[1]
    print(f"Hello from Python! You entered: {user_input}")
else:
    print("No input received.")