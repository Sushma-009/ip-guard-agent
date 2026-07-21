# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");

import json
import os
import chromadb
from typing import List, Dict, Any, Tuple

# Path to corpus dataset
_CORPUS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "patent_corpus.json"
)

# Initialize lightweight in-memory ChromaDB client
_chroma_client = chromadb.Client()

# Create or reset collection
try:
    _collection = _chroma_client.get_collection(name="patent_prior_art")
except Exception:
    _collection = _chroma_client.create_collection(
        name="patent_prior_art",
        metadata={"hnsw:space": "cosine"}
    )


def load_corpus() -> List[Dict[str, Any]]:
    """Loads versioned seed corpus from data/patent_corpus.json."""
    if not os.path.exists(_CORPUS_PATH):
        raise FileNotFoundError(f"Corpus dataset file missing at {_CORPUS_PATH}")
    with open(_CORPUS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_vector_db():
    """Seeds ChromaDB vector database with USPTO patent abstracts from JSON corpus."""
    corpus = load_corpus()
    expected_count = len(corpus)
    
    current_count = _collection.count()
    if current_count < expected_count:
        documents = [p["abstract"] for p in corpus]
        metadatas = [
            {
                "patent_id": p["patent_id"],
                "title": p["title"],
                "domain_tag": p["domain_tag"],
                "filing_date": p.get("filing_date", "")
            }
            for p in corpus
        ]
        ids = [p["patent_id"] for p in corpus]
        
        _collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    # Task 3: Cold-start startup assertion
    final_count = _collection.count()
    if final_count < expected_count:
        raise RuntimeError(
            f"Cold-start vector store seed assertion failed: expected at least {expected_count} patents, found {final_count}."
        )


# Seed immediately on module import
seed_vector_db()


def get_vector_store_stats() -> Dict[str, Any]:
    """Returns vector store health metrics for /health/vector-store endpoint."""
    corpus = load_corpus()
    return {
        "status": "healthy",
        "document_count": _collection.count(),
        "expected_corpus_size": len(corpus)
    }


def classify_similarity_tier(similarity_score: float) -> str:
    """Task 2 & Task A: Buckets cosine similarity scores into calibrated policy tiers.

    Empirical Calibration Benchmark (docs/threshold_calibration.md):
    - Unrelated Queries Max Observed Similarity : 0.309
    - True Paraphrase Min Observed Similarity   : 0.744
    - Empirical Gap Midpoint                     : 0.526 -> Calibrated Boundary: 0.55

    Tiers:
    - >= 0.55          -> HIGH_CONFLICT (Strong evidence against novelty)
    - 0.45 - 0.55     -> MODERATE_OVERLAP (Partial overlap requiring justification)
    - 0.35 - 0.45     -> LOW_OVERLAP (Low similarity context)
    - < 0.35          -> NOT_RELEVANT (Filtered out of LLM prompt)
    """
    if similarity_score >= 0.55:
        return "HIGH_CONFLICT"
    elif similarity_score >= 0.45:
        return "MODERATE_OVERLAP"
    elif similarity_score >= 0.35:
        return "LOW_OVERLAP"
    else:
        return "NOT_RELEVANT"


def search_prior_art_vectors(query: str, top_k: int = 3) -> Dict[str, Any]:
    """Queries ChromaDB vector database for semantically similar prior art patents.

    Args:
        query: The technology description or title to search.
        top_k: Number of nearest matches to return.

    Returns:
        Dict[str, Any]: Vector search results including raw similarity scores, tier labels, and filtering.
    """
    if not query or not query.strip():
        return {"status": "CLEAN", "matches": [], "max_similarity": 0.0}

    results = _collection.query(
        query_texts=[query],
        n_results=top_k
    )

    matches = []
    max_similarity = 0.0
    
    if results and results.get("ids") and results["ids"][0]:
        ids = results["ids"][0]
        distances = results["distances"][0] if "distances" in results and results["distances"] else [0.5] * len(ids)
        documents = results["documents"][0] if "documents" in results and results["documents"] else [""] * len(ids)
        metadatas = results["metadatas"][0] if "metadatas" in results and results["metadatas"] else [{}] * len(ids)

        for i in range(len(ids)):
            dist = float(distances[i])
            similarity = max(0.0, min(1.0, round(1.0 - dist, 3)))
            tier = classify_similarity_tier(similarity)
            
            if similarity > max_similarity:
                max_similarity = similarity
            
            # Exclude NOT_RELEVANT matches (< 0.35) from context output
            if tier != "NOT_RELEVANT":
                matches.append({
                    "patent_id": ids[i],
                    "title": metadatas[i].get("title", ""),
                    "domain_tag": metadatas[i].get("domain_tag", ""),
                    "raw_similarity_score": similarity,
                    "similarity_tier": tier,
                    "abstract_snippet": documents[i][:150] + "..."
                })

    status = "MATCH_FOUND" if matches else "CLEAN"
    return {
        "status": status,
        "matches": matches,
        "max_similarity": max_similarity
    }
