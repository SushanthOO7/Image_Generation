from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.auth import create_access_token, get_current_user, hash_password, verify_password
from backend.app.database import get_db
from backend.app.models import User
from backend.app.repositories import create_user, get_user_by_email
from backend.app.responses import user_response
from backend.app.schemas import AuthRequest, AuthResponse, LoginRequest, UserResponse

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register(
    request: AuthRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    existing_user = get_user_by_email(db, request.email)
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = create_user(db, request.email, hash_password(request.password))
    return AuthResponse(access_token=create_access_token(user), user=user_response(user))


@router.post("/login", response_model=AuthResponse)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    user = get_user_by_email(db, request.email)
    if user is None or user.password_hash is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return AuthResponse(access_token=create_access_token(user), user=user_response(user))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return user_response(current_user)
