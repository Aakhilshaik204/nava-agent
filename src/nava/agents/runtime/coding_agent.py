import os
import json
import uuid
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel
from nava.core.schemas import AgentState, AgentStatus, ToolRequest
from nava.core.llm import get_llm

class CodingPlan(BaseModel):
    thoughts: str
    tool_name: str
    arguments: dict

def build_coding_agent(registry=None) -> StateGraph:
    """Builds the Tier 2 cyclic coding agent execution graph."""
    
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
        structured_llm = llm.with_structured_output(CodingPlan)
        
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "coding_agent_prompt.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()

        # Extract skill catalog from orchestrator payload (injected by SkillManager)
        skill_catalog = payload.get("context", "")

        system_prompt = prompt_template.format(
            goal=agent_state.goal,
            tool_schemas_str=tool_schemas_str,
            skill_catalog=skill_catalog
        )
                        
        sys_msg = SystemMessage(content=system_prompt)
        
        history = state.get("history", [])
        
        content = f"Payload: {json.dumps(payload)}\n"
        if history:
            content += "\n[YOUR PREVIOUS ACTIONS & OBSERVATIONS]\n" + "\n".join(history) + "\n"
            
        if observation:
            content += f"\n[LATEST OBSERVATION]\nResult: {json.dumps(observation)}\n"
            
        human_msg = HumanMessage(content=content)
        
        try:
            decision = structured_llm.invoke([sys_msg, human_msg])
            print(f"\n[CodingAgent Thinking]:\n{decision.thoughts}\n")
        except Exception as e:
            print(f"\n[CodingAgent Error]: LLM generation or parsing failed: {e}")
            decision = CodingPlan(thoughts=f"Fatal error parsing structured output: {e}", tool_name="FINISH", arguments={})
        
        new_history = history.copy()
        if observation:
            # Truncate large observations before appending to history so we don't blow up the context window
            obs_str = json.dumps(observation)
            if len(obs_str) > 1500:
                obs_str = obs_str[:1500] + "... [TRUNCATED for history context]"
            new_history.append(f"Observation: {obs_str}")
            
        new_history.append(f"Action taken: {decision.tool_name}, args: {json.dumps(decision.arguments)}")
        state["history"] = new_history
        
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
