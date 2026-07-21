# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");

import json
import os
import sys

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from expense_agent.vector_store import search_prior_art_vectors, load_corpus

# Unrelated queries
unrelated_queries = [
    "Sourdough bread baking recipe app with temperature alarms",
    "Pet grooming appointment scheduler and dog washing queue",
    "Underwater basket weaving techniques and bamboo fiber knots",
    "Automated home coffee machine bean grinding sensor",
    "Personal fitness workout tracker for marathon runners"
]

# Related queries (paraphrases of seed patents)
paraphrased_queries = [
    ("US11234567B2", "Routing protocol and hardware architecture for quantum networks that speeds up packet header processing and entanglement distribution across optical channels"),
    ("US10456789B1", "Background daemon monitoring directory filesystem changes and performing delta encryption sync to AWS S3 storage buckets"),
    ("US9876543B2", "Zero knowledge cryptographic session key exchange over insecure database channels using homomorphic encryption"),
    ("US9123456B2", "Decentralized consensus protocol with secondary arbiter supervisor nodes resolving lockouts in distributed ledgers"),
    ("US8555222B2", "Automated receipt OCR processing engine checking corporate policy compliance and spending limits")
]

def run_diagnostic():
    print("=" * 80)
    print("EMPIRICAL VECTOR SIMILARITY THRESHOLD DIAGNOSTIC AUDIT")
    print("=" * 80)

    unrelated_scores = []
    print("\n--- UNRELATED QUERIES ---")
    for q in unrelated_queries:
        res = search_prior_art_vectors(q, top_k=3)
        max_sim = res.get("max_similarity", 0.0)
        top_match = res["matches"][0]["patent_id"] if res["matches"] else "NONE"
        unrelated_scores.append((max_sim, q, top_match))
        print(f"Max Similarity: {max_sim:.3f} | Query: '{q[:50]}...' | Top Match: {top_match}")

    related_scores = []
    print("\n--- TRUE MATCH / PARAPHRASED QUERIES ---")
    for target_id, q in paraphrased_queries:
        res = search_prior_art_vectors(q, top_k=3)
        matches = res.get("matches", [])
        top_match = matches[0] if matches else {"patent_id": "NONE", "raw_similarity_score": 0.0}
        sim = top_match["raw_similarity_score"]
        related_scores.append((sim, q, top_match["patent_id"], target_id))
        print(f"Similarity: {sim:.3f} | Target: {target_id} | Matched: {top_match['patent_id']} | Query: '{q[:50]}...'")

    unrelated_max = max(s[0] for s in unrelated_scores)
    related_min = min(s[0] for s in related_scores)

    print("\n" + "=" * 80)
    print("SUMMARY OBSERVATIONS:")
    print(f"- Highest Unrelated Similarity Score: {unrelated_max:.3f}")
    print(f"- Lowest True Match Similarity Score : {related_min:.3f}")
    print(f"- Empirical Decision Gap            : [{unrelated_max:.3f} --- Gap --- {related_min:.3f}]")
    print(f"- Suggested Midpoint Boundary       : {(unrelated_max + related_min) / 2.0:.3f}")
    print("=" * 80)

if __name__ == "__main__":
    run_diagnostic()