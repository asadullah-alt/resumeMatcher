import logging
from typing import Optional
from app.agent import AgentManager
from app.prompt import prompt_factory
from app.services.job_service import JobService
from app.services.resume_service import ResumeService
from app.models import CoverLetter, User, Resume

logger = logging.getLogger(__name__)

class CoverLetterService:
    def __init__(self, db: object):
        self.db = db
        self.agent_manager = AgentManager(strategy="md")
        self.job_service = JobService(db)
        self.resume_service = ResumeService(db)

    async def _verify_token_and_get_user_id(self, token: str) -> str:
        """
        Verify the token and return the associated user_id.
        """
        if not token:
            raise ValueError("Authentication token is required")
            
        user = await User.find_one({
            "$or": [
                {"google.token": token},
                {"linkedin.token": token},
                {"local.token": token}
            ]
        })
        
        if not user:
            raise ValueError("Invalid token or user not found")
            
        return str(user.id)

    async def generate_cover_letter(self, token: str, resume_id: str, job_id: str) -> str:
        """
        Generates a cover letter based on the resume and job description.
        Saves the generated cover letter to the database.
        """
        user_id = await self._verify_token_and_get_user_id(token)
       
        # Check if cover letter already exists
        try:
            try:
                existing_cover_letter = await CoverLetter.find_one(
                    CoverLetter.job_id == job_id                
                )
                
                if existing_cover_letter:
                    return existing_cover_letter.content
            except Exception as e:
                logger.error(f"Error fetching existing cover letter: {e}")
                raise
            
            # Fetch Resume
            
            resume = await Resume.find_one(
                Resume.resume_id == resume_id,
                Resume.user_id == user_id
            )
            if not resume:
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
            resume_str = resume.content

            # Get Prompt
            prompt_template = prompt_factory.get("cover_letter")
            prompt = prompt_template.format(job_str, resume_str)

            # Generate
            logger.info("Generating cover letter...")
            cover_letter_content = await self.agent_manager.run(prompt=prompt)
            
            # Clean up markdown markers if they exist
            # Order matters: more specific/longer markers first
            markers = ["```markdown", "```md", "```", "``````"]
            for marker in markers:
                cover_letter_content = cover_letter_content.replace(marker, "")
            cover_letter_content = cover_letter_content.strip()

            logger.info(f"###########cover_letter_content (cleaned): {cover_letter_content}") 
            # Save to DB
            cover_letter = CoverLetter(
                user_id=user_id,
                job_id=job_id,
                resume_id=resume_id,
                content=cover_letter_content
            )
            await cover_letter.insert()

            return cover_letter_content
        except Exception as e:
            logger.error(f"Error generating cover letter: {e}")
            raise   

    async def get_cover_letter(self, job_id: str, resume_id: str, token: str) -> Optional[str]:
        user_id = await self._verify_token_and_get_user_id(token)
        cover_letter = await CoverLetter.find_one(
            CoverLetter.job_id == job_id,
            CoverLetter.resume_id == resume_id,
            CoverLetter.user_id == user_id
        )
        return cover_letter.content if cover_letter else None

    async def update_cover_letter(self, job_id: str, resume_id: str, token: str, content: str) -> Optional[str]:
        user_id = await self._verify_token_and_get_user_id(token)
        cover_letter = await CoverLetter.find_one(
            CoverLetter.job_id == job_id,
            CoverLetter.resume_id == resume_id,
            CoverLetter.user_id == user_id
        )
        if cover_letter:
            cover_letter.content = content
            cover_letter.updated_at = datetime.utcnow()
            await cover_letter.save()
            return cover_letter.content
        return None

    async def delete_cover_letter(self, job_id: str, resume_id: str, token: str) -> bool:
        user_id = await self._verify_token_and_get_user_id(token)
        cover_letter = await CoverLetter.find_one(
            CoverLetter.job_id == job_id,
            CoverLetter.resume_id == resume_id,
            CoverLetter.user_id == user_id
        )
        if cover_letter:
            await cover_letter.delete()
            return True
        return False
