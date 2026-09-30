from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    created_at: datetime | None = None


class Conversation(BaseModel):
    id: str
    title: str
    model: str
    created_at: datetime
    updated_at: datetime
    messages: list[Message] = Field(default_factory=list)


class CreateChatRequest(BaseModel):
    model: str | None = None


class SendMessageRequest(BaseModel):
    model: str
    content: str = Field(min_length=1, max_length=100000)


class SendMessageResponse(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str
    conversation: Conversation
