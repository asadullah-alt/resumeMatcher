from __future__ import annotations

from datetime import datetime, timedelta
import jwt
import bcrypt
from typing import Optional
from beanie import Document
from pydantic import Field, BaseModel, EmailStr
from app.core.config import settings

class LocalAuth(BaseModel):
    email: EmailStr
    password: str

class FacebookAuth(BaseModel):
    id: str
    token: str
    name: str
    email: EmailStr

class GoogleAuth(BaseModel):
    id: str
    token: str
    email: EmailStr
    name: str

class LinkedInAuth(BaseModel):
    id: str
    token: str
    email: EmailStr
    name: str

class User(Document):
    local: Optional[LocalAuth] = None
    facebook: Optional[FacebookAuth] = None
    google: Optional[GoogleAuth] = None
    linkedin: Optional[LinkedInAuth] = None
    extension_token: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    async def generate_hash(self, password: str) -> str:
        """Generate a hashed password using bcrypt."""
        salt = bcrypt.gensalt(8)
        return bcrypt.hashpw(password.encode(), salt).decode()

    async def valid_password(self, password: str) -> bool:
        """Verify if the provided password matches the stored hash."""
        if not self.local or not self.local.password:
            return False
        return bcrypt.checkpw(
            password.encode(),
            self.local.password.encode()
        )

    async def generate_jwt(self, email: str) -> str:
        """Generate a JWT token valid for 15 minutes."""
       
        expiration = datetime.utcnow() + timedelta(minutes=15)
        
        payload = {
            "email": email,
            "id": str(self.id),
            "exp": int(expiration.timestamp())
        }
        
        return jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm="HS256"
        )

    class Settings:
        name = "users"  # MongoDB collection name

