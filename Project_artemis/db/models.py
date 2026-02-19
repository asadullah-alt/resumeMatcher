from datetime import datetime
from typing import Optional, List
from beanie import Document
from pydantic import Field, BaseModel
import enum

class EmploymentTypeEnum(str, enum.Enum):
    FULL_TIME = "Full-time"
    FULL_TIME_NO_DASH = "Full time"
    PART_TIME = "Part-time"
    PART_TIME_NO_DASH = "Part time"
    CONTRACT = "Contract"
    INTERNSHIP = "Internship"
    TEMPORARY = "Temporary"
    NOT_SPECIFIED = "Not Specified"

class RemoteStatusEnum(str, enum.Enum):
    FULLY_REMOTE = "Fully Remote"
    HYBRID = "Hybrid"
    ON_SITE = "On-site"
    REMOTE = "Remote"
    NOT_SPECIFIED = "Not Specified"
    MULTIPLE_LOCATIONS = "Multiple Locations"

class CompanyProfile(BaseModel):
    companyName: str = Field(..., alias="companyName")
    industry: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None

    class Config:
        populate_by_name = True

class Location(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    remote_status: RemoteStatusEnum = Field(..., alias="remoteStatus")

    class Config:
        populate_by_name = True

class Qualifications(BaseModel):
    required: List[str]
    preferred: Optional[List[str]] = None

class CompensationAndBenefits(BaseModel):
    salary_range: Optional[str] = Field(None, alias="salaryRange")
    benefits: Optional[List[str]] = None

    class Config:
        populate_by_name = True

class ApplicationInfo(BaseModel):
    how_to_apply: Optional[str] = Field(None, alias="howToApply")
    apply_link: Optional[str] = Field(None, alias="applyLink")
    contact_email: Optional[str] = Field(None, alias="contactEmail")

    class Config:
        populate_by_name = True

class Job(Document):
    job_url: str
    user_id: str
    job_id: str
    content: str
    raw_content: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    public: bool = False

    class Settings:
        name = "Job"

class ProcessedOpenJobs(Document):
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
    
    analyzed: bool = False
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "ProcessedOpenJobs"
