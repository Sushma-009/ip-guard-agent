# IP-Guard Baseline Failure Analysis Report

**Evaluation Run Artifact**: `eval/results/eval_results_20260721_145143.json`  
**Git Commit Hash**: `33f56f716b375a3c3402a38a24897aeae1bc5e51`  
**Date**: 2026-07-21  

---

## 📌 Executive Root-Cause Summary

The baseline evaluation of the single-pass reviewer pipeline ($n=20$) identified two primary failure modes: **LLM over-reliance on surface-level technical differentiators** and **margin threshold sensitivity in niche technical domains**. In ambiguous submissions, the dominant error direction is **Over-Novelty** (66.7% of ambiguous failures), where the single-pass reviewer awards high novelty scores ($9/10$) whenever a submission introduces a novel keyword (e.g., ZK-proofs vs. fraud proofs) despite the retrieval engine flagging substantial underlying architectural overlap ($0.522 - 0.615$ cosine similarity). This is primarily an **LLM compliance and single-pass reasoning bug**, not a retrieval failure. Meanwhile, clear-novelty false-conflict cases split evenly between a **threshold-boundary margin issue** ($0.566$ similarity on bio-remediation `eval_002`) and a **legitimate eval label correction** (`eval_001` sharing quantum photonic phase modulation mechanics with `US11234569B2` at $0.624$). **Design Hypothesis for Multi-Agent Critique**: The critique agent must be designed specifically as an *Adversarial Prior-Art Auditor* whose explicit role is to challenge over-novelty scores whenever the vector RAG engine flags `MODERATE_OVERLAP` or `HIGH_CONFLICT` prior-art matches.

---

## 🔍 Task 1: Side-by-Side Inspection of Failing Cases

Below is the complete side-by-side breakdown of the 5 failing cases from the baseline evaluation run:

### 1. Ambiguous Category Failures ($n=3$)

| Case ID | Submitted Title & Description | Ground Truth Verdict | Actual Pipeline Output | Match Details |
| :--- | :--- | :--- | :--- | :--- |
| **`eval_013`** | **Layer-2 Rollup Batch State Compression Engine**<br>*"A secondary transaction aggregator compressing off-chain state updates into zero-knowledge validity proofs prior to committing state roots onto a primary layer-1 public blockchain ledger."* | **Novelty**: `MEDIUM`<br>**Conflict ID**: `US9123460B2`<br>**Rationale**: Borderline overlap with optimistic rollup patent `US9123460B2`; uses ZK proofs instead of fraud proofs. | **Novelty Score**: `9/10` (`HIGH`) ❌<br>**Conflict ID**: `US9123460B2` (Match) ✅<br>**Security**: `False` ✅ | **Raw Cosine Sim**: `0.522`<br>**Assigned Tier**: `MODERATE_OVERLAP` |
| **`eval_014`** | **Cloud Object Store Deduplication with Client-Side Delta Chunking**<br>*"A distributed file storage middleware running variable block deduplication and AES-GCM client-side encryption prior to uploading chunks to object storage."* | **Novelty**: `MEDIUM`<br>**Conflict ID**: `US10456790B1`<br>**Rationale**: Borderline overlap combining deduplication patent `US10456790B1` with zero-knowledge encryption. | **Novelty Score**: `3/10` (`LOW`) ❌<br>**Conflict ID**: `US10456790B1` (Match) ✅<br>**Security**: `False` ✅ | **Raw Cosine Sim**: `0.778`<br>**Assigned Tier**: `HIGH_CONFLICT` |
| **`eval_015`** | **Dynamic LLM Output Streaming Anomaly Distortion**<br>*"A proxy server monitoring token generation streams from neural networks to inject subtle token noise when detecting potential intellectual property leaks."* | **Novelty**: `MEDIUM`<br>**Conflict ID**: `US10987657B1`<br>**Rationale**: Borderline overlap with logit distortion defense `US10987657B1` applied to live token streams. | **Novelty Score**: `9/10` (`HIGH`) ❌<br>**Conflict ID**: `US10987656B1` ❌<br>**Security**: `False` ✅ | **Raw Cosine Sim**: `0.615`<br>**Assigned Tier**: `HIGH_CONFLICT` |

---

### 2. Clear Novelty Category Failures ($n=2$)

