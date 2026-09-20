from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import (
    get_db_session,
    get_current_user,
)
from app.db.models import User
from app.models.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    CurrentUserResponse,
)
from app.security import (
    JWT_EXPIRE_MINUTES,
    create_access_token,
    verify_password,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


# ============================================================
# Auth status
# ============================================================

@router.get("/")
def auth_status():
    return {
        "status": "success",
        "message": "Auth router is working",
    }


# ============================================================
# Register
# ============================================================

@router.post(
    "/register",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db_session),
):
    existing_user = db.scalar(
        select(User).where(
            User.email == payload.email
        )
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


# ============================================================
# Login
# ============================================================

@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db_session),
):
    user = db.scalar(
        select(User).where(
            User.email == payload.email
        )
    )

    if user is None or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    if not verify_password(
        payload.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    access_token = create_access_token(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=JWT_EXPIRE_MINUTES * 60,
        path="/",
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.user_id,
        username=user.username,
        role=user.role,
    )

# ============================================================
# Current authenticated user
# ============================================================

@router.get(
    "/me",
    response_model=CurrentUserResponse,
)
def current_user(
    current_user: User = Depends(get_current_user),
):
    return current_user


# ============================================================
# Logout
# ============================================================

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key="access_token",
        path="/",
    )

    return {
        "status": "success",
        "message": "Logged out successfully",
    }