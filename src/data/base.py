"""SQLAlchemy declarative base shared across ORM models and database helpers."""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
