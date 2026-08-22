import os
import shutil
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from nava.core.schemas import ToolRequest

class StateSnapshot:
    def __init__(self, resource_ref: str, content_ref: Optional[str] = None):
        self.snapshot_id = str(uuid.uuid4())
        self.resource_ref = resource_ref
        self.content_ref = content_ref
        self.captured_at = datetime.utcnow()

class DefaultStateObserver:
    """
    Captures BEFORE and AFTER state snapshots for reversible actions (e.g. file writes).
    Saves snapshot data to .nava/snapshots/.
    """
    def __init__(self, snapshot_dir: str = ".nava/snapshots"):
        self.snapshot_dir = snapshot_dir
        os.makedirs(self.snapshot_dir, exist_ok=True)

    def capture_before(self, request: ToolRequest) -> Optional[StateSnapshot]:
        if request.tool_name in ["file.write", "code.replace_content"]:
            # Extract target file path
            file_path = request.arguments.get("file_path") or request.arguments.get("target_file") or request.arguments.get("filename")
            
            if file_path and os.path.exists(file_path):
                # Copy file to snapshot dir
                snap_id = str(uuid.uuid4())
                snap_path = os.path.join(self.snapshot_dir, snap_id)
                shutil.copy2(file_path, snap_path)
                return StateSnapshot(resource_ref=file_path, content_ref=snap_path)
            elif file_path:
                # File doesn't exist yet, so BEFORE state is effectively "empty/nonexistent"
                return StateSnapshot(resource_ref=file_path, content_ref=None)
        
        return None

    def observe(self, request: ToolRequest, result: Any, pre_snapshot: Optional[StateSnapshot] = None) -> Dict[str, Any]:
        """
        Return the observation, including pre_snapshot reference so it can be stored in the Receipt.
        """
        observation = {}
        if pre_snapshot:
            observation["pre_snapshot_id"] = pre_snapshot.snapshot_id
            observation["pre_resource"] = pre_snapshot.resource_ref
            observation["pre_content"] = pre_snapshot.content_ref
        return observation
