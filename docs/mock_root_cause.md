# Production Pipeline De-Mock Audit & Root Cause Analysis

**Audit Target**: `expense_agent/agent.py`  
**Date**: 2026-07-21  

---

## 📌 Task 1: Git History Trace

*   **Commit Hash**: `3346ce85092a859dcf67732ed77a7dbf822e2e6f`
*   **Author**: Sushma Ananthaneni
*   **Date**: `Tue Jul 7 10:50:57 2026 +0530`
*   **Commit Message**: `feat: pivot to IP-Guard patent screener capstone`
*   **Factual History Account**:
    *   The `mock_before_model` callback was introduced at line 373 of `expense_agent/agent.py` during the initial project pivot from ambient expense reporting to IP-Guard patent screening (`3346ce8`).
    *   It was intended as temporary test scaffolding (`# --- Callback for Integration Tests ---`) to prevent burning Google Gemini API quota during local workflow graph development.
    *   However, `before_model_callback=mock_before_model` was attached directly to the core `llm_reviewer` agent definition at Line 464 inside `agent.py`. It was never removed prior to running evaluations, causing all subsequent evaluation runs (and production server requests) to execute against Python template strings rather than real Gemini LLM API calls.

---

## 🔬 Task 2: Full Graph Node Audit

Every node in the `expense_agent/agent.py` workflow graph was audited to verify whether LLMs are used and whether any mocks exist:

| Node Name | Node Type | Uses LLM? | Callback Attached? | Real or Mocked Status |
| :--- | :--- | :---: | :---: | :--- |
| `parse_submission` | Python `@node` | **No** | None | **Real** (Pure Python JSON parsing & PII scrubbing) |
| `fast_reject` | Python `@node` | **No** | None | **Real** (Pure Python length validation routing) |
| `security_checkpoint` | Python `@node` | **No** | None | **Real** (Pure Python regex PII scrubbing, license checking, & prompt injection heuristics) |
| `llm_reviewer` | `LlmAgent` | **Yes** | `before_model_callback=mock_before_model` | ❌ **MOCKED** (Intercepted by `mock_before_model`; short-circuits Gemini API calls) |
| `human_review` | Python `@node` | **No** | None | **Real** (ADK `RequestInput` interrupt for HITL approval) |
| `record_outcome` | Python `@node` | **No** | None | **Real** (Pure Python output schema mapping) |

### Summary
`llm_reviewer` is the **only node** in the entire system that uses an LLM, and it was the **only node** containing a mock callback.
