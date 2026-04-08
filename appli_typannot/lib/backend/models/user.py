from datetime import datetime
from pydantic import EmailStr
from sqlmodel import SQLModel, Field


class UserBase(SQLModel):
    name: str = Field(index=True)
    age: int | None = Field(default=None, index=True)
    email: EmailStr = Field(index=True, unique=True)
    number: str = Field(min_length=10, max_length=15)


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    secret_name: str
    hashed_password: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)


class UserPublic(UserBase):
    id: int
    is_active: bool


class UserCreate(UserBase):
    secret_name: str
    password: str = Field(min_length=6, max_length=200)


class UserUpdate(SQLModel):
    name: str | None = None
    age: int | None = None
    email: EmailStr | None = None
    number: str | None = None
    secret_name: str | None = None
    is_active: bool | None = None


class UserListResponse(SQLModel):
    users: list[UserPublic]
    total: int
    offset: int
    limit: int

class LoginRequest(SQLModel):
    email: EmailStr
    password: str = Field(max_length=200)
