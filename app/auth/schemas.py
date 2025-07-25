from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
import uuid

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, description="Password cannot be empty")
    display_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenRefresh(BaseModel):
    refresh_token: str

class UserResponse(BaseModel):
    model_config = {"from_attributes": True}
    
    id: uuid.UUID
    email: str
    display_name: str
    email_verified: bool
    created_at: datetime