# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import json
import logging
import google.auth
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, Depends, Security
from pydantic import BaseModel, EmailStr
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from google.adk.cli.fast_api import get_fast_api_app, create_session_service_from_options
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types

from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback
from expense_agent.agent import root_agent
from expense_agent.db import (
    initialize_db, create_organization, create_user, get_user_by_email,
    create_submission, get_submission, list_submissions, update_submission_status,
    create_audit_log, list_audit_logs
)
from expense_agent.auth import (
    create_access_token, decode_access_token, hash_password, verify_password
)

# Standard Python logging configuration for console output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

setup_telemetry()
_, project_id = google.auth.default()

allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

# Artifact bucket for ADK (created by Terraform, passed via env var)
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
session_service_uri = None
artifact_service_uri = f"gs://{logs_bucket_name}" if logs_bucket_name else None

# Initialize the main FastAPI application using get_fast_api_app
# otel_to_cloud is set to False per security/operational guidelines
app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=artifact_service_uri,
    allow_origins=allow_origins,
    session_service_uri=session_service_uri,
    otel_to_cloud=False,
)
app.title = "ambient-expense-agent"
app.description = "API for interacting with the Agent ambient-expense-agent"

from expense_agent.vector_store import get_vector_store_stats

# Re-use the same session service database configuration as DevServer/ApiServer
session_service = create_session_service_from_options(
    base_dir=AGENT_DIR,
    session_service_uri=session_service_uri,
    use_local_storage=True
)

@app.on_event("startup")
def startup_event():
    initialize_db()
    # Seed organizations and users
    create_organization("org_a", "Organization A")
    create_organization("org_b", "Organization B")
    create_organization("org_eval", "Evaluation Org")
    
    pw_hash = hash_password("password123")
    
    # Org A users
    create_user("user_a_submitter", "org_a", "submitter@orga.com", "submitter", pw_hash)
    create_user("user_a_counsel", "org_a", "counsel@orga.com", "counsel", pw_hash)
    create_user("user_a_admin", "org_a", "admin@orga.com", "admin", pw_hash)
    
    # Org B users
    create_user("user_b_submitter", "org_b", "submitter@orgb.com", "submitter", pw_hash)
    create_user("user_b_counsel", "org_b", "counsel@orgb.com", "counsel", pw_hash)
    
    # Org Eval user
    create_user("user_eval", "org_eval", "eval@orgeval.com", "counsel", pw_hash)

@app.get("/health/vector-store")
async def health_vector_store():
    """Health check endpoint returning vector database status and document count."""
    return get_vector_store_stats()

# Global runner instance targeting the root agent
runner = Runner(
    agent=root_agent,
    session_service=session_service,
    app_name="app"
)


def is_hitl_paused(event: types.Content) -> bool:
    """Helper to detect if a workflow event represents a request for human input (HITL)."""
    if not (event.content and event.content.parts):
        return False
    return any(
        p.function_call and p.function_call.name == "adk_request_input"
        for p in event.content.parts
    )


