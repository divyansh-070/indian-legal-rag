"""
LLM Service — Wrapper for Groq/OpenAI-compatible LLM APIs.
Supports primary model + fallback with structured output parsing.
"""

import json
import os
import asyncio
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from api.config import settings


T = TypeVar("T", bound=BaseModel)


class LLMService:
    """Async LLM client compatible with Groq / OpenAI-style APIs."""
    
    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        fallback_model: str = None,
        timeout: float = 120.0,
    ):
        self.base_url = (base_url or settings.OLLAMA_HOST).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.fallback_model = fallback_model or settings.OLLAMA_FALLBACK_MODEL
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        # Auth: check for GROQ_API_KEY or OPENROUTER_API_KEY in settings / env
        self.api_key = (
            getattr(settings, "GROQ_API_KEY", "")
            or os.getenv("GROQ_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or ""
        )
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(timeout=self.timeout, headers=headers)
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.1,
        max_tokens: int = None,
        max_retries: int = 4,
    ) -> str:
        """Call the OpenAI-compatible /chat/completions endpoint with automatic 429 backoff."""
        client = await self._get_client()
        model = model or self.model
        
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        url = f"{self.base_url}/chat/completions"
        
        for attempt in range(max_retries):
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            
            # Handle rate limit (HTTP 429) gracefully
            if response.status_code == 429 and attempt < max_retries - 1:
                wait_seconds = 7.0
                try:
                    if "retry-after" in response.headers:
                        wait_seconds = float(response.headers["retry-after"]) + 0.5
                    else:
                        import re
                        msg = response.json().get("error", {}).get("message", "")
                        match = re.search(r"try again in ([\d\.]+)s", msg)
                        if match:
                            wait_seconds = float(match.group(1)) + 1.0
                except Exception:
                    pass
                
                print(f"[RATE LIMIT] Groq 429 limit hit. Waiting {wait_seconds:.1f}s before retry (attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(wait_seconds)
                continue
            
            error_body = response.text
            print(f"[ERROR] LLM API error: HTTP {response.status_code} from {url}")
            print(f"   Model: {model}")
            print(f"   API Key configured: {'Yes (' + self.api_key[:8] + '...)' if self.api_key else 'NO — MISSING!'}")
            print(f"   Response: {error_body[:500]}")
            response.raise_for_status()
    
    async def generate(
        self,
        prompt: str,
        system: str = None,
        model: str = None,
        use_fallback: bool = True,
    ) -> str:
        """Generate text response."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        try:
            return await self._chat_completion(messages, model=model)
        except Exception as e:
            if use_fallback and model != self.fallback_model:
                return await self._chat_completion(messages, model=self.fallback_model)
            raise
    
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system: str = None,
        model: str = None,
        use_fallback: bool = True,
        max_retries: int = 2,
    ) -> T:
        """Generate and parse structured output using Pydantic model."""
        schema = response_model.model_json_schema()
        format_prompt = f"""\
{prompt}

Respond ONLY with valid JSON matching this schema:
{json.dumps(schema, indent=2)}"""
        
        json_system = (system or "") + "\nYou MUST respond with valid JSON only. No markdown, no explanation."
        
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = await self.generate(
                    format_prompt,
                    system=json_system.strip(),
                    model=model,
                    use_fallback=use_fallback,
                )
                
                json_str = self._extract_json(response)
                data = json.loads(json_str)
                return response_model(**data)
                
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                if attempt < max_retries:
                    format_prompt += f"\n\nPREVIOUS RESPONSE WAS INVALID JSON. ERROR: {e}. Please output ONLY valid JSON."
                continue
        
        raise ValueError(f"Failed to generate valid structured output after {max_retries + 1} attempts. Last error: {last_error}")
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from response (handles markdown code fences)."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        use_fallback: bool = True,
    ) -> str:
        """Chat completion with message history."""
        try:
            return await self._chat_completion(messages, model=model)
        except Exception as e:
            if use_fallback and model != self.fallback_model:
                return await self._chat_completion(messages, model=self.fallback_model)
            raise
    
    async def embed(self, text: str, model: str = "nomic-embed-text") -> List[float]:
        """Generate embeddings (Ollama-compatible endpoint)."""
        client = await self._get_client()
        
        response = await client.post(
            f"{self.base_url}/embeddings",
            json={"model": model, "input": text},
        )
        response.raise_for_status()
        data = response.json()
        # Handle both OpenAI and Ollama response formats
        if "data" in data:
            return data["data"][0]["embedding"]
        return data.get("embedding", [])


# Global instance
llm_service = LLMService()