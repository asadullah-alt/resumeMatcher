from __future__ import annotations

from datetime import datetime, timedelta, UTC
import jwt
import bcrypt
from typing import Optional
from beanie import Document
from pydantic import Field, BaseModel, EmailStr, ConfigDict
from app.core.config import settings
from app.models.account_type import AccountType

class LocalAuth(BaseModel):
    email: EmailStr
    password: Optional[str] = None
    token: Optional[str] = None

class FacebookAuth(BaseModel):
    id: str
    token: str
    name: str
    email: EmailStr
class VerificationCode(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    code: str
    expires_at: datetime = Field(alias="expiresAt")

class VerificationAttempts(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    count: int
    last_attempt: Optional[datetime] = Field(None, alias="lastAttempt")

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
    verification_code: Optional[VerificationCode] = Field(None, alias="verificationCode")
    verification_attempts: Optional[VerificationAttempts] = Field(None, alias="verificationAttempts")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Billing fields
    account_type: AccountType = Field(default=AccountType.JOB_TRACKER)
    credits_remaining: int = Field(default=5)
    credits_used_this_period: int = Field(default=0)
    last_credit_reset: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total_credits_lifetime: int = Field(default=0)
    
    # User Preferences
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    visa_sponsorship: Optional[bool] = None
    remote_friendly: Optional[bool] = None
    country: Optional[str] = None
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
       
        expiration = datetime.now(UTC) + timedelta(minutes=15)
        
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

