from pydantic import BaseModel, Field

class ExtensionImprovementRequest(BaseModel):
    resume_id: str = Field(..., description="Resume ID")
    job_url: str = Field(..., description="Job URL")
    token: str = Field(..., description="User Token")
