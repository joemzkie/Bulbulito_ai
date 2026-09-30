from fastapi import APIRouter
from app.schemas.conversation import SendMessageRequest, SendMessageResponse
from app.services.chat_service import send_message

router = APIRouter(prefix="/chats", tags=["chat"])


@router.post("/{chat_id}/messages", response_model=SendMessageResponse)
def post_message(chat_id: str, request: SendMessageRequest) -> dict:
    return send_message(chat_id, request.model, request.content)
