from __future__ import annotations

import httpx

from app.providers.base import AIProvider, RawResult, parse_int

# En-têtes de limite exposés par certains fournisseurs ; absents => métrique indisponible (R1).
_RATE_HEADERS = {
    "x-ratelimit-remaining-requests": "remaining_requests",
    "x-ratelimit-remaining-tokens": "remaining_tokens",
    "x-ratelimit-reset-requests": "reset_requests",
    "x-ratelimit-reset-tokens": "reset_tokens",
}


class OpenAICompatibleProvider(AIProvider):
    def __init__(
        self,
        provider_id: str,
        model: str,
        base_url: str,
        api_key: str,
        data_sensitivity: tuple[str, ...],
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(provider_id, model, data_sensitivity)
        self._base = base_url.rstrip("/")
        self._api_key = api_key  # reste en mémoire backend, jamais sérialisé (R2)
        self._client = client or httpx.AsyncClient(timeout=60)

    def __repr__(self) -> str:
        return f"OpenAICompatibleProvider(id={self.id!r}, model={self.model!r})"

    async def _call(self, prompt: str) -> RawResult:
        resp = await self._client.post(
            f"{self._base}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}]},
        )
        resp.raise_for_status()
        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("reponse_invalide") from exc
        if not isinstance(text, str):
            raise ValueError("reponse_invalide")
        usage = data.get("usage") if isinstance(data, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        headers = {
            name: resp.headers[header]
            for header, name in _RATE_HEADERS.items()
            if header in resp.headers
        }
        return RawResult(
            text=text,
            input_tokens=parse_int(usage.get("prompt_tokens")),
            output_tokens=parse_int(usage.get("completion_tokens")),
            headers=headers,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
