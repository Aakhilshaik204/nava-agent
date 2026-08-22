import os
import glob
import json
import hashlib
from typing import Dict, List, Optional
from pydantic import BaseModel
from enum import Enum
from datetime import datetime

class SkillTrustState(str, Enum):
    TRUSTED = "TRUSTED"
    UNTRUSTED_NEW = "UNTRUSTED_NEW"
    UNTRUSTED_MODIFIED = "UNTRUSTED_MODIFIED"

class SkillDefinition(BaseModel):
    name: str
    description: str
    filepath: str
    content: str
    trust_state: SkillTrustState = SkillTrustState.UNTRUSTED_NEW

class SkillManager:
    def __init__(self, search_paths: Optional[List[str]] = None, ledger_path: str = "memory/trusted_plugins.json"):
        self.skills: Dict[str, SkillDefinition] = {}
        # Default search paths: local workspace and user home
        self.search_paths = search_paths or [
            os.path.join(os.getcwd(), ".nava", "skills"),
            os.path.expanduser("~/.nava/skills")
        ]
        self.ledger_path = ledger_path
        self.ledger: Dict[str, dict] = {}
        self._load_ledger()
        self.refresh_skills()

    def _load_ledger(self):
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    self.ledger = json.load(f)
            except Exception as e:
                print(f"[SkillManager] Failed to load trusted ledger: {e}")
                self.ledger = {}
        else:
            self.ledger = {}

    def _save_ledger(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.ledger_path)), exist_ok=True)
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            json.dump(self.ledger, f, indent=2)

    def approve_skill(self, name: str, approved_by: str = "local_user"):
        """Approves a skill, hashing its current disk content and saving to the ledger."""
        if name not in self.skills:
            raise ValueError(f"Skill '{name}' not found on disk.")
        
        skill = self.skills[name]
        with open(skill.filepath, "r", encoding="utf-8") as f:
            raw_content = f.read()
            
        file_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
        
        self.ledger[name] = {
            "hash": file_hash,
            "last_trusted_content": raw_content,
            "approved_at": datetime.utcnow().isoformat(),
            "approved_by": approved_by
        }
        self._save_ledger()
        skill.trust_state = SkillTrustState.TRUSTED
        print(f"[SkillManager] Skill '{name}' approved and hash-locked.")

    def get_ledger_content(self, name: str) -> Optional[str]:
        """Returns the last trusted content for diffing."""
        if name in self.ledger:
            return self.ledger[name].get("last_trusted_content")
        return None

    def refresh_skills(self):
        """Scans directories for SKILL.md files and parses them."""
        self.skills.clear()
        self._load_ledger()
        
        for base_path in self.search_paths:
            if not os.path.exists(base_path):
                continue
                
            # Find all SKILL.md files in subdirectories
            search_pattern = os.path.join(base_path, "**", "SKILL.md")
            skill_files = glob.glob(search_pattern, recursive=True)
            
            for filepath in skill_files:
                self._load_skill(filepath)

    def _load_skill(self, filepath: str):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw_content = f.read()
                
            file_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
                
            # Basic frontmatter parser (handles --- block at the top)
            name = os.path.basename(os.path.dirname(filepath)) # Default name is folder name
            description = "No description provided."
            content = raw_content
            
            lines = raw_content.split("\n")
            if lines and lines[0].strip() == "---":
                end_idx = -1
                for i in range(1, len(lines)):
                    if lines[i].strip() == "---":
                        end_idx = i
                        break
                
                if end_idx != -1:
                    frontmatter = lines[1:end_idx]
                    content = "\n".join(lines[end_idx+1:]).strip()
                    
                    for line in frontmatter:
                        if ":" in line:
                            k, v = line.split(":", 1)
                            k = k.strip().lower()
                            v = v.strip()
                            # remove quotes if any
                            if v.startswith("'") and v.endswith("'"): v = v[1:-1]
                            if v.startswith('"') and v.endswith('"'): v = v[1:-1]
                            
                            if k == "name":
                                name = v
                            elif k == "description":
                                description = v
                                
            # Determine Trust State
            trust_state = SkillTrustState.UNTRUSTED_NEW
            if name in self.ledger:
                if self.ledger[name].get("hash") == file_hash:
                    trust_state = SkillTrustState.TRUSTED
                else:
                    trust_state = SkillTrustState.UNTRUSTED_MODIFIED

            self.skills[name] = SkillDefinition(
                name=name,
                description=description,
                filepath=filepath,
                content=content,
                trust_state=trust_state
            )
        except Exception as e:
            print(f"[SkillManager] Failed to load skill at {filepath}: {e}")

    def get_trusted_skills(self) -> List[SkillDefinition]:
        """Returns all skills currently in TRUSTED state."""
        return [s for s in self.skills.values() if s.trust_state == SkillTrustState.TRUSTED]

    def get_catalog_string(self) -> str:
        """Returns a concise catalog of trusted skills for planning context."""
        trusted = self.get_trusted_skills()
        if not trusted:
            return "No trusted skills currently registered."
        lines = []
        for s in trusted:
            lines.append(f"- {s.name}: {s.description}")
        return "\n".join(lines)

    def export_skill_prompt_context(self) -> str:
        """Returns formatted string of trusted skills for injection into planning or dynamic reasoning contexts."""
        trusted = self.get_trusted_skills()
        if not trusted:
            return ""
        blocks = ["\n[APPROVED USER SKILLS]"]
        for s in trusted:
            blocks.append(f"- Skill: {s.name}\n  Description: {s.description}\n  Instructions:\n  {s.content}\n")
        return "\n".join(blocks)

    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        return self.skills.get(name)

    def get_all_skills(self) -> Dict[str, SkillDefinition]:
        return self.skills

