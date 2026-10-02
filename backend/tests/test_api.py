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
from app.providers import gemini as gemini_provider
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
        self.assertEqual(len(response.json()), 19)
        self.assertTrue(all(set(item) == {"name", "provider", "description"} for item in response.json().values()))
        self.assertNotIn("api_key", response.text.lower())
        self.assertNotIn("OPENAI_API_KEY", response.text)
        self.assertEqual(response.json()["openai-gpt-5.6-sol"], {
            "name": "GPT-5.6 Sol",
            "provider": "openai",
            "description": "Flagship model for complex coding, reasoning, research, and professional work",
        })
        self.assertEqual(response.json()["openai-gpt-5.6-luna"], {
            "name": "GPT-5.6 Luna",
            "provider": "openai",
            "description": "Fast, efficient model for everyday chat, coding, and high-volume tasks",
        })

    def test_gpt56_models_use_openai_ids_without_custom_temperature(self):
        response = type("Response", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": "ok"})()})()]})()
        completions = Mock(return_value=response)
        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completions)))
        config = {"base_url": "https://api.openai.com/v1", "api_key": "test-token"}

        with patch.dict(PROVIDERS, {"openai": config}), patch.object(provider_client, "OpenAI", return_value=fake_client) as sdk_client:
            for model_key, model_id in (
                ("openai-gpt-5.6-sol", "gpt-5.6-sol"),
                ("openai-gpt-5.6-luna", "gpt-5.6-luna"),
            ):
                with self.subTest(model_key=model_key):
                    self.assertEqual(provider_client.call_chatbot(model_key, [{"role": "user", "content": "Hi"}]), "ok")
                    payload = completions.call_args.kwargs
                    self.assertEqual(payload["model"], model_id)
                    self.assertNotIn("temperature", payload)
        self.assertEqual(sdk_client.call_args.kwargs["base_url"], config["base_url"])

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

    def test_gemini_dispatch_uses_native_endpoint_header_and_history(self):
        request = httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent")
        response = httpx.Response(200, request=request, json={
            "candidates": [{"content": {"parts": [
                {"text": "private reasoning", "thought": True},
                {"text": "ok"},
            ]}}],
        })
        config = {**PROVIDERS["gemini"], "api_key": "test-token"}
        messages = [
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "First turn"},
            {"role": "assistant", "content": "Earlier answer"},
            {"role": "user", "content": "Current turn"},
        ]
        with patch.dict(PROVIDERS, {"gemini": config}), patch.object(gemini_provider.httpx, "post", return_value=response) as post:
            self.assertEqual(provider_client.call_chatbot("gemini-2.5-flash", messages), "ok")
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent")
        self.assertEqual(kwargs["headers"], {
            "x-goog-api-key": "test-token",
            "Content-Type": "application/json",
        })
        self.assertNotIn("Authorization", kwargs["headers"])
        self.assertEqual(kwargs["json"]["systemInstruction"], {"parts": [{"text": "Be helpful."}]})
        self.assertEqual(kwargs["json"]["contents"], [
            {"role": "user", "parts": [{"text": "First turn"}]},
            {"role": "model", "parts": [{"text": "Earlier answer"}]},
            {"role": "user", "parts": [{"text": "Current turn"}]},
        ])
        self.assertEqual(kwargs["json"]["generationConfig"]["temperature"], 0.7)

    def test_gemini_model_prefix_is_neither_missing_nor_doubled(self):
        base = "https://generativelanguage.googleapis.com/v1beta/"
        expected = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        self.assertEqual(gemini_provider.generate_content_url(base, "gemini-2.5-flash"), expected)
        self.assertEqual(gemini_provider.generate_content_url(base, "models/gemini-2.5-flash"), expected)
        self.assertEqual(gemini_provider.generate_content_url(base, "models/models/gemini-2.5-flash"), expected)

    def test_gemini_3_dispatch_omits_unsupported_temperature(self):
        request = httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent")
        response = httpx.Response(200, request=request, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})
        config = {**PROVIDERS["gemini"], "api_key": "test-token"}
        with patch.dict(PROVIDERS, {"gemini": config}), patch.object(gemini_provider.httpx, "post", return_value=response) as post:
            self.assertEqual(provider_client.call_chatbot("gemini-3.8-flash", [{"role": "user", "content": "test"}]), "ok")
        self.assertNotIn("generationConfig", post.call_args.kwargs["json"])

    def test_gemini_404_error_identifies_model_availability(self):
        request = httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent")
        response = httpx.Response(404, request=request, json={"error": {"message": "private upstream body"}})
        config = {**PROVIDERS["gemini"], "api_key": "test-token"}
        with patch.dict(PROVIDERS, {"gemini": config}), patch.object(gemini_provider.httpx, "post", return_value=response):
            with self.assertRaises(ProviderRequestError) as raised:
                provider_client.call_chatbot("gemini-3.8-flash", [{"role": "user", "content": "test"}])
        self.assertIn("unavailable to this API project", str(raised.exception))
        self.assertNotIn("private upstream body", str(raised.exception))

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
