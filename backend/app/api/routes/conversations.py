from fastapi import APIRouter
from app.providers.registry import MODEL_REGISTRY
from app.schemas.conversation import CreateChatRequest, UpdateConversationRequest
from app.services import conversation_service

router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("")
def list_chats() -> list[dict]:
    return conversation_service.list_conversations()


@router.post("")
def create_chat(request: CreateChatRequest | None = None) -> dict:
    model = request.model if request and request.model in MODEL_REGISTRY else next(iter(MODEL_REGISTRY))
    agent = request.agent if request else "jiniral"
    return conversation_service.create_conversation(model, agent)


@router.get("/{chat_id}")
def get_chat(chat_id: str) -> dict:
    return conversation_service.get_conversation(chat_id)


@router.patch("/{chat_id}")
def rename_chat(chat_id: str, request: UpdateConversationRequest) -> dict:
    return conversation_service.update_conversation(chat_id, title=request.title, agent=request.agent)


@router.delete("/{chat_id}")
def delete_chat(chat_id: str) -> dict:
    conversation_service.delete_conversation(chat_id)
    return {"deleted": True}
