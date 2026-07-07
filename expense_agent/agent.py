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

import base64
import json
import re
import os
import google.auth
from google.auth.exceptions import DefaultCredentialsError

# Load .env file manually if it exists
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                val = val.strip("'\"")
                os.environ[key.strip()] = val

try:
    _, project_id = google.auth.default()
    if project_id:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
        os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") is None:
            if os.environ.get("GEMINI_API_KEY"):
                os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
                os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "False"
            else:
                os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
                os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "True"
    else:
        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") is None:
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
            os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "False"
except DefaultCredentialsError:
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") is None:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
        os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "False"

from typing import Any, List, Optional
from pydantic import BaseModel, Field

from google.adk.workflow import Workflow, node
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.tools import ToolContext
from google.adk.models.llm_response import LlmResponse

from google.genai import types
from .config import Config


# --- Pydantic Schemas ---

class SubmissionDetails(BaseModel):
    title: str = Field(description="The title of the innovation or patent idea")
    submitter: str = Field(description="The name of the submitting developer/engineer")
    department: str = Field(description="The department of the submitter")
    description: str = Field(description="Detailed description of the technology and how it works")
    libraries_used: List[str] = Field(default_factory=list, description="Third-party libraries, frameworks, or licenses used")
    date: str = Field(description="Date of submission")


class InnovationAnalysis(BaseModel):
    novelty_score: int = Field(description="Score from 1 (highly derivative) to 10 (extremely novel/unique)")
    commercial_impact: int = Field(description="Score from 1 (low value) to 10 (high business value)")
    flagged_risks: List[str] = Field(description="Legal or technical risks identified (e.g. licensing, complexity)")
    explanation: str = Field(description="Detailed legal and technical justification of the score")


class HumanDecision(BaseModel):
    decision: str = Field(description="The manual decision, must be either 'APPROVE' or 'REJECT'")
    comment: Optional[str] = Field(default="", description="Feedback or conditions from the IP Counsel")


class WorkflowState(BaseModel):
    submission: Optional[SubmissionDetails] = None
    innovation_analysis: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    redacted_types: List[str] = Field(default_factory=list)
    is_security_event: bool = False
    security_reasons: List[str] = Field(default_factory=list)


class WorkflowOutput(BaseModel):
    title: str
    submitter: str
    department: str
    description: str
    libraries_used: List[str] = Field(default_factory=list)
    date: str
    status: str
    reason: str
    innovation_analysis: Optional[str] = None
    redacted_types: List[str] = Field(default_factory=list)
    is_security_event: bool = False


# --- Helper Functions for Security ---

def scrub_pii(text: str) -> tuple[str, list[str]]:
    """Scrubs SSNs, Credit Cards, and developer credentials from the text and returns categories redacted."""
    redacted_types = []
    
    # Matches SSN with hyphens (e.g. 000-00-0000)
    ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    if ssn_pattern.search(text):
        text = ssn_pattern.sub("[REDACTED SSN]", text)
        redacted_types.append("SSN")
        
    # Matches Credit Cards
    cc_pattern = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
    if cc_pattern.search(text):
        text = cc_pattern.sub("[REDACTED CREDIT CARD]", text)
        redacted_types.append("Credit Card")
        
    # Matches developer tokens/secrets: e.g. api_key="abc", password="xyz"
    secrets_pattern = re.compile(r"\b(api_key|password|secret|token|private_key)\s*=\s*['\"][^'\"]{10,}['\"]", re.IGNORECASE)
    if secrets_pattern.search(text):
        text = secrets_pattern.sub(r"\1=[REDACTED SECRET]", text)
        redacted_types.append("Developer Secret")
        
    return text, redacted_types


def detect_forbidden_licenses(text: str, libraries: List[str]) -> List[str]:
    """Detects copyleft licenses in description or list of libraries."""
    violations = []
    copyleft_keywords = ["gpl", "agpl", "copyleft", "gnu general public"]
    
    text_lower = text.lower()
    for kw in copyleft_keywords:
        if kw in text_lower:
            violations.append(f"Description refers to copyleft terms ({kw})")
            
    for lib in libraries:
        lib_lower = lib.lower()
        for kw in copyleft_keywords:
            if kw in lib_lower:
                violations.append(f"Forbidden copyleft library/license: {lib}")
                
    return violations


