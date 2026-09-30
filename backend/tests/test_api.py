import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app
from app.storage import json_storage
from app.providers.registry import PROVIDERS


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


if __name__ == "__main__":
    unittest.main()
