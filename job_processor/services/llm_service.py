import asyncio
import httpx
import json
import re
from openai import OpenAI
from job_processor.config import Config
from job_processor.logger import get_logger

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

    async def _call_openai(self, prompt: str) -> dict:
        logger.debug(f"Calling OpenAI model: {Config.OPENAI_MODEL}")
        try:
            response = self.client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a specialized job data extractor. Always return JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            logger.info("OpenAI extraction successful")
            return result
        except Exception as e:
            logger.error(f"OpenAI extraction failed: {e}", exc_info=True)
            raise

    async def _wait_for_gpu_idle(
        self,
        threshold: int = 20,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
    ) -> None:
        """
        Block (asynchronously) until GPU utilization drops to *threshold* % or below.
        Falls back silently if CUDA is not available (CPU-only or no nvidia-smi).

        :param threshold:     Maximum GPU % load to accept before proceeding.
        :param poll_interval: Seconds between consecutive polls.
        :param timeout:       Give up waiting after this many seconds and proceed anyway.
        """
        try:
            import torch
            if not torch.cuda.is_available():
                return  # no GPU — nothing to wait for
        except ImportError:
            return

        elapsed = 0.0
        while elapsed < timeout:
            utilization = torch.cuda.utilization()  # integer 0-100
            logger.debug(f"GPU utilization: {utilization}% (threshold: {threshold}%)")
            if utilization <= threshold:
                logger.info(f"GPU at {utilization}% — proceeding with Ollama call.")
                return
            logger.info(
                f"GPU busy at {utilization}% (> {threshold}%). "
                f"Waiting {poll_interval}s before retrying …"
            )
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        logger.warning(
            f"GPU did not drop below {threshold}% within {timeout}s — proceeding anyway."
        )

    async def _call_ollama(self, prompt: str) -> dict:
        url = f"{Config.OLLAMA_BASE_URL}/api/generate"
        logger.debug(f"Calling Ollama model '{Config.OLLAMA_MODEL}' at {url}")
        await self._wait_for_gpu_idle(threshold=20, poll_interval=5.0, timeout=300.0)
        payload = {
            "model": Config.OLLAMA_MODEL,
            "system": "You are a JSON-only extraction engine. You MUST output ONLY a single valid JSON object. No prose, no explanation, no markdown fences, no preamble. Just the raw JSON object.",
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=6000.0)
                response.raise_for_status()
                result = response.json()

            if "response" not in result:
                logger.error(f"Ollama returned unexpected response (no 'response' key). Full response: {result}")
                raise KeyError(f"'response' key missing in Ollama output. Got keys: {list(result.keys())}")

            raw_text = result["response"].strip()
            logger.debug(f"Raw Ollama response (first 500 chars): {raw_text[:500]!r}")

            if not raw_text:
                logger.error(f"Ollama returned an empty 'response' string. Full result: {result}")
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
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error {e.response.status_code}: {e.response.text}", exc_info=True)
            raise
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse JSON from Ollama response: {e}", exc_info=True)
            raise
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
