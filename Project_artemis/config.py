import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Project Artemis"
    
    # MongoDB settings
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "careerforge"
    
    # Ollama settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "openai/gpt-oss-safeguard-20b"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()
