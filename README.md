# Bulbulito AI

Bulbulito AI is a local-first chat application with a React and TypeScript interface, a FastAPI backend, multiple LLM providers, and conversations stored as local JSON files.

## Self-documenting, modular architecture

Every part of Bulbulito has a clear responsibility, predictable location, and understandable interface. When something breaks, you should be able to find the relevant code, understand it, and change it without needing to understand the entire system.

| Area | Responsibility |
| --- | --- |
| `bulbulito_ui/src/` | Existing Bulbulito interface, UI state, and the frontend API service |
| `backend/app/api/routes/` | HTTP endpoints for models, chats, and messages |
| `backend/app/services/` | Chat and conversation application logic |
| `backend/app/providers/` | Provider credentials, model registry, and LLM dispatch |
| `backend/app/research/` | RIZARTS planning, retrieval, evidence extraction, synthesis, and validation |
| `backend/app/storage/` | Local conversation JSON persistence |
| `backend/data/chats/` | Private local conversation files; excluded from Git |

The frontend talks to the local FastAPI backend. Provider credentials are read by the backend from the project-root `.env` file and are never sent to the browser.

## Agents and models

Bulbulito has three agent modes:

- **JINIRAL** is the default general-purpose assistant.
- **BAI CODING** is the software-engineering assistant for programming, debugging, architecture, databases, APIs, data engineering, and algorithms.
- **RIZARTS** runs the research workflow described below.

The model selector and agent selector control different things. For JINIRAL and BAI CODING, the selected model comes from the backend model registry and is combined with the selected agent's behavior prompt. RIZARTS uses its configured research-stage models; the top model selection does not imply that every research stage uses that model.

### BAI CODING harness

BAI CODING is a guided chat mode, not an autonomous coding agent or a tool runner. The backend adds its coding instructions as a system prompt, then sends that prompt with the latest 40 user and assistant messages to the selected model. It has no access to the repository or terminal through this harness: it can only reason about code and project details included in the conversation. It must not claim to have inspected files, run commands, or tested code. It can suggest focused code for the user to review and apply.

The instructions guide BAI CODING to:

- Understand the request and the supplied code before proposing an answer, while keeping private reasoning private.
- Ground debugging in the provided inputs, outputs, types, data flow, and error paths; separate confirmed facts from assumptions.
- Identify the failure and its cause before offering the smallest suitable fix, with a concise explanation and relevant tradeoffs.
- Preserve the existing framework and architecture unless there is a clear reason to change them, and avoid unrelated rewrites or invented project details.
- Ask for specific missing context when it is needed to confirm a diagnosis, and keep code examples focused on the stated language and libraries.

The harness is defined by `BAI_CODING_PROMPT` in `backend/app/prompts.py` and selected for the `bai-coding` agent in `backend/app/services/chat_service.py`.

## Conversation history and context

Conversations are stored locally as one JSON file per chat:

```text
backend/data/chats/<chat-id>/conversation.json
```

For a normal JINIRAL or BAI CODING turn, the backend loads the conversation, adds the agent's system prompt, and sends the latest 40 user and assistant messages along with the new user message to the selected model. After a successful response, it appends the assistant message and saves the conversation JSON. On later turns, those saved messages provide context, helping the assistant follow references and maintain continuity. This is conversation memory supplied by the application; the model does not independently remember prior requests, and additional history does not guarantee a more accurate answer.

RIZARTS also receives up to the latest 12 earlier conversation messages as context for a research request. Its final response is saved to the same conversation JSON, so it remains visible when the chat is reopened.

## RIZARTS research mode

RIZARTS uses a small, bounded research pipeline rather than treating research as a normal chat prompt:

1. A planner creates search queries based on the topic and requested depth.
2. The backend retrieves DuckDuckGo search results and keeps the returned titles, URLs, and snippets.
3. An extractor turns the snippets into factual claims tied to the retrieved source indexes.
4. A synthesizer drafts a report and may cite only URLs returned by retrieval. Python validates citations against that source list.
5. An auditor checks the draft for gaps. If useful, the pipeline runs at most one refinement pass.

Search results are snippets, not full-page verification. If web search is unavailable, RIZARTS can return a clearly labeled best-effort answer from the model's general knowledge. If citations cannot be validated, it may also return a labeled uncited fallback. Those fallbacks are not web-verified research reports and must not be treated as having verified citations.

Research depth controls query and refinement limits:

| Depth | Planned queries | Refinement passes |
| --- | ---: | ---: |
| Quick | 3 | 0 |
| Standard | 3–4 | Up to 1 |
| Deep | 5 | Up to 1 |

## Local setup

### 1. Configure provider credentials

Create one `.env` file in the repository root, beside this README. The backend resolves this path from its source location, so startup does not depend on the terminal's current directory. Add the keys for providers you intend to use; do not commit real credential values.

```env
OPENAI_API_KEY=replace-with-your-key
GROQ_API_KEY=replace-with-your-key
OPENROUTER_API_KEY=replace-with-your-key
GEMINI_API_KEY=replace-with-your-key
```

The `.env` file is ignored by Git. Do not put provider keys in frontend files or frontend environment variables.

### 2. Start the FastAPI backend

From the repository root in PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

The API starts at `http://localhost:8000`. The health endpoint is `http://localhost:8000/api/health`.

### 3. Start the frontend

In a second terminal, from the repository root:

```powershell
cd bulbulito_ui
npm install
npm run dev
```

Open the local Vite URL printed in the terminal, normally `http://localhost:5173`.

## Main API routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/models` | List model metadata for the frontend selector |
| `GET` | `/api/chats` | List saved conversations |
| `POST` | `/api/chats` | Create a conversation |
| `GET` | `/api/chats/{chat_id}` | Load a conversation and its messages |
| `PATCH` | `/api/chats/{chat_id}` | Rename a conversation or update its agent |
| `POST` | `/api/chats/{chat_id}/messages` | Send a message using the selected model and agent |
| `DELETE` | `/api/chats/{chat_id}` | Delete a conversation |

## Local data and Git

Conversation JSON is stored under `backend/data/` and is ignored by Git. API credentials belong only in the ignored root `.env`. Before publishing changes, check `git status` and make sure no credentials, local data, or other private files are included. If private data was committed previously, a later deletion does not remove it from Git history.
