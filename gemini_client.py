"""
gemini_client.py
-----------------
Talks to Google's Gemini API.

WHAT CHANGED IN BATCH 1 (robustness):
- Request timeout, so a stuck connection can't hang forever.
- Bounded retries: only for errors that are usually temporary
  (overload 5xx, rate limit 429, network drops), max MAX_ATTEMPTS tries
  with a short pause between. Bad API key / bad request / timeout are
  NOT retried (retrying can't fix them).
- Every failure becomes a GeminiRequestError whose text is a short,
  human-readable message, which the sidecar shows directly.
- Empty / blocked responses are caught. Before, response.text could be
  None and main.py crashed on len(None).

SETUP:
1. Free API key: https://aistudio.google.com/apikey
2. PowerShell:  $env:GEMINI_API_KEY="your_key_here"
3. pip install google-genai
"""

import os
import time

from google import genai
from google.genai import errors, types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "PASTE_YOUR_KEY_HERE")
# Same default model as before; override with the OMNISIGHT_MODEL env var if it's ever retired.
MODEL_NAME = os.environ.get("OMNISIGHT_MODEL", "gemini-3.6-flash")

REQUEST_TIMEOUT_SECONDS = 30.0
MAX_ATTEMPTS = 3                      # 1 try + up to 2 retries
RETRY_BACKOFF_SECONDS = (1.0, 2.0)    # pause before retry 1, retry 2

DIRECT_MODE_SYSTEM_INSTRUCTION = """
You are OmniSight, an ambient AI pair-programmer watching a developer's
screen. You will be shown a screenshot of their code editor or terminal,
plus a short question or request from them.

Rules for your response:
- Be direct and concise. No filler, no "Great question!" preambles.
- If you can see an error, name the exact line/cause first, then the fix.
- Give a corrected code snippet only for the relevant lines, not a full
  file rewrite, unless they explicitly ask for the whole file.
- If the screenshot is unclear or you can't read part of the code, say so
  plainly instead of guessing.
- Keep responses short enough to read in a floating sidebar window —
  aim for under 120 words unless the fix genuinely needs more.
"""


class GeminiRequestError(Exception):
    """A failed Gemini request. str(error) is already a user-friendly message."""


def _looks_like_timeout(exc: Exception) -> bool:
    return (
        isinstance(exc, TimeoutError)
        or "timeout" in type(exc).__name__.lower()
        or "timed out" in str(exc).lower()
    )


def _classify(exc: Exception) -> tuple[bool, str]:
    """Returns (retryable, user_message) for any exception from the API call."""
    if isinstance(exc, errors.APIError):
        code = getattr(exc, "code", None)
        detail = str(exc)
        # Gemini reports a bad key as HTTP 400 "API key not valid", not only 401/403.
        if code in (401, 403) or "api key" in detail.lower():
            return False, (
                f"Gemini rejected the API key (HTTP {code}). "
                "Check that GEMINI_API_KEY is set correctly in this terminal."
            )
        if code == 429:
            return True, "Rate limit hit (HTTP 429). Wait a few seconds and try again."
        if code is not None and code >= 500:
            return True, f"Gemini is overloaded or unavailable (HTTP {code}). Try again in a moment."
        return False, f"Gemini rejected the request (HTTP {code}). {detail[:200]}"
    if _looks_like_timeout(exc):  # checked before OSError: TimeoutError is an OSError
        return False, (
            f"The request timed out after {REQUEST_TIMEOUT_SECONDS:.0f} s. "
            "Check your connection and try again."
        )
    if isinstance(exc, OSError):  # includes ConnectionError
        return True, "Network problem reaching Gemini. Check your internet connection."
    return False, f"Unexpected error ({type(exc).__name__}): {str(exc)[:200]}"


def _finish_reason(response) -> str | None:
    candidates = getattr(response, "candidates", None)
    if candidates:
        reason = getattr(candidates[0], "finish_reason", None)
        if reason:
            return str(reason)
    return None


class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY, thinking_level: str = "minimal", sleep_fn=time.sleep):
        if not api_key or api_key == "PASTE_YOUR_KEY_HERE":
            raise ValueError(
                "No Gemini API key set. Get a free one at "
                "https://aistudio.google.com/apikey and set GEMINI_API_KEY."
            )
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(REQUEST_TIMEOUT_SECONDS * 1000)),  # milliseconds
        )
        self.thinking_level = thinking_level
        self._sleep = sleep_fn
        self.last_attempts = 0  # how many tries the most recent request needed

    def ask_direct_mode(self, screenshot_jpeg_bytes: bytes, user_question: str) -> str:
        """
        Sends screenshot + question to Gemini and returns the answer text.
        Raises GeminiRequestError (with a readable message) on any failure.
        """
        prompt = user_question.strip() or (
            "Look at my screen. What's wrong, or what should I do next?"
        )
        image_part = types.Part.from_bytes(data=screenshot_jpeg_bytes, mime_type="image/jpeg")
        config = types.GenerateContentConfig(
            system_instruction=DIRECT_MODE_SYSTEM_INSTRUCTION,
            thinking_config=types.ThinkingConfig(thinking_level=self.thinking_level),
        )

        for attempt in range(1, MAX_ATTEMPTS + 1):
            self.last_attempts = attempt
            try:
                response = self.client.models.generate_content(
                    model=MODEL_NAME, contents=[image_part, prompt], config=config
                )
            except Exception as exc: 
                print(
    f"[Gemini Debug] Type: {type(exc).__name__} | "
    f"Code: {getattr(exc, 'code', 'N/A')} | "
    f"Error: {exc!r}"
)     # noqa: BLE001 — classified below, never swallowed
                retryable, message = _classify(exc)
                if retryable and attempt < MAX_ATTEMPTS:
                    self._sleep(RETRY_BACKOFF_SECONDS[attempt - 1])
                    continue
                if retryable:
                    message += f" (gave up after {attempt} attempts)"
                raise GeminiRequestError(message) from exc

            text = getattr(response, "text", None)
            if not text or not text.strip():
                reason = _finish_reason(response)
                raise GeminiRequestError(
                    "Gemini returned no text"
                    + (f" (finish reason: {reason})" if reason else "")
                    + ". Try asking again."
                )
            return text

        raise GeminiRequestError("Request failed.")  # unreachable; keeps the return type honest


if __name__ == "__main__":
    # Standalone test: screenshot now, ask Gemini, print answer + time.
    from delta_engine import DeltaEngine

    print("Testing Gemini connection... grabbing a screenshot now.")
    engine = DeltaEngine()
    jpeg = engine.grab_screenshot_for_ai()
    client = GeminiClient()

    start = time.time()
    try:
        answer = client.ask_direct_mode(jpeg, "What do you see on my screen?")
        print(f"\nGemini says ({time.time() - start:.1f}s, {client.last_attempts} attempt(s)):\n{answer}")
    except GeminiRequestError as e:
        print(f"\nFailed after {time.time() - start:.1f}s: {e}")
