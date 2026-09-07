"""
tool_manifest.py — Centralized Catalog & Manifest for Built-in Tools & MCP Servers.
Decouples raw tool schemas, risk metadata, and server configurations from Orchestrator.
"""
from typing import List, Optional, Dict, Any
from nava.tools.registry import ToolDefinition
from nava.core.schemas import RiskTier

def get_default_tools() -> List[ToolDefinition]:
    """Returns the complete catalog of built-in and MCP tool definitions."""
    return [
        # 1. System & Skills
        ToolDefinition(
            name="system.read_skill", description="Reads the full instructional content of a skill.",
            input_schema={"skill_name": "string"}, output_schema={"success": "boolean", "content": "string"},
            permissions_required=["system.read_skill"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="system.flag_review", description="Flags a completed task for human review and skill promotion.",
            input_schema={"task_id": "string", "reason": "string"}, output_schema={"success": "boolean"},
            permissions_required=["system.flag_review"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="subagent.dispatch_batch", description="Programmatically dispatches a batch of micro-subagents concurrently across items (files, URLs, hypotheses) with isolated sandboxes and typed schema returns.",
            input_schema={"subagents": "array", "pattern": "string (optional: fanout_synthesize, adversarial_verify, generate_filter, tournament, loop_until_done, classify_act)", "concurrency_limit": "integer (optional)"}, output_schema={"pattern": "string", "total_tasks": "integer", "successful_tasks": "integer", "failed_tasks": "integer", "results": "array", "merkle_root": "string"},
            permissions_required=["subagent.spawn"], risk_level=RiskTier.MEDIUM, reversible=True
        ),
        
        # 2. Filesystem & Documents
        ToolDefinition(
            name="file.write", description="Writes content to a file. Single root files are saved as task deliverables; directory paths go to project codebase.",
            input_schema={"filename": "string", "content": "string"}, output_schema={"success": "boolean", "saved_to": "string"},
            permissions_required=["filesystem.write"], risk_level=RiskTier.MEDIUM, reversible=True
        ),
        ToolDefinition(
            name="file.read", description="Reads text content from a file in task artifacts, project codebase, or root.",
            input_schema={"filename": "string"}, output_schema={"content": "string", "filepath": "string"},
            permissions_required=["filesystem.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="file.delete", description="Deletes a file safely.",
            input_schema={"filename": "string"}, output_schema={"success": "boolean", "message": "string"},
            permissions_required=["filesystem.write"], risk_level=RiskTier.MEDIUM, reversible=False
        ),
        ToolDefinition(
            name="file.create_pdf", description="Generates a formatted PDF document with title, sections, tables, and branding.",
            input_schema={"filename": "string", "title": "string", "sections": "array"}, output_schema={"success": "boolean", "saved_to": "string"},
            permissions_required=["filesystem.write"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="file.create_docx", description="Generates a formatted Word DOCX document with headers, bullet points, and tables.",
            input_schema={"filename": "string", "title": "string", "sections": "array"}, output_schema={"success": "boolean", "saved_to": "string"},
            permissions_required=["filesystem.write"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="file.create_pptx", description="Generates a presentation slide deck PPTX with slide layouts, titles, and body bullet cards.",
            input_schema={"filename": "string", "title": "string", "slides": "array"}, output_schema={"success": "boolean", "saved_to": "string"},
            permissions_required=["filesystem.write"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="presentation.create_slidev", description="Compiles raw Slidev markdown markup or a .md file into a Gamma-style presentation (HTML, PDF, or PPTX).",
            input_schema={"source": "string", "output_path": "string", "format": "string (optional: html, pdf, pptx)", "theme": "string (optional)"}, output_schema={"success": "boolean", "saved_to": "string", "source_markdown": "string"},
            permissions_required=["document.compile", "filesystem.write"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="presentation.render_template", description="Renders a Gamma-style presentation slide deck ('dark_executive', 'modern_light', 'pitch_deck', 'technical_deep_dive') to interactive HTML and PPTX.",
            input_schema={"template_name": "string", "title": "string", "slides": "array", "output_path": "string", "author": "string (optional)", "theme": "object (optional)"}, output_schema={"success": "boolean", "saved_to": "string", "total_slides": "integer"},
            permissions_required=["document.compile", "filesystem.write"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="typst.compile_pdf", description="Compiles raw Typst markup code or a .typ source file into a publication-quality vector PDF.",
            input_schema={"source": "string", "output_pdf": "string", "template_vars": "object (optional)"}, output_schema={"success": "boolean", "saved_to": "string", "bytes_written": "integer"},
            permissions_required=["document.compile"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="typst.render_template", description="Renders an executive pre-designed document template ('executive_report', 'technical_spec', 'datasheet', 'research_paper') to PDF.",
            input_schema={"template_name": "string", "title": "string", "author": "string", "content_blocks": "array", "output_pdf": "string", "theme": "object (optional)"}, output_schema={"success": "boolean", "saved_to": "string"},
            permissions_required=["document.compile"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="doc.read_document", description="Reads text content and structural elements from PDF, DOCX, PPTX, MD, TXT, or Typst files.",
            input_schema={"file_path": "string"}, output_schema={"success": "boolean", "content": "string", "format": "string"},
            permissions_required=["document.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        
        # 3. Code, AST Indexing & Superpowers
        ToolDefinition(
            name="code.search", description="Searches code across project workspace files using regex or literal patterns.",
            input_schema={"query": "string"}, output_schema={"matches": "array", "total_matches": "integer"},
            permissions_required=["filesystem.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="code.read_directory_tree", description="Generates an ASCII file tree of the project codebase.",
            input_schema={}, output_schema={"tree": "string", "total_files": "integer"},
            permissions_required=["filesystem.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="code.replace_content", description="Performs surgical search-and-replace in a file with exact string matching.",
            input_schema={"filename": "string", "target_content": "string", "replacement_content": "string"}, output_schema={"success": "boolean"},
            permissions_required=["filesystem.write"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="context7.get_symbol_graph", description="Extracts AST symbol graph (classes, methods, functions, imports) across project files.",
            input_schema={"filename": "string (optional)", "directory": "string (optional)"}, output_schema={"symbol_graph": "array", "total_symbols_extracted": "integer"},
            permissions_required=["ast.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="context7.slice_context", description="Extracts only target symbol definition and imports, reducing token footprint up to 80%.",
            input_schema={"filename": "string", "symbol_name": "string"}, output_schema={"symbol": "string", "snippet": "string"},
            permissions_required=["ast.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="superpowers.ast_search", description="Syntax-aware AST search for classes, functions, or patterns.",
            input_schema={"pattern": "string", "filename": "string (optional)"}, output_schema={"matches": "array", "total_found": "integer"},
            permissions_required=["ast.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="superpowers.ast_replace", description="Executes AST-verified replacement of target symbols or code blocks.",
            input_schema={"filename": "string", "target_symbol": "string", "replacement_code": "string"}, output_schema={"success": "boolean"},
            permissions_required=["ast.write"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="superpowers.compiler_autofix", description="Runs syntax compilation diagnostics and attempts automated self-healing.",
            input_schema={"filename": "string"}, output_schema={"status": "string", "diagnostics": "array"},
            permissions_required=["ast.write"], risk_level=RiskTier.LOW, reversible=True
        ),
        
        # 4. Git & Terminal
        ToolDefinition(
            name="git.status", description="Returns git branch, staged, modified, and untracked files.",
            input_schema={}, output_schema={"branch": "string", "status_output": "string"},
            permissions_required=["git.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="git.diff", description="Returns unified git diff of working directory or staged changes.",
            input_schema={"staged": "boolean (optional)"}, output_schema={"diff": "string", "lines_count": "integer"},
            permissions_required=["git.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="git.branch", description="Creates or inspects git feature branches.",
            input_schema={"branch_name": "string (optional)", "create": "boolean (optional)"}, output_schema={"branch": "string", "status": "string"},
            permissions_required=["git.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="git.commit", description="Stages and commits changes in active project.",
            input_schema={"message": "string (optional)"}, output_schema={"success": "boolean"},
            permissions_required=["git.write"], risk_level=RiskTier.MEDIUM, reversible=True
        ),
        ToolDefinition(
            name="terminal.execute", description="Executes command inside terminal sandbox capturing exit code and output.",
            input_schema={"command": "string", "timeout": "integer (optional)", "cwd": "string (optional)"}, output_schema={"success": "boolean", "returncode": "integer", "stdout": "string", "stderr": "string"},
            permissions_required=["terminal.execute"], risk_level=RiskTier.HIGH, reversible=False
        ),
        ToolDefinition(
            name="terminal.exec_command", description="Executes a shell command with strict timeout, directory confinement, and secret redaction.",
            input_schema={"command": "string", "timeout": "integer (optional)", "cwd": "string (optional)"}, output_schema={"success": "boolean", "returncode": "integer", "stdout": "string", "stderr": "string", "duration_seconds": "number"},
            permissions_required=["terminal.execute"], risk_level=RiskTier.HIGH, reversible=False
        ),
        ToolDefinition(
            name="terminal.run_tests", description="Runs automated test suites (pytest, unittest, npm, cargo, go) and returns structured pass/fail metrics.",
            input_schema={"test_command": "string (optional)", "framework": "string (optional)", "cwd": "string (optional)"}, output_schema={"success": "boolean", "verdict": "string", "passed": "integer", "failed": "integer", "errors": "integer"},
            permissions_required=["test.run"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="terminal.inspect_environment", description="Audits installed compilers, runtimes, OS details, and CLI tools with secret redaction.",
            input_schema={}, output_schema={"os": "string", "installed_toolchains": "object", "docker_sandbox_active": "boolean"},
            permissions_required=["system.inspect"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="docker.create_sandbox", description="Spawns an isolated ephemeral Docker container with memory/CPU limits.",
            input_schema={"image": "string (optional)", "memory_limit": "string (optional)", "cpu_limit": "string (optional)", "network_enabled": "boolean (optional)"}, output_schema={"success": "boolean", "sandbox_id": "string", "is_simulated": "boolean"},
            permissions_required=["docker.sandbox"], risk_level=RiskTier.HIGH, reversible=False
        ),
        ToolDefinition(
            name="docker.exec_in_sandbox", description="Executes command inside an isolated Docker sandbox container.",
            input_schema={"sandbox_id": "string", "command": "string", "timeout": "integer (optional)"}, output_schema={"success": "boolean", "returncode": "integer", "stdout": "string", "stderr": "string"},
            permissions_required=["docker.sandbox"], risk_level=RiskTier.HIGH, reversible=False
        ),
        ToolDefinition(
            name="docker.destroy_sandbox", description="Forcefully removes and purges an ephemeral Docker sandbox container.",
            input_schema={"sandbox_id": "string"}, output_schema={"success": "boolean", "status": "string"},
            permissions_required=["docker.sandbox"], risk_level=RiskTier.MEDIUM, reversible=True
        ),
        ToolDefinition(
            name="test.run", description="Runs automated test command.",
            input_schema={"command": "string"}, output_schema={"returncode": "integer", "stdout": "string"},
            permissions_required=["test.run"], risk_level=RiskTier.MEDIUM, reversible=False
        ),
        
        # 5. Research & Intelligence MCP Suite
        ToolDefinition(
            name="search.web", description="Performs multi-source web search returning text excerpts.",
            input_schema={"query": "string"}, output_schema={"query": "string", "raw_search_extract": "string"},
            permissions_required=["search.web"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="fetch.get_markdown", description="Fetches web URLs and converts raw HTML into token-dense, clean Markdown, stripping ads and navbars.",
            input_schema={"url": "string", "max_chars": "integer (optional)"}, output_schema={"url": "string", "markdown": "string"},
            permissions_required=["research.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="fetch.get_raw_html", description="Fetches raw unprocessed HTML from web URLs for DOM inspection.",
            input_schema={"url": "string", "max_chars": "integer (optional)"}, output_schema={"url": "string", "raw_html": "string"},
            permissions_required=["research.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="fetch.get_headers", description="Inspects HTTP headers, status code, and server metadata.",
            input_schema={"url": "string"}, output_schema={"url": "string", "status_code": "integer", "headers": "object"},
            permissions_required=["research.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="brave.search_web", description="Executes structured web search queries returning ranked titles, URLs, and snippets.",
            input_schema={"query": "string", "count": "integer (optional)"}, output_schema={"query": "string", "results": "array"},
            permissions_required=["research.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="brave.search_news", description="Searches recent news articles and announcements with metadata.",
            input_schema={"query": "string", "count": "integer (optional)"}, output_schema={"query": "string", "results": "array"},
            permissions_required=["research.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="arxiv.search_papers", description="Queries official ArXiv API for academic papers, abstracts, authors, and PDF links.",
            input_schema={"query": "string", "max_results": "integer (optional)"}, output_schema={"query": "string", "papers": "array"},
            permissions_required=["research.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="arxiv.get_paper_summary", description="Retrieves abstract and citation details for an ArXiv ID.",
            input_schema={"arxiv_id": "string"}, output_schema={"query": "string", "papers": "array"},
            permissions_required=["research.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        
        # 6. Database & Tabular Analytics Suite (DataAgent)
        ToolDefinition(
            name="sqlite.read_query", description="Executes SELECT queries against a SQLite database with row limits.",
            input_schema={"db_path": "string", "query": "string", "max_rows": "integer (optional)"}, output_schema={"columns": "array", "rows": "array"},
            permissions_required=["database.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="sqlite.write_query", description="Executes CREATE, INSERT, UPDATE, DELETE queries on a SQLite database.",
            input_schema={"db_path": "string", "query": "string"}, output_schema={"rows_affected": "integer"},
            permissions_required=["database.write"], risk_level=RiskTier.MEDIUM, reversible=True
        ),
        ToolDefinition(
            name="sqlite.list_tables", description="Lists all tables and views in a SQLite database with row counts.",
            input_schema={"db_path": "string"}, output_schema={"tables": "array"},
            permissions_required=["database.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="sqlite.describe_tables", description="Retrieves column definitions, data types, primary keys, and schema definitions.",
            input_schema={"db_path": "string", "table_name": "string (optional)"}, output_schema={"schemas": "object"},
            permissions_required=["database.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="data.sql_query_csv", description="Loads a CSV into an in-memory SQLite table and executes full SQL queries on-the-fly.",
            input_schema={"csv_path": "string", "query": "string", "table_name": "string (optional)", "max_rows": "integer (optional)"}, output_schema={"columns": "array", "rows": "array"},
            permissions_required=["data.analyze"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="data.profile_dataset", description="Profiles a tabular CSV dataset: row count, data types, nulls, distributions, and statistics.",
            input_schema={"csv_path": "string"}, output_schema={"total_rows": "integer", "columns": "array", "profiles": "object"},
            permissions_required=["data.analyze"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="data.aggregate", description="Performs structured GROUP BY aggregations on tabular CSV data (SUM, AVG, MIN, MAX, COUNT).",
            input_schema={"csv_path": "string", "group_by": "string", "agg_column": "string", "agg_func": "string (optional)"}, output_schema={"columns": "array", "rows": "array"},
            permissions_required=["data.analyze"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="data.correlation_matrix", description="Computes pairwise Pearson correlation coefficients across all numeric columns in a dataset.",
            input_schema={"csv_path": "string"}, output_schema={"numeric_columns": "array", "correlation_matrix": "object"},
            permissions_required=["data.analyze"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="data.detect_anomalies", description="Identifies statistical anomalies and outliers in a numeric column using Z-Score analysis.",
            input_schema={"csv_path": "string", "column": "string", "threshold": "number (optional, default 2.5)"}, output_schema={"anomalies_found": "integer", "anomalies": "array"},
            permissions_required=["data.analyze"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="data.pivot_table", description="Creates a cross-tabulated 2D pivot table from tabular data.",
            input_schema={"csv_path": "string", "index_col": "string", "pivot_col": "string", "value_col": "string", "agg_func": "string (optional)"}, output_schema={"columns": "array", "rows": "array"},
            permissions_required=["data.analyze"], risk_level=RiskTier.LOW, reversible=True
        ),

        # 7. Browser & Computer Automation (BrowserAgent & ComputerAgent)
        ToolDefinition(
            name="browser.navigate", description="Navigates the browser to a URL with anti-bot headers and wait-until strategies.",
            input_schema={"url": "string", "wait_until": "string (optional)"}, output_schema={"success": "boolean", "url": "string", "title": "string"},
            permissions_required=["browser.navigate"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="browser.extract_interactive_tree", description="Extracts numbered accessible interactive elements (buttons, inputs, links) with [#ID] for 95% token savings.",
            input_schema={}, output_schema={"success": "boolean", "total_elements": "integer", "interactive_tree": "string"},
            permissions_required=["browser.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="browser.screenshot", description="Captures high-res visual viewport or full-page screenshot and saves to task deliverables.",
            input_schema={"path": "string (optional)", "full_page": "boolean (optional)"}, output_schema={"success": "boolean", "saved_to": "string"},
            permissions_required=["browser.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="browser.click", description="Clicks an interactive element by element_id (e.g. element_id=1) or CSS selector.",
            input_schema={"element_id": "integer (optional)", "selector": "string (optional)"}, output_schema={"success": "boolean", "clicked": "string"},
            permissions_required=["browser.click"], risk_level=RiskTier.MEDIUM, reversible=False
        ),
        ToolDefinition(
            name="browser.type", description="Types text into an input field by element_id or CSS selector with sensitive pattern masking.",
            input_schema={"text": "string", "element_id": "integer (optional)", "selector": "string (optional)", "clear": "boolean (optional)"}, output_schema={"success": "boolean", "typed": "string"},
            permissions_required=["browser.type"], risk_level=RiskTier.MEDIUM, reversible=False
        ),
        ToolDefinition(
            name="browser.scroll", description="Scrolls viewport down or up smoothly.",
            input_schema={"direction": "string (optional, default 'down')", "amount": "integer (optional, default 500)"}, output_schema={"success": "boolean"},
            permissions_required=["browser.scroll"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="browser.select_option", description="Selects an option value in a dropdown select element by element_id or CSS selector.",
            input_schema={"value": "string", "element_id": "integer (optional)", "selector": "string (optional)"}, output_schema={"success": "boolean", "selected_value": "string"},
            permissions_required=["browser.type"], risk_level=RiskTier.MEDIUM, reversible=False
        ),
        ToolDefinition(
            name="browser.extract_text", description="Extracts structured readable text from the current browser DOM, stripping noise elements.",
            input_schema={}, output_schema={"text": "string"},
            permissions_required=["browser.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="browser.extract_dom", description="Returns raw DOM HTML of the active page for structural inspection.",
            input_schema={}, output_schema={"dom": "string"},
            permissions_required=["browser.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="browser.go_back", description="Navigates back to the previous page in history.",
            input_schema={}, output_schema={"success": "boolean", "url": "string"},
            permissions_required=["browser.navigate"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="desktop.screenshot", description="Captures full screenshot of desktop display and saves to task artifacts.",
            input_schema={"path": "string (optional)"}, output_schema={"success": "boolean", "saved_to": "string"},
            permissions_required=["desktop.read"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="desktop.click", description="Simulates mouse click at (x, y) screen coordinates with optional clicks/button.",
            input_schema={"x": "integer", "y": "integer", "button": "string (optional)", "clicks": "integer (optional)"}, output_schema={"success": "boolean"},
            permissions_required=["desktop.click"], risk_level=RiskTier.HIGH, reversible=False
        ),
        ToolDefinition(
            name="desktop.type", description="Types text into the active focused desktop window.",
            input_schema={"text": "string", "interval": "number (optional)"}, output_schema={"success": "boolean"},
            permissions_required=["desktop.type"], risk_level=RiskTier.HIGH, reversible=False
        ),
        ToolDefinition(
            name="desktop.hotkey", description="Triggers a keyboard shortcut combination (e.g. ['ctrl', 'c'], ['alt', 'tab']).",
            input_schema={"keys": "array"}, output_schema={"success": "boolean"},
            permissions_required=["desktop.type"], risk_level=RiskTier.HIGH, reversible=False
        ),
        ToolDefinition(
            name="desktop.get_screen_size", description="Returns screen resolution width and height.",
            input_schema={}, output_schema={"width": "integer", "height": "integer"},
            permissions_required=["desktop.read"], risk_level=RiskTier.LOW, reversible=True
        ),

        # 8. Memory & Knowledge
        ToolDefinition(
            name="memory.semantic_ingest", description="Chunks and indexes document into Tier 3 Knowledge base.",
            input_schema={"content": "string", "source_uri": "string"}, output_schema={"success": "boolean", "chunks_indexed": "integer"},
            permissions_required=["memory.semantic"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="memory.semantic_search", description="Hybrid dense vector and BM25 search over Tier 3 Knowledge.",
            input_schema={"query": "string", "limit": "integer (optional)"}, output_schema={"query": "string", "results": "array"},
            permissions_required=["memory.semantic"], risk_level=RiskTier.LOW, reversible=True
        ),
        
        # 9. Deep Reasoning & Audit MCP Suite (Reviewer & Verifier)
        ToolDefinition(
            name="sequential_thinking.step", description="Executes a dynamic multi-branch reasoning step, testing hypotheses and revising thoughts before approvals.",
            input_schema={"thought": "string", "thought_number": "integer", "total_thoughts": "integer", "next_thought_needed": "boolean (optional)", "is_revision": "boolean (optional)", "revises_thought": "integer (optional)", "branch_from_thought": "integer (optional)", "branch_id": "string (optional)", "confidence_score": "number (optional)"}, output_schema={"success": "boolean", "summary": "string"},
            permissions_required=["reasoning.sequential"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="audit.verify_invariants", description="Performs deterministic verification of NAVA's 21 System Invariants (Merkle ledger integrity, scope alignment, budget bounds).",
            input_schema={"task_id": "string (optional)", "check_scopes": "object (optional)", "check_ledger": "boolean (optional)"}, output_schema={"success": "boolean", "invariants_checked": "integer", "violations": "array"},
            permissions_required=["audit.verify"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="audit.security_scan", description="Performs static AST vulnerability scanning on Python/JS/script artifacts for code injection, hardcoded secrets, and prompt injection.",
            input_schema={"filename": "string"}, output_schema={"success": "boolean", "is_clean": "boolean", "total_findings": "integer", "findings": "array", "verdict": "string"},
            permissions_required=["audit.security"], risk_level=RiskTier.LOW, reversible=True
        ),
        ToolDefinition(
            name="audit.verify_grounding", description="Reconciles numeric figures and factual claims in reports (.md, .pdf, .txt) against source datasets (.csv, .json, .sqlite) to eliminate hallucinations.",
            input_schema={"report_path": "string", "data_source_path": "string"}, output_schema={"success": "boolean", "grounding_score": "number", "verified_evidence": "array", "verdict": "string"},
            permissions_required=["audit.verify"], risk_level=RiskTier.LOW, reversible=True
        ),
        
        # 10. Mock External
        ToolDefinition(
            name="mock.send_wire_transfer", description="Sends wire transfer (HITL mock).",
            input_schema={"amount": "number", "recipient": "string"}, output_schema={"success": "boolean"},
            permissions_required=["mock.send_wire_transfer"], risk_level=RiskTier.CRITICAL, reversible=False
        ),
        ToolDefinition(
            name="mock.notify_admin", description="Sends mock notification to admin.",
            input_schema={"message": "string"}, output_schema={"success": "boolean"},
            permissions_required=["mock.notify_admin"], risk_level=RiskTier.LOW, reversible=True
        )
    ]

def register_default_mcp_servers(mcp_manager, mcp_configs: Optional[Dict[str, dict]] = None) -> None:
    """Registers standard ecosystem MCP server configurations with MCPClientManager."""
    configs = mcp_configs or {}
    servers = [
        {
            "name": "context7",
            "command": "npx",
            "args": ["-y", "@context7/mcp-server@latest"],
            "custom_tools": [
                {"name": "context7.get_symbol_graph", "description": "Extracts AST symbol graph across project files.", "permissions_required": ["ast.read"], "risk_level": "LOW", "reversible": True},
                {"name": "context7.slice_context", "description": "Extracts target symbol definition reducing token footprint.", "permissions_required": ["ast.read"], "risk_level": "LOW", "reversible": True}
            ]
        },
        {
            "name": "superpowers",
            "command": "uvx",
            "args": ["mcp-superpowers-code@latest"],
            "custom_tools": [
                {"name": "superpowers.ast_search", "description": "Syntax-aware AST search.", "permissions_required": ["ast.read"], "risk_level": "LOW", "reversible": True},
                {"name": "superpowers.ast_replace", "description": "AST-verified code replacement.", "permissions_required": ["ast.write"], "risk_level": "LOW", "reversible": True},
                {"name": "superpowers.compiler_autofix", "description": "Compiler diagnostics & self-healing.", "permissions_required": ["ast.write"], "risk_level": "LOW", "reversible": True}
            ]
        },
        {
            "name": "git",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-git@latest"],
            "custom_tools": [
                {"name": "git.status", "description": "Returns git branch and file status.", "permissions_required": ["git.read"], "risk_level": "LOW", "reversible": True},
                {"name": "git.diff", "description": "Returns unified git diff.", "permissions_required": ["git.read"], "risk_level": "LOW", "reversible": True},
                {"name": "git.branch", "description": "Branch inspection and creation.", "permissions_required": ["git.read"], "risk_level": "LOW", "reversible": True},
                {"name": "git.commit", "description": "Commit project changes.", "permissions_required": ["git.write"], "risk_level": "MEDIUM", "reversible": True}
            ]
        },
        {
            "name": "fetch",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-fetch@latest"],
            "custom_tools": [
                {"name": "fetch.get_markdown", "description": "Fetches web URLs to token-dense clean Markdown.", "permissions_required": ["research.read"], "risk_level": "LOW", "reversible": True},
                {"name": "fetch.get_raw_html", "description": "Fetches raw HTML for DOM inspection.", "permissions_required": ["research.read"], "risk_level": "LOW", "reversible": True},
                {"name": "fetch.get_headers", "description": "Inspects HTTP headers and status codes.", "permissions_required": ["research.read"], "risk_level": "LOW", "reversible": True}
            ]
        },
        {
            "name": "brave-search",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search@latest"],
            "custom_tools": [
                {"name": "brave.search_web", "description": "Structured web search queries.", "permissions_required": ["research.read"], "risk_level": "LOW", "reversible": True},
                {"name": "brave.search_news", "description": "Searches recent news articles.", "permissions_required": ["research.read"], "risk_level": "LOW", "reversible": True}
            ]
        },
        {
            "name": "arxiv",
            "command": "uvx",
            "args": ["mcp-server-arxiv@latest"],
            "custom_tools": [
                {"name": "arxiv.search_papers", "description": "Queries official ArXiv API for papers and PDF links.", "permissions_required": ["research.read"], "risk_level": "LOW", "reversible": True},
                {"name": "arxiv.get_paper_summary", "description": "Retrieves abstract for ArXiv ID.", "permissions_required": ["research.read"], "risk_level": "LOW", "reversible": True}
            ]
        },
        {
            "name": "sqlite",
            "command": "uvx",
            "args": ["mcp-server-sqlite@latest"],
            "custom_tools": [
                {"name": "sqlite.read_query", "description": "Executes SELECT queries against a SQLite database with row limits.", "permissions_required": ["database.read"], "risk_level": "LOW", "reversible": True},
                {"name": "sqlite.write_query", "description": "Executes CREATE, INSERT, UPDATE, DELETE queries on a SQLite database.", "permissions_required": ["database.write"], "risk_level": "MEDIUM", "reversible": True},
                {"name": "sqlite.list_tables", "description": "Lists all tables and views in a SQLite database with row counts.", "permissions_required": ["database.read"], "risk_level": "LOW", "reversible": True},
                {"name": "sqlite.describe_tables", "description": "Retrieves column definitions, data types, primary keys, and schema definitions.", "permissions_required": ["database.read"], "risk_level": "LOW", "reversible": True}
            ]
        },
        {
            "name": "typst",
            "command": "uvx",
            "args": ["typst-mcp-server@latest"],
            "custom_tools": [
                {"name": "typst.compile_pdf", "description": "Compiles raw Typst markup into publication-grade vector PDF.", "permissions_required": ["document.compile"], "risk_level": "LOW", "reversible": True},
                {"name": "typst.render_template", "description": "Renders an executive report using pre-compiled Typst templates.", "permissions_required": ["document.compile"], "risk_level": "LOW", "reversible": True}
            ]
        },
        {
            "name": "sequential-thinking",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-sequential-thinking@latest"],
            "custom_tools": [
                {"name": "sequential_thinking.step", "description": "Executes dynamic multi-branch hypothesis reasoning step.", "permissions_required": ["reasoning.sequential"], "risk_level": "LOW", "reversible": True}
            ]
        },
        {
            "name": "audit-scanner",
            "command": "uvx",
            "args": ["nava-audit-mcp@latest"],
            "custom_tools": [
                {"name": "audit.verify_invariants", "description": "Deterministic verification of NAVA's 21 System Invariants.", "permissions_required": ["audit.verify"], "risk_level": "LOW", "reversible": True},
                {"name": "audit.security_scan", "description": "Performs static AST vulnerability scanning on code files.", "permissions_required": ["audit.security"], "risk_level": "LOW", "reversible": True},
                {"name": "audit.verify_grounding", "description": "Reconciles numeric figures in reports against source datasets.", "permissions_required": ["audit.verify"], "risk_level": "LOW", "reversible": True}
            ]
        },
        {
            "name": "docker-sandbox",
            "command": "uvx",
            "args": ["docker-sandbox-mcp@latest"],
            "custom_tools": [
                {"name": "docker.create_sandbox", "description": "Spawns an isolated ephemeral Docker container with memory/CPU limits.", "permissions_required": ["docker.sandbox"], "risk_level": "HIGH", "reversible": False},
                {"name": "docker.exec_in_sandbox", "description": "Executes command inside an isolated Docker sandbox container.", "permissions_required": ["docker.sandbox"], "risk_level": "HIGH", "reversible": False},
                {"name": "docker.destroy_sandbox", "description": "Forcefully removes and purges an ephemeral Docker sandbox container.", "permissions_required": ["docker.sandbox"], "risk_level": "MEDIUM", "reversible": True}
            ]
        },
        {
            "name": "playwright-browser",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-puppeteer@latest"],
            "custom_tools": [
                {"name": "browser.navigate", "description": "Navigates browser to URL.", "permissions_required": ["browser.navigate"], "risk_level": "LOW", "reversible": True},
                {"name": "browser.extract_interactive_tree", "description": "Extracts numbered accessible interactive elements for token savings.", "permissions_required": ["browser.read"], "risk_level": "LOW", "reversible": True},
                {"name": "browser.screenshot", "description": "Captures viewport/full-page screenshot.", "permissions_required": ["browser.read"], "risk_level": "LOW", "reversible": True},
                {"name": "browser.click", "description": "Clicks element by ID or selector.", "permissions_required": ["browser.click"], "risk_level": "MEDIUM", "reversible": False},
                {"name": "browser.type", "description": "Types text into input field.", "permissions_required": ["browser.type"], "risk_level": "MEDIUM", "reversible": False},
                {"name": "browser.scroll", "description": "Scrolls page viewport.", "permissions_required": ["browser.scroll"], "risk_level": "LOW", "reversible": True}
            ]
        },
        {
            "name": "desktop-automation",
            "command": "uvx",
            "args": ["desktop-automation-mcp@latest"],
            "custom_tools": [
                {"name": "desktop.get_screen_size", "description": "Returns primary screen resolution.", "permissions_required": ["desktop.read"], "risk_level": "LOW", "reversible": True},
                {"name": "desktop.screenshot", "description": "Captures full desktop screenshot to task artifacts.", "permissions_required": ["desktop.read"], "risk_level": "LOW", "reversible": True},
                {"name": "desktop.click", "description": "Simulates mouse click at coordinate (x, y).", "permissions_required": ["desktop.click"], "risk_level": "HIGH", "reversible": False},
                {"name": "desktop.type", "description": "Types text into active window.", "permissions_required": ["desktop.type"], "risk_level": "HIGH", "reversible": False},
                {"name": "desktop.hotkey", "description": "Triggers keyboard shortcut combination.", "permissions_required": ["desktop.type"], "risk_level": "HIGH", "reversible": False}
            ]
        },
        {
            "name": "gmail",
            "command": "uvx",
            "args": ["gmail-mcp-server@latest"],
            "custom_tools": [
                {"name": "gmail.search", "description": "Searches Gmail messages matching query.", "permissions_required": ["gmail.read"], "risk_level": "LOW", "reversible": True},
                {"name": "gmail.read", "description": "Reads full content of Gmail message by ID.", "permissions_required": ["gmail.read"], "risk_level": "LOW", "reversible": True}
            ]
        },
        {
            "name": "github",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github@latest"],
            "custom_tools": [
                {"name": "github.search_repositories", "description": "Searches GitHub repositories.", "permissions_required": ["github.read"], "risk_level": "LOW", "reversible": True},
                {"name": "github.create_issue", "description": "Creates an issue in a GitHub repository.", "permissions_required": ["github.write"], "risk_level": "MEDIUM", "reversible": False}
            ]
        }
    ]
    for s in servers:
        srv_name = s["name"]
        srv_cfg = configs.get(srv_name, {})
        is_enabled = srv_cfg.get("enabled", True) if isinstance(srv_cfg, dict) else True
        if is_enabled:
            mcp_manager.register_server(
                name=srv_name,
                command=s["command"],
                args=s["args"],
                custom_tools=s["custom_tools"],
                enabled=True
            )

get_builtin_tools = get_default_tools
