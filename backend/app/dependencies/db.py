"""FastAPI dependencies for database access.

This is the seam between the web layer and the database layer: routes
depend on ``get_db``, never on ``app.db.session`` directly. That keeps
``main.py``/routers ignorant of how sessions are constructed, and makes
it trivial to override this dependency in tests with an in-memory or
transactional test session.
"""
from typing import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped SQLAlchemy session.

    One session per request, always closed afterward. Rolls back on
    exception so a failed request never leaves a half-committed
    transaction lingering on the connection.

    Spring Boot equivalent: the request-scoped ``EntityManager`` Spring
    Data JPA manages for you per HTTP request.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
