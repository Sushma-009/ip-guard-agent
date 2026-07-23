# Multi-Agent Critique Loop Verification

This document records the factual tracing and verification checks performed to validate the multi-agent critique loop metrics under real, paced Gemini API execution (without offline mocks).

---

## 🔐 Real-LLM Baseline Performance Summary

The evaluation harness was run end-to-end against the real Gemini API (`gemini-3.1-flash-lite`) with active rate-limiting pacing (5-second delays between API requests and 12-second delays between cases) and exponential backoff.

*   **Evaluation Date**: 2026-07-23
*   **Result Details Artifact**: `eval/results/eval_results_20260723_124351.json`
*   **Total Cases**: 21
*   **Novelty Band Accuracy (Auto-Answered)**: **88.9%** (16/18 cases correct)
*   **Conflict ID Accuracy (Event-Sourced)**: **100.0%** (21/21 cases correct)
*   **Escalation Rate**: **0.0%** (0 cases escalated)
*   **Security Detection Accuracy**: **100.0%** (2/2 cases correct)

---

## 🔍 Novelty/Conflict Gap & Miss Trace

Under real model conditions, there are exactly 2 cases where the novelty band did not match the expected ground truth: `eval_013` and `eval_021`. Both represent the calibration gap identified in the A2 design brief.

### 1. `eval_013`
*   **Matched Patent ID**: `US9123460B2` (Optimistic rollup fraud-proof system)
*   **Expected Novelty Band**: `MEDIUM`
*   **Actual Novelty Band**: `LOW` (Novelty Score: `3/10`)
*   **Mechanism Trace**: 
    1. The `MatchVerifier` correctly classified the relationship as `VERIFIED_CONFLICT_WITH_DIFFERENTIATOR` (`is_verified = True`) because both describe L2 transaction compression engines, but the submission uses validity ZK-proofs instead of fraud-proofs.
    2. Because a verified conflict was present, the pipeline invoked the `ConflictArbiter`.
    3. The real `ConflictArbiter` evaluated the submission's description and concluded that a standard ZK-rollup architecture (without additional innovations like decentralized MPC witness generation or L1/L2 privacy layers) is a standard architectural integration and does not warrant a `MEDIUM` band. It returned `final_band: LOW`, forcing a `LOW` score.

### 2. `eval_021`
*   **Matched Patent ID**: `US9876548B2` (Symmetric index-based database search)
*   **Expected Novelty Band**: `MEDIUM`
*   **Actual Novelty Band**: `LOW` (Novelty Score: `3/10`)
*   **Mechanism Trace**:
    1. The `MatchVerifier` correctly classified the relationship as `VERIFIED_CONFLICT_WITH_DIFFERENTIATOR` (`is_verified = True`) because both execute searchable symmetric encryption (SSE) over database columns, but the submission adds homomorphic MPC threshold key custody.
    2. Because a verified conflict was present, the pipeline successfully invoked the `ConflictArbiter`.
    3. The `ConflictArbiter` analyzed the submission and ruled that the combination of static homomorphic MPC threshold key custody with standard SSE queries represents a logical application of existing cryptographic building blocks, rather than a novel security model (unless it introduced proactive secret re-sharding or dynamic temporal guarantees). It returned `final_band: LOW`, maintaining the rigid `LOW` ceiling.

---

## 🧪 ConflictArbiter Invocation Verification

In this real API run, **ConflictArbiter.arbitrate() was successfully invoked 10 times** for the following case IDs:
- `eval_007`, `eval_008`, `eval_009`, `eval_010`, `eval_011`, `eval_012`, `eval_013`, `eval_014`, `eval_016`, `eval_021`

### 💡 Calibration Takeaway
The MatchVerifier is no longer over-rejecting matches (which was bypassing the arbiter in earlier mock-wiring drafts). The ConflictArbiter now fires reliably on all verified high-conflict candidates. Its decision to score `eval_013` and `eval_021` as `LOW` reflects genuine model reasoning on the strength of the differentiators under zero-temperature conditions, confirming the scoping brief's assertion that single-point threshold calibration is unvalidated until more A2 candidate cases are tested.
