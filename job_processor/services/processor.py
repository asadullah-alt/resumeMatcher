import uuid
from typing import List, Dict, Any
from job_processor.models.job import Job, ProcessedOpenJobs, CompanyProfile, Location as JobLocation, Qualifications, RemoteStatusEnum
from app.models.resume import ProcessedResume, Location as ResumeLocation
from job_processor.services.llm_service import LLMService
from job_processor.services.vector_service import VectorService
from job_processor.services.qdrant_service import QdrantService
from job_processor.logger import get_logger

import os
import tempfile

logger = get_logger("job_processor.processor")

try:
    from skillNer.general_params import SKILL_DB
except (ImportError, PermissionError):
    # skillNer attempts to write 'skill_db_relax_20.json' to the current directory on import.
    # If the current directory is not writable (common in systemd services), it raises PermissionError.
    # We workaround this by temporarily switching to a writable temp directory during import.
    logger.warning("skillNer import failed from current directory — retrying from temp dir")
    original_cwd = os.getcwd()
    try:
        os.chdir(tempfile.gettempdir())
        from skillNer.general_params import SKILL_DB
        logger.info("skillNer SKILL_DB loaded successfully from temp dir")
    except Exception as e:
        logger.error(f"Failed to load skillNer SKILL_DB: {e}. Falling back to empty DB.", exc_info=True)
        SKILL_DB = {}
    finally:
        os.chdir(original_cwd)

