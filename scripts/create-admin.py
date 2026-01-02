#!/usr/bin/env python3
"""Create initial admin user for AI Gateway."""
import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings
from app.core.security import get_password_hash
from app.database import AsyncSessionLocal
from app.models.user import User
from sqlalchemy import select


async def create_admin():
    settings = get_settings()
    
    async with AsyncSessionLocal() as db:
        # Check if admin exists
        result = await db.execute(
            select(User).where(User.is_superuser == True)
        )
        if result.scalar_one_or_none():
            print("Admin user already exists.")
            return
        
        # Get credentials from env or prompt
        email = os.environ.get("ADMIN_EMAIL")
        password = os.environ.get("ADMIN_PASSWORD")
        
        if not email:
            email = input("Admin email: ")
        if not password:
            import getpass
            password = getpass.getpass("Admin password: ")
        
        # Create user
        admin = User(
            email=email,
            username=email.split("@")[0],
            password_hash=get_password_hash(password),
            is_active=True,
            is_superuser=True,
            auth_provider="local",
        )
        
        db.add(admin)
        await db.commit()
        
        print(f"Admin user created: {email}")


if __name__ == "__main__":
    asyncio.run(create_admin())
