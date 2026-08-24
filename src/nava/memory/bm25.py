import math
import re
from typing import List, Dict, Tuple, Set, Optional

# Common minimal English stop words
STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't",
    "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't",
    "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll",
    "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's",
    "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once",
    "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
    "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than", "that",
    "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these",
    "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't",
    "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's", "whom",
    "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've",
    "your", "yours", "yourself", "yourselves"
}

class BM25Index:
    """
    Okapi BM25 Sparse Inverted Index for exact keyword, identifier, and code symbol retrieval.
    Implements standard BM25 ranking parameters: k1=1.5, b=0.75.
    """
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_lengths: Dict[str, int] = {}
        self.inverted_index: Dict[str, Dict[str, int]] = {} # term -> {doc_id: freq}
        self.num_docs: int = 0
        self.avg_doc_length: float = 0.0

    def tokenize(self, text: str) -> List[str]:
        """Tokenizes text into normalized words and code tokens."""
        if not text:
            return []
        # Split on non-alphanumeric (preserves underscores and dots in code identifiers)
        raw_tokens = re.findall(r'[a-zA-Z0-9_\.]+', text.lower())
        return [t for t in raw_tokens if t not in STOP_WORDS and len(t) > 1]

    def add_document(self, doc_id: str, text: str) -> None:
        """Adds or updates a document in the BM25 index."""
        if doc_id in self.doc_lengths:
            self.remove_document(doc_id)
            
        tokens = self.tokenize(text)
        length = len(tokens)
        self.doc_lengths[doc_id] = length
        
        # Calculate term frequencies
        tf: Dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
            
        for term, freq in tf.items():
            if term not in self.inverted_index:
                self.inverted_index[term] = {}
            self.inverted_index[term][doc_id] = freq
            
        self.num_docs = len(self.doc_lengths)
        self._update_avg_doc_length()

    def remove_document(self, doc_id: str) -> None:
        """Removes a document from the index."""
        if doc_id not in self.doc_lengths:
            return
            
        del self.doc_lengths[doc_id]
        
        # Remove from inverted index
        terms_to_delete = []
        for term, postings in self.inverted_index.items():
            if doc_id in postings:
                del postings[doc_id]
                if not postings:
                    terms_to_delete.append(term)
                    
        for term in terms_to_delete:
            del self.inverted_index[term]
            
        self.num_docs = len(self.doc_lengths)
        self._update_avg_doc_length()

    def _update_avg_doc_length(self) -> None:
        if self.num_docs > 0:
            self.avg_doc_length = sum(self.doc_lengths.values()) / float(self.num_docs)
        else:
            self.avg_doc_length = 0.0

    def _idf(self, term: str) -> float:
        """Computes Robertson-Spärck Jones IDF."""
        doc_freq = len(self.inverted_index.get(term, {}))
        if doc_freq == 0:
            return 0.0
        # Standard Okapi IDF with +1 smoothing to avoid negative weights
        return math.log(1.0 + (self.num_docs - doc_freq + 0.5) / (doc_freq + 0.5))

    def search(self, query: str, limit: int = 10) -> List[Tuple[str, float]]:
        """
        Calculates BM25 scores for all matching documents and returns ranked (doc_id, score) pairs.
        """
        query_tokens = self.tokenize(query)
        if not query_tokens or self.num_docs == 0:
            return []

        scores: Dict[str, float] = {}
        for token in query_tokens:
            if token not in self.inverted_index:
                continue
                
            idf = self._idf(token)
            postings = self.inverted_index[token]
            
            for doc_id, freq in postings.items():
                doc_len = self.doc_lengths.get(doc_id, 1)
                # BM25 numerator and denominator
                num = freq * (self.k1 + 1.0)
                denom = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / (self.avg_doc_length or 1.0)))
                term_score = idf * (num / denom)
                
                scores[doc_id] = scores.get(doc_id, 0.0) + term_score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:limit]
