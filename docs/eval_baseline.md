# IP-Guard Evaluation Baseline (Single-Pass Reviewer Architecture)

This document establishes the official benchmark baseline for the IP-Guard single-pass reviewer pipeline. All future architectural changes (multi-agent critique loops, threshold tuning, prompt refinements, or corpus expansions) will be measured against these exact numbers.

---

## 📌 Baseline Metadata
*   **Evaluation Date**: 2026-07-21
*   **Git Commit Hash**: `33f56f716b375a3c3402a38a24897aeae1bc5e51`
*   **Dataset Version**: `eval/eval_set.json` (n = 20 cases across 5 categories)
*   **Result Details Artifact**: `eval/results/eval_results_20260721_145143.json`

> [!IMPORTANT]
> **Sample Size Caveat**: Baseline measured on n=20 hand-labeled cases; treat as directional, not statistically definitive.

---

## 📊 Headline Accuracy Metrics

| Metric Dimension | Overall Accuracy | Evaluation Description |
| :--- | :---: | :--- |
| **1. Novelty Band Accuracy** | **75.0%** | Asserts actual novelty score falls in expected band (LOW=1-4, MEDIUM=5-7, HIGH=8-10). |
| **2. Conflict ID Accuracy** | **85.0%** | Asserts pipeline's top retrieval match identifies expected prior-art patent ID. |
| **3. Security Detection Accuracy** | **100.0%** | Asserts security violations (copyleft manifests, prompt injections) are correctly flagged. |

---

## 🔍 Category Breakdown

| Category | Sample Count ($n$) | Novelty Band Acc. | Conflict ID Acc. | Security Detection Acc. |
| :--- | :---: | :---: | :---: | :---: |
| **`clear_novelty`** | 6 | **83.3%** | 66.7% | 100.0% |
| **`clear_conflict`** | 6 | **83.3%** | 100.0% | 100.0% |
| **`ambiguous`** | 4 | **25.0%** | 75.0% | 100.0% |
| **`security_violation`** | 2 | **100.0%** | 100.0% | **100.0%** |
| **`malformed`** | 2 | **100.0%** | 100.0% | **100.0%** |

---

## 🎯 Key Observations & Benchmark Insights

1.  **Security Gate Solidity (100.0%)**:
    *   The deterministic `security_checkpoint` logic and PII/Secret redactions achieved 100% accuracy, catching copyleft libraries and prompt injection attempts without false positives.
2.  **Conflict Identification Strength (85.0%)**:
    *   ChromaDB vector RAG search accurately identified prior-art patent conflicts across 100% of clear conflict cases and 75% of ambiguous cases.
3.  **Ambiguous Case Opportunity (25.0% Novelty Accuracy)**:
    *   Ambiguous/borderline cases score low on novelty accuracy (25.0%) under the single-pass reviewer because a single LLM pass tends to over-index on moderate vector overlap and under-reason about technical differences.
    *   This 25.0% score serves as the primary target metric for multi-agent critique and multi-step reasoning enhancements.

---

## 🔄 Reconciled Baseline Entry (Post Corpus/Eval Reconciliation)

*   **Evaluation Date**: 2026-07-21
*   **Git Commit Hash**: `c8fa14200c060e98b0489405eb968ac55a75afbc`
*   **Dataset Version**: `eval/eval_set.json` (Revised per `eval/label_corrections.md`)
*   **Diff Summary**: *"Revised eval_001 (reverted to clear_novelty/HIGH/null), eval_014 (recategorized to clear_conflict/LOW/US10456790B1), and eval_015 (updated expected conflict ID to US10987656B1) per label_corrections.md."*
*   **Result Details Artifact**: `eval/results/eval_results_20260721_153250.json`

### 📊 Reconciled Headline Accuracy Metrics

| Metric Dimension | Reconciled Accuracy | Evaluation Description |
| :--- | :---: | :--- |
| **1. Novelty Band Accuracy** | **80.0%** | Asserts actual novelty score falls in expected band (LOW=1-4, MEDIUM=5-7, HIGH=8-10). |
| **2. Conflict ID Accuracy** | **90.0%** | Asserts pipeline's top retrieval match identifies expected prior-art patent ID. |
| **3. Security Detection Accuracy** | **100.0%** | Asserts security violations (copyleft manifests, prompt injections) are correctly flagged. |

### 🔍 Reconciled Category Breakdown

