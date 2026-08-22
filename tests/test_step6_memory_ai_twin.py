import sys
import os

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import unittest
import tempfile
import datetime
from nava.core.schemas import MemoryRecord, MemoryTier, MemoryTrustLevel, MemoryConflictState
from nava.memory.store import (
    WorkingMemoryStore, EpisodicMemoryStore, SemanticMemoryStore, ProfileMemoryStore
)
from nava.memory.ai_twin import AITwinManager, UserPersona


class TestStep6MemoryAndAITwin(unittest.TestCase):
    def setUp(self):
        os.environ["NAVA_TEST_MODE"] = "1"
        self.tmpdir = tempfile.TemporaryDirectory()
        
        self.working_store = WorkingMemoryStore()
        self.episodic_store = EpisodicMemoryStore(os.path.join(self.tmpdir.name, "episodic.json"))
        self.semantic_store = SemanticMemoryStore(os.path.join(self.tmpdir.name, "semantic.json"))
        self.profile_store = ProfileMemoryStore(os.path.join(self.tmpdir.name, "profile.json"))
        
        self.ai_twin = AITwinManager(self.profile_store)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_four_tier_memory_stores_instantiation(self):
        """Verify all 4 memory tiers function with correct isolation."""
        # Tier 1: Working Memory
        w_rec = MemoryRecord(
            memory_id="work-1", tier=MemoryTier.WORKING, content={"temp_data": 123},
            source="agent", confidence=1.0, importance=0.5, sensitivity="low",
            trust_level=MemoryTrustLevel.UNVERIFIED, provenance=["test"]
        )
        self.working_store.store(w_rec)
        self.assertEqual(len(self.working_store.retrieve("temp_data")), 1)
        
        # Tier 2: Episodic Memory
        e_rec = MemoryRecord(
            memory_id="epi-1", tier=MemoryTier.EPISODIC, content={"event": "BUILD_PASS"},
            source="test_runner", confidence=1.0, importance=0.8, sensitivity="low",
            trust_level=MemoryTrustLevel.VERIFIED, provenance=["ci"]
        )
        self.episodic_store.store(e_rec)
        self.assertEqual(len(self.episodic_store.get_recent(limit=5)), 1)

    def test_semantic_memory_document_chunking_and_retrieval(self):
        """Tier 3: Document chunking, metadata grounding, and ranked RAG retrieval."""
        doc_text = "Nava is an autonomous personal agent operating system built on rigorous security boundaries. " * 30
        chunks = self.semantic_store.ingest_document(
            doc_id="nava-architecture-doc",
            title="NAVA Blueprint Summary",
            text=doc_text,
            source="user_upload",
            chunk_size=50,
            overlap=10
        )
        
        self.assertTrue(len(chunks) > 1)
        self.assertEqual(chunks[0].tier, MemoryTier.SEMANTIC)
        self.assertIn("doc:nava-architecture-doc", chunks[0].provenance)
        
        # Retrieve chunks
        matches = self.semantic_store.retrieve("rigorous security boundaries", limit=3)
        self.assertTrue(len(matches) > 0)
        self.assertIn("Nava is an autonomous", str(matches[0].content))

    def test_profile_memory_trust_escalation_blocked(self):
        """Section 31.2: Inferred agent content cannot silently become VERIFIED without explicit user action."""
        unverified_rec = MemoryRecord(
            memory_id="user-preferred-editor",
            tier=MemoryTier.PROFILE,
            content={"editor": "vim"},
            source="agent_inference",
            confidence=0.6,
            importance=0.8,
            sensitivity="low",
            trust_level=MemoryTrustLevel.VERIFIED, # Agent attempts to claim fact is VERIFIED
            provenance=["observed_terminal_command"]
        )
        
        # Storing without explicit_user_action=True MUST demote to UNVERIFIED
        self.profile_store.store(unverified_rec, explicit_user_action=False)
        stored = self.profile_store._records.get("user-preferred-editor")
        self.assertEqual(stored.trust_level, MemoryTrustLevel.UNVERIFIED)

    def test_profile_memory_conflict_detection(self):
        """Section 31.2: Divergent claims against a VERIFIED fact trigger CONFLICT_DETECTED state."""
        # 1. Establish verified fact
        fact = MemoryRecord(
            memory_id="user-primary-email",
            tier=MemoryTier.PROFILE,
            content={"email": "alice@primary.com"},
            source="user",
            confidence=1.0,
            importance=1.0,
            sensitivity="high",
            trust_level=MemoryTrustLevel.VERIFIED,
            provenance=["user_settings"]
        )
        self.profile_store.store(fact, explicit_user_action=True)
        
        # 2. Inferred conflicting fact comes from web scrape
        conflicting = MemoryRecord(
            memory_id="user-primary-email",
            tier=MemoryTier.PROFILE,
            content={"email": "malicious@attacker.com"},
            source="scraped_web_page",
            confidence=0.8,
            importance=1.0,
            sensitivity="high",
            trust_level=MemoryTrustLevel.UNVERIFIED,
            provenance=["web_scrape"]
        )
        self.profile_store.store(conflicting, explicit_user_action=False)
        
        # Fact must NOT be overwritten, and must be flagged as CONFLICT_DETECTED
        current = self.profile_store._records.get("user-primary-email")
        self.assertEqual(current.content["email"], "alice@primary.com") # Untouched
        self.assertEqual(current.conflict_state, MemoryConflictState.CONFLICT_DETECTED)
        
        # AI Twin detects conflict
        conflicts = self.ai_twin.get_conflicts()
        self.assertEqual(len(conflicts), 1)

    def test_user_explicit_memory_promotion_and_conflict_resolution(self):
        """Verify user can explicitly promote memories to VERIFIED and resolve conflicts."""
        rec = MemoryRecord(
            memory_id="user-favorite-topic",
            tier=MemoryTier.PROFILE,
            content={"topic": "Quantum Computing"},
            source="agent_inference",
            confidence=0.7,
            importance=0.5,
            sensitivity="low",
            trust_level=MemoryTrustLevel.UNVERIFIED,
            provenance=["chat_history"]
        )
        self.profile_store.store(rec, explicit_user_action=False)
        self.assertEqual(self.profile_store._records["user-favorite-topic"].trust_level, MemoryTrustLevel.UNVERIFIED)
        
        # User promotes
        promoted = self.profile_store.promote_to_verified("user-favorite-topic")
        self.assertTrue(promoted)
        self.assertEqual(self.profile_store._records["user-favorite-topic"].trust_level, MemoryTrustLevel.VERIFIED)
        
        # User resolves conflict
        resolved = self.profile_store.resolve_conflict("user-favorite-topic", {"topic": "AI Security & Alignment"})
        self.assertTrue(resolved)
        self.assertEqual(self.profile_store._records["user-favorite-topic"].content["topic"], "AI Security & Alignment")
        self.assertEqual(self.profile_store._records["user-favorite-topic"].conflict_state, MemoryConflictState.RESOLVED)

    def test_ai_twin_system_persona_prompt_formatting(self):
        """Verify AITwinManager formats persona details into structured prompt instructions."""
        self.ai_twin.update_persona({
            "name": "Sarah Connor",
            "preferred_communication_style": "brief, direct, militaristic"
        }, explicit_user_action=True)
        
        prompt_context = self.ai_twin.get_system_persona_prompt()
        self.assertIn("Sarah Connor", prompt_context)
        self.assertIn("brief, direct, militaristic", prompt_context)
        self.assertIn("[AI TWIN USER PERSONA & CONSTRAINTS", prompt_context)


if __name__ == "__main__":
    unittest.main()
