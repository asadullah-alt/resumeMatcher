from typing import List, Optional, Union
from pydantic import BaseModel, field_validator


class ImprovementItem(BaseModel):
    suggestion: str
    lineNumber: Optional[str] = None


class ResumeAnalysisModel(BaseModel):
    details: str
    commentary: str
    summary: Optional[str] = None
    improvements: List[ImprovementItem]
    similarity_comparison: Optional[float] = None
    
    @field_validator('similarity_comparison', mode='before')
    @classmethod
    def convert_similarity_to_float(cls, v):
        """Convert similarity_comparison from int, float, or empty string to float."""
        if v is None:
            return None
        if isinstance(v, str):
            # Handle empty string
            if v.strip() == "":
                return None
            # Try to convert string to float
            try:
                return float(v)
            except (ValueError, TypeError):
                return None
        if isinstance(v, (int, float)):
            return float(v)
        return None
