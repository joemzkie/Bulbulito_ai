import os
from pathlib import Path
from dotenv import load_dotenv

# This module is backend/app/providers/registry.py; resolve the only supported
# environment file from the project root, independent of the process cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

# 1. Provider base URLs and API keys
PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API"),
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.getenv("OPENROUTER_API_KEY") or os.getenv("OPEN_ROUTER"),
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/",
        "api_key": os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI"),
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        # Accepts either standard OPENAI_API_KEY or CODEX_API_KEY
        "api_key": os.getenv("OPENAI_API_KEY") or os.getenv("CODEX_API_KEY") or os.getenv("CODEX"),
    }
}

# 2. Unified Model Catalog
MODEL_REGISTRY = {
    # --- OpenAI (Uses your $50 credit balance) ---
    "openai-gpt-5.6-sol": {
        "provider": "openai",
        "model_id": "gpt-5.6-sol",
        "name": "GPT-5.6 Sol",
        "description": "Flagship model for complex coding, reasoning, research, and professional work",
        "supports_temperature": False,
    },
    "openai-gpt-5.6-luna": {
        "provider": "openai",
        "model_id": "gpt-5.6-luna",
        "name": "GPT-5.6 Luna",
        "description": "Fast, efficient model for everyday chat, coding, and high-volume tasks",
        "supports_temperature": False,
    },
    "openai-gpt-4o": {
        "provider": "openai",
        "model_id": "gpt-4o",
        "name": "GPT-4o (OpenAI)",
        "description": "High-intelligence flagship model for complex coding & tasks"
    },
    "openai-gpt-4o-mini": {
        "provider": "openai",
        "model_id": "gpt-4o-mini",
        "name": "GPT-4o Mini (OpenAI)",
        "description": "Affordable daily driver; preserves your $50 credit pool"
    },
    "openai-o3-mini": {
        "provider": "openai",
        "model_id": "o3-mini",
        "name": "o3-mini Reasoning (OpenAI)",
        "description": "Deep STEM, algorithmic logic, and code debugging"
    },
    "openai-o1": {
        "provider": "openai",
        "model_id": "o1",
        "name": "o1 Deep Thinking (OpenAI)",
        "description": "Extended chain-of-thought for architectural problems"
    },

    # --- Groq (Free, high-speed LPU inference) ---
    "groq-llama-3.3-70b": {
        "provider": "groq",
        "model_id": "llama-3.3-70b-versatile",
        "name": "Llama 3.3 70B (Groq)",
        "description": "Fast all-around reasoning, writing, and logic"
    },
    "groq-llama-3.1-8b": {
        "provider": "groq",
        "model_id": "llama-3.1-8b-instant",
        "name": "Llama 3.1 8B (Groq)",
        "description": "Ultra-low latency instant completions"
    },
    "groq-gpt-oss-120b": {
        "provider": "groq",
        "model_id": "openai/gpt-oss-120b",
        "name": "GPT-OSS 120B (Groq)",
        "description": "Dense open-weight reasoning model"
    },
    "groq-qwen-27b": {
        "provider": "groq",
        "model_id": "qwen/qwen3.8-27b",
        "name": "Qwen 3.8 27B (Groq)",
        "description": "Math, multilingual, and structured parsing"
    },

    # --- OpenRouter (Free tier models) ---
    "or-llama-3.3-70b": {
        "provider": "openrouter",
        "model_id": "meta-llama/llama-3.3-70b-instruct:free",
        "name": "Llama 3.3 70B Free (OpenRouter)",
        "description": "Free general knowledge and conversation"
    },
    "or-gpt-oss-120b": {
        "provider": "openrouter",
        "model_id": "openai/gpt-oss-120b:free",
        "name": "GPT-OSS 120B Free (OpenRouter)",
        "description": "Free deep reasoning and tool use"
    },
    "or-qwen-coder": {
        "provider": "openrouter",
        "model_id": "qwen/qwen3.8-27b:free",
        "name": "Qwen3.8 27B Free (OpenRouter)",
        "description": "Free model for coding, research, and structured tasks"
    },
    "or-nemotron-ultra": {
        "provider": "openrouter",
        "model_id": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "name": "Nemotron 3 Ultra Free (OpenRouter)",
        "description": "Free agentic reasoning and research"
    },

    # --- Google Gemini (Free via Google AI Studio) ---
    "gemini-2.5-flash": {
        "provider": "gemini",
        "model_id": "gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "description": "High speed, massive 1M token context window"
    },
    "gemini-2.5-pro": {
        "provider": "gemini",
        "model_id": "gemini-2.5-pro",
        "name": "Gemini 2.5 Pro",
        "description": "Advanced multi-file analysis and thinking"
    },
    "gemini-2.5-flash-lite": {
        "provider": "gemini",
        "model_id": "gemini-2.5-flash-lite",
        "name": "Gemini 2.5 Flash-Lite",
        "description": "Lightweight tasks and extraction"
    },
    "gemini-3.8-flash": {
        "provider": "gemini",
        "model_id": "gemini-3.8-flash",
        "name": "Gemini 3.8 Flash",
        "description": "Current-generation reasoning and multimodal assistant"
    },
    "gemini-3.5-flash-lite": {
        "provider": "gemini",
        "model_id": "gemini-3.5-flash-lite",
        "name": "Gemini 3.5 Flash-Lite",
        "description": "Fast, cost-efficient model for planning and extraction"
    }
}


def list_available_models() -> dict:
    """Returns a sanitized map suitable for populating frontend dropdown menus."""
    return {
        key: {
            "name": data["name"],
            "provider": data["provider"],
            "description": data["description"]
        }
        for key, data in MODEL_REGISTRY.items()
    }
