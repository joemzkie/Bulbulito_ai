import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from openai import APIStatusError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app
from app.storage import json_storage
from app.providers.registry import MODEL_REGISTRY, PROVIDERS
from app.providers import client as provider_client
from app.providers import openrouter as openrouter_provider
from app.providers.client import ProviderRequestError


class ChatApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_root = json_storage.storage.root
        json_storage.storage.root = Path(self.temp.name)
        self.client = TestClient(app)

    def tearDown(self):
        json_storage.storage.root = self.previous_root
        self.temp.cleanup()

    def test_models_are_sanitized_and_complete(self):
        response = self.client.get("/api/models")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 15)
        self.assertTrue(all(set(item) == {"name", "provider", "description"} for item in response.json().values()))
        self.assertNotIn("api_key", response.text.lower())

    def test_conversation_crud_and_history(self):
        created = self.client.post("/api/chats", json={"model": "groq-gpt-oss-120b"})
        self.assertEqual(created.status_code, 200)
        chat_id = created.json()["id"]
        self.assertEqual(self.client.get("/api/chats").status_code, 200)
        self.assertEqual(self.client.get(f"/api/chats/{chat_id}").json()["messages"], [])

        with patch("app.services.chat_service.call_chatbot", side_effect=["Hello back", "You said Hello"] ) as call:
            first = self.client.post(f"/api/chats/{chat_id}/messages", json={"model": "groq-gpt-oss-120b", "content": "Hello"})
            second = self.client.post(f"/api/chats/{chat_id}/messages", json={"model": "groq-gpt-oss-120b", "content": "What did I just say?"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        history = call.call_args_list[1].args[1]
        self.assertTrue(any(message["role"] == "user" and message["content"] == "Hello" for message in history))
        stored = self.client.get(f"/api/chats/{chat_id}").json()
        self.assertEqual([item["role"] for item in stored["messages"]], ["user", "assistant", "user", "assistant"])
        self.assertEqual(self.client.get("/api/chats").json()[0]["title"], "Hello")
        self.assertEqual(self.client.delete(f"/api/chats/{chat_id}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/chats/{chat_id}").status_code, 404)

    def test_unknown_model_and_missing_conversation_errors(self):
        response = self.client.post("/api/chats/missing/messages", json={"model": "xyz", "content": "Hello"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown model 'xyz'", response.json()["detail"])
        response = self.client.get("/api/chats/missing")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Conversation 'missing' not found.", response.json()["detail"])

    def test_missing_provider_key_is_clear_and_sanitized(self):
        created = self.client.post("/api/chats", json={"model": "groq-gpt-oss-120b"})
        chat_id = created.json()["id"]
        with patch.dict(PROVIDERS["groq"], {"api_key": None}):
            response = self.client.post(f"/api/chats/{chat_id}/messages", json={"model": "groq-gpt-oss-120b", "content": "Hello"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("Provider GROQ is not configured", response.json()["detail"])
        self.assertNotIn("api_key", response.text.lower())

    def test_openrouter_client_receives_app_headers(self):
        config = {"base_url": "https://openrouter.ai/api/v1", "api_key": "test-token"}
        with patch.object(openrouter_provider, "OpenAI") as sdk_client:
            openrouter_provider.create_openrouter_client(config)
        sdk_client.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-token",
            default_headers={
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "Local-Chatbot",
            },
        )

    def test_dispatcher_uses_openrouter_helper_only_for_openrouter(self):
        response = type("Response", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": "ok"})()})()]})()
        fake_client = type("FakeClient", (), {"chat": type("Chat", (), {"completions": type("Completions", (), {"create": lambda self, **kwargs: response})()})()})()
        config = PROVIDERS["openrouter"]
        with patch.object(provider_client, "create_openrouter_client", return_value=fake_client) as factory:
            self.assertEqual(provider_client.call_chatbot("or-qwen-coder", [{"role": "user", "content": "test"}]), "ok")
        factory.assert_called_once_with(config)

        config = PROVIDERS["groq"]
        with patch.object(provider_client, "OpenAI", return_value=fake_client) as sdk_client, patch.object(provider_client, "create_openrouter_client") as factory:
            self.assertEqual(provider_client.call_chatbot("groq-llama-3.3-70b", [{"role": "user", "content": "test"}]), "ok")
        sdk_client.assert_called_once_with(base_url=config["base_url"], api_key=config["api_key"])
        factory.assert_not_called()

    def test_openrouter_registry_uses_current_free_model_slugs(self):
        self.assertEqual(MODEL_REGISTRY["or-qwen-coder"]["model_id"], "qwen/qwen3.8-27b:free")
        self.assertIn("Qwen3.8", MODEL_REGISTRY["or-qwen-coder"]["name"])
        self.assertEqual(MODEL_REGISTRY["or-nemotron-ultra"]["model_id"], "nvidia/nemotron-3-ultra-550b-a55b:free")

    def test_openrouter_404_becomes_safe_actionable_error(self):
        request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        response = httpx.Response(404, request=request)
        upstream_error = APIStatusError(
            "upstream raw response",
            response=response,
            body={"error": {"message": "model unavailable", "user_id": "private-user-id"}},
        )
        completions = Mock()
        completions.create.side_effect = upstream_error
        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        config = {"base_url": "https://openrouter.ai/api/v1", "api_key": "test-token"}
        with patch.dict(PROVIDERS, {"openrouter": config}), patch.object(provider_client, "create_openrouter_client", return_value=fake_client):
            with self.assertRaises(ProviderRequestError) as raised:
                provider_client.call_chatbot("or-qwen-coder", [{"role": "user", "content": "test"}])
        self.assertIn("qwen/qwen3.8-27b:free", str(raised.exception))
        self.assertIn("no longer available on the free tier", str(raised.exception))
        self.assertNotIn("private-user-id", str(raised.exception))
        self.assertNotIn("test-token", str(raised.exception))

    def test_unexpected_provider_failure_logs_only_safe_diagnostics(self):
        completions = Mock()
        completions.create.side_effect = RuntimeError("private response body and credential")
        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        config = {"base_url": "https://openrouter.ai/api/v1", "api_key": "test-token"}
        with patch.dict(PROVIDERS, {"openrouter": config}), patch.object(provider_client, "create_openrouter_client", return_value=fake_client):
            with self.assertLogs("bulbulito.providers", level="WARNING") as captured:
                with self.assertRaises(ProviderRequestError) as raised:
                    provider_client.call_chatbot("or-qwen-coder", [{"role": "user", "content": "test"}])
        self.assertEqual(str(raised.exception), "Openrouter could not complete the request.")
        log_output = "\n".join(captured.output)
        self.assertIn("category=unexpected", log_output)
        self.assertIn("error_type=RuntimeError", log_output)
        self.assertNotIn("private response body", log_output)
        self.assertNotIn("credential", log_output)

    def test_api_returns_actionable_provider_error_without_upstream_details(self):
        created = self.client.post("/api/chats", json={"model": "or-qwen-coder"})
        chat_id = created.json()["id"]
        failure = ProviderRequestError("OpenRouter model is unavailable on the free tier.")
        with patch("app.services.chat_service.call_chatbot", side_effect=failure):
            response = self.client.post(f"/api/chats/{chat_id}/messages", json={"model": "or-qwen-coder", "content": "Hello"})
        self.assertEqual(response.status_code, 502)
        self.assertIn("unavailable on the free tier", response.json()["detail"])
        self.assertNotIn("api_key", response.text.lower())

    def test_api_preserves_sanitized_rate_limit_status(self):
        created = self.client.post("/api/chats", json={"model": "or-qwen-coder"})
        chat_id = created.json()["id"]
        failure = ProviderRequestError("OpenRouter rate limit reached. Wait and try again.", status_code=429)
        with patch("app.services.chat_service.call_chatbot", side_effect=failure):
            response = self.client.post(f"/api/chats/{chat_id}/messages", json={"model": "or-qwen-coder", "content": "Hello"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], "OpenRouter rate limit reached. Wait and try again.")


if __name__ == "__main__":
    unittest.main()
