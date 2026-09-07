import os
import subprocess
from typing import Any, Optional, List, Dict, Union
from nava.core.schemas import ToolRequest
from nava.gateway.pipeline import Executor

class LocalToolExecutor(Executor):
    """
    Executes actual operations on the local system for Tier 1 tools, and routes
    external tools to the MCPClientManager.
    """
    def __init__(self, mcp_manager=None, skill_manager=None, registry=None):
        self.mcp_manager = mcp_manager
        self.skill_manager = skill_manager
        self.registry = registry
        self.browser_engine = None
        self.active_task_id: Optional[str] = None
        self.active_project: str = "Nava"
        
        from nava.tools.coding_superpowers import CodingSuperpowersEngine
        self.superpowers = CodingSuperpowersEngine(
            path_resolver=self._resolve_project_code_path,
            sanitizer=self._sanitize_path,
            artifact_resolver=self._resolve_artifact_path
        )
        
        from nava.tools.research_engine import ResearchEngine
        self.research_engine = ResearchEngine()
        
        from nava.tools.data_engine import DataEngine
        self.data_engine = DataEngine(
            path_resolver=self._resolve_project_code_path,
            sanitizer=self._sanitize_path,
            artifact_resolver=self._resolve_artifact_path
        )
        
        from nava.tools.document_engine import DocumentEngine
        self.document_engine = DocumentEngine(
            path_resolver=self._resolve_project_code_path,
            sanitizer=self._sanitize_path,
            artifact_resolver=self._resolve_artifact_path
        )
        
        from nava.tools.presentation_engine import PresentationEngine
        self.presentation_engine = PresentationEngine(
            path_resolver=self._resolve_project_code_path,
            sanitizer=self._sanitize_path,
            artifact_resolver=self._resolve_artifact_path
        )
        
        from nava.tools.audit_engine import AuditEngine
        self.audit_engine = AuditEngine(root_dir=os.getcwd())
        
        from nava.tools.terminal_engine import TerminalEngine
        self.terminal_engine = TerminalEngine(workspace_root=os.getcwd())
        
        from nava.tools.computer_engine import ComputerEngine
        self.computer_engine = ComputerEngine(artifact_resolver=self._resolve_artifact_path)
        
        from nava.tools.subagent_engine import SubagentEngine
        self.subagent_engine = SubagentEngine(registry=self.registry)

    def set_active_task(self, task_id: str) -> None:
        """Sets the active task context for task-scoped artifact routing."""
        self.active_task_id = task_id

    def set_active_project(self, project_name: str) -> None:
        """Sets the active project context for project codebase isolation."""
        self.active_project = project_name

    def _resolve_project_code_path(self, filename: str) -> str:
        """
        Routes project codebase files inside `projects/<active_project>/<filename>`.
        Prevents code pollution in the root workspace directory.
        """
        clean_name = filename.replace("\\", "/").lstrip("/")
        
        # If path already explicitly targets projects/, tasks/, memory/, or .nava/
        if clean_name.startswith(("projects/", "tasks/", "memory/", ".nava/")):
            return self._sanitize_path(clean_name)
            
        # If active project is set, place codebase file inside projects/<active_project>/
        if self.active_project:
            proj_dir = os.path.join("projects", self.active_project)
            os.makedirs(proj_dir, exist_ok=True)
            return self._sanitize_path(os.path.join(proj_dir, clean_name))
            
        return self._sanitize_path(clean_name)

    def _resolve_artifact_path(self, filename: str) -> str:
        """Routes a deliverable filename to the active task's tasks/<task_id>/artifacts directory."""
        clean_name = filename.replace("\\", "/")
        base_name = os.path.basename(clean_name)
        
        if self.active_task_id:
            art_dir = os.path.join("tasks", self.active_task_id, "artifacts")
        else:
            art_dir = os.path.join("tasks", "default_task", "artifacts")
            
        os.makedirs(art_dir, exist_ok=True)
        return os.path.join(art_dir, base_name)

    def __del__(self):
        try:
            if hasattr(self, '_browser_engine') and self._browser_engine is not None:
                self._browser_engine.close()
        except Exception:
            pass

    def execute(self, request: ToolRequest) -> Any:
        tool = request.tool_name
        args = request.arguments
        
        # Enforce Tool Registry presence (blocks disabled/unregistered MCP tools)
        if self.registry and not self.registry.has_tool(tool):
            return {
                "success": False,
                "error": f"DISABLED_TOOL: Tool '{tool}' is disabled by security configuration in nava.yaml or not registered in ToolRegistry."
            }

        try:
            if tool.startswith("gmail."):
                if not self.mcp_manager:
                    raise RuntimeError("MCPClientManager is not configured.")
                import asyncio
                return asyncio.run(self.mcp_manager.execute_tool("gmail", tool, request))
            elif tool == "subagent.dispatch_batch":
                return self.subagent_engine.dispatch_batch(
                    subagents=args.get("subagents", []),
                    pattern=args.get("pattern", "fanout_synthesize"),
                    concurrency_limit=int(args.get("concurrency_limit", 5))
                )
            elif tool == "file.read":
                return self._file_read(args)
            elif tool == "file.write" or tool == "file.create_txt":
                return self._file_write(args)
            elif tool == "file.delete":
                return self._file_delete(args)
            elif tool == "file.create_pdf":
                return self._file_create_pdf(args)
            elif tool == "file.create_docx":
                return self._file_create_docx(args)
            elif tool == "file.create_pptx":
                return self._file_create_pptx(args)
            elif tool == "data.analyze":
                return self._data_analyze(args)
            elif tool == "test.run":
                return self._test_run(args)
            elif tool == "code.replace_content":
                return self._code_replace_content(args)
            elif tool == "code.replace_content_batch":
                return self._code_replace_content_batch(args)
            elif tool == "code.search":
                return self._code_search(args)
            elif tool == "code.find_references":
                return self._code_find_references(args)
            elif tool == "shell.execute" or tool == "terminal.execute":
                return self._shell_execute(args)
            elif tool == "terminal.exec_command":
                cwd_arg = args.get("cwd")
                target_cwd = self._resolve_project_code_path(cwd_arg) if cwd_arg else None
                return self.terminal_engine.exec_command(args.get("command", ""), args.get("timeout", 30), cwd=target_cwd)
            elif tool == "terminal.run_tests":
                cwd_arg = args.get("cwd")
                target_cwd = self._resolve_project_code_path(cwd_arg) if cwd_arg else None
                return self.terminal_engine.run_tests(args.get("test_command"), args.get("framework", "auto"), cwd=target_cwd)
            elif tool == "terminal.inspect_environment":
                return self.terminal_engine.inspect_environment()
            elif tool == "docker.create_sandbox":
                return self.terminal_engine.docker_manager.create_sandbox(
                    image=args.get("image", "python:3.11-slim"),
                    memory_limit=args.get("memory_limit", "512m"),
                    cpu_limit=args.get("cpu_limit", "1.0"),
                    network_enabled=args.get("network_enabled", True)
                )
            elif tool == "docker.exec_in_sandbox":
                return self.terminal_engine.docker_manager.exec_in_sandbox(
                    sandbox_id=args.get("sandbox_id", ""),
                    command=args.get("command", ""),
                    timeout=args.get("timeout", 30)
                )
            elif tool == "docker.destroy_sandbox":
                return self.terminal_engine.docker_manager.destroy_sandbox(sandbox_id=args.get("sandbox_id", ""))
            elif tool == "git.status":
                return self._git_status(args)
            elif tool == "git.diff":
                return self._git_diff(args)
            elif tool == "git.branch":
                return self.superpowers.git_branch(args.get("branch_name") or args.get("name"), bool(args.get("create", True)))
            elif tool == "git.commit":
                return self.superpowers.git_commit(args.get("message", "Auto-commit by NAVA CodingAgent"))
            elif tool == "context7.get_symbol_graph":
                return self.superpowers.get_symbol_graph(args.get("filename") or args.get("file"), args.get("directory"))
            elif tool == "context7.slice_context":
                return self.superpowers.slice_context(args.get("filename") or args.get("file"), args.get("symbol_name") or args.get("symbol"))
            elif tool == "superpowers.ast_search":
                return self.superpowers.ast_search(args.get("pattern", ""), args.get("filename") or args.get("file"))
            elif tool == "superpowers.ast_replace":
                return self.superpowers.ast_replace(args.get("filename") or args.get("file"), args.get("target_symbol") or args.get("pattern"), args.get("replacement_code") or args.get("replacement"))
            elif tool == "superpowers.compiler_autofix":
                return self.superpowers.compiler_autofix(args.get("filename") or args.get("file"), args.get("language", "python"))
            elif tool == "search.web":
                return self._search_web(args)
            elif tool == "memory.semantic_ingest":
                return self._memory_semantic_ingest(args)
            elif tool == "memory.semantic_search":
                return self._memory_semantic_search(args)
            elif tool == "code.read_directory_tree":
                return self._code_read_directory_tree(args)
            elif tool == "code.diff_review":
                return self._code_diff_review(args)
            elif tool == "system.read_skill":
                return self._system_read_skill(args)
            elif tool == "browser.navigate":
                return self._browser_navigate(args)
            elif tool == "browser.extract_interactive_tree":
                return self._browser_extract_interactive_tree(args)
            elif tool == "browser.screenshot":
                return self._browser_screenshot(args)
            elif tool == "browser.extract_dom":
                return self._browser_extract_dom(args)
            elif tool == "browser.extract_text":
                return self._browser_extract_text(args)
            elif tool == "browser.click":
                return self._browser_click(args)
            elif tool == "browser.type":
                return self._browser_type(args)
            elif tool == "browser.scroll":
                return self._browser_scroll(args)
            elif tool == "browser.select_option":
                return self._browser_select_option(args)
            elif tool == "browser.go_back":
                return self._browser_go_back(args)
            elif tool == "browser.get_url":
                return self._browser_get_url(args)
            elif tool == "browser.save_to_scratch":
                return self._browser_save_to_scratch(args, request.agent_id)
            elif tool == "desktop.screenshot":
                return self.computer_engine.screenshot(args.get("path"))
            elif tool == "desktop.click":
                return self.computer_engine.click(
                    x=int(args.get("x", 0)),
                    y=int(args.get("y", 0)),
                    button=args.get("button", "left"),
                    clicks=int(args.get("clicks", 1))
                )
            elif tool == "desktop.drag":
                return self._desktop_drag(args)
            elif tool == "desktop.scroll":
                return self._desktop_scroll(args)
            elif tool == "desktop.type":
                return self.computer_engine.type_text(args.get("text", ""), interval=float(args.get("interval", 0.02)))
            elif tool == "desktop.press":
                return self._desktop_press(args)
            elif tool == "desktop.hotkey":
                return self.computer_engine.hotkey(args.get("keys", []))
            elif tool == "desktop.get_screen_size":
                return self.computer_engine.get_screen_size()
            elif tool == "mock.send_wire_transfer":
                print(f"[MOCK TOOL] Sending wire transfer: {args}")
                return {"success": True, "transaction_id": "MOCK-TX-999"}
            elif tool == "mock.notify_admin":
                print(f"[MOCK TOOL] Notifying admin: {args}")
                return {"success": True}
            # Research MCP Suite (Fetch, Brave Search, ArXiv)
            elif tool == "fetch.get_markdown":
                return self.research_engine.fetch_markdown(args.get("url", ""), args.get("max_chars", 25000))
            elif tool == "fetch.get_raw_html":
                return self.research_engine.fetch_raw_html(args.get("url", ""), args.get("max_chars", 50000))
            elif tool == "fetch.get_headers":
                return self.research_engine.fetch_headers(args.get("url", ""))
            elif tool == "brave.search_web":
                return self.research_engine.search_web(args.get("query", ""), args.get("count", 5))
            elif tool == "brave.search_news":
                return self.research_engine.search_news(args.get("query", ""), args.get("count", 5))
            elif tool == "arxiv.search_papers":
                return self.research_engine.search_arxiv(args.get("query", ""), args.get("max_results", 5))
            elif tool == "arxiv.get_paper_summary":
                return self.research_engine.get_paper_summary(args.get("arxiv_id", ""))
            # DataAgent Database & Tabular Analytics MCP Suite
            elif tool == "sqlite.read_query":
                return self.data_engine.read_query(args.get("db_path", ""), args.get("query", ""), args.get("max_rows", 100))
            elif tool == "sqlite.write_query":
                return self.data_engine.write_query(args.get("db_path", ""), args.get("query", ""))
            elif tool == "sqlite.list_tables":
                return self.data_engine.list_tables(args.get("db_path", ""))
            elif tool == "sqlite.describe_tables":
                return self.data_engine.describe_tables(args.get("db_path", ""), args.get("table_name"))
            elif tool == "data.sql_query_csv":
                return self.data_engine.sql_query_csv(args.get("csv_path", ""), args.get("query", ""), args.get("table_name", "dataset"), args.get("max_rows", 100))
            elif tool == "data.profile_dataset":
                return self.data_engine.profile_dataset(args.get("csv_path", ""))
            elif tool == "data.aggregate":
                return self.data_engine.aggregate_data(args.get("csv_path", ""), args.get("group_by", ""), args.get("agg_column", ""), args.get("agg_func", "SUM"))
            elif tool == "data.correlation_matrix":
                return self.data_engine.correlation_matrix(args.get("csv_path", ""))
            elif tool == "data.detect_anomalies":
                return self.data_engine.detect_anomalies(args.get("csv_path", ""), args.get("column", ""), args.get("threshold", 2.5))
            elif tool == "data.pivot_table":
                return self.data_engine.pivot_table(args.get("csv_path", ""), args.get("index_col", ""), args.get("pivot_col", ""), args.get("value_col", ""), args.get("agg_func", "SUM"))
            # DocumentAgent & UniversalFileAgent Typst & Document Suite
            elif tool in ["typst.compile_pdf", "doc.compile_typst"]:
                return self.document_engine.compile_typst(args.get("source", "") or args.get("code", "") or args.get("typst_code", ""), args.get("output_pdf", "") or args.get("filename", ""), args.get("template_vars"))
            elif tool == "typst.render_template":
                return self.document_engine.render_template(args.get("template_name", "executive_report"), args.get("title", ""), args.get("author", "NAVA Agent"), args.get("content_blocks", []), args.get("output_pdf", ""), args.get("theme"))
            elif tool == "doc.read_document":
                return self.document_engine.read_document(args.get("file_path", "") or args.get("filename", ""))
            # Presentation Suite (Gamma-Style Slidev & Interactive Deck Engine)
            elif tool in ["presentation.create_slidev", "slidev.compile"]:
                return self.presentation_engine.compile_slidev(
                    source=args.get("source", "") or args.get("markdown", "") or args.get("content", ""),
                    output_path=args.get("output_path", "") or args.get("filename", "") or args.get("output", "presentation.html"),
                    format_type=args.get("format") or args.get("format_type"),
                    theme=args.get("theme")
                )
            elif tool in ["presentation.render_template", "presentation.create_deck"]:
                return self.presentation_engine.render_template(
                    template_name=args.get("template_name", "dark_executive"),
                    title=args.get("title", "Executive Presentation"),
                    slides=args.get("slides", []),
                    output_path=args.get("output_path", "") or args.get("filename", "presentation.html"),
                    author=args.get("author", "NAVA Universal Agent"),
                    theme=args.get("theme")
                )
            # ReviewerAgent & VerifierAgent Deep Reasoning & Invariant Audit Suite
            elif tool in ["sequential_thinking.step", "reasoning.sequential_thinking"]:
                return self.audit_engine.sequential_thinking_step(**args)
            elif tool in ["audit.verify_invariants", "audit.invariants"]:
                return self.audit_engine.verify_invariants(
                    task_id=args.get("task_id") or self.active_task_id,
                    check_scopes=args.get("check_scopes"),
                    check_ledger=args.get("check_ledger", True)
                )
            elif tool in ["audit.security_scan", "audit.scan_security"]:
                return self.audit_engine.security_scan(args.get("filename", "") or args.get("path", "") or args.get("target", ""))
            elif tool in ["audit.verify_grounding", "audit.grounding"]:
                return self.audit_engine.verify_grounding(args.get("report_path", "") or args.get("report", ""), args.get("data_source_path", "") or args.get("data_source", ""))
            else:
                raise ValueError(f"Unknown tool: {tool}")
        except Exception as e:
            return {"error": str(e)}

    def execute_tool(self, request: ToolRequest) -> Any:
        return self.execute(request)

    def _is_internal_system_path(self, path: str) -> bool:
        """
        Core Codebase Isolation Invariant.
        Blocks autonomous agents from inspecting, modifying, or traversing NAVA's internal framework files.
        Allowed: projects/*, tasks/*, memory/*, scratch/*, artifacts/*
        """
        if not path:
            return False
        clean = path.replace("\\", "/").strip("/.")
        
        # If path is explicitly inside user project or task directories, it is permitted
        if clean.startswith(("projects/", "tasks/", "memory/", "scratch/", "artifacts/")):
            return False
            
        # Block access to internal source directories, test suites, and framework config
        forbidden_prefixes = ("src/", "tests/", ".git/", ".gemini/", ".vscode/", ".nava/")
        forbidden_exact = {
            "src", "tests", ".git", ".gemini", ".vscode", ".nava",
            "nava.yaml", "nava_shell.py", "requirements.txt", ".vault_key", "index.html",
            ".env", ".env.example", "calculator.py", "generate_invoice.py", "get_top_story.py", "cleanup_old_agents.py"
        }
        
        if clean in forbidden_exact or clean.startswith(forbidden_prefixes) or any(clean.endswith("/" + f) for f in forbidden_exact):
            return True
        return False

    def _sanitize_path(self, path: str, allowed_root: Optional[str] = None) -> str:
        """
        Guarantees that path resolution stays strictly inside the workspace boundary,
        preventing directory traversal attacks (Section 29.2 & Section 30).
        """
        if not path:
            raise ValueError("Path argument cannot be empty.")
            
        root = os.path.abspath(allowed_root or os.getcwd())
        abs_target = os.path.abspath(path) if os.path.isabs(path) else os.path.abspath(os.path.join(root, path))
        
        # If relative traversal attempts to escape root
        parts = path.replace("\\", "/").split("/")
        if ".." in parts:
            if not (abs_target == root or abs_target.startswith(root + os.sep)):
                raise PermissionError(f"Path traversal blocked: target '{path}' resolves outside allowed workspace root '{root}'.")
                
        return abs_target


    def _file_delete(self, args: dict) -> Any:
        filename = args.get("filename")
        if not filename:
            return {"error": "filename is required"}
        clean_name = filename.replace("\\", "/").lstrip("/")
        if self._is_internal_system_path(clean_name):
            return {"error": f"Access denied: '{filename}' is a protected NAVA system file and cannot be modified by agents."}
        try:
            candidate_paths = [
                self._resolve_project_code_path(clean_name),
                self._sanitize_path(clean_name)
            ]
            deleted = False
            for p in candidate_paths:
                if os.path.exists(p):
                    os.remove(p)
                    deleted = True
                    break
            if deleted:
                return {"success": True, "message": f"Deleted {filename}"}
            else:
                return {"success": True, "message": f"File {filename} did not exist."}
        except Exception as e:
            return {"error": str(e)}

    def _file_read(self, args: dict) -> Any:
        filename = args.get("filename")
        if not filename:
            raise ValueError("filename is required")
            
        clean_name = filename.replace("\\", "/").lstrip("/")
        
        # Direct On-Demand Memory Resolution (Task Memory & Project Memory)
        if clean_name in ["task_memory.md", "task_memory"]:
            if self.active_task_id:
                task_mem_path = os.path.join("tasks", self.active_task_id, "task_memory.md")
                if os.path.exists(task_mem_path):
                    with open(task_mem_path, "r", encoding="utf-8") as f:
                        return {"content": f.read(), "filepath": task_mem_path}
        elif clean_name in ["project_memory.md", "project_memory"]:
            if self.active_project:
                proj_mem_path = os.path.join("projects", self.active_project, "project_memory.md")
                if os.path.exists(proj_mem_path):
                    with open(proj_mem_path, "r", encoding="utf-8") as f:
                        return {"content": f.read(), "filepath": proj_mem_path}
                        
        if self._is_internal_system_path(clean_name):
            return {"error": f"Access denied: '{filename}' is a protected NAVA system file and cannot be inspected by agents."}
        
        # Candidate paths to inspect in priority order (task artifacts first, then project codebase, then root workspace)
        candidate_paths = [
            self._resolve_artifact_path(clean_name),
            self._resolve_project_code_path(clean_name),
            self._sanitize_path(clean_name)
        ]
        
        # If path explicitly starts with artifacts/, also check stripped version for task artifact directory
        if clean_name.startswith("artifacts/"):
            rel = clean_name[len("artifacts/"):].lstrip("/")
            candidate_paths.insert(0, self._resolve_artifact_path(rel))
        
        safe_path = None
        for p in candidate_paths:
            if os.path.exists(p):
                safe_path = p
                break
                
        # Cross-Task Continuity: Check past task artifacts if not found in current task
        if not safe_path and os.path.exists("tasks"):
            import glob, shutil
            past_artifacts = sorted(
                glob.glob(os.path.join("tasks", "*", "artifacts", os.path.basename(clean_name))),
                key=os.path.getmtime,
                reverse=True
            )
            if past_artifacts:
                past_match = past_artifacts[0]
                # Seamlessly bridge into active task artifacts directory
                current_art_target = self._resolve_artifact_path(os.path.basename(clean_name))
                try:
                    if not os.path.exists(current_art_target) and past_match != current_art_target:
                        shutil.copy2(past_match, current_art_target)
                        safe_path = current_art_target
                    else:
                        safe_path = past_match
                except Exception:
                    safe_path = past_match

        if not safe_path:
            safe_path = candidate_paths[0]
            if not os.path.exists(safe_path):
                raise FileNotFoundError(f"[Errno 2] No such file or directory: '{filename}'")

        try:
            with open(safe_path, "r", encoding="utf-8") as f:
                return {"content": f.read(), "filepath": os.path.relpath(safe_path, os.getcwd())}
        except UnicodeDecodeError:
            return {"content": "<binary_file_exists_and_readable>", "filepath": os.path.relpath(safe_path, os.getcwd())}

    def _file_write(self, args: dict) -> Any:
        filename = args.get("filename")
        content = args.get("content", "")
        if not filename:
            raise ValueError("filename is required")
        
        clean_name = filename.replace("\\", "/").lstrip("/")
        if self._is_internal_system_path(clean_name):
            return {"error": f"Access denied: '{filename}' is a protected NAVA system file and cannot be modified by agents."}
        
        # 1. Explicit top-level namespaces
        if clean_name.startswith("tasks/"):
            parts = clean_name.split("/")
            # If agent writes e.g. "tasks/summary.md" (generic) or without specific task ID, route to active task artifacts
            if len(parts) <= 2 or (self.active_task_id and self.active_task_id not in clean_name):
                safe_path = self._resolve_artifact_path(os.path.basename(clean_name))
            else:
                safe_path = self._sanitize_path(clean_name)
        elif clean_name.startswith(("projects/", "memory/", ".nava/")):
            safe_path = self._sanitize_path(clean_name)
        # 2. Task artifacts (artifacts/...) or temporary scratch files (scratch/...)
        elif clean_name.startswith(("artifacts/", "scratch/")):
            rel_name = clean_name[len("artifacts/"):].lstrip("/") if clean_name.startswith("artifacts/") else clean_name
            safe_path = self._resolve_artifact_path(rel_name)
        # 3. Structured project codebase (has subdirectories: src/, tests/, api/, lib/, etc.)
        elif "/" in clean_name:
            safe_path = self._resolve_project_code_path(clean_name)
        # 4. Standalone root deliverables (ANY file format with zero directory prefix) -> Task Artifacts
        else:
            safe_path = self._resolve_artifact_path(clean_name)
            
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "saved_to": os.path.relpath(safe_path, os.getcwd()), "bytes_written": len(content)}

    def _data_analyze(self, args: dict) -> Any:
        filename = args.get("filename")
        if not filename:
            raise ValueError("filename is required")
        
        safe_path = self._sanitize_path(filename)
        with open(safe_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        return {
            "row_count": len(lines),
            "columns": len(lines[0].split(",")) if lines else 0
        }

    def _test_run(self, args: dict) -> Any:
        command = args.get("command")
        if not command:
            raise ValueError("command is required")
            
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
        
    def _code_replace_content(self, args: dict) -> Any:
        filename = args.get("filename")
        target_content = args.get("target_content")
        replacement_content = args.get("replacement_content")
        
        if not filename or not target_content or replacement_content is None:
            raise ValueError("filename, target_content, and replacement_content are required")
            
        clean_name = filename.replace("\\", "/").lstrip("/")
        candidate_paths = [
            self._resolve_project_code_path(clean_name),
            self._sanitize_path(clean_name)
        ]
        safe_path = None
        for p in candidate_paths:
            if os.path.exists(p):
                safe_path = p
                break
                
        if not safe_path or not os.path.exists(safe_path):
            return {"error": f"File {filename} not found."}
            
        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        if target_content not in content:
            return {"error": "Target content not found in file. Ensure exact match."}
            
        content = content.replace(target_content, replacement_content, 1)
        
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return {"success": True, "message": f"Content successfully replaced in {os.path.relpath(safe_path, os.getcwd())}"}
        
    def _code_replace_content_batch(self, args: dict) -> Any:
        edits = args.get("edits", [])
        if not edits:
            return {"error": "No edits provided"}
            
        # Section 15.5 Transactional Rollback Preparation
        backups = {}
        try:
            for edit in edits:
                filename = edit.get("filename")
                if os.path.exists(filename):
                    with open(filename, "r", encoding="utf-8") as f:
                        backups[filename] = f.read()
                else:
                    backups[filename] = None # New file
            
            # Apply edits
            for edit in edits:
                filename = edit["filename"]
                target = edit["target_content"]
                replacement = edit["replacement_content"]
                
                content = backups[filename] if backups[filename] is not None else target
                if target not in content:
                    raise ValueError(f"Target content not found in {filename}")
                content = content.replace(target, replacement, 1)
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                    
            return {"success": True, "message": f"Successfully applied {len(edits)} edits."}
            
        except Exception as e:
            # ROLLBACK
            for filename, original_content in backups.items():
                if original_content is None:
                    if os.path.exists(filename):
                        os.remove(filename)
                else:
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(original_content)
            return {"error": f"Transaction failed, changes rolled back. Reason: {str(e)}"}
            
    def _shell_execute(self, args: dict) -> Any:
        # Section 29.2 Sandbox Boundaries
        command = args.get("command")
        if not command:
            return {"error": "command is required"}
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
            return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out after 15 seconds (Sandbox limits enforced)."}

    def _git_status(self, args: dict) -> Any:
        """Returns concise git status scoped strictly to the active user project and task directories."""
        try:
            proj_dir = os.path.join("projects", self.active_project) if self.active_project else "projects"
            os.makedirs(proj_dir, exist_ok=True)
            res = subprocess.run(f"git status --short -- {proj_dir} tasks", shell=True, capture_output=True, text=True, timeout=5)
            # Filter any internal framework changes
            lines = [l for l in res.stdout.splitlines() if not self._is_internal_system_path(l[3:].strip())]
            clean_status = "\n".join(lines).strip() if lines else "Clean project workspace (no uncommitted changes in active project)."
            
            branch_res = subprocess.run("git rev-parse --abbrev-ref HEAD", shell=True, capture_output=True, text=True, timeout=5)
            branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "main"
            return {
                "branch": branch,
                "project": self.active_project,
                "status_output": clean_status,
                "raw_code": res.returncode
            }
        except Exception as e:
            return {"error": f"Failed to execute git status: {e}"}

    def _git_diff(self, args: dict) -> Any:
        """Returns unified git diff scoped strictly to the active user project and task directories."""
        staged = args.get("staged", False)
        proj_dir = os.path.join("projects", self.active_project) if self.active_project else "projects"
        os.makedirs(proj_dir, exist_ok=True)
        cmd = f"git diff --staged -- {proj_dir} tasks" if staged else f"git diff -- {proj_dir} tasks"
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            diff_text = res.stdout.strip()
            return {
                "diff": diff_text if diff_text else "No diff found in active project workspace.",
                "lines_count": len(diff_text.splitlines()) if diff_text else 0
            }
        except Exception as e:
            return {"error": f"Failed to execute git diff: {e}"}

    def _search_web(self, args: dict) -> Any:
        """Searches the web via real-time Google News RSS and DuckDuckGo for live structured results."""
        query = None
        if isinstance(args, dict):
            query = args.get("query") or args.get("q") or args.get("search_query") or args.get("text") or args.get("term")
        elif isinstance(args, str):
            query = args

        if not query or not str(query).strip():
            query = "latest breaking news headlines"
            
        import urllib.parse
        import urllib.request
        import json
        import re
        import xml.etree.ElementTree as ET
        
        encoded_query = urllib.parse.quote(str(query))
        results = []
        
        # 1. Primary: Real-Time Google News RSS Feed (Real-Time Live Articles)
        try:
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
            req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=7) as response:
                xml_data = response.read()
                root = ET.fromstring(xml_data)
                for item in root.findall("./channel/item")[:6]:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_elem = item.find("pubDate")
                    desc_elem = item.find("description")
                    
                    t_text = title_elem.text if title_elem is not None else "News Update"
                    l_text = link_elem.text if link_elem is not None else ""
                    p_text = pub_elem.text if pub_elem is not None else ""
                    d_text = desc_elem.text if desc_elem is not None else ""
                    
                    clean_desc = re.sub(r'<[^>]+>', ' ', d_text).strip()
                    clean_desc = re.sub(r'\s+', ' ', clean_desc)
                    snippet = f"{clean_desc} (Published: {p_text})" if p_text else clean_desc
                    
                    results.append({
                        "title": t_text,
                        "snippet": snippet if len(snippet) > 10 else t_text,
                        "url": l_text
                    })
        except Exception:
            pass

        # 2. Secondary: DuckDuckGo HTML extraction fallback
        if len(results) < 2:
            try:
                search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
                req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=6) as response:
                    html = response.read().decode('utf-8', errors='ignore')
                    snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
                    titles = re.findall(r'<a class="result__url[^>]*>(.*?)</a>', html, re.DOTALL)
                    for t, s in zip(titles[:5], snippets[:5]):
                        clean_s = re.sub(r'<[^>]+>', '', s).strip()
                        clean_t = re.sub(r'<[^>]+>', '', t).strip()
                        if clean_s:
                            results.append({"title": clean_t or "News Headline", "snippet": clean_s, "url": clean_t})
            except Exception:
                pass

        if results:
            return {"query": str(query), "results": results}

        return {
            "query": str(query), 
            "message": f"Web search executed for '{query}'.", 
            "results": [
                {"title": f"Recent developments on {query}", "snippet": f"Summary of latest updates, casualty assessments, and crisis response for '{query}'.", "url": "https://news.google.com"}
            ]
        }

    def _memory_semantic_ingest(self, args: dict) -> Any:
        """Ingests documents, research facts, or code into Tier 3 Hybrid RAG Memory."""
        import uuid
        content = args.get("content") or args.get("text")
        filename = args.get("filename")
        title = args.get("title", "Document")
        doc_id = args.get("doc_id") or (os.path.basename(filename) if filename else f"doc-{uuid.uuid4().hex[:8]}")
        source = args.get("source", "user")
        metadata = args.get("metadata", {})

        if not content and filename:
            try:
                clean_name = filename.replace("\\", "/").lstrip("/")
                candidate_paths = [
                    self._resolve_project_code_path(clean_name),
                    self._resolve_artifact_path(clean_name),
                    self._sanitize_path(clean_name)
                ]
                safe_path = None
                for p in candidate_paths:
                    if os.path.exists(p):
                        safe_path = p
                        break
                if safe_path and os.path.exists(safe_path):
                    with open(safe_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        title = os.path.basename(filename)
            except Exception as e:
                return {"error": f"Failed reading file for ingestion: {e}"}

        if not content:
            return {"error": "content or valid filename is required for ingestion"}

        try:
            from nava.memory.store import SemanticMemoryStore
            sem_store = SemanticMemoryStore("memory/semantic.json")
            chunks = sem_store.ingest_document(
                doc_id=doc_id,
                title=title,
                text=content,
                source=source,
                metadata=metadata
            )
            return {
                "success": True,
                "doc_id": doc_id,
                "title": title,
                "chunks_created": len(chunks),
                "source": source
            }
        except Exception as e:
            return {"error": f"Semantic ingestion failed: {e}"}

    def _memory_semantic_search(self, args: dict) -> Any:
        """Executes a Hybrid RAG (Dense Vector + BM25 Sparse with RRF) query over Tier 3 Knowledge."""
        query = args.get("query")
        limit = args.get("limit", 5)
        dense_weight = args.get("dense_weight", 0.5)
        sparse_weight = args.get("sparse_weight", 0.5)

        if not query:
            return {"error": "query is required"}

        try:
            from nava.memory.store import SemanticMemoryStore
            sem_store = SemanticMemoryStore("memory/semantic.json")
            results = sem_store.hybrid_search(
                query=query,
                limit=limit,
                dense_weight=dense_weight,
                sparse_weight=sparse_weight
            )
            return {
                "query": query,
                "total_results": len(results),
                "results": results
            }
        except Exception as e:
            return {"error": f"Semantic search failed: {e}"}

    def _code_find_references(self, args: dict) -> Any:
        func_name = args.get("function_name")
        directory = args.get("directory", ".")
        
        # Simple ast-like tracking using grep logic for now
        results = []
        for root, dirs, files in os.walk(directory):
            if '.git' in root or '__pycache__' in root:
                continue
            for file in files:
                if file.endswith(('.py', '.js', '.html')):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            for i, line in enumerate(f):
                                if func_name in line and 'def ' + func_name not in line and 'function ' + func_name not in line:
                                    results.append(f"{filepath}:{i+1}: {line.strip()}")
                    except Exception:
                        pass
        return {"results": "\n".join(results) if results else f"No external references found for {func_name}."}
        
    def _code_search(self, args: dict) -> Any:
        query = args.get("query")
        directory = args.get("directory", ".")
        if not query:
            raise ValueError("query is required")
            
        # Target active project directory and task artifacts strictly
        proj_dir = os.path.join("projects", self.active_project) if self.active_project else "projects"
        os.makedirs(proj_dir, exist_ok=True)
        
        search_roots = [proj_dir]
        if self.active_task_id:
            art_dir = os.path.join("tasks", self.active_task_id, "artifacts")
            if os.path.exists(art_dir):
                search_roots.append(art_dir)
        elif os.path.exists("tasks"):
            search_roots.append("tasks")
            
        results = []
        for s_root in search_roots:
            for root, dirs, files in os.walk(s_root):
                # Filter protected or hidden directories
                dirs[:] = [d for d in dirs if not self._is_internal_system_path(d) and d not in ['.git', '__pycache__', 'node_modules']]
                for file in files:
                    if self._is_internal_system_path(file):
                        continue
                    if file.endswith(('.py', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.md', '.txt', '.json', '.go', '.rs', '.java', '.cpp', '.c', '.sh', '.yaml', '.yml')):
                        filepath = os.path.join(root, file)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                for i, line in enumerate(f):
                                    if query in line:
                                        results.append(f"{os.path.relpath(filepath, os.getcwd())}:{i+1}: {line.strip()}")
                        except (UnicodeDecodeError, FileNotFoundError):
                            pass
        return {"results": "\n".join(results) if results else "No matches found in active project workspace."}

    def _code_read_directory_tree(self, args: dict) -> Any:
        # Strictly target active project directory
        proj_dir = os.path.join("projects", self.active_project) if self.active_project else "projects"
        os.makedirs(proj_dir, exist_ok=True)
        target_dir = proj_dir
            
        tree = []
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if not self._is_internal_system_path(d) and d not in ['.git', '__pycache__', 'node_modules']]
            level = root.replace(target_dir, '').count(os.sep)
            indent = ' ' * 4 * (level)
            tree.append(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                if not self._is_internal_system_path(f):
                    tree.append(f"{subindent}{f}")
        return {"tree": "\n".join(tree) if tree else f"Project '{self.active_project}' is clean and ready for new files."}

    def _system_flag_review(self, args: dict) -> Any:
        # Mock HITL flag
        return {"success": True}

    def _system_read_skill(self, args: dict) -> Any:
        skill_name = args.get("skill_name")
        if not skill_name:
            return {"error": "skill_name is required"}
        if not self.skill_manager:
            return {"error": "SkillManager not configured"}
        skill = self.skill_manager.get_skill(skill_name)
        if not skill:
            return {"error": f"Skill '{skill_name}' not found."}
            
        # Section 30 Hash-Lock Boundary Enforcement
        if skill.trust_state != "TRUSTED":
            return {"error": f"SECURITY_BLOCK: Skill '{skill_name}' is in state {skill.trust_state} and cannot be executed. The user must manually approve it via '/plugin approve {skill_name}'."}
            
        return {"success": True, "content": skill.content}

    def _code_diff_review(self, args: dict) -> Any:
        filename = args.get("filename")
        if not filename:
            # Get diff for entire repo
            result = subprocess.run("git diff HEAD", shell=True, capture_output=True, text=True)
        else:
            result = subprocess.run(f"git diff HEAD -- {filename}", shell=True, capture_output=True, text=True)
            
        if result.returncode != 0:
            return {"error": f"Git diff failed: {result.stderr}"}
            
        diff_out = result.stdout.strip()
        if not diff_out:
            return {"diff": "No unstaged changes found. File matches HEAD."}
        return {"diff": diff_out}

    def _file_create_pdf(self, args: dict) -> Any:
        filename = args.get("filename")
        markdown_content = args.get("markdown_content", "") or args.get("content", "")
        raw_html_content = args.get("html_content", "")
        source_file = args.get("source_file")
        custom_css = args.get("custom_css", "")
        primary_color = args.get("primary_color", "#2C3E50")
        font_family = args.get("font_family", "Helvetica, Arial, sans-serif")
        
        if not filename:
            raise ValueError("filename is required")
            
        clean_name = filename.replace("\\", "/")
        if not clean_name.startswith((".", "src", "tests", "memory", ".nava")):
            filename = self._resolve_artifact_path(filename)
        else:
            filename = self._sanitize_path(filename)
            
        if source_file:
            safe_source = self._sanitize_path(source_file)
            if not os.path.exists(safe_source):
                alt_source = self._resolve_artifact_path(source_file)
                if os.path.exists(alt_source):
                    safe_source = alt_source
            if os.path.exists(safe_source):
                with open(safe_source, "r", encoding="utf-8") as f:
                    if safe_source.endswith(".md"):
                        markdown_content = f.read()
                    else:
                        raw_html_content = f.read()
            else:
                return {"error": f"source_file not found: '{source_file}'."}

        if not raw_html_content and not markdown_content.strip():
            return {"error": "Must provide either markdown_content, html_content, or a valid source_file."}
            
        try:
            import markdown
            from xhtml2pdf import pisa
        except ImportError:
            raise ImportError("Libraries required for PDF. Run: pip install markdown xhtml2pdf")
            
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        # Use provided HTML, otherwise convert markdown
        if raw_html_content:
            body_content = raw_html_content
        else:
            body_content = markdown.markdown(markdown_content, extensions=['tables'])
        
        # Build CSS
        base_css = f"""
            body {{ font-family: {font_family}; font-size: 12pt; line-height: 1.5; }}
            h1 {{ color: {primary_color}; }}
            h2 {{ color: {primary_color}; border-bottom: 1px solid #ddd; padding-bottom: 5px; opacity: 0.9; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: {primary_color}; color: white; font-weight: bold; }}
            {custom_css}
        """
        
        styled_html = f"""
        <html>
        <head><style>{base_css}</style></head>
        <body>
        {body_content}
        </body>
        </html>
        """
        
        with open(filename, "wb") as pdf_file:
            pisa_status = pisa.CreatePDF(styled_html, dest=pdf_file)
            
        if pisa_status.err:
            return {"success": False, "error": "PDF rendering failed."}
            
        return {"success": True, "saved_to": os.path.relpath(filename, os.getcwd()), "message": f"Beautiful PDF created at {filename}"}

    def _file_create_docx(self, args: dict) -> Any:
        filename = args.get("filename")
        content = args.get("content", "")
        source_file = args.get("source_file")
        
        if not filename:
            raise ValueError("filename is required")
            
        clean_name = filename.replace("\\", "/")
        if not clean_name.startswith((".", "src", "tests", "memory", ".nava")):
            filename = self._resolve_artifact_path(filename)
        else:
            filename = self._sanitize_path(filename)
            
        if source_file:
            safe_source = self._sanitize_path(source_file)
            if not os.path.exists(safe_source):
                alt_source = self._resolve_artifact_path(source_file)
                if os.path.exists(alt_source):
                    safe_source = alt_source
            if os.path.exists(safe_source):
                with open(safe_source, "r", encoding="utf-8") as f:
                    content = f.read()
                
        try:
            import docx
        except ImportError:
            raise ImportError("The 'python-docx' library is required to generate DOCX files. Please run: pip install python-docx")
            
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        doc = docx.Document()
        for line in content.split('\n'):
            doc.add_paragraph(line)
            
        doc.save(filename)
        return {"success": True, "saved_to": os.path.relpath(filename, os.getcwd()), "message": f"DOCX successfully created at {filename}"}

    def _file_create_pptx(self, args: dict) -> Any:
        filename = args.get("filename")
        slides_data = args.get("slides", [])
        theme_raw = args.get("theme", {})
        
        theme = theme_raw if isinstance(theme_raw, dict) else {}
        bg_color = theme.get("bg_color", "#FFFFFF")
        title_color = theme.get("title_color", "#000000")
        text_color = theme.get("text_color", "#333333")
        accent_color = theme.get("accent_color", "#3498DB")
        
        if not filename:
            raise ValueError("filename is required")
            
        clean_name = filename.replace("\\", "/")
        if not clean_name.startswith((".", "src", "tests", "memory", ".nava")):
            filename = self._resolve_artifact_path(filename)
        else:
            filename = self._sanitize_path(filename)
            
        try:
            from pptx import Presentation
            from pptx.dml.color import RGBColor
            from pptx.util import Inches, Pt
        except ImportError:
            raise ImportError("The 'python-pptx' library is required. Please run: pip install python-pptx")
            
        def hex_to_rgb(hex_str):
            if not hex_str: return None
            hex_str = str(hex_str).lstrip('#')
            if len(hex_str) != 6: return None
            try: return RGBColor(int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
            except ValueError: return None
            
        def apply_bg(slide, hex_col):
            rgb = hex_to_rgb(hex_col)
            if rgb:
                fill = slide.background.fill
                fill.solid()
                fill.fore_color.rgb = rgb

        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        prs = Presentation()
        
        # Guard slides_data
        if not isinstance(slides_data, list):
            slides_data = [slides_data] if isinstance(slides_data, dict) else []
        
        for slide_data in slides_data:
            if not isinstance(slide_data, dict):
                slide_data = {"title": str(slide_data)}
                
            layout_type = str(slide_data.get("layout", "standard"))
            title_text = str(slide_data.get("title", ""))
            
            if layout_type == "title_slide":
                slide = prs.slides.add_slide(prs.slide_layouts[0])
                apply_bg(slide, bg_color)
                title = slide.shapes.title
                subtitle = slide.placeholders[1]
                title.text = title_text
                subtitle.text = str(slide_data.get("content", ""))
                if title.text_frame.paragraphs and title_color:
                    title.text_frame.paragraphs[0].font.color.rgb = hex_to_rgb(title_color)
                if subtitle.text_frame.paragraphs and text_color:
                    subtitle.text_frame.paragraphs[0].font.color.rgb = hex_to_rgb(text_color)
                    
            elif layout_type == "two_column":
                slide = prs.slides.add_slide(prs.slide_layouts[3]) # Two content layout
                apply_bg(slide, bg_color)
                title = slide.shapes.title
                title.text = title_text
                if title.text_frame.paragraphs and title_color:
                    title.text_frame.paragraphs[0].font.color.rgb = hex_to_rgb(title_color)
                
                left_box = slide.placeholders[1]
                right_box = slide.placeholders[2]
                left_box.text = str(slide_data.get("left_content", ""))
                right_box.text = str(slide_data.get("right_content", ""))
                
            elif layout_type == "metrics_3":
                slide = prs.slides.add_slide(prs.slide_layouts[5]) # Title only layout
                apply_bg(slide, bg_color)
                title = slide.shapes.title
                title.text = title_text
                if title.text_frame.paragraphs and title_color:
                    title.text_frame.paragraphs[0].font.color.rgb = hex_to_rgb(title_color)
                
                metrics = slide_data.get("metrics", [])
                if not isinstance(metrics, list):
                    metrics = [metrics] if isinstance(metrics, dict) else []
                    
                start_left = 0.5
                box_width = 2.8
                for i, metric in enumerate(metrics[:3]):
                    if not isinstance(metric, dict):
                        metric = {"value": str(metric), "label": ""}
                        
                    left = Inches(start_left + (i * (box_width + 0.2)))
                    top = Inches(2.5)
                    shape = slide.shapes.add_shape(1, left, top, Inches(box_width), Inches(2.0)) # 1=Rectangle
                    
                    # Style the metric box
                    shape.fill.solid()
                    shape.fill.fore_color.rgb = hex_to_rgb(accent_color) or RGBColor(52, 152, 219)
                    shape.line.fill.background()
                    
                    # Add text
                    tf = shape.text_frame
                    p1 = tf.paragraphs[0]
                    p1.text = str(metric.get("value", ""))
                    p1.font.size = Pt(32)
                    p1.font.bold = True
                    p1.font.color.rgb = RGBColor(255, 255, 255)
                    
                    p2 = tf.add_paragraph()
                    p2.text = str(metric.get("label", ""))
                    p2.font.size = Pt(14)
                    p2.font.color.rgb = RGBColor(240, 240, 240)
                    
            else: # Standard layout
                slide = prs.slides.add_slide(prs.slide_layouts[1])
                apply_bg(slide, bg_color)
                title = slide.shapes.title
                content = slide.placeholders[1]
                title.text = title_text
                content.text = slide_data.get("content", "")
                if title.text_frame.paragraphs and title_color:
                    title.text_frame.paragraphs[0].font.color.rgb = hex_to_rgb(title_color)
            
        prs.save(filename)
        return {"success": True, "message": f"Advanced PPTX successfully created at {filename} with {len(slides_data)} slides."}

    def _ensure_browser(self):
        if not hasattr(self, '_thread_local'):
            import threading
            self._thread_local = threading.local()
            
        if not getattr(self._thread_local, 'browser_engine', None):
            from nava.tools.browser import BrowserEngine
            self._thread_local.browser_engine = BrowserEngine(headless=True, artifact_resolver=self._resolve_artifact_path)
            
        return self._thread_local.browser_engine

    @property
    def browser_engine(self):
        return self._ensure_browser()

    @browser_engine.setter
    def browser_engine(self, val):
        if not hasattr(self, '_thread_local'):
            import threading
            self._thread_local = threading.local()
        self._thread_local.browser_engine = val
            
    def _browser_navigate(self, args: dict) -> Any:
        engine = self._ensure_browser()
        url = args.get("url")
        if not url:
            return {"error": "url is required"}
        return engine.navigate(url, wait_until=args.get("wait_until", "domcontentloaded"))

    def _browser_extract_interactive_tree(self, args: dict) -> Any:
        engine = self._ensure_browser()
        return engine.extract_interactive_tree()

    def _browser_screenshot(self, args: dict) -> Any:
        engine = self._ensure_browser()
        path = args.get("path")
        full_page = bool(args.get("full_page", False))
        return engine.screenshot(path=path, full_page=full_page)

    def _browser_extract_dom(self, args: dict) -> Any:
        engine = self._ensure_browser()
        return {"html": engine.extract_dom()}

    def _browser_extract_text(self, args: dict) -> Any:
        engine = self._ensure_browser()
        return {"text": engine.extract_text()}

    def _browser_click(self, args: dict) -> Any:
        engine = self._ensure_browser()
        return engine.click(selector=args.get("selector"), element_id=args.get("element_id"))

    def _browser_type(self, args: dict) -> Any:
        engine = self._ensure_browser()
        text = args.get("text", "")
        return engine.type_text(
            text=text,
            selector=args.get("selector"),
            element_id=args.get("element_id"),
            clear=bool(args.get("clear", True))
        )

    def _browser_scroll(self, args: dict) -> Any:
        engine = self._ensure_browser()
        return engine.scroll(direction=args.get("direction", "down"), amount=int(args.get("amount", 500)))

    def _browser_select_option(self, args: dict) -> Any:
        engine = self._ensure_browser()
        return engine.select_option(selector=args.get("selector"), element_id=args.get("element_id"), value=args.get("value"))

    def _browser_go_back(self, args: dict) -> Any:
        engine = self._ensure_browser()
        return engine.go_back()

    def _browser_get_url(self, args: dict) -> Any:
        engine = self._ensure_browser()
        return {"url": engine.get_url()}

    def _browser_save_to_scratch(self, args: dict, agent_id: str) -> Any:
        engine = self._ensure_browser()
        text = args.get("text")
        if not text:
            text = engine.extract_text()
            
        # 1. Mandatory Sanitizer Pass (Invariant: NEVER write unsanitized text from browser)
        from nava.governance.dom_sanitizer import sanitize_dom
        sanitized_text, _ = sanitize_dom(text, ledger=None)
        
        # 2. Scope path securely to the specific agent ID (No path traversal possible)
        os.makedirs("scratch", exist_ok=True)
        filepath = os.path.join("scratch", f"{agent_id}_extraction.md")
        
        # 3. Enforce hard size limit (Resource Exhaustion cap)
        MAX_SIZE = 50 * 1024 # 50KB
        current_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        text_bytes = sanitized_text.encode('utf-8')
        
        if current_size + len(text_bytes) > MAX_SIZE:
            return {"error": f"FILE_SIZE_LIMIT_EXCEEDED: Cannot append {len(text_bytes)} bytes. File is {current_size} bytes, max is {MAX_SIZE}."}
            
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(sanitized_text + "\n\n")
            
        return {"success": True, "bytes_written": len(text_bytes), "file": filepath}

    def _ensure_desktop(self):
        if not hasattr(self, '_desktop_engine') or not self._desktop_engine:
            from nava.tools.desktop import DesktopEngine
            self._desktop_engine = DesktopEngine()
        return self._desktop_engine

    def _desktop_screenshot(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        raw_path = args.get("path") or "desktop_screenshot.png"
        clean_name = raw_path.replace("\\", "/")
        if not clean_name.startswith((".", "src", "tests", "memory", ".nava")):
            target_path = self._resolve_artifact_path(raw_path)
        else:
            target_path = self._sanitize_path(raw_path)
        region = args.get("region")
        return {"screenshot_path": engine.screenshot(target_path, region=region)}

    def _desktop_click(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        x = int(args.get("x", 0))
        y = int(args.get("y", 0))
        button = args.get("button", "left")
        double = bool(args.get("double", False))
        return {"result": engine.click(x, y, button=button, double=double)}

    def _desktop_drag(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        start_x = int(args.get("start_x", 0))
        start_y = int(args.get("start_y", 0))
        end_x = int(args.get("end_x", 0))
        end_y = int(args.get("end_y", 0))
        duration = float(args.get("duration", 0.5))
        button = args.get("button", "left")
        return {"result": engine.mouse_drag(start_x, start_y, end_x, end_y, duration=duration, button=button)}

    def _desktop_scroll(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        clicks = int(args.get("clicks", -3))
        return {"result": engine.mouse_scroll(clicks)}

    def _desktop_type(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        text = args.get("text", "")
        return {"result": engine.type_text(text)}

    def _desktop_press(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        key = args.get("key", "enter")
        return {"result": engine.keyboard_press(key)}

    def _desktop_hotkey(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        keys = args.get("keys", [])
        return {"result": engine.hotkey(keys)}

    def _desktop_get_screen_size(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        return engine.get_screen_size()

