import os
import logging

import google.generativeai as genai
from typing import Any, Dict
from fastapi.concurrency import run_in_threadpool

from ..exceptions import ProviderError
from .base import Provider
from ...core import settings

logger = logging.getLogger(__name__)


class GenAIProvider(Provider):
    """
    Provider for Google Generative AI (Gemini).
    Note: GenAI is used for LLM generation only, not for embeddings.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = settings.LL_MODEL,
        opts: Dict[str, Any] | None = None,
    ):
        if opts is None:
            opts = {}
        api_key = api_key or settings.LLM_API_KEY or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ProviderError("Google Generative AI API key is missing")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name
        self.opts = opts

    def _generate_sync(self, prompt: str, options: Dict[str, Any]) -> str:
        try:
            # Extract generation config parameters
            generation_config = {}
            allowed_keys = {
                "temperature",
                "top_p",
                "top_k",
                "max_output_tokens",
                "candidate_count",
            }
            
            for key in allowed_keys:
                value = self.opts.get(key)
                if value is not None:
                    generation_config[key] = value
            
            # Update with any runtime options
            for key in allowed_keys:
                if key in options and options[key] is not None:
                    generation_config[key] = options[key]
            
            # Generate response
            if generation_config:
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(**generation_config),
                )
            else:
                response = self.model.generate_content(prompt)
            
            return response.text
        except Exception as e:
            raise ProviderError(f"Google Generative AI - error generating response: {e}") from e

    async def __call__(self, prompt: str, **generation_args: Any) -> str:
        if generation_args:
            logger.warning(f"GenAIProvider - generation_args will be used: {generation_args}")
        
        allowed = {
            "temperature",
            "top_p",
            "top_k",
            "max_output_tokens",
            "candidate_count",
        }
        myopts = {}
        for key in allowed:
            value = self.opts.get(key)
            if value is not None:
                myopts[key] = value
        myopts.update({k: v for k, v in generation_args.items() if k in allowed and v is not None})
        
        return await run_in_threadpool(self._generate_sync, prompt, myopts)
