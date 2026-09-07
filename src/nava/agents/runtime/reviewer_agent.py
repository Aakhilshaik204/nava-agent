import datetime
import uuid
import os
import json
from typing import TypedDict, Optional, Dict, Any, List
from langgraph.graph import StateGraph, START, END

from nava.core.schemas import AgentState, ToolRequest, ResultEnum, AgentStatus, Event
from nava.gateway.pipeline import ActionGateway
from nava.core.llm import get_llm, safe_structured_invoke
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field, model_validator
from nava.tools.registry import ToolRegistry

class GraphState(TypedDict):
    agent_state: AgentState
    payload: Dict[str, Any]
    plan: Optional[str]
    tool_request: Optional[ToolRequest]
    observation: Optional[Any]
    gateway: ActionGateway

class PlanDecision(BaseModel):
    thoughts: str = Field(default="Reviewing codebase and evaluating changes...")
    tool_name: str = Field(default="FINISH")
    arguments: Dict[str, Any] = Field(default_factory=dict)
    requested_scope: str = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def normalize_action(cls, data: dict) -> dict:
        if not isinstance(data, dict):
            return data
        if "thoughts" not in data:
            data["thoughts"] = data.get("reasoning") or data.get("thought") or data.get("rationale") or "Reviewing codebase..."
        if "tool_name" not in data:
            data["tool_name"] = data.get("tool") or data.get("action") or data.get("function") or "FINISH"
        if "arguments" not in data:
            extracted_args = data.get("args") or data.get("params") or data.get("parameters") or data.get("input") or data.get("data")
            if isinstance(extracted_args, dict):
                data["arguments"] = extracted_args
            else:
                reserved = {"thoughts", "reasoning", "thought", "rationale", "tool_name", "tool", "action", "function", "requested_scope"}
                extra_args = {k: v for k, v in data.items() if k not in reserved}
                data["arguments"] = extra_args if extra_args else {}
        return data

def plan_node(state: GraphState) -> GraphState:
    agent_state = state["agent_state"]
    payload = state.get("payload", {})
    observation = state.get("observation", None)
    
    # Fast path for testing
    if os.environ.get("NAVA_TEST_MODE") == "1":
        if not observation:
            state["plan"] = "code.diff_review"
            state["tool_request"] = ToolRequest(
                request_id=f"req-{uuid.uuid4().hex[:8]}",
                agent_id=agent_state.agent_id,
                tool_name="code.diff_review",
                arguments={"filename": "test.py"},
                requested_scope=agent_state.permission_scope[0] if agent_state.permission_scope else ""
            )
            return state
        else:
            state["plan"] = "FINISH"
            state["tool_request"] = None
            return state

    llm = get_llm()
    
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "reviewer_agent_prompt.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    except Exception:
        prompt_template = "You are ReviewerAgent. Goal: {goal}\nTools: {tool_schemas_str}"
        
    tool_schemas = payload.get("available_tool_schemas", agent_state.tool_scope)
        
    system_prompt = prompt_template.replace("{role}", agent_state.role).replace("{goal}", agent_state.goal).replace("{tool_schemas_str}", json.dumps(tool_schemas, indent=2))
    
    sys_msg = SystemMessage(content=system_prompt + f"\nAvailable scopes: {agent_state.permission_scope}")
    
    history = state.get("history", [])
    
    # Construct context
    context_str = f"Payload: {json.dumps(payload)}\n"
    if history:
        context_str += "\n[YOUR PREVIOUS ACTIONS & OBSERVATIONS]\n" + "\n".join(history) + "\n"
        
    if observation:
        context_str += f"\n[LATEST OBSERVATION]\nResult: {json.dumps(observation)}\n"
    
    human_msg = HumanMessage(content=context_str + "\nDecide which tool to use next, or 'FINISH' if you are done.")
    
    try:
        decision = safe_structured_invoke(llm, PlanDecision, [sys_msg, human_msg])
    except Exception as e:
        decision = PlanDecision(thoughts=f"Parsing recovered: {e}", tool_name="FINISH", arguments={})
    
    new_history = history.copy()
    if observation:
        new_history.append(f"Observation: {json.dumps(observation)}")
    new_history.append(f"Action taken: {decision.tool_name}, args: {json.dumps(decision.arguments)}")
    state["history"] = new_history
    
    print(f"\n[ReviewerAgent Thinking]:\n{decision.thoughts}\n")
    
    if decision.tool_name == "FINISH":
        state["plan"] = "FINISH"
        state["tool_request"] = None
    else:
        req_scope = decision.requested_scope or (agent_state.permission_scope[0] if agent_state.permission_scope else "")
        req = ToolRequest(
            request_id=f"req-{uuid.uuid4().hex[:8]}",
            agent_id=agent_state.agent_id,
            tool_name=decision.tool_name,
            arguments=decision.arguments,
            requested_scope=req_scope
        )
        state["tool_request"] = req
        state["plan"] = decision.tool_name
        
    return state

def build_reviewer_agent(registry: ToolRegistry) -> StateGraph:
    workflow = StateGraph(GraphState)
    
    workflow.add_node("plan", plan_node)
    
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", END)
    
    return workflow.compile()
