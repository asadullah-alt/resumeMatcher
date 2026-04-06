import asyncio
import logging
import traceback
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Any

from fastapi import APIRouter, status, Header, HTTPException, Depends
from bs4 import BeautifulSoup
from app.models.job import Job, ProcessedOpenJobs
from job_processor.models.job import OpenJobsVector, UserJobMatch
from app.services.open_job_service import OpenJobService
from app.services.email_service import EmailService
from pydantic import BaseModel, Field

class SingleMatchRequest(BaseModel):
    model_config = {"populate_by_name": True}
    email: str
    job_url: str = Field(..., alias="jobUrl")

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

def clean_html_body(html_string: str) -> str:
    """
    Cleans raw HTML into plain text with consistent spacing.
    Migrated from OpenJobService to ensure cleaning happens before DB insertion.
    """
    try:
        soup = BeautifulSoup(html_string, 'html.parser')

        # Scope to Body if present
        body_tag = soup.find('body')
        target_content = body_tag if body_tag else soup
        
        # Tags that represent paragraph or sections
        MAJOR_BLOCK_TAGS = [
            'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
            'div', 'section', 'article', 'aside', 'main', 'nav', 'header', 'footer',
            'li', 'ul', 'ol', 'blockquote', 'table', 'tr', 'form', 
            'fieldset', 'legend', 'dt', 'dd', 'address', 'pre'
        ]
        
        # Remove unwanted tags
        tags_to_remove_completely = ['script', 'svg', 'iframe', 'style', 'a', 'code']
        for tag_name in tags_to_remove_completely:
            for tag in target_content.find_all(tag_name):
                tag.extract()
                
        # Insert spacing for blocks
        for tag_name in MAJOR_BLOCK_TAGS:
            for tag in target_content.find_all(tag_name):
                tag.insert_before('\n\n')
                if tag_name not in ['li', 'tr', 'dt', 'dd']:
                    tag.append('\n\n')

        # Handle line breaks
        for br_tag in target_content.find_all('br'):
            br_tag.replace_with('\n')

        text_content = target_content.get_text(strip=False)
        
        # Post-processing
        text_content = text_content.replace('\\n', '\n')
        text_content = text_content.replace('\r\n', '\n').replace('\r', '\n')
        
        lines = text_content.split('\n')
        cleaned_lines = [line.strip() for line in lines if line.strip()]
        return '\n'.join(cleaned_lines)

    except Exception as e:
        logger.error(f"Error cleaning HTML: {e}")
        return html_string # Return raw if cleaning fails

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
        # Generate a unique job_id based on current time
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        unique_suffix = secrets.token_hex(4)
        job_data.job_id = f"{timestamp}-{unique_suffix}"

        logger.info(f"[Job Process] Generated unique job_id: {job_data.job_id} | url: {job_data.job_url}")

        
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
        
        # If sourced from extension, clean the content before saving
        job_content = job_data.content
        if job_data.user_id == "extension":
            logger.info(f"  -> Cleaning HTML content for extension job: {job_data.job_id}")
            job_content = clean_html_body(job_content)

        new_job = Job(
            job_url=job_data.job_url,
            user_id=job_data.user_id,
            job_id=job_data.job_id,
            content=job_content,
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

@router.post("/users/profile/sync", status_code=status.HTTP_200_OK)
async def sync_user_profile(
    email: str,
    admin: User = Depends(get_admin_user),
    db: Any = Depends(get_db_session)
):
    """
    Syncs a user's city and experience from their default resume.
    """
    user = await User.find_one({
        "$or": [
            {"local.email": email},
            {"google.email": email},
            {"linkedin.email": email}
        ]
    })
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    resume_service = ResumeService(db=db)
    success = await resume_service.sync_user_profile_with_default_resume(str(user.id))
    
    if not success:
         raise HTTPException(status_code=400, detail="Failed to sync profile (maybe no default resume?)")
         
    return {"message": f"Successfully synced profile for {email}"}

@router.post("/users/profile/sync-all", status_code=status.HTTP_200_OK)
async def sync_all_user_profiles(
    admin: User = Depends(get_admin_user),
    db: Any = Depends(get_db_session)
):
    """
    Syncs all users' city and experience from their default resumes.
    """
    users = await User.find_all().to_list()
    resume_service = ResumeService(db=db)
    
    synced_count = 0
    for user in users:
        success = await resume_service.sync_user_profile_with_default_resume(str(user.id))
        if success:
            synced_count += 1
            
    return {"message": f"Successfully synced {synced_count} user profiles"}

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

@router.post("/match/single", status_code=status.HTTP_200_OK)
async def match_single_job(
    request: SingleMatchRequest,
    admin: User = Depends(get_admin_user)
):
    """
    Calculates the match percentage for a specific job URL and user email.
    """
    email = request.email
    job_url = request.job_url
    
    logger.info(f"--- [match_single_job] Request for email: {email}, job_url: {job_url} ---")
    
    user = await User.find_one({
        "$or": [
            {"local.email": email},
            {"google.email": email}
        ]
    })
    
    if not user:
        logger.error(f"  -> User not found: {email}")
        raise HTTPException(status_code=404, detail=f"User with email {email} not found")

    user_id = str(user.id)
    from job_processor.services.processor import JobProcessor
    processor = JobProcessor(user_id=user_id)
    
    try:
        match_percentage = await processor.calculate_single_match(job_url, user_id)
        
        # Extract username
        username = None
        if user.google:
            username = user.google.name
        elif user.facebook:
            username = user.facebook.name
        elif user.linkedin:
            username = user.linkedin.name
        
        if not username and email:
            username = email.split("@")[0]
            
        return {
            "message": "Successfully calculated match percentage.",
            "email": email,
            "username": username,
            "job_url": job_url,
            "match_percentage": match_percentage
        }
    except Exception as e:
        logger.error(f"  -> [CRITICAL] Error calculating single match: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal matching error: {str(e)}")

@router.get("/vectors/weighted-count", status_code=status.HTTP_200_OK)
async def get_weighted_vector_count():
    """
    Returns the total number of open_jobs_vectors multiplied by 1000.
    """
    count = await OpenJobsVector.count()
    weighted_count = count * 1000
    
    return {
        "total_vectors": count,
        "weighted_count": weighted_count
    }

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
    matches = []
    
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
    user_city = (user.city or "").strip().lower()

    enriched_results = []
    for match in matches:
        # Join with ProcessedOpenJobs
        job_details = await ProcessedOpenJobs.find_one(
            ProcessedOpenJobs.job_id == match.job_id
        )
        
        if not job_details:
            continue

        # Filter logic (no older than 20 days, must have posted date, must have company name)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=20)
        
        # 1. Age check
        job_processed_at = job_details.processed_at
        if job_processed_at.tzinfo is None:
            job_processed_at = job_processed_at.replace(tzinfo=timezone.utc)
        if job_processed_at < cutoff_date:
            continue
            
        # 2. Posted date check
        if not job_details.date_posted or str(job_details.date_posted).strip() == "":
            continue
            
        # 3. Company name check
        if not job_details.company_profile or not job_details.company_profile.companyName or str(job_details.company_profile.companyName).strip() == "":
            continue

        enriched_results.append(EnrichedMatch(
            match=match,
            job_details=job_details
        ))

    # Sort by percentage_match descending
    enriched_results.sort(
        key=lambda x: x.match.percentage_match,
        reverse=True
    )
            
    if not enriched_results:
        try:
            # Fetch latest experience from default resume
            latest_experience = "Not specified"
            default_resume = await ProcessedResume.find_one(
                {"user_id": user_id, "default": True}
            )
            if default_resume and default_resume.experiences:
                # Assuming the first experience is the latest one
                latest_experience = default_resume.experiences[0].job_title

            # Prepare user preferences
            prefs = []
            if user.salary_min: prefs.append(f"Min Salary: {user.salary_min}")
            if user.salary_max: prefs.append(f"Max Salary: {user.salary_max}")
            if user.visa_sponsorship is not None: prefs.append(f"Visa Sponsorship: {'Yes' if user.visa_sponsorship else 'No'}")
            if user.remote_friendly is not None: prefs.append(f"Remote Friendly: {'Yes' if user.remote_friendly else 'No'}")
            if user.country: prefs.append(f"Country: {user.country}")
            if user.city: prefs.append(f"City: {user.city}")
            if user.experience: prefs.append(f"Years of Experience: {user.experience}")
            
            prefs_str = ", ".join(prefs) if prefs else "None specified"

            # Construct email content
            admin_email = "asadullahbeg@gmail.com"
            subject = f"Zero Matches for User: {user.local.email if user.local else user.google.email if user.google else user_id}"
            
            email_body = f"""
            <html>
                <body>
                    <h2>Zero Match Notification</h2>
                    <p>A user has received zero enriched matches.</p>
                    <ul>
                        <li><strong>User Email:</strong> {user.local.email if user.local else user.google.email if user.google else 'N/A'}</li>
                        <li><strong>Latest Job Title:</strong> {latest_experience}</li>
                        <li><strong>Preferences:</strong> {prefs_str}</li>
                    </ul>
                </body>
            </html>
            """
            
            email_service = EmailService()
            email_service.send_email(admin_email, subject, email_body)
            logger.info(f"Zero match notification sent for user {user_id} to {admin_email}")
            
        except Exception as e:
            logger.error(f"Failed to send zero match notification for user {user_id}: {e}")

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
@router.post("/match/clicked/{match_id}", status_code=status.HTTP_200_OK)
async def update_match_clicked(
    match_id: str,
    x_user_token: str = Header(..., alias="X-User-Token")
):
    """
    Updates the UserJobMatch document to set clicked=True.
    Requires user validation via token.
    """
    billing_service = BillingService()
    user = await billing_service.get_user_by_token(x_user_token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid user token."
        )
    
    match = await UserJobMatch.get(match_id)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match with ID {match_id} not found."
        )
    
    if match.user_id != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this match."
        )
    
    match.clicked = True
    await match.save()
    return {"message": "Match updated successfully.", "clicked": True}

