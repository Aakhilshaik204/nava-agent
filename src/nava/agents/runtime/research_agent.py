import os
import json
import uuid
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel
from nava.core.schemas import AgentState, AgentStatus, ToolRequest
from nava.core.llm import get_llm

class ResearchPlan(BaseModel):
    thoughts: str
    tool_name: str
    arguments: dict

def build_research_agent(registry=None) -> StateGraph:
    """Builds the Tier 2 cyclic ResearchAgent execution graph for multi-source research and synthesis."""
    workflow = StateGraph(dict)

    def plan_node(state: dict):
        agent_state: AgentState = state["agent_state"]
        payload = state.get("payload", {})
        observation = state.get("observation")
        history = state.get("history", [])
        
        if agent_state.status != AgentStatus.RUNNING:
            agent_state.status = AgentStatus.RUNNING
            
        tool_schemas = []
        if registry:
            for t_name in agent_state.tool_scope:
                t_def = registry.get_tool(t_name)
                if t_def:
                    tool_schemas.append(f"- {t_name}: {t_def.description}\n  Schema: {json.dumps(t_def.input_schema)}")
        tool_schemas_str = "\n".join(tool_schemas) if tool_schemas else "No tools available."

        llm = get_llm()
        structured_llm = llm.with_structured_output(ResearchPlan)
        
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "research_agent_prompt.txt")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()
        except Exception:
            prompt_template = "You are ResearchAgent. Goal: {goal}\nTools:\n{tool_schemas_str}"

        system_prompt = prompt_template.format(
            goal=agent_state.goal,
            tool_schemas_str=tool_schemas_str
        )
                        
        sys_msg = SystemMessage(content=system_prompt)
        
        content = f"Research Payload / Prior Context: {json.dumps(payload)}\n"
        if history:
            content += "\n[PREVIOUS RESEARCH ACTIONS & OBSERVATIONS]\n"
            for item in history[-4:]:
                content += f"- Action: {item.get('action')}\n  Result: {str(item.get('observation'))[:600]}\n"
                
        if observation:
            content += f"\n[LATEST OBSERVATION]\nResult: {str(observation)[:2000]}\n"
            
        content += "\nPlan your next research action (e.g. search.web, browser.navigate, browser.extract_text, memory.semantic_ingest, file.write) or emit tool_name: 'FINISH' if research is complete."
        human_msg = HumanMessage(content=content)
        
        try:
            decision = structured_llm.invoke([sys_msg, human_msg])
            print(f"\n[ResearchAgent Thinking]:\n{decision.thoughts}\n")
            print(f"[ResearchAgent Action]:\n  → {decision.tool_name}({decision.arguments})\n")
            state["plan"] = decision.tool_name
            state["arguments"] = decision.arguments
            state["thoughts"] = decision.thoughts
        except Exception as e:
            print(f"[ResearchAgent Error]: LLM generation failed: {e}")
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

        # Resolve correct scope for this tool
        resolved_scope = agent_state.permission_scope[0] if agent_state.permission_scope else ""
        if registry:
            t_def = registry.get_tool(tool_name)
            if t_def and t_def.permissions_required:
                resolved_scope = t_def.permissions_required[0]

        req = ToolRequest(
            request_id=f"req-{uuid.uuid4().hex[:8]}",
            agent_id=agent_state.agent_id,
            tool_name=tool_name,
            arguments=arguments,
            requested_scope=resolved_scope
        )
        
        try:
            print(f"Agent {agent_state.agent_id} requested tool: {tool_name}")
            receipt = gateway.process_request(req, agent_state)
            state["receipt"] = receipt
            obs = receipt.data if receipt else {"status": "executed"}
            state["observation"] = obs
            
            # If scratch extraction or file was created, save path in payload for downstream agents
            if isinstance(obs, dict) and "saved_to" in obs:
                state.setdefault("payload", {})["research_extraction_file"] = obs["saved_to"]
            elif isinstance(obs, dict) and "results" in obs:
                state.setdefault("payload", {})["search_results"] = obs["results"]
                
        except Exception as e:
            state["error"] = str(e)
            state["observation"] = f"Execution failed: {e}"
            
        history = state.get("history", [])
        history.append({
            "action": f"{tool_name}({arguments})",
            "observation": str(state.get("observation", ""))[:400]
        })
        state["history"] = history
        return state

    def should_continue(state: dict):
        if state.get("is_success") or state.get("plan") == "FINISH":
            return END
        if state.get("error") and "LOOP_BUDGET_EXHAUSTED" in str(state.get("error", "")):
            return END
        return "plan"

    workflow.add_node("plan", plan_node)
    workflow.add_node("act", act_node)
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "act")
    workflow.add_conditional_edges("act", should_continue, {"plan": "plan", END: END})

    return workflow.compile()
