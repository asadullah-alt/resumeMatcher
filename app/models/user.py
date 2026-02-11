from __future__ import annotations

from datetime import datetime, timedelta
import jwt
import bcrypt
from typing import Optional
from beanie import Document
from pydantic import Field, BaseModel, EmailStr
from app.core.config import settings
from app.models.account_type import AccountType

class LocalAuth(BaseModel):
    email: EmailStr
    password: str
    token: str

class FacebookAuth(BaseModel):
    id: str
    token: str
    name: str
    email: EmailStr
class verificationCode(BaseModel):
    code: str
    expiresAt: datetime
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
    active_resume: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Billing fields
    account_type: AccountType = Field(default=AccountType.JOB_TRACKER)
    credits_remaining: int = Field(default=5)
    credits_used_this_period: int = Field(default=0)
    last_credit_reset: datetime = Field(default_factory=datetime.utcnow)
    total_credits_lifetime: int = Field(default=0)

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

