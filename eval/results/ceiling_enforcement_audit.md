# HIGH_CONFLICT Novelty Ceiling Enforcement Audit Report

**Evaluation Run Artifact**: `eval/results/eval_results_20260721_154606.json`  
**Date**: 2026-07-21  

---

## 📌 Task 1 Audit Results: Group A vs Group B Breakdown

We audited all 12 cases in the 21-case evaluation dataset where vector retrieval assigned `similarity_tier == "HIGH_CONFLICT"` ($\ge 0.55$).

### Group A: Correct HIGH_CONFLICT Matches (`matched_patent_id == expected_conflict_patent_id`)

| Case ID | Category | Expected Conflict Patent ID | Matched Patent ID | Raw Cosine Sim. | Actual Novelty Score | Compliant ($\le 4/10$)? |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **`eval_007`** | `clear_conflict` | `US9123456B2` | `US9123456B2` | `0.910` | `3/10` | ✅ Yes |
| **`eval_008`** | `clear_conflict` | `US10987654B1` | `US10987654B1` | `0.946` | **`6/10`** | ❌ **Violation (> 4)** |
| **`eval_009`** | `clear_conflict` | `US11234567B2` | `US11234567B2` | `0.927` | `3/10` | ✅ Yes |
| **`eval_010`** | `clear_conflict` | `US10456789B1` | `US10456789B1` | `0.950` | `3/10` | ✅ Yes |
| **`eval_011`** | `clear_conflict` | `US9876543B2` | `US9876543B2` | `0.938` | `3/10` | ✅ Yes |
| **`eval_012`** | `clear_conflict` | `US7654321B2` | `US7654321B2` | `0.940` | `3/10` | ✅ Yes |
| **`eval_013`** | `ambiguous` | `US9123460B2` | `US9123460B2` | `0.634` | **`9/10`** | ❌ **Violation (> 4)** |
| **`eval_014`** | `clear_conflict` | `US10456790B1` | `US10456790B1` | `0.730` | `3/10` | ✅ Yes |
| **`eval_015`** | `ambiguous` | `US10987656B1` | `US10987656B1` | `0.580` | **`9/10`** | ❌ **Violation (> 4)** |
| **`eval_016`** | `ambiguous` | `US7654324B2` | `US7654324B2` | `0.775` | **`6/10`** | ❌ **Violation (> 4)** |
| **`eval_021`** | `ambiguous` | `US9876548B2` | `US9876548B2` | `0.717` | `3/10` | ✅ Yes |

*   **Group A Violation Tally**: **4 out of 11 cases in Group A scored $> 4/10$** (`eval_008`, `eval_013`, `eval_015`, `eval_016`).

---

### Group B: Incorrect / False-Positive HIGH_CONFLICT Matches (`matched_patent_id != expected_conflict_patent_id`)

| Case ID | Category | Expected Conflict Patent ID | Matched Patent ID | Raw Cosine Sim. | Actual Novelty Score | Notes |
| :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| **`eval_001`** | `clear_novelty` | `None` | `US11234569B2` | `0.622` | `6/10` | Retrieval false positive on quantum terms. |

---

## 🎯 Task 1 Decision & Next Step

**Decision**: **Group A shows multiple ceiling violations ($4/11$ cases scored $> 4/10$). Prompt-level guidance alone is unreliable.**

Proceeding to **Task 2**: Implement deterministic post-processing escalation logic (`ceiling_override_needed: true` and `status == PAUSED_FOR_REVIEW`) whenever a `HIGH_CONFLICT` match yields a novelty score $> 4/10$.
