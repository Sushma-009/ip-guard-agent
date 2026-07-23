import pytest
import os
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Define standard environment before imports to ensure startup validation passes
os.environ["JWT_SECRET"] = "super-secret-test-key-12345"

from app.fast_api_app import app
from expense_agent.db import (
    initialize_db, create_organization, create_user, get_user_by_email,
    create_submission, get_submission, list_submissions, list_audit_logs,
    get_connection
)
from expense_agent.auth import hash_password, create_access_token

@pytest.fixture(autouse=True)
def setup_test_db():
    initialize_db()
    
    # Seed Organizations
    create_organization("org_a", "Organization A")
    create_organization("org_b", "Organization B")
    
    # Hash password
    pw_hash = hash_password("password123")
    
    # Seed Users
    create_user("user_a_sub", "org_a", "submitter@orga.com", "submitter", pw_hash)
    create_user("user_a_counsel", "org_a", "counsel@orga.com", "counsel", pw_hash)
    create_user("user_b_sub", "org_b", "submitter@orgb.com", "submitter", pw_hash)
    create_user("user_b_counsel", "org_b", "counsel@orgb.com", "counsel", pw_hash)
    
    yield

def get_auth_header(user_id: str, org_id: str, role: str) -> dict:
    token = create_access_token({"user_id": user_id, "org_id": org_id, "role": role})
    return {"Authorization": f"Bearer {token}"}

# Task 1: Password hashing named library check
def test_password_hash_uses_named_library():
    user = get_user_by_email("submitter@orga.com")
    assert user is not None
    password_hash = user["password_hash"]
    # bcrypt hashes start with $2b$ or $2a$ or $2y$
    assert password_hash.startswith("$2b$") or password_hash.startswith("$2a$")

# Task 2: JWT validation & secret checks
def test_jwt_expired_token_rejected():
    client = TestClient(app)
    # Issue token with past expiry
    past_expiry = datetime.now(timezone.utc) - timedelta(hours=2)
    expired_token = jwt.encode(
        {"user_id": "user_a_sub", "org_id": "org_a", "role": "submitter", "exp": past_expiry},
        os.environ["JWT_SECRET"],
        algorithm="HS256"
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/submissions", headers=headers)
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()

def test_missing_jwt_secret_fails_startup():
    # If JWT_SECRET is absent, importing the module should fail loudly
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError) as exc_info:
            # Re-import or reload to trigger initialization check
            import importlib
            import expense_agent.auth
            importlib.reload(expense_agent.auth)
        assert "JWT_SECRET environment variable is missing or empty" in str(exc_info.value)

# Task 4 & 5: Adversarial isolation verification
def test_cross_tenant_read_blocked():
    client = TestClient(app)
    
    # 1. Create a submission under Org B
    submission_id = "sub-orgb-test1234"
    create_submission(
        submission_id=submission_id,
        org_id="org_b",
        user_id="user_b_sub",
        title="Org B Secret Innovation",
        description="Detailing some top secret Org B algorithms.",
        libraries_used=[],
        status="PAUSED_FOR_REVIEW",
        reason=""
    )
    
    # 2. Attempt to read from Org A user
    headers = get_auth_header("user_a_sub", "org_a", "submitter")
    response = client.get(f"/submissions/{submission_id}", headers=headers)
    
    # Must return exactly 404 (not 403) to prevent resource existence leakage
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_cross_tenant_write_blocked():
    client = TestClient(app)
    
    # Authenticate as Org A, try to submit spoofing Org B in the payload
    # Note: our endpoint does not read org_id from payload, it enforces it from JWT token
    headers = get_auth_header("user_a_sub", "org_a", "submitter")
    payload = {
        "title": "Malicious Spoofed Submission",
        "description": "Attempting to inject a submission into Org B's namespace.",
        "libraries_used": []
    }
    
    # We mock runner.run_async to bypass executing actual LLM / RAG calls in this test
    with patch("app.fast_api_app.runner.run_async") as mock_run:
        # Mock run_async to yield an event showing it paused
        mock_event = MagicMock()
        mock_event.output = None
        
        # Mock human paused input
        mock_part = MagicMock()
        mock_part.function_call.name = "adk_request_input"
        mock_event.content.parts = [mock_part]
        
        async def mock_async_gen(*args, **kwargs):
            yield mock_event
            
        mock_run.return_value = mock_async_gen()
        
        response = client.post("/submissions", json=payload, headers=headers)
        assert response.status_code == 200
        
        submission_id = response.json()["submission_id"]
        
        # Assert that the database row created has org_id = 'org_a', not 'org_b'
        sub = get_submission("org_a", submission_id)
        assert sub is not None
        assert sub["org_id"] == "org_a"
        
        # Verify it cannot be retrieved by org_b
        sub_b = get_submission("org_b", submission_id)
        assert sub_b is None

