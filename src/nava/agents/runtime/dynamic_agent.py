"""
dynamic_agent.py — Cyclic multi-step agent for DynamicAgent roles.

Same execution graph as CodingAgent (plan → observe → plan → ... → FINISH),
but uses dynamic_agent_prompt.txt which allows writing any file type (.txt,
.md, .json, etc.) without the coding-only restrictions of CodingAgent.
"""
import os
import json
import uuid
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field, model_validator
from nava.core.schemas import AgentState, AgentStatus, ToolRequest
from nava.core.llm import get_llm, safe_structured_invoke


class DynamicPlan(BaseModel):
    thoughts: str = Field(default="Executing task step...")
    tool_name: str = Field(default="file.write")
    arguments: dict = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_action(cls, data: dict) -> dict:
        if not isinstance(data, dict):
            return data
        if "thoughts" not in data:
            data["thoughts"] = data.get("reasoning") or data.get("thought") or data.get("rationale") or "Executing task step..."
        if "tool_name" not in data:
            data["tool_name"] = data.get("tool") or data.get("action") or data.get("function") or "file.write"
        if "arguments" not in data:
            extracted_args = data.get("args") or data.get("params") or data.get("parameters") or data.get("input") or data.get("data")
            if isinstance(extracted_args, dict):
                data["arguments"] = extracted_args
            else:
                reserved = {"thoughts", "reasoning", "thought", "rationale", "tool_name", "tool", "action", "function"}
                extra_args = {k: v for k, v in data.items() if k not in reserved}
                data["arguments"] = extra_args if extra_args else {}
        return data


def build_dynamic_agent(registry=None) -> StateGraph:
    """Builds a cyclic multi-step agent for DynamicAgent roles."""

    workflow = StateGraph(dict)

    def plan_node(state: dict):
        agent_state: AgentState = state["agent_state"]
        payload = state.get("payload", {})
        observation = state.get("observation")

        if agent_state.status != AgentStatus.RUNNING:
            agent_state.status = AgentStatus.RUNNING

        tool_schemas_str = "No tools available."
        if registry:
            tool_schemas = []
            for t_name in agent_state.tool_scope:
                t_def = registry.get_tool(t_name)
                if t_def:
                    tool_schemas.append(f"- {t_name}: {t_def.description}\n  Schema: {json.dumps(t_def.input_schema)}")
            if tool_schemas:
                tool_schemas_str = "\n".join(tool_schemas)

        llm = get_llm()

        prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "dynamic_agent_prompt.txt")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()
        except Exception:
            prompt_template = "You are DynamicAgent. Goal: {goal}\nTools: {tool_schemas_str}"

        # Extract skill catalog from orchestrator payload (injected by SkillManager)
        skill_catalog = payload.get("context", "")

        system_prompt = prompt_template.replace("{goal}", agent_state.goal).replace("{tool_schemas_str}", tool_schemas_str).replace("{skill_catalog}", str(skill_catalog))

        sys_msg = SystemMessage(content=system_prompt)

        history = state.get("history", [])

        content = f"Payload: {json.dumps(payload)}\n"
        if history:
            content += "\n[YOUR PREVIOUS ACTIONS & OBSERVATIONS]\n" + "\n".join(history) + "\n"

        if observation:
            content += f"\n[LATEST OBSERVATION]\nResult: {json.dumps(observation)}\n"

        human_msg = HumanMessage(content=content)

        try:
            decision = safe_structured_invoke(llm, DynamicPlan, [sys_msg, human_msg])
            print(f"\n[DynamicAgent Thinking]:\n{decision.thoughts}\n")
        except Exception as e:
            print(f"\n[DynamicAgent Error]: LLM generation or parsing failed: {e}")
            fallback_tool = agent_state.tool_scope[0] if agent_state.tool_scope else "file.write"
            decision = DynamicPlan(thoughts=f"Recovered from parsing error: {e}", tool_name=fallback_tool, arguments={})

        new_history = history.copy()
        if observation:
            obs_str = json.dumps(observation)
            if len(obs_str) > 1500:
                obs_str = obs_str[:1500] + "... [TRUNCATED for history context]"
            new_history.append(f"Observation: {obs_str}")

        new_history.append(f"Action taken: {decision.tool_name}, args: {json.dumps(decision.arguments)}")
        state["history"] = new_history

        # Invariant: Never finish on Step 1 if history has 0 actions
        if decision.tool_name == "FINISH" and len(history) == 0:
            fallback_tool = agent_state.tool_scope[0] if agent_state.tool_scope else "file.write"
            decision.tool_name = fallback_tool
            decision.arguments = {}

        if decision.tool_name == "FINISH":
            state["tool_request"] = None
            state["plan"] = "FINISH"
            return state

        # Resolve correct scope for this specific tool
        resolved_scope = agent_state.permission_scope[0] if agent_state.permission_scope else ""
        if registry:
            try:
                t_def = registry.get_tool(decision.tool_name)
                if t_def and t_def.permissions_required:
                    resolved_scope = t_def.permissions_required[0]
            except Exception:
                pass
        req = ToolRequest(
            request_id=f"req-{uuid.uuid4().hex[:8]}",
            agent_id=agent_state.agent_id,
            tool_name=decision.tool_name,
            arguments=decision.arguments,
            requested_scope=resolved_scope
        )
        state["tool_request"] = req
        state["plan"] = decision.tool_name
        return state

    workflow.add_node("plan", plan_node)
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", END)

    return workflow.compile()
