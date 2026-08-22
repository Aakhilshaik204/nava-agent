import datetime
import uuid
import os
import json
from typing import TypedDict, Optional, Dict, Any, List
from langgraph.graph import StateGraph, START, END

from nava.core.schemas import AgentState, ToolRequest, ResultEnum, AgentStatus, Event
from nava.gateway.pipeline import ActionGateway
from nava.core.llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from nava.tools.registry import ToolRegistry

class GraphState(TypedDict):
    agent_state: AgentState
    payload: Dict[str, Any]
    plan: Optional[str]
    tool_request: Optional[ToolRequest]
    observation: Optional[Any]
    gateway: ActionGateway

class PlanDecision(BaseModel):
    thoughts: str = Field(description="Your step-by-step reasoning for choosing this tool.")
    tool_name: str = Field(description="The name of the tool to execute. Must be 'FINISH' if you are completely done.")
    arguments: Dict[str, Any] = Field(description="The arguments for the tool.")
    requested_scope: str = Field(description="The permission scope required for this tool.")

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
    structured_llm = llm.with_structured_output(PlanDecision)
    
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "reviewer_agent_prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
        
    tool_schemas = payload.get("available_tool_schemas", agent_state.tool_scope)
        
    system_prompt = prompt_template.format(
        role=agent_state.role,
        goal=agent_state.goal,
        tool_schemas_str=json.dumps(tool_schemas, indent=2)
    )
    
    sys_msg = SystemMessage(content=system_prompt + f"\nAvailable scopes: {agent_state.permission_scope}")
    
    history = state.get("history", [])
    
    # Construct context
    context_str = f"Payload: {json.dumps(payload)}\n"
    if history:
        context_str += "\n[YOUR PREVIOUS ACTIONS & OBSERVATIONS]\n" + "\n".join(history) + "\n"
        
    if observation:
        context_str += f"\n[LATEST OBSERVATION]\nResult: {json.dumps(observation)}\n"
    
    human_msg = HumanMessage(content=context_str + "\nDecide which tool to use next, or 'FINISH' if you are done.")
    
    decision: PlanDecision = structured_llm.invoke([sys_msg, human_msg])
    
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
        req = ToolRequest(
            request_id=f"req-{uuid.uuid4().hex[:8]}",
            agent_id=agent_state.agent_id,
            tool_name=decision.tool_name,
            arguments=decision.arguments,
            requested_scope=decision.requested_scope
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
