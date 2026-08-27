import os
import uuid
import hashlib
import datetime
from typing import List, Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from nava.core.schemas import AgentSpec, Priority
from nava.core.llm import get_llm

class SubGoal(BaseModel):
    role: str = Field(description="The formal role of the agent (must be a known template, or 'DynamicAgent' if none fit).")
    display_label: Optional[str] = Field(None, description="A human-readable descriptive name (e.g. 'WebResearchAgent', 'DataAnalysisAgent', 'PDFAnalyzer') used only for audit logs.")
    goal: str = Field(description="The specific goal for this sub-agent.")
    required_tools: List[str] = Field(description="The tools this agent will need.")
    required_permissions: List[str] = Field(description="The permissions this agent will need.")
    stage: int = Field(default=1, description="The execution stage number (1, 2, 3...). Sub-goals with the same stage number execute concurrently in parallel.")
    is_parallel: bool = Field(default=True, description="Whether this sub-goal can run concurrently with others in the same stage.")

class GoalPlan(BaseModel):
    thoughts: str = Field(description="Your step-by-step reasoning for breaking down the objective into parallel and sequential execution stages.")
    sub_goals: List[SubGoal] = Field(description="List of sub-goals organized by execution stages.")

def compute_dedup_hash(role: str, goal: str, tools: List[str]) -> str:
    clean_goal = goal.strip().lower()
    tools_str = ",".join(sorted(tools))
    raw = f"{role}:{clean_goal}:{tools_str}".encode('utf-8')
    return hashlib.sha256(raw).hexdigest()[:16]