def test_audit_log_isolation():
    client = TestClient(app)
    
    # Create prerequisite submissions for the audit logs
    create_submission("sub-orga-1", "org_a", "user_a_sub", "Title A", "Description A is here.", [], "PAUSED_FOR_REVIEW", "")
    create_submission("sub-orgb-1", "org_b", "user_b_sub", "Title B", "Description B is here.", [], "PAUSED_FOR_REVIEW", "")
    
    # Create audit logs for Org A and Org B
    from expense_agent.db import create_audit_log
    create_audit_log("org_a", "sub-orga-1", {"q": "a"}, [{"v": "a"}], {"arb": "a"})
    create_audit_log("org_b", "sub-orgb-1", {"q": "b"}, [{"v": "b"}], {"arb": "b"})
    
    # Fetch as Org A counsel
    headers_a = get_auth_header("user_a_counsel", "org_a", "counsel")
    response_a = client.get("/audit-logs", headers=headers_a)
    assert response_a.status_code == 200
    logs_a = response_a.json()
    assert len(logs_a) == 1
    assert logs_a[0]["org_id"] == "org_a"
    assert logs_a[0]["submission_id"] == "sub-orga-1"
    
    # Fetch as Org B counsel
    headers_b = get_auth_header("user_b_counsel", "org_b", "counsel")
    response_b = client.get("/audit-logs", headers=headers_b)
    assert response_b.status_code == 200
    logs_b = response_b.json()
    assert len(logs_b) == 1
    assert logs_b[0]["org_id"] == "org_b"
    assert logs_b[0]["submission_id"] == "sub-orgb-1"

def test_role_boundary_within_org():
    client = TestClient(app)
    
    # Create a submission pending review under Org A
    submission_id = "sub-orga-paused"
    create_submission(
        submission_id=submission_id,
        org_id="org_a",
        user_id="user_a_sub",
        title="Pending Innovation",
        description="A great patent description is here.",
        libraries_used=[],
        status="PAUSED_FOR_REVIEW",
        reason=""
    )
    
    # Attempt to review from submitter role (should fail with 403 Forbidden)
    headers = get_auth_header("user_a_sub", "org_a", "submitter")
    payload = {"decision": "APPROVE", "comment": "Looks good"}
    
    response = client.post(f"/submissions/{submission_id}/review", json=payload, headers=headers)
    assert response.status_code == 403
    
    # Attempt to review from counsel role (should succeed)
    headers_counsel = get_auth_header("user_a_counsel", "org_a", "counsel")
    with patch("app.fast_api_app.runner.run_async") as mock_run:
        mock_event = MagicMock()
        mock_event.output = {"status": "APPROVED_FOR_FILING", "reason": "Approved by Counsel"}
        
        async def mock_async_gen(*args, **kwargs):
            yield mock_event
            
        mock_run.return_value = mock_async_gen()
        
        response_ok = client.post(f"/submissions/{submission_id}/review", json=payload, headers=headers_counsel)
        assert response_ok.status_code == 200
        assert response_ok.json()["status"] == "APPROVED_FOR_FILING"
