from __future__ import annotations

from typing import AsyncGenerator

import motor.motor_asyncio
from beanie import init_beanie

from .config import settings
from ..models import (
    Resume,
    ProcessedResume,
    Job,
    ProcessedJob,
    User,
    Improvement,
    CoverLetter,
    ProcessedOpenJobs,
    ImprovedResume,
)


# Globals populated during startup
_motor_client: motor.motor_asyncio.AsyncIOMotorClient | None = None
_motor_db = None


async def init_db(app=None) -> None:
    """Initialize Motor client and Beanie (call from application lifespan/startup)."""
    global _motor_client, _motor_db
    _motor_client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGO_URI)
    _motor_db = _motor_client[settings.MONGO_DB_NAME]

    # Initialize Beanie with all document models
    await init_beanie(
        database=_motor_db,
        document_models=[
            Resume,
            ProcessedResume,
            Job,
            ProcessedJob,
            User,
            Improvement,
            CoverLetter,
            ProcessedOpenJobs,
            ImprovedResume,
        ],
    )


async def close_db() -> None:
    """Close Motor client (call on shutdown)."""
    global _motor_client
    if _motor_client is not None:
        _motor_client.close()


async def get_db_session() -> AsyncGenerator:
    """FastAPI dependency: yields the Motor database instance (or None if not initialized)."""
    yield _motor_db


def get_motor_client() -> motor.motor_asyncio.AsyncIOMotorClient | None:
    return _motor_client
