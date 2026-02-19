from __future__ import annotations

from datetime import datetime, UTC
from typing import Optional, List
from enum import Enum

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
    start_date: Optional[str] = Field(None, alias="start_date")
    end_date: Optional[str] = Field(None, alias="end_date")
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


class Publication(BaseModel):
    title: Optional[str] = None
    authors: Optional[List[str]] = Field(default_factory=list)
    publication_venue: Optional[str] = Field(None, alias="publication_venue")
    date: Optional[str] = None
    link: Optional[str] = None
    description: Optional[str] = None


class Language(BaseModel):
    language: Optional[str] = None
    proficiency: Optional[str] = None


class ConferenceType(str, Enum):
    CONFERENCE = "conference"
    TRAINING = "training"
    WORKSHOP = "workshop"


class ConferenceTrainingWorkshop(BaseModel):
    type: Optional[ConferenceType] = None
    name: Optional[str] = None
    organizer: Optional[str] = None
    date: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    certificate_link: Optional[str] = Field(None, alias="certificate_link")


class Award(BaseModel):
    title: Optional[str] = None
    issuer: Optional[str] = None
    date: Optional[str] = None
    description: Optional[str] = None


class ExtracurricularActivity(BaseModel):
    activity_name: Optional[str] = Field(None, alias="activity_name")
    role: Optional[str] = None
    organization: Optional[str] = None
    start_date: Optional[str] = Field(None, alias="start_date")
    end_date: Optional[str] = Field(None, alias="end_date")
    description: Optional[str] = None


class ImprovedResume(Document):
    """Improved resume stored as a Beanie Document with structured fields."""
  
    job_id: str
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
    publications: Optional[List[Publication]] = Field(default_factory=list)
    conferences_trainings_workshops: Optional[List[ConferenceTrainingWorkshop]] = Field(default_factory=list)
    awards: Optional[List[Award]] = Field(default_factory=list)
    extracurricular_activities: Optional[List[ExtracurricularActivity]] = Field(default_factory=list)
    languages: Optional[List[Language]] = Field(default_factory=list)
    summary: Optional[str] = None
    extracted_keywords: Optional[List[str]] = Field(default_factory=list)
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class ProcessedResume(Document):
    """Processed resume stored as a Beanie Document with structured fields.

    Keep `user_id`, `resume_name`, `resume_id` and `processed_at` unchanged.
    Other fields are structured according to the provided `StructuredResumeModel`.
    """
    user_id: str
    resume_name: str
    resume_id: str
    default: bool = False
    personal_data: Optional[PersonalData] = None
    experiences: Optional[List[Experience]] = Field(default_factory=list)
    projects: Optional[List[Project]] = Field(default_factory=list)
    skills: Optional[List[Skill]] = Field(default_factory=list)
    research_work: Optional[List[ResearchWork]] = Field(default_factory=list)
    achievements: Optional[List[str]] = Field(default_factory=list)
    education: Optional[List[Education]] = Field(default_factory=list)
    publications: Optional[List[Publication]] = Field(default_factory=list)
    conferences_trainings_workshops: Optional[List[ConferenceTrainingWorkshop]] = Field(default_factory=list)
    awards: Optional[List[Award]] = Field(default_factory=list)
    extracurricular_activities: Optional[List[ExtracurricularActivity]] = Field(default_factory=list)
    languages: Optional[List[Language]] = Field(default_factory=list)
    summary: Optional[str] = None
    extracted_keywords: Optional[List[str]] = Field(default_factory=list)

    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Resume(Document):
    user_id: str
    resume_id: str
    resume_name: str
    content: str
    content_type: Optional[str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

