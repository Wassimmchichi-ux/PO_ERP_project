"""Database engine and session factory.

Owns exactly two things: the SQLAlchemy ``Engine`` (one per process,
holding the connection pool) and the ``Session`` factory built on top
of it. Nothing here talks to specific tables — that's what
``app/repositories/`` is for.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verifies connections are alive before use;
                         # avoids "server closed the connection
                         # unexpectedly" errors after idle periods.
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,  # Lets services still read attributes off
                              # an entity right after commit, without
                              # triggering a surprise implicit query.
)


def get_session() -> Session:
    """Create a new Session bound to the shared engine.

    Not a FastAPI dependency itself (see
    ``app/dependencies/db.py`` for that) — kept separate so scripts,
    tests, and background tasks can obtain a session without going
    through the web layer at all.
    """
    return SessionLocal()
