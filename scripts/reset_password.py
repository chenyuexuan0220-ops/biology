"""Reset an existing account password from the local server workspace."""

import argparse
import getpass

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Audit, User
from app.security import passwords


def main():
    parser = argparse.ArgumentParser(description="Reset an existing account password")
    parser.add_argument("email", help="Email address of the existing account")
    args = parser.parse_args()

    with SessionLocal.begin() as db:
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
        if not user:
            raise SystemExit("Account not found")

        password = getpass.getpass("New password (10+ characters): ")
        if len(password) < 10 or len(password) > 128:
            raise SystemExit("Password must contain 10-128 characters")
        confirmation = getpass.getpass("Confirm new password: ")
        if password != confirmation:
            raise SystemExit("Passwords do not match")

        user.password_hash = passwords.hash(password)
        db.add(Audit(actor_id=user.id, action="PASSWORD_RESET_BY_OPERATOR", details={"user_id": user.id}))
        print("Password reset:", user.email)


if __name__ == "__main__":
    main()
