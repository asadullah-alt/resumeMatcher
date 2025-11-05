from __future__ import annotations

from datetime import datetime
from typing import Optional

from beanie import Document
from pydantic import Field


class User(Document):
    email: str
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

