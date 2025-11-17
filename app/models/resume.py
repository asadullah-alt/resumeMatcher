from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from beanie import Document
from pydantic import BaseModel, Field, ConfigDict


class Location(BaseModel):
    city: Optional[str] = None
    country: Optional[str] = None


class PersonalData(BaseModel):
    first_name: str = Field(..., alias="first_name")
    last_name: Optional[str] = Field(None, alias="last_name")
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    portfolio: Optional[str] = None
    location: Optional[Location] = None


class Experience(BaseModel):
    job_title: str = Field(..., alias="job_title")
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: str = Field(..., alias="start_date")
    end_date: Optional[str] = Field(..., alias="end_date")
    description: Optional[List[str]] = Field(default_factory=list)
    technologies_used: Optional[List[str]] = Field(default_factory=list, alias="technologies_used")


class Project(BaseModel):
    project_name: str = Field(..., alias="project_name")
    description: Optional[str] = None
    technologies_used: List[str] = Field(default_factory=list, alias="technologies_used")
    link: Optional[str] = None
    start_date: Optional[str] = Field(None, alias="start_date")
    end_date: Optional[str] = Field(None, alias="end_date")


class Skill(BaseModel):
    category: Optional[str] = None
    skill_name: str = Field(..., alias="skill_name")


class ResearchWork(BaseModel):
    title: Optional[str] = None
    publication: Optional[str] = None
    date: Optional[str] = None
    link: Optional[str] = None
    description: Optional[str] = None


class Education(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = Field(None, alias="field_of_study")
    start_date: Optional[str] = Field(None, alias="start_date")
    end_date: Optional[str] = Field(None, alias="end_date")
    grade: Optional[str] = None
    description: Optional[str] = None


class ProcessedResume(Document):
    """Processed resume stored as a Beanie Document with structured fields.

    Keep `user_id`, `resume_name`, `resume_id` and `processed_at` unchanged.
    Other fields are structured according to the provided `StructuredResumeModel`.
    """
    user_id: str
    resume_name: str
    resume_id: str

    personal_data: Optional[PersonalData] = None
    experiences: Optional[List[Experience]] = Field(default_factory=list)
    projects: Optional[List[Project]] = Field(default_factory=list)
    skills: Optional[List[Skill]] = Field(default_factory=list)
    research_work: Optional[List[ResearchWork]] = Field(default_factory=list)
    achievements: Optional[List[str]] = Field(default_factory=list)
    education: Optional[List[Education]] = Field(default_factory=list)
    extracted_keywords: Optional[List[str]] = Field(default_factory=list)

    processed_at: datetime = Field(default_factory=datetime.utcnow)


class Resume(Document):
    user_id: str
    resume_id: str
    resume_name: str
    content: str
    content_type: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

