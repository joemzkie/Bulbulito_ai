from openai import OpenAI


def create_openrouter_client(provider_config: dict) -> OpenAI:
    """Create an OpenRouter client with the app-identification headers."""
    return OpenAI(
        base_url=provider_config["base_url"],
        api_key=provider_config["api_key"],
        default_headers={
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "Local-Chatbot",
        },
    )
