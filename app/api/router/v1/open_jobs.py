import asyncio
import logging
import traceback
from typing import List
from fastapi import APIRouter, status, Header, HTTPException, Depends
from app.models.job import Job, ProcessedOpenJobs
from job_processor.models.job import OpenJobsVector, UserJobMatch
from app.services.open_job_service import OpenJobService
from pydantic import BaseModel
from app.models.user import User

logger = logging.getLogger(__name__)


async def _run_processor_after_delay(job_pairs: list):
    """
    Background task: waits 60 seconds then runs JobProcessor on each
    (source_job, processed_job) pair. Runs in the FastAPI event loop so
    no extra DB connection is needed.
    """
    logger.info(
        f"JobProcessor scheduled: waiting 60s before processing {len(job_pairs)} job(s)..."
    )
    await asyncio.sleep(60)

    from job_processor.services.processor import JobProcessor
    processor = JobProcessor()

    for source_job, processed_job in job_pairs:
        try:
            logger.info(f"[Job {source_job.job_id}] Starting JobProcessor pipeline")
            await processor.process_new_job(source_job, processed_job)
        except Exception as e:
            logger.error(
                f"[Job {source_job.job_id}] JobProcessor failed: {e}\n{traceback.format_exc()}"
            )

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
    # Pairs collected for background processing: (Job, ProcessedOpenJobs)
    jobs_to_process: list = []

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
                jobs_to_process.append((new_job, processed_job))
        except Exception as e:
            # We log the error but don't fail the whole request
            logger.error(f"Error processing open job {new_job.job_id}: {e}\n{traceback.format_exc()}")

        inserted_count += 1

    # Fire background task: wait 60s then run JobProcessor for all newly inserted jobs
    if jobs_to_process:
        asyncio.create_task(_run_processor_after_delay(jobs_to_process))
        logger.info(
            f"Background JobProcessor task queued for {len(jobs_to_process)} job(s) "
            f"(will run after 60s delay)"
        )

    return BatchJobResponse(
        inserted_count=inserted_count,
        skipped_count=skipped_count,
        processed_jobs=processed_jobs,
        message=f"Successfully processed batch. Inserted: {inserted_count}, Skipped: {skipped_count}"
    )

from app.models.resume import ProcessedResume

@router.post("/resumes/process/user", status_code=status.HTTP_200_OK)
async def process_user_resume(
    email: str, 
    overwrite: bool = False, 
    admin: User = Depends(get_admin_user)
):
    """
    Triggers the vectorization pipeline for a specific user's default resume.
    """
    user = await User.find_one({"local.email": email})
    if not user:
        raise HTTPException(status_code=404, detail=f"User with email {email} not found")

    resume = await ProcessedResume.find_one({"user_id": str(user.id), "default": True})
    if not resume:
        raise HTTPException(status_code=404, detail=f"No default ProcessedResume found for user {email}")

    from job_processor.services.processor import JobProcessor
    processor = JobProcessor()
    
    try:
        await processor._process_new_resume(resume, overwrite=overwrite)
        return {"message": f"Successfully triggered processing for {email}'s default resume."}
    except Exception as e:
        logger.error(f"Failed to process resume for {email}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal processing error: {str(e)}")

@router.post("/resumes/process/all", status_code=status.HTTP_200_OK)
async def process_all_user_resumes(
    overwrite: bool = False, 
    admin: User = Depends(get_admin_user)
):
    """
    Iterates through all users and triggers the vectorization pipeline 
    for their default ProcessedResumes one-by-one.
    """
    from job_processor.services.processor import JobProcessor
    processor = JobProcessor()
    
    users = await User.find_all().to_list()
    processed_count = 0
    errors = []

    for user in users:
        resume = await ProcessedResume.find_one({"user_id": str(user.id), "default": True})
        if resume:
            try:
                await processor._process_new_resume(resume, overwrite=overwrite)
                processed_count += 1
            except Exception as e:
                logger.error(f"Failed to process resume for {user.id}: {e}")
                errors.append(str(user.id))

    return {
        "message": f"Batch process completed. Processed: {processed_count}, Errors: {len(errors)}",
        "error_user_ids": errors
    }

@router.post("/match/user", status_code=status.HTTP_200_OK)
async def match_user_to_jobs(
    email: str, 
    admin: User = Depends(get_admin_user)
):
    """
    Matches the user's default resume vectors against existing open job vectors.
    Saves the match percentages to UserJobMatch collection.
    """
    user = await User.find_one({"local.email": email})
    if not user:
        raise HTTPException(status_code=404, detail=f"User with email {email} not found")

    user_id = str(user.id)
    from job_processor.services.processor import JobProcessor
    processor = JobProcessor()
    
    try:
        matches = await processor.match_user_resumes_to_jobs(user_id)
        if matches is None:
             raise HTTPException(status_code=404, detail=f"No default resume or vectors found for user {email}.")
             
        return {
            "message": f"Successfully matched user {email} with jobs.",
            "match_count": len(matches),
            "matches": matches
        }
    except Exception as e:
        logger.error(f"Failed to match user {email} with jobs: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal matching error: {str(e)}")

@router.get("/vectors", response_model=List[OpenJobsVector], status_code=status.HTTP_200_OK)
async def get_open_jobs_vectors(admin: User = Depends(get_admin_user)):
    """
    Returns all OpenJobsVector documents.
    Requires X-Admin-Email and X-Admin-Token headers.
    """
    vectors = await OpenJobsVector.find_all().to_list()
    return vectors
