import asyncio
import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from job_processor.services.llm_service import LLMService
from job_processor.config import Config

async def test_extraction():
    # Ensure provider is ollama for testing
    Config.LLM_EXTRACTION_PROVIDER = "ollama"
    
    print(f"Testing LLMService with provider: {Config.LLM_EXTRACTION_PROVIDER}")
    print(f"Ollama Model: {Config.OLLAMA_MODEL}")
    print(f"Ollama Base URL: {Config.OLLAMA_BASE_URL}")

    service = LLMService()
    job_text = """
    Software Engineer at CareerForge. 
    Location: Remote. 
    Salary: $100k - $150k. 
    Requirements: 5 years of Python, experience with FastAPI and MongoDB.
    """
    
    try:
        print("Starting extraction...")
        result = await service.extract_structured_data(job_text)
        print("\nExtraction Result:")
        import json
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"\nExtraction Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_extraction())
