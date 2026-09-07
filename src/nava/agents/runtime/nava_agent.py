"""
nava_agent.py — The core NAVA ad-hoc agent.

This graph is used for any dynamically-invented agent role (e.g. ResearchAgent,
EmailAgent, DataAnalystAgent). It receives a goal, reasons about which tools to
use and what arguments to pass, then executes sequentially.

Graph: analyze → act → observe → teardown
"""
import datetime
import uuid
import os
import json
from typing import TypedDict, Optional, Dict, Any, List

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field, model_validator

from nava.core.schemas import AgentState, ToolRequest, ResultEnum, AgentStatus, Event
from nava.gateway.pipeline import ActionGateway
from nava.core.llm import get_llm, safe_structured_invoke


# ── State ─────────────────────────────────────────────────────────────────────

class NavaAgentState(TypedDict):
    agent_state: AgentState
    payload: Dict[str, Any]
    plan: Optional[Any]
    tool_requests: List[ToolRequest]
    receipts: List[Any]
    is_success: bool
    gateway: ActionGateway


# ── Output schema ─────────────────────────────────────────────────────────────

class NavAction(BaseModel):
    tool_name: str = Field(default="file.write")
    arguments: Dict[str, Any] = Field(default_factory=dict)
    requested_scope: str = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def normalize_action(cls, data: dict) -> dict:
        if not isinstance(data, dict):
            return data
        if "tool_name" not in data:
            data["tool_name"] = data.get("tool") or data.get("action") or data.get("function") or "file.write"
        if "arguments" not in data:
            extracted_args = data.get("args") or data.get("params") or data.get("parameters") or data.get("input") or data.get("data")
            if isinstance(extracted_args, dict):
                data["arguments"] = extracted_args
            else:
                reserved = {"tool_name", "tool", "action", "function", "requested_scope"}
                extra_args = {k: v for k, v in data.items() if k not in reserved}
                data["arguments"] = extra_args if extra_args else {}
        return data

class NavPlan(BaseModel):
    thoughts: str = Field(default="Analyzing task and preparing tool actions...")
    actions: List[NavAction] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_plan(cls, data: dict) -> dict:
        if not isinstance(data, dict):
            return data
        if "thoughts" not in data:
            data["thoughts"] = data.get("reasoning") or data.get("thought") or data.get("rationale") or "Analyzing task..."
        if "actions" not in data:
            if "action" in data:
                data["actions"] = [data["action"]] if isinstance(data["action"], dict) else []
            else:
                data["actions"] = []
        return data


# ── Nodes ─────────────────────────────────────────────────────────────────────

def analyze_node(state: NavaAgentState) -> NavaAgentState:
    agent_state = state["agent_state"]
    payload = state.get("payload", {})

    # Fast path for CI/test mode
    if os.environ.get("NAVA_TEST_MODE") == "1":
        actions = [
            NavAction(
                tool_name=tool_name,
                arguments=payload,
                requested_scope=agent_state.permission_scope[0] if agent_state.permission_scope else ""
            )
            for tool_name in agent_state.tool_scope
        ]
        state["plan"] = NavPlan(thoughts="Test mode — executing ceiling tools.", actions=actions)
        return state

    # Load prompt from prompts folder
    prompt_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "prompts", "nava_agent_prompt.txt"
    )
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    except Exception:
        prompt_template = "You are NavaAgent. Role: {role}. Goal: {goal}\nTools: {tools}"

    tool_schemas_str = json.dumps(payload.get("available_tool_schemas", {}), indent=2)

    system_prompt = prompt_template.replace("{role}", agent_state.role).replace("{goal}", agent_state.goal).replace("{tools}", str(agent_state.tool_scope)).replace("{scopes}", str(agent_state.permission_scope)).replace("{tool_schemas_str}", tool_schemas_str)

    llm = get_llm()

    sys_msg = SystemMessage(content=system_prompt)
    human_msg = HumanMessage(content=f"Context payload: {json.dumps(payload)}\n\nReason and produce your action plan.")

    try:
        plan: NavPlan = safe_structured_invoke(llm, NavPlan, [sys_msg, human_msg])
        print(f"\n[{agent_state.role} Thinking]:\n{plan.thoughts}\n")
        print(f"[{agent_state.role} Actions]:")
        for act in plan.actions:
            print(f"  → {act.tool_name}({act.arguments})")
        state["plan"] = plan
    except Exception as e:
        print(f"\n[{agent_state.role} Error]: LLM generation or parsing failed: {e}")
        state["plan"] = NavPlan(thoughts=f"Failed to generate plan: {e}", actions=[])
    
    return state


