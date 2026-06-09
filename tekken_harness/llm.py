"""
LLM backend abstraction: Anthropic API or any OpenAI-compatible endpoint.

Select with env vars:

  TEKKEN_AGENT_BACKEND = "anthropic" (default) | "openai"
  TEKKEN_AGENT_MODEL   = model name for whichever backend

Anthropic backend:
  ANTHROPIC_API_KEY

OpenAI-compatible backend (OpenRouter, Ollama, vLLM, LM Studio, llama.cpp...):
  OPENAI_BASE_URL  e.g. http://localhost:11434/v1   (Ollama)
                        http://localhost:1234/v1    (LM Studio)
                        https://openrouter.ai/api/v1
  OPENAI_API_KEY   any non-empty string for local servers (e.g. "ollama")

The model MUST be vision-capable (e.g. gpt-4o, qwen2.5-vl, llava, gemma3,
minicpm-v). Text-only models can't see the game.
"""

from __future__ import annotations

import os


def _backend_name() -> str:
    return os.environ.get("TEKKEN_AGENT_BACKEND", "anthropic").lower()


def default_model() -> str:
    if m := os.environ.get("TEKKEN_AGENT_MODEL"):
        return m
    return "claude-sonnet-4-5" if _backend_name() == "anthropic" else "gpt-4o-mini"


class LLM:
    """Unified interface: complete(system, text, image_b64, media_type) -> str."""

    def __init__(self, model: str | None = None, max_tokens: int = 400):
        self.backend = _backend_name()
        self.model = model or default_model()
        self.max_tokens = max_tokens

        if self.backend == "anthropic":
            import anthropic
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise SystemExit("Set ANTHROPIC_API_KEY (or TEKKEN_AGENT_BACKEND=openai).")
            self.client = anthropic.Anthropic()
        elif self.backend == "openai":
            from openai import OpenAI
            base_url = os.environ.get("OPENAI_BASE_URL")
            api_key = os.environ.get("OPENAI_API_KEY", "not-needed")
            if not base_url and api_key == "not-needed":
                raise SystemExit("Set OPENAI_BASE_URL (and OPENAI_API_KEY if the server requires one).")
            self.client = OpenAI(base_url=base_url, api_key=api_key)
        else:
            raise SystemExit(f"Unknown TEKKEN_AGENT_BACKEND: {self.backend!r}")

    def complete(self, system: str, text: str, image_b64: str, media_type: str) -> str:
        if self.backend == "anthropic":
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image",
                         "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                        {"type": "text", "text": text},
                    ],
                }],
            )
            return "".join(b.text for b in msg.content if b.type == "text")

        # OpenAI-compatible: images go as data-URI image_url parts.
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                    {"type": "text", "text": text},
                ]},
            ],
        )
        return resp.choices[0].message.content or ""