class GoalPlanner:
    def __init__(self, available_templates: List[str], ceiling_tools: List[str], ceiling_permissions: List[str], budget_engine=None, registry=None):
        self.available_templates = available_templates
        self.ceiling_tools = ceiling_tools
        self.ceiling_permissions = ceiling_permissions
        self.budget_engine = budget_engine
        self.registry = registry
        if os.environ.get("NAVA_TEST_MODE") == "1":
            self.llm = None
        else:
            self.llm = get_llm()


    def plan(self, objective: str, parent_id: str, budget_ref: str = None) -> List[AgentSpec]:
        if os.environ.get("NAVA_TEST_MODE") == "1":
            # Mock plan for testing
            return [
                AgentSpec(
                    request_id=f"req-{uuid.uuid4().hex[:8]}",
                    requested_role="DocumentAgent",
                    goal=objective,
                    parent_agent_id=parent_id,
                    requested_tools=["file.write"],
                    requested_permission_scope=["filesystem.write"],
                    ttl=datetime.timedelta(minutes=15),
                    max_steps=10,
                    max_tokens=5000,
                    max_children=2,
                    dedup_hash=compute_dedup_hash("DocumentAgent", objective, ["file.write"]),
                    stage=1,
                    is_parallel=True
                )
            ]

        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "planner_prompt.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
            
        system_prompt = prompt_template.format(
            templates=self.available_templates,
            tools=self.ceiling_tools,
            permissions=self.ceiling_permissions
        )
        
        sys_msg = SystemMessage(content=system_prompt)
        human_msg = HumanMessage(content=f"Objective: {objective}")

        structured_llm = self.llm.with_structured_output(GoalPlan)
        try:
            if self.budget_engine and budget_ref:
                self.budget_engine.consume_internal_llm_call(budget_ref, tokens=500)
            plan: GoalPlan = structured_llm.invoke([sys_msg, human_msg])
        except Exception as e:
            print(f"Planner failed: {e}")
            raise e

        print(f"\n[Orchestrator Planner Thinking]:\n{plan.thoughts}\n")
        print("[Orchestrator Plan]:")
        for i, sg in enumerate(plan.sub_goals):
            print(f"  [Stage {sg.stage}] {sg.role} ({sg.display_label or sg.role}) → {sg.goal}")
            print(f"     Tools: {sg.required_tools}")

        specs = []
        for sg in plan.sub_goals:
            req_tools = list(sg.required_tools or [])
            def _is_tool_active(tool_name: str) -> bool:
                if self.registry and not self.registry.has_tool(tool_name):
                    return False
                if self.ceiling_tools and tool_name not in self.ceiling_tools and "*" not in self.ceiling_tools:
                    return False
                return True

            # Ensure baseline tools for specialized roles (guards against small LLM tool omissions)
            if sg.role == "CodingAgent":
                for bt in [
                    "file.write", "file.read", "code.replace_content", "code.search", "test.run",
                    "context7.get_symbol_graph", "context7.slice_context",
                    "superpowers.ast_search", "superpowers.ast_replace", "superpowers.compiler_autofix",
                    "git.status", "git.diff"
                ]:
                    if bt not in req_tools and _is_tool_active(bt):
                        req_tools.append(bt)
            elif sg.role == "ResearchAgent":
                for bt in [
                    "search.web", "brave.search_web", "brave.search_news",
                    "fetch.get_markdown", "fetch.get_raw_html", "fetch.get_headers",
                    "arxiv.search_papers", "arxiv.get_paper_summary",
                    "browser.navigate", "browser.extract_text", "file.write", "file.read"
                ]:
                    if bt not in req_tools and _is_tool_active(bt):
                        req_tools.append(bt)
            elif sg.role == "BrowserAgent":
                for bt in [
                    "browser.navigate", "browser.extract_interactive_tree", "browser.screenshot",
                    "browser.click", "browser.type", "browser.scroll", "browser.select_option",
                    "browser.extract_text", "browser.extract_dom", "browser.go_back",
                    "file.read", "file.write"
                ]:
                    if bt not in req_tools and _is_tool_active(bt):
                        req_tools.append(bt)
            elif sg.role == "ComputerAgent":
                for bt in [
                    "desktop.screenshot", "desktop.click", "desktop.type",
                    "desktop.hotkey", "desktop.get_screen_size", "file.read", "file.write"
                ]:
                    if bt not in req_tools and _is_tool_active(bt):
                        req_tools.append(bt)
            elif sg.role == "DataAgent":
                for bt in [
                    "sqlite.read_query", "sqlite.write_query", "sqlite.list_tables", "sqlite.describe_tables",
                    "data.sql_query_csv", "data.profile_dataset", "data.aggregate",
                    "data.correlation_matrix", "data.detect_anomalies", "data.pivot_table",
                    "file.read", "file.write"
                ]:
                    if bt not in req_tools and _is_tool_active(bt):
                        req_tools.append(bt)
            elif sg.role in ["DocumentAgent", "UniversalFileAgent"]:
                for bt in [
                    "typst.compile_pdf", "typst.render_template", "doc.read_document",
                    "file.write", "file.read", "file.create_pdf", "file.create_docx", "file.create_pptx"
                ]:
                    if bt not in req_tools and _is_tool_active(bt):
                        req_tools.append(bt)
            elif sg.role == "ReviewerAgent":
                for bt in ["file.read", "sequential_thinking.step", "audit.security_scan", "code.search", "git.diff"]:
                    if bt not in req_tools and _is_tool_active(bt):
                        req_tools.append(bt)
            elif sg.role == "VerifierAgent":
                for bt in ["file.read", "audit.verify_invariants", "audit.verify_grounding", "sequential_thinking.step", "doc.read_document"]:
                    if bt not in req_tools and _is_tool_active(bt):
                        req_tools.append(bt)
            elif sg.role == "TerminalAgent":
                for bt in [
                    "terminal.execute", "terminal.exec_command", "terminal.run_tests",
                    "terminal.inspect_environment", "docker.create_sandbox", "docker.exec_in_sandbox",
                    "docker.destroy_sandbox", "git.status", "git.diff", "file.read", "file.write"
                ]:
                    if bt not in req_tools and _is_tool_active(bt):
                        req_tools.append(bt)

            sg.required_tools = [t for t in req_tools if _is_tool_active(t)]
            dedup = compute_dedup_hash(sg.role, sg.goal, req_tools)
            
            # Auto-synthesize requested_permission_scope from required_tools if registry is available
            derived_perms = list(sg.required_permissions or [])
            if self.registry:
                for t_name in req_tools:
                    try:
                        t_def = self.registry.get_tool(t_name)
                        if t_def:
                            for p in t_def.permissions_required:
                                if p not in derived_perms:
                                    derived_perms.append(p)
                    except Exception:
                        pass

            specs.append(AgentSpec(
                request_id=f"req-{uuid.uuid4().hex[:8]}",
                requested_role=sg.role,
                display_label=sg.display_label or sg.role,
                goal=sg.goal,
                parent_agent_id=parent_id,
                requested_tools=req_tools,
                requested_permission_scope=derived_perms,
                ttl=datetime.timedelta(minutes=30),
                max_steps=20,
                max_tokens=10000,
                max_children=2,
                dedup_hash=dedup,
                stage=sg.stage,
                is_parallel=sg.is_parallel
            ))
            
        return specs

