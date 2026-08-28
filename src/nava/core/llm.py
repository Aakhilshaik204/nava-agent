"""
Shared LLM factory for NAVA.
All settings (LLM_PROVIDER, LLM_MODEL, API keys) are configured entirely by the user in .env.
No models are hardcoded.
"""
import os
import sys
from dotenv import load_dotenv

GLOBAL_ENV_FILE = os.path.expanduser("~/.nava/.env")

def get_llm():
    # 1. Load global ~/.nava/.env if exists
    if os.path.exists(GLOBAL_ENV_FILE):
        load_dotenv(GLOBAL_ENV_FILE)

    # 2. Load local workspace .env (overrides global if present)
    local_env = os.path.join(os.getcwd(), ".env")
    if os.path.exists(local_env):
        load_dotenv(local_env, override=True)

    provider = os.environ.get("LLM_PROVIDER", "google").lower().strip()
    
    # Model is read entirely from user's .env file (default fallback only if unset in .env)
    model = os.environ.get("LLM_MODEL", "gemini-2.5-flash").strip()

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            if os.environ.get("NAVA_TEST_MODE") == "1":
                api_key = "mock_key_for_testing"
            else:
                raise ValueError(
                    "Missing Google API Key! Please set GEMINI_API_KEY or GOOGLE_API_KEY in your .env file.\n"
                    "Get a free key from: https://aistudio.google.com/app/apikey"
                )
        return ChatGoogleGenerativeAI(model=model, max_retries=10, google_api_key=api_key)

    elif provider == "openrouter":
        from langchain_openai import ChatOpenAI
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set in environment or .env file.")
        base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        return ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            openai_api_base=base_url,
        )

    elif provider == "groq":
        from langchain_groq import ChatGroq
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set in environment or .env file.")
        return ChatGroq(
            model=model,
            api_key=api_key,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.environ.get("OPENAI_API_KEY", "ollama")
        base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1")
        return ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            openai_api_base=base_url,
        )

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{provider}'. "
            "Supported values in .env: 'google', 'openrouter', 'groq', 'openai'"
        )
