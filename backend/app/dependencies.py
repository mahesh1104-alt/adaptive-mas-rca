import os
import uuid

import psycopg2
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.models import User
from app.security import decode_access_token


# ============================================================
# PostgreSQL configuration
# ============================================================

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "rca_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "rca_password")
POSTGRES_DB = os.getenv("POSTGRES_DB", "rca_db")


# ============================================================
# Existing raw PostgreSQL dependency
# ============================================================

def get_db():
    connection = None

    try:
        connection = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB,
        )

        yield connection

    finally:
        if connection:
            connection.close()


# ============================================================
# SQLAlchemy configuration
# ============================================================

DATABASE_URL = (
    f"postgresql+psycopg2://"
    f"{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db_session():
    """
    Provide a SQLAlchemy database session for FastAPI endpoints.
    """

    db: Session = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# ============================================================
# JWT authentication
# ============================================================

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db_session),
) -> User:
    """
    Validate the JWT bearer token and return the authenticated user.
    """

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, user_uuid)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ============================================================
# Role authorization
# ============================================================

def require_engineer(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Allow access only to authenticated users with engineer role.
    """

    if current_user.role.lower() != "engineer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Engineer role required",
        )

    return current_user