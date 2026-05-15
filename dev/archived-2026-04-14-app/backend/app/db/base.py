"""
Base class for all database models.
"""
from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy import Column, DateTime, func


class Base(DeclarativeBase):
    """Base class for all models."""
    
    @declared_attr.directive
    def __tablename__(cls) -> str:
        """Generate __tablename__ automatically from class name."""
        return cls.__name__.lower()