@app.post("/")
@app.post("/pubsub")
async def handle_pubsub(request: Request):
    """Endpoint that receives Pub/Sub trigger messages, normalizes the subscription path,

    and runs the expense approval workflow.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse JSON body: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(payload, dict) or "message" not in payload:
        logger.error(f"Invalid Pub/Sub push payload format: {payload}")
        raise HTTPException(status_code=400, detail="Payload must contain a 'message' object")

    # 1. Extract and normalize subscription path down to the short name
    sub_path = payload.get("subscription") or "projects/default/subscriptions/default-sub"
    sub_name = sub_path.split("/")[-1] if sub_path else "default-sub"

    # 2. Extract message details
    msg = payload.get("message", {})
    msg_id = msg.get("messageId") or msg.get("message_id") or "unknown-msg-id"

    # 3. Create a clean, unique, and readable session ID using the subscription name
    session_id = f"{sub_name}-{msg_id}"
    logger.info(f"Received Pub/Sub trigger. Sub: {sub_name}, Msg ID: {msg_id}, Session: {session_id}")

    # 4. Create or load the agent session
    try:
        session = await session_service.get_session(
            app_name="app",
            user_id="pubsub_trigger",
            session_id=session_id
        )
        if not session:
            session = await session_service.create_session(
                app_name="app",
                user_id="pubsub_trigger",
                session_id=session_id
            )
    except Exception as e:
        logger.exception(f"Failed to load or create session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize session database record")

    # 5. Wrap the Pub/Sub message dictionary inside a Content payload
    message_text = json.dumps(msg)
    new_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message_text)]
    )

    # 6. Run the workflow runner asynchronously
    try:
        events = []
        async for event in runner.run_async(
            new_message=new_message,
            user_id="pubsub_trigger",
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            events.append(event)
    except Exception as e:
        logger.exception(f"Error executing agent workflow for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Workflow execution error: {e}")

    # 7. Check if workflow suspended (paused) for HITL or completed
    is_paused = False
    final_output = None

    for e in events:
        if getattr(e, "output", None) is not None:
            final_output = e.output
        if is_hitl_paused(e):
            is_paused = True

    if is_paused:
        logger.info(f"Workflow session {session_id} suspended. Pending human manual review.")
        return {
            "status": "PAUSED_FOR_REVIEW",
            "session_id": session_id,
            "message": "Expense report is pending human approval."
        }

    status = "UNKNOWN"
    reason = ""
    if final_output:
        if isinstance(final_output, dict):
            status = final_output.get("status", "UNKNOWN")
            reason = final_output.get("reason", "")
        else:
            status = getattr(final_output, "status", "UNKNOWN")
            reason = getattr(final_output, "reason", "")

    logger.info(f"Workflow session {session_id} completed. Status: {status}, Reason: {reason}")
    return {
        "status": status,
        "session_id": session_id,
        "reason": reason
    }


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback."""
    logger.info(f"Feedback collected: {feedback.model_dump()}")
    return {"status": "success"}


# JWT Security Dependency
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

class LoginPayload(BaseModel):
    email: EmailStr
    password: str

@app.post("/auth/login")
async def login(payload: LoginPayload):
    user = get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({
        "user_id": user["user_id"],
        "org_id": user["org_id"],
        "role": user["role"]
    })
    return {"access_token": token, "token_type": "bearer"}

class SubmissionPayload(BaseModel):
    title: str
    description: str
    libraries_used: list[str] = []

