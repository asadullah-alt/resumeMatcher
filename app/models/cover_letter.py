from typing import Optional
from datetime import datetime
from beanie import Document
from pydantic import Field

class CoverLetter(Document):
    user_id: str
    job_id: str
    resume_id: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "cover_letters"