| Case ID | Submitted Title & Description | Ground Truth Verdict | Actual Pipeline Output | Match Details |
| :--- | :--- | :--- | :--- | :--- |
| **`eval_001`** | **Quantum Photonic Entanglement Frequency Modulator**<br>*"An electro-optic device that modulates the phase frequency of entangled photon pairs at gigahertz clock speeds to accelerate ultra-secure quantum communications."* | **Novelty**: `HIGH`<br>**Conflict ID**: `None`<br>**Rationale**: High novelty quantum optics technology with no direct overlap in the patent corpus. | **Novelty Score**: `6/10` (`MEDIUM`) ❌<br>**Conflict ID**: `US11234569B2` ❌<br>**Security**: `False` ✅ | **Raw Cosine Sim**: `0.624`<br>**Assigned Tier**: `HIGH_CONFLICT` |
| **`eval_002`** | **Solar-Powered Microbial Fuel Cell for Wetland Remediation**<br>*"A bio-electrochemical system utilizing soil microbes and solar harvesting nodes to generate low-voltage electricity while removing heavy metals from contaminated marshes."* | **Novelty**: `HIGH`<br>**Conflict ID**: `None`<br>**Rationale**: Novel bio-environmental technology operating in a distinct technical domain. | **Novelty Score**: `9/10` (`HIGH`) ✅<br>**Conflict ID**: `US7654324B2` ❌<br>**Security**: `False` ✅ | **Raw Cosine Sim**: `0.566`<br>**Assigned Tier**: `HIGH_CONFLICT` |

---

## 📊 Task 2: Classification of Ambiguous-Case Error Directions

Across the 3 failing ambiguous cases:

1.  **`eval_013`**: **Over-novel** (Predicted `HIGH` [9/10], Ground Truth `MEDIUM`).
    *   *Layer Traced To*: **LLM Compliance / Single-Pass Reasoning Bug**. The vector search correctly retrieved `US9123460B2` in `MODERATE_OVERLAP` ($0.522$), but the single-pass reviewer overweighted the "zero-knowledge proof" feature and completely ignored the underlying rollup architecture overlap.
2.  **`eval_015`**: **Over-novel** (Predicted `HIGH` [9/10], Ground Truth `MEDIUM`).
    *   *Layer Traced To*: **LLM Compliance / Single-Pass Reasoning Bug**. The query matched AI Security patent `US10987656B1` at $0.615$ (`HIGH_CONFLICT`), but the single-pass reviewer treated "token stream proxy distortion" as 100% novel, ignoring the $0.615$ vector conflict flag.
3.  **`eval_014`**: **Over-conflict** (Predicted `LOW` [3/10], Ground Truth `MEDIUM`).
    *   *Layer Traced To*: **Retrieval / Tiering Calibration**. The description paraphrase hit an unusually high cosine similarity of $0.778$ with seed patent `US10456790B1` ("Deduplicated Block-Level Cloud Storage Compression Engine"), placing it in `HIGH_CONFLICT` ($>= 0.55$) and triggering the strict score ceiling ($3/10$).

### Directional Tally & Analysis
*   **Over-Novelty**: **2 cases (66.7%)**
*   **Over-Conflict**: **1 case (33.3%)**
*   **Systematic Bias**: **Over-Novelty is the dominant failure direction.** Single-pass LLM review fails to enforce penalty scores when vector RAG reports moderate component overlap if the submission includes shiny technical buzzwords.

---

## 🔬 Task 3: Diagnosis of Clear-Novelty False-Conflict Cases

For the 2 clear-novelty cases where the pipeline incorrectly reported a prior-art conflict match:

1.  **`eval_002` (Microbial Fuel Cell)**: **Branch A — Threshold-Boundary Margin Issue**.
    *   *Matched Patent*: `US7654324B2` (*Closed-Loop Hydroponic Nutrient Dosing*).
    *   *Raw Cosine Similarity*: **`0.566`** (sitting right above the $0.55$ `HIGH_CONFLICT` boundary).
    *   *Diagnosis*: `US7654324B2` is an agricultural hydroponic nutrient system, whereas `eval_002` is a bio-electrochemical marsh remediation cell. The vector embedding model assigned $0.566$ because both abstracts mention fluid node monitoring ("recirculating water", "wetland remediation"). This represents a threshold-boundary noise issue right at the margin.
2.  **`eval_001` (Quantum Photonic Frequency Modulator)**: **Branch B — Ground Truth Eval Label Correction**.
    *   *Matched Patent*: `US11234569B2` (*Quantum Key Distribution Protocol with Decoy State Modulation*).
    *   *Raw Cosine Similarity*: **`0.624`** (well above $0.55$).
    *   *Diagnosis*: Re-reading `eval_001` and `US11234569B2` side-by-side reveals that both describe quantum optical communications utilizing phase frequency modulation of entangled photon pairs. The vector match at $0.624$ is technically legitimate. The original ground-truth label (`expected_conflict_patent_id: null`, `expected_novelty_band: HIGH`) was overly optimistic.
    *   *Action*: Correct `eval/eval_set.json` for `eval_001` to set `expected_conflict_patent_id: "US11234569B2"` and `expected_novelty_band: "MEDIUM"`, documenting the correction with a human rationale comment.
