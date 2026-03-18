from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


class OpenRouterError(RuntimeError):
    pass


def _load_dotenv_if_present() -> None:
    """
    Minimal .env loader for local development.
    - Loads `backend/.env` if present
    - Does not override already-set environment variables
    """
    backend_root = Path(__file__).resolve().parents[2]
    env_path = backend_root / ".env"
    if not env_path.exists():
        return

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


@dataclass
class OpenRouterClient:
    api_key: str
    model: str = "google/gemini-2.0-flash-001"
    timeout_s: float = 60.0
    base_url: str = "https://openrouter.ai/api/v1"

    @classmethod
    def from_env(cls) -> "OpenRouterClient":
        _load_dotenv_if_present()
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise OpenRouterError("Missing OPENROUTER_API_KEY environment variable.")
        model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        return cls(api_key=api_key, model=model, base_url=base_url)

    async def generate_text(self, *, system: str, user: str) -> str:
        async def _call() -> dict[str, Any]:
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                # Optional, but recommended by OpenRouter for attribution/metrics.
                "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost"),
                "X-Title": os.getenv("OPENROUTER_APP_TITLE", "Conversational BI"),
            }
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
                "top_p": 0.9,
                "max_tokens": 4096,
            }

            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise OpenRouterError(f"OpenRouter API error {resp.status_code}: {resp.text}")
                return resp.json()

        async def _call_with_retries() -> dict[str, Any]:
            delays = [0.3, 1.0, 2.0]
            last: Exception | None = None
            for i in range(len(delays) + 1):
                try:
                    return await _call()
                except OpenRouterError as e:
                    last = e
                    s = str(e)
                    if any(code in s for code in ("OpenRouter API error 429", "OpenRouter API error 503")):
                        if i < len(delays):
                            await asyncio.sleep(delays[i])
                            continue
                    raise
            assert last is not None
            raise last

        data = await _call_with_retries()
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise OpenRouterError(f"Unexpected OpenRouter response shape: {data}") from e

