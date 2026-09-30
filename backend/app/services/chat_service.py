from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import HTTPException

from app.prompts import BAI_CODING_PROMPT, JINIRAL_PROMPT, RIZARTS_PROMPT
from app.providers.client import ProviderNotConfiguredError, ProviderRequestError, call_chatbot
from app.providers.registry import MODEL_REGISTRY
from app.research.orchestrator import ResearchPipelineError, run_rizarts_research
from app.storage.json_storage import storage


AGENT_PROMPTS = {"jiniral": JINIRAL_PROMPT, "bai-coding": BAI_CODING_PROMPT, "rizarts": RIZARTS_PROMPT}
MAX_HISTORY_MESSAGES = 40


def send_message(
    chat_id: str,
    model: str,
    content: str,
    agent: str = "jiniral",
    research_depth: str = "deep",
    research_constraints: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict:
    if model not in MODEL_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Unknown model '{model}'")
    if agent not in ("jiniral", "bai-coding", "rizarts"):
        raise HTTPException(status_code=422, detail=f"Unknown agent '{agent}'.")
    if research_depth not in ("quick", "standard", "deep"):
        raise HTTPException(status_code=422, detail=f"Unknown research depth '{research_depth}'.")
    conversation = storage.load(chat_id)
    conversation.setdefault("agent", "jiniral")
    now = datetime.now(timezone.utc).isoformat()
    conversation["model"] = model
    conversation["agent"] = agent
    conversation["messages"].append({"role": "user", "content": content, "created_at": now})
    if conversation["title"] == "New conversation":
        conversation["title"] = content.strip().splitlines()[0][:72] or "New conversation"

    history = [
        {"role": "system", "content": AGENT_PROMPTS[agent]}
    ]
    history.extend(
        {"role": msg["role"], "content": msg["content"]}
        for msg in conversation["messages"][-MAX_HISTORY_MESSAGES:]
        if msg.get("role") in ("user", "assistant")
    )
    try:
        if agent == "rizarts":
            answer = run_rizarts_research(
                topic=content,
                research_depth=research_depth,
                constraints=research_constraints,
                conversation_history=conversation["messages"][:-1][-12:],
                progress=progress,
            )
        else:
            answer = call_chatbot(model, history)
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ProviderRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ResearchPipelineError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="The selected provider could not complete the request.") from exc

    now = datetime.now(timezone.utc).isoformat()
    conversation["messages"].append({"role": "assistant", "content": answer, "created_at": now})
    conversation["updated_at"] = now
    storage.save(conversation)
    return {"role": "assistant", "content": answer, "conversation": conversation}
