from datetime import datetime, UTC
from typing import Optional, List
import enum
from beanie import Document
from pydantic import Field, BaseModel

# Import unified models from job_processor to prevent CollectionWasNotInitialized error
from job_processor.models.job import (
    Job,
    ProcessedOpenJobs,
    EmploymentTypeEnum,
    RemoteStatusEnum,
    CompanyProfile,
    Location,
    Qualifications,
    CompensationAndBenefits,
    ApplicationInfo
)

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
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

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

