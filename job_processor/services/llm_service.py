
import os
import httpx
import json
import re
from openai import OpenAI
from ollama import AsyncClient
from dotenv import load_dotenv, find_dotenv
from fastapi.concurrency import run_in_threadpool
from job_processor.config import Config
from job_processor.logger import get_logger

load_dotenv(find_dotenv(), override=True)

logger = get_logger("job_processor.llm_service")

class LLMService:
    def __init__(self):
        self.provider = Config.LLM_EXTRACTION_PROVIDER
        logger.info(f"LLMService initialized with provider: '{self.provider}'")
        
        # Initialize OpenAI client for extraction if provider is openai
        if self.provider == "openai":
            self.client = OpenAI(
                base_url=Config.OPENAI_BASE_URL,
                api_key=Config.OPENAI_API_KEY
            )
        elif self.provider == "ollama":
            self.ollama_client = AsyncClient(host=Config.OLLAMA_BASE_URL)
        
    async def extract_structured_data(self, job_text: str) -> dict:
        """
        Extracts structured metadata from job description.
        """
        prompt = f"""You are a JSON-only extraction engine. Output ONLY a single valid JSON object — no explanation, no comments, no markdown, no preamble.

Extract structured metadata and skills from the job description below.
Label all technical skills as "Hard Skill" and all behavioral skills as "Soft Skill".
If a field is unknown or not mentioned, use null.

Required JSON schema (output this exact structure):
{{
  "title": string,
  "company": string or null,
  "location": string or null,
  "remote_friendly": boolean,
  "salary_min": number or null,
  "salary_max": number or null,
  "skills": [
    {{"skill_name": string, "skill_type": "Hard Skill" | "Soft Skill"}}
  ],
  "experience_years": number or null,
  "posted_at": string (ISO-8601) or null,
  "visa_sponsorship": boolean,
  "source_url": string or null
}}

Job Description:
{job_text}

JSON output:"""

        logger.debug(f"Sending extraction prompt to '{self.provider}' (text length: {len(job_text)} chars)")

        if self.provider == "openai":
            return await self._call_openai(prompt)
        elif self.provider == "ollama":
            return await self._call_ollama(prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _generate_openai_sync(self, prompt: str) -> dict:
        """Synchronous OpenAI call — runs inside a thread via run_in_threadpool."""
        api_key = os.getenv("OPENROUTER_API_KEY") or Config.OPENAI_API_KEY
        if not api_key or api_key == "YOUR_OPENROUTER_API_KEY":
            raise ValueError("OpenAI/OpenRouter API key is missing. Set OPENROUTER_API_KEY in your .env file.")

        client = OpenAI(
            api_key=api_key,
            base_url=Config.OPENAI_BASE_URL,
        )
        response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a specialized job data extractor. Always return JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    async def _call_openai(self, prompt: str) -> dict:
        logger.debug(f"Calling OpenAI/OpenRouter model: {Config.OPENAI_MODEL} at {Config.OPENAI_BASE_URL}")
        try:
            result = await run_in_threadpool(self._generate_openai_sync, prompt)
            logger.info("OpenAI extraction successful")
            return result
        except Exception as e:
            logger.error(f"OpenAI extraction failed: {e}", exc_info=True)
            raise



    async def _call_ollama(self, prompt: str) -> dict:
        logger.debug(f"Calling Ollama model '{Config.OLLAMA_MODEL}' at {Config.OLLAMA_BASE_URL}")

        try:
            response = await self.ollama_client.generate(
                model=Config.OLLAMA_MODEL,
                system="You are a JSON-only extraction engine. You MUST output ONLY a single valid JSON object. No prose, no explanation, no markdown fences, no preamble. Just the raw JSON object.",
                prompt=prompt,
                stream=False
            )
            
            # The library returns a Mapping/dict-like object
            if "response" not in response:
                logger.error(f"Ollama returned unexpected response (no 'response' key). Full response: {response}")
                raise KeyError(f"'response' key missing in Ollama output. Got keys: {list(response.keys())}")

            raw_text = response["response"].strip()
            logger.debug(f"Raw Ollama response (first 500 chars): {raw_text[:500]!r}")

            if not raw_text:
                logger.error(f"Ollama returned an empty 'response' string. Full result: {response}")
                raise ValueError("Ollama returned an empty response. The model may have timed out or failed to generate output.")

            # Primary: direct JSON parse
            try:
                parsed = json.loads(raw_text)
                logger.info("Ollama extraction successful")
                return parsed
            except json.JSONDecodeError:
                pass

            # Fallback: robustly extract JSON from reasoning/thinking model output
            extracted = self._extract_json_from_text(raw_text)
            if extracted is not None:
                logger.warning("Ollama response was not pure JSON — extracted JSON block from surrounding text.")
                return extracted

            logger.error(f"Failed to parse JSON from Ollama response. Raw text: {raw_text!r}")
            raise ValueError(f"Could not extract valid JSON from Ollama response: {raw_text[:200]!r}")
        except Exception as e:
            logger.error(f"Ollama extraction failed: {e}", exc_info=True)
            raise

    def _extract_json_from_text(self, text: str) -> dict | None:
        """
        Robustly extract a JSON object from model output that may contain:
        - <think>...</think> reasoning blocks (DeepSeek-R1, Qwen3)
        - Markdown code fences (```json ... ```)
        - Prose preamble before/after the JSON
        Returns the parsed dict, or None if no valid JSON object is found.
        """
        # 1. Strip <think>...</think> blocks produced by reasoning models
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # 2. Try markdown code fence: ```json ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence_match:
            candidate = fence_match.group(1).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # 3. Brace-depth scan — find the outermost {...} block
        #    Works even when prose contains stray braces.
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        # Outer braces found but content invalid — keep scanning
                        next_start = text.find("{", i + 1)
                        if next_start == -1:
                            return None
                        start = next_start
                        depth = 0
        return None
