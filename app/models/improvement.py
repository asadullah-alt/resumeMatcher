from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any

from beanie import Document
from pydantic import Field


class Improvement(Document):
    """Stores improvement analysis results for resume-job combinations."""
    
    resume_id: str
    job_id: str
    original_score: float
    new_score: float
    updated_resume: str = Field(..., description="HTML formatted updated resume")
    resume_preview: Optional[Dict[str, Any]] = None
    details: str = ""
    commentary: str = ""
    improvements: List[Dict[str, Any]] = Field(default_factory=list)
    original_resume_markdown: str
    updated_resume_markdown: str
    job_description: str
    job_keywords: str
    skill_comparison: List[Dict[str, Any]] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "Improvement"
        indexes = [
            "resume_id",
            "job_id",
            [("resume_id", 1), ("job_id", 1)],  # Compound index for unique resume-job combination
            "created_at",
            "updated_at",
        ]
