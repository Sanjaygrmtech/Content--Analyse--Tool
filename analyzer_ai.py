from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

import google.generativeai as genai

from prompts import build_analysis_prompt

MODEL_NAME = "gemini-2.0-flash"


def configure_gemini(api_key: str):
    """Configures Gemini client with provided API key."""
    if not api_key or not api_key.strip():
        raise ValueError("Gemini API key is required.")
    genai.configure(api_key=api_key.strip())


def _extract_json_text(response: Any) -> str:
    text = getattr(response, "text", "") or ""
    if text.strip():
        return text.strip()

    candidates = getattr(response, "candidates", []) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", []) if content else []
        part_text = "".join(getattr(part, "text", "") for part in parts).strip()
        if part_text:
            return part_text
    return ""


def run_ai_analysis(
    my_content: dict[str, Any],
    competitor_contents: list[dict[str, Any]],
    keyword: str,
    rule_results: dict[str, Any],
) -> dict[str, Any]:
    """Runs Gemini analysis, retries JSON parsing failures up to 2 times, with 60s timeout."""
    try:
        prompt = build_analysis_prompt(my_content, competitor_contents, keyword, rule_results)
        model = genai.GenerativeModel(MODEL_NAME)
    except Exception as exc:
        return {"error": f"Failed to prepare AI analysis: {exc}"}

    max_attempts = 3
    last_error = "Unknown AI error"

    for attempt in range(1, max_attempts + 1):
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    model.generate_content,
                    prompt,
                    generation_config={"temperature": 0.2, "response_mime_type": "application/json"},
                )
                response = future.result(timeout=60)

            response_text = _extract_json_text(response)
            if not response_text:
                last_error = "Empty AI response."
                continue

            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                return parsed
            last_error = "AI response was valid JSON but not an object."

        except FuturesTimeoutError:
            last_error = "Gemini request timed out after 60 seconds."
        except json.JSONDecodeError as exc:
            last_error = f"Invalid JSON from AI (attempt {attempt}): {exc}"
        except Exception as exc:
            last_error = f"Gemini request failed (attempt {attempt}): {exc}"

    return {"error": last_error}
