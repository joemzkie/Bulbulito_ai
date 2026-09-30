from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.config import SYSTEM_PROMPT
from app.providers.client import ProviderNotConfiguredError, call_chatbot
from app.providers.registry import MODEL_REGISTRY
from app.storage.json_storage import storage


def send_message(chat_id: str, model: str, content: str) -> dict:
    if model not in MODEL_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Unknown model '{model}'")
    conversation = storage.load(chat_id)
    now = datetime.now(timezone.utc).isoformat()
    conversation["model"] = model
    conversation["messages"].append({"role": "user", "content": content, "created_at": now})
    if conversation["title"] == "New conversation":
        conversation["title"] = content.strip().splitlines()[0][:72] or "New conversation"

    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    history.extend({"role": msg["role"], "content": msg["content"]} for msg in conversation["messages"])
    try:
        answer = call_chatbot(model, history)
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="The selected provider could not complete the request.") from exc

    now = datetime.now(timezone.utc).isoformat()
    conversation["messages"].append({"role": "assistant", "content": answer, "created_at": now})
    conversation["updated_at"] = now
    storage.save(conversation)
    return {"role": "assistant", "content": answer, "conversation": conversation}
