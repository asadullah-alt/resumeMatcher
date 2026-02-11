from fastapi import APIRouter

from .job import job_router
from .resume import resume_router
from .config import config_router
from .cover_letter import cover_letter_router
from .user_analysis import router as user_analysis_router

v1_router = APIRouter(prefix="/api/v1", tags=["v1"])
v1_router.include_router(resume_router, prefix="/resumes")
v1_router.include_router(job_router, prefix="/jobs")
v1_router.include_router(config_router)
v1_router.include_router(cover_letter_router, prefix="/cover-letters")
v1_router.include_router(user_analysis_router, prefix="/user-analysis", tags=["user-analysis"])


__all__ = ["v1_router"]
