"""Generate ready-to-publish product posts with a local Ollama model."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List


DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
OLLAMA_TIMEOUT_SECONDS = 120


class OllamaError(RuntimeError):
    """An actionable error from the local Ollama service or its response."""


@dataclass(frozen=True)
class PostDraft:
    """Structured post data returned by the model."""

    product_name: str
    characteristics: List[str]
    call_to_action: str


def build_prompt(source_text: str, language: str = "English") -> str:
    """Build a constrained prompt for extracting social-post copy."""
    language_instruction = (
        "the same language as the source text" if language == "Source language" else language
    )
    return f"""You are a technical product copywriter for an industrial products company.
Read the product information between SOURCE tags and create a short social-media post.

Return ONLY a valid JSON object with exactly these keys:
{{
  "product_name": "short product name",
  "characteristics": ["characteristic 1", "characteristic 2", "characteristic 3"],
  "call_to_action": "a concise invitation to contact us"
}}

Rules:
- The characteristics array must contain exactly three concise items.
- Use only facts present in the source. Do not invent specifications, certifications,
  prices, availability, or applications.
- Write the post copy in {language_instruction}. Keep a product name that is clear and specific.
- The call to action must invite the reader to contact us or send a direct message.
- Do not include Markdown, emojis, or any text outside the JSON object.

<SOURCE>
{source_text.strip()}
</SOURCE>
"""


def generate_social_post(
    source_text: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
    language: str = "English",
) -> str:
    """Send product information to Ollama and return formatted post text."""
    if not source_text.strip():
        raise ValueError("Paste product information before generating a post.")

    selected_model = (model if model is not None else DEFAULT_OLLAMA_MODEL).strip()
    selected_url = (base_url if base_url is not None else DEFAULT_OLLAMA_URL).strip()
    if not selected_model:
        raise ValueError("Enter an Ollama model name.")
    if not selected_url:
        raise ValueError("Enter an Ollama server URL.")

    request_body = json.dumps(
        {
            "model": selected_model,
            "prompt": build_prompt(source_text, language),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        }
    ).encode("utf-8")
    try:
        request = urllib.request.Request(
            f"{selected_url.rstrip('/')}/api/generate",
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace").strip()
        suffix = f": {detail}" if detail else ""
        raise OllamaError(f"Ollama returned HTTP {error.code}{suffix}") from error
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError) as error:
        raise OllamaError(
            f"Could not connect to Ollama at {selected_url}. "
            "Start Ollama and confirm the server URL."
        ) from error

    try:
        ollama_payload = json.loads(response_body)
        model_response = ollama_payload["response"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise OllamaError("Ollama returned an unexpected response.") from error

    draft = parse_post_response(model_response)
    return format_post(draft)


def parse_post_response(model_response: Any) -> PostDraft:
    """Validate the JSON object emitted by Ollama."""
    if not isinstance(model_response, str):
        raise OllamaError("Ollama returned a non-text response.")

    cleaned_response = model_response.strip()
    if cleaned_response.startswith("```"):
        cleaned_response = cleaned_response.removeprefix("```").strip()
        if cleaned_response.lower().startswith("json"):
            cleaned_response = cleaned_response[4:].lstrip()
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3].rstrip()

    try:
        data: Dict[str, Any] = json.loads(cleaned_response)
    except json.JSONDecodeError as error:
        raise OllamaError("Ollama did not return valid JSON. Try the Generate button again.") from error

    if not isinstance(data, dict):
        raise OllamaError("Ollama did not return a JSON object.")
    product_name = data.get("product_name")
    characteristics = data.get("characteristics")
    call_to_action = data.get("call_to_action")
    if not isinstance(product_name, str) or not product_name.strip():
        raise OllamaError("The generated post is missing a product name.")
    if not isinstance(characteristics, list) or len(characteristics) != 3:
        raise OllamaError("The generated post did not contain three characteristics.")
    if not all(isinstance(item, str) and item.strip() for item in characteristics):
        raise OllamaError("The generated characteristics were not valid text.")
    if not isinstance(call_to_action, str) or not call_to_action.strip():
        raise OllamaError("The generated post is missing a contact call to action.")

    return PostDraft(
        product_name=product_name.strip(),
        characteristics=[item.strip() for item in characteristics],
        call_to_action=call_to_action.strip(),
    )


def format_post(draft: PostDraft) -> str:
    """Format structured copy into the post style shown in the GUI."""
    bullets = "\n".join(f"- {item}" for item in draft.characteristics)
    return f"{draft.product_name}\n{bullets}\n\n{draft.call_to_action}"
