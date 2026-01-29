"""
Database connection setup for SQLite using SQLAlchemy 2.0
With WAL mode for concurrent reads/writes (Scraper + Dashboard)
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import os

# Database file path - stored in project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_ROOT, "ptt_sentiment.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine with SQLite
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    connect_args={"check_same_thread": False}  # Required for SQLite with threading
)

# CRITICAL: Enable WAL mode for concurrent reads/writes
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db() -> Session:
    """
    Context manager for database sessions.
    
    Usage:
        with get_db() as db:
            db.query(Post).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Get a database session (for use in generators/FastAPI style).
    Remember to close the session when done.
    """
    return SessionLocal()


def init_db():
    """Initialize the database tables."""
    from .models import Base
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized at: {DB_PATH}")


def vacuum_db():
    """Run VACUUM to optimize SQLite storage."""
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("VACUUM"))
        conn.commit()
    print("Database vacuumed successfully")
