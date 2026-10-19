"""Explicit local operator action; public registration never grants admin rights."""

import argparse
import getpass
from sqlalchemy import select
from app.db import SessionLocal
from app.models import User, Audit
from app.security import passwords

parser = argparse.ArgumentParser()
parser.add_argument("email")
args = parser.parse_args()
with SessionLocal.begin() as db:
    user = db.scalar(select(User).where(User.email == args.email.lower()))
    if not user:
        password = getpass.getpass("Admin password (10+ characters): ")
        if len(password) < 10:
            raise SystemExit("Password too short")
        user = User(email=args.email.lower(), name="管理员", password_hash=passwords.hash(password))
        db.add(user)
        db.flush()
    user.is_admin = True
    db.add(Audit(actor_id=user.id, action="ADMIN_GRANTED_BY_OPERATOR", details={"user_id": user.id}))
    print("Administrator configured:", user.email)
