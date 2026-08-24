import os
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from nava.core.schemas import MemoryRecord, MemoryTier, MemoryTrustLevel
from nava.memory.embeddings import EmbeddingEngine, get_embedding_engine
from nava.memory.bm25 import BM25Index

class HybridRAGStore:
    """
    Tier 3: Hybrid Dense Vector + Sparse BM25 Retrieval Engine with Reciprocal Rank Fusion (RRF).
    Implements Blueprint Section 22 (Knowledge / RAG System) for grounded, high-precision semantic retrieval.
    """
    def __init__(
        self,
        json_path: str = "memory/semantic.json",
        vector_path: str = "memory/semantic_vectors.json",
        embedding_engine: Optional[EmbeddingEngine] = None
    ):
        self.json_path = json_path
        self.vector_path = vector_path
        self.embedding_engine = embedding_engine or get_embedding_engine()
        
        self.records: Dict[str, MemoryRecord] = {}
        self.vectors: Dict[str, List[float]] = {}
        self.bm25 = BM25Index()
        
        self._load()

    def _load(self) -> None:
        """Loads semantic records and vectors from persistent storage."""
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        rec = MemoryRecord(**item)
                        self.records[rec.memory_id] = rec
                        
                        # Populate BM25 index with chunk text
                        chunk_text = ""
                        if isinstance(rec.content, dict):
                            chunk_text = rec.content.get("text", "") or str(rec.content)
                        else:
                            chunk_text = str(rec.content)
                            
                        self.bm25.add_document(rec.memory_id, chunk_text)
            except Exception as e:
                print(f"[HybridRAGStore] Warning loading {self.json_path}: {e}")
                self.records = {}

        if os.path.exists(self.vector_path):
            try:
                with open(self.vector_path, "r", encoding="utf-8") as f:
                    self.vectors = json.load(f)
            except Exception as e:
                print(f"[HybridRAGStore] Warning loading {self.vector_path}: {e}")
                self.vectors = {}

    def _save(self) -> None:
        """Persists records and dense vector embeddings to disk."""
        os.makedirs(os.path.dirname(os.path.abspath(self.json_path)), exist_ok=True)
        os.makedirs(os.path.dirname(os.path.abspath(self.vector_path)), exist_ok=True)
        
        # Save memory records
        with open(self.json_path, "w", encoding="utf-8") as f:
            data = [json.loads(r.model_dump_json()) for r in self.records.values()]
            json.dump(data, f, indent=2)
            
        # Save vectors
        with open(self.vector_path, "w", encoding="utf-8") as f:
            json.dump(self.vectors, f)

    def store_record(self, record: MemoryRecord, vector: Optional[List[float]] = None) -> None:
        """Stores a single memory record and updates dense + sparse indexes."""
        self.records[record.memory_id] = record
        
        chunk_text = ""
        if isinstance(record.content, dict):
            chunk_text = record.content.get("text", "") or str(record.content)
        else:
            chunk_text = str(record.content)
            
        # Update BM25
        self.bm25.add_document(record.memory_id, chunk_text)
        
        # Update Vector
        if vector is None:
            vector = self.embedding_engine.embed_text(chunk_text)
        self.vectors[record.memory_id] = vector
        
        self._save()

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
        Chunks text into semantic blocks, generates dense embeddings, builds BM25 index,
        and saves everything with grounding provenance metadata.
        """
        words = text.split()
        chunks: List[MemoryRecord] = []
        start = 0
        chunk_index = 0
        
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text = " ".join(words[start:end])
            chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:12]
            
            mem_id = f"sem-{doc_id}-{chunk_index}-{chunk_hash}"
            record = MemoryRecord(
                memory_id=mem_id,
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
            
            # Embed chunk
            vec = self.embedding_engine.embed_text(chunk_text)
            self.records[mem_id] = record
            self.vectors[mem_id] = vec
            self.bm25.add_document(mem_id, chunk_text)
            
            chunks.append(record)
            chunk_index += 1
            start += (chunk_size - overlap)
            if start >= len(words) or end == len(words):
                break
                
        self._save()
        return chunks

    def hybrid_search(
        self,
        query: str,
        limit: int = 5,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5,
        rrf_k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Performs dual-branch search (Dense Vector Cosine Similarity + Okapi BM25 Sparse Search),
        fuses the ranked lists using Reciprocal Rank Fusion (RRF), and returns grounded results.
        """
        if not self.records:
            return []

        # 1. Dense Vector Retrieval
        query_vec = self.embedding_engine.embed_text(query)
        dense_scores = []
        for mem_id, doc_vec in self.vectors.items():
            sim = EmbeddingEngine.cosine_similarity(query_vec, doc_vec)
            dense_scores.append((mem_id, sim))
        dense_scores.sort(key=lambda x: x[1], reverse=True)
        dense_ranks = {mem_id: rank + 1 for rank, (mem_id, _) in enumerate(dense_scores)}

        # 2. Sparse BM25 Retrieval
        bm25_scores = self.bm25.search(query, limit=len(self.records))
        sparse_ranks = {mem_id: rank + 1 for rank, (mem_id, _) in enumerate(bm25_scores)}

        # 3. Reciprocal Rank Fusion (RRF)
        all_candidate_ids = set(self.records.keys())
        rrf_scores: Dict[str, float] = {}
        
        for mem_id in all_candidate_ids:
            score = 0.0
            if mem_id in dense_ranks:
                score += dense_weight / (rrf_k + dense_ranks[mem_id])
            if mem_id in sparse_ranks:
                score += sparse_weight / (rrf_k + sparse_ranks[mem_id])
            rrf_scores[mem_id] = score

        ranked_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for mem_id, rrf_score in ranked_results[:limit]:
            if rrf_score <= 0.0:
                continue
            rec = self.records.get(mem_id)
            if not rec:
                continue
                
            content = rec.content if isinstance(rec.content, dict) else {"text": str(rec.content)}
            results.append({
                "memory_id": rec.memory_id,
                "doc_id": content.get("doc_id", "unknown"),
                "title": content.get("title", "Untitled"),
                "chunk_index": content.get("chunk_index", 0),
                "text": content.get("text", str(rec.content)),
                "source": rec.source,
                "rrf_score": round(rrf_score, 5),
                "dense_rank": dense_ranks.get(mem_id),
                "sparse_rank": sparse_ranks.get(mem_id),
                "trust_level": rec.trust_level.value if hasattr(rec.trust_level, "value") else str(rec.trust_level),
                "provenance": rec.provenance or []
            })
            
        return results

    def delete(self, memory_id: str) -> None:
        """Deletes a record and its corresponding vector and BM25 postings."""
        self.records.pop(memory_id, None)
        self.vectors.pop(memory_id, None)
        self.bm25.remove_document(memory_id)
        self._save()
