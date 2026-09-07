import os
import sys
from dotenv import load_dotenv

def load_all_env():
    """Loads environment variables strictly from local workspace .env."""
    local_env = os.path.join(os.getcwd(), ".env")
    if os.path.exists(local_env):
        load_dotenv(local_env, override=True)

def has_configured_key() -> bool:
    """Checks if any valid API key is present in environment or env files."""
    load_all_env()
    keys = [
        "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", 
        "GROQ_API_KEY", "OPENROUTER_API_KEY", "API_KEY", "LATENTSTACK_API_KEY"
    ]
    for k in keys:
        val = os.environ.get(k)
        if val and len(val.strip()) > 5:
            return True
    return False

def generate_env_content(
    active_provider: str = "google",
    active_model: str = "gemini-2.5-flash",
    gemini_key: str = "",
    openrouter_key: str = "",
    openai_key: str = "",
    groq_key: str = "",
    openai_base_url: str = ""
) -> str:
    """Generates a clean, universal .env template with one primary key filled and others left empty."""
    base_url_line = f"OPENAI_BASE_URL={openai_base_url}\n" if openai_base_url else "# OPENAI_BASE_URL=http://localhost:11434/v1\n"
    
    return f"""# ==============================================================================
# NAVA Universal LLM & Agent OS Configuration
# ==============================================================================

# Active LLM Provider: "google" | "openrouter" | "openai" | "groq"
LLM_PROVIDER={active_provider}

# Active Model: Set to any model supported by your chosen provider
LLM_MODEL={active_model}

# ------------------------------------------------------------------------------
# API Keys (Set the key for your active LLM_PROVIDER, others left blank)
# ------------------------------------------------------------------------------
GEMINI_API_KEY={gemini_key}
OPENROUTER_API_KEY={openrouter_key}
OPENAI_API_KEY={openai_key}
GROQ_API_KEY={groq_key}

# Custom OpenAI-compatible Base URL (For Ollama, vLLM, LMStudio)
{base_url_line}"""

def ensure_api_key():
    """
    Interactive first-time onboarding wizard:
    Step 1: Select Provider
    Step 2: Select Model
    Step 3: Enter Key
    Automatically writes local workspace .env.
    """
    if has_configured_key():
        return

    print("\n" + "─"*72)
    print(" ⚡ NAVA AGENT OS: First-Time Setup Wizard (Runs Once)")
    print("─"*72)
    print(" Select your primary LLM Provider to get started:\n")
    print("   [1] Google Gemini   (Recommended — Free Tier & 1M+ Context)")
    print("   [2] OpenRouter      (Claude 3.5, DeepSeek R1, GPT-4o, Llama 3.3)")
    print("   [3] OpenAI          (GPT-4o, GPT-4o-mini, o3-mini)")
    print("   [4] Groq            (Ultra-fast Llama 3.3 70B)")
    print("   [5] Local Ollama    (Self-hosted OpenAI-compatible endpoint)\n")

    try:
        # Step 1: Provider selection
        p_choice = input(" Choose Provider [1-5] (default: 1): ").strip() or "1"
        
        provider_map = {
            "1": "google",
            "2": "openrouter",
            "3": "openai",
            "4": "groq",
            "5": "openai"
        }
        provider = provider_map.get(p_choice, "google")

        # Step 2: Model selection
        model_options = {
            "google": [
                ("1", "gemini-2.5-flash", "Recommended: Fast & powerful"),
                ("2", "gemini-2.5-pro", "Deep reasoning & complex coding"),
                ("3", "gemini-2.0-flash", "High speed & efficiency")
            ],
            "openrouter": [
                ("1", "anthropic/claude-3.5-sonnet", "Recommended: State-of-the-art coding"),
                ("2", "deepseek/deepseek-r1", "Reasoning & math specialist"),
                ("3", "openai/gpt-4o", "Omni multi-modal"),
                ("4", "meta-llama/llama-3.3-70b-instruct", "Open-weights leader")
            ],
            "openai": [
                ("1", "gpt-4o", "Recommended: Flagship model"),
                ("2", "gpt-4o-mini", "Lightweight & fast"),
                ("3", "o3-mini", "Reasoning model")
            ],
            "groq": [
                ("1", "llama-3.3-70b-versatile", "Recommended: Ultra-fast 70B"),
                ("2", "deepseek-r1-distill-llama-70b", "Reasoning distilled")
            ]
        }

        print(f"\n Select model for '{provider}':")
        opts = model_options.get(provider, [("1", "gemini-2.5-flash", "Default")])
        for num, m_name, m_desc in opts:
            print(f"   [{num}] {m_name:<34} ({m_desc})")
        print(f"   [C] Custom model name...")

        m_choice = input(f"\n Choose Model [1-{len(opts)} or C] (default: 1): ").strip() or "1"
        
        if m_choice.upper() == "C":
            model = input(" Enter custom model identifier: ").strip() or opts[0][1]
        else:
            selected = next((m[1] for m in opts if m[0] == m_choice), opts[0][1])
            model = selected

        # Step 3: Enter API Key
        key_urls = {
            "google": "https://aistudio.google.com/app/apikey",
            "openrouter": "https://openrouter.ai/keys",
            "openai": "https://platform.openai.com/api-keys",
            "groq": "https://console.groq.com/keys"
        }
        
        if p_choice == "5":
            # Local Ollama
            base_url = input("\n Enter Ollama Base URL (default: http://localhost:11434/v1): ").strip() or "http://localhost:11434/v1"
            key = "ollama"
            env_content = generate_env_content(
                active_provider="openai",
                active_model=model,
                openai_key="ollama",
                openai_base_url=base_url
            )
        else:
            url = key_urls.get(provider, "")
            print(f"\n Enter your {provider.capitalize()} API Key (Get one at: {url}):")
            key = input(" API Key: ").strip()
            
            if not key:
                print("\n ℹ️  No key entered. Generating blank universal `.env` template.")
                env_content = generate_env_content(active_provider=provider, active_model=model)
            else:
                env_content = generate_env_content(
                    active_provider=provider,
                    active_model=model,
                    gemini_key=key if provider == "google" else "",
                    openrouter_key=key if provider == "openrouter" else "",
                    openai_key=key if provider == "openai" else "",
                    groq_key=key if provider == "groq" else ""
                )

        # Save locally in current workspace
        local_env = os.path.join(os.getcwd(), ".env")
        with open(local_env, "w", encoding="utf-8") as f:
            f.write(env_content)

        load_all_env()
        print(f"\n ✓ Setup complete! Configured '{provider}' with model '{model}'.")
        print(f" ✓ Saved configuration to local .env file.")
        print(f" ℹ️  To change provider or add other keys later, simply edit your `.env` file.\n")

    except (KeyboardInterrupt, EOFError):
        print("\nExiting setup.")
        sys.exit(0)

def main():
    """CLI entrypoint for `nava` command when installed via pip or pipx."""
    ensure_api_key()

    from nava.ui.cowork_tui import CoworkTUI
    tui = CoworkTUI()
    tui.run()

if __name__ == "__main__":
    main()
