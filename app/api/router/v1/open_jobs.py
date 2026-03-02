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
from app.models.resume import Resume, ProcessedResume
from app.services import ResumeService
from app.services.billing_service import BillingService
from app.core import get_db_session

logger = logging.getLogger(__name__)


async def _run_processor_after_delay(job_pairs: list, delay: int = 60):
    """
    Background task: waits 'delay' seconds then runs JobProcessor on each
    (source_job, processed_job) pair. Runs in the FastAPI event loop so
    no extra DB connection is needed.
    """
    if delay > 0:
        logger.info(
            f"JobProcessor scheduled: waiting {delay}s before processing {len(job_pairs)} job(s)..."
        )
        await asyncio.sleep(delay)
    else:
        logger.info(f"JobProcessor starting immediately for {len(job_pairs)} job(s)...")

    from job_processor.services.processor import JobProcessor
    # We'll initialize a fresh processor per job in the loop below to handle mixed user_ids


    for source_job, processed_job in job_pairs:
        try:
            logger.info(f"[Job {source_job.job_id}] Starting JobProcessor pipeline")
            processor = JobProcessor(user_id=source_job.user_id)
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

class EnrichedMatch(BaseModel):
    match: UserJobMatch
    job_details: ProcessedOpenJobs

async def get_admin_user(
    x_admin_email: str = Header(..., alias="X-Admin-Email"),
    x_admin_token: str = Header(..., alias="X-Admin-Token")
):
    # Requirement: only authenticates if local.email is 'asadullahbeg@gmail.com' 
    # and token is the one in local.token for that user
    if x_admin_email != "asadullahbeg@gmail.com":
        raise HTTPException(status_code=403, detail="Unauthorized: Only asadullahbeg can access this API.")
    
    admin = await User.find_one({
        "$or": [
            {"local.email": "asadullahbeg@gmail.com"},
            {"google.email": "asadullahbeg@gmail.com"}
        ]
    })
    
    if not admin:
        raise HTTPException(status_code=403, detail="Unauthorized: User not found.")
        
    # Check if the token matches either local or google token
    is_valid_token = False
    if admin.local and admin.local.token == x_admin_token:
        is_valid_token = True
    elif admin.google and admin.google.token == x_admin_token:
        is_valid_token = True
        
    if not is_valid_token:
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid token.")
    
    return admin

