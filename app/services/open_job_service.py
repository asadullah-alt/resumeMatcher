import uuid
import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import ValidationError
from app.agent import AgentManager
from app.prompt import prompt_factory
from app.schemas.json import json_schema_factory
from app.models import Job, ProcessedOpenJobs
from app.schemas.pydantic import StructuredJobModel

logger = logging.getLogger(__name__)

class OpenJobService:
    def __init__(self):
        self.json_agent_manager = AgentManager(
            model_provider="ollama",
            model="gpt-oss-safeguard:20b"
        )

    async def run(self, job_id: str, user_id: str, content: str, job_url: str = None) -> Optional[ProcessedOpenJobs]:
        """
        Processes the job by extracting structured data and storing it.
        """
        logger.info(f"Processing open job: {job_id}")
        return await self._extract_and_store_structured_open_job(
            job_id=job_id,
            user_id=user_id,
            job_description_text=content,
            job_url=job_url
        )

    async def _extract_and_store_structured_open_job(
        self, job_id: str, user_id: str, job_description_text: str, job_url: str = None
    ):
        """
        Extract and store structured open job data in the database.
        """
        structured_job = await self._extract_structured_json(job_description_text)
        if not structured_job:
            logger.info("Structured open job extraction failed.")
            return None

        processed_job = ProcessedOpenJobs(
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
            compensation_and_benefits=structured_job.get("compensation_and_benefits"),
            application_info=structured_job.get("application_info"),
            is_visa_sponsored=structured_job.get("is_visa_sponsored", None),
            is_remote=structured_job.get("is_remote", None),
            analyzed=False
        )

        extracted_kw = structured_job.get("extracted_keywords")
        if isinstance(extracted_kw, str):
            try:
                extracted_kw = json.loads(extracted_kw)
            except json.JSONDecodeError:
                pass
        
        if isinstance(extracted_kw, dict):
            for key in ("extracted_keywords", "extractedKeywords"):
                if key in extracted_kw and isinstance(extracted_kw[key], list):
                    extracted_kw = extracted_kw[key]
                    break
        
        if not isinstance(extracted_kw, list):
            extracted_kw = None

        processed_job.extracted_keywords = extracted_kw
        await processed_job.insert()
        logger.info(f"Successfully processed and stored open job: {job_id}")
        return processed_job

    def fix_nested_json_strings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively parses any string values that look like JSON."""
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
                    fixed_data[key] = json.loads(fixed_data[key])
                except json.JSONDecodeError:
                    pass
        return fixed_data

    async def _extract_structured_json(
        self, job_description_text: str
    ) -> Dict[str, Any] | None:
        """
        Uses AgentManager to ask LLM for structured JSON.
        """
        prompt_template = prompt_factory.get("structured_job")
        prompt = prompt_template.format(
            json.dumps(json_schema_factory.get("structured_job"), indent=2),
            job_description_text,
        )
        
        for attempt in range(1, 3):
            logger.info(f"Structured Open Job Extraction Attempt {attempt}")
            raw_output_v1 = await self.json_agent_manager.run(prompt=prompt)
            raw_output = self.fix_nested_json_strings(raw_output_v1)
            
            try:
                structured_job = StructuredJobModel.model_validate(raw_output)
                return structured_job.model_dump(mode="json")
            except ValidationError as e:
                logger.info(f"Validation error on attempt {attempt}: {e}")
                if attempt == 2:
                    return None
        return None
