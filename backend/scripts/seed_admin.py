#!/usr/bin/env python
"""
Creates the first ElevateGate administrator.

Interactive:
    python -m scripts.seed_admin

Non-interactive (e.g. a container entrypoint or CI bootstrap step):
    ADMIN_EMAIL=admin@example.com ADMIN_NAME="IT Admin" ADMIN_PASSWORD='...' \
        python -m scripts.seed_admin

The password is never printed, logged, or echoed to the terminal - interactive prompts use
getpass, and the non-interactive path reads it from an environment variable the caller is
responsible for not leaking (e.g. a Docker secret, not a logged CI variable).

Safe to re-run: if an admin with the given email already exists, the script reports that and
exits 0 without making any change - it's a bootstrap step, not a user-management tool.
"""

import asyncio
import getpass
import os
import sys

from app.core.security import hash_secret
from app.database import AsyncSessionLocal
from app.models.enums import AdminRole
from app.repositories import admin_user_repository

_MIN_PASSWORD_LENGTH = 12


def _prompt_for_credentials() -> tuple[str, str, str]:
    email = os.environ.get("ADMIN_EMAIL") or input("Admin email: ").strip()
    name = os.environ.get("ADMIN_NAME") or input("Admin name: ").strip()

    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    return email, name, password


async def _seed(email: str, name: str, password: str) -> int:
    if not email or "@" not in email:
        print("A valid email address is required.", file=sys.stderr)
        return 1
    if not name:
        print("A name is required.", file=sys.stderr)
        return 1
    if len(password) < _MIN_PASSWORD_LENGTH:
        print(f"Password must be at least {_MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 1

    async with AsyncSessionLocal() as session:
        existing = await admin_user_repository.get_by_email(session, email)
        if existing is not None:
            print(f"An admin with email {email} already exists; nothing to do.")
            return 0

        admin = await admin_user_repository.create(
            session,
            email=email,
            name=name,
            password_hash=hash_secret(password),
            role=AdminRole.ADMIN,
        )
        await session.commit()

    print(f"Created administrator {admin.email} (id={admin.id}, role={admin.role.value}).")
    return 0


def main() -> int:
    email, name, password = _prompt_for_credentials()
    return asyncio.run(_seed(email, name, password))


if __name__ == "__main__":
    raise SystemExit(main())
