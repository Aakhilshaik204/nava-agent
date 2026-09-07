import json
import re
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field, model_validator
from nava.core.schemas import AgentState, ToolRequest
from nava.core.llm import get_llm, safe_structured_invoke
from nava.governance.dom_sanitizer import sanitize_dom

# Max history entries to keep (sliding window = last N message pairs)
_MAX_HISTORY_PAIRS = 4  # 4 pairs = 8 messages = last 4 rounds of thought

# Pattern to strip sensitive data from error messages
_SENSITIVE_ERR_PATTERN = re.compile(
    r'(api[_-]?key|token|password|secret|credential)[=:]\s*\S+',
    re.IGNORECASE
)

def _sanitize_error(error_str: str) -> str:
    """Strip API keys, tokens, and internal paths from error messages."""
    sanitized = _SENSITIVE_ERR_PATTERN.sub('[REDACTED]', error_str)
    # Also strip absolute Windows/Unix paths
    sanitized = re.sub(r'[A-Z]:\\[\w\\]+', '[PATH]', sanitized)
    sanitized = re.sub(r'/(?:home|usr|etc|var|tmp)/[\w/]+', '[PATH]', sanitized)
    return sanitized


class BrowserPlan(BaseModel):
    thoughts: str = Field(default="Navigating browser and observing web elements...")
    tool_name: str = Field(default="browser.navigate")
    arguments: dict = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_action(cls, data: dict) -> dict:
        if not isinstance(data, dict):
            return data
        if "thoughts" not in data:
            data["thoughts"] = data.get("reasoning") or data.get("thought") or data.get("rationale") or "Navigating browser..."
        if "tool_name" not in data:
            data["tool_name"] = data.get("tool") or data.get("action") or data.get("function") or "browser.navigate"
        if "arguments" not in data:
            extracted_args = data.get("args") or data.get("params") or data.get("parameters") or data.get("input") or data.get("data")
            if isinstance(extracted_args, dict):
                data["arguments"] = extracted_args
            else:
                reserved = {"thoughts", "reasoning", "thought", "rationale", "tool_name", "tool", "action", "function"}
                extra_args = {k: v for k, v in data.items() if k not in reserved}
                data["arguments"] = extra_args if extra_args else {}
        return data

def build_browser_agent(registry=None) -> StateGraph:
    """Builds the Tier 2 cyclic BrowserAgent execution graph."""
    
    workflow = StateGraph(dict)

    def plan_node(state: dict):
        agent_state: AgentState = state["agent_state"]
        observation = state.get("observation", "No observation yet.")
        consumed = state.get("consumed_steps", 0)
        max_steps = state.get("max_steps", 15)
        
        if consumed >= max_steps:
            state["plan"] = "FINISH"
            state["error"] = "LOOP_BUDGET_EXHAUSTED"
            return state

        # If observation is raw HTML, sanitize it before feeding to LLM
        if isinstance(observation, dict) and "html" in observation:
            sanitized_html, is_flagged = sanitize_dom(
                observation["html"],
                ledger=state.get("gateway").audit_ledger if state.get("gateway") else None
            )
            observation = f"Sanitized DOM (flagged={is_flagged}):\n{sanitized_html[:5000]}..."
        
        # If observation is extracted text, just truncate it
        if isinstance(observation, dict) and "text" in observation:
            text = observation["text"]
            if len(text) > 4000:
                observation = text[:4000] + "... [TRUNCATED]"
            else:
                observation = text
        
        llm = get_llm()
        
        tool_schemas_str = "No tools available."
        if registry:
            tool_schemas = []
            for t_name in agent_state.tool_scope:
                t_def = registry.get_tool(t_name)
                if t_def:
                    tool_schemas.append(f"- {t_name}: {t_def.description}\n  Schema: {json.dumps(t_def.input_schema)}")
            if tool_schemas:
                tool_schemas_str = "\n".join(tool_schemas)

        import os
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "browser_agent_prompt.txt")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()
        except Exception:
            prompt_template = "You are BrowserAgent. Goal: {goal}\nTools: {tool_schemas}"
            
        system_prompt = prompt_template.replace("{goal}", agent_state.goal).replace("{tool_schemas}", tool_schemas_str)
        messages = [SystemMessage(content=system_prompt)]
        
        # Sliding window history — keep only the last N pairs
        history = state.get("history", [])
        if len(history) > _MAX_HISTORY_PAIRS * 2:
            # Summarize older history into a single message
            old_messages = history[:-((_MAX_HISTORY_PAIRS * 2))]
            summary_parts = []
            for msg in old_messages:
                content = msg.content if hasattr(msg, 'content') else str(msg)
                summary_parts.append(content[:200])
            summary = "Summary of earlier actions:\n" + "\n".join(summary_parts)
            messages.append(HumanMessage(content=summary))
            # Keep recent history
            history = history[-((_MAX_HISTORY_PAIRS * 2)):]
        
        for h in history:
            messages.append(h)
            
        messages.append(HumanMessage(content=f"Current Observation:\n{observation}\n\nWhat is your next action?"))
        
        try:
            plan = safe_structured_invoke(llm, BrowserPlan, messages)
            
            # Record our own thought/action to history for the next iteration
            # Truncate observation in history to save context
            obs_summary = str(observation)[:500]
            history.append(HumanMessage(content=f"Observation: {obs_summary}"))
            history.append(AIMessage(content=f"Thought: {plan.thoughts}\nAction: {plan.tool_name}({json.dumps(plan.arguments)})"))
            state["history"] = history
            
            if plan.tool_name.lower() in ["finish", "none", "stop"]:
                state["plan"] = "FINISH"
                state["final_answer"] = plan.thoughts
                state["tool_request"] = None
            else:
                import uuid
                state["plan"] = plan.thoughts
                state["tool_request"] = ToolRequest(
                    request_id=f"req-{uuid.uuid4().hex[:8]}",
                    agent_id=agent_state.agent_id,
                    tool_name=plan.tool_name,
                    arguments=plan.arguments,
                    requested_scope=plan.tool_name
                )
        except Exception as e:
            sanitized_err = _sanitize_error(str(e))
            print(f"[BrowserAgent] Failed to plan: {sanitized_err}")
            state["plan"] = "FINISH"
            state["error"] = sanitized_err
            state["tool_request"] = None
            
        state["consumed_steps"] = consumed + 1
        return state

    def execute_node(state: dict):
        req = state.get("tool_request")
        if not req:
            return state
            
        gateway = state.get("gateway")
        if not gateway:
            state["observation"] = "Error: Gateway not available."
            return state
            
        print(f"\n[BrowserAgent] Executing: {req.tool_name}({req.arguments})")
        print(f"[BrowserAgent] Thoughts: {state.get('plan')}")
        
        result = gateway.process_request(req)
        state["receipt"] = result
        state["observation"] = result.result_data
        return state

    def should_continue(state: dict):
        if state.get("plan") == "FINISH" or state.get("error"):
            return "end"
        return "execute"

    workflow.add_node("plan", plan_node)
    workflow.add_node("execute", execute_node)
    
    workflow.set_entry_point("plan")
    workflow.add_conditional_edges("plan", should_continue, {"execute": "execute", "end": END})
    workflow.add_edge("execute", "plan")

    return workflow.compile()
