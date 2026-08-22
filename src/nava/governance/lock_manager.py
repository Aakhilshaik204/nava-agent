import time
import threading
import os
from enum import Enum
from typing import Dict, List, Optional, Any
from nava.core.schemas import ToolRequest
from nava.gateway.pipeline import ConcurrencyManager

class LockType(str, Enum):
    READ = "READ"
    WRITE = "WRITE"

class ResourceLock:
    def __init__(self):
        self.writer_ttl: Optional[float] = None
        self.writer_agent: Optional[str] = None
        self.reader_holders: List[dict] = [] # List of {"agent_id": str, "ttl": float}

    def cleanup(self, current_time: float):
        # Remove expired write lock
        if self.writer_ttl and current_time >= self.writer_ttl:
            self.writer_ttl = None
            self.writer_agent = None
        # Remove expired read locks
        self.reader_holders = [r for r in self.reader_holders if current_time < r["ttl"]]

    def release_agent(self, agent_id: str):
        if self.writer_agent == agent_id:
            self.writer_ttl = None
            self.writer_agent = None
        self.reader_holders = [r for r in self.reader_holders if r["agent_id"] != agent_id]

    def can_acquire(self, lock_type: LockType, requesting_agent: str) -> bool:
        if self.writer_agent is not None and self.writer_agent != requesting_agent:
            return False # Blocked by an active writer
        if lock_type == LockType.WRITE:
            # Blocked if there are active readers other than the requesting agent itself
            if any(r["agent_id"] != requesting_agent for r in self.reader_holders):
                return False
        return True

class DefaultLockManager(ConcurrencyManager):
    """
    Manages resource locks to prevent simultaneous overwrites by concurrent agents.
    Implements Section 15.3 Shared/Read and Exclusive/Write lock distinctions.
    """
    def __init__(self, lock_ttl_seconds: int = 30):
        self.locks: Dict[str, ResourceLock] = {}
        self.lock_ttl_seconds = lock_ttl_seconds
        self._lock = threading.RLock()

    def _normalize_uri(self, raw_uri: str) -> str:
        if not raw_uri:
            return ""
        try:
            return os.path.normpath(str(raw_uri)).replace("\\", "/")
        except Exception:
            return str(raw_uri)

    def _extract_uris(self, request: ToolRequest) -> List[str]:
        args = request.arguments or {}
        raw_uris = []
        
        if "filenames" in args and isinstance(args["filenames"], list):
            raw_uris.extend(args["filenames"])
        if "filename" in args and args["filename"]:
            raw_uris.append(args["filename"])
        if "file_path" in args and args["file_path"]:
            raw_uris.append(args["file_path"])
        if "path" in args and args["path"]:
            raw_uris.append(args["path"])
        if "target_file" in args and args["target_file"]:
            raw_uris.append(args["target_file"])
        if "source_file" in args and args["source_file"]:
            raw_uris.append(args["source_file"])
        if "directory" in args and args["directory"]:
            raw_uris.append(args["directory"])
        if "edits" in args and isinstance(args["edits"], list):
            for edit in args["edits"]:
                if isinstance(edit, dict) and "filename" in edit:
                    raw_uris.append(edit["filename"])
                    
        normalized = []
        for u in raw_uris:
            if u:
                norm = self._normalize_uri(u)
                if norm and norm not in normalized:
                    normalized.append(norm)
        return normalized

    def _infer_lock_type(self, request: ToolRequest) -> LockType:
        tool_str = (request.tool_name + " " + request.requested_scope).lower()
        write_keywords = ["write", "delete", "replace", "create", "execute", "append", "modify", "patch", "remove", "unlink", "drop"]
        if any(kw in tool_str for kw in write_keywords):
            return LockType.WRITE
        return LockType.READ

    def _is_path_conflict(self, uri1: str, uri2: str) -> bool:
        if uri1 == uri2:
            return True
        u1 = uri1.rstrip("/") + "/"
        u2 = uri2.rstrip("/") + "/"
        return u1.startswith(u2) or u2.startswith(u1)

    def check_locks(self, request: ToolRequest) -> bool:
        with self._lock:
            uris = self._extract_uris(request)
            if not uris:
                return True

            lock_type = self._infer_lock_type(request)
            current_time = time.time()
            agent_id = request.agent_id
            
            # Phase 1: Check if ALL requested URIs can be acquired
            for uri in uris:
                # Check exact match and hierarchy conflicts
                for existing_uri, existing_lock in self.locks.items():
                    existing_lock.cleanup(current_time)
                    if self._is_path_conflict(uri, existing_uri):
                        if not existing_lock.can_acquire(lock_type, agent_id):
                            return False

            # Phase 2: Acquire all locks atomically
            expiration = current_time + self.lock_ttl_seconds
            for uri in uris:
                if uri not in self.locks:
                    self.locks[uri] = ResourceLock()
                if lock_type == LockType.WRITE:
                    self.locks[uri].writer_ttl = expiration
                    self.locks[uri].writer_agent = agent_id
                else:
                    self.locks[uri].reader_holders.append({"agent_id": agent_id, "ttl": expiration})
                
            return True

    def release_lock(self, request: ToolRequest, agent_id: Optional[str] = None):
        """Releases locks for a specific tool request."""
        with self._lock:
            uris = self._extract_uris(request)
            target_agent = agent_id or request.agent_id
            for uri in uris:
                if uri in self.locks:
                    self.locks[uri].release_agent(target_agent)

    def release_all(self, agent_id: str):
        """Releases all locks held by a specific agent. Used during teardown."""
        with self._lock:
            for lock in self.locks.values():
                lock.release_agent(agent_id)

    def release_all_global(self):
        """
        Emergency Kill Switch (Section 31.4):
        Immediately flushes all active locks across all resources.
        """
        with self._lock:
            self.locks.clear()
            print("[DefaultLockManager] EMERGENCY STOP: All global locks flushed.")


