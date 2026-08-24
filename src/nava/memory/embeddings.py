import math
import hashlib
import os
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

class EmbeddingEngine(ABC):
    """Abstract base class for dense vector embedding generation."""
    
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generates a dense embedding vector for a single string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates dense embedding vectors for a batch of strings."""
        pass

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Computes cosine similarity between two normalized or unnormalized vectors."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
            
        return float(dot_product / (norm_a * norm_b))


class LocalDeterministicEmbeddingEngine(EmbeddingEngine):
    """
    High-performance 384-dimensional dense semantic hashing vector generator.
    Employs sub-word n-gram character and word-level feature projections with L2 normalization.
    Guarantees deterministic, zero-network, air-gapped dense embeddings for testing and local operation.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def _hash_token(self, token: str, seed: int) -> int:
        h = hashlib.sha256(f"{token}_{seed}".encode("utf-8")).hexdigest()
        return int(h[:8], 16)

    def embed_text(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * self.dimension
            
        vector = [0.0] * self.dimension
        words = text.lower().split()
        
        for w in words:
            # Word-level projection
            idx1 = self._hash_token(w, 1) % self.dimension
            idx2 = self._hash_token(w, 2) % self.dimension
            weight = 1.0 + (len(w) * 0.1)
            vector[idx1] += weight
            vector[idx2] += weight * 0.5
            
            # Character n-grams (3-grams) for morphological capture
            for i in range(len(w) - 2):
                ngram = w[i:i+3]
                ng_idx = self._hash_token(ngram, 3) % self.dimension
                vector[ng_idx] += 0.4

        # L2 Normalization
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 0:
            vector = [float(x / norm) for x in vector]
            
        return vector

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


class CloudEmbeddingEngine(EmbeddingEngine):
    """Integrates with OpenAI / Google GenAI embeddings when API keys are available."""
    def __init__(self, provider: str = "google", model: Optional[str] = None):
        self.provider = provider
        self.model = model
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            if self.provider == "google" and os.getenv("GEMINI_API_KEY"):
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                self._client = GoogleGenerativeAIEmbeddings(model=self.model or "models/text-embedding-004")
            elif self.provider == "openai" and os.getenv("OPENAI_API_KEY"):
                from langchain_openai import OpenAIEmbeddings
                self._client = OpenAIEmbeddings(model=self.model or "text-embedding-3-small")
        except Exception:
            self._client = None

    def embed_text(self, text: str) -> List[float]:
        if self._client:
            try:
                return self._client.embed_query(text)
            except Exception:
                pass
        # Fallback to local deterministic engine
        return LocalDeterministicEmbeddingEngine().embed_text(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if self._client:
            try:
                return self._client.embed_documents(texts)
            except Exception:
                pass
        return LocalDeterministicEmbeddingEngine().embed_batch(texts)


def get_embedding_engine(prefer_cloud: Optional[bool] = None) -> EmbeddingEngine:
    """Factory to retrieve the best available embedding engine."""
    if os.getenv("NAVA_TEST_MODE") == "1":
        return LocalDeterministicEmbeddingEngine()

    if prefer_cloud is True:
        if os.getenv("GEMINI_API_KEY"):
            return CloudEmbeddingEngine(provider="google")
        if os.getenv("OPENAI_API_KEY"):
            return CloudEmbeddingEngine(provider="openai")
            
    return LocalDeterministicEmbeddingEngine()
