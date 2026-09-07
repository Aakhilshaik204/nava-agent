"""
Shared Universal LLM factory for NAVA.
Fully provider-agnostic and user-configurable via .env.

Supported Providers:
    - google      → Google Gemini API (gemini-2.5-flash, gemini-2.5-pro, etc.)
    - openrouter  → OpenRouter Unified Gateway (Claude 3.5, DeepSeek R1, GPT-4o, Llama 3.3, etc.)
    - openai      → OpenAI API or local/proxy endpoints (Ollama, vLLM, LatentStack, LMStudio)
    - groq        → Groq Ultra-fast Inference (Llama 3.3 70B, etc.)
    - latentstack → LatentStack / Custom OpenAI-compatible proxy gateways
"""
import os
import sys
import json
import re
from dotenv import load_dotenv

def get_llm():
    # Load local workspace .env
    local_env = os.path.join(os.getcwd(), ".env")
    if os.path.exists(local_env):
        load_dotenv(local_env, override=True)

    # Detect provider from .env or auto-infer from available API keys / endpoints
    provider = os.environ.get("LLM_PROVIDER", "").lower().strip()
    
    # Generic / Custom API variables (e.g. LatentStack hackathon keys)
    custom_base_url = os.environ.get("API_BASE") or os.environ.get("LATENTSTACK_BASE_URL")
    custom_api_key = os.environ.get("API_KEY") or os.environ.get("LATENTSTACK_API_KEY")
    
    if not provider:
        if custom_base_url or (custom_api_key and custom_api_key.startswith("ls-")):
            provider = "latentstack"
        elif os.environ.get("OPENROUTER_API_KEY"):
            provider = "openrouter"
        elif os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            provider = "google"
        elif os.environ.get("GROQ_API_KEY"):
            provider = "groq"
        elif os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
        else:
            provider = "google"

    # Default fallback models per provider if not specified in .env
    default_models = {
        "google": "gemini-2.5-flash",
        "openrouter": "anthropic/claude-3.5-sonnet",
        "openai": "gpt-4o",
        "groq": "llama-3.3-70b-versatile",
        "latentstack": "gemini/gemini-3.7-flash"
    }

    # Model is read directly from LLM_MODEL or MODEL_NAME in user's .env file
    model = (
        os.environ.get("LLM_MODEL") or 
        os.environ.get("MODEL_NAME") or 
        default_models.get(provider, "gemini-2.5-flash")
    ).strip()

    # Provider: Google Gemini
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            if os.environ.get("NAVA_TEST_MODE") == "1":
                api_key = "mock_key_for_testing"
            else:
                raise ValueError(
                    "Missing Gemini API Key! Please set GEMINI_API_KEY in your .env file.\n"
                    "Get a key from: https://aistudio.google.com/app/apikey"
                )
        return ChatGoogleGenerativeAI(model=model, max_retries=10, google_api_key=api_key)

    # Provider: OpenRouter (All Models: Claude, OpenAI, DeepSeek, Mistral, Meta)
    elif provider == "openrouter":
        from langchain_openai import ChatOpenAI
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "Missing OpenRouter API Key! Please set OPENROUTER_API_KEY in your .env file.\n"
                "Get a key from: https://openrouter.ai/keys"
            )
        base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        return ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            openai_api_base=base_url,
        )

    # Provider: Groq
    elif provider == "groq":
        from langchain_groq import ChatGroq
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "Missing Groq API Key! Please set GROQ_API_KEY in your .env file.\n"
                "Get a key from: https://console.groq.com/keys"
            )
        return ChatGroq(
            model=model,
            api_key=api_key,
        )

    # Provider: LatentStack or Generic OpenAI-compatible Proxy Gateway
    elif provider in ["latentstack", "custom"]:
        from langchain_openai import ChatOpenAI
        api_key = custom_api_key or os.environ.get("OPENAI_API_KEY")
        base_url = custom_base_url or os.environ.get("OPENAI_BASE_URL", "https://latentstack.dev/v1")
        if not api_key:
            raise ValueError(
                "Missing API_KEY! Please set API_KEY in your .env file."
            )
        return ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            openai_api_base=base_url,
        )

    # Provider: OpenAI (Official api.openai.com or local Ollama / vLLM / LMStudio)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.environ.get("OPENAI_API_KEY") or custom_api_key
        base_url = os.environ.get("OPENAI_BASE_URL") or custom_base_url
        
        # If using custom local endpoint (e.g. Ollama) without key, default key to "ollama"
        if not api_key:
            if base_url:
                api_key = "ollama"
            elif os.environ.get("NAVA_TEST_MODE") == "1":
                api_key = "mock_key_for_testing"
            else:
                raise ValueError(
                    "Missing OpenAI API Key! Please set OPENAI_API_KEY in your .env file.\n"
                    "Get a key from: https://platform.openai.com/api-keys\n"
                    "(Or set OPENAI_BASE_URL=http://localhost:11434/v1 for local Ollama)"
                )
                
        kwargs = {"model": model, "openai_api_key": api_key}
        if base_url and base_url.strip():
            kwargs["openai_api_base"] = base_url.strip()
            
        return ChatOpenAI(**kwargs)

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{provider}'. "
            "Supported values in .env: 'google', 'openrouter', 'groq', 'openai', 'latentstack'"
        )

