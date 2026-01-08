import os
import logging

from openai import OpenAI
from typing import Any, Dict
from fastapi.concurrency import run_in_threadpool
from dotenv import load_dotenv
from ..exceptions import ProviderError
from .base import Provider, EmbeddingProvider
from ...core import settings

logger = logging.getLogger(__name__)
load_dotenv()

class OpenAIProvider(Provider):
    def __init__(self, api_key: str | None = None, model_name: str = settings.LL_MODEL,
                 opts: Dict[str, Any] = None):
        if opts is None:
            opts = {}
        
        # Ensure 12k is the default if not provided in opts
        if "max_tokens" not in opts and "max_output_tokens" not in opts:
            opts["max_tokens"] = 12000
            
        api_key = api_key or settings.LLM_API_KEY or os.getenv("OPENAI_API_KEY")
        print("APIKEY",api_key)
        if not api_key:
            raise ProviderError("OpenAI API key is missing")
            
        self._client = OpenAI(api_key=api_key, base_url=settings.LLM_BASE_URL)
        self.model = model_name
        self.opts = opts
        self.instructions = ""

    def _generate_sync(self, prompt: str, options: Dict[str, Any]) -> str:
        try:
            # Note: Using standard chat.completions for OpenRouter/OpenAI compatibility
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.instructions},
                    {"role": "user", "content": prompt}
                ],
                **options,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise ProviderError(f"OpenAI - error generating response: {e}") from e

    async def __call__(self, prompt: str, **generation_args: Any) -> str:
        # Define allowed keys for the API
        allowed = {
            "temperature",
            "top_p",
            "max_tokens", # Added this
            "max_output_tokens", # Keep for internal compatibility
            "verbosity",
            "reasoning_effort",
            "grammar",
            "extra_headers",
        }
        
        myopts = {}
        # Merge self.opts and generation_args
        combined_args = {**self.opts, **generation_args}
        
        for key in allowed:
            value = combined_args.get(key)
            if value is not None:
                # Map 'max_output_tokens' to 'max_tokens' for the OpenAI Client
                if key == "max_output_tokens":
                    myopts["max_tokens"] = value
                else:
                    myopts[key] = value

        return await run_in_threadpool(self._generate_sync, prompt, myopts)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str | None = None,
        embedding_model: str = settings.EMBEDDING_MODEL,
    ):
        api_key = api_key or settings.EMBEDDING_API_KEY or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ProviderError("OpenAI API key is missing")
        self._client = OpenAI(api_key=api_key)
        self._model = embedding_model

    async def embed(self, text: str) -> list[float]:
        try:
            response = await run_in_threadpool(
                self._client.embeddings.create, input=text, model=self._model
            )
            return response.data[0].embedding
        except Exception as e:
            raise ProviderError(f"OpenAI - error generating embedding: {e}") from e
