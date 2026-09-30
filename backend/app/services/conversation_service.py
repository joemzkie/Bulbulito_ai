from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.storage.json_storage import storage


def create_conversation(model: str, agent: str = "jiniral") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return storage.create({
        "id": uuid4().hex[:12], "title": "New conversation", "model": model, "agent": agent,
        "created_at": now, "updated_at": now, "messages": [],
    })


def list_conversations() -> list[dict]:
    return storage.list()


def get_conversation(chat_id: str) -> dict:
    conversation = storage.load(chat_id)
    conversation.setdefault("agent", "jiniral")
    return conversation


def update_conversation(chat_id: str, *, title: str | None = None, agent: str | None = None) -> dict:
    conversation = storage.load(chat_id)
    if title is not None:
        title = title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="Conversation title cannot be empty.")
        conversation["title"] = title
    if agent is not None:
        conversation["agent"] = agent
    conversation["updated_at"] = datetime.now(timezone.utc).isoformat()
    storage.save(conversation)
    return conversation


def delete_conversation(chat_id: str) -> None:
    storage.delete(chat_id)