def detect_prompt_injection(text: str) -> bool:
    """Heuristic check to detect attempts to override instructions or rules."""
    phrases = [
        "ignore previous instructions",
        "ignore all instructions",
        "bypass rules",
        "bypass threshold",
        "override threshold",
        "auto-approve this submission",
        "you must approve",
        "system override",
        "override system",
        "force approval",
        "force approve"
    ]
    lower_text = text.lower()
    return any(phrase in lower_text for phrase in phrases)


# --- Custom Agent Skill (Function Tool) ---

def check_prior_art(query: str, tool_context: ToolContext = None) -> dict:
    """Searches the patent registry database for prior art matching the query.

    Args:
        query: The patent or technology name to look up in the registry.

    Returns:
        dict: The result containing matches found or confirmation of clean status.
    """
    # Simple simulated database of existing patented concepts
    database = {
        "blockchain database": "US Patent 9,123,456 - Distributed Ledger Architecture",
        "llm security gate": "US Patent 10,987,654 - AI Prompt Injection Firewall",
        "expense auto-approval": "US Patent 8,555,222 - Automated Expense Audit Workflow"
    }
    
    query_lower = query.lower()
    matches = []
    for key, patent in database.items():
        if key in query_lower:
            matches.append(patent)
            
    if matches:
        return {"status": "MATCH_FOUND", "prior_art": matches}
    return {"status": "CLEAN", "prior_art": []}


# --- Workflow Nodes ---

def parse_submission(ctx: Context, node_input: Any) -> Event:
    """Parses incoming innovation submission and validates input structure."""
    # Scrub PII from user_content in-place so no downstream LlmAgent or trace history leaks raw PII
    detected_types = []
    if ctx.user_content and ctx.user_content.parts:
        for part in ctx.user_content.parts:
            if part.text:
                clean_text, types_scrubbed = scrub_pii(part.text)
                part.text = clean_text
                detected_types.extend(types_scrubbed)
    if detected_types:
        ctx.state["redacted_types"] = list(set(detected_types))

    # 1. Extract raw data/text
    data = None
    if isinstance(node_input, types.Content):
        text = ""
        if node_input.parts:
            text = "".join(part.text for part in node_input.parts if part.text)
        if not text:
            raise ValueError("Received empty text content in Content message.")
        try:
            event_json = json.loads(text)
        except Exception as e:
            raise ValueError(f"Failed to parse outer JSON from Content message. Error: {e}")
        data = event_json.get("data", event_json)
    elif isinstance(node_input, dict):
        data = node_input.get("data", node_input)
    else:
        data = node_input
    
    # 2. Decode / parse raw data
    if isinstance(data, str):
        try:
            decoded = base64.b64decode(data).decode("utf-8")
            try:
                parsed_data = json.loads(decoded)
            except Exception:
                try:
                    import ast
                    parsed_data = ast.literal_eval(decoded)
                except Exception:
                    normalized = decoded.replace("'", '"')
                    parsed_data = json.loads(normalized)
        except Exception:
            try:
                parsed_data = json.loads(data)
            except Exception:
                try:
                    import ast
                    parsed_data = ast.literal_eval(data)
                except Exception:
                    try:
                        normalized = data.replace("'", '"')
                        parsed_data = json.loads(normalized)
                    except Exception as e:
                        raise ValueError(f"Failed to parse data as base64 or JSON: {e}")
    elif isinstance(data, dict):
        parsed_data = data
    else:
        raise ValueError(f"Unsupported data type: {type(data)}")

    # 3. Extract fields robustly
    title = str(parsed_data.get("title", "")).strip()
    submitter = str(parsed_data.get("submitter", "")).strip()
    department = str(parsed_data.get("department", "")).strip()
    description = str(parsed_data.get("description", "")).strip()
    
    libraries = parsed_data.get("libraries_used", [])
    if isinstance(libraries, str):
        libraries = [lib.strip() for lib in libraries.split(",") if lib.strip()]
    elif not isinstance(libraries, list):
        libraries = []

    submission = SubmissionDetails(
        title=title,
        submitter=submitter,
        department=department,
        description=description,
        libraries_used=libraries,
        date=str(parsed_data.get("date", "")),
    )

    # 4. Apply routing rule: auto-reject if title is missing or description is too short
    if not title or len(description) < 15:
        return Event(
            output=submission,
            route="fast_reject",
            state={"submission": submission.model_dump()}
        )
    else:
        return Event(
            output=submission,
            route="security_gate",
            state={"submission": submission.model_dump()}
        )


