from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = PROJECT_ROOT / "backend"
CHAT_DATA_DIR = BACKEND_DIR / "data" / "chats"
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE)

SYSTEM_PROMPT = "You are Bulbulito AI, a helpful local AI assistant.\nBe clear, accurate, and useful."
FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
