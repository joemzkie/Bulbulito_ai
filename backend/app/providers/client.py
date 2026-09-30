from openai import OpenAI
from .registry import PROVIDERS, MODEL_REGISTRY


class ProviderNotConfiguredError(Exception):
    """Raised when the selected provider has no server-side credential."""


def call_chatbot(user_model_choice: str, messages: list, temperature: float = 0.7) -> str:
    """
    Routes the prompt to the user's selected model across Groq, OpenRouter,
    Gemini, or OpenAI.
    """
    if user_model_choice not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model '{user_model_choice}'")

    # 1. Resolve configuration from registry
    model_config = MODEL_REGISTRY[user_model_choice]
    provider_name = model_config["provider"]
    provider_config = PROVIDERS[provider_name]

    # 2. Check for missing credentials
    if not provider_config["api_key"]:
        raise ProviderNotConfiguredError(
            f"Provider {provider_name.upper()} is not configured. "
            "Add its credential to the project root .env file."
        )

    # 3. Dynamic client initialization
    client = OpenAI(
        base_url=provider_config["base_url"],
        api_key=provider_config["api_key"]
    )

    # 4. Construct payload
    payload = {
        "model": model_config["model_id"],
        "messages": messages,
    }

    # OpenAI reasoning models (o1, o3-mini) do not accept custom temperatures
    is_reasoning_model = model_config["model_id"].startswith(("o1", "o3"))
    if not is_reasoning_model:
        payload["temperature"] = temperature

    # 5. Dispatch request
    try:
        response = client.chat.completions.create(**payload)
        content = response.choices[0].message.content
        if not isinstance(content, str):
            raise RuntimeError("The provider returned an empty response.")
        return content
    except Exception as exc:
        # Do not surface SDK exception text; it can include request details.
        raise RuntimeError("The selected provider could not complete the request.") from exc


# --- Quick Test Execution ---
if __name__ == "__main__":
    from .registry import list_available_models
    test_messages = [
        {"role": "system", "content": "You are a backend software engineer. Keep answers short and direct."},
        {"role": "user", "content": "In 2 sentences, what are the advantages of using pybind11 over ctypes?"}
    ]

    # Test choice 1: OpenAI via your credits
    # Test choice 2: "groq-llama-3.3-70b", "or-qwen-coder", "gemini-2.5-flash"
    chosen_model = "openai-gpt-4o-mini"

    print(f"Routing to {MODEL_REGISTRY[chosen_model]['name']}...")
    try:
        reply = call_chatbot(chosen_model, test_messages)
        print("\nResponse:\n", reply)
    except Exception as err:
        print(f"Error during execution: {err}")
