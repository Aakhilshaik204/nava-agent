import os
import sys
import shutil
import tempfile
import unittest

os.environ["NAVA_TEST_MODE"] = "1"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from nava.memory.embeddings import LocalDeterministicEmbeddingEngine, EmbeddingEngine
from nava.memory.bm25 import BM25Index
from nava.memory.hybrid_rag import HybridRAGStore
from nava.memory.store import SemanticMemoryStore
from nava.tools.executor import LocalToolExecutor

class TestHybridRAGSystem(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.json_path = os.path.join(self.temp_dir, "semantic.json")
        self.vector_path = os.path.join(self.temp_dir, "semantic_vectors.json")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_local_deterministic_embeddings(self):
        """Verify dense embedding dimensions, normalization, and cosine similarity."""
        engine = LocalDeterministicEmbeddingEngine(dimension=384)
        
        vec1 = engine.embed_text("Autonomous agent governance and risk management")
        vec2 = engine.embed_text("Autonomous agent governance and safety policies")
        vec3 = engine.embed_text("Cooking recipes for Italian pasta carbonara")

        self.assertEqual(len(vec1), 384)
        self.assertEqual(len(vec2), 384)
        self.assertEqual(len(vec3), 384)

        sim_related = EmbeddingEngine.cosine_similarity(vec1, vec2)
        sim_unrelated = EmbeddingEngine.cosine_similarity(vec1, vec3)

        self.assertGreater(sim_related, 0.6)
        self.assertLess(sim_unrelated, sim_related)

    def test_bm25_sparse_indexing_and_scoring(self):
        """Verify Okapi BM25 tokenization, document frequency, and keyword ranking."""
        bm25 = BM25Index(k1=1.5, b=0.75)
        
        bm25.add_document("doc1", "FastAPI web framework with async SQLAlchemy and PostgreSQL backend")
        bm25.add_document("doc2", "React frontend with Tailwind CSS and Vite bundling")
        bm25.add_document("doc3", "PostgreSQL database indexing and query performance optimization")

        results = bm25.search("PostgreSQL database")
        self.assertTrue(len(results) > 0)
        
        top_doc_id, top_score = results[0]
        # doc3 contains both "PostgreSQL" and "database"
        self.assertEqual(top_doc_id, "doc3")
        self.assertGreater(top_score, 0.0)

        # Verify removal
        bm25.remove_document("doc3")
        res_after = bm25.search("PostgreSQL database")
        self.assertEqual(len(res_after), 1)
        self.assertEqual(res_after[0][0], "doc1")

    def test_hybrid_rag_store_rrf_fusion(self):
        """Verify document chunking, dense+sparse hybrid search, and RRF score calculation."""
        store = HybridRAGStore(json_path=self.json_path, vector_path=self.vector_path)
        
        sample_doc = (
            "The NAVA Action Gateway serves as a mandatory choke point for all tool operations. "
            "It enforces a 17-step pipeline verifying permissions, risk scores, budgets, and concurrency locks. "
            "Every tool call generates a cryptographic tamper-evident ActionReceipt appended to the audit ledger."
        )
        
        chunks = store.ingest_document(
            doc_id="nava_architecture_spec",
            title="NAVA Action Gateway Specification",
            text=sample_doc,
            source="spec",
            chunk_size=20,
            overlap=5,
            metadata={"chapter": 12, "author": "NAVA Architect"}
        )

        self.assertGreater(len(chunks), 0)
        self.assertTrue(os.path.exists(self.json_path))
        self.assertTrue(os.path.exists(self.vector_path))

        # Query using Hybrid Search
        results = store.hybrid_search("17-step pipeline Action Gateway permissions", limit=3)
        self.assertTrue(len(results) > 0)
        
        top = results[0]
        self.assertEqual(top["doc_id"], "nava_architecture_spec")
        self.assertIn("Action Gateway", top["text"])
        self.assertIn("rrf_score", top)
        self.assertIn("dense_rank", top)
        self.assertIn("sparse_rank", top)
        self.assertGreater(top["rrf_score"], 0.0)

    def test_semantic_memory_store_integration(self):
        """Verify SemanticMemoryStore backward compatibility and upgraded hybrid search API."""
        sem_store = SemanticMemoryStore(filepath=self.json_path, vector_path=self.vector_path)
        
        doc_text = "Docker containerization and Kubernetes cluster deployment for scalable AI microservices."
        chunks = sem_store.ingest_document(
            doc_id="k8s_guide",
            title="Kubernetes Guide",
            text=doc_text,
            source="user"
        )
        
        self.assertEqual(len(chunks), 1)

        # Test retrieve (MemoryRecord list)
        records = sem_store.retrieve("Kubernetes cluster")
        self.assertTrue(len(records) > 0)
        self.assertIn("Kubernetes", str(records[0].content))

        # Test hybrid_search (Structured dictionary list)
        hybrid_res = sem_store.hybrid_search("Docker containerization", limit=2)
        self.assertTrue(len(hybrid_res) > 0)
        self.assertEqual(hybrid_res[0]["doc_id"], "k8s_guide")

    def test_executor_hybrid_rag_tools(self):
        """Verify memory.semantic_ingest and memory.semantic_search via LocalToolExecutor."""
        orig_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            executor = LocalToolExecutor()
            executor.set_active_project("KnowledgeProject")
            
            # 1. Ingest via tool
            ingest_args = {
                "title": "Quantum Computing Principles",
                "content": "Quantum superposition and entanglement enable exponential speedups for quantum algorithms like Shor's and Grover's algorithms.",
                "source": "physics_paper",
                "metadata": {"category": "physics"}
            }
            res_ingest = executor._memory_semantic_ingest(ingest_args)
            self.assertTrue(res_ingest.get("success"))
            self.assertEqual(res_ingest.get("chunks_created"), 1)

            # 2. Search via tool
            search_args = {
                "query": "Grover's algorithm superposition entanglement",
                "limit": 3
            }
            res_search = executor._memory_semantic_search(search_args)
            self.assertEqual(res_search.get("total_results"), 1)
            
            top_hit = res_search["results"][0]
            self.assertEqual(top_hit["title"], "Quantum Computing Principles")
            self.assertIn("superposition", top_hit["text"])
            self.assertGreater(top_hit["rrf_score"], 0.0)
        finally:
            os.chdir(orig_cwd)

if __name__ == "__main__":
    unittest.main()
