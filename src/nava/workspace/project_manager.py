import os
import re
import shutil
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from nava.workspace.indexer import ProjectIndexer

class ProjectWorkspace:
    """
    Manages project-scoped context, workspace indexing, and persistent `.nava/project_memory.md`.
    Provides autonomous context continuity across sessions ("Continue where we left off")
    and snapshot restore points in `.nava/checkpoints/`.
    """
    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = os.path.abspath(root_dir or os.getcwd())
        self.nava_dir = os.path.join(self.root_dir, ".nava")
        self.checkpoints_dir = os.path.join(self.nava_dir, "checkpoints")
        self.memory_path = os.path.join(self.nava_dir, "project_memory.md")
        self.indexer = ProjectIndexer(self.root_dir)
        os.makedirs(self.nava_dir, exist_ok=True)
        os.makedirs(self.checkpoints_dir, exist_ok=True)

    def initialize_project_memory(self, project_goal: Optional[str] = None, force: bool = False) -> str:
        """
        Creates or updates the `.nava/project_memory.md` file based on project analysis.
        """
        if os.path.exists(self.memory_path) and not force:
            return self.read_memory()

        summary = self.indexer.get_summary()
        tech_stack_str = ", ".join(summary.get("tech_stack", [])) or "General / Polyglot"
        folder_name = os.path.basename(self.root_dir)
        goal_str = project_goal or f"Autonomous workspace execution for {folder_name}."

        content = f"""# 📌 Project Workspace Memory

## 🎯 1. Project Overview & Architecture
- **Project Name**: {folder_name}
- **Root Directory**: `{self.root_dir}`
- **Primary Goal**: {goal_str}
- **Tech Stack**: {tech_stack_str}
- **Total Indexed Files**: {summary.get("total_files", 0)}

## 📍 2. Current Execution State (Live Checkpoint)
- **Active Objective**: None (Initialized)
- **Last Active Agent**: None
- **Timestamp**: {datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
- **Status**: INITIALIZED / READY_FOR_TASKS
- **Touched Files**: []

## 📝 3. Architectural Decisions & Constraints
- *Decision 1*: All file mutations are governed by NAVA Action Gateway and concurrency locks.
- *Constraint 1*: Operations must remain confined within the workspace root.

## ⏳ 4. Resume Queue (Next Immediate Steps)
1. [ ] Awaiting first objective from user.
"""
        with open(self.memory_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return content

    def read_memory(self) -> str:
        """Reads the current contents of `.nava/project_memory.md`."""
        if not os.path.exists(self.memory_path):
            return self.initialize_project_memory()
        try:
            with open(self.memory_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading project memory: {e}"

    def save_checkpoint(
        self, 
        task_id: str, 
        objective: str, 
        last_agent: str, 
        touched_files: List[str], 
        next_steps: Optional[List[str]] = None,
        status: str = "READY_TO_RESUME",
        decisions: Optional[List[str]] = None,
        create_snapshot: bool = True
    ) -> None:
        """
        Saves a structured execution checkpoint to `.nava/project_memory.md`
        and optionally creates a snapshot backup in `.nava/checkpoints/`.
        """
        existing_content = self.read_memory()
        
        # Prepare Next Steps
        steps_list = next_steps or [f"Continue next phase of: {objective}"]
        formatted_steps = "\n".join([f"{i+1}. [ ] {step}" for i, step in enumerate(steps_list)])
        
        # Format Checkpoint Block
        touched_str = str(touched_files)
        now_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        checkpoint_block = f"""## 📍 2. Current Execution State (Live Checkpoint)
- **Active Objective**: {objective}
- **Last Active Agent**: {last_agent} ({task_id})
- **Timestamp**: {now_ts}
- **Status**: {status}
- **Touched Files**: {touched_str}"""

        resume_block = f"""## ⏳ 4. Resume Queue (Next Immediate Steps)
{formatted_steps}"""

        # Replace Section 2 in markdown
        sec2_pattern = re.compile(r"## 📍 2\. Current Execution State.*?(?=## 📝 3\.|\Z)", re.DOTALL)
        if sec2_pattern.search(existing_content):
            updated = sec2_pattern.sub(checkpoint_block + "\n\n", existing_content)
        else:
            updated = existing_content + "\n\n" + checkpoint_block

        # Replace Section 4 in markdown
        sec4_pattern = re.compile(r"## ⏳ 4\. Resume Queue.*?\Z", re.DOTALL)
        if sec4_pattern.search(updated):
            updated = sec4_pattern.sub(resume_block, updated)
        else:
            updated = updated + "\n\n" + resume_block

        # Append any new decisions
        if decisions:
            for d in decisions:
                updated = self._append_decision_to_text(updated, d)

        try:
            with open(self.memory_path, "w", encoding="utf-8") as f:
                f.write(updated)
        except Exception as e:
            print(f"[ProjectWorkspace] Warning: Failed to write checkpoint: {e}")

        # Create file snapshot in .nava/checkpoints/
        if create_snapshot and touched_files:
            self.create_file_snapshot(task_id, touched_files)

    def create_file_snapshot(self, snapshot_id: str, file_paths: List[str]) -> str:
        """Copies touched files into `.nava/checkpoints/<snapshot_id>/` for fast rollback."""
        snap_dir = os.path.join(self.checkpoints_dir, snapshot_id)
        os.makedirs(snap_dir, exist_ok=True)
        
        manifest = {
            "snapshot_id": snapshot_id,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files": []
        }
        
        for fp in file_paths:
            abs_p = os.path.abspath(fp) if os.path.isabs(fp) else os.path.abspath(os.path.join(self.root_dir, fp))
            if os.path.exists(abs_p) and os.path.isfile(abs_p):
                rel_p = os.path.relpath(abs_p, self.root_dir)
                dest = os.path.join(snap_dir, rel_p.replace("/", "_").replace("\\", "_"))
                shutil.copy2(abs_p, dest)
                manifest["files"].append({"original": rel_p, "backup": os.path.basename(dest)})
                
        with open(os.path.join(snap_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            
        return snap_dir

    def restore_file_snapshot(self, snapshot_id: str) -> bool:
        """Restores files from a previous snapshot."""
        snap_dir = os.path.join(self.checkpoints_dir, snapshot_id)
        manifest_p = os.path.join(snap_dir, "manifest.json")
        if not os.path.exists(manifest_p):
            return False
            
        with open(manifest_p, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
        for item in manifest.get("files", []):
            backup_p = os.path.join(snap_dir, item["backup"])
            orig_p = os.path.join(self.root_dir, item["original"])
            if os.path.exists(backup_p):
                os.makedirs(os.path.dirname(orig_p), exist_ok=True)
                shutil.copy2(backup_p, orig_p)
                
        return True

    def get_welcome_back_message(self) -> Optional[str]:
        """
        Returns a friendly startup greeting if an active checkpoint is ready to resume.
        """
        content = self.read_memory()
        if "None (Initialized)" in content:
            return None
            
        obj_match = re.search(r"- \*\*Active Objective\*\*:\s*(.+)", content)
        agent_match = re.search(r"- \*\*Last Active Agent\*\*:\s*(.+)", content)
        touched_match = re.search(r"- \*\*Touched Files\*\*:\s*(.+)", content)
        step_match = re.search(r"## ⏳ 4\. Resume Queue[^\n]*\n1\.\s*\[\s*\]\s*(.+)", content)
        
        objective = obj_match.group(1).strip() if obj_match else "Previous Task"
        agent = agent_match.group(1).strip() if agent_match else "Agent"
        touched = touched_match.group(1).strip() if touched_match else "[]"
        next_step = step_match.group(1).strip() if step_match else "Continue task"
        
        return f"""┌────────────────────────────────────────────────────────────────────────┐
│ 🧠 [WORKSPACE CONTEXT CONTINUITY]                                     │
├────────────────────────────────────────────────────────────────────────┤
│ Welcome back! Last session we were working on:                         │
│ 🎯 Objective: {objective[:56]}
│ 🤖 Agent: {agent[:58]}
│ 📂 Touched Files: {touched[:54]}
│ ⏳ Next Step: {next_step[:58]}
│                                                                        │
│ 👉 Type 'continue' to resume where you left off, or enter a new goal. │
└────────────────────────────────────────────────────────────────────────┘"""

    def get_active_objective(self) -> Optional[str]:
        """Returns the active objective from memory if present."""
        content = self.read_memory()
        obj_match = re.search(r"- \*\*Active Objective\*\*:\s*(.+)", content)
        if obj_match and "None (Initialized)" not in obj_match.group(1):
            return obj_match.group(1).strip()
        return None

    def append_decision(self, decision_text: str) -> None:
        """Appends an architectural decision or constraint to Section 3."""
        content = self.read_memory()
        updated = self._append_decision_to_text(content, decision_text)
        with open(self.memory_path, "w", encoding="utf-8") as f:
            f.write(updated)

    def _append_decision_to_text(self, text: str, decision: str) -> str:
        sec3_match = re.search(r"(## 📝 3\. Architectural Decisions & Constraints\n)(.*?)(?=## ⏳ 4\.|\Z)", text, re.DOTALL)
        if sec3_match:
            existing_decisions = sec3_match.group(2).strip()
            new_decision_line = f"- *Decision*: {decision}"
            updated_decisions = f"{existing_decisions}\n{new_decision_line}\n\n"
            return text[:sec3_match.start(2)] + updated_decisions + text[sec3_match.end(2):]
        return text

    def get_resume_context(self) -> Optional[str]:
        """
        Extracts recent checkpoint data from `.nava/project_memory.md` to inject into the planner.
        """
        content = self.read_memory()
        if "READY_TO_RESUME" not in content and "IN_PROGRESS" not in content:
            return None
            
        sec2_match = re.search(r"## 📍 2\. Current Execution State.*?(?=## 📝 3\.|\Z)", content, re.DOTALL)
        sec4_match = re.search(r"## ⏳ 4\. Resume Queue.*?\Z", content, re.DOTALL)
        
        ctx_parts = ["[PROJECT CONTINUITY CONTEXT]"]
        if sec2_match:
            ctx_parts.append(sec2_match.group(0).strip())
        if sec4_match:
            ctx_parts.append(sec4_match.group(0).strip())
            
        return "\n\n".join(ctx_parts)
