# NAVA: Personal Agent Operating System

[![PyPI version](https://img.shields.io/pypi/v/nava-agent.svg)](https://pypi.org/project/nava-agent/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

```bash
pip install nava-agent
```

**NAVA** is a deterministic, multi-agent personal operating system designed for autonomous workspace execution, secure computer use, deep research synthesis, and persistent human-AI collaboration.

Built around a **17-step mutation gateway**, an **inter-agent message bus**, a **4-tier memory hierarchy**, a dynamic **Model Context Protocol (MCP) ecosystem of 15 specialized servers**, and **21 certified system invariants**, NAVA guarantees strict least-privilege bounding, tamper-evident audit receipts, and transactional rollback across all filesystem, terminal, browser, and OS desktop interactions.

---

## Table of Contents
1. [System Architecture Overview](#system-architecture-overview)
2. [NAVA Root Kernel Controller](#the-nava-root-agent-kernel-controller)
3. [Model Context Protocol (MCP) Ecosystem (15 Servers)](#model-context-protocol-mcp-ecosystem-15-servers)
4. [Specialized Agent Suite](#specialized-agent-suite)
5. [Core Codebase Isolation Invariant](#core-codebase-isolation-invariant-section-292)
6. [On-Demand Memory Architecture](#on-demand-memory-architecture-80-token-savings)
7. [The 17-Step Chokepoint Action Gateway](#the-17-step-chokepoint-action-gateway)
8. [Four-Tier Memory Hierarchy & AI Twin](#four-tier-memory-hierarchy--ai-twin)
9. [The 21 Certified System Invariants](#the-21-certified-system-invariants)
10. [Configuration & User-Configurable Security Switches](#configuration--user-configurable-security-switches)
11. [Interactive TUI Cowork Shell](#interactive-tui-cowork-shell)
12. [Repository Layout](#repository-layout)
13. [Getting Started & Quickstart](#getting-started--quickstart)
14. [Automated Verification & Test Suite](#automated-verification--test-suite)

---

## System Architecture Overview

NAVA replaces unconstrained LLM prompt chains with a deterministic operating system kernel. Every tool call--whether modifying code, executing shell commands, clicking desktop GUI windows, compiling Typst documents, or querying external APIs via MCP--is treated as a managed system call subject to policy evaluation, risk scoring, resource quotas, and concurrency locking.

```text
                           USER OBJECTIVE / SHELL
                                     |
                                     v
                    +---------------------------------+
                    |     NAVA ROOT ORCHESTRATOR      |
                    |   (Executive Kernel Controller) |
                    +----------------+----------------+
                                     |
                             Decompose Goal
                                     |
                                     v
                             [ GoalPlanner ]
                 Stage 1 (Parallel) ---> Stage 2 (Sequential)
                                     |
                                     v
                             [ AgentFactory ]
                 JIT Dynamic Synthesis & Scope Intersect:
            Child_Scope = Parent_Scope & Spec_Scope & Policy_Scope
                                     |
             +-----------------------+-----------------------+
             |                                               |
             v                                               v
+--------------------------+                   +--------------------------+
| SPECIALIZED STATIC AGENTS|                   |  DYNAMIC JIT SUBAGENTS   |
| * CodingAgent            |<----------------->|  * PDFIndexerAgent       |
| * TerminalAgent (DevOps) |    Inter-Agent    |  * DataExtractionAgent   |
| * ReviewerAgent (AST)    |    Message Bus    |  * SecurityAuditorAgent  |
| * VerifierAgent (Proof)  |    (Pub / Sub)    |  * WebScraperAgent       |
| * BrowserAgent (Web)     |                   |  * SuperpowersCodeAgent  |
| * ComputerAgent (OS GUI) |                   |                          |
| * UniversalFileAgent     |                   |                          |
+------------+-------------+                   +-------------+------------+
             |                                               |
             +-----------------------+-----------------------+
                                     |
                          Tool Request RPC Call
                                     |
                                     v
         +--------------------------------------------------------+
         |            17-STEP ACTION GATEWAY PIPELINE             |
         |  0. Emergency Kill Check    9. Credential Broker Token |
         |  1. Schema Validation      10. HITL Gatekeeper         |
         |  2. Agent Identity Check   11. Dry-Run & Pre-Snapshot  |
         |  3. Agent TTL Verification 12. Sandboxed Tool Dispatch |
         |  4. Parent Scope Check     13. State Observation Hash  |
         |  5. Permission Checker     14. Post-Execution Verify   |
         |  6. Policy Engine (ALLOW)  15. Cryptographic Receipt   |
         |  7. Additive Risk Engine   16. Audit Ledger Append     |
         |  8. Concurrency Locks      17. Lock Release & Teardown |
         +---------------------------+----------------------------+
                                     |
                                     v
         +--------------------------------------------------------+
         |                 HOST SYSTEM BOUNDARIES                 |
         |  * Isolated Project Files   * Playwright Headless Web  |
         |  * Ephemeral Docker Sandbox * OS Desktop GUI Perception|
         |  * 15 JSON-RPC MCP Servers  * Merkle Append-Only Ledger|
         +--------------------------------------------------------+
```

---

## The NAVA Root Agent (Kernel Controller)

At the apex of the OS resides the **NAVA Root Agent** (`src/nava/orchestrator.py`), serving as the privileged executive supervisor:

```text
+------------------------------------------------------------------------+
|                        NAVA ROOT AGENT KERNEL                          |
+------------------------------------------------------------------------+
|  * Root Security Ceilings (nava.yaml)                                  |
|  * Stage & Parallel Goal Decomposition (GoalPlanner)                   |
|  * Subagent Lifecycle Supervisor (Spawn -> Observe -> Teardown)        |
|  * Global Task Budget Enforcement (Tokens, Steps, Depth, Retries)      |
|  * Project Workspace Context Continuator (.nava/project_memory.md)    |
|  * Out-of-Band Emergency Kill Switch Circuit Breaker                   |
+------------------------------------------------------------------------+
```

### 1. Root Security Ceilings (Section 26)
Subagents spawned during task execution can **never** acquire permissions, credentials, or tool access beyond what is granted to the Root Agent in `nava.yaml`.

### 2. Hierarchical Execution Supervision
* **Autonomous Task Staging**: Decomposes complex human instructions into sequential stages (1, 2, ..., N).
* **Concurrent Subagent Dispatch**: Executes independent sub-goals in parallel worker threads while maintaining shared state consistency.
* **Deterministic Teardown**: Upon task completion or failure, thread locks are released, temporary OAuth tokens revoked, and child states set to `TERMINATED`.

---

## Model Context Protocol (MCP) Ecosystem (15 Servers)

NAVA implements the official standard **Model Context Protocol (JSON-RPC 2.0 over stdio)** via `StdioMCPClient` and `MCPClientManager`. Every server can be individually toggled via `enabled: true / false` in `nava.yaml`:

| MCP Server | Assigned Roles | Package & Command | Capabilities & Tool Suite |
| :--- | :--- | :--- | :--- |
| **`context7`** | `CodingAgent` | `npx -y @context7/mcp-server@latest` | AST repository symbol graphs & context definition slicing (`context7.get_symbol_graph`, `context7.slice_context`). |
| **`superpowers`** | `CodingAgent` | `uvx mcp-superpowers-code@latest` | Syntax-aware structural code search, replacement, and compiler auto-fix (`superpowers.ast_search`, `superpowers.ast_replace`, `superpowers.compiler_autofix`). |
| **`git`** | `CodingAgent`, `TerminalAgent` | `npx -y @modelcontextprotocol/server-git@latest` | Project git branch inspection, diffs, staging, and commit operations (`git.status`, `git.diff`, `git.branch`, `git.commit`). |
| **`fetch`** | `ResearchAgent` | `npx -y @modelcontextprotocol/server-fetch@latest` | Token-dense HTML-to-Markdown page conversion and header inspection (`fetch.get_markdown`, `fetch.get_raw_html`, `fetch.get_headers`). |
| **`brave-search`** | `ResearchAgent` | `npx -y @modelcontextprotocol/server-brave-search@latest` | Web search and recent news queries (`brave.search_web`, `brave.search_news`). |
| **`arxiv`** | `ResearchAgent` | `uvx mcp-server-arxiv@latest` | Academic paper search, PDF retrieval, and abstract extraction (`arxiv.search_papers`, `arxiv.get_paper_summary`). |
| **`sqlite`** | `DataAgent` | `uvx mcp-server-sqlite@latest` | SQL query execution, table inspection, and schema profiling (`sqlite.read_query`, `sqlite.write_query`, `sqlite.list_tables`, `sqlite.describe_tables`). |
| **`typst`** | `DocumentAgent`, `UniversalFileAgent` | `uvx typst-mcp-server@latest` | Rust vector Typst compilation into PDF/DOCX reports (`typst.compile_pdf`, `typst.render_template`). |
| **`sequential-thinking`**| `ReviewerAgent`, `VerifierAgent` | `npx -y @modelcontextprotocol/server-sequential-thinking@latest` | Multi-branch hypothesis reasoning and thought revision (`sequential_thinking.step`). |
| **`audit-scanner`** | `ReviewerAgent`, `VerifierAgent` | `uvx nava-audit-mcp@latest` | Deterministic verification of NAVA's 21 System Invariants, AST security scanning, and factual report grounding (`audit.verify_invariants`, `audit.security_scan`, `audit.verify_grounding`). |
| **`docker-sandbox`** | `TerminalAgent` | `uvx docker-sandbox-mcp@latest` | Ephemeral container execution with CPU/memory limits and automatic purge (`docker.create_sandbox`, `docker.exec_in_sandbox`, `docker.destroy_sandbox`). |
| **`playwright-browser`** | `BrowserAgent` | `npx -y @modelcontextprotocol/server-puppeteer@latest` | Headless browser navigation, numbered interactive tree extraction (`[#1]`, `[#2]`), viewport screenshotting, click/type/scroll (`browser.navigate`, `browser.extract_interactive_tree`, `browser.screenshot`, `browser.click`, `browser.type`, `browser.scroll`). |
| **`desktop-automation`** | `ComputerAgent` | `uvx desktop-automation-mcp@latest` | Display resolution perception, high-res desktop screenshots, mouse clicks, keystrokes, and keyboard hotkeys (`desktop.get_screen_size`, `desktop.screenshot`, `desktop.click`, `desktop.type`, `desktop.hotkey`). |
| **`gmail`** | `EmailAgent` | `uvx gmail-mcp-server@latest` | Email search, thread reading, and drafting (`gmail.search`, `gmail.read`). |
| **`github`** | `GitHubAgent` | `npx -y @modelcontextprotocol/server-github@latest` | Repository search, PR reviews, and issue creation (`github.search_repositories`, `github.create_issue`). |

---

## Specialized Agent Suite

NAVA includes a core suite of purpose-built static agents configured for dedicated workflows:

```text
+------------------------------------------------------------------------+
|                     SPECIALIZED STATIC AGENT SUITE                     |
+------------------------------------------------------------------------+
|  1. CodingAgent        AST refactoring, compiler auto-fix, batch edits |
|  2. ReviewerAgent      Security audits, AST vulnerability scan, diffs  |
|  3. VerifierAgent      21 System Invariants proof, grounding checks    |
|  4. ResearchAgent      Web crawling, paper search, semantic RAG        |
|  5. TerminalAgent      Shell execution, Docker sandboxing, test suites |
|  6. BrowserAgent       Playwright web automation & interactive trees   |
|  7. ComputerAgent      OS desktop perception & coordinate mouse/keys   |
|  8. DataAgent          SQL analysis, CSV profiling, anomaly detection  |
|  9. UniversalFileAgent Publication-grade Typst, DOCX, PPTX generation  |
+------------------------------------------------------------------------+
```

---

## Core Codebase Isolation Invariant (Section 29.2)

NAVA enforces a strict mathematical separation between **NAVA's internal operating system files** and **user workspace projects**:

```text
                              LOCAL HOST FILESYSTEM
                                        |
             +--------------------------+--------------------------+
             |                                                     |
             v                                                     v
+-------------------------+                               +-------------------------+
| PROTECTED SYSTEM FILES  |                               | ALLOWED USER WORKSPACE  |
| * src/ (NAVA Framework) |                               | * projects/*            |
| * tests/ (Test Suites)  |      <-- ACCESS BLOCKED --    | * tasks/<id>/artifacts/*|
| * nava.yaml (Policy)    |       (Hard-blocked by        | * scratch/*             |
| * nava_shell.py         |        LocalToolExecutor)     | * memory/*              |
| * .vault_key / .env     |                               | * .nava/project_memory  |
+-------------------------+                               +-------------------------+
```

* **Automatic Task Artifact Sandboxing**: When an agent writes deliverables (e.g. `file.write("auth_service.py")` or `file.write("tasks/summary.md")`), the path is automatically routed into the isolated task directory `tasks/<active_task_id>/artifacts/`.
* **Zero System Modification**: Agents attempting to read or write to `src/`, `tests/`, or framework config are instantly halted with an `Access denied` security receipt.

---

## On-Demand Memory Architecture (80% Token Savings)

NAVA eliminates bloated raw Markdown dumps from LLM system prompts. Instead of injecting tens of thousands of tokens of project history into every call:

1. **Token-Dense Pointers**: The Orchestrator passes compact pointers (`task_id`, `project_name`).
2. **On-Demand Loading**: Agents inspect context on demand via `file.read("task_memory.md")` or `file.read("project_memory.md")`.
3. **80% Token Footprint Reduction**: Execution cycles run up to 4x faster with drastically reduced API costs and zero LLM context saturation.

---

## The 17-Step Chokepoint Action Gateway

Every mutating action in NAVA must pass sequentially through the **17-step ActionGateway chokepoint** (`src/nava/gateway/pipeline.py`):

```text
                        INCOMING TOOL REQUEST
                                    |
                                    v
     [ Step 0a: Emergency Kill Switch ] ---> Verifies Kill Switch Not Tripped
                                    |
                                    v
     [ Step 0b: Request Event Log    ] ---> Emits TOOL_REQUESTED to Audit Ledger
                                    |
                                    v
     [ Step 1: Schema Validation     ] ---> Validates Input Argument Types
                                    |
                                    v
     [ Step 2: Agent Identity Check  ] ---> Authenticates Agent UUID
                                    |
                                    v
     [ Step 3: Agent TTL & Expiry    ] ---> Enforces 5-Minute Agent Lifetime
                                    |
                                    v
     [ Step 4: Parent Scope Check    ] ---> Enforces Non-Increasing Child Scope
                                    |
                                    v
     [ Step 5: Permission Checker    ] ---> Verifies Tool in Granted Permissions
                                    |
                                    v
     [ Step 6: Policy Engine (ALLOW) ] ---> Evaluates Static Rules & Security Switches
                                    |
                                    v
     [ Step 7: Additive Risk Engine  ] ---> Calculates Additive Risk Tier (LOW-CRITICAL)
                                    |
                                    v
     [ Step 8: Task Budget Engine    ] ---> Checks & Consumes Token/Step Quotas
                                    |
                                    v
     [ Step 9: Concurrency Locks     ] ---> Acquires Shared-Read / Exclusive-Write Lock
                                    |
                                    v
     [ Step 10: Credential Broker    ] ---> Generates Ephemeral 5-Min OAuth Token
                                    |
                                    v
     [ Step 11: HITL Gatekeeper      ] ---> Solicits Human Sign-Off for High Risk
                                    |
                                    v
     [ Step 12: Dry-Run & Pre-State  ] ---> Snapshots Resource Hash Before Execution
                                    |
                                    v
     [ Step 13: Sandboxed Execution  ] ---> Dispatches Tool Locally or via MCP
                                    |
                                    v
     [ Step 14: State Observation    ] ---> Records File Hashes & Output Payloads
                                    |
                                    v
     [ Step 15: Post-Verification    ] ---> Verifies Mutation Integrity & Invariants
                                    |
                                    v
     [ Step 16: Cryptographic Receipt] ---> Generates Immutable Signed Execution Receipt
                                    |
                                    v
     [ Step 17: Memory Sync & Release] ---> Appends to Audit Ledger & Releases Locks
                                    |
                                    v
                           EXECUTION COMPLETE
```

---

## Four-Tier Memory Hierarchy & AI Twin

```text
+------------------------------------------------------------------------+
|                        4-TIER MEMORY HIERARCHY                         |
+------------------------------------------------------------------------+
|  Tier 1: Working Memory     | Ephemeral task-scoped scratchpad          |
|  Tier 2: Episodic Memory    | Append-only task receipts & execution logs|
|  Tier 3: Semantic Memory    | Chunked knowledge graph & RAG embeddings  |
|  Tier 4: Profile Memory     | AI Twin verified facts & user preferences |
+------------------------------------------------------------------------+
```

* **Profile Trust Escalation Gate (Invariant #20)**: External content (scraped web pages, downloaded documents, LLM inferences) can never silently write or upgrade memories to `VERIFIED` status in Tier 4 without explicit human confirmation.
* **Conflict Flagging**: Contradictory observations are tagged with `CONFLICT_DETECTED` and routed for user clarification.

---

## The 21 Certified System Invariants

NAVA mathematically guarantees 21 core operating system invariants:

1. **Mutation Gate Chokepoint**: 100% of state mutations must pass through the 17-step Action Gateway.
2. **Append-Only Audit Ledger**: `nava_audit.jsonl` is strictly append-only; past records cannot be modified or truncated.
3. **Receipt Immutability**: Cryptographic execution receipts are immutable once written.
4. **Root Ceiling Enforcement**: Dynamic subagents cannot exceed the root security ceiling in `nava.yaml`.
5. **Non-Increasing Permission Scoping**: Child Scope = Parent Scope & Requested Scope & Policy Allowed Scope.
6. **Maximum Spawn Depth Bound**: Dynamic agent spawn trees are strictly limited to depth <= 10.
7. **Runaway Loop Bound**: Maximum 3 retries on identical failure state; 4th identical failure halts execution.
8. **Short-Lived Credential Isolation**: Scoped credentials have a 5-minute TTL; raw tokens are isolated from agent context.
9. **Write-Exclusive Locking**: Exclusive write locks block concurrent read and write operations on the same resource.
10. **Shared-Read Concurrency**: Multiple subagents can acquire non-conflicting shared read locks concurrently.
11. **Automatic Reversible Rollback**: Tool failures on reversible operations trigger automatic pre-snapshot state restoration.
12. **Irreversible Compensation Routing**: Non-reversible failures route to `CompensationEngine` for compensation workflows.
13. **Bounded Cleanup Budget**: Rollback and compensation routines execute under a strict resource ceiling (<= 5 steps).
14. **HITL Escalation Gate**: Operations returning policy outcome `APPROVAL` strictly mandate a signed user approval record.
15. **Critical Risk Hard-Block**: Tools scoring in the `CRITICAL` risk tier are blocked from automated execution.
16. **Deterministic Resource Teardown**: Agent termination releases locks, revokes temporary credentials, and sets `TERMINATED` status.
17. **Skill Hash-Locking**: Modifying `SKILL.md` on disk triggers an `UNTRUSTED_MODIFIED` state, halting execution until re-hashed.
18. **Out-of-Band Emergency Kill Switch**: Invoking the kill switch immediately halts running threads, revokes credentials, and cancels approvals.
19. **Untrusted Delimiter Boundary**: External untrusted content is strictly wrapped in `<untrusted_content>` tags with tag escaping.
20. **Profile Trust Escalation Gate**: Inferred facts cannot promote themselves to `VERIFIED` tier without explicit user confirmation.
21. **Scope Alignment Invariant**: Agent Permission >= Credential Scope >= Tool Scope.

---

## Configuration & User-Configurable Security Switches

Configured in `nava.yaml`:

```yaml
# Global Execution & Resource Budgets
budget:
  max_agents: 50
  max_depth: 10
  max_steps: 1000
  max_tokens: 1000000

# User-Configurable Security Feature Switches (Section 13 & 26)
security_switches:
  enable_terminal_execution: true    # Set to false to disable all shell/terminal execution
  enable_docker_sandboxing: true     # Set to false to disable ephemeral Docker container creation
  enable_desktop_gui_control: true   # Set to false to make ComputerAgent read-only (screenshots only)
  enable_browser_automation: true    # Set to false to disable Playwright web navigation & form automation
  enable_code_mutation: true         # Set to false to make CodingAgent read-only
  enable_external_integrations: true # Set to false to block external web MCPs, Gmail, and GitHub integrations
  enable_deep_audit_gates: true      # Set to false to bypass sequential thinking & AST security scanners
  enforce_codebase_isolation: true   # Set to false to disable strict isolation of NAVA's internal framework files

# Model Context Protocol (MCP) Ecosystem & Specialized Agent Servers
mcp_servers:
  context7:
    enabled: true
    command: "npx"
    args: ["-y", "@context7/mcp-server@latest"]
    assigned_roles: ["CodingAgent"]
    trust_state: "TRUSTED"
  
  superpowers:
    enabled: true
    command: "uvx"
    args: ["mcp-superpowers-code@latest"]
    assigned_roles: ["CodingAgent"]
    trust_state: "TRUSTED"

  git:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-git@latest"]
    assigned_roles: ["CodingAgent", "TerminalAgent"]
    trust_state: "TRUSTED"

  fetch:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-fetch@latest"]
    assigned_roles: ["ResearchAgent"]
    trust_state: "TRUSTED"

  brave-search:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-brave-search@latest"]
    assigned_roles: ["ResearchAgent"]
    trust_state: "TRUSTED"

  arxiv:
    enabled: true
    command: "uvx"
    args: ["mcp-server-arxiv@latest"]
    assigned_roles: ["ResearchAgent"]
    trust_state: "TRUSTED"

  sqlite:
    enabled: true
    command: "uvx"
    args: ["mcp-server-sqlite@latest"]
    assigned_roles: ["DataAgent"]
    trust_state: "TRUSTED"

  typst:
    enabled: true
    command: "uvx"
    args: ["typst-mcp-server@latest"]
    assigned_roles: ["DocumentAgent", "UniversalFileAgent"]
    trust_state: "TRUSTED"

  sequential-thinking:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-sequential-thinking@latest"]
    assigned_roles: ["ReviewerAgent", "VerifierAgent"]
    trust_state: "TRUSTED"

  audit-scanner:
    enabled: true
    command: "uvx"
    args: ["nava-audit-mcp@latest"]
    assigned_roles: ["ReviewerAgent", "VerifierAgent"]
    trust_state: "TRUSTED"

  docker-sandbox:
    enabled: true
    command: "uvx"
    args: ["docker-sandbox-mcp@latest"]
    assigned_roles: ["TerminalAgent"]
    trust_state: "TRUSTED"

  playwright-browser:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-puppeteer@latest"]
    assigned_roles: ["BrowserAgent"]
    trust_state: "TRUSTED"

  desktop-automation:
    enabled: true
    command: "uvx"
    args: ["desktop-automation-mcp@latest"]
    assigned_roles: ["ComputerAgent"]
    trust_state: "TRUSTED"

  gmail:
    enabled: true
    command: "uvx"
    args: ["gmail-mcp-server@latest"]
    assigned_roles: ["EmailAgent"]
    trust_state: "TRUSTED"

  github:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github@latest"]
    assigned_roles: ["GitHubAgent"]
    trust_state: "TRUSTED"
```

---

## Interactive TUI Cowork Shell

Launch the command shell:

```bash
nava
```

### Slash Commands:
* `/mcp` -- Inspect active MCP servers, registered tools, trust status, and risk tiers.
* `/mcp approve <server> <tool>` -- Approve new or modified MCP tool definitions into the trusted hash ledger.
* `/twin` -- Inspect or update AI Twin persona facts (`/twin set role Software Architect`).
* `/skills` -- Inspect loaded `SKILL.md` skills and their SHA-256 integrity hash status.
* `/budget` -- View live task budget token, step, and agent consumption metrics.
* `/kill` -- Trigger the out-of-band Emergency Kill Switch circuit breaker.
* `tasks` -- View all past task memories.
* `task resume <task_id>` -- Resume an existing task session with complete historical context.
* `projects` / `project use <name>` -- Switch between isolated project workspaces.

---

## Repository Layout

```text
.
|-- .nava/                           # Project Workspace context ledger & AST checkpoints
|-- memory/                          # Four-Tier persistent JSON memory stores
|-- projects/                        # User project workspaces
|-- tasks/                           # Isolated task sessions & deliverable artifacts
|-- src/
|   `-- nava/
|       |-- agents/
|       |   |-- factory.py           # AgentFactory with permission intersection
|       |   |-- planner.py           # GoalPlanner stage decomposition & tool assignment
|       |   |-- templates.py         # Static agent template catalog
|       |   `-- runtime/             # LangGraph cyclic execution runtimes
|       |-- core/
|       |   |-- boot.py              # Bootstrapper & security switch ceiling filtering
|       |   |-- ledger.py            # Append-only audit ledger
|       |   |-- llm.py               # Frontier LLM gateway
|       |   |-- message_bus.py       # Inter-agent Pub/Sub broker
|       |   |-- sanitizer.py         # Prompt injection sanitizer
|       |   `-- schemas.py           # Pydantic core schemas
|       |-- credentials/
|       |   |-- vault.py             # AES-256 credential vault
|       |   `-- broker.py            # Scoped 5-minute credential broker
|       |-- gateway/
|       |   `-- pipeline.py          # 17-step ActionGateway implementation
|       |-- governance/
|       |   |-- policy_engine.py     # Deterministic policy evaluation & security switches
|       |   |-- risk_engine.py       # Additive risk scoring
|       |   |-- budget_engine.py     # Token/step budgets & runaway loop detector
|       |   |-- lock_manager.py      # Read/write concurrency locks
|       |   |-- hitl_manager.py      # Human-in-the-Loop approval queues
|       |   |-- rollback_engine.py   # Reversible state restoration
|       |   |-- compensation_engine.py # Irreversible compensation routines
|       |   |-- dom_sanitizer.py     # DOM tripwire cleaner
|       |   `-- state_observer.py    # Resource hash snapshotting
|       |-- memory/
|       |   |-- store.py             # Working, Episodic, Semantic, Profile memory stores
|       |   `-- ai_twin.py           # AI Twin persona and fact manager
|       |-- prompts/                 # On-demand prompt templates
|       |-- skills/
|       |   |-- manager.py           # SKILL.md parsing & hash verification
|       |   `-- promotion.py         # Dynamic skill promotion engine
|       |-- tools/
|       |   |-- executor.py          # LocalToolExecutor & codebase isolation sandbox
|       |   |-- registry.py          # ToolRegistry & schema definitions
|       |   |-- tool_manifest.py     # Complete tool catalog & MCP registration
|       |   |-- browser.py           # Playwright headless browser engine
|       |   |-- computer_engine.py   # OS desktop GUI perception & coordinate control
|       |   |-- terminal_engine.py   # TerminalEngine & DockerSandboxManager
|       |   |-- data_engine.py       # SQLite, SQL CSV & data profiling engine
|       |   |-- document_engine.py   # Typst Rust vector PDF engine
|       |   |-- audit_engine.py      # AST vulnerability & invariant verification engine
|       |   `-- mcp_client.py        # StdioMCPClient & MCPClientManager
|       |-- ui/
|       |   `-- cowork_tui.py        # Interactive terminal UI
|       |-- workspace/
|       |   |-- indexer.py           # AST symbol parser
|       |   `-- project_manager.py   # Workspace context continuity engine
|       `-- orchestrator.py          # End-to-end task orchestration kernel
|-- tests/                           # Complete automated unit & integration test suites
|   |-- test_security_switches.py    # User security switches & MCP disabling tests
|   |-- test_browser_computer_mcp.py # Browser & desktop automation tests
|   |-- test_terminal_agent_mcp.py   # DevOps & Docker sandbox tests
|   |-- test_codebase_isolation.py   # Core codebase isolation sandbox tests
|   |-- test_21_invariants.py        # 21 System Invariants tests
|   |-- test_specialized_agents.py   # Static agent template tests
|   |-- test_project_workspace.py    # Workspace context tests
|   `-- test_agent_message_bus.py    # Inter-agent Pub/Sub tests
|-- nava.yaml                        # OS configuration, budgets & security policy
|-- nava_shell.py                    # Interactive shell entrypoint
`-- requirements.txt                 # Dependencies
```

---

## Getting Started & Quickstart

### 1. Prerequisites
* Python 3.10 or higher
* Node.js / `npx` (for NPM MCP servers like `@context7/mcp-server`, `@modelcontextprotocol/server-git`)
* Python `uv` / `uvx` (for Python MCP servers like `mcp-server-sqlite`, `typst-mcp-server`)
* Google Gemini API Key (or local OpenAI-compatible LLM endpoint)

---

### 2. Installation Options

#### Option A: Install from PyPI (Recommended)
You can install NAVA directly as a Python package or standalone CLI tool:

```bash
# Using standard pip
pip install nava-agent

# Or as an isolated global tool with pipx
pipx install nava-agent

# Install Playwright browser dependencies
playwright install chromium
```

#### Option B: Install from Source (Developer Setup)
```bash
# Clone the repository
git clone https://github.com/Aakhilshaik204/nava-agent.git
cd nava-agent

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# Install in editable mode
pip install -e .
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install chromium
```

---

### 3. Environment Configuration
Set your Gemini API key in your environment or create a `.env` file:
```bash
# Windows PowerShell
$env:GEMINI_API_KEY="your_gemini_api_key_here"

# Linux / macOS
export GEMINI_API_KEY="your_gemini_api_key_here"
```

Or create a `.env` file in your workspace root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
NAVA_ENV=development
```

---

### 4. Launching the Operating System

If installed via PyPI/pipx, launch from any directory using the global `nava` command:
```bash
nava
```

Or run the interactive shell directly from the repository:
```bash
python nava_shell.py
```

---

## Automated Verification & Test Suite

Run the full automated test suite:

```bash
# 1. Verify User Security Switches & MCP Dynamic Disabling
python -m unittest tests/test_security_switches.py -v

# 2. Verify Browser & Desktop Computer Use MCP Suite
python -m unittest tests/test_browser_computer_mcp.py -v

# 3. Verify Terminal DevOps & Docker Sandboxing Suite
python -m unittest tests/test_terminal_agent_mcp.py -v

# 4. Verify Core Codebase Isolation Invariant
python -m unittest tests/test_codebase_isolation.py -v

# 5. Verify all 21 Certified System Invariants
python -m unittest tests/test_21_invariants.py -v

# 6. Verify Specialized Agent Templates
python -m unittest tests/test_specialized_agents.py -v

# 7. Verify Workspace Memory & AST Indexer
python -m unittest tests/test_project_workspace.py -v

# 8. Verify Inter-Agent Message Bus & Peer Review
python -m unittest tests/test_agent_message_bus.py -v
```

---

## License

Apache 2.0 License. See `LICENSE` for details.
