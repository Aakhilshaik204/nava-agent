import os
import uuid
import hashlib
import datetime
from typing import List, Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field, model_validator
from nava.core.schemas import AgentSpec, Priority
from nava.core.llm import get_llm, safe_structured_invoke

class SubGoal(BaseModel):
    role: str = Field(default="DynamicAgent", description="The formal role of the agent (must be a known template, or 'DynamicAgent' if none fit).")
    display_label: Optional[str] = Field(None, description="A human-readable descriptive name used for audit logs.")
    goal: str = Field(default="Execute sub-task", description="The specific goal for this sub-agent.")
    required_tools: List[str] = Field(default_factory=list, description="The tools this agent will need.")
    required_permissions: List[str] = Field(default_factory=list, description="The permissions this agent will need.")
    stage: int = Field(default=1, description="The execution stage number.")
    is_parallel: bool = Field(default=True, description="Whether this sub-goal can run concurrently.")

    @model_validator(mode="before")
    @classmethod
    def normalize_subgoal(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "role" not in data and "agent" in data:
                data["role"] = data["agent"]
            if "required_tools" not in data:
                data["required_tools"] = data.get("tools", [])
            if "required_permissions" not in data:
                data["required_permissions"] = data.get("permissions", [])
            if "goal" not in data and "description" in data:
                data["goal"] = data["description"]
            elif "goal" not in data and "task" in data:
                data["goal"] = data["task"]
        return data

class GoalPlan(BaseModel):
    thoughts: str = Field(default="Executing planned execution stages...", description="Your step-by-step reasoning.")
    sub_goals: List[SubGoal] = Field(default_factory=list, description="List of sub-goals organized by execution stages.")

    @model_validator(mode="before")
    @classmethod
    def normalize_plan(cls, data: Any) -> Any:
        if isinstance(data, list):
            return {"thoughts": "Executing planned execution stages...", "sub_goals": data}
        if isinstance(data, dict):
            if "thoughts" not in data:
                data["thoughts"] = data.get("reasoning") or data.get("plan_summary") or "Executing planned execution stages..."
            if "sub_goals" not in data:
                for alt_key in ["goal_plan", "subgoals", "steps", "tasks", "plan", "stages", "actions"]:
                    if alt_key in data and isinstance(data[alt_key], list):
                        data["sub_goals"] = data[alt_key]
                        break
        return data

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

        current_date_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
        system_prompt = (
            prompt_template
            .replace("{templates}", str(self.available_templates))
            .replace("{tools}", str(self.ceiling_tools))
            .replace("{permissions}", str(self.ceiling_permissions))
            .replace("{current_date}", current_date_str)
        )
        
        sys_msg = SystemMessage(content=system_prompt)
        human_msg = HumanMessage(content=f"Current Date: {current_date_str}\nObjective: {objective}")

        try:
            if self.budget_engine and budget_ref:
                self.budget_engine.consume_internal_llm_call(budget_ref, tokens=500)
            plan: GoalPlan = safe_structured_invoke(self.llm, GoalPlan, [sys_msg, human_msg])
        except Exception as e:
            print(f"Planner failed: {e}")
            plan = GoalPlan(thoughts="Synthesizing direct execution plan...", sub_goals=[])

        # Auto-heal empty plan if LLM failed to generate or parse sub-goals
        if not plan.sub_goals:
            obj_lower = objective.lower()
            if any(k in obj_lower for k in ["slide", "presentation", "deck", "ppt", "pptx", "pdf", "report", "docx"]):
                plan.thoughts = "Auto-synthesizing presentation generation stages..."
                plan.sub_goals = [
                    SubGoal(
                        role="DocumentAgent",
                        display_label="Generate Gamma-Style Presentation",
                        goal=f"Generate the complete presentation: {objective}. Save the deliverables as .html and companion .pptx in task artifacts with dynamic theme and rich layout variety.",
                        required_tools=["presentation.render_template", "presentation.create_slidev", "file.write", "file.read"],
                        required_permissions=["filesystem.write", "filesystem.read"],
                        stage=1,
                        is_parallel=True
                    ),
                    SubGoal(
                        role="VerifierAgent",
                        display_label="Verify Presentation Deliverables",
                        goal=f"Verify that all presentation artifacts and slides for '{objective}' exist and contain complete, high-quality content.",
                        required_tools=["file.read", "audit.verify_grounding"],
                        required_permissions=["filesystem.read"],
                        stage=2,
                        is_parallel=False
                    )
                ]
            elif any(k in obj_lower for k in ["code", "build", "app", "implement", "refactor", "fix", "script"]):
                plan.thoughts = "Auto-synthesizing coding implementation stages..."
                plan.sub_goals = [
                    SubGoal(
                        role="CodingAgent",
                        display_label="Implement Code Solution",
                        goal=objective,
                        required_tools=["file.write", "file.read", "code.replace_content", "test.run"],
                        required_permissions=["filesystem.write", "filesystem.read"],
                        stage=1,
                        is_parallel=True
                    )
                ]
            elif any(k in obj_lower for k in ["search", "research", "find", "arxiv", "scrape"]):
                plan.thoughts = "Auto-synthesizing research retrieval stages..."
                plan.sub_goals = [
                    SubGoal(
                        role="ResearchAgent",
                        display_label="Execute Research Query",
                        goal=objective,
                        required_tools=["search.web", "brave.search_web", "fetch.get_markdown", "file.write"],
                        required_permissions=["filesystem.write", "network.http"],
                        stage=1,
                        is_parallel=True
                    )
                ]
            else:
                plan.thoughts = "Auto-synthesizing universal execution stage..."
                plan.sub_goals = [
                    SubGoal(
                        role="DynamicAgent",
                        display_label="Execute Objective",
                        goal=objective,
                        required_tools=["file.write", "file.read"],
                        required_permissions=["filesystem.write", "filesystem.read"],
                        stage=1,
                        is_parallel=True
                    )
                ]

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
                    "file.write", "file.read", "file.create_pdf", "file.create_docx", "file.create_pptx",
                    "presentation.create_slidev", "presentation.render_template"
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

