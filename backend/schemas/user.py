from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    admin_email: EmailStr
    admin_password: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_admin: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str