class JobProcessor:
    def __init__(self):
        logger.info("Initializing JobProcessor")
        self.llm = LLMService()
        self.vector_service = VectorService()
        self.qdrant = QdrantService()
        self.db_lookup = {v['skill_name'].lower(): v['skill_name'] for k, v in SKILL_DB.items()}
        logger.info(f"SKILL_DB loaded with {len(self.db_lookup)} entries")

    def standardize_skills(self, skills_list: List[Any]) -> List[Dict[str, Any]]:
        """
        Standardizes skills using skillNER's SKILL_DB.
        Accepts list of dictionaries or raw strings extracted by LLM.
        """
        standardized_results = []
        seen_skills = set()
        added_to_db = 0

        for skill_item in skills_list:
            # Handle both dicts and strings from LLM
            if isinstance(skill_item, dict):
                name = skill_item.get("skill_name", "").strip()
                skill_type = skill_item.get("skill_type", "Hard Skill")
            else:
                name = str(skill_item).strip()
                skill_type = "Hard Skill"  # Default if not specified
                
            if not name:
                continue

            name_lower = name.lower()
            if name_lower in self.db_lookup:
                canonical_name = self.db_lookup[name_lower]
            else:
                canonical_name = name
                # Add to SKILL_DB if missing
                new_id = f"custom_{uuid.uuid4().hex[:8].upper()}"
                SKILL_DB[new_id] = {
                    'skill_name': canonical_name,
                    'skill_type': skill_type,
                    'skill_len': len(canonical_name.split()),
                    'high_surfce_forms': {'full': canonical_name.lower()},
                    'low_surface_forms': [canonical_name.lower()],
                    'match_on_tokens': False
                }
                self.db_lookup[name_lower] = canonical_name
                added_to_db += 1
                logger.debug(f"New skill added to SKILL_DB: '{canonical_name}' (type: {skill_type})")

            if canonical_name not in seen_skills:
                splade = self.vector_service.get_splade_vector(canonical_name)
                standardized_results.append({
                    "skill_name": canonical_name,
                    "skill_type": skill_type,
                    "splade_weight": splade["weight"],
                    "splade_tokens": splade["tokens"]
                })
                seen_skills.add(canonical_name)

        logger.info(f"Standardized {len(standardized_results)} skills ({added_to_db} new added to SKILL_DB)")
        return standardized_results

    def flatten_data(self, metadata: Dict[str, Any], raw_content: str) -> str:
        """
        Flattens extracted metadata and raw content into natural language for vectorization.
        """
        parts = []
        title = metadata.get("title")
        company = metadata.get("company")
        if title and company:
            parts.append(f"This is a {title} position at {company}.")
        
        if raw_content:
            parts.append(raw_content)
            
        responsibilities = metadata.get("key_responsibilities", [])
        if responsibilities:
            parts.append("Key Responsibilities: " + "; ".join(responsibilities))
            
        skills = metadata.get("skills", [])
        if skills:
            hard = [s["skill_name"] for s in skills if s.get("skill_type") == "Hard Skill"]
            soft = [s["skill_name"] for s in skills if s.get("skill_type") == "Soft Skill"]
            if hard:
                parts.append("Hard Skills Required: " + ", ".join(hard))
            if soft:
                parts.append("Soft Skills Required: " + ", ".join(soft))

        flattened = " ".join(parts)
        logger.debug(f"Flattened text length: {len(flattened)} chars")
        return flattened

    def flatten_resume_data(self, resume: ProcessedResume) -> str:
        """
        Flattens structured resume data into natural language for vectorization.
        """
        parts = []
        
        if resume.summary:
            parts.append(resume.summary)
            
        # Skills
        if resume.skills:
            skill_names = [s.skill_name for s in resume.skills if s.skill_name]
            if skill_names:
                parts.append("Skills: " + ", ".join(skill_names))
                
        # Experience
        for exp in resume.experiences:
            exp_parts = []
            if exp.job_title:
                exp_parts.append(f"worked as {exp.job_title}")
            if exp.company:
                exp_parts.append(f"at {exp.company}")
            if exp.description:
                exp_parts.append(". ".join(exp.description))
            if exp_parts:
                parts.append("Experience: " + " ".join(exp_parts))
                
        # Projects
        for proj in resume.projects:
            proj_parts = []
            if proj.project_name:
                proj_parts.append(f"Project: {proj.project_name}")
            if proj.description:
                proj_parts.append(proj.description)
            if proj_parts:
                parts.append(" ".join(proj_parts))

        # Education
        for edu in resume.education:
            edu_parts = []
            if edu.degree:
                edu_parts.append(edu.degree)
            if edu.field_of_study:
                edu_parts.append(f"in {edu.field_of_study}")
            if edu.institution:
                edu_parts.append(f"from {edu.institution}")
            if edu_parts:
                parts.append("Education: " + " ".join(edu_parts))

        flattened = " ".join(parts)
        logger.debug(f"Flattened resume length: {len(flattened)} chars")
        return flattened

    async def _process_new_resume(self, resume: ProcessedResume):
        """
        Pipeline for processing resumes: Flattening -> Vectorization -> Save to Qdrant.
        Only processes if resume.default is True.
        """
        if not resume.default:
            logger.info(f"[Resume {resume.resume_id}] Not default resume — skipping vectorization")
            return

        resume_id = resume.resume_id
        logger.info(f"[Resume {resume_id}] Starting resume processing pipeline")

        # 1. Flattening
        logger.info(f"[Resume {resume_id}] Step 1/2 — Flattening resume data")
        flattened = self.flatten_resume_data(resume)

        # 2. Vectorize + Save to Qdrant
        logger.info(f"[Resume {resume_id}] Step 2/2 — Generating vectors and upserting to Qdrant")
        dense_vector = self.vector_service.get_dense_vector(flattened)
        sparse_vector = self.vector_service.get_splade_vector(flattened)

        # Prepare payload
        payload = resume.dict()
        # Ensure job_description equivalent is set for consistency if needed, 
        # or just use the flattened content
        payload["resume_text"] = flattened
        
        # Convert date to string for JSON serialization if necessary
        if "processed_at" in payload and payload["processed_at"]:
            payload["processed_at"] = payload["processed_at"].isoformat()

        await self.qdrant.upsert_vector(
            collection_name=self.qdrant.resume_collection,
            entity_id=resume_id,
            dense_vector=dense_vector,
            sparse_vector=sparse_vector,
            payload=payload,
        )
        logger.info(f"[Resume {resume_id}] Resume pipeline completed successfully — upserted to Qdrant")

    async def process_new_job(self, source_job: Job, processed_job: ProcessedOpenJobs):
        """
        The main pipeline: LLM Extraction -> Skill Standardization -> Flattening -> Vectorization -> Save to OpenJobsVector.
        """
        job_id = source_job.job_id
        logger.info(f"[Job {job_id}] Starting processing pipeline")

        # 1. LLM Extraction
        logger.info(f"[Job {job_id}] Step 1/4 — Extracting metadata via LLM")
        raw_metadata = await self.llm.extract_structured_data(source_job.content)
        logger.debug(f"[Job {job_id}] LLM returned keys: {list(raw_metadata.keys())}")

        # 2. Skill Standardization
        logger.info(f"[Job {job_id}] Step 2/4 — Standardizing skills")
        extracted_skills = raw_metadata.get("skills", [])
        standardized_skills = self.standardize_skills(extracted_skills)
        raw_metadata["skills"] = standardized_skills

        # 3. Flattening
        logger.info(f"[Job {job_id}] Step 3/4 — Flattening data for vectorization")
        flattened = self.flatten_data(raw_metadata, source_job.content)

        # 4. Vectorize + Save to Qdrant
        logger.info(f"[Job {job_id}] Step 4/4 — Generating vectors and upserting to Qdrant")
        dense_vector = self.vector_service.get_dense_vector(flattened)
        sparse_vector = self.vector_service.get_splade_vector(flattened)

        # job_id lives in the payload — no separate top-level field
        payload = {
            **raw_metadata,
            "job_id": processed_job.job_id,
            "job_description": flattened,
        }

        await self.qdrant.upsert_vector(
            collection_name=self.qdrant.job_collection,
            entity_id=processed_job.job_id,
            dense_vector=dense_vector,
            sparse_vector=sparse_vector,
            payload=payload,
        )
        logger.info(f"[Job {job_id}] Pipeline completed successfully — vector upserted to Qdrant")