@app.post("/submissions")
async def submit_innovation(
    payload: SubmissionPayload,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] not in ("submitter", "admin", "counsel"):
        raise HTTPException(status_code=403, detail="Forbidden")
        
    org_id = current_user["org_id"]
    user_id = current_user["user_id"]
    
    import uuid
    submission_id = f"sub-{org_id}-{uuid.uuid4().hex[:8]}"
    
    status = "PAUSED_FOR_REVIEW"
    reason = ""
    if not payload.title.strip() or len(payload.description.strip()) < 15:
        status = "REJECTED"
        reason = "Malformed submission with empty title or short description."
        
    create_submission(
        submission_id=submission_id,
        org_id=org_id,
        user_id=user_id,
        title=payload.title,
        description=payload.description,
        libraries_used=payload.libraries_used,
        status=status,
        reason=reason
    )
    
    if status == "REJECTED":
        create_audit_log(
            org_id=org_id,
            submission_id=submission_id,
            query_audit={"reason": "Rejected by parser checks."},
            verifier_audit=[],
            arbiter_audit=None
        )
        return {
            "status": "REJECTED",
            "submission_id": submission_id,
            "reason": reason
        }
        
    try:
        session = await session_service.get_session(
            app_name="app",
            user_id=user_id,
            session_id=submission_id
        )
        if not session:
            session = await session_service.create_session(
                app_name="app",
                user_id=user_id,
                session_id=submission_id
            )
    except Exception as e:
        logger.exception(f"Failed to load or create session {submission_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize session database record")

    input_dict = {
        "data": {
            "title": payload.title,
            "submitter": user_id,
            "department": "R&D",
            "description": payload.description,
            "libraries_used": payload.libraries_used,
            "date": datetime.now().strftime("%Y-%m-%d")
        }
    }
    new_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=json.dumps(input_dict))]
    )

    try:
        events = []
        async for event in runner.run_async(
            new_message=new_message,
            user_id=user_id,
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            events.append(event)
    except Exception as e:
        logger.exception(f"Error executing agent workflow for session {submission_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Workflow execution error: {e}")

    is_paused = False
    final_output = None

    for e in events:
        if getattr(e, "output", None) is not None:
            final_output = e.output
        if is_hitl_paused(e):
            is_paused = True
            
    session_state = getattr(session, "state", {})
    query_audit = session_state.get("query_audit")
    verifier_audit = session_state.get("verifier_audit", [])
    arbiter_audit = session_state.get("arbiter_audit")
    
    create_audit_log(
        org_id=org_id,
        submission_id=submission_id,
        query_audit=query_audit,
        verifier_audit=verifier_audit,
        arbiter_audit=arbiter_audit
    )

    if is_paused:
        return {
            "status": "PAUSED_FOR_REVIEW",
            "submission_id": submission_id,
            "message": "Expense report is pending human approval."
        }

    status = "UNKNOWN"
    reason = ""
    if final_output:
        if isinstance(final_output, dict):
            status = final_output.get("status", "UNKNOWN")
            reason = final_output.get("reason", "")
        else:
            status = getattr(final_output, "status", "UNKNOWN")
            reason = getattr(final_output, "reason", "")
            
    update_submission_status(org_id, submission_id, status, reason)

    return {
        "status": status,
        "submission_id": submission_id,
        "reason": reason
    }

@app.get("/submissions")
async def list_submissions_endpoint(
    current_user: dict = Depends(get_current_user)
):
    org_id = current_user["org_id"]
    role = current_user["role"]
    user_id = current_user["user_id"]
    
    filter_user_id = user_id if role == "submitter" else None
    return list_submissions(org_id, filter_user_id)

@app.get("/submissions/{submission_id}")
async def get_submission_endpoint(
    submission_id: str,
    current_user: dict = Depends(get_current_user)
):
    org_id = current_user["org_id"]
    sub = get_submission(org_id, submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return sub

class ReviewPayload(BaseModel):
    decision: str
    comment: str = ""

@app.post("/submissions/{submission_id}/review")
async def review_submission(
    submission_id: str,
    payload: ReviewPayload,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "counsel":
        raise HTTPException(status_code=403, detail="Forbidden")
        
    org_id = current_user["org_id"]
    
    sub = get_submission(org_id, submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
        
    if sub["status"] != "PAUSED_FOR_REVIEW":
        raise HTTPException(status_code=400, detail="Submission is not pending review")
        
    try:
        session = await session_service.get_session(
            app_name="app",
            user_id=sub["user_id"],
            session_id=submission_id
        )
        if not session:
            session = await session_service.create_session(
                app_name="app",
                user_id=sub["user_id"],
                session_id=submission_id
            )
            
        decision_dict = {
            "decision": payload.decision,
            "comment": payload.comment
        }
        new_message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=json.dumps(decision_dict))]
        )
        
        events = []
        async for event in runner.run_async(
            new_message=new_message,
            user_id=sub["user_id"],
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            events.append(event)
            
        final_output = None
        for e in events:
            if getattr(e, "output", None) is not None:
                final_output = e.output
                
        status = "UNKNOWN"
        reason = ""
        if final_output:
            if isinstance(final_output, dict):
                status = final_output.get("status", "UNKNOWN")
                reason = final_output.get("reason", "")
            else:
                status = getattr(final_output, "status", "UNKNOWN")
                reason = getattr(final_output, "reason", "")
                
        update_submission_status(org_id, submission_id, status, reason)
        return {
            "status": status,
            "submission_id": submission_id,
            "reason": reason
        }
    except Exception as e:
        logger.exception(f"Error reviewing submission {submission_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Review processing error: {e}")

@app.get("/audit-logs")
async def list_audit_logs_endpoint(
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] not in ("counsel", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
        
    org_id = current_user["org_id"]
    return list_audit_logs(org_id)


# Main execution - serving on port 8080
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
