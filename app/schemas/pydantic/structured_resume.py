from typing import List, Optional
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


class StructuredResumeModel(BaseModel):
    personal_data: PersonalData = Field(..., alias="personal_data")
    experiences: List[Experience] = Field(default_factory=list, alias="experiences")
    projects: Optional[List[Project]] = Field(default_factory=list, alias="projects")
    skills: Optional[List[Skill]] = Field(default_factory=list, alias="skills")
    research_work: Optional[List[ResearchWork]] = Field(
        default_factory=list, alias="research_work"
    )
    achievements: Optional[List[str]] = Field(default_factory=list, alias="achievements")
    education: List[Education] = Field(default_factory=list, alias="education")
    summary: Optional[str] = Field(None, alias="summary")
    extracted_keywords: List[str] = Field(
        default_factory=list, alias="extracted_keywords"
    )

    class ConfigDict:
        validate_by_name = True
        str_strip_whitespace = True
        populate_by_name = True
