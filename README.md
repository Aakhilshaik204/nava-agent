# NAVA: Personal Agent Operating System

NAVA is a deterministic, multi-agent personal operating system designed for autonomous workspace execution, secure computer use, deep research synthesis, and persistent human-AI collaboration.

Built around a 12-step mutation gateway, a 4-tier memory hierarchy, an inter-agent message bus, and 21 mathematically verified system invariants, NAVA guarantees strict least-privilege bounding, tamper-evident audit receipts, and transactional rollback across all filesystem, terminal, browser, and OS desktop interactions.

---

## Table of Contents
1. [System Architecture Overview](#system-architecture-overview)
2. [The NAVA Root Agent (Kernel Controller)](#the-nava-root-agent-kernel-controller)
3. [Dynamic Agents & Just-In-Time (JIT) Synthesis](#dynamic-agents--just-in-time-jit-synthesis)
4. [Specialized Static Agent Suite](#specialized-static-agent-suite)
5. [The 12-Step Chokepoint Action Gateway](#the-12-step-chokepoint-action-gateway)
6. [Real-Time Multi-Agent Collaboration (AgentMessageBus)](#real-time-multi-agent-collaboration-agentmessagebus)
7. [Project Workspace Memory (.nava/)](#project-workspace-memory-nava)
8. [Four-Tier Memory Architecture & AI Twin](#four-tier-memory-architecture--ai-twin)
9. [The 21 Certified System Invariants](#the-21-certified-system-invariants)
10. [Configuration & Security Switches](#configuration--security-switches)
11. [Repository Structure](#repository-structure)
12. [Getting Started & Quickstart](#getting-started--quickstart)
13. [Verification & Test Suite](#verification--test-suite)

---

## System Architecture Overview

NAVA replaces unconstrained prompt chains with a deterministic operating system kernel. Every tool call—whether writing a file, running a shell command, clicking an OS desktop window, or drafting an email via Model Context Protocol (MCP)—is treated as a managed system call subject to policy validation, risk scoring, resource quotas, and concurrency locking.

```
                           USER OBJECTIVE / SHELL
                                     │
                                     ▼
                    ┌─────────────────────────────────┐
                    │     NAVA ROOT ORCHESTRATOR      │
                    │   (Executive Kernel Controller) │
                    └────────────────┬────────────────┘
                                     │
                        Decompose Objective
                                     │
                                     ▼
                            [ GoalPlanner ]
                 Stage 1 (Parallel) ──► Stage 2 (Sequential)
                                     │
                                     ▼
                            [ AgentFactory ]
                 JIT Dynamic Synthesis & Scope Intersect:
            Child_Scope = Parent_Scope ∩ Spec_Scope ∩ Policy_Scope
                                     │
             ┌───────────────────────┴───────────────────────┐
             │                                               │
             ▼                                               ▼
┌──────────────────────────┐                   ┌──────────────────────────┐
│  SPECIALIZED STATIC AGENTS│                   │  JUST-IN-TIME DYNAMIC    │
│  • CodingAgent           │◄─────────────────►│  AGENTS                  │
│  • ReviewerAgent         │   Inter-Agent     │  • WebResearchAgent      │
│  • ResearchAgent         │   Message Bus     │  • ASTRefactorAgent      │
│  • TerminalAgent         │   (Pub/Sub)       │  • DataExtractionAgent   │
│  • ComputerAgent         │                   │  • PDFCompilationAgent   │
└────────────┬─────────────┘                   └─────────────┬────────────┘
             │                                               │
             └───────────────────────┬───────────────────────┘
                                     │
                          Tool Request RPC Call
                                     │
                                     ▼
         ┌────────────────────────────────────────────────────────┐
         │             12-STEP ACTION GATEWAY PIPELINE            │
         │  1. Auth & Lineage Check    7. Pre-State Snapshot      │
         │  2. Policy Engine (ALLOW)   8. Sandboxed Tool Dispatch │
         │  3. Additive Risk Engine    9. Post-State Verification │
         │  4. Budget & Quota Check   10. Cryptographic Receipt   │
         │  5. Concurrency Locks      11. Lock Release & Teardown │
         │  6. HITL Gatekeeper        12. Episodic Memory Sync    │
         └───────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
         ┌────────────────────────────────────────────────────────┐
         │                 HOST SYSTEM BOUNDARIES                 │
         │  • Local Filesystem Root    • Playwright Browser       │
         │  • OS Desktop GUI Driver    • MCP External Servers     │
         └────────────────────────────────────────────────────────┘
```

---

## The NAVA Root Agent (Kernel Controller)

At the apex of the operating system resides the **NAVA Root Agent** (`src/nava/orchestrator.py`), serving as the privileged executive supervisor of the agent collective:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        NAVA ROOT AGENT KERNEL                          │
├────────────────────────────────────────────────────────────────────────┤
│  • Root Security Ceilings (nava.yaml)                                  │
│  • Executive Stage & Parallel Goal Decomposition (GoalPlanner)        │
│  • Subagent Lifecycle Supervisor (Spawn -> Observe -> Teardown)        │
│  • Global Task Budget Enforcement (Tokens, Steps, Depth, Retries)      │
│  • Project Workspace Context Continuator (.nava/project_memory.md)    │
│  • Out-of-Band Emergency Kill Switch Circuit Breaker                   │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. Root Security Ceilings (Blueprint Section 26)
The Root Agent acts as the maximum security ceiling for all operations. Subagents spawned during task execution can never acquire permissions, credentials, or tool access beyond what is granted to the Root Agent in `nava.yaml`.

### 2. Hierarchical Execution Supervision
* **Autonomous Task Staging**: Decomposes complex human instructions into isolated stages ($1, 2, \dots, N$).
* **Concurrent Subagent Dispatch**: Executes independent sub-goals concurrently in parallel worker threads while maintaining shared state consistency.
* **Deterministic Teardown**: Upon task completion or failure, the root controller flushes thread locks, revokes temporary OAuth tokens, and transitions child states to `TERMINATED`.

### 3. Context Continuity & Crash Recovery
The Root Agent automatically reads `.nava/project_memory.md` on startup, detecting unfinished objectives from previous sessions and enabling single-word resumption (`continue`) without loss of architectural decisions.

---

## Dynamic Agents & Just-In-Time (JIT) Synthesis

While static agents handle dedicated operational domains, real-world development requires adaptable, task-specific workers. NAVA's **Dynamic Agent Engine** (`src/nava/agents/factory.py` & `src/nava/agents/runtime/dynamic_agent.py`) synthesizes specialized agents just-in-time.

```
                  USER OBJECTIVE: "Parse 50 PDFs and index into Qdrant"
                                     │
                                     ▼
                         1. SPECIFICATION (AgentSpec)
                            - Role: PDFIndexerAgent
                            - Required Tools: ['file.read', 'memory.semantic_ingest']
                            - Stage: 1 (Parallel)
                                     │
                                     ▼
                    2. DEDUPLICATION HASHING (Invariant #7)
                       dedup_hash = SHA256("PDFIndexerAgent:goal:tools")
                                     │
                                     ▼
                  3. PERMISSION INTERSECTION (Invariant #5)
             Child_Scope = Parent_Scope ∩ Requested_Scope ∩ Policy_Scope
                                     │
                                     ▼
                      4. ISOLATED RUNTIME INSTANTIATION
                         Cyclic Multi-Step Graph (Plan ◄──► Act)
                                     │
                                     ▼
                    5. AUTOMATIC SKILL PROMOTION (Sec 9.6)
              Promotes successful novel workflows to SKILL.md
```

### 1. Non-Increasing Permission Inheritance (Invariant #5)
Dynamic agents can never escalate privileges. The `AgentFactory` enforces mathematical intersection:

$$\text{Child Scope} = \text{Parent Scope} \cap \text{Requested Scope} \cap \text{Policy Allowed Scope}$$

If a dynamically synthesized agent requests `terminal.execute` but its parent or active policy prohibits terminal execution, the capability is stripped before instantiation.

### 2. Deduplication & Runaway Loop Prevention (Invariant #7)
Every dynamic agent spec is hashed with its role, objective, and tool grant:

$$\text{Dedup Hash} = \text{SHA256}(\text{role} \parallel \text{clean\_goal} \parallel \text{tools})[:16]$$

If an agent fails identically 3 times, the 4th identical failure triggers an automatic task abort and routes to `CompensationEngine`, preventing infinite execution loops and runaway token consumption.

### 3. Dynamic Skill Promotion (Section 9.6)
When a Dynamic Agent solves a novel problem sequence successfully, NAVA's `SkillPromoter` can extract the successful action trajectory, package it into a standard `SKILL.md` with SHA-256 integrity locking, and save it to `.nava/local_skills/` for future instant reuse across projects.

---

## Specialized Static Agent Suite

NAVA includes a core suite of purpose-built static agents configured for dedicated workflows:

```
┌────────────────────────────────────────────────────────────────────────┐
│                     SPECIALIZED STATIC AGENT SUITE                     │
├────────────────────────────────────────────────────────────────────────┤
│  1. CodingAgent       Cyclic code refactoring, AST edits, batch patches│
│  2. ReviewerAgent     Diff analysis, quality audits, peer review       │
│  3. ResearchAgent     Deep web search, text extraction, semantic RAG   │
│  4. TerminalAgent     Sandboxed shell execution, git, test runners     │
│  5. ComputerAgent     OS desktop GUI control, DPI scaling, coordinates │
│  6. UniversalFileAgent Single-shot PDF/DOCX/PPTX report compilation    │
└────────────────────────────────────────────────────────────────────────┘
```

| Agent | Core Capabilities | Tool & Scope Grant |
| :--- | :--- | :--- |
| **`CodingAgent`** | Multi-step code analysis, AST symbol exploration, transactional multi-file batch patching, and syntax validation. | `code.search`, `code.replace_content`, `code.replace_content_batch`, `filesystem.write` |
| **`ReviewerAgent`** | AST linting, structural diff review, and closed-loop peer review feedback on the message bus. | `code.diff_review`, `filesystem.read`, `git.read` |
| **`ResearchAgent`** | Multi-source web crawling, noise stripping, fact cross-referencing, and Tier 3 Semantic RAG ingestion. | `search.web`, `browser.navigate`, `browser.extract_text`, `browser.save_to_scratch`, `memory.semantic_ingest` |
| **`TerminalAgent`** | Sandboxed shell commands, git branch/diff inspection, test suite execution (`pytest`, `unittest`, `npm test`), and compilation diagnostics. | `terminal.execute`, `shell.execute`, `test.run`, `git.status`, `git.diff` |
| **`ComputerAgent`** | OS desktop perception (Per-Monitor DPI scaling, region screenshots) and grounded mouse/keyboard automation with credential blockers. | `desktop.screenshot`, `desktop.click`, `desktop.drag`, `desktop.scroll`, `desktop.type`, `desktop.hotkey` |
| **`UniversalFileAgent`** | Single-shot document compilation, converting structured text into formatted PDF, Word (`.docx`), and PowerPoint (`.pptx`) deliverables. | `file.write`, `file.create_pdf`, `file.create_docx`, `file.create_pptx` |

---

## The 12-Step Chokepoint Action Gateway

Every mutating action in NAVA must pass sequentially through the 12-step `ActionGateway` chokepoint (`src/nava/gateway/pipeline.py`):

```
                        INCOMING MUTATION REQUEST
                                    │
                                    ▼
     [ Step 1: Authentication & Lineage ] ──► Validates UUID & Active TTL
                                    │
                                    ▼
     [ Step 2: Policy Engine (ALLOW)   ] ──► Checks Static Rules & Switches
                                    │
                                    ▼
     [ Step 3: Additive Risk Engine     ] ──► Computes Additive Risk Score
                                    │
                                    ▼
     [ Step 4: Task Budget Engine       ] ──► Verifies Tokens, Steps & Depth
                                    │
                                    ▼
     [ Step 5: Concurrency Lock Manager ] ──► Acquires Shared/Exclusive Locks
                                    │
                                    ▼
     [ Step 6: HITL Approval Gate       ] ──► Triggers User Prompt if HIGH Risk
                                    │
                                    ▼
     [ Step 7: State Observer Snapshot  ] ──► Captures Pre-Execution File Hash
                                    │
                                    ▼
     [ Step 8: Execution Sandbox        ] ──► Dispatches Tool Locally or via MCP
                                    │
                                    ▼
     [ Step 9: Post-State Verification  ] ──► Validates Size, Path & Integrity
                                    │
                                    ▼
     [ Step 10: Audit Receipt Ledger    ] ──► Emits Signed JSON Receipt
                                    │
                                    ▼
     [ Step 11: Teardown & Lock Release ] ──► Releases Concurrency Locks
                                    │
                                    ▼
     [ Step 12: Episodic Memory Sync    ] ──► Syncs Task Outcome to Tier 2 Store
                                    │
                                    ▼
                           EXECUTION COMPLETE
```

---

## Real-Time Multi-Agent Collaboration (AgentMessageBus)

NAVA coordinates multi-agent swarms using a high-throughput, thread-safe Pub/Sub broker (`src/nava/core/message_bus.py`):

### 1. Channel-Based Communication
Agents subscribe and publish to isolated channels:
* `task:<stage_id>:<topic>`: Ephemeral channel for agents collaborating on a shared stage.
* `peer_review`: Dedicated channel for code submission and review feedback.
* `broadcast:progress`: Global streaming channel broadcasting step metrics and reasoning thoughts.

### 2. Closed-Loop Peer Review Protocol
When `CodingAgent` generates code changes, it initiates a closed-loop review handshake:

```
  [ CodingAgent ]                                 [ ReviewerAgent ]
         │                                                │
         │─── 1. PEER_REVIEW_REQUEST(diff, file_path) ───►│
         │                                                │ Evaluates AST & Tests
         │◄── 2. PEER_REVIEW_FEEDBACK(approved, fixes) ───│
         │
   [ If Changes Requested ]
   Applies fixes & resubmits
```

### 3. Real-Time UI Streaming
The `AgentMessageBus` exposes an `add_global_listener` hook that feeds directly into WebSocket and Server-Sent Event (SSE) streams for real-time frontend visualization.

---

## Project Workspace Memory (.nava/)

Every project directory managed by NAVA contains a persistent `.nava/` workspace context ledger:

```
<Project_Root>/
├── .nava/
│   ├── project_memory.md       ◄── Human & machine-readable context ledger
│   ├── project_index.json      ◄── Function & Class AST Symbol Knowledge Graph
│   └── checkpoints/            ◄── Snapshot diff restore points for fast rollbacks
├── src/ ...
└── tests/ ...
```

### Structure of `project_memory.md`
1. **Project Overview & Architecture**: Tech stack, primary goal, file index stats.
2. **Current Execution State (Live Checkpoint)**: Active objective, last active agent, timestamp, touched files.
3. **Architectural Decisions & Constraints**: Append-only log of technical decisions (e.g. "Using RS256 for JWT").
4. **Resume Queue**: Ordered checklist of completed and pending sub-tasks for cross-session continuity.

---

## Four-Tier Memory Architecture & AI Twin

```
┌────────────────────────────────────────────────────────────────────────┐
│                        4-TIER MEMORY HIERARCHY                         │
├────────────────────────────────────────────────────────────────────────┤
│  Tier 1: Working Memory     │ Ephemeral task-scoped scratchpad          │
│  Tier 2: Episodic Memory    │ Append-only task receipts & execution logs│
│  Tier 3: Semantic Memory    │ Chunked knowledge graph & RAG embeddings  │
│  Tier 4: Profile Memory     │ AI Twin verified facts & user preferences │
└────────────────────────────────────────────────────────────────────────┘
```

### Memory Security & Invariant #20
* **Profile Trust Escalation Gate**: External content (scraped web pages, downloaded documents, LLM inferences) can never silently write or upgrade memories to `VERIFIED` status in Tier 4.
* **Conflict Flagging**: If a new observation contradicts an existing verified profile fact, NAVA marks the fact with `CONFLICT_DETECTED` and requests user clarification instead of overwriting.

---

## The 21 Certified System Invariants

NAVA adheres to 21 system invariants validated through continuous unit and adversarial test suites:

1. **Mutation Gate Chokepoint**: 100% of state-mutating requests must pass through the 12-step Gateway.
2. **Append-Only Audit Ledger**: `nava_audit.jsonl` is strictly append-only; past records cannot be modified or truncated.
3. **Receipt Immutability**: Cryptographic execution receipts are immutable once written.
4. **Root Ceiling Enforcement**: Dynamic subagents cannot exceed the root security ceiling in `nava.yaml`.
5. **Non-Increasing Permission Scoping**: $\text{Child Scope} = \text{Parent Scope} \cap \text{Requested Scope} \cap \text{Policy Allowed Scope}$.
6. **Maximum Spawn Depth Bound**: Dynamic agent spawn trees are strictly limited to $\text{depth} \le 10$.
7. **Runaway Loop Bound**: Maximum 3 retries on identical failure state; 4th identical failure halts execution.
8. **Short-Lived Credential Isolation**: Scoped credentials have a 5-minute TTL; raw tokens are isolated from agent context.
9. **Write-Exclusive Locking**: Exclusive write locks block concurrent read and write operations on the same resource.
10. **Shared-Read Concurrency**: Multiple subagents can acquire non-conflicting shared read locks concurrently.
11. **Automatic Reversible Rollback**: Tool failures on reversible operations trigger automatic pre-snapshot state restoration.
12. **Irreversible Compensation Routing**: Non-reversible failures route to `CompensationEngine` for designated compensation workflows.
13. **Bounded Cleanup Budget**: Rollback and compensation routines execute under a strict resource ceiling ($\le 5$ steps).
14. **HITL Escalation Gate**: Operations returning policy outcome `APPROVAL` strictly mandate a signed user approval record.
15. **Critical Risk Hard-Block**: Tools scoring in the `CRITICAL` risk tier are blocked from automated execution.
16. **Deterministic Resource Teardown**: Agent termination releases locks, revokes temporary credentials, and sets `TERMINATED` status.
17. **Skill Hash-Locking**: Modifying `SKILL.md` on disk triggers an `UNTRUSTED_MODIFIED` state, halting execution until re-hashed.
18. **Out-of-Band Emergency Kill Switch**: Invoking the kill switch immediately halts running threads, revokes credentials, and cancels approvals.
19. **Untrusted Delimiter Boundary**: External untrusted content is strictly wrapped in `<untrusted_content>` tags with tag escaping.
20. **Profile Trust Escalation Gate**: Inferred facts cannot promote themselves to `VERIFIED` tier without explicit user confirmation.
21. **Scope Alignment Invariant**: $\text{Agent Permission} \supseteq \text{Credential Scope} \supseteq \text{Tool Scope}$.

---

## Configuration & Security Switches

Global resource budgets, capabilities, and master security feature switches are defined in `nava.yaml`:

```yaml
# Root Agent Security Ceilings
root_agent:
  ceiling_permissions:
    - filesystem.write
    - filesystem.read
    - data.analyze
    - test.run
    - terminal.execute
    - shell.execute
    - browser.*
    - desktop.*
    - search.web
    - memory.semantic

  ceiling_tools:
    - file.read
    - file.write
    - file.delete
    - file.create_pdf
    - file.create_docx
    - file.create_pptx
    - code.search
    - code.replace_content
    - code.replace_content_batch
    - terminal.execute
    - shell.execute
    - test.run
    - git.status
    - git.diff
    - search.web
    - memory.semantic_ingest
    - browser.navigate
    - browser.extract_text
    - browser.save_to_scratch
    - desktop.screenshot
    - desktop.click
    - desktop.type
    - desktop.hotkey

# Global Resource Budgets
budget:
  max_agents: 50
  max_depth: 10
  max_steps: 1000
  max_tokens: 1000000

# User-Configurable Security Feature Switches
security_switches:
  enable_terminal_execution: true    # Toggle shell/terminal execution
  enable_desktop_gui_control: true   # Toggle mouse/keyboard automation (false = screenshot-only mode)
  enable_external_integrations: true # Toggle external MCP/Gmail integrations
```

---

## Repository Structure

```
.
├── .nava/                           # Project Workspace context ledger & checkpoints
│   ├── project_memory.md            # Live execution state and architectural decisions
│   ├── project_index.json           # Python AST code symbols index
│   └── checkpoints/                 # Ephemeral pre-mutation snapshot backups
├── memory/                          # Persistent JSON memory tiers
│   ├── profile.json                 # Tier 4: AI Twin verified facts
│   ├── semantic.json                # Tier 3: Knowledge base & RAG records
│   └── episodic.json                # Tier 2: Task execution receipts
├── src/
│   └── nava/
│       ├── agents/
│       │   ├── factory.py           # AgentFactory with permission intersection
│       │   ├── planner.py           # GoalPlanner stage decomposition
│       │   ├── templates.py         # Static agent template definitions
│       │   └── runtime/             # LangGraph agent execution runtimes
│       │       ├── coding_agent.py
│       │       ├── reviewer_agent.py
│       │       ├── research_agent.py
│       │       ├── terminal_agent.py
│       │       ├── computer_agent.py
│       │       └── dynamic_agent.py
│       ├── core/
│       │   ├── boot.py              # System bootstrap & initialization
│       │   ├── ledger.py            # Append-only audit ledger
│       │   ├── llm.py               # Frontier LLM interface
│       │   ├── message_bus.py       # Inter-agent Pub/Sub broker
│       │   ├── sanitizer.py         # Prompt injection & delimiter sanitizer
│       │   └── schemas.py           # Pydantic schemas and models
│       ├── credentials/
│       │   ├── vault.py             # Encrypted credential storage
│       │   └── broker.py            # Short-lived credential broker
│       ├── gateway/
│       │   └── pipeline.py          # 12-step ActionGateway implementation
│       ├── governance/
│       │   ├── policy_engine.py     # Rule evaluation & security switches
│       │   ├── risk_engine.py       # Additive scoring risk engine
│       │   ├── budget_engine.py     # Quota tracking & loop detection
│       │   ├── lock_manager.py      # Read/write concurrency control
│       │   ├── hitl_manager.py      # Human-in-the-Loop approval queues
│       │   ├── rollback_engine.py   # Reversible state rollback
│       │   ├── compensation_engine.py # Irreversible compensation routines
│       │   ├── dom_sanitizer.py     # HTML tripwire & injection cleaner
│       │   └── state_observer.py    # Resource hash snapshotting
│       ├── memory/
│       │   └── store.py             # Working, Episodic, Semantic, Profile stores
│       ├── skills/
│       │   ├── manager.py           # SKILL.md parsing & hash verification
│       │   └── promotion.py         # Dynamic skill promotion pipeline
│       ├── tools/
│       │   ├── executor.py          # Local tool execution engine
│       │   ├── registry.py          # Tool definitions & schemas
│       │   ├── browser.py           # Playwright Chromium browser driver
│       │   ├── desktop.py           # DPI-aware OS desktop GUI engine
│       │   └── mcp_client.py        # Model Context Protocol stdio client
│       ├── workspace/
│       │   ├── indexer.py           # AST symbol parser
│       │   └── project_manager.py   # Workspace context continuity engine
│       └── orchestrator.py          # End-to-end task orchestration kernel
├── tests/                           # Complete test suite (39 verified tests)
│   ├── test_21_invariants.py        # 21 System Invariants verification
│   ├── test_project_workspace.py    # Workspace memory & AST indexer tests
│   ├── test_specialized_agents.py   # Specialized agents & security switches tests
│   └── test_agent_message_bus.py    # Pub/Sub broker & peer review loop tests
├── nava.yaml                        # OS configuration & security policy
├── nava_shell.py                    # Interactive CLI shell
└── requirements.txt                 # Dependencies
```

---

## Getting Started & Quickstart

### Prerequisites
* Python 3.10 or higher
* Google Gemini API key (or local OpenAI-compatible endpoint)

### Installation
```bash
# Clone the repository
git clone https://github.com/your-org/nava.git
cd nava

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser binaries (optional, for browser automation)
playwright install chromium
```

### Environment Configuration
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
NAVA_ENV=development
```

### Launching the Interactive Shell
```bash
python nava_shell.py
```

---

## Verification & Test Suite

Run the full automated test suite:

```bash
# 1. Verify all 21 certified system invariants
python -m unittest tests/test_21_invariants.py -v

# 2. Verify specialized agents and security switches
python -m unittest tests/test_specialized_agents.py -v

# 3. Verify project workspace memory and AST indexer
python -m unittest tests/test_project_workspace.py -v

# 4. Verify inter-agent message bus & peer review loop
python -m unittest tests/test_agent_message_bus.py -v
```

---

## License

Apache 2.0 License. See `LICENSE` for details.
