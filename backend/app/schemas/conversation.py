from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator

AgentId = Literal["jiniral", "bai-coding", "rizarts"]
ResearchDepth = Literal["quick", "standard", "deep"]


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    created_at: datetime | None = None


class Conversation(BaseModel):
    id: str
    title: str
    model: str
    agent: AgentId = "jiniral"
    created_at: datetime
    updated_at: datetime
    messages: list[Message] = Field(default_factory=list)


class CreateChatRequest(BaseModel):
    model: str | None = None
    agent: AgentId = "jiniral"


class UpdateConversationRequest(BaseModel):
    model_config = {"str_strip_whitespace": True}

    title: str | None = Field(default=None, min_length=1, max_length=120)
    agent: AgentId | None = None

    @model_validator(mode="after")
    def require_update(self):
        if self.title is None and self.agent is None:
            raise ValueError("Provide a title or agent to update.")
        return self


class SendMessageRequest(BaseModel):
    model: str
    agent: AgentId = "jiniral"
    content: str = Field(min_length=1, max_length=100000)
    research_depth: ResearchDepth = "deep"
    research_constraints: str | None = Field(default=None, max_length=5000)


class SendMessageResponse(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str
    conversation: Conversation
