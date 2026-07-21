# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");

import json
import os
import sys
from typing import List

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from expense_agent.vector_store import load_corpus

_EVAL_SET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_set.json")


def run_blind_review(case_id: str, candidate_patent_ids: List[str]):
    """Prints ONLY case title + description and candidate patents' titles + abstracts.

    NO similarity scores, NO tier labels, NO prior pipeline output visible.
    """
    if not os.path.exists(_EVAL_SET_PATH):
        raise FileNotFoundError(f"eval_set.json missing at {_EVAL_SET_PATH}")

    with open(_EVAL_SET_PATH, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

    target_case = next((c for c in eval_cases if c["case_id"] == case_id), None)
    if not target_case:
        raise ValueError(f"Case {case_id} not found in eval_set.json")

    corpus = load_corpus()
    candidate_patents = [p for p in corpus if p["patent_id"] in candidate_patent_ids]

    print("=" * 80)
    print(f"BLIND HUMAN TECHNICAL REVIEW: {case_id}")
    print("=" * 80)
    print(f"SUBMISSION TITLE       : {target_case.get('title', '')}")
    print(f"SUBMISSION DESCRIPTION : {target_case.get('description', '')}")
    print(f"LIBRARIES USED         : {target_case.get('libraries_used', [])}")
    print("=" * 80)
    print("\nCANDIDATE PRIOR ART PATENTS FOR INDEPENDENT COMPARISON:\n")

    for i, p in enumerate(candidate_patents, 1):
        print(f"--- CANDIDATE #{i}: {p['patent_id']} ---")
        print(f"Title   : {p['title']}")
        print(f"Domain  : {p['domain_tag']}")
        print(f"Abstract: {p['abstract']}\n")

    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python blind_review.py <case_id> <patent_id_1> [<patent_id_2> ...]")
        sys.exit(1)

    c_id = sys.argv[1]
    p_ids = sys.argv[2:]
    run_blind_review(c_id, p_ids)
