import uuid
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pydantic import ValidationError
from bs4 import BeautifulSoup, Tag
from app.agent import AgentManager
from app.prompt import prompt_factory
from app.schemas.json import json_schema_factory
from app.models import Job, Resume, ProcessedJob
from app.schemas.pydantic import StructuredJobModel
from .exceptions import JobNotFoundError

logger = logging.getLogger(__name__)


class JobService:
    def __init__(self, db: object):
        # keep db param for compatibility; Beanie document models used directly
        self.db = db
        self.json_agent_manager = AgentManager()
   
    def clean_html_body(self, html_string):
        try:
            # 1. Parse the HTML string
            soup = BeautifulSoup(html_string, 'html.parser')

            # 2. Scope to Body: Look only in the body tag. If not found, use the entire soup.
            body_tag = soup.find('body')
            target_content = body_tag if body_tag else soup
            
            # 3. Define tags that should introduce a specific amount of spacing

            # Tags that usually represent a paragraph or section break (two newlines)
            MAJOR_BLOCK_TAGS = [
                'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                'div', 'section', 'article', 'aside', 'main', 'nav', 'header', 'footer',
                'li', 'ul', 'ol', 'blockquote', 'table', 'tr', 'form', 
                'fieldset', 'legend', 'dt', 'dd', 'address', 'pre'
            ]
            
            # Tags that usually represent a single line break
            LINE_BREAK_TAGS = ['br']

            # 4. Explicitly remove unwanted tags (scripts, svgs, iframes, links, styles)
            # This ensures their content is completely excluded from the result.
            tags_to_remove_completely = ['script', 'svg', 'iframe', 'style', 'a']
            for tag_name in tags_to_remove_completely:
                for tag in target_content.find_all(tag_name):
                    # Use .extract() to remove the tag and its contents
                    tag.extract()
                    
            # 5. Insert two newlines before and after major block elements.
            for tag_name in MAJOR_BLOCK_TAGS:
                for tag in target_content.find_all(tag_name):
                    # Insert two newlines before the tag (simulates top margin/break)
                    tag.insert_before('\n\n')
                    
                    # Append two newlines if it's a general block element.
                    # Skip list items/table rows as they are usually contained by the next break.
                    if tag_name not in ['li', 'tr', 'dt', 'dd']:
                        tag.append('\n\n')
            # 6. Replace <br> tags with a single newline.
            for br_tag in target_content.find_all(LINE_BREAK_TAGS):
                br_tag.replace_with('\n')

            # 7. Final Text Extraction: get all text content, preserving injected newlines
            # Use get_text() on the target_content (body or soup).
            text_content = target_content.get_text(strip=False)
            
            # 8. Post-processing to clean up redundant whitespace

            # 0. Handle literal newlines (escaped \n) which might be present in the text
            text_content = text_content.replace('\\n', '\n')

            # A. Normalize all newline combinations to just \n
            text_content = text_content.replace('\r\n', '\n').replace('\r', '\n')
            
            # B. Final reconstruction: Split by newline and remove lines that are only whitespace
            lines = text_content.split('\n')
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            text_content = '\n'.join(cleaned_lines)

            return text_content

        except Exception as e:
            # Simple error handling
            return f"An error occurred during parsing: {e}"
    async def _verify_token_and_get_user_id(self, token: str) -> str:
        """
        Verify the token and return the associated user_id.
        
        Args:
            token: The authentication token
            
        Returns:
            str: The user_id associated with the token
            
        Raises:
            ValueError: If token is invalid or user not found
        """
        from app.models import User
        
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

    async def create_and_store_job(self, job_data: dict) -> tuple[str, bool]:
        """
        Stores job data in the database and returns a list of job IDs.
        
        Args:
            job_data: Dictionary containing job information
            token: Authentication token
        """
        logger.info(f"Welcome to the job creator")
        token = str(job_data.get("token"))
        user_id = await self._verify_token_and_get_user_id(token)
        job_description_raw = job_data.get("job_descriptions")
        job_url = job_data.get("job_url")

        if job_url:
            existing_job = await Job.find_one({"job_url": job_url, "user_id": user_id})
            if existing_job:
                logger.info(f"Job with url {job_url} already exists for user {user_id}")
                return existing_job.job_id, True

        job_description = self.clean_html_body(job_description_raw)
        job_id = str(uuid.uuid4())
        job = Job(job_id=job_id,user_id=user_id,content=job_description,job_url=job_url,raw_content=job_description_raw)
        await job.insert()
        await self._extract_and_store_structured_job(job_id=job_id,user_id=user_id,job_description_text=job_description,job_url=job_url)
        return job_id, False

    async def _is_resume_available(self, resume_id: str) -> bool:
        """
        Checks if a resume exists in the database.
        """
        resume = await Resume.find_one(Resume.resume_id == resume_id)
        return resume is not None

    async def _extract_and_store_structured_job(
        self, job_id: str, user_id: str, job_description_text: str, job_url: str = None
    ):
        """
        Extract and store structured job data in the database
        
        Args:
            job_id: The ID of the job
            user_id: The ID of the user who owns this job
            job_description_text: The raw job description text
        """
        structured_job = await self._extract_structured_json(job_description_text)
        if not structured_job:
            logger.info("Structured job extraction failed.")
            return None

        processed_job = ProcessedJob(
            job_url=job_url,
            job_id=job_id,
            user_id=user_id,
            job_title=structured_job.get("job_title"),
            company_profile=structured_job.get("company_profile"),
            location=structured_job.get("location"),
            date_posted=structured_job.get("date_posted"),
            employment_type=structured_job.get("employment_type"),
            job_summary=structured_job.get("job_summary"),
            key_responsibilities=structured_job.get("key_responsibilities"),
            qualifications=structured_job.get("qualifications"),
            compensation_and_benfits=structured_job.get("compensation_and_benfits"),
            application_info=structured_job.get("application_info"),
            is_visa_sponsored=structured_job.get("is_visa_sponsored", None),
            is_remote=structured_job.get("is_remote", None),  
        )
        # Cleaning: ensure extracted_keywords is a list. Some LLM outputs wrap the
        # keywords in a nested JSON string/object like:
        # '{"extracted_keywords": ["Python", "..."]}'
        # or a dict: {"extracted_keywords": [...]}. Handle those cases and
        # extract the inner list before saving the ProcessedJob document.
        extracted_kw = structured_job.get("extracted_keywords")

        # If it's a JSON string, try to parse it
        if isinstance(extracted_kw, str):
            try:
                parsed = json.loads(extracted_kw)
                extracted_kw = parsed
            except json.JSONDecodeError:
                # leave as-is if not JSON
                pass

        # If it's a dict with an inner 'extracted_keywords' key, pull the list out
        if isinstance(extracted_kw, dict):
            # support both snake_case and camelCase keys
            for key in ("extracted_keywords", "extractedKeywords"):
                if key in extracted_kw and isinstance(extracted_kw[key], list):
                    extracted_kw = extracted_kw[key]
                    break

        # Final sanity: only keep as list or None
        if not isinstance(extracted_kw, list):
            extracted_kw = None

        # assign the cleaned keywords
        processed_job.extracted_keywords = extracted_kw
        await processed_job.insert()

        return job_id
    def fix_nested_json_strings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively parses any string values that look like JSON."""
        
        # List of keys that were flagged in the error detail
        keys_to_fix = [
            'location', 
            'key_responsibilities', 
            'qualifications', 
            'application_info', 
            'extracted_keywords'
        ]

        fixed_data = data.copy()
        for key in keys_to_fix:
            if key in fixed_data and isinstance(fixed_data[key], str):
                try:
                    # Attempt to parse the string value into a proper Python object
                    fixed_data[key] = json.loads(fixed_data[key])
                except json.JSONDecodeError:
                    # Handle cases where the string isn't valid JSON (optional, but safe)
                    print(f"Warning: Could not decode JSON string for key: {key}")

        return fixed_data
    async def _extract_structured_json(
        self, job_description_text: str
    ) -> Dict[str, Any] | None:
        """
        Uses the AgentManager+JSONWrapper to ask the LLM to
        return the data in exact JSON schema we need.
        """
        prompt_template = prompt_factory.get("structured_job")
        prompt = prompt_template.format(
            json.dumps(json_schema_factory.get("structured_job"), indent=2),
            job_description_text,
        )
        logger.info(f"Structured Job Prompt: {prompt}")
        raw_output_v1 = await self.json_agent_manager.run(prompt=prompt)
        logging.info(f"Structured Job Raw Output (String Type Check): {type(raw_output_v1)}")
        raw_output = self.fix_nested_json_strings(raw_output_v1)
        logger.info(f"Structured Job Raw Output: {raw_output}")
        try:
            structured_job: StructuredJobModel = StructuredJobModel.model_validate(
                raw_output
            )
        except ValidationError as e:
            logger.info(f"Validation error: {e}")
            error_details = []
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                error_details.append(f"{field}: {error['msg']}")
            
            logger.info(f"Validation error details: {'; '.join(error_details)}")
            return None
        return structured_job.model_dump(mode="json")

    async def get_job_with_processed_data(self, job_id: str, token: str) -> Optional[Dict]:
        """
        Fetches both job and processed job data from the database and combines them.

        Args:
            job_id: The ID of the job to retrieve
            token: Authentication token for user verification

        Returns:
            Combined data from both job and processed_job models

        Raises:
            JobNotFoundError: If the job is not found
            ValueError: If token is invalid or user not found
        """
        user_id = await self._verify_token_and_get_user_id(token)
        job = await Job.find_one({"$and": [{"job_id": job_id}, {"user_id": user_id}]})

        if not job:
            raise JobNotFoundError(job_id=job_id)

        processed_job = await ProcessedJob.find_one(
            {"$and": [{"job_id": job_id}, {"user_id": user_id}]}
        )

        combined_data = {
            "job_id": job.job_id,
            "raw_job": {
                "id": str(job.id),
                "content": job.content,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            },
            "processed_job": None
        }

        if processed_job:
            combined_data["processed_job"] = {
                "jobUrl":processed_job.job_url,
                "jobPosition": processed_job.job_title,
                "companyProfile": processed_job.company_profile.model_dump() if processed_job.company_profile else None,
                "location": processed_job.location.model_dump(),
                "date_posted": processed_job.date_posted,
                "employment_type": processed_job.employment_type,
                "jobSummary": processed_job.job_summary,
                "keyResponsibilities": processed_job.key_responsibilities,
                "qualifications": processed_job.qualifications.model_dump(),
                "compensationAndBenefits": processed_job.compensation_and_benefits,
                "applicationInfo": processed_job.application_info.model_dump(),
                "extractedKeywords": processed_job.extracted_keywords,
                "processed_at": processed_job.processed_at.isoformat() if processed_job.processed_at else None,
            }
        
        return combined_data

    async def get_job_without_token(self, job_id: str) -> Optional[Dict]:
      

        processed_job = await ProcessedJob.find_one({"job_id": job_id})
        if not processed_job:
            raise JobNotFoundError(job_id=job_id)

        combined_data = {
            "job_id": processed_job.job_id,
            "processed_job": None
        }

        if processed_job:
            combined_data["processed_job"] = {
                "jobUrl": processed_job.job_url,
                "jobPosition": processed_job.job_title,
                "companyProfile": processed_job.company_profile.model_dump() if processed_job.company_profile else None,
                "location": processed_job.location.model_dump(),
                "date_posted": processed_job.date_posted,
                "employment_type": processed_job.employment_type,
                "jobSummary": processed_job.job_summary,
                "keyResponsibilities": processed_job.key_responsibilities,
                "qualifications": processed_job.qualifications.model_dump(),
                "compensationAndBenefits": processed_job.compensation_and_benefits,
                "applicationInfo": processed_job.application_info.model_dump(),
                "isVisaSponsored": processed_job.is_visa_sponsored,
                "isRemote": processed_job.is_remote,
                "extractedKeywords": processed_job.extracted_keywords,
                "processed_at": processed_job.processed_at.isoformat() if processed_job.processed_at else None,
            }
        return combined_data

    async def get_job_by_url(self, job_url: str) -> Optional[Dict]:
        """
        Fetches only the job data from the database using job_url.

        Args:
            job_url: The URL of the job to retrieve

        Returns:
            Job document data

        Raises:
            JobNotFoundError: If the job is not found
        """
        job = await Job.find_one({"job_url": job_url})

        if not job:
            raise JobNotFoundError(job_id=job_url)

        return {
            "job_id": job.job_id,
            "raw_job": {
                "id": str(job.id),
                
                "raw_content": job.raw_content,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "job_url": job.job_url,
            }
        }
