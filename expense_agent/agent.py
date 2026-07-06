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

from google.genai import types
from .config import Config


# --- Pydantic Schemas ---

class ExpenseDetails(BaseModel):
    amount: float
    submitter: str
    category: str
    description: str
    date: str


class ExpenseInput(BaseModel):
    data: Any


class RiskAnalysis(BaseModel):
    risk_score: int = Field(description="Risk score from 1 (low) to 10 (high)")
    risk_factors: List[str] = Field(description="List of identified risk factors")
    explanation: str = Field(description="Brief explanation of the risk assessment")


class HumanDecision(BaseModel):
    decision: str = Field(description="The manual decision, must be either 'APPROVE' or 'REJECT'")


class WorkflowState(BaseModel):
    expense: Optional[ExpenseDetails] = None
    risk_analysis: Optional[RiskAnalysis] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    redacted_types: List[str] = Field(default_factory=list)
    is_security_event: bool = False


class WorkflowOutput(BaseModel):
    amount: float
    submitter: str
    category: str
    description: str
    date: str
    status: str
    reason: str
    risk_analysis: Optional[RiskAnalysis] = None
    redacted_types: List[str] = Field(default_factory=list)
    is_security_event: bool = False


# --- Helper Functions for Security ---

def scrub_pii(text: str) -> tuple[str, list[str]]:
    """Scrubs SSNs and Credit Card numbers from the text and returns categories redacted."""
    redacted_types = []
    
    # Matches SSN with hyphens (e.g. 000-00-0000)
    ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    if ssn_pattern.search(text):
        text = ssn_pattern.sub("[REDACTED SSN]", text)
        redacted_types.append("SSN")
        
    # Matches Credit Cards (13 to 16 digits, with optional spaces/dashes)
    cc_pattern = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
    if cc_pattern.search(text):
        text = cc_pattern.sub("[REDACTED CREDIT CARD]", text)
        redacted_types.append("Credit Card")
        
    return text, redacted_types


def detect_prompt_injection(text: str) -> bool:
    """Heuristic check to detect attempts to override instructions or rules."""
    phrases = [
        "ignore previous instructions",
        "ignore all instructions",
        "bypass rules",
        "bypass threshold",
        "override threshold",
        "auto-approve this expense",
        "you must approve",
        "system override",
        "override system",
        "ignore the threshold",
        "ignore the limit",
        "override the limit",
        "force approval",
        "force approve"
    ]
    lower_text = text.lower()
    return any(phrase in lower_text for phrase in phrases)


# --- Workflow Nodes ---

def parse_expense(ctx: Context, node_input: Any) -> Event:
    """Parses incoming expense data (handling Content objects, base64 and raw JSON), and routes based on threshold."""
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
    elif isinstance(node_input, ExpenseInput):
        data = node_input.data
    elif isinstance(node_input, dict):
        data = node_input.get("data", node_input)
    else:
        data = node_input
    
    # 2. Decode / parse raw data
    if isinstance(data, str):
        try:
            # Try to base64 decode (Pub/Sub message)
            decoded = base64.b64decode(data).decode("utf-8")
            try:
                parsed_data = json.loads(decoded)
            except Exception:
                try:
                    import ast
                    parsed_data = ast.literal_eval(decoded)
                except Exception:
                    # Fix mixed quotes (e.g. 'key") and python-dict string quirks by normalizing single quotes
                    normalized = decoded.replace("'", '"')
                    parsed_data = json.loads(normalized)
        except Exception:
            # Fall back to direct JSON/eval string parsing (local testing)
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
                        raise ValueError(f"Failed to parse data as base64 or JSON/eval/normalized string: {e}")
    elif isinstance(data, dict):
        parsed_data = data
    else:
        raise ValueError(f"Unsupported data type for expense event: {type(data)}")

    # 2. Extract fields robustly
    amount_raw = parsed_data.get("amount", 0.0)
    if isinstance(amount_raw, str):
        amount_raw = amount_raw.replace("$", "").replace(",", "").strip()
    try:
        amount = float(amount_raw)
    except (ValueError, TypeError):
        amount = 0.0

    expense = ExpenseDetails(
        amount=amount,
        submitter=str(parsed_data.get("submitter", "")),
        category=str(parsed_data.get("category", "")),
        description=str(parsed_data.get("description", "")),
        date=str(parsed_data.get("date", "")),
    )

    # 3. Apply routing rule
    if expense.amount < Config.THRESHOLD:
        return Event(
            output=expense,
            route="auto_approve",
            state={"expense": expense.model_dump()}
        )
    else:
        return Event(
            output=expense,
            route="llm_review",
            state={"expense": expense.model_dump()}
        )


def auto_approve(node_input: ExpenseDetails) -> WorkflowOutput:
    """Instantly approves the expense under the threshold, bypassing the LLM."""
    return WorkflowOutput(
        amount=node_input.amount,
        submitter=node_input.submitter,
        category=node_input.category,
        description=node_input.description,
        date=node_input.date,
        status="APPROVED",
        reason=f"Auto-approved: expense amount is below the ${Config.THRESHOLD:.2f} threshold."
    )


def security_checkpoint(ctx: Context, node_input: ExpenseDetails) -> Event:
    """Checkpoint to scrub PII and defend against prompt injection before LLM review."""
    description = node_input.description
    
    # 1. Scrub PII
    clean_description, redacted_types = scrub_pii(description)
    existing_redacted = ctx.state.get("redacted_types", []) or []
    all_redacted = list(set(redacted_types + existing_redacted))
    
    updated_expense = node_input.model_copy(update={"description": clean_description})
    
    # 2. Heuristic prompt injection defense
    is_injection = detect_prompt_injection(clean_description)
    
    state_delta = {
        "expense": updated_expense.model_dump(),
        "redacted_types": all_redacted,
        "is_security_event": is_injection
    }
    
    if is_injection:
        # Bypasses LLM entirely, routes straight to human review
        return Event(
            output=updated_expense,
            route="security_flagged",
            state=state_delta
        )
    else:
        # Clean expense continues on to the LLM reviewer
        return Event(
            output=updated_expense,
            route="clean",
            state=state_delta
        )


