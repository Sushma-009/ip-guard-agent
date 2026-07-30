"""Tests confirming query_audit null-vs-failure guarantee and novelty_score no-silent-default.

Task 1: query_audit is null only when the step is architecturally skipped.
         Any exception during audit_query() produces an explicit AUDIT_FAILED object.

Task 2: novelty_score is NULL in the database when unparseable.
         _parse_novelty_score never returns 0 or any default integer.
"""
import pytest
import json
import os
import sys
from unittest.mock import patch

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("JWT_SECRET", "test-secret-for-frontend-checks")

# isolated_db fixture is provided by tests/conftest.py

# --- Task 1: query_audit null-vs-failure guarantee ---

def test_query_audit_failure_produces_explicit_error_object():
    """If audit_query() raises, query_audit must be a non-null error object, not absent."""
    from expense_agent.agent import check_prior_art
    
    class FakeToolContext:
        def __init__(self):
            self.state = {
                "submission": {
                    "title": "Test Invention",
                    "description": "A detailed description of a novel quantum computing technique for error correction"
                }
            }
    
    fake_ctx = FakeToolContext()
    
    # Monkeypatch audit_query to raise, and mock downstream calls to avoid real API hits
    with patch("expense_agent.agent.audit_query", side_effect=RuntimeError("Simulated audit failure")), \
         patch("expense_agent.agent.search_prior_art_vectors", return_value={"status": "CLEAN", "matches": [], "max_similarity": 0.0}):
        result = check_prior_art("quantum computing error correction", tool_context=fake_ctx)
    
    # query_audit must be set (not absent/None)
    assert "query_audit" in fake_ctx.state, "query_audit missing from state after audit failure"
    qa = fake_ctx.state["query_audit"]
    assert qa is not None, "query_audit is None after audit failure — should be an explicit error object"
    assert qa.get("status") == "AUDIT_FAILED", f"Expected status AUDIT_FAILED, got {qa.get('status')}"
    assert "error" in qa, "Error message missing from AUDIT_FAILED object"
    assert "Simulated audit failure" in qa["error"], f"Error message doesn't contain original exception: {qa['error']}"
    # corrected_query should fall back to the original query, not crash
    assert qa.get("corrected_query") == "quantum computing error correction"
    assert qa.get("is_drifted") is False


def test_query_audit_null_only_on_security_flagged_path(isolated_db):
    """query_audit is legitimately null only for security-flagged submissions
    that never reach the retrieval stage."""
    from expense_agent.db import (
        initialize_db, create_organization, create_user,
        create_submission, create_audit_log, list_audit_logs
    )
    from expense_agent.auth import hash_password
    
    initialize_db()
    
    create_organization("org_test_qa", "Test Org QA")
    create_user("user_test_qa", "org_test_qa", "qa@test.com", "submitter", hash_password("pass"))
    
    # Simulate a security-flagged submission: query_audit is null (never ran)
    create_submission(
        submission_id="sub-sec-001",
        org_id="org_test_qa",
        user_id="user_test_qa",
        title="Security Flagged Sub",
        description="Contains prompt injection attempt",
        libraries_used=[],
        status="SECURITY_FLAGGED",
        reason="Prompt injection detected"
    )
    create_audit_log(
        org_id="org_test_qa",
        submission_id="sub-sec-001",
        query_audit=None,  # Legitimately null: step was architecturally skipped
        verifier_audit=[],
        arbiter_audit=None
    )
    
    logs = list_audit_logs("org_test_qa")
    sec_log = [l for l in logs if l["submission_id"] == "sub-sec-001"][0]
    assert sec_log["query_audit"] is None, "Security-flagged path should have null query_audit"
    
    # Simulate a REJECTED submission: query_audit has explicit rejection reason
    create_submission(
        submission_id="sub-rej-001",
        org_id="org_test_qa",
        user_id="user_test_qa",
        title="",
        description="short",
        libraries_used=[],
        status="REJECTED",
        reason="Malformed"
    )
    create_audit_log(
        org_id="org_test_qa",
        submission_id="sub-rej-001",
        query_audit={"reason": "Rejected by parser checks."},
        verifier_audit=[],
        arbiter_audit=None
    )
    
    logs = list_audit_logs("org_test_qa")
    rej_log = [l for l in logs if l["submission_id"] == "sub-rej-001"][0]
    assert rej_log["query_audit"] is not None, "REJECTED path should have non-null query_audit"
    assert rej_log["query_audit"]["reason"] == "Rejected by parser checks."


# --- Task 2: novelty_score no-silent-default ---

def test_parse_novelty_score_no_silent_zero():
    """_parse_novelty_score must return None (not 0) for unparseable inputs."""
    from app.fast_api_app import _parse_novelty_score
    
    # Valid inputs
    assert _parse_novelty_score("Novelty Score: 8") == 8
    assert _parse_novelty_score("Novelty Assessment (Novelty Score: 3/10)") == 3
    assert _parse_novelty_score("Score is 7/10 overall") == 7
    
    # Unparseable / missing inputs — must return None, never 0
    assert _parse_novelty_score(None) is None, "None input should return None, not 0"
    assert _parse_novelty_score("") is None, "Empty string should return None, not 0"
    assert _parse_novelty_score("No score here") is None, "No match should return None, not 0"
    assert _parse_novelty_score("The score is unknown") is None
    assert _parse_novelty_score(123) is None, "Non-string input should return None, not 0"
    
    # Edge: score out of 1-10 range
    assert _parse_novelty_score("Novelty Score: 0") is None, "Score 0 out of 1-10 range should return None"
    assert _parse_novelty_score("Novelty Score: 15") is None, "Score 15 out of 1-10 range should return None"


def test_novelty_score_stored_as_null_in_database(isolated_db):
    """When novelty_score is None, the database stores SQL NULL, not 0."""
    from expense_agent.db import (
        initialize_db, create_organization, create_user,
        create_submission, update_submission_analysis, get_submission
    )
    from expense_agent.auth import hash_password
    
    initialize_db()
    
    create_organization("org_test_ns", "Test Org NS")
    create_user("user_test_ns", "org_test_ns", "ns@test.com", "submitter", hash_password("pass"))
    
    create_submission(
        submission_id="sub-ns-001",
        org_id="org_test_ns",
        user_id="user_test_ns",
        title="Test Submission",
        description="A sufficiently long description for validation",
        libraries_used=["numpy"],
        status="PAUSED_FOR_REVIEW",
        reason=""
    )
    
    # Persist with None novelty_score (simulating unparseable analysis)
    update_submission_analysis(
        org_id="org_test_ns",
        submission_id="sub-ns-001",
        innovation_analysis="Analysis text without any parseable score",
        novelty_score=None
    )
    
    sub = get_submission("org_test_ns", "sub-ns-001")
    assert sub is not None
    assert sub["innovation_analysis"] == "Analysis text without any parseable score"
    assert sub["novelty_score"] is None, f"Expected NULL, got {sub['novelty_score']} — silent-zero coercion detected"
    
    # Also test with a valid score to confirm the column works
    update_submission_analysis(
        org_id="org_test_ns",
        submission_id="sub-ns-001",
        innovation_analysis="Novelty Score: 7/10. Very novel.",
        novelty_score=7
    )
    
    sub2 = get_submission("org_test_ns", "sub-ns-001")
    assert sub2["novelty_score"] == 7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
