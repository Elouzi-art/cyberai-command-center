from __future__ import annotations

import httpx

from app.providers.base import AIProvider, RawResult, parse_int


class OllamaProvider(AIProvider):
    def __init__(
        self,
        provider_id: str,
        model: str,
        base_url: str,
        data_sensitivity: tuple[str, ...],
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(provider_id, model, data_sensitivity)
        self._base = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=120)

    async def _call(self, prompt: str) -> RawResult:
        resp = await self._client.post(
            f"{self._base}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response") if isinstance(data, dict) else None
        if not isinstance(text, str):
            raise ValueError("reponse_invalide")
        return RawResult(
            text=text,
            input_tokens=parse_int(data.get("prompt_eval_count")),
            output_tokens=parse_int(data.get("eval_count")),
        )

    async def aclose(self) -> None:
        await self._client.aclose()