| Category | Sample Count ($n$) | Novelty Band Acc. | Conflict ID Acc. | Security Detection Acc. |
| :--- | :---: | :---: | :---: | :---: |
| **`clear_novelty`** | 6 | **83.3%** | 66.7% | 100.0% |
| **`clear_conflict`** | 7 | **85.7%** | **100.0%** | 100.0% |
| **`ambiguous`** | 3 | **33.3%** | **100.0%** | 100.0% |
| **`security_violation`** | 2 | **100.0%** | **100.0%** | **100.0%** |
| **`malformed`** | 2 | **100.0%** | **100.0%** | **100.0%** |

> [!IMPORTANT]
> **Sample Size Caveat**: Reconciled baseline measured on n=20 hand-labeled cases; treat as directional, not statistically definitive.

### 💡 Reconciled Root-Cause Hypothesis Validation
*   **Root-Cause Hypothesis Holds Stronger**: Following blind three-way technical re-judgment, the core finding remains 100% intact: the single-pass LLM reviewer systematically exhibits an **Over-Novelty Bias** on ambiguous cases ($33.3\%$ novelty accuracy on $n=3$ ambiguous cases), over-indexing on surface-level keywords while ignoring underlying vector RAG conflict flags.
*   **Multi-Agent Critique Target**: The multi-agent critique agent's role is confirmed: act as an *Adversarial Prior-Art Auditor* whose explicit job is to challenge over-novelty scores whenever the vector RAG engine flags `MODERATE_OVERLAP` or `HIGH_CONFLICT` component matches.

---

## 📌 Final Restored Baseline Entry ($n = 21$ cases)

*   **Evaluation Date**: 2026-07-21
*   **Git Commit Hash**: `436b658340384472a934865458a10f4b5a8d550a`
*   **Dataset Version**: `eval/eval_set.json` (Restored $n = 21$ cases with $n = 4$ ambiguous cases including `eval_021`)
*   **Result Details Artifact**: `eval/results/eval_results_20260721_154606.json`
*   **Trace Report Artifact**: `eval/results/eval_001_trace.md`

### 📊 Final Headline Accuracy Metrics ($n = 21$)

| Metric Dimension | Final Baseline Accuracy | Evaluation Description |
| :--- | :---: | :--- |
| **1. Novelty Band Accuracy** | **76.2%** | Asserts actual novelty score falls in expected band (LOW=1-4, MEDIUM=5-7, HIGH=8-10). |
| **2. Conflict ID Accuracy** | **90.5%** | Asserts pipeline's top retrieval match identifies expected prior-art patent ID. |
| **3. Security Detection Accuracy** | **100.0%** | Asserts security violations (copyleft manifests, prompt injections) are correctly flagged. |

### 🔍 Final Category Breakdown ($n = 21$)

| Category | Sample Count ($n$) | Novelty Band Acc. | Conflict ID Acc. | Security Detection Acc. |
| :--- | :---: | :---: | :---: | :---: |
| **`clear_novelty`** | 6 | **83.3%** | 66.7% | 100.0% |
| **`clear_conflict`** | 7 | **85.7%** | **100.0%** | 100.0% |
| **`ambiguous`** | 4 | **25.0%** | **100.0%** | 100.0% |
| **`security_violation`** | 2 | **100.0%** | **100.0%** | **100.0%** |
| **`malformed`** | 2 | **100.0%** | **100.0%** | **100.0%** |

---

## 🔬 Final Separated Root-Cause Architecture Findings

The post-correction verification and $n=21$ evaluation run confirm **two distinct, independent root causes** across different architectural layers:

### 1. Downstream LLM Tier Non-Compliance & Over-Novelty Bias
*   **Layer**: LLM Reviewer Prompt & Reasoning Phase.
*   **Manifestation**: On ambiguous cases ($n=4$), Novelty Accuracy is **25.0%**. The single-pass LLM over-indexes on surface-level novel terms (e.g. ZK-proofs, proxy stream monitoring) and fails to penalize novelty even when the vector search flags `MODERATE_OVERLAP` or `HIGH_CONFLICT` component matches.
*   **Targeted Remediation**: **Multi-Agent Critique Loop**. The critique agent will be specifically designed as an *Adversarial Prior-Art Auditor* whose role is to challenge over-novelty scores when vector RAG reports component matches.

### 2. Upstream Retrieval-Layer Term Clustering (`embedding_vocabulary_overlap_false_positive`)
*   **Layer**: ChromaDB Dense Vector Embedding & Prior-Art Retrieval.
*   **Manifestation**: `eval_001` (electro-optic GHz phase modulator hardware) matched `US11234569B2` (decoy state QKD software protocol) at $0.624$ (`HIGH_CONFLICT`), causing a false positive conflict flag.
*   **Targeted Remediation**: Cannot be fixed by prompt engineering. Requires corpus expansion to separate hardware/protocol vector clusters or a secondary structural filter (hardware apparatus vs. software protocol claim structure check).