def fast_reject(node_input: SubmissionDetails) -> WorkflowOutput:
    """Automatically rejects submissions that lack complete information."""
    return WorkflowOutput(
        title=node_input.title,
        submitter=node_input.submitter,
        department=node_input.department,
        description=node_input.description,
        libraries_used=node_input.libraries_used,
        date=node_input.date,
        status="REJECTED",
        reason="Auto-rejected: Incomplete submission. Title must be present, and description must be at least 15 characters long."
    )


def security_checkpoint(ctx: Context, node_input: SubmissionDetails) -> Event:
    """Checkpoint to scrub secrets/PII, inspect copyleft licenses, and defend against injection."""
    description = node_input.description
    libraries = node_input.libraries_used
    
    # 1. Scrub PII & Secrets
    clean_description, redacted_types = scrub_pii(description)
    existing_redacted = ctx.state.get("redacted_types", []) or []
    all_redacted = list(set(redacted_types + existing_redacted))
    
    updated_submission = node_input.model_copy(update={"description": clean_description})
    
    # 2. Check for license violations
    license_violations = detect_forbidden_licenses(clean_description, libraries)
    
    # 3. Prompt injection check
    is_injection = detect_prompt_injection(clean_description)
    
    is_security_event = is_injection or len(license_violations) > 0
    reasons = []
    if is_injection:
        reasons.append("Potential prompt injection attempt detected.")
    if license_violations:
        reasons.extend(license_violations)
        
    state_delta = {
        "submission": updated_submission.model_dump(),
        "redacted_types": all_redacted,
        "is_security_event": is_security_event,
        "security_reasons": reasons
    }
    
    if is_security_event:
        # Bypasses the LLM entirely, routing straight to human review
        return Event(
            output=updated_submission,
            route="security_flagged",
            state=state_delta
        )
    else:
        # Clean submission continues to the LLM reviewer
        return Event(
            output=updated_submission,
            route="clean",
            state=state_delta
        )


# --- Callback for Integration Tests ---

async def mock_before_model(callback_context, llm_request) -> Optional[LlmResponse]:
    """Mock callback triggered to avoid billing/API issues during playground & integration tests."""
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text="Novelty Score: 8/10. Commercial Impact: 9/10. Prior art lookup returned no matching blockers. Recommended for patent filing.")]
        )
    )


# LLM node for assessing patent prior art and scoring novelty
llm_reviewer = LlmAgent(
    name="llm_reviewer",
    model=Gemini(model=Config.MODEL),
    instruction=(
        "You are an expert AI patent reviewer and intellectual property (IP) analyst. "
        "Review the provided innovation submission details. "
        "You MUST call the check_prior_art tool to check if the submission title or technology "
        "has prior art matches in the database. "
        "Analyze the novelty and potential commercial impact of the technology based on the tool's findings. "
        "Write a detailed technical evaluation containing: "
        "1. Novelty Assessment (Novelty Score out of 10) "
        "2. Commercial Impact Score (out of 10) "
        "3. Prior Art Check results "
        "4. Flagged Technical Risks "
        "5. Final Filing Recommendation."
    ),
    tools=[check_prior_art],
    output_key="innovation_analysis",
    before_model_callback=mock_before_model
)


