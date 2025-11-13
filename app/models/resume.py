from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from beanie import Document
from pydantic import BaseModel, Field, ConfigDict


class Location(BaseModel):
    city: Optional[str] = None
    country: Optional[str] = None


class PersonalData(BaseModel):
    firstName: str = Field(..., alias="firstName")
    lastName: Optional[str] = Field(None, alias="lastName")
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    portfolio: Optional[str] = None
    location: Optional[Location] = None


class Experience(BaseModel):
    job_title: str = Field(..., alias="jobTitle")
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: str = Field(..., alias="startDate")
    end_date: str = Field(..., alias="endDate")
    description: List[str] = Field(default_factory=list)
    technologies_used: Optional[List[str]] = Field(default_factory=list, alias="technologiesUsed")


class Project(BaseModel):
    project_name: str = Field(..., alias="projectName")
    description: Optional[str] = None
    technologies_used: List[str] = Field(default_factory=list, alias="technologiesUsed")
    link: Optional[str] = None
    start_date: Optional[str] = Field(None, alias="startDate")
    end_date: Optional[str] = Field(None, alias="endDate")


class Skill(BaseModel):
    category: Optional[str] = None
    skill_name: str = Field(..., alias="skillName")


class ResearchWork(BaseModel):
    title: Optional[str] = None
    publication: Optional[str] = None
    date: Optional[str] = None
    link: Optional[str] = None
    description: Optional[str] = None


class Education(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = Field(None, alias="fieldOfStudy")
    start_date: Optional[str] = Field(None, alias="startDate")
    end_date: Optional[str] = Field(None, alias="endDate")
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
    experiences: List[Experience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    skills: List[Skill] = Field(default_factory=list)
    research_work: List[ResearchWork] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    extracted_keywords: List[str] = Field(default_factory=list)

    processed_at: datetime = Field(default_factory=datetime.utcnow)


class Resume(Document):
    user_id: str
    resume_id: str
    resume_name: str
    content: str
    content_type: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

