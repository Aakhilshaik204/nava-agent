"""
file_agent.py — Agent graph for file-producing agents.

Used by: DocumentAgent, DataAgent, VerifierAgent, UniversalFileAgent.
These agents receive a goal and produce a single file output (PDF, DOCX,
PPTX, TXT, CSV etc.) using one tool call.

Graph: plan → teardown (single-shot, no retry loop)
"""
import datetime
import uuid
import os
import json
from typing import TypedDict, Optional, Dict, Any, List

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from nava.core.schemas import AgentState, ToolRequest, ResultEnum, AgentStatus, Event
from nava.gateway.pipeline import ActionGateway
from nava.core.llm import get_llm, safe_structured_invoke
from pydantic import BaseModel, Field, model_validator


# ── State ─────────────────────────────────────────────────────────────────────

class FileAgentState(TypedDict):
    agent_state: AgentState
    payload: Dict[str, Any]
    plan: Optional[str]
    tool_request: Optional[ToolRequest]
    receipt: Optional[Any]
    is_success: bool
    gateway: ActionGateway


# ── Output schema ─────────────────────────────────────────────────────────────

class FileDecision(BaseModel):
    thoughts: str = Field(default="Executing file operation...")
    tool_name: str = Field(default="file.write")
    arguments: Dict[str, Any] = Field(default_factory=dict)
    requested_scope: str = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def normalize_action(cls, data: dict) -> dict:
        if not isinstance(data, dict):
            return data
        if "thoughts" not in data:
            data["thoughts"] = data.get("reasoning") or data.get("thought") or data.get("rationale") or "Executing file operation..."
        if "tool_name" not in data:
            data["tool_name"] = data.get("tool") or data.get("action") or data.get("function") or "file.write"
        if "arguments" not in data:
            extracted_args = data.get("args") or data.get("params") or data.get("parameters") or data.get("input") or data.get("data")
            if isinstance(extracted_args, dict):
                data["arguments"] = extracted_args
            else:
                reserved = {"thoughts", "reasoning", "thought", "rationale", "tool_name", "tool", "action", "function", "requested_scope"}
                extra_args = {k: v for k, v in data.items() if k not in reserved}
                data["arguments"] = extra_args if extra_args else {}
        return data


# ── Nodes ─────────────────────────────────────────────────────────────────────

def plan_node(state: FileAgentState) -> FileAgentState:
    agent_state = state["agent_state"]
    payload = state.get("payload", {})

    # Fast path for CI/test mode
    if os.environ.get("NAVA_TEST_MODE") == "1":
        tool = "file.create_txt" if "file.create_txt" in agent_state.tool_scope else agent_state.tool_scope[0]
        state["plan"] = tool
        state["tool_request"] = ToolRequest(
            request_id=f"req-{uuid.uuid4().hex[:8]}",
            agent_id=agent_state.agent_id,
            tool_name=tool,
            arguments={"filename": payload.get("filename"), "content": payload.get("content")},
            requested_scope=agent_state.permission_scope[0] if agent_state.permission_scope else ""
        )
        return state

    # Load prompt from prompts folder
    prompt_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "prompts", "file_agent_prompt.txt"
    )
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    except Exception:
        prompt_template = "You are FileAgent. Role: {role}. Goal: {goal}\nTools: {tool_schemas_str}"

    tool_schemas = payload.get("available_tool_schemas", agent_state.tool_scope)

    system_prompt = prompt_template.replace("{role}", agent_state.role).replace("{goal}", agent_state.goal).replace("{tool_schemas_str}", json.dumps(tool_schemas, indent=2))

    llm = get_llm()

    sys_msg = SystemMessage(content=system_prompt + f"\nAvailable scopes: {agent_state.permission_scope}")
    human_msg = HumanMessage(content=f"Payload: {json.dumps(payload)}\nDecide which tool to use and its arguments.")

    try:
        decision: FileDecision = safe_structured_invoke(llm, FileDecision, [sys_msg, human_msg])
        print(f"\n[{agent_state.role} Thinking]:\n{decision.thoughts}\n")
        print(f"[{agent_state.role} Action]:\n  → {decision.tool_name}({decision.arguments})\n")
    except Exception as e:
        print(f"\n[{agent_state.role} Error]: LLM generation or parsing failed: {e}")
        fallback_tool = agent_state.tool_scope[0] if agent_state.tool_scope else "file.write"
        decision = FileDecision(thoughts=f"Recovered from parsing: {e}", tool_name=fallback_tool, arguments={})

    state["plan"] = decision.tool_name
    req_scope = decision.requested_scope or (agent_state.permission_scope[0] if agent_state.permission_scope else "")
    state["tool_request"] = ToolRequest(
        request_id=f"req-{uuid.uuid4().hex[:8]}",
        agent_id=agent_state.agent_id,
        tool_name=decision.tool_name,
        arguments=decision.arguments,
        requested_scope=req_scope
    )
    return state


def teardown_node(state: FileAgentState) -> FileAgentState:
    state["agent_state"].status = AgentStatus.TERMINATED
    return state


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_file_agent() -> StateGraph:
    """Build the single-shot file-producing agent graph."""
    workflow = StateGraph(FileAgentState)

    workflow.add_node("plan", plan_node)
    workflow.add_node("teardown", teardown_node)

    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "teardown")
    workflow.add_edge("teardown", END)

    return workflow.compile()
