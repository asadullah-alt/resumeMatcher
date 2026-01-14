from typing import List, Optional
from pydantic import BaseModel


class ImprovementItem(BaseModel):
    suggestion: str
    lineNumber: Optional[str] = None


class ResumeAnalysisModel(BaseModel):
    details: str
    commentary: str
    summary: Optional[str] = None
    improvements: List[ImprovementItem]
    similarity_comparison: Optional[int] = None
