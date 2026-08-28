import os
import sys
from dotenv import load_dotenv

GLOBAL_NAVA_DIR = os.path.expanduser("~/.nava")
GLOBAL_ENV_FILE = os.path.join(GLOBAL_NAVA_DIR, ".env")

def load_all_env():
    """Loads global ~/.nava/.env first, then overrides with local workspace .env."""
    if os.path.exists(GLOBAL_ENV_FILE):
        load_dotenv(GLOBAL_ENV_FILE)
    local_env = os.path.join(os.getcwd(), ".env")
    if os.path.exists(local_env):
        load_dotenv(local_env, override=True)

def has_configured_key() -> bool:
    """Checks if any valid API key is present in environment or env files."""
    load_all_env()
    keys = ["GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"]
    for k in keys:
        val = os.environ.get(k)
        if val and len(val.strip()) > 5:
            return True
    return False

def ensure_api_key():
    """
    Asks the user for their API key ONCE on initial install.
    Saves it globally to ~/.nava/.env so it NEVER asks again in any project.
    """
    if has_configured_key():
        return

    os.makedirs(GLOBAL_NAVA_DIR, exist_ok=True)

    print("\n" + "─"*72)
    print(" ⚡ NAVA AGENT OS: Initial Setup (Runs Once)")
    print("─"*72)
    print(" NAVA needs an API key to power its planner, coding, and dynamic agents.")
    print(" Recommended: Free Google Gemini API Key (https://aistudio.google.com/app/apikey)\n")

    try:
        key = input(" Enter your API Key (e.g. AIza... or sk-...): ").strip()
        if not key:
            print("\n ℹ️  No key entered. You can set GEMINI_API_KEY in ~/.nava/.env or your local .env.\n")
            return

        if key.startswith("sk-") and not key.startswith("sk-ant") and not key.startswith("sk-or-"):
            provider = "openai"
            model = "gpt-4o"
            env_content = f"OPENAI_API_KEY={key}\nLLM_PROVIDER=openai\nLLM_MODEL=gpt-4o\n"
        elif key.startswith("gsk_"):
            provider = "groq"
            model = "llama-3.3-70b-versatile"
            env_content = f"GROQ_API_KEY={key}\nLLM_PROVIDER=groq\nLLM_MODEL=llama-3.3-70b-versatile\n"
        elif key.startswith("sk-or-"):
            provider = "openrouter"
            model = "anthropic/claude-3.5-sonnet"
            env_content = f"OPENROUTER_API_KEY={key}\nLLM_PROVIDER=openrouter\nLLM_MODEL=anthropic/claude-3.5-sonnet\n"
        else:
            provider = "google"
            model = "gemini-2.5-flash"
            env_content = f"GOOGLE_API_KEY={key}\nGEMINI_API_KEY={key}\nLLM_PROVIDER=google\nLLM_MODEL=gemini-2.5-flash\n"

        # 1. Save globally to ~/.nava/.env (persists across all folders on this machine)
        with open(GLOBAL_ENV_FILE, "w", encoding="utf-8") as f:
            f.write(f"# NAVA Global Configuration\n{env_content}")

        # 2. Also save to current directory .env if not exists
        local_env = os.path.join(os.getcwd(), ".env")
        if not os.path.exists(local_env):
            with open(local_env, "w", encoding="utf-8") as f:
                f.write(f"# NAVA Workspace Configuration\n{env_content}")

        load_all_env()
        print(f" ✓ Saved globally to {GLOBAL_ENV_FILE}!")
        print(f" ✓ Configured provider: '{provider}', model: '{model}'. Edit anytime in your .env.\n")

    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        sys.exit(0)

def main():
    """CLI entrypoint for `nava` command when installed via pip or pipx."""
    ensure_api_key()

    from nava.ui.cowork_tui import CoworkTUI
    tui = CoworkTUI()
    tui.run()

if __name__ == "__main__":
    main()