@router.post("/", response_model=BatchJobResponse, status_code=status.HTTP_201_CREATED)
async def create_open_jobs(jobs: List[Job], admin: User = Depends(get_admin_user)):
    """
    Batch insert jobs if they don't already exist with public=True.
    """
    logger.info(f"--- [create_open_jobs] Batch processing started for {len(jobs)} jobs ---")
    inserted_count = 0
    skipped_count = 0
    processed_jobs = []
    # Pairs collected for background processing: (Job, ProcessedOpenJobs)
    jobs_to_process: list = []

    for job_data in jobs:
        logger.info(f"[Job Process] Handling job_id: {job_data.job_id} | url: {job_data.job_url}")
        
        # Check if job already exists with public=True
        existing_job = await Job.find_one({"job_url": job_data.job_url, "public": True})
        
        if existing_job:
            logger.info(f"  -> Skipping: Job already exists with public=True (id: {existing_job.job_id})")
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
        logger.info(f"  -> Inserted into 'Job' collection. Beanie ID: {new_job.id}")
        
        # Process the job using the new service
        try:
            logger.info(f"  -> Initializing OpenJobService for user_id: {new_job.user_id}")
            open_job_service = OpenJobService(user_id=new_job.user_id)
            
            logger.info(f"  -> Running extraction pipeline for job: {new_job.job_id}")
            processed_job = await open_job_service.run(
                job_id=new_job.job_id,
                user_id=new_job.user_id,
                content=new_job.content,
                job_url=new_job.job_url
            )
            
            if processed_job:
                logger.info(f"  -> Extraction successful. Job title: {processed_job.job_title}")
                processed_jobs.append(processed_job)
                jobs_to_process.append((new_job, processed_job))
            else:
                logger.warning(f"  -> Extraction returned None for job: {new_job.job_id}")

        except Exception as e:
            # We log the error but don't fail the whole request
            logger.error(f"  -> [CRITICAL] Failed to process open job {new_job.job_id}: {e}\n{traceback.format_exc()}")

        inserted_count += 1

    # Fire background task: wait 60s then run JobProcessor for all newly inserted jobs
    if jobs_to_process:
        # Separate extension jobs for immediate processing
        immediate_jobs = [(s, p) for s, p in jobs_to_process if s.user_id == "extension"]
        delayed_jobs = [(s, p) for s, p in jobs_to_process if s.user_id != "extension"]
        
        if immediate_jobs:
            asyncio.create_task(_run_processor_after_delay(immediate_jobs, delay=0))
            logger.info(f"--- [create_open_jobs] Immediate JobProcessor task queued for {len(immediate_jobs)} extension job(s) ---")
            
        if delayed_jobs:
            asyncio.create_task(_run_processor_after_delay(delayed_jobs, delay=60))
            logger.info(
                f"--- [create_open_jobs] Delayed JobProcessor task queued for {len(delayed_jobs)} job(s) ---"
                f" (will run after 60s delay)"
            )
    else:
        logger.info("--- [create_open_jobs] No new jobs to queue for JobProcessor background task. ---")

    logger.info(f"--- [create_open_jobs] Finished. Inserted: {inserted_count}, Skipped: {skipped_count} ---")
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
    user = await User.find_one({
        "$or": [
            {"local.email": email},
            {"google.email": email}
        ]
    })
    if not user:
        raise HTTPException(status_code=404, detail=f"User with email {email} not found")

    resume = await ProcessedResume.find_one({"user_id": str(user.id), "default": True})
    if not resume:
        raise HTTPException(status_code=404, detail=f"No default ProcessedResume found for user {email}")

    from job_processor.services.processor import JobProcessor
    processor = JobProcessor(user_id=str(user.id))
    
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
    # Will initialize per-user inside the loop for correctness, though usually not needed for "all"

    
    users = await User.find_all().to_list()
    processed_count = 0
    errors = []

    for user in users:
        resume = await ProcessedResume.find_one({"user_id": str(user.id), "default": True})
        if resume:
            try:
                processor = JobProcessor(user_id=str(user.id))
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
    overwrite: bool = False,
    admin: User = Depends(get_admin_user)
):
    """
    Matches the user's default resume vectors against existing open job vectors.
    Saves the match percentages to UserJobMatch collection.
    """
    user = await User.find_one({
        "$or": [
            {"local.email": email},
            {"google.email": email}
        ]
    })
    if not user:
        raise HTTPException(status_code=404, detail=f"User with email {email} not found")

    user_id = str(user.id)
    from job_processor.services.processor import JobProcessor
    processor = JobProcessor(user_id=user_id)
    
    try:
        matches = await processor.match_user_resumes_to_jobs(user_id, overwrite=overwrite)
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