# LLM node for reviewing expense for risk factors
llm_reviewer = LlmAgent(
    name="llm_reviewer",
    model=Gemini(model=Config.MODEL),
    instruction=(
        "You are an AI risk assessor for expense reports. Review the provided expense details "
        "and determine if there are any risk factors (e.g. mismatch between category and description, "
        "suspicious submitter/amounts, unusual dates, etc.). "
        "Generate a structured risk assessment containing a risk score from 1 (low) to 10 (high), "
        "a list of risk factors, and a brief explanation."
    ),
    output_schema=RiskAnalysis,
    output_key="risk_analysis",
)


@node(rerun_on_resume=True)
async def human_review(ctx: Context, node_input: Any):
    """Interrupts the workflow to wait for manual human decision."""
    expense_dict = ctx.state.get("expense")
    if not expense_dict:
        raise ValueError("Expense details not found in state context.")
    expense = ExpenseDetails(**expense_dict)

    is_security_event = ctx.state.get("is_security_event", False)
    redacted_types = ctx.state.get("redacted_types", [])

    if not ctx.resume_inputs or "human_approval" not in ctx.resume_inputs:
        message_parts = []
        if is_security_event:
            message_parts.append(
                "🚨 SECURITY WARNING: Potential prompt injection detected in the expense description!\n"
                "The LLM reviewer has been bypassed for safety. Manual review is required.\n"
            )
        else:
            message_parts.append("⚠️ ALERT: Expense report requires manual approval.\n")
            
        message_parts.append(
            f"Submitter: {expense.submitter}\n"
            f"Amount: ${expense.amount:.2f}\n"
            f"Category: {expense.category}\n"
            f"Description: {expense.description}\n"
            f"Date: {expense.date}"
        )
        
        if redacted_types:
            message_parts.append(f"\n🔐 Redacted PII categories: {', '.join(redacted_types)}")
            
        if not is_security_event:
            # If clean, node_input will be the RiskAnalysis output from llm_reviewer
            if isinstance(node_input, dict):
                risk = RiskAnalysis(**node_input)
            else:
                risk = node_input
                
            message_parts.append(
                f"\nRisk Analysis:\n"
                f"- Score: {risk.risk_score}/10\n"
                f"- Factors: {', '.join(risk.risk_factors) if risk.risk_factors else 'None'}\n"
                f"- Explanation: {risk.explanation}"
            )
            
        message_parts.append("\nPlease approve or reject this expense.")
        
        yield RequestInput(
            interrupt_id="human_approval",
            message="\n".join(message_parts),
            response_schema=HumanDecision
        )
        return

    # Process response once resumed
    decision_input = ctx.resume_inputs["human_approval"]
    if isinstance(decision_input, dict):
        decision_text = str(decision_input.get("decision", "")).strip().upper()
    else:
        decision_text = str(decision_input).strip().upper()

    if "APPROVE" in decision_text or "YES" in decision_text:
        status = "APPROVED"
        reason = "Manually approved by human reviewer."
    elif "REJECT" in decision_text or "NO" in decision_text:
        status = "REJECTED"
        reason = "Manually rejected by human reviewer."
    else:
        # Prompt again if answer is invalid
        message = f"Invalid response '{decision_text}'. Please reply with 'APPROVE' or 'REJECT'."
        yield RequestInput(
            interrupt_id="human_approval",
            message=message,
            response_schema=HumanDecision
        )
        return

    # Extract risk analysis if it was evaluated
    risk_analysis_dict = ctx.state.get("risk_analysis")
    risk_analysis = RiskAnalysis(**risk_analysis_dict) if risk_analysis_dict else None

    yield Event(
        output={
            "status": status,
            "reason": reason,
            "expense": expense,
            "risk_analysis": risk_analysis,
            "redacted_types": redacted_types,
            "is_security_event": is_security_event
        },
        state={"status": status, "reason": reason}
    )


def record_outcome(node_input: dict) -> WorkflowOutput:
    """Constructs and records the final outcome after manual approval/rejection."""
    expense_data = node_input["expense"]
    risk_data = node_input["risk_analysis"]

    if isinstance(expense_data, dict):
        expense = ExpenseDetails(**expense_data)
    else:
        expense = expense_data

    if risk_data:
        if isinstance(risk_data, dict):
            risk = RiskAnalysis(**risk_data)
        else:
            risk = risk_data
    else:
        risk = None

    return WorkflowOutput(
        amount=expense.amount,
        submitter=expense.submitter,
        category=expense.category,
        description=expense.description,
        date=expense.date,
        status=node_input["status"],
        reason=node_input["reason"],
        risk_analysis=risk,
        redacted_types=node_input["redacted_types"],
        is_security_event=node_input["is_security_event"]
    )


# --- Workflow Graph Definition ---

root_agent = Workflow(
    name="expense_approval_workflow",
    description="Workflow that handles expense reports, auto-approving under $100 and utilizing LLM & Human review for $100+",
    input_schema=None,
    state_schema=WorkflowState,
    output_schema=WorkflowOutput,
    edges=[
        ("START", parse_expense),
        (parse_expense, {"auto_approve": auto_approve, "llm_review": security_checkpoint}),
        (security_checkpoint, {"clean": llm_reviewer, "security_flagged": human_review}),
        (llm_reviewer, human_review),
        (human_review, record_outcome),
    ]
)
