from __future__ import annotations
import enum
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict, Any
from beanie import Document
from pydantic import Field, BaseModel, ConfigDict

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
        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower == "string": return cls.NOT_SPECIFIED
            mapping = {member.value.lower(): member for member in cls}
            if value_lower in mapping: return mapping[value_lower]
        return cls.NOT_SPECIFIED

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
        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower == "string": return cls.NOT_SPECIFIED
            mapping = {member.value.lower(): member for member in cls}
            if value_lower in mapping: return mapping[value_lower]
        return cls.NOT_SPECIFIED

class CompanyProfile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    companyName: str = Field(..., alias="companyName")
    industry: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None

class Location(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    remote_status: RemoteStatusEnum = Field(..., alias="remoteStatus")

class Qualifications(BaseModel):
    required: List[str]
    preferred: Optional[List[str]] = None

class CompensationAndBenefits(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    salary_range: Optional[str] = Field(None, alias="salaryRange")
    benefits: Optional[List[str]] = None

class ApplicationInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    how_to_apply: Optional[str] = Field(None, alias="howToApply")
    apply_link: Optional[str] = Field(None, alias="applyLink")
    contact_email: Optional[str] = Field(None, alias="contactEmail")

class ProcessedOpenJobs(Document):
    """Document for storing processed open job postings."""
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
    compensation_and_benefits: Optional[CompensationAndBenefits] = Field(None, alias="compensationAndBenefits")
    application_info: Optional[ApplicationInfo] = Field(None, alias="applicationInfo")
    extracted_keywords: Optional[List[str]] = Field(None, alias="extractedKeywords")
    is_visa_sponsored: Optional[bool] = Field(None, alias="isVisaSponsored")
    is_remote: Optional[bool] = Field(None, alias="isRemote")

    # Vector fields
    flattened_description: Optional[str] = None
    full_job_vector_sparse: Optional[Dict[str, Any]] = None
    full_job_vector_dense: Optional[List[float]] = None
    skills: Optional[List[Dict[str, Any]]] = None

    # Extra functionality
    analyzed: bool = False
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(days=30))
   
    # Metadata fields
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "ProcessedOpenJobs"
        indexes = [
            "user_id",
            "job_id",
            "employment_type",
            "date_posted",
            "processed_at",
            [("expires_at", 1)], # TTL index should be managed by Mongo, but Beanie can hint
        ]

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
        str_strip_whitespace=True
    )

class Job(Document):
    """The source collection we watch for inserts."""
    job_url: str
    user_id: str
    job_id: str
    content: str
    raw_content: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    public: bool = False

    class Settings:
        name = "Job"

class OpenJobsVector(Document):
    """Stores vector data and metadata for processed jobs."""
    job_id: str
    dense_vector: List[float]
    sparse_vector: Dict[str, Any]
    job_description: str
    metadata: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "OpenJobsVector"
        indexes = [
            "job_id",
            "created_at"
        ]

class UserJobMatch(Document):
    """Stores the match result between a user's resume and an open job."""
    user_id: str
    job_id: str
    job_url: Optional[str] = None
    percentage_match: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "UserJobMatch"
        indexes = [
            "user_id",
            "job_id",
            "created_at"
        ]
