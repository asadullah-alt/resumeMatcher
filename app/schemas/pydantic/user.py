from typing import Optional
from pydantic import BaseModel

class UserPreferences(BaseModel):
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    visa_sponsorship: Optional[bool] = None
    remote_friendly: Optional[bool] = None
    country: Optional[str] = None
    city: Optional[str] = None
    experience: Optional[float] = None

class UserPreferencesUpdate(BaseModel):
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    visa_sponsorship: Optional[bool] = None
    remote_friendly: Optional[bool] = None
    country: Optional[str] = None
    city: Optional[str] = None
    experience: Optional[float] = None
    token: str
