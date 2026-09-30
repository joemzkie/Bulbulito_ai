import json
from queue import Queue
from threading import Thread

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.conversation import SendMessageRequest
from app.services.chat_service import send_message

router = APIRouter(prefix="/chats", tags=["chat"])


@router.post("/{chat_id}/messages")
def post_message(chat_id: str, request: SendMessageRequest):
    if request.agent != "rizarts":
        return send_message(chat_id, request.model, request.content, request.agent, request.research_depth)

    events: Queue = Queue()
    finished = object()

    def worker() -> None:
        try:
            conversation = send_message(
                chat_id,
                request.model,
                request.content,
                request.agent,
                request.research_depth,
                request.research_constraints,
                progress=lambda status: events.put(("progress", {"status": status})),
            )
            events.put(("complete", {"conversation": conversation["conversation"]}))
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "RIZARTS could not complete this research request."
            events.put(("error", {"detail": detail}))
        except Exception:
            events.put(("error", {"detail": "RIZARTS could not complete this research request. Please try again."}))
        finally:
            events.put(finished)

    Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            item = events.get()
            if item is finished:
                break
            event, data = item
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
