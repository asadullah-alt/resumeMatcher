from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field, AliasChoices


class Location(BaseModel):
    city: Optional[str] = None
    country: Optional[str] = None


class PersonalData(BaseModel):
    first_name: str = Field(..., alias="first_name")
    last_name: Optional[str] = Field(..., alias="last_name")
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    portfolio: Optional[str] = None
    location: Optional[Location] = None


class Experience(BaseModel):
    job_title: str = Field(..., alias="job_title")
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = Field(..., alias="start_date")
    end_date: Optional[str] = Field(..., alias="end_date")
    description: Optional[List[str]] = Field(default_factory=list, alias="description")
    technologies_used: Optional[List[str]] = Field(
        default_factory=list, alias="technologies_used"
    )


class Project(BaseModel):
    project_name: str = Field(..., validation_alias=AliasChoices('name', 'title', 'project_name'))
    description: Optional[str] = None
    technologies_used: Optional[List[str]] = Field(..., validation_alias=AliasChoices('technologies', 'tech_stack', 'tools',"technologies_used"))
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


class Language(BaseModel):
    language: Optional[str] = None
    proficiency: Optional[str] = None


class StructuredResumeModel(BaseModel):
    personal_data: dict = Field(
        validation_alias=AliasChoices("personalInfo", "personal_details", "personal_data")
    )
    experiences: List[Experience] = Field(default_factory=list, alias="experiences")
    projects: Optional[List[Project]] = Field(default_factory=list, alias="projects")
    skills: Optional[List[Skill]] = Field(default_factory=list, alias="skills")
    research_work: Optional[List[ResearchWork]] = Field(
        default_factory=list, alias="research_work"
    )
    achievements: Optional[List[str]] = Field(default_factory=list, alias="achievements")
    education: List[Education] = Field(default_factory=list, alias="education")
    publications: Optional[List[Publication]] = Field(default_factory=list, alias="publications")
    conferences_trainings_workshops: Optional[List[ConferenceTrainingWorkshop]] = Field(
        default_factory=list, alias="conferences_trainings_workshops"
    )
    awards: Optional[List[Award]] = Field(default_factory=list, alias="awards")
    extracurricular_activities: Optional[List[ExtracurricularActivity]] = Field(
        default_factory=list, alias="extracurricular_activities"
    )
    languages: Optional[List[Language]] = Field(default_factory=list, alias="languages")
    summary: Optional[str] = Field(None, alias="summary")
    extracted_keywords: List[str] = Field(
        default_factory=list, alias="extracted_keywords"
    )

    class ConfigDict:
        validate_by_name = True
        str_strip_whitespace = True
        populate_by_name = True
