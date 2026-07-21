# Tracing Pipeline Behavior: Case `eval_001`

**Artifact Analyzed**: `eval/results/eval_results_20260721_153250.json`  
**Case ID**: `eval_001` (`Quantum Photonic Entanglement Frequency Modulator`)  
**Date**: 2026-07-21  

---

## 📌 Extracted Pipeline Output Metrics
*   **Matched Patent ID**: `US11234569B2` (*Quantum Key Distribution Protocol with Decoy State Modulation*)
*   **Raw Cosine Similarity Score**: **`0.624`**
*   **Assigned Policy Tier**: **`HIGH_CONFLICT`** ($\ge 0.55$)
*   **Pipeline Novelty Score**: `6/10` (`actual_novelty_band: MEDIUM`)
*   **Ground Truth Target**: `expected_conflict_patent_id: null` (`expected_novelty_band: HIGH`)

---

## 🔬 Definite Branch Confirmation: Retrieval-Layer False Positive

**Confirmed Branch**: **`embedding_vocabulary_overlap_false_positive`**

### Technical Diagnosis & Root Cause Analysis
1.  **Dense Vocabulary Clustering**: The embedding model assigned a high cosine similarity of $0.624$ (`HIGH_CONFLICT` tier) between `eval_001` ("electro-optic device modulating phase frequency of entangled photon pairs at GHz clock speeds") and `US11234569B2` ("QKD protocol modulating phase and decoy states to mitigate photon-number-splitting attacks").
2.  **Vocabulary vs. Mechanism**: Both descriptions cluster tightly around shared physics vocabulary ("quantum", "photonic", "phase", "modulation"). However, blind human technical review confirmed that `eval_001` describes a physical GHz electro-optic hardware modulator, whereas `US11234569B2` claims a software protocol for decoy state modulation in QKD.
3.  **Upstream Retrieval Failure**: Because the vector store surfaced `US11234569B2` in `HIGH_CONFLICT` tier ($0.624$), the LLM reviewer received a prompt instructing it that a `HIGH_CONFLICT` match was detected. The downstream LLM reviewer score of `6/10` is an upstream artifact of the retrieval step handing it a false conflict.

> [!IMPORTANT]
> **Remediation Boundary**: No prompt engineering or multi-agent critique prompt can fix this retrieval-layer false positive. A critique agent operates on top of the context provided by retrieval; if retrieval surfaces an unrelated patent as `HIGH_CONFLICT`, a critique agent cannot fix the vector space cluster. Remediation requires either:
> 1. Corpus expansion in quantum hardware patents to separate protocol vectors from electro-optic hardware vectors.
> 2. Secondary structural filtering (e.g. hardware apparatus vs. software protocol claim structure check) alongside dense vector similarity.
