import logging

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from .registry import PROVIDERS, MODEL_REGISTRY
from .openrouter import create_openrouter_client

logger = logging.getLogger("bulbulito.providers")


class ProviderNotConfiguredError(Exception):
    """Raised when the selected provider has no server-side credential."""


class ProviderRequestError(Exception):
    """A sanitized, user-safe upstream provider failure."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


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
    if provider_name == "openrouter":
        client = create_openrouter_client(provider_config)
    else:
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
    except APIStatusError as exc:
        # OpenRouter's free model catalog changes; give a safe, useful error
        # without returning the upstream response body or request metadata.
        local_status_code = 502
        if provider_name == "openrouter" and exc.status_code == 404:
            message = f"OpenRouter model '{model_config['model_id']}' was not found or is no longer available on the free tier."
        elif exc.status_code in (401, 403):
            message = f"{provider_name.title()} rejected the configured credentials. Check the provider entry in the project root .env file."
        elif exc.status_code == 402:
            message = f"{provider_name.title()} requires available credits or a paid model for this request."
        elif exc.status_code == 429:
            message = f"{provider_name.title()} rate limit reached. Wait and try again."
            local_status_code = 429
        elif exc.status_code == 400:
            message = f"{provider_name.title()} rejected the request parameters for model '{model_config['model_id']}'."
        else:
            message = f"{provider_name.title()} could not complete the request (upstream status {exc.status_code})."
        logger.warning(
            "Provider request failed: provider=%s model_key=%s category=http_status upstream_status=%s",
            provider_name,
            user_model_choice,
            exc.status_code,
        )
        raise ProviderRequestError(message, status_code=local_status_code) from exc
    except APITimeoutError as exc:
        logger.warning(
            "Provider request failed: provider=%s model_key=%s category=timeout",
            provider_name,
            user_model_choice,
        )
        raise ProviderRequestError(f"{provider_name.title()} request timed out. Wait and try again.", status_code=504) from exc
    except APIConnectionError as exc:
        logger.warning(
            "Provider request failed: provider=%s model_key=%s category=connection error_type=%s",
            provider_name,
            user_model_choice,
            type(exc).__name__,
        )
        raise ProviderRequestError(f"Could not connect to {provider_name.title()}. Check your internet connection and try again.") from exc
    except Exception as exc:
        # Do not surface SDK exception text; it can include request details.
        logger.warning(
            "Provider request failed: provider=%s model_key=%s category=unexpected error_type=%s",
            provider_name,
            user_model_choice,
            type(exc).__name__,
        )
        raise ProviderRequestError(f"{provider_name.title()} could not complete the request.") from exc


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
