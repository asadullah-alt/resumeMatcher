from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from beanie import Document
from datetime import datetime
from typing import Optional, List
import enum
from pydantic import Field, BaseModel


class EmploymentTypeEnum(str, enum.Enum):
    """Case-insensitive Enum for employment types."""

    FULL_TIME = "Full-time"
    FULL_TIME_NO_DASH = "Full time"
    PART_TIME = "Part-time"
    PART_TIME_NO_DASH = "Part time"
    CONTRACT = "Contract"
    INTERNSHIP = "Internship"
    TEMPORARY = "Temporary"
    NOT_SPECIFIED = "Not Specified"

    @classmethod
    def _missing_(cls, value: object):
        """Handles case-insensitive lookup."""
        if isinstance(value, str):
            if value.lower() == "string":
                return cls.NOT_SPECIFIED
            
            value_lower = value.lower()
            mapping = {member.value.lower(): member for member in cls}
            if value_lower in mapping:
                return mapping[value_lower]

        raise ValueError(
            "employment type must be one of: Full-time, Full time, Part-time, Part time, Contract, Internship, Temporary, Not Specified (case insensitive)"
        )


class RemoteStatusEnum(str, enum.Enum):
    """Case-insensitive Enum for remote work status."""

    FULLY_REMOTE = "Fully Remote"
    HYBRID = "Hybrid"
    ON_SITE = "On-site"
    REMOTE = "Remote"
    NOT_SPECIFIED = "Not Specified"
    MULTIPLE_LOCATIONS = "Multiple Locations"

    @classmethod
    def _missing_(cls, value: object):
        """Handles case-insensitive lookup."""
        if isinstance(value, str):
            if value.lower() == "string":
                return cls.NOT_SPECIFIED
            
            value_lower = value.lower()
            mapping = {member.value.lower(): member for member in cls}
            if value_lower in mapping:
                return mapping[value_lower]

        raise ValueError(
            "remote_status must be one of: Fully Remote, Hybrid, On-site, Remote, Not Specified, Multiple Locations (case insensitive)"
        )


class CompanyProfile(BaseModel):
    """Embedded company profile information."""
    companyName: str = Field(..., alias="companyName")
    industry: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None

    class Config:
        populate_by_name = True


class Location(BaseModel):
    """Embedded location information."""
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    remote_status: RemoteStatusEnum = Field(..., alias="remoteStatus")

    class Config:
        populate_by_name = True


class Qualifications(BaseModel):
    """Embedded qualifications information."""
    required: List[str]
    preferred: Optional[List[str]] = None


class CompensationAndBenefits(BaseModel):
    """Embedded compensation and benefits information."""
    salary_range: Optional[str] = Field(None, alias="salaryRange")
    benefits: Optional[List[str]] = None

    class Config:
        populate_by_name = True


class ApplicationInfo(BaseModel):
    """Embedded application information."""
    how_to_apply: Optional[str] = Field(None, alias="howToApply")
    apply_link: Optional[str] = Field(None, alias="applyLink")
    contact_email: Optional[str] = Field(None, alias="contactEmail")

    class Config:
        populate_by_name = True


class ProcessedJob(Document):
    """Main document for storing processed job postings."""
    job_url: str
    user_id: str
    job_id: str
    job_title: Optional[str] = Field(None, alias="jobTitle")
    company_profile: Optional[CompanyProfile] = Field(None, alias="companyProfile")
    location: Optional[Location] = None
    date_posted: Optional[str] = Field(None, alias="datePosted")
    employment_type: Optional[EmploymentTypeEnum] = Field(None, alias="employmentType")
    job_summary: Optional[str] = Field(None, alias="jobSummary")
    key_responsibilities: Optional[List[str]] = Field(None, alias="keyResponsibilities")
    qualifications: Optional[Qualifications] = None
    compensation_and_benefits: Optional[CompensationAndBenefits] = Field(
        None, alias="compensationAndBenefits"
    )
    application_info: Optional[ApplicationInfo] = Field(None, alias="applicationInfo")
    extracted_keywords: Optional[List[str]] = Field(None, alias="extractedKeywords")
    is_visa_sponsored: Optional[bool] = Field(None, alias="isVisaSponsored")
    is_remote: Optional[bool] = Field(None, alias="isRemote")
    
    # Metadata fields
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "ProcessedJob"
        indexes = [
            "user_id",
            "job_id",
            [("user_id", 1), ("job_id", 1)],  # Compound index for user_id + job_id
            "employment_type",
            "date_posted",
            "processed_at",
        ]

    class Config:
        use_enum_values = True
        populate_by_name = True
        str_strip_whitespace = True

class Job(Document):
    job_url: str
    user_id: str
    job_id: str
    content: str
    raw_content: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    public: bool = False