@router.post("/match/applied/{match_id}", status_code=status.HTTP_200_OK)
async def update_match_applied(
    match_id: str,
    x_user_token: str = Header(..., alias="X-User-Token")
):
    """
    Updates the UserJobMatch document to set clicked_on_applied=True.
    Requires user validation via token.
    """
    billing_service = BillingService()
    user = await billing_service.get_user_by_token(x_user_token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid user token."
        )
    
    match = await UserJobMatch.get(match_id)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match with ID {match_id} not found."
        )
    
    if match.user_id != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this match."
        )
    
    match.clicked_on_applied = True
    await match.save()
    return {"message": "Match updated successfully.", "clickedOnApplied": True}

@router.post("/match/seen/{match_id}", status_code=status.HTTP_200_OK)
async def clicked_on_matched_job(
    match_id: str,
    x_user_token: str = Header(..., alias="X-User-Token")
):
    """
    Updates the UserJobMatch document to set new_matched_job=False.
    Requires user validation via token.
    """
    billing_service = BillingService()
    user = await billing_service.get_user_by_token(x_user_token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid user token."
        )
    
    match = await UserJobMatch.get(match_id)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match with ID {match_id} not found."
        )
    
    if match.user_id != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this match."
        )
    
    match.new_matched_job = False
    await match.save()
    return {"message": "Match updated successfully.", "new_matched_job": False}

