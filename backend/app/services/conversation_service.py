from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.storage.json_storage import storage


def create_conversation(model: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return storage.create({
        "id": uuid4().hex[:12], "title": "New conversation", "model": model,
        "created_at": now, "updated_at": now, "messages": [],
    })


def list_conversations() -> list[dict]:
    return storage.list()


def get_conversation(chat_id: str) -> dict:
    return storage.load(chat_id)


def rename_conversation(chat_id: str, title: str) -> dict:
    title = title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Conversation title cannot be empty.")
    conversation = storage.load(chat_id)
    conversation["title"] = title
    conversation["updated_at"] = datetime.now(timezone.utc).isoformat()
    storage.save(conversation)
    return conversation


def delete_conversation(chat_id: str) -> None:
    storage.delete(chat_id)
