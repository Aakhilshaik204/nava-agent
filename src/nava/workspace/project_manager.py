import os
import re
import shutil
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from nava.workspace.indexer import ProjectIndexer

class TaskManager:
    """
    Manages individual '+ New' Task and Chat sessions.
    Every task is isolated in `tasks/<task_id>/` with its own `task_memory.md`
    and task-scoped `artifacts/` folder visible in the workspace.
    """
    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = os.path.abspath(root_dir or os.getcwd())
        self.tasks_dir = os.path.join(self.root_dir, "tasks")
        os.makedirs(self.tasks_dir, exist_ok=True)
        self._active_task_id: Optional[str] = None

    def _resolve_project_dir(self, objective: str, project_id: Optional[str] = None) -> Optional[str]:
        """Resolves target project workspace directory if specified in objective or project context."""
        m = re.search(r'projects/([a-zA-Z0-9_\-]+)', objective or "", re.IGNORECASE)
        if m:
            p_name = m.group(1)
            p_dir = os.path.join(self.root_dir, "projects", p_name)
            os.makedirs(p_dir, exist_ok=True)
            return p_dir
        if project_id and project_id != "default":
            p_dir = os.path.join(self.root_dir, "projects", project_id)
            os.makedirs(p_dir, exist_ok=True)
            return p_dir
        return None

    def create_task(self, objective: str, project_id: Optional[str] = "default") -> str:
        """Creates a brand new task session with clean task_memory.md audit receipt."""
        now = datetime.utcnow()
        clean_name = re.sub(r'[^a-zA-Z0-9]', '_', objective[:24]).strip('_').lower()
        task_id = f"tsk_{now.strftime('%Y%m%d_%H%M%S')}_{clean_name or 'goal'}"
        
        task_folder = os.path.join(self.tasks_dir, task_id)
        artifacts_folder = os.path.join(task_folder, "artifacts")
        os.makedirs(artifacts_folder, exist_ok=True)
        
        task_memory_path = os.path.join(task_folder, "task_memory.md")
        content = f"""# 📋 Task Memory: {objective}

- **Task ID**: `{task_id}`
- **Created At**: {now.strftime("%Y-%m-%dT%H:%M:%SZ")}
- **Status**: RUNNING
- **Project Context**: `{project_id}`

---

## 🎯 1. Objective & Requirements
{objective}

## 🤖 2. Agent Swarm & Execution Plan
*Initializing plan...*

## ⚡ 3. Actions & Tool Invocations
- [{now.strftime('%H:%M:%S')}] Task initialized.

## 📦 4. Generated Artifacts
*(No artifacts generated yet)*

## 📝 5. Outcome & Verification
*Task in progress...*
"""
        with open(task_memory_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        self._active_task_id = task_id
        return task_id

    def get_task_dir(self, task_id: str) -> str:
        return os.path.join(self.tasks_dir, task_id)

    def get_task_artifacts_dir(self, task_id: str) -> str:
        d = os.path.join(self.tasks_dir, task_id, "artifacts")
        os.makedirs(d, exist_ok=True)
        return d

    def record_plan(self, task_id: str, stages_desc: List[str], objective: Optional[str] = None, project_id: Optional[str] = None) -> None:
        """Updates Section 2 of task_memory.md with the decomposed plan."""
        task_folder = os.path.join(self.tasks_dir, task_id)
        memory_path = os.path.join(task_folder, "task_memory.md")
        
        plan_text = "## 🤖 2. Agent Swarm & Execution Plan\n" + "\n".join([f"- {s}" for s in stages_desc]) + "\n"
        if os.path.exists(memory_path):
            with open(memory_path, "r", encoding="utf-8") as f:
                content = f.read()
            updated = re.sub(r"## 🤖 2\. Agent Swarm & Execution Plan.*?(?=## ⚡ 3\.|\Z)", plan_text + "\n", content, flags=re.DOTALL)
            with open(memory_path, "w", encoding="utf-8") as f:
                f.write(updated)

    def record_action(self, task_id: str, agent_role: str, tool_name: str, args: dict, result_summary: str) -> None:
        """Appends an executed tool action to Section 3 of task_memory.md."""
        task_folder = os.path.join(self.tasks_dir, task_id)
        now_ts = datetime.utcnow().strftime("%H:%M:%S")
        action_line = f"- [{now_ts}] **{agent_role}** → `{tool_name}({json.dumps(args)})` → {result_summary}\n"
        
        p = os.path.join(task_folder, "task_memory.md")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            sec3_match = re.search(r"(## ⚡ 3\. Actions & Tool Invocations\n)(.*?)(?=## 📦 4\.|\Z)", content, re.DOTALL)
            if sec3_match:
                existing = sec3_match.group(2)
                updated_sec = existing + action_line
                updated = content[:sec3_match.start(2)] + updated_sec + content[sec3_match.end(2):]
                with open(p, "w", encoding="utf-8") as f:
                    f.write(updated)

    def record_artifact(self, task_id: str, artifact_path: str) -> None:
        """Appends a generated deliverable file to Section 4 of task_memory.md."""
        task_folder = os.path.join(self.tasks_dir, task_id)
        rel_p = os.path.relpath(artifact_path, self.root_dir) if os.path.isabs(artifact_path) else artifact_path
        artifact_line = f"- [`{os.path.basename(rel_p)}`]({rel_p})\n"
        
        p = os.path.join(task_folder, "task_memory.md")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            sec4_match = re.search(r"(## 📦 4\. Generated Artifacts\n)(.*?)(?=## 📝 5\.|\Z)", content, re.DOTALL)
            if sec4_match:
                existing = sec4_match.group(2).replace("*(No artifacts generated yet)*\n", "").replace("*(No artifacts generated yet)*", "")
                updated_sec = existing + artifact_line
                updated = content[:sec4_match.start(2)] + updated_sec + content[sec4_match.end(2):]
                with open(p, "w", encoding="utf-8") as f:
                    f.write(updated)

    def complete_task(self, task_id: str, outcome_summary: str, is_success: bool = True, artifacts: Optional[List[str]] = None, project_id: Optional[str] = None) -> None:
        """
        Marks task as COMPLETED in task_memory.md and syncs a receipt to Tier 2 Episodic Memory.
        """
        task_folder = os.path.join(self.tasks_dir, task_id)
        status_str = "COMPLETED" if is_success else "FAILED"
        outcome_block = f"## 📝 5. Outcome & Verification\n**Status**: {status_str}\n\n{outcome_summary}\n"
        
        p = os.path.join(task_folder, "task_memory.md")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            content = re.sub(r"- \*\*Status\*\*:\s*[A-Z_]+", f"- **Status**: {status_str}", content)
            content = re.sub(r"## 📝 5\. Outcome & Verification.*?\Z", outcome_block, content, flags=re.DOTALL)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)

        # Sync to Tier 2 Episodic Memory (memory/episodic.json)
        try:
            from nava.memory.store import EpisodicMemoryStore
            from nava.core.schemas import MemoryRecord, MemoryTier, MemoryTrustLevel
            epi_path = os.path.join(self.root_dir, "memory", "episodic.json")
            epi_store = EpisodicMemoryStore(epi_path)
            record = MemoryRecord(
                memory_id=f"epi-{task_id}",
                tier=MemoryTier.EPISODIC,
                content={
                    "task_id": task_id,
                    "status": "COMPLETED" if is_success else "FAILED",
                    "outcome": outcome_summary,
                    "artifacts": artifacts or [],
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                },
                source="task_manager",
                confidence=1.0,
                importance=0.8,
                sensitivity="low",
                trust_level=MemoryTrustLevel.VERIFIED if is_success else MemoryTrustLevel.UNVERIFIED,
                provenance=[f"task:{task_id}"]
            )
            epi_store.store(record)
        except Exception as e:
            print(f"[TaskManager] Note: Could not sync to episodic memory: {e}")

    def list_tasks(self) -> List[Dict[str, Any]]:
        """Lists all existing tasks in reverse chronological order."""
        if not os.path.exists(self.tasks_dir):
            return []
            
        tasks = []
        for item in os.listdir(self.tasks_dir):
            task_p = os.path.join(self.tasks_dir, item)
            mem_p = os.path.join(task_p, "task_memory.md")
            if os.path.isdir(task_p) and os.path.exists(mem_p):
                try:
                    with open(mem_p, "r", encoding="utf-8") as f:
                        txt = f.read()
                    status_m = re.search(r"- \*\*Status\*\*:\s*([A-Z_]+)", txt)
                    status = status_m.group(1) if status_m else "UNKNOWN"
                    obj_m = re.search(r"# 📋 Task Memory:\s*(.+)", txt)
                    objective = obj_m.group(1).strip() if obj_m else item
                    tasks.append({
                        "task_id": item,
                        "objective": objective,
                        "status": status,
                        "path": mem_p
                    })
                except Exception:
                    pass
                    
        tasks.sort(key=lambda t: t["task_id"], reverse=True)
        return tasks

    def get_task_memory(self, task_id: str) -> Optional[str]:
        mem_p = os.path.join(self.tasks_dir, task_id, "task_memory.md")
        if os.path.exists(mem_p):
            with open(mem_p, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def resume_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Sets an existing task as the active task session, loading its context and artifacts."""
        task_folder = os.path.join(self.tasks_dir, task_id)
        mem_p = os.path.join(task_folder, "task_memory.md")
        if not os.path.exists(mem_p):
            # Check for partial prefix match
            for item in os.listdir(self.tasks_dir):
                if item.startswith(task_id):
                    task_id = item
                    task_folder = os.path.join(self.tasks_dir, item)
                    mem_p = os.path.join(task_folder, "task_memory.md")
                    break
                    
        if os.path.exists(mem_p):
            self._active_task_id = task_id
            with open(mem_p, "r", encoding="utf-8") as f:
                content = f.read()
            return {"task_id": task_id, "memory": content}
        return None


class ProjectWorkspace:
    """
    Manages long-term Project-scoped context inside `projects/<project_name>/project_memory.md`.
    Contains codebase architecture, tech stack, and architectural decisions.
    """
    def __init__(self, root_dir: Optional[str] = None, project_name: Optional[str] = None):
        self.root_dir = os.path.abspath(root_dir or os.getcwd())
        self.project_name = project_name or os.path.basename(self.root_dir)
        self.projects_dir = os.path.join(self.root_dir, "projects", self.project_name)
        self.memory_path = os.path.join(self.projects_dir, "project_memory.md")
        self.indexer = ProjectIndexer(self.root_dir)
        self.task_manager = TaskManager(self.root_dir)
        
        os.makedirs(self.projects_dir, exist_ok=True)

    def initialize_project_memory(self, project_goal: Optional[str] = None, force: bool = False) -> str:
        """Creates or updates `projects/<project_name>/project_memory.md`."""
        target_path = self.memory_path
        if os.path.exists(target_path) and not force:
            return self.read_memory()

        summary = self.indexer.get_summary()
        tech_stack_str = ", ".join(summary.get("tech_stack", [])) or "General / Polyglot"
        goal_str = project_goal or f"Autonomous workspace execution for {self.project_name}."

        content = f"""# 📌 Project Workspace Memory: {self.project_name}

## 🎯 1. Project Overview & Architecture
- **Project Name**: {self.project_name}
- **Root Directory**: `{self.root_dir}`
- **Primary Goal**: {goal_str}
- **Tech Stack**: {tech_stack_str}
- **Total Indexed Files**: {summary.get("total_files", 0)}

## 📝 2. Architectural Decisions & Constraints
- *Decision 1*: All file mutations are governed by NAVA Action Gateway and concurrency locks.
- *Decision 2*: All task deliverables and outputs are created inside their respective task's artifacts directory.
- *Constraint 1*: Operations must remain confined within the workspace root.
"""
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return content

    def read_memory(self) -> str:
        """Reads project_memory.md."""
        if os.path.exists(self.memory_path):
            with open(self.memory_path, "r", encoding="utf-8") as f:
                return f.read()
        return self.initialize_project_memory()

    def append_decision(self, decision_text: str) -> None:
        """Appends an architectural decision to Section 2."""
        content = self.read_memory()
        sec_match = re.search(r"(## 📝 2\. Architectural Decisions & Constraints\n)(.*?)(?=\Z)", content, re.DOTALL)
        if sec_match:
            existing = sec_match.group(2).strip()
            updated_sec = f"{existing}\n- *Decision*: {decision_text}\n"
            updated = content[:sec_match.start(2)] + updated_sec
        else:
            updated = content + f"\n## 📝 2. Architectural Decisions & Constraints\n- *Decision*: {decision_text}\n"
            
        with open(self.memory_path, "w", encoding="utf-8") as f:
            f.write(updated)

    def sync_task_completion(self, task_id: str, objective: str, artifacts: Optional[List[str]] = None) -> None:
        """Syncs completed task deliverables, milestones, and indexed files into project_memory.md."""
        content = self.read_memory()
        
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        deliverable_str = "\n".join([f"  - `{a}`" for a in (artifacts or [])]) if artifacts else "  - (Project files saved in workspace)"
        
        entry = f"\n### ✅ Milestone: {objective}\n- **Task ID**: `{task_id}`\n- **Timestamp**: {now_str}\n- **Deliverables**:\n{deliverable_str}\n"
        
        if "## 📦 3. Project Milestones & Deliverables" in content:
            updated = content + entry
        else:
            updated = content + f"\n## 📦 3. Project Milestones & Deliverables\n{entry}"
            
        with open(self.memory_path, "w", encoding="utf-8") as f:
            f.write(updated)

    def get_resume_context(self) -> Optional[str]:
        """Returns project architecture decisions and recent task context."""
        content = self.read_memory()
        tasks = self.task_manager.list_tasks()
        ctx_parts = [f"[PROJECT ARCHITECTURE CONTEXT: {self.project_name}]"]
        if "## 📝 2. Architectural Decisions" in content or "## 📝 3. Architectural Decisions" in content:
            sec_match = re.search(r"## 📝 [0-9]\. Architectural Decisions.*?\Z", content, re.DOTALL)
            if sec_match:
                ctx_parts.append(sec_match.group(0).strip())
        if tasks:
            latest = tasks[0]
            ctx_parts.append(f"[LATEST TASK CONTEXT]\nTask: {latest['objective']}\nStatus: {latest['status']}")
        return "\n\n".join(ctx_parts)

    def list_projects(self) -> List[str]:
        """Lists all existing projects in projects/."""
        base_projects_dir = os.path.join(self.root_dir, "projects")
        if not os.path.exists(base_projects_dir):
            return [self.project_name]
            
        projects = []
        for item in os.listdir(base_projects_dir):
            p = os.path.join(base_projects_dir, item)
            if os.path.isdir(p) and os.path.exists(os.path.join(p, "project_memory.md")):
                projects.append(item)
                
        if self.project_name not in projects:
            projects.append(self.project_name)
            
        return sorted(projects)

    def create_project(self, project_name: str, project_goal: Optional[str] = None) -> str:
        """Creates a brand new project and initializes its project_memory.md."""
        clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', project_name).strip('_')
        self.project_name = clean_name
        self.projects_dir = os.path.join(self.root_dir, "projects", self.project_name)
        self.memory_path = os.path.join(self.projects_dir, "project_memory.md")
        os.makedirs(self.projects_dir, exist_ok=True)
        return self.initialize_project_memory(project_goal=project_goal, force=True)

    def switch_project(self, project_name: str) -> bool:
        """Switches the active project context."""
        clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', project_name).strip('_')
        self.project_name = clean_name
        self.projects_dir = os.path.join(self.root_dir, "projects", self.project_name)
        self.memory_path = os.path.join(self.projects_dir, "project_memory.md")
        os.makedirs(self.projects_dir, exist_ok=True)
        if not os.path.exists(self.memory_path):
            self.initialize_project_memory()
        return True

    def get_welcome_back_message(self) -> Optional[str]:
        """Returns startup greeting summarizing active project and recent task status."""
        tasks = self.task_manager.list_tasks()
        if not tasks:
            return None
            
        latest_task = tasks[0]
        return f"""┌────────────────────────────────────────────────────────────────────────┐
│ 🧠 [WORKSPACE CONTEXT CONTINUITY]                                     │
├────────────────────────────────────────────────────────────────────────┤
│ Project: {self.project_name[:58]}
│ Recent Task: {latest_task['objective'][:52]}
│ Status: {latest_task['status'][:58]}
│                                                                        │
│ 👉 Type '+ New' or 'new' to start a fresh clean task session.         │
│ 👉 Type 'tasks' to view all past task memories.                        │
│ 👉 Type 'projects' or 'project new <name>' to manage projects.        │
└────────────────────────────────────────────────────────────────────────┘"""
