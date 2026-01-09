from pydantic import BaseModel, Field

class SetDefaultResumeRequest(BaseModel):
    token: str = Field(..., description="User authentication token")
    resume_id: str = Field(..., description="ID of the resume to set as default")
