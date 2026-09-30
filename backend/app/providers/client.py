import logging

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from .registry import PROVIDERS, MODEL_REGISTRY
from .openrouter import create_openrouter_client
from .gemini import call_gemini

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
    elif provider_name != "gemini":
        client = OpenAI(
            base_url=provider_config["base_url"],
            api_key=provider_config["api_key"]
        )

    # 4. Construct payload
    payload = {
        "model": model_config["model_id"],
        "messages": messages,
    }

    # OpenAI reasoning models and Gemini 3 models do not accept custom temperatures.
    model_id = model_config["model_id"]
    is_reasoning_model = model_id.startswith(("o1", "o3", "gemini-3"))
    if not is_reasoning_model:
        payload["temperature"] = temperature

    # 5. Dispatch request. Gemini uses its native GenerateContent endpoint so
    # AQ-format API keys are sent in x-goog-api-key, never as Bearer tokens.
    try:
        if provider_name == "gemini":
            return call_gemini(
                base_url=provider_config["base_url"],
                api_key=provider_config["api_key"],
                model_id=model_id,
                messages=messages,
                temperature=temperature,
            )
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
        elif provider_name == "gemini" and exc.status_code == 404:
            message = f"Gemini model '{model_config['model_id']}' was not found or is unavailable to this API project. Check the model's current API availability."
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
    except httpx.HTTPStatusError as exc:
        upstream_status = exc.response.status_code
        local_status_code = 502
        if provider_name == "gemini" and upstream_status == 404:
            message = f"Gemini model '{model_config['model_id']}' was not found or is unavailable to this API project. Check the model's current API availability."
        elif upstream_status in (401, 403):
            message = f"{provider_name.title()} rejected the configured credentials. Check the provider entry in the project root .env file."
        elif upstream_status == 402:
            message = f"{provider_name.title()} requires available credits or a paid model for this request."
        elif upstream_status == 429:
            message = f"{provider_name.title()} rate limit reached. Wait and try again."
            local_status_code = 429
        elif upstream_status == 400:
            message = f"{provider_name.title()} rejected the request parameters for model '{model_config['model_id']}'."
        else:
            message = f"{provider_name.title()} could not complete the request (upstream status {upstream_status})."
        logger.warning(
            "Provider request failed: provider=%s model_key=%s category=http_status upstream_status=%s",
            provider_name,
            user_model_choice,
            upstream_status,
        )
        raise ProviderRequestError(message, status_code=local_status_code) from exc
    except httpx.TimeoutException as exc:
        logger.warning(
            "Provider request failed: provider=%s model_key=%s category=timeout",
            provider_name,
            user_model_choice,
        )
        raise ProviderRequestError(f"{provider_name.title()} request timed out. Wait and try again.", status_code=504) from exc
    except httpx.RequestError as exc:
        logger.warning(
            "Provider request failed: provider=%s model_key=%s category=connection error_type=%s",
            provider_name,
            user_model_choice,
            type(exc).__name__,
        )
        raise ProviderRequestError(f"Could not connect to {provider_name.title()}. Check your internet connection and try again.") from exc
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
