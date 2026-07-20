"""
LangChain LLM factory — one stateless chat model per call.

Routing by model_id prefix:
  gemini-*               → ChatGoogleGenerativeAI  (Google AI Studio, free, vision ✓)
  gemma-*                → ChatGoogleGenerativeAI  (Google AI Studio, free, text-only)
  gemma2-*               → ChatGroq                (Groq free tier, text-only)
  llama-*                → ChatGroq                (Groq free tier, text-only)
  meta-llama/llama-4-*   → ChatGroq                (Groq free tier, vision ✓)
  qwen/*                 → ChatGroq                (Groq free tier, qwen3.6-27b has vision ✓)
  mixtral-*              → ChatGroq                (Groq free tier, text-only)
  gpt-*                  → ChatOpenAI              (paid, vision ✓)
  claude-*               → ChatAnthropic           (paid, vision ✓)

Groq deprecates models on short notice (see console.groq.com/docs/deprecations) —
if a model_id here starts failing with `model_decommissioned`, check
console.groq.com/docs/models for its replacement before assuming it's a bug.
"""

from __future__ import annotations
from langchain_core.language_models.chat_models import BaseChatModel
from app.core.config import settings

_GEMINI_TEMPERATURE = 0.0

_GEMINI_MODEL_ALIASES: dict[str, str] = {
    "gemini-1.5-flash": "gemini-2.5-flash",
    "gemini-1.5-pro": "gemini-2.5-pro",
    "gemini-2.0-flash": "gemini-2.5-flash",
    "gemini-2.0-flash-lite": "gemini-2.5-flash-lite",
}

# Models that cannot process images — image attachment is silently skipped for these.
_TEXT_ONLY_MODELS: frozenset[str] = frozenset({
    "gemma-2-9b-it",
    "gemma2-9b-it",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
})


def is_vision_capable(model_id: str) -> bool:
    """Return False for text-only models so callers can skip image attachment."""
    return model_id not in _TEXT_ONLY_MODELS


def get_llm(model_id: str) -> BaseChatModel:
    model_id = _GEMINI_MODEL_ALIASES.get(model_id, model_id)
    m = model_id.lower()

    # ── Google AI Studio (Gemini + Gemma via Google) ──────────────────────────
    if m.startswith("gemini") or (m.startswith("gemma") and not m.startswith("gemma2")):
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_id,
            google_api_key=settings.google_api_key,
            temperature=_GEMINI_TEMPERATURE,
            # Ask for JSON when the model supports it.
            generation_config={"response_mime_type": "application/json"} if m.startswith("gemini") else {},
        )

    # ── Groq (Llama, Gemma2, Mixtral, Qwen) ───────────────────────────────────
    if (
        m.startswith("llama")
        or m.startswith("meta-llama/")
        or m.startswith("gemma2")
        or m.startswith("mixtral")
        or m.startswith("qwen")
    ):
        from langchain_groq import ChatGroq
        model_kwargs = {}
        if m.startswith("qwen"):
            # qwen3.6-27b is a reasoning model that otherwise emits a
            # <think>...</think> chain-of-thought as part of response.content
            # before the actual JSON answer — long enough that it was
            # exhausting the turn before the JSON ever got emitted, breaking
            # _extract_json downstream. "none" skips thinking mode entirely
            # rather than just hiding it, since this task needs a direct
            # structured answer, not step-by-step reasoning. Installed groq
            # SDK (0.9.0) predates reasoning_effort as a typed create() param,
            # so it has to go through extra_body (its documented passthrough
            # for provider-specific params) rather than as a bare model_kwarg.
            model_kwargs["extra_body"] = {"reasoning_effort": "none"}
        return ChatGroq(
            model=model_id,
            api_key=settings.groq_api_key,
            max_tokens=None,
            model_kwargs=model_kwargs,
        )

    # ── OpenAI (paid) ──────────────────────────────────────────────────────────
    if m.startswith("gpt"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_id,
            api_key=settings.openai_api_key,
            max_tokens=None,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

    # ── Anthropic (paid) ───────────────────────────────────────────────────────
    if m.startswith("claude"):
        from langchain_anthropic import ChatAnthropic
        # Unlike ChatOpenAI/ChatGoogleGenerativeAI, ChatAnthropic's installed
        # version rejects max_tokens=None outright (pydantic validation error)
        # instead of treating it as "no explicit limit" — it needs a real value.
        return ChatAnthropic(
            model=model_id,
            api_key=settings.anthropic_api_key,
            max_tokens=8192,
        )

    raise ValueError(
        f"Unknown model_id: {model_id!r}. "
        "Expected prefix: gemini-, gemma-, gemma2-, llama-, mixtral-, gpt-, claude-"
    )