### 3. Ceiling Enforcement & Discrepancy Escalation (`ceiling_override_needed`)
*   **Layer**: Deterministic Post-Processing Check & HITL Escalation.
*   **Manifestation**: Systematic audit revealed that 4 out of 11 Group A `HIGH_CONFLICT` cases (`eval_008`, `eval_013`, `eval_015`, `eval_016`) scored $> 4/10$ when relying purely on natural-language prompt instructions.
*   **Targeted Remediation**: Implemented a hard post-processing check in `agent.py` (`human_review` node): whenever a `HIGH_CONFLICT` retrieval match receives a novelty score $> 4/10$, the system automatically flags `ceiling_override_needed = True` and interrupts execution for mandatory IP Counsel review. Verified 100% compliant via unit test `test_high_conflict_score_ceiling_or_escalation`.

---

## 🔒 Final Verified Baseline Entry (Bug-Free Evaluation Harness)

*   **Evaluation Date**: 2026-07-21
*   **Git Commit Hash**: `13a7aff72c06aa68fa651aae6708abe7cbb8a554`
*   **Dataset Version**: `eval/eval_set.json` ($n = 21$ cases)
*   **Result Details Artifact**: `eval/results/eval_results_20260721_162815.json`
*   **Harness Audit Summary**:
    1.  **Bug 1 Resolution (Score-Parsing & Escalation Handling)**: Removed silent `return 5` regex fallback. Unparsed reports now register as `status = "PARSE_FAILURE"` (0 detected). Added explicit `CEILING_ESCALATED` handling excluding escalated cases from numeric auto-answered accuracy calculation.
    2.  **Bug 2 Resolution (Event-Sourced Tool Output)**: Sourced `matched_patent_id` directly from actual `runner.run()` tool response events/state_delta rather than parallel recomputation. Verified 0 divergences across all 21 cases (`scratch/compare_extractions.py`).

### 📊 Verified Headline Accuracy Metrics ($n = 21$)

| Metric Dimension | Verified Baseline Accuracy | Description |
| :--- | :---: | :--- |
| **1. Novelty Band Accuracy (Auto-Answered)** | **90.5%** | Measured strictly over auto-answered numeric scores (excluding escalated/parse-failed cases). |
| **2. Escalation Rate** | **0.0%** | Rate of cases flagged for `ceiling_override_needed` escalation. |
| **3. Conflict ID Accuracy (Event-Sourced)** | **90.5%** | Conflict ID matching extracted directly from pipeline tool execution events. |
| **4. Security Detection Accuracy** | **100.0%** | Deterministic security checkpoint accuracy. |
| **5. Parse Failure Count** | **0** | Zero unparsed or defaulted LLM report structures. |

### 🔍 Verified Category Breakdown ($n = 21$)

| Category | Total ($n$) | Auto-Ans | Novelty Correct | Escalated | Parse Fail | Novelty Acc | Conflict Acc |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`clear_novelty`** | 6 | 6 | 5 | 0 | 0 | **83.3%** | 66.7% |
| **`clear_conflict`** | 7 | 7 | 7 | 0 | 0 | **100.0%** | **100.0%** |
| **`ambiguous`** | 4 | 4 | 3 | 0 | 0 | **75.0%** | **100.0%** |
| **`security_violation`** | 2 | 2 | 2 | 0 | 0 | **100.0%** | **100.0%** |
| **`malformed`** | 2 | 2 | 2 | 0 | 0 | **100.0%** | **100.0%** |
| **VERIFIED OVERALL** | **21** | **21** | **19** | **0** | **0** | **90.5%** | **90.5%** |

### 💡 Baseline Calibration Comparison & Inflation Summary
*   **Metric Integrity Restored**: Sourcing `matched_patent_id` directly from pipeline execution events confirmed 100% agreement with vector RAG search ($0$ divergences), validating that the vector tier outputs delivered to `llm_reviewer` during evaluation perfectly reflect actual deployed pipeline behavior.
*   **Harness Soundness**: With silent regex fallbacks removed (`parse_failure_count: 0`) and explicit `CEILING_ESCALATED` routing active, the baseline is locked and ready to serve as the ground-truth benchmark for the multi-agent critique loop phase.
