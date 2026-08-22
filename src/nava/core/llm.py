"""
Shared LLM factory for Nava.
All agents read LLM_PROVIDER and LLM_MODEL from the environment.
To switch models, update .env — no code changes needed.

Supported providers:
    openrouter  → uses langchain_openai.ChatOpenAI pointed at openrouter.ai
    google      → uses langchain_google_genai.ChatGoogleGenerativeAI
"""
import os


def get_llm():
    provider = os.environ.get("LLM_PROVIDER", "google").lower()
    model = os.environ.get("LLM_MODEL", "gemini-1.5-flash")

    if provider == "openrouter":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            openai_api_key=os.environ.get("OPENROUTER_API_KEY"),
            openai_api_base="https://openrouter.ai/api/v1",
        )

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key and os.environ.get("NAVA_TEST_MODE") == "1":
            api_key = "mock_key_for_testing"
        return ChatGoogleGenerativeAI(model=model, max_retries=10, google_api_key=api_key)

    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model,
            api_key=os.environ.get("GROQ_API_KEY"),
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            openai_api_key=os.environ.get("OPENAI_API_KEY", "ollama"),
            openai_api_base=os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1"),
        )

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{provider}'. "
            "Supported values: 'openrouter', 'google', 'groq', 'openai'"
        )
