import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # MongoDB
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/careerforge")
    DB_NAME = os.getenv("DB_NAME", "careerforge")
    
    # LLM Provider for Extraction: 'openai' or 'ollama'
    LLM_EXTRACTION_PROVIDER = os.getenv("LLM_EXTRACTION_PROVIDER", "ollama").lower()
    
    # OpenAI / OpenRouter
    OPENAI_API_KEY = os.getenv("OPENROUTER_API_KEY", "YOUR_OPENROUTER_API_KEY")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-oss-20b")
    
    # Ollama
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
    
    # Embedding Models
    DENSE_EMBEDDING_MODEL = "text-embedding-3-small"
    SPLADE_MODEL_ID = "naver/splade-cocondenser-ensembledistil"
