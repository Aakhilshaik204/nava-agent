import os
import json
import uuid
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field, model_validator
from nava.core.schemas import AgentState, AgentStatus, ToolRequest
from nava.core.llm import get_llm, safe_structured_invoke

class DocumentPlan(BaseModel):
    thoughts: str = Field(default="Executing document synthesis...")
    tool_name: str = Field(default="FINISH")
    arguments: dict = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_action(cls, data: dict) -> dict:
        if not isinstance(data, dict):
            return data
        if "thoughts" not in data:
            data["thoughts"] = data.get("reasoning") or data.get("thought") or data.get("rationale") or "Executing document synthesis..."
        if "tool_name" not in data:
            data["tool_name"] = data.get("tool") or data.get("action") or data.get("function") or "FINISH"
        if "arguments" not in data:
            extracted_args = data.get("args") or data.get("params") or data.get("parameters") or data.get("input") or data.get("data")
            if isinstance(extracted_args, dict):
                data["arguments"] = extracted_args
            else:
                reserved = {"thoughts", "reasoning", "thought", "rationale", "tool_name", "tool", "action", "function"}
                extra_args = {k: v for k, v in data.items() if k not in reserved}
                data["arguments"] = extra_args if extra_args else {}
        return data

def build_document_agent(registry=None) -> StateGraph:
    """Builds the cyclic DocumentAgent execution graph for publication-grade Typst compilation and document generation."""
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
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "document_agent_prompt.txt")
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
            system_prompt = f"You are DocumentAgent. Goal: {agent_state.goal}\nDate: {current_date_str}\nTools:\n{tool_schemas_str}"
                        
        sys_msg = SystemMessage(content=system_prompt)
        
        content = f"Task Context / Document Brief: {json.dumps(payload)}\n"
        if history:
            content += "\n[YOUR PREVIOUS ACTIONS & OBSERVATIONS]\n" + "\n".join(history) + "\n"
                
        if observation:
            content += f"\n[LATEST OBSERVATION]\nResult: {json.dumps(observation)}\n"
            
        human_msg = HumanMessage(content=content)
        
        try:
            decision = safe_structured_invoke(llm, DocumentPlan, [sys_msg, human_msg])
            print(f"\n[DocumentAgent Thinking]:\n{decision.thoughts}\n")
            print(f"[DocumentAgent Action]:\n  → {decision.tool_name}({decision.arguments})\n")
        except Exception as e:
            print(f"\n[DocumentAgent Error]: LLM generation failed: {e}")
            decision = DocumentPlan(thoughts=f"Fatal error: {e}", tool_name="FINISH", arguments={})

        new_history = history.copy()
        if observation:
            obs_str = json.dumps(observation)
            if len(obs_str) > 1500:
                obs_str = obs_str[:1500] + "... [TRUNCATED]"
            new_history.append(f"Observation: {obs_str}")

        new_history.append(f"Action taken: {decision.tool_name}, args: {json.dumps(decision.arguments)}")
        state["history"] = new_history

        # Check if observation shows successful PDF compilation
        pdf_just_compiled = (
            isinstance(observation, dict) and observation.get("success") is True and ("saved_to" in observation or "compiler" in observation)
        )
        already_compiled = (
            pdf_just_compiled
            or any("saved_to" in h or "typst.compile_pdf" in h or "file.create_pdf" in h for h in history)
            or state.get("is_compiled") is True
        )

        if decision.tool_name == "FINISH" or already_compiled:
            if already_compiled:
                state["tool_request"] = None
                state["plan"] = "FINISH"
                return state

            # If the goal is purely an analysis/reading step without requesting a document/PDF, do not compile
            goal_lower = agent_state.goal.lower()
            is_doc_goal = any(kw in goal_lower for kw in ["pdf", "typst", "report", "document", "compile", "generate", "create", "publish", "author"])
            if not is_doc_goal:
                state["tool_request"] = None
                state["plan"] = "FINISH"
                return state

            # Dynamically extract target output pdf from goal or source topic
            import re
            m_pdf = re.search(r"['`](tasks/[^'`]+\.pdf|[a-zA-Z0-9_\-\.\/]+\.pdf)['`]", agent_state.goal) or re.search(r"to\s+['`]?([a-zA-Z0-9_\-\.\/]+\.pdf)['`]?", agent_state.goal, re.IGNORECASE)
            
            # Check for source research markdown mentioned in goal
            m_src = re.search(r"['`](tasks/[^'`]+\.md|[a-zA-Z0-9_\-\.\/]+\.md)['`]", agent_state.goal) or re.search(r"from\s+['`]?([a-zA-Z0-9_\-\.\/]+\.md)['`]?", agent_state.goal, re.IGNORECASE)
            res_md_path = m_src.group(1) if m_src else None

            if m_pdf:
                target_pdf = m_pdf.group(1)
            elif res_md_path:
                src_slug = os.path.splitext(os.path.basename(res_md_path))[0].replace("_research", "").replace("_brief", "").replace("_notes", "")
                target_pdf = f"tasks/{src_slug}_report.pdf"
            else:
                goal_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', agent_state.goal.strip()[:35]).strip('_').lower()
                target_pdf = f"tasks/{goal_slug}_report.pdf"

            print(f"[DocumentAgent]: Compiling publication-grade PDF deliverable '{target_pdf}'...")
            
            import glob
            if res_md_path and not os.path.exists(res_md_path):
                base_name = os.path.basename(res_md_path)
                matching = sorted(glob.glob(f"tasks/**/artifacts/{base_name}", recursive=True) + glob.glob(f"tasks/**/{base_name}", recursive=True), key=os.path.getmtime, reverse=True)
                if matching:
                    res_md_path = matching[0]

            # Fallback: Find newest valid research markdown file (exclude task_memory and project_memory)
            if not res_md_path or not os.path.exists(res_md_path):
                all_mds = sorted(glob.glob("tasks/**/*.md", recursive=True) + glob.glob("tasks/*.md"), key=os.path.getmtime, reverse=True)
                valid_mds = [
                    p for p in all_mds 
                    if not os.path.basename(p).startswith("task_memory") 
                    and not os.path.basename(p).startswith("project_memory")
                ]
                if valid_mds:
                    res_md_path = valid_mds[0]
            
            src_content = f"= {agent_state.goal.title()}\n\n== Executive Overview\nComprehensive intelligence and deliverable synthesis.\n"
            if res_md_path and os.path.exists(res_md_path):
                try:
                    with open(res_md_path, "r", encoding="utf-8") as f:
                        raw_md = f.read()
                        src_content = raw_md.replace("# ", "= ").replace("## ", "== ").replace("### ", "=== ")
                except Exception:
                    pass
            
            req = ToolRequest(
                request_id=f"req-{uuid.uuid4().hex[:8]}",
                agent_id=agent_state.agent_id,
                tool_name="typst.compile_pdf",
                arguments={"source": src_content, "output_pdf": target_pdf},
                requested_scope="document.compile"
            )
            state["tool_request"] = req
            state["plan"] = "typst.compile_pdf"
            state["is_compiled"] = True
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
