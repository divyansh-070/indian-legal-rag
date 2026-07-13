"""
LLM Service — Wrapper around Ollama for local LLM inference.
Supports primary model + fallback with structured output parsing.
"""

import json
import asyncio
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from api.config import settings


T = TypeVar("T", bound=BaseModel)


class LLMService:
    """Async Ollama client with structured output support."""
    
    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        fallback_model: str = None,
        timeout: float = 120.0,
    ):
        self.base_url = base_url or settings.OLLAMA_HOST
        self.model = model or settings.OLLAMA_MODEL
        self.fallback_model = fallback_model or settings.OLLAMA_FALLBACK_MODEL
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _generate_raw(
        self,
        prompt: str,
        model: str = None,
        system: str = None,
        format: str = None,
        options: Dict = None,
    ) -> str:
        """Raw generation call to Ollama."""
        client = await self._get_client()
        model = model or self.model
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options or {"temperature": 0.1, "top_p": 0.9},
        }
        
        if system:
            payload["system"] = system
        if format:
            payload["format"] = format
        
        response = await client.post(
            f"{self.base_url}/api/generate",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")
    
    async def generate(
        self,
        prompt: str,
        system: str = None,
        model: str = None,
        use_fallback: bool = True,
    ) -> str:
        """Generate text response."""
        try:
            return await self._generate_raw(prompt, model=model, system=system)
        except Exception as e:
            if use_fallback and model != self.fallback_model:
                return await self._generate_raw(prompt, model=self.fallback_model, system=system)
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
        # Build format schema from Pydantic model
        schema = response_model.model_json_schema()
        format_prompt = f"""
{prompt}

Respond ONLY with valid JSON matching this schema:
{json.dumps(schema, indent=2)}
"""
        
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = await self.generate(
                    format_prompt,
                    system=system,
                    model=model,
                    use_fallback=use_fallback,
                )
                
                # Extract JSON from response
                json_str = self._extract_json(response)
                data = json.loads(json_str)
                return response_model(**data)
                
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                if attempt < max_retries:
                    # Add correction hint
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
        client = await self._get_client()
        model = model or self.model
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.1, "top_p": 0.9},
        }
        
        try:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")
        except Exception as e:
            if use_fallback and model != self.fallback_model:
                return await self.chat(messages, model=self.fallback_model, use_fallback=False)
            raise
    
    async def embed(self, text: str, model: str = "nomic-embed-text") -> List[float]:
        """Generate embeddings using Ollama."""
        client = await self._get_client()
        
        response = await client.post(
            f"{self.base_url}/api/embeddings",
            json={"model": model, "prompt": text},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("embedding", [])


# Global instance
llm_service = LLMService()