# Root Cause Analysis: Counsel Workflow Resumption Defect

**Bug Title**: Counsel Approve/Reject Workflow Resumption Interruption Bypass  
**Root Cause File**: `app/fast_api_app.py`  
**Date Logged**: 2026-08-02  
**Original Implementation Commit**: `5249b0e` ("Implement Multi-Tenant Foundation with Auth, Isolation, and Adversarial Tests")  

---

## 📌 Root Cause Analysis

### 1. The Defect Description
When Counsel submitted an Approve or Reject decision via the `/submissions/{submission_id}/review` endpoint, the workflow failed to resume the paused `human_review` node and instead restarted the entire workflow from the initial `START` node (`parse_submission`). This resulted in every submission—regardless of Counsel's actual decision—being routed to the `fast_reject` fallback node and saved as `REJECTED` with the reason *"Auto-rejected: Incomplete submission. Title must be present, and description must be at least 15 characters long."*

### 2. Technical Explanation
The bug was caused by a two-fold integration gap with the ADK 2.0 graph engine:
1. **Missing `invocation_id`:** When calling `runner.run_async()`, the code did not pass the paused invocation's `invocation_id`. Without an explicit `invocation_id`, the ADK runner assumed this was a brand new user request and restarted execution from the `START` node.
2. **Text Part vs. Function Response Part:** The decision payload was passed as a raw text content part (`Part.from_text(...)`). However, the ADK runner expects responses to human-in-the-loop interrupts (`adk_request_input`) to be mapped back as a structured `FunctionResponse` content part using the corresponding function call ID of the active interrupt.

### 3. Verification Gap History
* **How it went undetected:** When the `/review` endpoint was originally built in `5249b0e`, it was unit-tested in isolation using mock assertions that checked only the HTTP `200 OK` response status, rather than verifying the final resolved database state of the resumed workflow. 
* **The Lesson:** Any endpoint that resumes a paused/interrupted workflow needs an end-to-end test that checks the final resolved outcome (e.g. database status and reasons), not just that the endpoint returns success — this is the same class of gap as the earlier mocked-LLM and silent-parsing-default issues.

---

## 🔬 Codebase Audit (Task 3)

We ran an audit across the entire Python codebase using the following command to search for all occurrences of ADK session resumption or `adk_request_input` handling:
```bash
grep -rn "adk_request_input\|invocation_id\|function_response\|resume" --include="*.py" --exclude-dir=".venv" .
```

### Audit Scope and Findings:
* **`app/fast_api_app.py`**: The `/submissions/{submission_id}/review` endpoint is the **only** API endpoint in the web application that handles session resumption or processes `adk_request_input` interrupts.
* **`tests/` and `scratch/`**: Other occurrences of resumption patterns were found strictly in test scripts (`test_agent.py`) and debugging utilities (`run_real_test_cases.py`), all of which correctly utilize the structured `FunctionResponse` payload to simulate human decisions.
* **Conclusion**: No other production code paths contain the workflow resumption bug.