# Email Template for Job Matches
EMAIL_TEMPLATE_MATCHES = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f0f2f5; color: #1c1e21; }
        .container { max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1); }
        .header { background: linear-gradient(135deg, #6e8efb, #a777e3); padding: 40px 20px; text-align: center; color: #ffffff; }
        .header h1 { margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px; }
        .content { padding: 40px 30px; line-height: 1.6; }
        .content p { margin-bottom: 20px; font-size: 16px; }
        .button-container { text-align: center; margin: 30px 0; }
        .button { background-color: #6e8efb; background: linear-gradient(135deg, #6e8efb, #a777e3); color: #ffffff !important; padding: 16px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 18px; display: inline-block; transition: transform 0.2s; box-shadow: 0 4px 15px rgba(110, 142, 251, 0.3); }
        .features { background-color: #f8fafc; padding: 25px; border-radius: 10px; margin: 20px 0; border: 1px solid #e2e8f0; }
        .features h3 { margin-top: 0; color: #4a5568; font-size: 18px; }
        .feature-item { margin-bottom: 15px; display: flex; align-items: flex-start; }
        .feature-icon { color: #6e8efb; margin-right: 12px; font-size: 20px; }
        .feature-text { font-size: 15px; color: #4a5568; }
        .footer { background-color: #f9fafb; padding: 30px; text-align: center; font-size: 14px; color: #718096; border-top: 1px solid #edf2f7; }
        .footer a { color: #6e8efb; text-decoration: none; }
        .logo { font-weight: 800; font-size: 22px; color: #ffffff; margin-bottom: 10px; display: block; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="logo">Bhai Kaam Do</span>
            <h1>Your Top Matches are Ready!</h1>
        </div>
        <div class="content">
            <p>Hi there,</p>
            <p>Our system has finished processing your profile, and we’ve found several <strong>top job matches</strong> that align with your skills and preferences.</p>
            <p>You can view your personalized list and start applying immediately by visiting your dashboard:</p>
            
            <div class="button-container">
                <a href="https://bhaikaamdo.com/matches" class="button">View My Job Matches</a>
            </div>

            <div class="features">
                <h3>Why check these matches?</h3>
                <div class="feature-item">
                    <div class="feature-icon">🎯</div>
                    <div class="feature-text"><strong>Tailored to You:</strong> These roles were selected based on your specific experience and criteria.</div>
                </div>
                <div class="feature-item">
                    <div class="feature-icon">🚀</div>
                    <div class="feature-text"><strong>High Compatibility:</strong> We’ve prioritized listings where you have the highest chance of landing an interview.</div>
                </div>
                <div class="feature-item">
                    <div class="feature-icon">⚡</div>
                    <div class="feature-text"><strong>Real-time Updates:</strong> New matches are added as soon as they hit our system.</div>
                </div>
            </div>

            <p>If you have any questions or need assistance with your account, please don't hesitate to reach out to our team at <a href="mailto:support@bhaikaamdo.com">support@bhaikaamdo.com</a>.</p>
            
            <p>Best of luck with the hunt!</p>
            <p><strong>The Bhai Kaam Do Team</strong></p>
        </div>
        <div class="footer">
            <p>&copy; 2026 Bhai Kaam Do. All rights reserved.</p>
            <p>Helping you find the work you deserve.</p>
        </div>
    </div>
</body>
</html>
"""

class MatchNotificationRequest(BaseModel):
    user_email: str

@router.post("/send-match-notification", status_code=status.HTTP_200_OK)
async def send_match_notification(
    request: MatchNotificationRequest,
    admin: User = Depends(get_admin_user)
):
    """
    Sends a match notification email to the specified recipient.
    """
    email_service = EmailService()
    subject = "Your top matches are ready"
    success = email_service.send_email(request.user_email, subject, EMAIL_TEMPLATE_MATCHES)
    
    if success:
        return {"message": f"Successfully sent match notification to {request.user_email}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send notification email.")

@router.post("/send-match-notifications-all", status_code=status.HTTP_200_OK)
async def send_match_notifications_all(
    admin: User = Depends(get_admin_user)
):
    """
    Finds all unique users in 'UserJobMatch' and sends them a notification email.
    """
    logger.info("--- [send_match_notifications_all] Batch notification process started ---")
    
    # 1. Get all unique user_ids from UserJobMatch
    try:
        user_ids = await UserJobMatch.get_motor_collection().distinct("user_id")
    except Exception as e:
        logger.error(f"Failed to fetch unique user_ids from UserJobMatch: {e}")
        # Fallback to fetching all and extracting unique set if motor collection is not directly accessible
        all_matches = await UserJobMatch.find_all().to_list()
        user_ids = {m.user_id for m in all_matches}
        
    logger.info(f"Found {len(user_ids)} unique users with matches.")
    
    email_service = EmailService()
    sent_count = 0
    failed_count = 0
    skipped_count = 0
    
    for user_id in user_ids:
        try:
            # Note: user_id is a string, Beanie handles it
            user = await User.get(user_id)
            if not user:
                logger.warning(f"User {user_id} not found in database, skipping.")
                skipped_count += 1
                continue
                
            # Determine the best email address
            to_email = None
            if user.local and user.local.email:
                to_email = user.local.email
            elif user.google and user.google.email:
                to_email = user.google.email
            elif user.linkedin and user.linkedin.email:
                to_email = user.linkedin.email
            elif user.facebook and user.facebook.email:
                to_email = user.facebook.email
                
            if not to_email:
                logger.warning(f"User {user_id} has no valid email address, skipping.")
                skipped_count += 1
                continue
                
            subject = "Your top matches are ready"
            success = email_service.send_email(to_email, subject, EMAIL_TEMPLATE_MATCHES)
            
            if success:
                sent_count += 1
                logger.info(f"Notification sent to {to_email} (ID: {user_id})")
            else:
                failed_count += 1
                logger.error(f"Failed to send notification to {to_email} (ID: {user_id})")
                
        except Exception as e:
            logger.error(f"Error processing notification for user {user_id}: {e}")
            failed_count += 1
            
    logger.info(f"--- [send_match_notifications_all] Finished. Sent: {sent_count}, Failed: {failed_count}, Skipped: {skipped_count} ---")
    
    return {
        "message": "Batch notification process completed.",
        "unique_users_found": len(user_ids),
        "emails_sent": sent_count,
        "emails_failed": failed_count,
        "users_skipped_no_email_or_not_found": skipped_count
    }
