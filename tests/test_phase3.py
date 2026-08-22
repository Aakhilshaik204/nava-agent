import pytest
import datetime
import os
import tempfile
from nava.core.schemas import MemoryRecord, MemoryTier, MemoryTrustLevel, MemoryConflictState
from nava.memory.store import ProfileMemoryStore, EpisodicMemoryStore

def test_profile_memory_hard_rule():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "profile.json")
        store = ProfileMemoryStore(path)

        # 1. Store a verified record explicitly
        r1 = MemoryRecord(
            memory_id="1", tier=MemoryTier.PROFILE, content="trusted:alice", source="user",
            confidence=1.0, importance=1.0, sensitivity="low", trust_level=MemoryTrustLevel.VERIFIED
        )
        store.store(r1, explicit_user_action=True)

        # 2. Try to store a conflicting UNVERIFIED record (should flag conflict, NOT overwrite)
        r2 = MemoryRecord(
            memory_id="1", tier=MemoryTier.PROFILE, content="trusted:bob", source="agent",
            confidence=1.0, importance=1.0, sensitivity="low", trust_level=MemoryTrustLevel.UNVERIFIED
        )
        store.store(r2, explicit_user_action=False)
        
        # Reload and check
        loaded = store.retrieve("trusted")
        assert len(loaded) == 1
        assert loaded[0].content == "trusted:alice" # Still Alice
        assert loaded[0].conflict_state == MemoryConflictState.CONFLICT_DETECTED

        # 3. Try to inject a VERIFIED record without explicit_user_action (should demote to UNVERIFIED)
        r3 = MemoryRecord(
            memory_id="2", tier=MemoryTier.PROFILE, content="trusted:charlie", source="agent",
            confidence=1.0, importance=1.0, sensitivity="low", trust_level=MemoryTrustLevel.VERIFIED
        )
        store.store(r3, explicit_user_action=False)
        
        loaded3 = store.retrieve("charlie")
        assert len(loaded3) == 1
        assert loaded3[0].trust_level == MemoryTrustLevel.UNVERIFIED

def test_episodic_ttl():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "episodic.json")
        store = EpisodicMemoryStore(path)
        
        # Store an expired record
        expired_r = MemoryRecord(
            memory_id="1", tier=MemoryTier.EPISODIC, content="failed task", source="system",
            confidence=1.0, importance=0.5, sensitivity="low",
            expiration=datetime.datetime.utcnow() - datetime.timedelta(days=1)
        )
        store.store(expired_r)
        
        # Store a valid record
        valid_r = MemoryRecord(
            memory_id="2", tier=MemoryTier.EPISODIC, content="success task", source="system",
            confidence=1.0, importance=0.5, sensitivity="low",
            expiration=datetime.datetime.utcnow() + datetime.timedelta(days=1)
        )
        store.store(valid_r)
        
        # Instantiate a new store to trigger _load filter
        store2 = EpisodicMemoryStore(path)
        
        matches = store2.retrieve("task")
        assert len(matches) == 1
        assert matches[0].memory_id == "2"
