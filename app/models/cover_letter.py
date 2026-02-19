from typing import Optional
from datetime import datetime, UTC
from beanie import Document
from pydantic import Field

class CoverLetter(Document):
    user_id: str
    job_id: str
    resume_id: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "cover_letters"
