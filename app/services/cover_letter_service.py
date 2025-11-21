import logging
from typing import Optional
from app.agent import AgentManager
from app.prompt import prompt_factory
from app.services.job_service import JobService
from app.services.resume_service import ResumeService

logger = logging.getLogger(__name__)

class CoverLetterService:
    def __init__(self, db: object):
        self.db = db
        self.agent_manager = AgentManager()
        self.job_service = JobService(db)
        self.resume_service = ResumeService(db)

    async def generate_cover_letter(self, token: str, resume_id: str, job_id: str) -> str:
        """
        Generates a cover letter based on the resume and job description.
        """
        # Fetch Resume
        resume_data = await self.resume_service.get_resume_with_processed_data(resume_id)
        if not resume_data:
             raise ValueError(f"Resume with id {resume_id} not found")

        # Fetch Job
        job_data = await self.job_service.get_job_with_processed_data(job_id, token)
        if not job_data:
            raise ValueError(f"Job with id {job_id} not found")
            
        # Prepare Data for Prompt
        # We use the processed data if available, otherwise fall back to raw content or empty
        
        # Format Job Posting
        processed_job = job_data.get("processed_job")
        if processed_job:
            job_str = str(processed_job) # Or format it nicely as JSON
        else:
            job_str = job_data.get("raw_job", {}).get("content", "")

        # Format Resume Details
        processed_resume = resume_data.get("processed_resume")
        if processed_resume:
            resume_str = str(processed_resume) # Or format it nicely as JSON
        else:
            resume_str = resume_data.get("raw_resume", {}).get("content", "")

        # Get Prompt
        prompt_template = prompt_factory.get("cover_letter")
        prompt = prompt_template.format(job_str, resume_str)

        # Generate
        logger.info("Generating cover letter...")
        cover_letter = await self.agent_manager.run(prompt=prompt)
        
        return cover_letter
