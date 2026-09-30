"""Native Gemini GenerateContent API transport."""

from urllib.parse import quote

import httpx


def generate_content_url(base_url: str, model_id: str) -> str:
    """Build the v1beta GenerateContent URL with exactly one models/ prefix."""
    clean_model = model_id.strip().lstrip("/")
    while clean_model.startswith("models/"):
        clean_model = clean_model[len("models/"):]
    if not clean_model:
        raise ValueError("Gemini model identifier cannot be empty.")
    model_path = quote(f"models/{clean_model}", safe="/-._")
    return f"{base_url.rstrip('/')}/{model_path}:generateContent"


def _build_request(messages: list, model_id: str, temperature: float) -> dict:
    system_text = "\n\n".join(
        message["content"]
        for message in messages
        if message.get("role") == "system" and isinstance(message.get("content"), str)
    )
    contents = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        contents.append({
            "role": "user" if role == "user" else "model",
            "parts": [{"text": content}],
        })

    payload = {"contents": contents}
    if system_text:
        payload["systemInstruction"] = {"parts": [{"text": system_text}]}
    if not model_id.startswith("gemini-3"):
        payload["generationConfig"] = {"temperature": temperature}
    return payload


def call_gemini(
    *, base_url: str, api_key: str, model_id: str, messages: list,
    temperature: float = 0.7,
) -> str:
    """Call Gemini's native REST API using its API-key header authentication."""
    response = httpx.post(
        generate_content_url(base_url, model_id),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json=_build_request(messages, model_id, temperature),
        timeout=60.0,
    )
    response.raise_for_status()
    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini returned no response candidates.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(
        part.get("text", "")
        for part in parts
        if part.get("thought") is not True and isinstance(part.get("text"), str)
    )
    if not text:
        raise ValueError("Gemini returned an empty response.")
    return text
