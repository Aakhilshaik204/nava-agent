import json
import os
import re
import uuid
import hashlib
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from nava.core.schemas import MemoryRecord, MemoryTier, MemoryTrustLevel, MemoryConflictState

class MemoryStore(ABC):
    @abstractmethod
    def store(self, record: MemoryRecord) -> None:
        pass
        
    @abstractmethod
    def retrieve(self, query: str, limit: int = 10) -> List[MemoryRecord]:
        pass
        
    @abstractmethod
    def delete(self, memory_id: str) -> None:
        pass

class WorkingMemoryStore(MemoryStore):
    """Tier 1: Ephemeral task-scoped working memory scratchpad."""
    def __init__(self):
        self._records: Dict[str, MemoryRecord] = {}
        
    def store(self, record: MemoryRecord) -> None:
        self._records[record.memory_id] = record
        
    def retrieve(self, query: str, limit: int = 10) -> List[MemoryRecord]:
        matches = [r for r in self._records.values() if query.lower() in str(r.content).lower()]
        return matches[:limit]
        
    def delete(self, memory_id: str) -> None:
        self._records.pop(memory_id, None)
        
    def clear(self) -> None:
        self._records.clear()

class PersistentJSONStore(MemoryStore):
    """Base class for persistent JSON array storage."""
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._records: Dict[str, MemoryRecord] = {}
        self._load()
        
    def _load(self):
        if not os.path.exists(self.filepath):
            return
        with open(self.filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                for item in data:
                    record = MemoryRecord(**item)
                    # Filter out expired records on load
                    if record.expiration and record.expiration < datetime.utcnow():
                        continue
                    self._records[record.memory_id] = record
            except Exception as e:
                print(f"[PersistentJSONStore] Error loading {self.filepath}: {e}")
                self._records = {}
                
    def _save(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.filepath)), exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            data = [json.loads(r.model_dump_json()) for r in self._records.values()]
            json.dump(data, f, indent=2)

    def store(self, record: MemoryRecord) -> None:
        record.updated_at = datetime.utcnow()
        self._records[record.memory_id] = record
        self._save()

    def retrieve(self, query: str, limit: int = 10) -> List[MemoryRecord]:
        terms = [t.lower() for t in query.split() if len(t) > 2]
        scored = []
        for r in self._records.values():
            text = str(r.content).lower()
            score = sum(1 for term in terms if term in text)
            if score > 0 or query.lower() in text:
                scored.append((score + (1 if query.lower() in text else 0), r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:limit]]

    def get_recent(self, limit: int = 5) -> List[MemoryRecord]:
        sorted_records = sorted(self._records.values(), key=lambda r: r.updated_at or r.created_at, reverse=True)
        return sorted_records[:limit]

    def delete(self, memory_id: str) -> None:
        if memory_id in self._records:
            del self._records[memory_id]
            self._save()

    def promote_to_verified(self, memory_id: str) -> bool:
        """Section 31.2: Explicit user promotion of an UNVERIFIED memory to VERIFIED."""
        if memory_id in self._records:
            rec = self._records[memory_id]
            rec.trust_level = MemoryTrustLevel.VERIFIED
            rec.conflict_state = MemoryConflictState.RESOLVED
            rec.updated_at = datetime.utcnow()
            self._save()
            return True
        return False

    def resolve_conflict(self, memory_id: str, chosen_content: Any) -> bool:
        """Allows user to explicitly resolve a CONFLICT_DETECTED memory record."""
        if memory_id in self._records:
            rec = self._records[memory_id]
            rec.content = chosen_content
            rec.trust_level = MemoryTrustLevel.VERIFIED
            rec.conflict_state = MemoryConflictState.RESOLVED
            rec.updated_at = datetime.utcnow()
            self._save()
            return True
        return False

class EpisodicMemoryStore(PersistentJSONStore):
    """Tier 2: Experience-based ledger tracking task execution trajectories and failures."""
    pass

class SemanticMemoryStore(PersistentJSONStore):
    """
    Tier 3: Unstructured Knowledge & RAG memory store.
    Supports document chunking, provenance metadata grounding, and ranked retrieval.
    """
    def ingest_document(
        self,
        doc_id: str,
        title: str,
        text: str,
        source: str = "workspace",
        chunk_size: int = 300,
        overlap: int = 50,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[MemoryRecord]:
        """
        Chunks text into semantic blocks and stores them with grounding metadata.
        """
        words = text.split()
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text = " ".join(words[start:end])
            chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:12]
            
            chunk_record = MemoryRecord(
                memory_id=f"sem-{doc_id}-{chunk_index}-{chunk_hash}",
                tier=MemoryTier.SEMANTIC,
                content={
                    "doc_id": doc_id,
                    "title": title,
                    "chunk_index": chunk_index,
                    "text": chunk_text,
                    "source": source,
                    "metadata": metadata or {}
                },
                source=source,
                confidence=1.0,
                importance=0.7,
                sensitivity="low",
                trust_level=MemoryTrustLevel.VERIFIED if source in ["user", "admin"] else MemoryTrustLevel.UNVERIFIED,
                provenance=[f"doc:{doc_id}", f"source:{source}"]
            )
            self.store(chunk_record)
            chunks.append(chunk_record)
            
            chunk_index += 1
            start += (chunk_size - overlap)
            if start >= len(words) or end == len(words):
                break
                
        return chunks

class ProfileMemoryStore(PersistentJSONStore):
    """Tier 4: AI Twin structured facts. Enforces strict Section 31.2 Trust Escalation rules."""
    def __init__(self, filepath: str = "memory/profile.json"):
        super().__init__(filepath)
    
    def store(self, record: MemoryRecord, explicit_user_action: bool = False) -> None:
        # Section 31.2 Hard Rule: Inferred content can NEVER automatically upgrade to VERIFIED.
        existing = self._records.get(record.memory_id)
        
        if existing and existing.trust_level == MemoryTrustLevel.VERIFIED:
            # Cannot silently overwrite VERIFIED facts
            if not explicit_user_action:
                if str(existing.content) != str(record.content):
                    # Flag conflict instead of overwriting
                    existing.conflict_state = MemoryConflictState.CONFLICT_DETECTED
                    existing.updated_at = datetime.utcnow()
                    self._save()
                return # Block silent overwrite
                
        if record.trust_level == MemoryTrustLevel.VERIFIED and not explicit_user_action:
            # Force demotion if trying to store as verified without user action
            record.trust_level = MemoryTrustLevel.UNVERIFIED
            
        super().store(record)
