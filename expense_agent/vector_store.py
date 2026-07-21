# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");

import chromadb
from typing import List, Dict, Any

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

# Seed USPTO Patent Abstract Dataset
_SEED_PATENTS = [
    {
        "id": "US9123456B2",
        "title": "Distributed Ledger Consensus and Secondary Supervisor Arbitration",
        "abstract": "A decentralized consensus mechanism that integrates secondary supervisor nodes to arbitrate conflict resolution in high-throughput ledger transactions, resolving partition lockouts.",
        "category": "Blockchain & Distributed Systems"
    },
    {
        "id": "US10987654B1",
        "title": "Artificial Intelligence Prompt Injection Firewall and Input Filtering",
        "abstract": "Systems and methods for detecting prompt injection, instruction overrides, and adversarial jailbreak attempts in large language model input streams using heuristic gates.",
        "category": "AI & LLM Security"
    },
    {
        "id": "US8555222B2",
        "title": "Automated Corporate Expense Audit Workflow",
        "abstract": "An automated system for processing financial receipts, evaluating corporate policy compliance, and executing auto-approvals based on spending thresholds.",
        "category": "Financial Workflows"
    },
    {
        "id": "US11234567B2",
        "title": "Quantum Packet Header Processing and Network Routing Protocol",
        "abstract": "Routing protocol and hardware architecture for quantum networks that speeds up packet header processing and entanglement distribution across optical channels.",
        "category": "Quantum Networking"
    },
    {
        "id": "US10456789B1",
        "title": "Automated Cloud File Synchronization and Encrypted S3 Backup Storage",
        "abstract": "A background service monitoring local filesystem events and executing delta synchronization to S3-compatible cloud storage buckets using client-side encryption.",
        "category": "Cloud Infrastructure"
    },
    {
        "id": "US9876543B2",
        "title": "Homomorphic Cryptographic Key Exchange for Distributed Databases",
        "abstract": "Methods for conducting secure key exchanges across untrusted network nodes enabling zero-knowledge queries against homomorphically encrypted database tables.",
        "category": "Cryptography"
    }
]

def seed_vector_db():
    """Seeds the ChromaDB vector database with USPTO patent abstracts if empty."""
    if _collection.count() == 0:
        documents = [p["abstract"] for p in _SEED_PATENTS]
        metadatas = [{"id": p["id"], "title": p["title"], "category": p["category"]} for p in _SEED_PATENTS]
        ids = [p["id"] for p in _SEED_PATENTS]
        _collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

# Seed immediately on module import
seed_vector_db()


def search_prior_art_vectors(query: str, top_k: int = 3) -> Dict[str, Any]:
    """Queries ChromaDB vector database for semantically similar prior art patents.

    Args:
        query: The technology description or title to search.
        top_k: Number of nearest matches to return.

    Returns:
        Dict[str, Any]: Vector search results including patent IDs, similarity scores, and titles.
    """
    if not query or not query.strip():
        return {"status": "CLEAN", "matches": []}

    results = _collection.query(
        query_texts=[query],
        n_results=top_k
    )

    matches = []
    if results and results.get("ids") and results["ids"][0]:
        ids = results["ids"][0]
        distances = results["distances"][0] if "distances" in results and results["distances"] else [0.5] * len(ids)
        documents = results["documents"][0] if "documents" in results and results["documents"] else [""] * len(ids)
        metadatas = results["metadatas"][0] if "metadatas" in results and results["metadatas"] else [{}] * len(ids)

        for i in range(len(ids)):
            # Cosine distance to similarity conversion: similarity = 1 - distance
            dist = float(distances[i])
            similarity = max(0.0, min(1.0, round(1.0 - dist, 3)))
            
            # Filter matches with similarity > 0.45 as relevant prior art
            if similarity >= 0.45:
                matches.append({
                    "patent_id": ids[i],
                    "title": metadatas[i].get("title", ""),
                    "category": metadatas[i].get("category", ""),
                    "similarity_score": similarity,
                    "abstract_snippet": documents[i][:150] + "..."
                })

    if matches:
        return {"status": "MATCH_FOUND", "matches": matches}
    return {"status": "CLEAN", "matches": []}
