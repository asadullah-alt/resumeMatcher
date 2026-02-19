from typing import List
from fastapi import APIRouter, status, Header, HTTPException, Depends
from app.models.job import Job, ProcessedOpenJobs
from app.services.open_job_service import OpenJobService
from pydantic import BaseModel
from app.models.user import User

router = APIRouter()

class BatchJobResponse(BaseModel):
    inserted_count: int
    skipped_count: int
    processed_jobs: List[ProcessedOpenJobs]
    message: str

async def get_admin_user(
    x_admin_email: str = Header(..., alias="X-Admin-Email"),
    x_admin_token: str = Header(..., alias="X-Admin-Token")
):
    # Requirement: only authenticates if local.email is 'asadullahbeg@gmail.com' 
    # and token is the one in local.token for that user
    if x_admin_email != "asadullahbeg@gmail.com":
        raise HTTPException(status_code=403, detail="Unauthorized: Only asadullahbeg can access this API.")
    
    admin = await User.find_one({"local.email": "asadullahbeg@gmail.com"})
    if not admin or not admin.local or admin.local.token != x_admin_token:
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid token or user not found.")
    
    return admin

@router.post("/", response_model=BatchJobResponse, status_code=status.HTTP_201_CREATED)
async def create_open_jobs(jobs: List[Job], admin: User = Depends(get_admin_user)):
    """
    Batch insert jobs if they don't already exist with public=True.
    """
    inserted_count = 0
    skipped_count = 0
    processed_jobs = []

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
            raw_content=job_data.content,
            public=job_data.public
        )
        await new_job.insert()
        
        # Process the job using the new service
        try:
            open_job_service = OpenJobService()
            processed_job = await open_job_service.run(
                job_id=new_job.job_id,
                user_id=new_job.user_id,
                content=new_job.content,
                job_url=new_job.job_url
            )
            if processed_job:
                processed_jobs.append(processed_job)
        except Exception as e:
            # We log the error but don't fail the whole request
            import logging
            logging.getLogger(__name__).error(f"Error processing open job {new_job.job_id}: {e}")
            
        inserted_count += 1

    return BatchJobResponse(
        inserted_count=inserted_count,
        skipped_count=skipped_count,
        processed_jobs=processed_jobs,
        message=f"Successfully processed batch. Inserted: {inserted_count}, Skipped: {skipped_count}"
    )
