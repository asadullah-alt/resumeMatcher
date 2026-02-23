import uuid
from typing import List, Dict, Any
from job_processor.models.job import Job, ProcessedOpenJobs, CompanyProfile, Location as JobLocation, Qualifications, RemoteStatusEnum
from app.models.resume import ProcessedResume, Location as ResumeLocation
from app.models.user import User
from job_processor.services.llm_service import LLMService
from job_processor.services.vector_service import VectorService
from job_processor.services.qdrant_service import QdrantService
from job_processor.logger import get_logger

import os
import tempfile
import re
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil import parser

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

    def calculate_experience_years(self, experiences: List[Any]) -> float:
        """
        Calculates total years of experience from a list of experiences.
        Handles overlapping intervals and various date formats.
        """
        if not experiences:
            return 0.0

        intervals = []
        now = datetime.now()

        for exp in experiences:
            start_str = getattr(exp, "start_date", None)
            end_str = getattr(exp, "end_date", None)
            
            if not start_str:
                continue

            try:
                # Parse start date
                start_dt = parser.parse(str(start_str), fuzzy=True)
                
                # Parse end date
                if not end_str or any(x in str(end_str).lower() for x in ["present", "current", "now"]):
                    end_dt = now
                else:
                    end_dt = parser.parse(str(end_str), fuzzy=True)
                
                if start_dt > end_dt:
                    start_dt, end_dt = end_dt, start_dt
                    
                intervals.append((start_dt, end_dt))
            except (ValueError, TypeError, OverflowError) as e:
                logger.warning(f"Failed to parse dates for experience calculation ({start_str} - {end_str}): {e}")
                continue

        if not intervals:
            return 0.0

        # Merge overlapping intervals
        intervals.sort(key=lambda x: x[0])
        merged = []
        if intervals:
            curr_start, curr_end = intervals[0]
            for i in range(1, len(intervals)):
                next_start, next_end = intervals[i]
                if next_start <= curr_end:
                    curr_end = max(curr_end, next_end)
                else:
                    merged.append((curr_start, curr_end))
                    curr_start, curr_end = next_start, next_end
            merged.append((curr_start, curr_end))

        total_days = sum((end - start).days for start, end in merged)
        total_years = round(total_days / 365.25, 1)
        
        logger.info(f"Calculated {total_years} years of experience from {len(experiences)} entries")
        return total_years

    def flatten_resume_data(self, resume: ProcessedResume) -> str:
        """
        Flattens all structured resume data into natural language for vectorization.
        """
        parts = []
        
        if resume.summary:
            parts.append(f"Summary: {resume.summary}")
            
        # Skills
        if resume.skills:
            skill_names = [s.skill_name for s in resume.skills if s.skill_name]
            if skill_names:
                parts.append("Skills: " + ", ".join(skill_names))
                
        # Experience
        for exp in resume.experiences:
            exp_parts = []
            if exp.job_title:
                exp_parts.append(f"Role: {exp.job_title}")
            if exp.company:
                exp_parts.append(f"at {exp.company}")
            if exp.description:
                exp_parts.append(". ".join(exp.description))
            if exp_parts:
                parts.append("Experience entry: " + " ".join(exp_parts))
                
        # Projects
        for proj in resume.projects:
            proj_parts = []
            if proj.project_name:
                proj_parts.append(f"Project: {proj.project_name}")
            if proj.description:
                proj_parts.append(proj.description)
            if proj.technologies_used:
                proj_parts.append("Using: " + ", ".join(proj.technologies_used))
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
            if edu.description:
                edu_parts.append(edu.description)
            if edu_parts:
                parts.append("Education: " + " ".join(edu_parts))

        # Research Work
        for research in resume.research_work:
            r_parts = []
            if research.title: r_parts.append(f"Research: {research.title}")
            if research.publication: r_parts.append(f"Published in: {research.publication}")
            if research.description: r_parts.append(research.description)
            if r_parts: parts.append(" ".join(r_parts))

        # Achievements
        if resume.achievements:
            parts.append("Achievements: " + "; ".join(resume.achievements))

        # Publications
        for pub in resume.publications:
            p_parts = []
            if pub.title: p_parts.append(f"Publication: {pub.title}")
            if pub.publication_venue: p_parts.append(f"Venue: {pub.publication_venue}")
            if pub.description: p_parts.append(pub.description)
            if p_parts: parts.append(" ".join(p_parts))

        # Conferences, Trainings, Workshops
        for item in resume.conferences_trainings_workshops:
            c_parts = []
            if item.name: c_parts.append(f"{item.type.value if hasattr(item.type, 'value') else item.type or 'Event'}: {item.name}")
            if item.organizer: c_parts.append(f"by {item.organizer}")
            if item.description: c_parts.append(item.description)
            if c_parts: parts.append(" ".join(c_parts))

        # Awards
        for award in resume.awards:
            a_parts = []
            if award.title: a_parts.append(f"Award: {award.title}")
            if award.issuer: a_parts.append(f"issued by {award.issuer}")
            if award.description: a_parts.append(award.description)
            if a_parts: parts.append(" ".join(a_parts))

        # Extracurricular Activities
        for activity in resume.extracurricular_activities:
            ext_parts = []
            if activity.activity_name: ext_parts.append(f"Activity: {activity.activity_name}")
            if activity.role: ext_parts.append(f"as {activity.role}")
            if activity.organization: ext_parts.append(f"with {activity.organization}")
            if activity.description: ext_parts.append(activity.description)
            if ext_parts: parts.append(" ".join(ext_parts))

        # Languages
        if resume.languages:
            lang_parts = [f"{l.language} ({l.proficiency or 'Native'})" for l in resume.languages if l.language]
            if lang_parts:
                parts.append("Languages: " + ", ".join(lang_parts))

        flattened = " ".join(parts)
        logger.debug(f"Flattened resume length: {len(flattened)} chars")
        return flattened

    async def _process_new_resume(self, resume: ProcessedResume, overwrite: bool = False):
        """
        Pipeline for processing resumes: Flattening -> Vectorization -> Save to Qdrant.
        Only processes if resume.default is True.
        """
        if not resume.default:
            logger.info(f"[Resume {resume.resume_id}] Not default resume — skipping vectorization")
            return

        resume_id = resume.resume_id

        # Deduplication check
        if not overwrite and self.qdrant.point_exists(self.qdrant.resume_collection, resume_id):
            logger.info(f"[Resume {resume_id}] already exists in Qdrant and overwrite is False — skipping")
            return
        logger.info(f"[Resume {resume_id}] Starting resume processing pipeline")

        # 1. Flattening
        logger.info(f"[Resume {resume_id}] Step 1/2 — Flattening resume data")
        flattened = self.flatten_resume_data(resume)

        # 2. Vectorize + Save to Qdrant
        logger.info(f"[Resume {resume_id}] Step 2/2 — Generating vectors and upserting to Qdrant")
        dense_vector = self.vector_service.get_dense_vector(flattened)
        sparse_vector = self.vector_service.get_splade_vector(flattened)

        # 3. Fetch User and enrich metadata
        user = await User.find_one(User.id == resume.user_id) # ProcessedResume.user_id is a string usually
        if not user:
            # Try converting to ObjectId if needed, but Beanie usually handles string IDs
            # If standard string ID fail, attempt raw search
            user = await User.get(resume.user_id)
            
        exp_years = self.calculate_experience_years(resume.experiences)

        # Prepare metadata matching job schema
        latest_title = None
        if resume.experiences:
            latest_title = resume.experiences[0].job_title

        location_str = None
        if resume.personal_data and resume.personal_data.location:
            loc = resume.personal_data.location
            location_str = ", ".join(filter(None, [loc.city, loc.country]))

        resume_metadata = {
            "title": latest_title,
            "location": location_str,
            "remote_friendly": user.remote_friendly if user else None,
            "salary_min": user.salary_min if user else None,
            "salary_max": user.salary_max if user else None,
            "skills": [{"skill_name": s.skill_name, "skill_type": "Hard Skill"} for s in resume.skills if s.skill_name],
            "experience_years": exp_years,
            "posted_at": resume.processed_at.isoformat() if resume.processed_at else None,
            "visa_sponsorship": user.visa_sponsorship if user else None
        }

        # Prepare final payload
        # Use model_dump_json() then loads() to ensure all custom types (like PydanticObjectId) 
        # are converted to JSON-safe primitives (strings, etc.)
        full_resume_json = json.loads(resume.model_dump_json())

        payload = {
            "resume_id": resume_id,
            "user_id": str(resume.user_id),
            "resume_name": resume.resume_name,
            "resume_text": flattened,
            "metadata": resume_metadata,
            "full_resume": full_resume_json
        }

        self.qdrant.upsert_vector(
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

        self.qdrant.upsert_vector(
            collection_name=self.qdrant.job_collection,
            entity_id=processed_job.job_id,
            dense_vector=dense_vector,
            sparse_vector=sparse_vector,
            payload=payload,
        )
        logger.info(f"[Job {job_id}] Pipeline completed successfully — vector upserted to Qdrant")
    async def match_user_resumes_to_jobs(self, user_id: str, overwrite: bool = False):
        """
        Matches the user's default resume vectors against existing open job vectors.
        Saves the match percentages to UserJobMatch collection.
        """
        from job_processor.models.job import UserJobMatch
        
        logger.info(f"[User {user_id}] Starting user-job matching process (overwrite={overwrite})")
        
        # 1. Find default resume for this user
        resume = await ProcessedResume.find_one(
            ProcessedResume.user_id == str(user_id),
            ProcessedResume.default == True
        )
        
        if not resume:
            logger.warning(f"[User {user_id}] No default processed resume found — matching aborted")
            return
        
        resume_id = resume.resume_id
        logger.info(f"[User {user_id}] Found default resume {resume_id}")

        # 2. Retrieve vectors from Qdrant
        point_data = self.qdrant.get_point_by_id(self.qdrant.resume_collection, resume_id)
        if not point_data or "vectors" not in point_data:
            logger.warning(f"[User {user_id}] Vectors for resume {resume_id} not found in Qdrant — matching aborted")
            return

        vectors = point_data["vectors"]
        dense_vec = vectors.get("dense")
        sparse_vec = vectors.get("sparse")

        if not dense_vec or not sparse_vec:
            logger.warning(f"[User {user_id}] Incomplete vectors for resume {resume_id} — matching aborted")
            return

        # 3. Search Qdrant for matching jobs
        logger.info(f"[User {user_id}] Searching for top matching jobs")
        matches = self.qdrant.search_jobs(dense_vec, sparse_vec.model_dump() if hasattr(sparse_vec, "model_dump") else sparse_vec, limit=100)

        # 4. Save/Update match results in MongoDB
        results = []
        for match in matches:
            job_id = match["job_id"]
            percentage = min(match["score"] * 100, 100.0)
            
            # Fetch job_url from ProcessedOpenJobs
            processed_job = await ProcessedOpenJobs.find_one({"job_id": str(job_id)})
            job_url = processed_job.job_url if processed_job else None

            # Check if match already exists
            exists = await UserJobMatch.find_one({
                "user_id": str(user_id),
                "job_id": str(job_id)
            })
            
            if exists:
                if not overwrite:
                    logger.info(f"[User {user_id}] Match with job {job_id} already exists — skipping")
                    results.append(exists)
                    continue
                else:
                    logger.info(f"[User {user_id}] Match with job {job_id} exists — updating")
                    exists.percentage_match = percentage
                    exists.job_url = job_url
                    await exists.save()
                    results.append(exists)
                    continue

            match_doc = UserJobMatch(
                user_id=str(user_id),
                job_id=str(job_id),
                job_url=job_url,
                percentage_match=percentage
            )
            await match_doc.insert()
            results.append(match_doc)

        # Sort results by percentage match descending
        results.sort(key=lambda x: x.percentage_match, reverse=True)

        logger.info(f"[User {user_id}] Successfully matched with {len(results)} jobs")
        return results
