import os
import uuid
import json
import tempfile
import logging

from markitdown import MarkItDown
from typing import Any

from app.models import Resume, ProcessedResume
from pydantic import ValidationError
from typing import Dict, Optional

from app.agent import AgentManager
from app.prompt import prompt_factory
from app.schemas.json import json_schema_factory
from app.schemas.pydantic import StructuredResumeModel
from .exceptions import ResumeNotFoundError, ResumeValidationError

logger = logging.getLogger(__name__)


class ResumeService:
    def __init__(self, db: object):
        # db parameter retained for compatibility with FastAPI dependency injection
        # but Beanie document models are used directly.
        self.db = db
        self.md = MarkItDown(enable_plugins=False)
        self.json_agent_manager = AgentManager()
        
        # Validate dependencies for DOCX and PDF processing
        self._validate_dependencies()

    def _validate_dependencies(self):
        """Validate that required dependencies for DOCX and PDF processing are available"""
        missing_deps = []
        
        # DOCX Validation
        try:
            # Check if markitdown can handle docx files
            from markitdown.converters import DocxConverter
            # Try to instantiate the converter to check if dependencies are available
            DocxConverter()
        except ImportError:
            missing_deps.append("markitdown[all]==0.1.2")
        except Exception as e:
            if "MissingDependencyException" in str(e) or "dependencies needed to read .docx files" in str(e):
                missing_deps.append("markitdown[all]==0.1.2 (current installation missing DOCX extras)")

        # PDF Validation (marker-pdf)
        try:
            import marker
        except ImportError:
            missing_deps.append("marker-pdf")
        
        if missing_deps:
            logger.warning(
                f"Missing dependencies: {', '.join(missing_deps)}. "
                f"File processing may fail. Install with: pip install {' '.join(missing_deps)}"
            )


    async def convert_and_store_resume(
        self, file_bytes: bytes, file_type: str, filename: str, content_type: str = "md", token: Optional[str] = None, resume_name: Optional[str] = None
    ):
        """
        Converts resume file (PDF/DOCX) to text using MarkItDown and stores it in the database.

        Args:
            file_bytes: Raw bytes of the uploaded file
            file_type: MIME type of the file ("application/pdf" or "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            filename: Original filename
            content_type: Output format ("md" for markdown or "html")
            token: Authentication token for processing

        Returns:
            None
        """
        logger.info(f"Converting file: {filename} of type: {file_type}")
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=self._get_file_extension(file_type)
        ) as temp_file:
            temp_file.write(file_bytes)
            temp_path = temp_file.name

        try:
            text_content = ""
            if file_type == "application/pdf":
                try:
                    from marker.converters.pdf import PdfConverter
                    from marker.models import create_model_dict
                    from marker.output import text_from_rendered
                    
                    # Load models
                    converter = PdfConverter(artifact_dict=create_model_dict(),)
                    rendered = converter(temp_path)
                    text, _, images = text_from_rendered(rendered)
                    text_content = text
                except ImportError:
                     raise Exception("marker-pdf not installed. Please install it to process PDFs.")
                except Exception as e:
                     raise Exception(f"PDF conversion failed with marker-pdf: {str(e)}")
            else:
                try:
                    result = self.md.convert(temp_path)
                    text_content = result.text_content
                except Exception as e:
                    # Handle specific markitdown conversion errors
                    error_msg = str(e)
                    if "MissingDependencyException" in error_msg or "DocxConverter" in error_msg:
                        raise Exception(
                            "File conversion failed: markitdown is missing DOCX support. "
                            "Please install with: pip install 'markitdown[all]==0.1.2' or contact system administrator."
                        ) from e
                    elif "docx" in error_msg.lower():
                        raise Exception(
                            f"DOCX file processing failed: {error_msg}. "
                            "Please ensure the file is a valid DOCX document."
                        ) from e
                    else:
                        raise Exception(f"File conversion failed: {error_msg}") from e
            
            resume_id,user_id = await self._store_resume_in_db(text_content, content_type,token,resume_name)

            saved = await self._extract_and_store_structured_resume(
                resume_id=resume_id, resume_text=text_content,token=token,user_id=user_id,resume_name=resume_name
            )

            # If structured resume was determined invalid, do not return the id; inform caller
            if not saved:
                return "Not a valid Resume"

            return resume_id
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _get_file_extension(self, file_type: str) -> str:
        """Returns the appropriate file extension based on MIME type"""
        if file_type == "application/pdf":
            return ".pdf"
        elif (
            file_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            return ".docx"
        return ""

    async def _store_resume_in_db(self, text_content: str, content_type: str, token: Optional[str], resume_name: Optional[str]) -> tuple[str, str | None]:
        """
        Stores the parsed resume content in the database.
        """
        resume_id = str(uuid.uuid4())

        # Check for user by token in different fields
        user = await self.db.users.find_one({
            "$or": [
                {"local.token": token},
                {"google.token": token},
                {"linkedin.token": token}
            ]
        })

        if not user:
            logger.warning(f"No user found for token: {token}")

        user_id = str(user['_id']) if user else None
        logger.info(f"Structured Resume userId: {user_id}")
        resume = Resume(
            resume_name=resume_name,
            resume_id=resume_id,
            content=text_content,
            content_type=content_type,
            user_id=user_id
        )

        await resume.insert()
        return resume_id,user_id

    async def _extract_and_store_structured_resume(
        self, resume_id, resume_text: str, token: Optional[str] = None, user_id: Optional[str] = None, resume_name: Optional[str] = None
    ) -> bool:
        """
        extract and store structured resume data in the database
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                structured_resume = await self._extract_structured_json(resume_text)
                if not structured_resume:
                    logger.error("Structured resume extraction returned None.")
                    raise ResumeValidationError(
                        resume_id=resume_id,
                        message="Failed to extract structured data from resume. Please ensure your resume contains all required sections.",
                    )

                # If both personal_data and experiences are missing/empty, treat as invalid
                personal_data = structured_resume.get("personal_data")
                experiences = structured_resume.get("experiences")

                if (personal_data is None or personal_data == {}) and (
                    experiences is None or (isinstance(experiences, list) and len(experiences) == 0)
                ):
                    logger.warning(f"Structured resume for resume_id={resume_id} missing personal_data and experiences; not saving processed resume.")
                    # Do not save ProcessedResume; indicate invalid resume to caller
                    return False

                # Check if this is the user's first ProcessedResume
                is_first_resume = False
                if user_id:
                    existing_resumes_count = await ProcessedResume.find(
                        ProcessedResume.user_id == str(user_id)
                    ).count()
                    is_first_resume = existing_resumes_count == 0

                processed_resume = ProcessedResume(
                    resume_name=resume_name,
                    user_id=str(user_id) if user_id else None,
                    resume_id=resume_id,
                    default=is_first_resume,  # Set to True if this is the first resume
                    personal_data=structured_resume.get("personal_data"),
                    experiences=structured_resume.get("experiences") or [],
                    projects=structured_resume.get("projects") or [],
                    skills=structured_resume.get("skills") or [],
                    research_work=structured_resume.get("research_work") or [],
                    achievements=structured_resume.get("achievements") or [],
                    education=structured_resume.get("education") or [],
                    extracted_keywords=structured_resume.get("extracted_keywords") or [],
                )
                
                await processed_resume.insert()
                return True
            except ResumeValidationError:
                if attempt == max_retries - 1:
                    # Re-raise validation errors to propagate to the upload endpoint
                    raise
                logger.warning(f"Attempt {attempt + 1} failed with validation error. Retrying...")
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Error storing structured resume: {str(e)}")
                    raise ResumeValidationError(
                        resume_id=resume_id,
                        message=f"Failed to store structured resume data: {str(e)}",
                    )
                logger.warning(f"Attempt {attempt + 1} failed with error: {str(e)}. Retrying...")
        return False

    async def _extract_structured_json(
        self, resume_text: str
    ) -> dict | None:
        """
        Uses the AgentManager+JSONWrapper to ask the LLM to
        return the data in exact JSON schema we need.
        """
        prompt_template = prompt_factory.get("structured_resume")
        print("Schema", json.dumps(json_schema_factory.get("structured_resume"), indent=2))
        prompt = prompt_template.format(
            json.dumps(json_schema_factory.get("structured_resume"), indent=2),
            resume_text,
        )
        logger.info(f"Structured Resume Prompt: {prompt}")
        raw_output = await self.json_agent_manager.run(prompt=prompt)
        logger.info(f"Raw ouptut {raw_output}")
        try:
            structured_resume: StructuredResumeModel = (
                StructuredResumeModel.model_validate(raw_output)
            )
        except ValidationError as e:
            logger.info(f"Validation error: {e}")
            error_details = []
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                error_details.append(f"{field}: {error['msg']}")

            user_friendly_message = "Resume validation failed. " + "; ".join(
                error_details
            )
            raise ResumeValidationError(
                validation_error=user_friendly_message,
                message=f"Resume structure validation failed: {user_friendly_message}",
            )
        logger.info(f"#########################Extracted sturctured resume################")
        return structured_resume.model_dump()

    async def get_resume_with_processed_data(self, resume_id: str) -> Optional[Dict]:
        """
        Fetches both resume and processed resume data from the database and combines them.

        Args:
            resume_id: The ID of the resume to retrieve

        Returns:
            Combined data from both resume and processed_resume models

        Raises:
            ResumeNotFoundError: If the resume is not found
        """
        # Use Beanie queries
        resume = await Resume.find_one(Resume.resume_id == resume_id)

        if not resume:
            raise ResumeNotFoundError(resume_id=resume_id)

        processed_resume = await ProcessedResume.find_one(
            ProcessedResume.resume_id == resume_id
        )

        combined_data = {
            "resume_id": resume.resume_id,
            "raw_resume": {
                "id": resume.id,
                "content": resume.content,
                "content_type": resume.content_type,
                "created_at": resume.created_at.isoformat()
                if resume.created_at
                else None,
            },
            "processed_resume": None,
        }

        if processed_resume:
            combined_data["processed_resume"] = {
                "personal_data": json.loads(processed_resume.personal_data)
                if processed_resume.personal_data
                else None,
                "experiences": json.loads(processed_resume.experiences).get(
                    "experiences", []
                )
                if processed_resume.experiences
                else None,
                "projects": json.loads(processed_resume.projects).get("projects", [])
                if processed_resume.projects
                else [],
                "skills": json.loads(processed_resume.skills).get("skills", [])
                if processed_resume.skills
                else [],
                "research_work": json.loads(processed_resume.research_work).get(
                    "research_work", []
                )
                if processed_resume.research_work
                else [],
                "achievements": json.loads(processed_resume.achievements).get(
                    "achievements", []
                )
                if processed_resume.achievements
                else [],
                "education": json.loads(processed_resume.education).get("education", [])
                if processed_resume.education
                else [],
                "extracted_keywords": json.loads(
                    processed_resume.extracted_keywords
                ).get("extracted_keywords", [])
                if processed_resume.extracted_keywords
                else [],
                "processed_at": processed_resume.processed_at.isoformat()
                if processed_resume.processed_at
                else None,
            }

        return combined_data

    async def get_resume_ids_for_token(self, token: str) -> dict:
        """
        Returns a dictionary containing a list of resume_id strings and the default_resume ID 
        for the user identified by the given token.

        If the user is not found for the token, returns empty list and None for default_resume.
        """
        # Find user by token in the same fields used during storage
        user = await self.db.users.find_one({
            "$or": [
                {"local.token": token},
                {"google.token": token},
                {"linkedin.token": token},
            ]
        })

        if not user:
            logger.info(f"No user found for token when fetching resumes: {token}")
            return {"resumes": [], "default_resume": None}

        user_id = str(user.get("_id"))

        # Query Resume documents for this user_id
        resumes = await ProcessedResume.find(ProcessedResume.user_id == user_id).to_list()
        
        # Find the first resume with default=True
        default_resume = None
        for r in resumes:
            if r.default:
                default_resume = r.resume_id
                break
        
        return {
            "resumes": [{"id": r.resume_id, "resume_name": r.resume_name} for r in resumes],
            "default_resume": default_resume
        }

    async def set_default_resume(self, token: str, resume_id: str) -> bool:
        """
        Sets the specified resume as default for the user and unsets others.
        Returns True if successful, False otherwise.
        """
        # Find user by token
        user = await self.db.users.find_one({
            "$or": [
                {"local.token": token},
                {"google.token": token},
                {"linkedin.token": token},
            ]
        })

        if not user:
            logger.warning(f"No user found for token when setting default resume: {token}")
            return False

        user_id = str(user.get("_id"))

        # Verify the resume belongs to the user
        target_resume = await ProcessedResume.find_one(
            ProcessedResume.resume_id == resume_id,
            ProcessedResume.user_id == user_id
        )

        if not target_resume:
            logger.warning(f"Resume {resume_id} not found for user {user_id}")
            return False
            
        # Unset default for all other resumes of this user
        await ProcessedResume.find(
            ProcessedResume.user_id == user_id
        ).update({"$set": {"default": False}})
        
        # Set the target resume as default
        target_resume.default = True
        await target_resume.save()
        
        return True