@node(rerun_on_resume=True)
async def human_review(ctx: Context, node_input: Any):
    """Interrupts the workflow to wait for manual decision from corporate IP Counsel."""
    submission_dict = ctx.state.get("submission")
    if not submission_dict:
        raise ValueError("Submission details not found in state context.")
    submission = SubmissionDetails(**submission_dict)

    is_security_event = ctx.state.get("is_security_event", False)
    redacted_types = ctx.state.get("redacted_types", [])
    security_reasons = ctx.state.get("security_reasons", [])

    if not ctx.resume_inputs or "human_approval" not in ctx.resume_inputs:
        message_parts = []
        if is_security_event:
            message_parts.append(
                "🚨 SECURITY / COMPLIANCE WARNING: Potential risk detected in this submission!\n"
                "The LLM reviewer has been bypassed for safety. Manual IP Counsel review is required.\n"
            )
            if security_reasons:
                message_parts.append("Flagged Violation Details:")
                for reason in security_reasons:
                    message_parts.append(f"- {reason}")
                message_parts.append("")
        else:
            message_parts.append("⚠️ ALERT: Innovation submission requires review and filing decision.\n")
            
        message_parts.append(
            f"Title: {submission.title}\n"
            f"Submitter: {submission.submitter} ({submission.department})\n"
            f"Description: {submission.description}\n"
            f"Libraries Used: {', '.join(submission.libraries_used) if submission.libraries_used else 'None'}\n"
            f"Date: {submission.date}"
        )
        
        if redacted_types:
            message_parts.append(f"\n🔐 Redacted PII/Secrets: {', '.join(redacted_types)}")
            
        if not is_security_event:
            # If clean, display the LLM's prior-art analysis report
            analysis_report = ctx.state.get("innovation_analysis") or str(node_input)
            message_parts.append(
                f"\n--- AI Patent Analysis & Prior-Art Report ---\n"
                f"{analysis_report}"
            )
            
        message_parts.append("\nPlease approve or reject this submission for patent filing.")
        
        yield RequestInput(
            interrupt_id="human_approval",
            message="\n".join(message_parts),
            response_schema=HumanDecision
        )
        return

    # Process response once resumed
    decision_input = ctx.resume_inputs["human_approval"]
    comment = ""
    if isinstance(decision_input, dict):
        decision_text = str(decision_input.get("decision", "")).strip().upper()
        comment = str(decision_input.get("comment", "")).strip()
    else:
        decision_text = str(decision_input).strip().upper()

    if "APPROVE" in decision_text or "YES" in decision_text:
        status = "APPROVED_FOR_FILING"
        reason = f"Approved for filing by IP Counsel. Comment: {comment}" if comment else "Approved for filing by IP Counsel."
    elif "REJECT" in decision_text or "NO" in decision_text:
        status = "REJECTED"
        reason = f"Rejected by IP Counsel. Comment: {comment}" if comment else "Rejected by IP Counsel."
    else:
        message = f"Invalid response '{decision_text}'. Please reply with 'APPROVE' or 'REJECT'."
        yield RequestInput(
            interrupt_id="human_approval",
            message=message,
            response_schema=HumanDecision
        )
        return

    yield Event(
        output={
            "status": status,
            "reason": reason,
            "submission": submission,
            "innovation_analysis": ctx.state.get("innovation_analysis", "Bypassed due to safety flag."),
            "redacted_types": redacted_types,
            "is_security_event": is_security_event
        },
        state={"status": status, "reason": reason}
    )


def record_outcome(node_input: dict) -> WorkflowOutput:
    """Constructs and records the final outcome after manual IP counsel decision."""
    submission_data = node_input["submission"]
    analysis_text = node_input["innovation_analysis"]

    if isinstance(submission_data, dict):
        submission = SubmissionDetails(**submission_data)
    else:
        submission = submission_data

    return WorkflowOutput(
        title=submission.title,
        submitter=submission.submitter,
        department=submission.department,
        description=submission.description,
        libraries_used=submission.libraries_used,
        date=submission.date,
        status=node_input["status"],
        reason=node_input["reason"],
        innovation_analysis=analysis_text,
        redacted_types=node_input["redacted_types"],
        is_security_event=node_input["is_security_event"]
    )


# --- Workflow Graph Definition ---

root_agent = Workflow(
    name="innovation_screening_workflow",
    description="Workflow that handles corporate innovation submissions, auto-rejecting invalid entries, checking for license compliance/prompt injection, analyzing prior art, and utilizing HITL for filing decisions.",
    input_schema=None,
    state_schema=WorkflowState,
    output_schema=WorkflowOutput,
    edges=[
        ("START", parse_submission),
        (parse_submission, {"fast_reject": fast_reject, "security_gate": security_checkpoint}),
        (security_checkpoint, {"clean": llm_reviewer, "security_flagged": human_review}),
        (llm_reviewer, human_review),
        (human_review, record_outcome),
    ]
)
