import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="engineer", max_length=50)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: uuid.UUID
    username: str
    role: str


class CurrentUserResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    email: EmailStr
    role: str