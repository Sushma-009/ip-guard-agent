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
from fastapi import FastAPI, Request, HTTPException
from google.adk.cli.fast_api import get_fast_api_app, create_session_service_from_options
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types

from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback
from expense_agent.agent import root_agent

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


# Main execution - serving on port 8080
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
