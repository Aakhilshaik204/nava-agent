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
from nava.core.llm import get_llm


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
    thoughts: str = Field(description="Step-by-step reasoning for choosing this tool and these arguments.")
    tool_name: str = Field(description="The name of the tool to execute.")
    arguments: Dict[str, Any] = Field(description="The exact arguments for the tool.")
    requested_scope: str = Field(description="The permission scope required for this tool.")


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
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    tool_schemas = payload.get("available_tool_schemas", agent_state.tool_scope)

    system_prompt = prompt_template.format(
        role=agent_state.role,
        goal=agent_state.goal,
        tool_schemas_str=json.dumps(tool_schemas, indent=2)
    )

    llm = get_llm()
    structured_llm = llm.with_structured_output(FileDecision)

    sys_msg = SystemMessage(content=system_prompt + f"\nAvailable scopes: {agent_state.permission_scope}")
    human_msg = HumanMessage(content=f"Payload: {json.dumps(payload)}\nDecide which tool to use and its arguments.")

    try:
        decision: FileDecision = structured_llm.invoke([sys_msg, human_msg])
        print(f"\n[{agent_state.role} Thinking]:\n{decision.thoughts}\n")
        print(f"[{agent_state.role} Action]:\n  → {decision.tool_name}({decision.arguments})\n")
    except Exception as e:
        print(f"\n[{agent_state.role} Error]: LLM generation or parsing failed: {e}")
        # Graceful fallback so it doesn't crash the orchestrator
        state["plan"] = "FAILED"
        state["tool_request"] = None
        state["is_success"] = False
        return state

    state["plan"] = decision.tool_name
    state["tool_request"] = ToolRequest(
        request_id=f"req-{uuid.uuid4().hex[:8]}",
        agent_id=agent_state.agent_id,
        tool_name=decision.tool_name,
        arguments=decision.arguments,
        requested_scope=decision.requested_scope
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