@router.get("/matches/enriched", response_model=List[EnrichedMatch], status_code=status.HTTP_200_OK)
async def get_enriched_matches(
    x_user_token: str = Header(..., alias="X-User-Token")
):
    """
    Returns enriched match results for the user identified by the provided token.
    Only matches with percentage_match > 30 are returned.
    If no matches are found, triggers the matching engine.
    """
    billing_service = BillingService()
    user = await billing_service.get_user_by_token(x_user_token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid user token."
        )
    
    user_id = str(user.id)
    
    # 1. Initial lookup for matches > 30
    matches = await UserJobMatch.find(
        UserJobMatch.user_id == user_id,
        UserJobMatch.percentage_match > 30
    ).to_list()
    
    # 2. If no matches found, trigger processor
    if not matches:
        logger.info(f"No matches > 30% found for user {user_id}. Triggering matching engine.")
        from job_processor.services.processor import JobProcessor
        processor = JobProcessor(user_id=user_id)
        try:
            # Run matching
            await processor.match_user_resumes_to_jobs(user_id)
            
            # Re-fetch matches
            matches = await UserJobMatch.find(
                UserJobMatch.user_id == user_id,
                UserJobMatch.percentage_match > 30
            ).to_list()
        except Exception as e:
            logger.error(f"Failed to trigger matching for user {user_id}: {e}")
            # We still want to return empty or whatever matches were found if any errors occurred
    
    user_country = (user.country or "").strip().lower()

    enriched_results = []
    for match in matches:
        # Join with ProcessedOpenJobs
        job_details = await ProcessedOpenJobs.find_one(
            ProcessedOpenJobs.job_id == match.job_id
        )
        if not job_details:
            continue

        # Filter by country if the user has a country preference set
        if user_country:
            job_country = ""
            if job_details.location and job_details.location.country:
                job_country = job_details.location.country.strip().lower()
            if job_country != user_country:
                continue

        enriched_results.append(EnrichedMatch(
            match=match,
            job_details=job_details
        ))
            
    return enriched_results

@router.get("/details/{job_id}", response_model=ProcessedOpenJobs, status_code=status.HTTP_200_OK)
async def get_job_details(
    job_id: str,
    x_user_token: str = Header(..., alias="X-User-Token")
):
    """
    Returns the details of a processed job identified by job_id.
    Requires user validation via token.
    """
    billing_service = BillingService()
    user = await billing_service.get_user_by_token(x_user_token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid user token."
        )
    
    job_details = await ProcessedOpenJobs.find_one(
        ProcessedOpenJobs.job_id == job_id
    )
    
    if not job_details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found."
        )
        
    return job_details

@router.post("/resumes/process/raw/{resume_id}", status_code=status.HTTP_200_OK)
async def process_raw_resume(
    resume_id: str,
    admin: User = Depends(get_admin_user),
    db: Any = Depends(get_db_session)
):
    """
    Fetches raw resume content from the Resume collection and triggers 
    the extraction pipeline to create a ProcessedResume.
    """
    logger.info(f"--- [process_raw_resume] Manual processing request for resume_id: {resume_id} ---")
    
    resume = await Resume.find_one(Resume.resume_id == resume_id)
    if not resume:
        logger.error(f"  -> Resume not found: {resume_id}")
        raise HTTPException(status_code=404, detail=f"Resume with id {resume_id} not found in Resume collection.")

    # Check if ProcessedResume already exists
    existing_processed = await ProcessedResume.find_one(ProcessedResume.resume_id == resume_id)
    if existing_processed:
        logger.info(f"  -> Skipping: ProcessedResume already exists for {resume_id}")
        return {"message": f"ProcessedResume already exists for resume {resume_id}. Skipping processing."}

    try:
        resume_service = ResumeService(db)
        logger.info(f"  -> Triggering extraction for resume: {resume_id} (user_id: {resume.user_id})")
        
        success = await resume_service._extract_and_store_structured_resume(
            resume_id=resume.resume_id,
            resume_text=resume.content,
            user_id=resume.user_id,
            resume_name=resume.resume_name
        )
        
        if success:
            logger.info(f"  -> Successfully created ProcessedResume for {resume_id}")
            return {"message": f"Successfully processed raw resume {resume_id}."}
        else:
            logger.error(f"  -> Extraction failed for resume: {resume_id}")
            raise HTTPException(status_code=500, detail="Extraction failed. Resume might be invalid or incomplete.")
            
    except Exception as e:
        logger.error(f"  -> [CRITICAL] Error processing raw resume {resume_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal processing error: {str(e)}")

