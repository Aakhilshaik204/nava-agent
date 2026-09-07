import os
import sys
from typing import Any, Optional, Dict, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from nava.core.boot import NavaBootstrapper
from nava.agents.planner import GoalPlanner
from nava.agents.factory import AgentFactory
from nava.tools.registry import ToolRegistry, ToolDefinition
from nava.governance.policy_engine import DefaultPolicyEngine
from nava.governance.budget_engine import DefaultBudgetEngine
from nava.governance.risk_engine import DefaultRiskEngine
from nava.governance.hitl_manager import SingleApprovalManager
from nava.core.ledger import JsonlAuditLedger
from nava.core.schemas import PolicyRule, Outcome, RiskTier, AgentStatus
from nava.tools.executor import LocalToolExecutor
from nava.gateway.pipeline import build_default_gateway, build_test_gateway
from nava.agents.runtime.file_agent_variants import build_document_agent, build_data_agent, build_verifier_agent
from nava.agents.runtime.nava_agent import build_nava_agent
from nava.agents.runtime.file_agent import build_file_agent

from nava.skills.manager import SkillManager

class Orchestrator:
    def __init__(self, config_path: str = "nava.yaml"):
        bootstrapper = NavaBootstrapper(config_path)
        self.root_agent, self.budget = bootstrapper.bootstrap()
        
        import threading
        self._emergency_stop_event = threading.Event()
        self.skill_manager = SkillManager()
        from nava.skills.promotion import SkillPromoter
        self.skill_promoter = SkillPromoter(self.skill_manager)
        self.ledger = JsonlAuditLedger("nava_audit.jsonl")
        self.registry = ToolRegistry()
        
        # Load security feature switches and mcp_servers from nava.yaml if present
        sec_switches = None
        self.mcp_configs = {}
        try:
            import yaml
            if os.path.exists("nava.yaml"):
                with open("nava.yaml", "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    if isinstance(cfg, dict):
                        sec_switches = cfg.get("security_switches", {})
                        self.mcp_configs = cfg.get("mcp_servers", {})
        except Exception:
            pass
            
        self.policy = DefaultPolicyEngine(security_switches=sec_switches)
        
        # Load default policy rules matching all permissions in root agent ceiling
        default_rules = [
            PolicyRule(rule_id=f"rule-{i+1}", scope=perm, condition="", outcome=Outcome.ALLOW, priority=1)
            for i, perm in enumerate(self.root_agent.permission_scope)
        ]
        for scope in [
            "research.read", "fetch.*", "brave.*", "arxiv.*",
            "database.read", "database.write", "data.analyze", "sqlite.*", "data.*",
            "ast.read", "ast.write", "context7.*", "superpowers.*",
            "git.read", "git.write", "filesystem.read", "filesystem.write",
            "test.run", "terminal.execute", "browser.*", "desktop.*", "search.web", "gmail.read",
            "subagent.spawn", "subagent.*"
        ]:
            if not any(r.scope == scope for r in default_rules):
                default_rules.append(PolicyRule(rule_id=f"rule-{len(default_rules)+1}", scope=scope, condition="", outcome=Outcome.ALLOW, priority=1))
        self.policy.load_rules(default_rules)
        
        self.budget_engine = DefaultBudgetEngine()
        self.budget_engine.register_budget(self.budget)
        
        from nava.memory.store import ProfileMemoryStore, SemanticMemoryStore, EpisodicMemoryStore
        from nava.memory.ai_twin import AITwinManager
        self.profile_store = ProfileMemoryStore("memory/profile.json")
        self.semantic_store = SemanticMemoryStore("memory/semantic.json")
        self.episodic_store = EpisodicMemoryStore("memory/episodic.json")
        self.ai_twin = AITwinManager(self.profile_store)
        self.risk = DefaultRiskEngine(self.profile_store)
        
        self.hitl = SingleApprovalManager()
        self.register_tools()
        self.factory = AgentFactory(self.registry, self.policy, self.budget_engine)
        
        from nava.credentials.vault import CredentialVault
        from nava.credentials.broker import CredentialBroker
        from nava.workspace.project_manager import ProjectWorkspace, TaskManager
        from nava.core.message_bus import AgentMessageBus
        self.vault = CredentialVault()
        self.credential_broker = CredentialBroker(self.vault)
        self.workspace = ProjectWorkspace(root_dir=os.getcwd())
        self.task_manager = TaskManager(root_dir=os.getcwd())
        self.workspace.initialize_project_memory()
        self.message_bus = AgentMessageBus()
        
        from nava.tools.mcp_client import MCPClientManager
        from nava.tools.tool_manifest import get_default_tools, register_default_mcp_servers
        self.mcp_manager = MCPClientManager(self.registry, credential_broker=self.credential_broker)
        
        # Check if gmail server is enabled
        gmail_cfg = self.mcp_configs.get("gmail", {})
        gmail_enabled = gmail_cfg.get("enabled", True) if isinstance(gmail_cfg, dict) else True
        if sec_switches and not sec_switches.get("enable_external_integrations", True):
            gmail_enabled = False

        if gmail_enabled:
            self.mcp_manager.register_server(
                name="gmail",
                command=sys.executable,
                args=["src/nava/tools/mcp_gmail_server.py"],
                required_service="gmail",
                enabled=True
            )
        register_default_mcp_servers(self.mcp_manager, mcp_configs=self.mcp_configs)
        
        from nava.governance.state_observer import DefaultStateObserver
        self.state_observer = DefaultStateObserver()
        
        self.planner = GoalPlanner(
            available_templates=["DocumentAgent", "DataAgent", "VerifierAgent", "CodingAgent", "ReviewerAgent", "UniversalFileAgent", "BrowserAgent", "ResearchAgent", "TerminalAgent", "ComputerAgent"],
            ceiling_tools=self.root_agent.tool_scope,
            ceiling_permissions=self.root_agent.permission_scope,
            budget_engine=self.budget_engine,
            registry=self.registry
        )
        
    def register_tools(self):
        from nava.tools.tool_manifest import get_default_tools
        
        # Determine disabled prefixes from mcp_configs
        disabled_prefixes = set()
        for srv_name, srv_cfg in getattr(self, "mcp_configs", {}).items():
            if isinstance(srv_cfg, dict) and not srv_cfg.get("enabled", True):
                if srv_name == "sqlite":
                    disabled_prefixes.add("sqlite.")
                elif srv_name == "arxiv":
                    disabled_prefixes.add("arxiv.")
                elif srv_name == "brave-search":
                    disabled_prefixes.add("brave.")
                elif srv_name == "fetch":
                    disabled_prefixes.add("fetch.")
                elif srv_name == "typst":
                    disabled_prefixes.add("typst.")
                elif srv_name == "docker-sandbox":
                    disabled_prefixes.add("docker.")
                elif srv_name == "desktop-automation":
                    disabled_prefixes.add("desktop.")
                elif srv_name == "github":
                    disabled_prefixes.add("github.")
                elif srv_name == "gmail":
                    disabled_prefixes.add("gmail.")
                elif srv_name == "context7":
                    disabled_prefixes.add("context7.")
                elif srv_name == "superpowers":
                    disabled_prefixes.add("superpowers.")
                elif srv_name == "sequential-thinking":
                    disabled_prefixes.add("sequential_thinking.")
                elif srv_name == "audit-scanner":
                    disabled_prefixes.add("audit.")

        for tool in get_default_tools():
            if any(tool.name.startswith(dp) for dp in disabled_prefixes):
                continue
            self.registry.register_tool(tool)
            
    def execute(self, goal: str):
        print(f"--- Nava Orchestrator ---")
        print(f"Objective: {goal}")
               # 1. Check for explicit slash commands
        explicit_skill_context = ""
        if goal.startswith("/"):
            parts = goal.split(" ", 2)
            cmd = parts[0][1:] # remove '/'
            
            if cmd == "mcp" and len(parts) >= 3 and parts[1] == "approve":
                target_args = parts[2].split(" ")
                if len(target_args) < 2:
                    print("Usage: /mcp approve <server_name> <tool_name>")
                    return
                server_name, tool_name = target_args[0], target_args[1]
                
                try:
                    pending_tools = self.mcp_manager.pending_tools.get(server_name, {})
                    if tool_name not in pending_tools:
                        print(f"No pending tool '{tool_name}' found for server '{server_name}'.")
                        return
                        
                    tool_dict = pending_tools[tool_name]
                    trust_state = tool_dict.get("trust_state")
                    
                    if trust_state == "TRUSTED":
                        print(f"Tool '{tool_name}' is already TRUSTED.")
                        return
                        
                    import json
                    canonical_dict = {
                        "name": tool_dict.get("name", ""),
                        "description": tool_dict.get("description", ""),
                        "input_schema": tool_dict.get("input_schema", {}),
                        "permissions_required": tool_dict.get("permissions_required", []),
                        "risk_level": tool_dict.get("risk_level", "MEDIUM"),
                        "reversible": tool_dict.get("reversible", True),
                        "required_credentials": tool_dict.get("required_credentials", [])
                    }
                    new_content = json.dumps(canonical_dict, indent=2)
                    
                    if trust_state == "UNTRUSTED_NEW":
                        print(f"\n--- NEW MCP TOOL DETECTED: {server_name}::{tool_name} ---")
                        print(new_content)
                        print("-" * 40)
                        
                        dangerous_keywords = ["shell.execute", "file.delete", "mock.send_wire_transfer", "password", "token", "key", "~/.ssh"]
                        warning_fired = any(k in new_content.lower() for k in dangerous_keywords)
                        if warning_fired:
                            print("\033[91m[WARNING: Dangerous keyword detected in new tool schema!]\033[0m")
                            ans = input("DANGEROUS KEYWORDS DETECTED. Type 'AUTHORIZE' to approve this tool: ")
                            is_approved = (ans == 'AUTHORIZE')
                        else:
                            ans = input("Approve this new MCP tool? [y/N]: ")
                            is_approved = (ans.lower() == 'y')
                            
                        if is_approved:
                            self.mcp_manager.approve_tool(server_name, tool_name, actor="local_user")
                            from nava.core.schemas import Event
                            import uuid
                            evt = Event(event_id=f"evt-{uuid.uuid4().hex[:8]}", event_type="MCP_TOOL_APPROVED", task_id="system", payload={"server": server_name, "tool": tool_name, "state": "NEW", "actor": "local_user"})
                            self.ledger.append_event(evt)
                        return
                        
                    if trust_state == "UNTRUSTED_MODIFIED":
                        old_content = self.mcp_manager.get_ledger_content(server_name, tool_name) or ""
                        
                        import difflib
                        diff = list(difflib.unified_diff(old_content.splitlines(), new_content.splitlines(), lineterm=""))
                        
                        print(f"\n--- MCP TOOL MODIFIED: {server_name}::{tool_name} ---")
                        dangerous_keywords = ["shell.execute", "file.delete", "mock.send_wire_transfer", "password", "token", "key", "~/.ssh"]
                        warning_fired = False
                        for line in diff:
                            if line.startswith("+"):
                                if any(k in line.lower() for k in dangerous_keywords):
                                    print(f"\033[91m[WARNING: Dangerous keyword detected]\033[0m {line}")
                                    warning_fired = True
                                else:
                                    print(f"\033[92m{line}\033[0m")
                            elif line.startswith("-"):
                                print(f"\033[91m{line}\033[0m")
                            else:
                                print(line)
                                
                        print("-" * 40)
                        if warning_fired:
                            ans = input("DANGEROUS KEYWORDS DETECTED. Type 'AUTHORIZE' to approve these changes: ")
                            is_approved = (ans == 'AUTHORIZE')
                        else:
                            ans = input("Approve these schema changes? [y/N]: ")
                            is_approved = (ans.lower() == 'y')
                            
                        if is_approved:
                            self.mcp_manager.approve_tool(server_name, tool_name, actor="local_user")
                            from nava.core.schemas import Event
                            import uuid
                            evt = Event(event_id=f"evt-{uuid.uuid4().hex[:8]}", event_type="MCP_TOOL_APPROVED", task_id="system", payload={"server": server_name, "tool": tool_name, "state": "MODIFIED", "actor": "local_user"})
                            self.ledger.append_event(evt)
                        return
                except Exception as e:
                    print(f"Error approving MCP tool: {e}")
                    return

            if cmd == "plugin" and len(parts) >= 3 and parts[1] == "approve":
                skill_name = parts[2]
                skill = self.skill_manager.get_skill(skill_name)
                if not skill:
                    print(f"Skill '{skill_name}' not found.")
                    return
                
                if skill.trust_state == "TRUSTED":
                    print(f"Skill '{skill_name}' is already TRUSTED.")
                    return
                    
                if skill.trust_state == "UNTRUSTED_NEW":
                    print(f"\n--- NEW PLUGIN DETECTED: {skill_name} ---")
                    print(skill.content)
                    print("-" * 40)
                    ans = input("Approve this new plugin? [y/N]: ")
                    if ans.lower() == 'y':
                        self.skill_manager.approve_skill(skill_name)
                        # Log to Audit Ledger
                        from nava.core.schemas import Event
                        import uuid
                        evt = Event(event_id=f"evt-{uuid.uuid4().hex[:8]}", event_type="PLUGIN_APPROVED", task_id="system", payload={"plugin": skill_name, "state": "NEW", "actor": "local_user"})
                        self.ledger.append_event(evt)
                    return
                    
                if skill.trust_state == "UNTRUSTED_MODIFIED":
                    old_content = self.skill_manager.get_ledger_content(skill_name) or ""
                    new_content = skill.content
                    
                    import difflib
                    diff = list(difflib.unified_diff(old_content.splitlines(), new_content.splitlines(), lineterm=""))
                    
                    print(f"\n--- PLUGIN MODIFIED: {skill_name} ---")
                    dangerous_keywords = ["shell.execute", "file.delete", "mock.send_wire_transfer", "password", "token", "key", "~/.ssh"]
                    warning_fired = False
                    for line in diff:
                        if line.startswith("+"):
                            # Simple scanner for dangerous additions
                            if any(k in line for k in dangerous_keywords):
                                print(f"\033[91m[WARNING: Dangerous keyword detected]\033[0m {line}")
                                warning_fired = True
                            else:
                                print(f"\033[92m{line}\033[0m")
                        elif line.startswith("-"):
                            print(f"\033[91m{line}\033[0m")
                        else:
                            print(line)
                            
                    print("-" * 40)
                    if warning_fired:
                        ans = input("DANGEROUS KEYWORDS DETECTED. Type 'AUTHORIZE' to approve these changes: ")
                        is_approved = (ans == 'AUTHORIZE')
                    else:
                        ans = input("Approve these changes? [y/N]: ")
                        is_approved = (ans.lower() == 'y')
                        
                    if is_approved:
                        self.skill_manager.approve_skill(skill_name)
                        from nava.core.schemas import Event
                        import uuid
                        evt = Event(event_id=f"evt-{uuid.uuid4().hex[:8]}", event_type="PLUGIN_APPROVED", task_id="system", payload={"plugin": skill_name, "state": "MODIFIED", "actor": "local_user"})
                        self.ledger.append_event(evt)
                    return

            # Otherwise, assume it's a skill execution command
            skill_cmd = cmd
            query = " ".join(parts[1:]) if len(parts) > 1 else ""
            
            print(f"[Orchestrator] Detected explicit skill command: /{skill_cmd}")
            skill = self.skill_manager.get_skill(skill_cmd)
            if skill:
                if skill.trust_state != "TRUSTED":
                    print(f"\n[!] SECURITY BLOCK: Skill '{skill_cmd}' is in state {skill.trust_state}.")
                    print(f"Refusing to execute unverified instructional content.")
                    print(f"Run '/plugin approve {skill_cmd}' to review and authorize it.\n")
                    return
                    
                print(f"[Orchestrator] Activating skill: {skill.name}")
                explicit_skill_context = f"\n[EXPLICIT SKILL INSTRUCTIONS: {skill.name}]\n{skill.content}\n"
                goal = query # update goal to just the query
            else:
                print(f"[Orchestrator] Warning: Skill '{skill_cmd}' not found.")
                
        # 2. Check if user explicitly mentioned a slash skill in the prompt (e.g. "/typst-pdf-maker ...")
        if not explicit_skill_context:
            import re
            slash_match = re.search(r'/([a-zA-Z0-9_\-]+)', goal)
            if slash_match:
                candidate_skill = slash_match.group(1)
                skill = self.skill_manager.get_skill(candidate_skill)
                if skill and skill.trust_state == "TRUSTED":
                    print(f"[Orchestrator] Activating explicitly requested skill: {skill.name}")
                    explicit_skill_context = f"\n[EXPLICIT SKILL INSTRUCTIONS: {skill.name}]\n{skill.content}\n"

        import time
        start_time = time.time()
        
        # Clean, token-dense objective for the planner
        enhanced_objective = f"{goal}\n{explicit_skill_context}".strip()
        
        # Initialize or resume task session
        if getattr(self.task_manager, '_active_task_id', None):
            active_task_id = self.task_manager._active_task_id
            print(f"[Orchestrator] Continuing in active task session: `{active_task_id}`")
        else:
            active_task_id = self.task_manager.create_task(goal, project_id=self.workspace.project_name)
        if not hasattr(self, '_shared_executor'):
            self._shared_executor = LocalToolExecutor(mcp_manager=self.mcp_manager, skill_manager=self.skill_manager)
        self._shared_executor.set_active_task(active_task_id)

        agent_specs = self.planner.plan(enhanced_objective, self.root_agent.agent_id, budget_ref=self.root_agent.budget_ref)
        
        # Record plan into task_memory.md, task.md, and implementation_plan.md
        stages_desc = [f"[Stage {getattr(s, 'stage', 1)}] {s.requested_role} → {s.goal}" for s in agent_specs]
        proj_name = self.workspace.project_name if hasattr(self, 'workspace') and self.workspace else "default"
        self.task_manager.record_plan(active_task_id, stages_desc, objective=goal, project_id=proj_name)

        # Render Rich Orchestrator Plan
        from nava.ui.terminal import BoxRenderer, TerminalTheme, AgentTreeVisualizer
        plan_rows = []
        for s in agent_specs:
            stg = getattr(s, 'stage', 1) or 1
            mode = "PARALLEL" if getattr(s, 'is_parallel', True) else "SEQUENTIAL"
            badge = TerminalTheme.badge(s.requested_role)
            plan_rows.append(f"Stage {stg} [{mode}] → {badge} ({s.display_label or s.requested_role}): {s.goal}")
        print("\n" + BoxRenderer.render_panel("ORCHESTRATOR EXECUTION PLAN", plan_rows, color=TerminalTheme.CYAN, icon="📋"))

        # 2. Execute with lightweight context (agents read task_memory.md / project_memory.md on-demand)
        global_payload = {
            "context": f"Overall Objective: {goal}\n{explicit_skill_context}".strip(),
            "task_id": active_task_id,
            "project_name": self.workspace.project_name if hasattr(self, 'workspace') and self.workspace else "Nava",
            "available_memory_files": ["task_memory.md", "project_memory.md"]
        }
        
        import threading
        import concurrent.futures
        payload_lock = threading.Lock()
        
        if not hasattr(self, 'lock_manager'):
            from nava.governance.lock_manager import DefaultLockManager
            self.lock_manager = DefaultLockManager()

        # Group agent specs by execution stage
        stages = {}
        for i, spec in enumerate(agent_specs):
            stg = getattr(spec, 'stage', 1) or 1
            stages.setdefault(stg, []).append((i, spec))
            
        sorted_stages = sorted(stages.keys())
        
        try:
            for stg in sorted_stages:
                if self._emergency_stop_event.is_set():
                    break

                stage_items = stages[stg]
                can_parallel = len(stage_items) > 1 and all(getattr(s, 'is_parallel', True) for _, s in stage_items)
                
                # Print Rich Live Stage Header and Workers
                print(AgentTreeVisualizer.render_stage_header(stg, len(sorted_stages), can_parallel, len(stage_items)))
                for j, (idx, spec) in enumerate(stage_items):
                    is_last = (j == len(stage_items) - 1)
                    print(AgentTreeVisualizer.render_worker_line(idx + 1, is_last, spec.requested_role, spec.display_label or spec.requested_role, spec.goal, "RUNNING"))
                print(AgentTreeVisualizer.render_stage_footer())
                
                if can_parallel:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(stage_items), 8)) as executor:
                        future_to_spec = {
                            executor.submit(self._execute_single_agent, spec, idx, len(agent_specs), global_payload, payload_lock, active_task_id): (idx, spec)
                            for idx, spec in stage_items
                        }
                        for future in concurrent.futures.as_completed(future_to_spec):
                            idx, spec = future_to_spec[future]
                            try:
                                future.result()
                            except Exception as e:
                                print(f"{TerminalTheme.CRIMSON}[!] Error in parallel worker for Stage {stg} ({spec.requested_role}): {e}{TerminalTheme.RESET}")
                else:
                    for idx, spec in stage_items:
                        if self._emergency_stop_event.is_set():
                            break
                        self._execute_single_agent(spec, idx, len(agent_specs), global_payload, payload_lock, active_task_id)

            duration_sec = time.time() - start_time
            if not self._emergency_stop_event.is_set():
                # Complete task in TaskManager
                self.task_manager.complete_task(active_task_id, outcome_summary=f"Completed {len(agent_specs)} sub-tasks successfully.", is_success=True)
                
                # Collect deliverables
                art_dir = self.task_manager.get_task_artifacts_dir(active_task_id)
                artifacts = []
                if os.path.exists(art_dir):
                    for root, _, files in os.walk(art_dir):
                        for f in files:
                            rel_p = os.path.relpath(os.path.join(root, f), os.getcwd())
                            artifacts.append(rel_p)
                            
                self.task_manager.complete_task(
                    active_task_id, 
                    outcome_summary=f"Task completed successfully in {duration_sec}s across {len(agent_specs)} execution stages with {len(artifacts)} deliverables produced.",
                    is_success=True, 
                    artifacts=artifacts,
                    project_id=proj_name
                )
                if hasattr(self, 'workspace') and self.workspace:
                    try:
                        self.workspace.sync_task_completion(active_task_id, goal, artifacts)
                    except Exception:
                        pass
                print("\n" + BoxRenderer.render_completion_card(
                    goal=goal,
                    task_id=active_task_id,
                    duration_sec=duration_sec,
                    artifacts=artifacts,
                    total_subtasks=len(agent_specs)
                ))
            else:
                self.task_manager.complete_task(active_task_id, outcome_summary="Task halted by emergency stop.", is_success=False, project_id=proj_name)
                print(f"\n{TerminalTheme.CRIMSON}🛑 Task halted by Emergency Stop.{TerminalTheme.RESET}")

        except KeyboardInterrupt:
            print(f"\n\n{TerminalTheme.CRIMSON}{TerminalTheme.BOLD}🚨 KEYBOARD INTERRUPT (Ctrl+C) DETECTED! TRIGGERING EMERGENCY STOP...{TerminalTheme.RESET}")
            self.emergency_stop()
            self.task_manager.complete_task(active_task_id, outcome_summary="Emergency stop triggered via Ctrl+C.", is_success=False, project_id=proj_name)
            print(f"{TerminalTheme.CRIMSON}🛑 In-flight agents aborted. Scoped credentials revoked. Concurrency locks released.{TerminalTheme.RESET}")
        finally:
            self._emergency_stop_event.clear()

        import glob
        for f in glob.glob("scratch/*_extraction.md"):
            try:
                os.remove(f)
                print(f"{TerminalTheme.SLATE}[Teardown] Cleaned up ephemeral extraction file: {f}{TerminalTheme.RESET}")
            except Exception:
                pass
        
        print(f"\n{TerminalTheme.CYAN}──────────────────────────────────────────────────────────────────────────{TerminalTheme.RESET}\n")

    def _execute_single_agent(self, spec, index: int, total_specs: int, global_payload: dict, payload_lock: Any, task_id: Optional[str] = None):
        from nava.ui.terminal import TerminalTheme
        badge = TerminalTheme.badge(spec.requested_role)
        print(f"\n{TerminalTheme.BOLD}[{index+1}/{total_specs}]{TerminalTheme.RESET} Spawning {badge} ({spec.display_label or spec.requested_role}) for goal: {spec.goal}")
        
        try:
            child_agent = self.factory.spawn_agent(spec, self.root_agent)
        except Exception as e:
            print(f"Failed to spawn agent: {e}")
            return {"success": False, "error": str(e)}
            
        from nava.core.ledger import LocalFileReceiptStore
        receipt_store = LocalFileReceiptStore("tasks/receipts")
        
        gateway = build_test_gateway(
            self.registry, self.policy, self.risk, self.budget_engine, 
            self.hitl, self.ledger, child_agent, 
            receipt_store=receipt_store,
            concurrency_manager=self.lock_manager,
            credential_broker=self.credential_broker,
            state_observer=self.state_observer
        )
        if hasattr(self, '_emergency_stop_event'):
            gateway._emergency_event = self._emergency_stop_event
        if not hasattr(self, '_shared_executor'):
            self._shared_executor = LocalToolExecutor(mcp_manager=self.mcp_manager, skill_manager=self.skill_manager)
        if hasattr(self, "workspace") and self.workspace:
            self._shared_executor.set_active_project(self.workspace.project_name)
        if task_id:
            self._shared_executor.set_active_task(task_id)
        gateway.executor = self._shared_executor
        
        from nava.agents.runtime.graph_dispatcher import get_agent_graph
        graph = get_agent_graph(child_agent.role, self.registry)
            
        with payload_lock:
            payload_copy = dict(global_payload)
            
        initial_state = {
            "agent_state": child_agent,
            "payload": payload_copy,
            "plan": None,
            "tool_requests": [],
            "receipts": [],
            "is_success": False,
            "gateway": gateway,
            "message_bus": getattr(self, "message_bus", None),
            "history": []
        }
        
        if child_agent.role in ["DocumentAgent", "DataAgent", "VerifierAgent", "UniversalFileAgent"]:
            initial_state["tool_request"] = None
            initial_state["receipt"] = None
        elif child_agent.role in ["CodingAgent", "ReviewerAgent"]:
            initial_state["tool_request"] = None
            initial_state["receipt"] = None
            
        agent_schemas = {}
        for t_name in child_agent.tool_scope:
            t_def = self.registry.get_tool(t_name)
            if t_def:
                agent_schemas[t_name] = t_def.input_schema
        initial_state["payload"]["available_tool_schemas"] = agent_schemas
        
        print(f"Invoking graph for {child_agent.role}...")
        
        try:
            if child_agent.role in ["VerifierAgent", "DocumentAgent", "DataAgent", "UniversalFileAgent", "CodingAgent", "ReviewerAgent", "BrowserAgent", "DynamicAgent", "ResearchAgent", "ComputerAgent", "TerminalAgent"]:
                current_state = initial_state
                while True:
                    current_state = graph.invoke(current_state, config={"recursion_limit": 50})
                    tool_req = current_state.get("tool_request")
                    plan_name = current_state.get("plan")
                    
                    if plan_name == "FINISH":
                        print(f"{child_agent.role} finished its cyclic task.")
                        import json
                        def truncate_result(res):
                            res_str = json.dumps(res) if not isinstance(res, str) else res
                            return res_str[:1500] + "... [TRUNCATED]" if len(res_str) > 1500 else res
                            
                        final_data = current_state.get("final_answer") or current_state.get("observation")
                        with payload_lock:
                            global_payload[f"Step_{index+1}_{child_agent.role}"] = truncate_result(final_data)
                        break
                        
                    if tool_req:
                        print(f"Agent {child_agent.agent_id} requested tool: {tool_req.tool_name}")
                        receipt = gateway.process_request(tool_req)
                        print(f"-> Tool Execution Result: {receipt.result.name}")
                        print(f"-> Data: {receipt.result_data}")
                        
                        if task_id:
                            self.task_manager.record_action(task_id, child_agent.role, tool_req.tool_name, tool_req.arguments, receipt.result.name)
                            if isinstance(receipt.result_data, dict):
                                art_p = receipt.result_data.get("saved_to") or receipt.result_data.get("screenshot_path") or receipt.result_data.get("file")
                                if art_p:
                                    self.task_manager.record_artifact(task_id, str(art_p))
                        
                        if receipt.result.name == "FAILURE":
                            error_str = str(receipt.result_data.get("error", "Unknown error"))
                            if tool_req.tool_name == "test.run":
                                from nava.memory.store import EpisodicMemoryStore
                                from nava.core.schemas import MemoryRecord, MemoryTier, MemoryTrustLevel
                                import uuid
                                epi_store = EpisodicMemoryStore("memory/episodic.json")
                                record = MemoryRecord(
                                    memory_id=f"epi-{uuid.uuid4().hex[:8]}",
                                    tier=MemoryTier.EPISODIC,
                                    content={"event": "TEST_FAILURE", "command": tool_req.arguments, "error": error_str},
                                    trust_level=MemoryTrustLevel.UNVERIFIED,
                                    provenance=["coding_agent_test_loop"]
                                )
                                epi_store.store(record)
                                print("-> Logged failure to EpisodicMemoryStore.")
                            
                            if not self.budget_engine.record_failure(child_agent, error_str):
                                print("\n[!] RUNAWAY LOOP DETECTED (Section 14.4). Same failure state hit 3 times.")
                                print("-> Escalating to ReviewerAgent...")
                                
                                from nava.core.schemas import AgentSpec
                                import datetime, uuid
                                rev_spec = AgentSpec(
                                    request_id=f"req-{uuid.uuid4().hex[:8]}",
                                    requested_role="ReviewerAgent",
                                    goal=f"Analyze why {child_agent.role} failed: {error_str}",
                                    parent_agent_id=self.root_agent.agent_id,
                                    requested_tools=["code.diff_review", "file.read"],
                                    requested_permission_scope=["filesystem.read"],
                                    ttl=datetime.timedelta(minutes=10),
                                    max_steps=5,
                                    max_tokens=2000,
                                    max_children=0,
                                    dedup_hash=f"rev-{uuid.uuid4().hex[:8]}"
                                )
                                try:
                                    rev_agent = self.factory.spawn_agent(rev_spec, self.root_agent)
                                    rev_state = {"agent_state": rev_agent, "payload": dict(global_payload), "history": []}
                                    from nava.agents.runtime.reviewer_agent import build_reviewer_agent
                                    rev_graph = build_reviewer_agent(self.registry)
                                    rev_final = rev_graph.invoke(rev_state)
                                except Exception as e:
                                    print(f"-> Failed to run Reviewer fallback: {e}")
                                
                                print("\n-> Escalating to HITL (Human-in-the-Loop)...")
                                self.hitl.request_approval(
                                    tool_request=tool_req,
                                    assessment=None,
                                    context=f"CodingAgent is stuck on error: {error_str}. Reviewer analysis complete. Please intervene or abort."
                                )
                                break
                        
                        current_state["observation"] = receipt.result_data
                        current_state["tool_request"] = None
            else:
                final_state = graph.invoke(initial_state)
                tool_req = final_state.get("tool_request")
                
                import json
                def truncate_result(res):
                    res_str = json.dumps(res)
                    return res_str[:1500] + "... [TRUNCATED for inter-agent context]" if len(res_str) > 1500 else res

                if tool_req:
                    print(f"Agent {child_agent.agent_id} requested tool: {tool_req.tool_name}")
                    receipt = gateway.process_request(tool_req)
                    print(f"-> Tool Execution Result: {receipt.result.name}")
                    print(f"-> Data: {receipt.result_data}")
                    with payload_lock:
                        global_payload[f"{child_agent.role}_result"] = truncate_result(receipt.result_data)
                
                if final_state.get("receipt"):
                    result_enum = final_state["receipt"].result
                    result_data = final_state["receipt"].result_data
                    print(f"-> Tool Execution Result: {result_enum.name}")
                    print(f"-> Data: {result_data}")
                    with payload_lock:
                        global_payload[f"Step_{index+1}_{child_agent.role}"] = truncate_result(result_data)
                    final_state["is_success"] = (result_enum.name == "SUCCESS")
                elif final_state.get("receipts"):
                    results_data = [r.result_data for r in final_state["receipts"]]
                    print(f"-> Tool Execution Results Data: {results_data}")
                    with payload_lock:
                        global_payload[f"Step_{index+1}_{child_agent.role}"] = truncate_result(results_data)
                    final_state["is_success"] = all(r.result.name == "SUCCESS" for r in final_state["receipts"])
                elif tool_req and 'receipt' in locals():
                    final_state["is_success"] = (receipt.result.name == "SUCCESS")
                    
                if not final_state.get('is_success'):
                    print(f"\n[!] Agent {child_agent.role} failed. Initiating Rollback & Compensation (Phase 7)...")
                    from nava.governance.compensation_engine import CompensationEngine
                    from nava.governance.rollback_engine import RollbackEngine
                    from nava.core.schemas import AgentState, AgentType, TaskBudget
                    import datetime, uuid
                    
                    rbk_budget = TaskBudget(
                        task_id=f"budget-rbk-{uuid.uuid4().hex[:8]}",
                        max_agents=1, max_depth=1, max_steps=5, max_tokens=5000,
                        max_runtime=datetime.timedelta(minutes=5), max_retries=1
                    )
                    self.budget_engine.register_budget(rbk_budget)
                    
                    rbk_agent = AgentState(
                        agent_id="SYSTEM_ROLLBACK",
                        role="SYSTEM_ROLLBACK",
                        type=AgentType.STATIC,
                        goal="Rollback failed task",
                        permission_scope=["*"],
                        credential_scope=[],
                        tool_scope=["*"],
                        depth=0,
                        ttl=datetime.timedelta(minutes=5),
                        expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
                        budget_ref=rbk_budget.task_id
                    )
                    
                    rbk_gateway = build_test_gateway(
                        self.registry, self.policy, self.risk, self.budget_engine, 
                        self.hitl, self.ledger, rbk_agent, 
                        receipt_store=receipt_store,
                        concurrency_manager=self.lock_manager,
                        credential_broker=self.credential_broker,
                        state_observer=self.state_observer
                    )
                    
                    comp_engine = CompensationEngine(rbk_gateway)
                    rollback_engine = RollbackEngine(rbk_gateway, comp_engine)
                    
                    agent_receipts = receipt_store.get_receipts_by_agent(child_agent.agent_id)
                    rollback_engine.rollback(agent_receipts, rbk_budget.task_id)
                    print(f"[Budget Check] SYSTEM_ROLLBACK budget consumed steps: {rbk_budget.consumed_steps}/{rbk_budget.max_steps}")
        finally:
            print(f"-> Tearing down agent: {child_agent.agent_id} ({child_agent.role})")
            child_agent.status = AgentStatus.TERMINATED
            budget = self.budget_engine.budgets.get(child_agent.budget_ref)
            if budget and budget.consumed_agents > 0:
                budget.consumed_agents -= 1
            print(f"-> Teardown complete for {child_agent.agent_id}.")

    def emergency_stop(self, reason: str = "User triggered emergency halt"):
        """
        Emergency Kill Switch (Section 31.4 & Invariant #18):
        Out-of-band immediate shutdown of all in-flight execution.
        """
        print(f"\n=======================================================")
        print(f"  [!] EMERGENCY STOP TRIGGERED: {reason}")
        print(f"=======================================================")
        
        if hasattr(self, '_emergency_stop_event'):
            self._emergency_stop_event.set()
            
        if hasattr(self, 'credential_broker'):
            self.credential_broker.emergency_revoke_all()
            
        if hasattr(self, 'hitl'):
            self.hitl.cancel_all_pending()
            
        if hasattr(self, 'lock_manager'):
            self.lock_manager.release_all_global()
            
        from nava.core.schemas import Event
        import uuid, datetime
        evt = Event(
            event_id=f"evt-halt-{uuid.uuid4().hex[:8]}",
            event_type="EMERGENCY_HALT",
            task_id=self.root_agent.budget_ref or "global",
            payload={"reason": reason, "timestamp": datetime.datetime.utcnow().isoformat()}
        )
        self.ledger.append_event(evt)
        print("[Orchestrator] Emergency halt executed. All systems safely secured.")




if __name__ == "__main__":
    if not os.path.exists("nava.yaml"):
        # Write a dummy config for manual testing
        with open("nava.yaml", "w") as f:
            f.write("""
root_agent:
  ceiling_permissions:
    - filesystem.write
    - filesystem.read
    - data.analyze
    - test.run
  ceiling_tools:
    - file.write
    - file.create_pdf
    - file.create_docx
    - file.create_pptx
    - file.read
    - test.run
budget:
  max_agents: 50
  max_depth: 10
  max_steps: 1000
  max_tokens: 1000000
""")
    
    import sys
    orch = Orchestrator()
    if len(sys.argv) > 1:
        objective = " ".join(sys.argv[1:])
    else:
        objective = input("Enter objective: ")
        
    if objective:
        orch.run(objective)
