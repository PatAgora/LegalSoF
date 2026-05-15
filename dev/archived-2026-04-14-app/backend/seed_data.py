"""Seed database with test data"""
import os
import secrets
import string
import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import User, Matter
from app.core.security import get_password_hash, validate_password_policy
from app.core.config import settings
from datetime import datetime, timedelta


def generate_secure_password(length: int = 16) -> str:
    """Generate a password that meets the security policy."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        valid, _ = validate_password_policy(password)
        if valid:
            return password


db_url = str(settings.DATABASE_URL).replace("postgresql+asyncpg", "postgresql")
engine = create_engine(db_url)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    # Admin user
    admin = db.query(User).filter(User.email == 'admin@example.com').first()
    if not admin:
        password = os.environ.get("ADMIN_PASSWORD") or generate_secure_password()
        admin = User(
            email='admin@example.com',
            hashed_password=get_password_hash(password),
            full_name='Admin User',
            is_active=True,
            is_superuser=True
        )
        db.add(admin)
        db.commit()
        print("Admin user created")
        if not os.environ.get("ADMIN_PASSWORD"):
            print(f"  Generated password: {password}")
            print("  Save this and change it after first login.")
    else:
        print("Admin user exists")

    # Test matters
    if db.query(Matter).count() == 0:
        matters = [
            Matter(
                reference_number='MAT-2024-001',
                client_name='John Smith',
                client_entity_name='Smith Holdings Ltd',
                transaction_type='PROPERTY_PURCHASE',
                target_amount=500000.00,
                target_currency='GBP',
                target_business_name='123 High Street, London',
                transaction_date=datetime.now() + timedelta(days=30),
                status='UNDER_REVIEW',
                risk_rating='MEDIUM',
                created_by_id=admin.id
            ),
            Matter(
                reference_number='MAT-2024-002',
                client_name='Sarah Johnson',
                client_entity_name='Johnson Ventures Ltd',
                transaction_type='BUSINESS_PURCHASE',
                target_amount=2500000.00,
                target_currency='GBP',
                target_business_name='TechStart Solutions Ltd',
                transaction_date=datetime.now() + timedelta(days=60),
                status='UNDER_REVIEW',
                risk_rating='HIGH',
                created_by_id=admin.id
            ),
            Matter(
                reference_number='MAT-2024-003',
                client_name='Michael Chen',
                client_entity_name='Chen Investment Group',
                transaction_type='INVESTMENT',
                target_amount=1000000.00,
                target_currency='GBP',
                target_business_name='Green Energy Fund',
                description='Investment in renewable energy fund',
                transaction_date=datetime.now() + timedelta(days=45),
                status='DRAFT',
                risk_rating='LOW',
                created_by_id=admin.id
            )
        ]
        for m in matters:
            db.add(m)
        db.commit()
        print("Created 3 test matters")
    else:
        print("Matters exist")

    print("\nSeed complete!")
except Exception as e:
    print(f"Error: {e}")
    db.rollback()
finally:
    db.close()
