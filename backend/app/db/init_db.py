"""Database metadata initialization for the Demo application."""

from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401 - register all SQLAlchemy models with Base


def create_tables() -> None:
    """Create missing tables without altering existing data."""
    Base.metadata.create_all(bind=engine)
