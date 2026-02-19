import httpx
from ..config import settings
import logging

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.LLM_MODEL

    async def extract_skills(self, job_content: str) -> list[str]:
        prompt = f"List all the skills found in this job description. Return only a comma-separated list of skills.\n\nJob Description:\n{job_content}"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
                
                response_text = data.get("response", "")
                # Simple parsing for comma-separated list
                skills = [s.strip() for s in response_text.split(",") if s.strip()]
                return skills
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return []

llm_service = LLMService()