def act_node(state: NavaAgentState) -> NavaAgentState:
    agent_state = state["agent_state"]
    gateway = state["gateway"]
    plan: NavPlan = state["plan"]

    reqs = []
    receipts = []

    for action in plan.actions:
        req = ToolRequest(
            request_id=f"req-{uuid.uuid4().hex[:8]}",
            agent_id=agent_state.agent_id,
            tool_name=action.tool_name,
            arguments=action.arguments,
            requested_scope=action.requested_scope,
        )
        reqs.append(req)
        receipt = gateway.process_request(req)
        receipts.append(receipt)

    state["tool_requests"] = reqs
    state["receipts"] = receipts
    return state


class VerificationDecision(BaseModel):
    is_verified: bool = Field(description="True if the tool output successfully accomplished the intent. False if it failed, returned an error, or returned empty/irrelevant results.")
    reason: str = Field(description="Reasoning for the verification decision.")

def observe_node(state: NavaAgentState) -> NavaAgentState:
    receipts = state["receipts"]
    agent_state = state["agent_state"]
    gateway = state["gateway"]

    all_success = all(r.result == ResultEnum.SUCCESS for r in receipts) if receipts else False

    # True independent verification: if the tool didn't crash, we still need to verify the *content*
    is_verified = False
    verification_reason = "No receipts to verify"

    if all_success and receipts:
        llm = get_llm()
        structured_llm = llm.with_structured_output(VerificationDecision)
        
        # We need to verify what the agent actually did vs what it wanted to do
        receipt_data = [r.result_data for r in receipts]
        
        sys_msg = SystemMessage(content="You are a Verifier. Your job is to check if the tool execution actually accomplished the goal.")
        human_msg = HumanMessage(content=f"Goal: {agent_state.goal}\n\nTool Output: {receipt_data}\n\nDid this successfully achieve the goal? Or did it return an API error / no results / wrong data?")
        
        try:
            # Wire into Budget Engine to charge for this internal call
            # We estimate tokens here or could read from real callback
            # Gateway provides access to the budget_engine via orchestrator, but we have gateway object
            if hasattr(gateway, 'budget_engine'):
                gateway.budget_engine.consume_internal_llm_call(agent_state.budget_ref, tokens=200)
                
            decision: VerificationDecision = structured_llm.invoke([sys_msg, human_msg])
            is_verified = decision.is_verified
            verification_reason = decision.reason
            print(f"[{agent_state.role} Verification]: {decision.is_verified} — {decision.reason}")
        except Exception as e:
            # Fallback if verifier fails
            is_verified = False
            verification_reason = f"Verification LLM failed: {e}"
    else:
        is_verified = False
        verification_reason = "Tool execution failed at the Gateway layer."

    event = Event(
        event_id=f"evt-{uuid.uuid4().hex[:8]}",
        event_type="VERIFICATION_PASSED" if is_verified else "FAILED",
        task_id=agent_state.goal,
        agent_id=agent_state.agent_id,
        payload=(
            {"receipt_ids": [r.receipt_id for r in receipts], "reason": verification_reason}
            if is_verified
            else {"reason": verification_reason, "receipt_ids": [r.receipt_id for r in receipts] if receipts else []}
        ),
    )
    gateway.audit_ledger.append_event(event)
    state["is_success"] = is_verified
    return state


def teardown_node(state: NavaAgentState) -> NavaAgentState:
    state["agent_state"].status = AgentStatus.TERMINATED
    return state


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_nava_agent() -> StateGraph:
    """Build the NAVA ad-hoc agent graph used for any dynamically-invented role."""
    workflow = StateGraph(NavaAgentState)

    workflow.add_node("analyze", analyze_node)
    workflow.add_node("act", act_node)
    workflow.add_node("observe", observe_node)
    workflow.add_node("teardown", teardown_node)

    workflow.add_edge(START, "analyze")
    workflow.add_edge("analyze", "act")
    workflow.add_edge("act", "observe")
    workflow.add_edge("observe", "teardown")
    workflow.add_edge("teardown", END)

    return workflow.compile()
