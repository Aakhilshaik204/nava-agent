import os
import json
import uuid
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field, model_validator
from nava.core.schemas import AgentState, AgentStatus, ToolRequest
from nava.core.llm import get_llm, safe_structured_invoke

class ResearchPlan(BaseModel):
    thoughts: str = Field(default="Initiating multi-source web search...")
    tool_name: str = Field(default="search.web")
    arguments: dict = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_action(cls, data: dict) -> dict:
        if not isinstance(data, dict):
            return data
        if "thoughts" not in data:
            data["thoughts"] = data.get("reasoning") or data.get("thought") or data.get("rationale") or "Executing research step..."
        if "tool_name" not in data:
            data["tool_name"] = data.get("tool") or data.get("action") or data.get("function") or "search.web"
        if "arguments" not in data:
            extracted_args = data.get("args") or data.get("params") or data.get("parameters") or data.get("input") or data.get("data")
            if isinstance(extracted_args, dict):
                data["arguments"] = extracted_args
            else:
                reserved = {"thoughts", "reasoning", "thought", "rationale", "tool_name", "tool", "action", "function"}
                extra_args = {k: v for k, v in data.items() if k not in reserved}
                data["arguments"] = extra_args if extra_args else {}
        return data

def build_research_agent(registry=None) -> StateGraph:
    """Builds the Tier 2 cyclic ResearchAgent execution graph for deep research and synthesis."""
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
                try:
                    t_def = registry.get_tool(t_name)
                    if t_def:
                        tool_schemas.append(f"- {t_name}: {t_def.description}\n  Schema: {json.dumps(t_def.input_schema)}")
                except KeyError:
                    pass
        tool_schemas_str = "\n".join(tool_schemas) if tool_schemas else "No tools available."

        llm = get_llm()
        
        import datetime
        current_date_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "research_agent_prompt.txt")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()
            system_prompt = (
                prompt_template
                .replace("{goal}", str(agent_state.goal))
                .replace("{tool_schemas_str}", str(tool_schemas_str))
                .replace("{current_date}", current_date_str)
            )
        except Exception:
            system_prompt = f"You are ResearchAgent. Goal: {agent_state.goal}\nDate: {current_date_str}\nTools:\n{tool_schemas_str}"
                        
        sys_msg = SystemMessage(content=system_prompt)
        
        content = f"Research Payload / Context: {json.dumps(payload)}\n"
        if history:
            content += "\n[YOUR PREVIOUS ACTIONS & OBSERVATIONS]\n" + "\n".join(history) + "\n"
                
        if observation:
            content += f"\n[LATEST OBSERVATION]\nResult: {json.dumps(observation)}\n"
            
        human_msg = HumanMessage(content=content)
        
        try:
            decision = safe_structured_invoke(llm, ResearchPlan, [sys_msg, human_msg])
            print(f"\n[ResearchAgent Thinking]:\n{decision.thoughts}\n")
            print(f"[ResearchAgent Action]:\n  → {decision.tool_name}({decision.arguments})\n")
        except Exception as e:
            print(f"\n[ResearchAgent Error]: LLM generation failed: {e}")
            decision = ResearchPlan(thoughts=f"Fatal error: {e}", tool_name="FINISH", arguments={})

        new_history = history.copy()
        if observation:
            obs_str = json.dumps(observation)
            if len(obs_str) > 1500:
                obs_str = obs_str[:1500] + "... [TRUNCATED]"
            new_history.append(f"Observation: {obs_str}")

        new_history.append(f"Action taken: {decision.tool_name}, args: {json.dumps(decision.arguments)}")
        state["history"] = new_history

        # Guard: ResearchAgent must NEVER finish on step 1 without performing at least one search
        if decision.tool_name == "FINISH" and len(history) == 0 and observation is None:
            decision.tool_name = "search.web"
            decision.arguments = {"query": agent_state.goal}

        if decision.tool_name == "FINISH":
            # Dynamically extract target markdown filename from goal
            import re
            m = re.search(r"['`](tasks/[^'`]+\.md|[a-zA-Z0-9_\-\.\/]+\.md)['`]", agent_state.goal) or re.search(r"to\s+['`]?([a-zA-Z0-9_\-\.\/]+\.md)['`]?", agent_state.goal, re.IGNORECASE)
            if m:
                target_filename = m.group(1)
            else:
                goal_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', agent_state.goal.strip()[:35]).strip('_').lower()
                target_filename = f"tasks/{goal_slug}_research.md"

            already_written = any("Action taken: file.write" in h for h in history)
            if not already_written and (observation or len(history) > 1):
                # Synthesize gathered notes into structured markdown
                synth_lines = [
                    f"# Intelligence Summary: {agent_state.goal}\n",
                    "## Executive Overview",
                    "Synthesized news intelligence gathered from real-time web searches and news sources.\n",
                    "## Key Developments & Highlights\n"
                ]
                for h in history:
                    if "Observation:" in h:
                        obs_clean = h.replace("Observation:", "").strip()
                        try:
                            obs_obj = json.loads(obs_clean)
                            if isinstance(obs_obj, dict) and "results" in obs_obj:
                                for r in obs_obj["results"]:
                                    t = r.get("title", "Update")
                                    s = r.get("snippet", "")
                                    u = r.get("url", "")
                                    synth_lines.append(f"### {t}\n- **Summary**: {s}\n- **Source**: {u}\n")
                            elif isinstance(obs_obj, dict) and "title" in obs_obj:
                                synth_lines.append(f"### {obs_obj.get('title')}\n- **URL**: {obs_obj.get('url')}\n")
                        except Exception:
                            if len(obs_clean) > 20:
                                synth_lines.append(f"- {obs_clean[:400]}\n")

                synth_content = "\n".join(synth_lines)
                req = ToolRequest(
                    request_id=f"req-{uuid.uuid4().hex[:8]}",
                    agent_id=agent_state.agent_id,
                    tool_name="file.write",
                    arguments={"filename": target_filename, "content": synth_content},
                    requested_scope="filesystem.write"
                )
                state["tool_request"] = req
                state["plan"] = "file.write"
                return state

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

        # Failsafe: Ensure arguments dict has required keys
        final_args = dict(decision.arguments)
        if decision.tool_name == "search.web" and not final_args.get("query"):
            final_args["query"] = agent_state.goal

        req = ToolRequest(
            request_id=f"req-{uuid.uuid4().hex[:8]}",
            agent_id=agent_state.agent_id,
            tool_name=decision.tool_name,
            arguments=final_args,
            requested_scope=resolved_scope
        )
        state["tool_request"] = req
        state["plan"] = decision.tool_name
        return state

    workflow.add_node("plan", plan_node)
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", END)

    return workflow.compile()
