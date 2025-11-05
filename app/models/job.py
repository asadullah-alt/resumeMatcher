from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from beanie import Document
from pydantic import Field


class ProcessedJob(Document):
    user_id: str
    job_id: str
    job_title: Optional[str] = None
    company_profile: Optional[str] = None
    location: Optional[str] = None
    date_posted: Optional[str] = None
    employment_type: Optional[str] = None
    job_summary: Optional[str] = None
    key_responsibilities: Optional[str] = None
    qualifications: Optional[str] = None
    compensation_and_benfits: Optional[str] = None
    application_info: Optional[str] = None
    extracted_keywords: Optional[str] = None
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class Job(Document):
    user_id: str
    job_id: str
    resume_id: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

