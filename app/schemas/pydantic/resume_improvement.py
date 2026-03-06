from uuid import UUID
from pydantic import BaseModel, Field


class ResumeImprovementRequest(BaseModel):
    job_id: UUID = Field(..., description="DB UUID reference to the job")
    resume_id: UUID = Field(..., description="DB UUID reference to the resume")
    analysis_again: bool = Field(
        False, description="Optional DB UUID reference to a prior analysis"
    )
    token: str = Field(..., description="User Token")


class OpenJobImprovementRequest(BaseModel):
    match_id: str = Field(..., description="UserJobMatch document _id to resolve job_id from")
    resume_id: UUID = Field(..., description="DB UUID reference to the resume")
    analysis_again: bool = Field(
        False, description="Whether to force re-analysis"
    )
    token: str = Field(..., description="User Token")