def _extract_dict_from_response(raw_res, schema):
    """Deep inspection of AIMessage to extract structured dictionary across all model/proxy variants."""
    # 1. Native tool_calls field on AIMessage
    if hasattr(raw_res, "tool_calls") and raw_res.tool_calls:
        for tc in raw_res.tool_calls:
            if isinstance(tc, dict) and "args" in tc and isinstance(tc["args"], dict):
                try:
                    return schema.model_validate(tc["args"])
                except Exception:
                    pass

    # 2. Raw additional_kwargs (e.g. OpenAI function_call or tool_calls)
    if hasattr(raw_res, "additional_kwargs") and raw_res.additional_kwargs:
        tcs = raw_res.additional_kwargs.get("tool_calls", [])
        if isinstance(tcs, list):
            for tc in tcs:
                if isinstance(tc, dict) and "function" in tc:
                    fn_args = tc["function"].get("arguments")
                    if isinstance(fn_args, str):
                        try:
                            return schema.model_validate(json.loads(fn_args))
                        except Exception:
                            pass
                    elif isinstance(fn_args, dict):
                        try:
                            return schema.model_validate(fn_args)
                        except Exception:
                            pass
                            
        fn_call = raw_res.additional_kwargs.get("function_call")
        if fn_call and isinstance(fn_call, dict):
            fn_args = fn_call.get("arguments")
            if isinstance(fn_args, str):
                try:
                    return schema.model_validate(json.loads(fn_args))
                except Exception:
                    pass
            elif isinstance(fn_args, dict):
                try:
                    return schema.model_validate(fn_args)
                except Exception:
                    pass

    # 3. Text content (string or list of content blocks)
    raw_content = raw_res.content if hasattr(raw_res, "content") else str(raw_res)
    if isinstance(raw_content, list):
        text_parts = []
        for part in raw_content:
            if isinstance(part, dict) and "text" in part:
                text_parts.append(part["text"])
            elif isinstance(part, str):
                text_parts.append(part)
        raw_text = "\n".join(text_parts)
    else:
        raw_text = str(raw_content)

    clean_text = raw_text.strip()
    if "```json" in clean_text:
        clean_text = clean_text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in clean_text:
        clean_text = clean_text.split("```", 1)[1].split("```", 1)[0].strip()

    if clean_text:
        try:
            data = json.loads(clean_text)
            return schema.model_validate(data)
        except Exception:
            match = re.search(r'(\{[\s\S]*\})', clean_text)
            if match:
                try:
                    data = json.loads(match.group(1))
                    return schema.model_validate(data)
                except Exception:
                    pass

    return None

def safe_structured_invoke(llm, schema, messages):
    """
    Invokes LLM with structured output schema with robust multi-layer fallback
    for proxies/models that wrap JSON in markdown blocks (```json ... ```),
    place output in tool_calls, or return structured dictionaries.
    """
    # Attempt 1: Native with_structured_output
    try:
        structured_llm = llm.with_structured_output(schema)
        res = structured_llm.invoke(messages)
        if isinstance(res, schema):
            return res
        if isinstance(res, dict):
            return schema.model_validate(res)
    except Exception:
        pass

    # Attempt 2: Direct invoke and deep response inspection
    try:
        raw_res = llm.invoke(messages)
        parsed = _extract_dict_from_response(raw_res, schema)
        if parsed is not None:
            return parsed
    except Exception:
        pass

    # Attempt 3: Direct JSON schema guidance retry with complete schema specification
    try:
        from langchain_core.messages import HumanMessage
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        retry_msg = HumanMessage(content=(
            f"You MUST respond ONLY with a single valid JSON object matching this schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"Do not include any conversational explanation or markdown outside the JSON block."
        ))
        raw_res2 = llm.invoke(messages + [retry_msg])
        parsed2 = _extract_dict_from_response(raw_res2, schema)
        if parsed2 is not None:
            return parsed2
    except Exception:
        pass

    # Attempt 4: Safe default initialization if schema supports defaults
    try:
        return schema()
    except Exception:
        pass

    raise ValueError(f"Could not parse valid JSON for {schema.__name__} from model response.")
