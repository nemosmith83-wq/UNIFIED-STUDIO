"""Create a Unified Studio account interactively on the server."""
from getpass import getpass

import auth


def main():
    username = input("Username: ").strip()
    display_name = input("Display name (optional): ").strip()
    password = getpass("Password (10+ chars, with letters and numbers): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords did not match.")
    try:
        user = auth.create_user(username, display_name, password)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(f"Created account: {user['username']}")


if __name__ == "__main__":
    main()
