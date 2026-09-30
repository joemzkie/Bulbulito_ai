import json
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from app.core.config import CHAT_DATA_DIR


class JsonConversationStorage:
    def __init__(self, root: Path = CHAT_DATA_DIR):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _file(self, chat_id: str) -> Path:
        # IDs are generated server-side, but still reject path traversal inputs.
        if not chat_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in chat_id):
            raise HTTPException(status_code=400, detail="Invalid conversation ID.")
        return self.root / chat_id / "conversation.json"

    def create(self, conversation: dict) -> dict:
        path = self._file(conversation["id"])
        path.parent.mkdir(parents=True, exist_ok=False)
        self.save(conversation)
        return conversation

    def load(self, chat_id: str) -> dict:
        path = self._file(chat_id)
        try:
            with path.open("r", encoding="utf-8") as stream:
                return json.load(stream)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Conversation '{chat_id}' not found.")
        except (json.JSONDecodeError, OSError):
            raise HTTPException(status_code=500, detail="Conversation data could not be read.")

    def save(self, conversation: dict) -> None:
        path = self._file(conversation["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="conversation-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(conversation, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def list(self) -> list[dict]:
        results = []
        for file in self.root.glob("*/conversation.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                data.pop("messages", None)
                results.append(data)
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(results, key=lambda item: item.get("updated_at", ""), reverse=True)

    def delete(self, chat_id: str) -> None:
        path = self._file(chat_id)
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"Conversation '{chat_id}' not found.")
        shutil.rmtree(path.parent)


storage = JsonConversationStorage()
