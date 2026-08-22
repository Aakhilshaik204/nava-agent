import os
import json
import uuid
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel
from nava.core.schemas import AgentState, AgentStatus, ToolRequest
from nava.core.llm import get_llm

class ComputerPlan(BaseModel):
    thoughts: str
    tool_name: str
    arguments: dict

def build_computer_agent(registry=None) -> StateGraph:
    """Builds the Tier 2 cyclic ComputerAgent execution graph for Desktop OS automation."""
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
        structured_llm = llm.with_structured_output(ComputerPlan)
        
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "computer_agent_prompt.txt")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()
        except Exception:
            prompt_template = "You are ComputerAgent. Goal: {goal}\nTools:\n{tool_schemas_str}"

        system_prompt = prompt_template.format(
            goal=agent_state.goal,
            tool_schemas_str=tool_schemas_str
        )
                        
        sys_msg = SystemMessage(content=system_prompt)
        history = state.get("history", [])
        content = f"Objective Context: {json.dumps(payload)}\n"
        if history:
            content += "Recent Actions & Observations:\n"
            for item in history[-3:]:
                content += f"- Action: {item.get('action')}, Result: {item.get('observation')}\n"
                
        if observation:
            content += f"\nLast Tool Observation: {observation}\n"
            
        content += "\nPlan your next desktop action or emit FINISH if complete."
        human_msg = HumanMessage(content=content)
        
        try:
            plan = structured_llm.invoke([sys_msg, human_msg])
            state["plan"] = plan.tool_name
            state["arguments"] = plan.arguments
            state["thoughts"] = plan.thoughts
        except Exception as e:
            state["plan"] = "FINISH"
            state["error"] = str(e)
            
        return state

    def act_node(state: dict):
        tool_name = state.get("plan")
        arguments = state.get("arguments", {})
        agent_state: AgentState = state["agent_state"]
        gateway = state.get("gateway")
        
        if tool_name == "FINISH":
            state["is_success"] = True
            return state

        req = ToolRequest(
            request_id=f"req-{uuid.uuid4().hex[:8]}",
            agent_id=agent_state.agent_id,
            tool_name=tool_name,
            arguments=arguments,
            requested_scope=tool_name
        )
        
        try:
            receipt = gateway.process_request(req, agent_state)
            state["receipt"] = receipt
            state["observation"] = receipt.data if receipt else "No receipt emitted."
        except Exception as e:
            state["error"] = str(e)
            state["observation"] = f"Execution failed: {e}"
            
        # Update history
        history = state.get("history", [])
        history.append({
            "action": f"{tool_name}({arguments})",
            "observation": str(state.get("observation", ""))[:300]
        })
        state["history"] = history
        return state

    def should_continue(state: dict):
        if state.get("is_success") or state.get("plan") == "FINISH":
            return END
        if state.get("error") and "LOOP_BUDGET_EXHAUSTED" in state.get("error", ""):
            return END
        return "plan"

    workflow.add_node("plan", plan_node)
    workflow.add_node("act", act_node)
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "act")
    workflow.add_conditional_edges("act", should_continue, {"plan": "plan", END: END})

    return workflow.compile()
