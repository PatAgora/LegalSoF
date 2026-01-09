#!/usr/bin/env python3
"""
Script to create initial admin user.
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Add parent directory to path
sys.path.insert(0, ".")

from app.models.user import User, UserRole
from app.core.security import get_password_hash
from app.core.config import settings


async def create_admin():
    """Create initial admin user."""
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Check if admin exists
        result = await session.execute(
            select(User).where(User.email == "admin@example.com")
        )
        existing_admin = result.scalar_one_or_none()
        
        if existing_admin:
            print("✓ Admin user already exists")
            return
        
        # Create admin user
        admin_user = User(
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            full_name="System Administrator",
            role=UserRole.ADMIN,
            is_active=True,
            is_superuser=True,
        )
        
        session.add(admin_user)
        await session.commit()
        
        print("✓ Admin user created successfully")
        print("  Email: admin@example.com")
        print("  Password: admin123")
        print("  ⚠️  Please change the password immediately!")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_admin())
