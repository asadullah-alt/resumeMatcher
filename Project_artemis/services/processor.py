from ..db.models import Job, ProcessedOpenJobs
from .llm import llm_service
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class JobProcessor:
    async def process_job(self, job: Job):
        try:
            logger.info(f"Processing job {job.job_id}")
            
            # Use raw_content if available, otherwise content
            content_to_process = job.raw_content or job.content
            
            if not content_to_process:
                logger.warning(f"No content to process for job {job.job_id}")
                return

            # Extract skills using Ollama
            skills = await llm_service.extract_skills(content_to_process)
            
            # Create ProcessedOpenJobs document
            processed_job = ProcessedOpenJobs(
                job_url=job.job_url,
                user_id=job.user_id,
                job_id=job.job_id,
                extracted_keywords=skills,
                analyzed=True,
                processed_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            await processed_job.insert()
            logger.info(f"Successfully processed job {job.job_id} and added to processedOpenJobs")
            
        except Exception as e:
            logger.error(f"Error processing job {job.job_id}: {e}")

job_processor = JobProcessor()
