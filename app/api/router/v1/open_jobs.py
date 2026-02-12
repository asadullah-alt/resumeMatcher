from typing import List
from fastapi import APIRouter, status
from app.models.job import Job
from pydantic import BaseModel

router = APIRouter()

class BatchJobResponse(BaseModel):
    inserted_count: int
    skipped_count: int
    message: str

@router.post("/", response_model=BatchJobResponse, status_code=status.HTTP_201_CREATED)
async def create_open_jobs(jobs: List[Job]):
    """
    Batch insert jobs if they don't already exist with public=True.
    """
    inserted_count = 0
    skipped_count = 0

    for job_data in jobs:
        # Check if job already exists with public=True
        existing_job = await Job.find_one({"job_url": job_data.job_url, "public": True})
        
        if existing_job:
            skipped_count += 1
            continue
        
        # If it doesn't exist, we insert it. 
        # Note: We need to exclude 'id' from the job_data if it's provided, 
        # but since Job is a List[Job] from request, beanie handles it.
        # However, we want to make sure we don't accidentally overwrite or use an old ID.
        # Beanie's Document.insert() will create a new one if id is None.
        
        new_job = Job(
            job_url=job_data.job_url,
            user_id=job_data.user_id,
            job_id=job_data.job_id,
            content=job_data.content,
            raw_content=job_data.raw_content,
            public=job_data.public
        )
        await new_job.insert()
        inserted_count += 1

    return BatchJobResponse(
        inserted_count=inserted_count,
        skipped_count=skipped_count,
        message=f"Successfully processed batch. Inserted: {inserted_count}, Skipped: {skipped_count}"
    )
