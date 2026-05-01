"""
Unified AI client — supports Google Gemini (free) and Anthropic Claude (paid).

Usage:
    client = AIClient.from_env()          # reads AI_PROVIDER from .env
    text   = client.generate(system, user)
"""
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Default models per provider
_DEFAULTS = {
    "gemini":    "models/gemini-2.5-flash",   # free tier — latest stable flash
    "anthropic": "claude-sonnet-4-6",
}


class AIClient:
    def __init__(self, provider: str, api_key: str, model: Optional[str] = None):
        self.provider = provider.lower().strip()
        self.api_key  = api_key
        self.model    = model or _DEFAULTS.get(self.provider, "")

        if self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "anthropic":
            self._init_anthropic()
        else:
            raise ValueError(f"Unknown AI provider: '{provider}'. Use 'gemini' or 'anthropic'.")

    # ── Factory ───────────────────────────────────────────────────────────────
    @classmethod
    def from_env(cls) -> "AIClient":
        provider = os.getenv("AI_PROVIDER", "gemini").lower()
        if provider == "gemini":
            key = os.getenv("GOOGLE_API_KEY", "")
        else:
            key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            raise RuntimeError(
                f"No API key found for provider '{provider}'. "
                "Check your .env file."
            )
        return cls(provider=provider, api_key=key)

    @classmethod
    def from_keys(
        cls,
        provider: str,
        google_key: str = "",
        anthropic_key: str = "",
        model: Optional[str] = None,
    ) -> "AIClient":
        key = google_key if provider == "gemini" else anthropic_key
        return cls(provider=provider, api_key=key, model=model)

    # ── Provider init ─────────────────────────────────────────────────────────
    def _init_gemini(self):
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError:
            raise ImportError("google-genai is required: pip install google-genai")
        self._genai_client = genai.Client(api_key=self.api_key)
        self._genai_types  = genai_types
        logger.info(f"Gemini client ready — model: {self.model}")

    def _init_anthropic(self):
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic is required: pip install anthropic")
        self._anthropic = anthropic.Anthropic(api_key=self.api_key)
        logger.info(f"Anthropic client ready — model: {self.model}")

    # ── Core generate method ──────────────────────────────────────────────────
    def generate(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
        retries: int = 3,
    ) -> str:
        """
        Generate text from a system + user prompt.
        Automatically retries on rate-limit (429) errors with exponential back-off.
        """
        for attempt in range(1, retries + 1):
            try:
                if self.provider == "gemini":
                    return self._gemini_generate(system, user, max_tokens)
                else:
                    return self._anthropic_generate(system, user, max_tokens)
            except Exception as e:
                err = str(e).lower()
                is_rate_limit = "429" in err or "quota" in err or "rate" in err
                if is_rate_limit and attempt < retries:
                    wait = 2 ** attempt  # 2, 4 seconds
                    logger.warning(f"Rate limit hit, retrying in {wait}s… (attempt {attempt})")
                    time.sleep(wait)
                else:
                    raise

    # ── Gemini backend ────────────────────────────────────────────────────────
    _GEMINI_FALLBACK_ORDER = [
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash",
        "models/gemini-2.0-flash-lite",
    ]

    def _gemini_generate(self, system: str, user: str, max_tokens: int) -> str:
        types = self._genai_types
        models_to_try = (
            [self.model]
            + [m for m in self._GEMINI_FALLBACK_ORDER if m != self.model]
        )
        last_err = None
        for model_name in models_to_try:
            try:
                response = self._genai_client.models.generate_content(
                    model=model_name,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        max_output_tokens=max_tokens,
                        temperature=0.2,
                    ),
                    contents=user,
                )
                if model_name != self.model:
                    logger.info(f"Using fallback Gemini model: {model_name}")
                return response.text.strip()
            except Exception as e:
                err = str(e)
                if "429" in err or "quota" in err.lower() or "exhausted" in err.lower():
                    last_err = e
                    logger.warning(f"Quota hit for {model_name}, trying next model…")
                    continue
                raise
        raise RuntimeError(
            f"All Gemini models quota-exhausted. Try again in 24h. Last error: {last_err}"
        )

    # ── Anthropic backend ─────────────────────────────────────────────────────
    def _anthropic_generate(self, system: str, user: str, max_tokens: int) -> str:
        response = self._anthropic.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text.strip()

    # ── Convenience ───────────────────────────────────────────────────────────
    @property
    def provider_label(self) -> str:
        labels = {
            "gemini": f"Google Gemini ({self.model})",
            "anthropic": f"Anthropic Claude ({self.model})",
        }
        return labels.get(self.provider, self.provider)
