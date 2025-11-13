from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from beanie import Document
from pydantic import Field


class ProcessedResume(Document):
    """Processed resume stored as a Beanie Document.

    For compatibility with existing service logic we store structured
    blobs as JSON-encoded strings (same field names as before).
    """
    resume_name:str
    resume_id: str
    personal_data: Optional[str] = None
    experiences: Optional[str] = None
    projects: Optional[str] = None
    skills: Optional[str] = None
    research_work: Optional[str] = None
    achievements: Optional[str] = None
    education: Optional[str] = None
    extracted_keywords: Optional[str] = None
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class Resume(Document):
    user_id: str
    resume_id: str
    resume_name: str
    content: str
    content_type: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

