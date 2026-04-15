"""Database seed script — demo users and access policies.

Run via:
    docker compose exec backend python -m app.scripts.seed_db
    # or locally:
    python -m app.scripts.seed_db

Creates:
  - 3 demo users (alice/engineer, bob/hr, charlie/manager)
  - access_policies rows for each role
  - Idempotent: skips rows that already exist
"""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, ".")

from app.auth.password import hash_password
from app.core.database import AsyncSessionLocal
from app.models.access_policy import AccessPolicy
from app.models.user import User

DEMO_USERS = [
    {
        "username": "alice",
        "email": "alice@sentinelrag.local",
        "password": "alice123",
        "role": "engineer",
        "department": "platform",
    },
    {
        "username": "bob",
        "email": "bob@sentinelrag.local",
        "password": "bob123",
        "role": "hr",
        "department": "people_ops",
    },
    {
        "username": "charlie",
        "email": "charlie@sentinelrag.local",
        "password": "charlie123",
        "role": "manager",
        "department": "engineering",
    },
]

# Maps (role, department) → comma-separated allowed classifications
DEMO_POLICIES = [
    # Engineers see internal engineering docs
    {"role": "engineer", "department": "engineering", "allowed_classification": "internal"},
    # HR sees internal and confidential HR docs
    {"role": "hr", "department": "hr", "allowed_classification": "internal,confidential"},
    # Managers see their own department (engineering) + legal docs
    # HR docs are restricted to HR staff only — managers do not have cross-dept HR access
    {"role": "manager", "department": "engineering", "allowed_classification": "internal"},
    {"role": "manager", "department": "legal", "allowed_classification": "internal,confidential"},
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        # ── Users ──────────────────────────────────────────────────────────
        for data in DEMO_USERS:
            existing = await db.execute(
                select(User).where(User.username == data["username"])
            )
            if existing.scalar_one_or_none() is not None:
                print(f"  [skip] user '{data['username']}' already exists")
                continue

            user = User(
                username=data["username"],
                email=data["email"],
                hashed_password=hash_password(data["password"]),
                role=data["role"],
                department=data["department"],
            )
            db.add(user)
            print(f"  [create] user '{data['username']}' (role={data['role']})")

        await db.commit()

        # ── Access Policies ────────────────────────────────────────────────
        for p in DEMO_POLICIES:
            existing = await db.execute(
                select(AccessPolicy).where(
                    AccessPolicy.role == p["role"],
                    AccessPolicy.department == p["department"],
                )
            )
            if existing.scalar_one_or_none() is not None:
                print(f"  [skip] policy {p['role']}/{p['department']} already exists")
                continue

            policy = AccessPolicy(
                role=p["role"],
                department=p["department"],
                allowed_classification=p["allowed_classification"],
            )
            db.add(policy)
            print(f"  [create] policy {p['role']} → {p['department']} ({p['allowed_classification']})")

        await db.commit()

    print("\nSeed complete.")


if __name__ == "__main__":
    print("Seeding database...")
    asyncio.run(seed())
