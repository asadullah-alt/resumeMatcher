from uuid import UUID
from typing import List
from pydantic import BaseModel, Field


class JobUploadRequest(BaseModel):
    job_descriptions: str
    job_url: str
    token: str


class JobGetRequest(BaseModel):
    job_url: str
