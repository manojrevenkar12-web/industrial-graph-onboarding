"""Real model adapters: Claude (Messages API) and any OpenAI-compatible endpoint (Azure OpenAI, vLLM, a gateway).

They implement the same two reads the simulated model does: find the words in a text that name a machine, and read a
maintenance question. Each asks for one JSON object and parses it strictly; anything else comes back as "no reading",
which code treats as nothing found. Prompts carry the text only; ids stay in code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx

MENTION_PROMPT = (
    "Find the equipment this text from an industrial plant refers to (a pump, compressor, exchanger, vessel or fan, "
    "with its number). Copy the words exactly as written.\n"
    'Reply with JSON only: {{"quote": "<words copied from the text, or null>", "confidence": <0-1>}}.\n'
    "Text: {text}"
)
QUESTION_PROMPT = (
    "A maintenance engineer asks a question about a plant. Intents: sensors, last_corrective, vibration_trend, "
    "most_corrective.\n"
    'Reply with JSON only: {{"intent": "<intent>", "entity": "<words naming the machine, copied, or null>", '
    '"unit": <unit number or null>, "confidence": <0-1>}}.\n'
    "Question: {text}"
)


def parse(raw: str, keys: tuple[str, ...]) -> dict | None:
    try:
        start, end = raw.index("{"), raw.rindex("}") + 1
        obj = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(obj, dict) or any(k not in obj for k in keys):
        return None
    return obj


class _Base:
    calls: int

    def _ask(self, prompt: str) -> str:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def mention(self, text: str, key: str) -> dict:
        self.calls += 1
        obj = parse(self._ask(MENTION_PROMPT.format(text=text)), ("quote",))
        if obj is None or not isinstance(obj.get("quote"), str | type(None)):
            return {"quote": None, "confidence": 0.0}
        return {"quote": obj["quote"], "confidence": float(obj.get("confidence") or 0.0)}

    def read_question(self, text: str, key: str) -> dict:
        self.calls += 1
        obj = parse(self._ask(QUESTION_PROMPT.format(text=text)), ("intent", "entity"))
        if obj is None:
            return {"intent": None, "entity": None, "unit": None, "confidence": 0.0}
        unit = obj.get("unit")
        return {
            "intent": obj.get("intent"),
            "entity": obj.get("entity"),
            "unit": int(unit) if isinstance(unit, int | str) and str(unit).isdigit() else None,
            "confidence": float(obj.get("confidence") or 0.0),
        }


@dataclass
class ClaudeReader(_Base):
    api_key: str
    model: str = "claude-sonnet-5-5"
    url: str = "https://api.anthropic.com/v1/messages"
    client: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=30))
    calls: int = 0

    def _ask(self, prompt: str) -> str:
        r = self.client.post(
            self.url,
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            json={"model": self.model, "max_tokens": 200, "messages": [{"role": "user", "content": prompt}]},
        )
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))


@dataclass
class OpenAICompatibleReader(_Base):
    base_url: str
    api_key: str
    model: str
    client: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=30))
    calls: int = 0

    def _ask(self, prompt: str) -> str:
        r = self.client.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers={"authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]},
        )
        r.raise_for_status()
        return str(r.json()["choices"][0]["message"]["content"])
