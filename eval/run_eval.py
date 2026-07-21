# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");

import json
import os
import sys
import datetime
import re
from typing import Dict, Any, List, Optional

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types

from expense_agent.agent import root_agent

_EVAL_SET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_set.json")
_RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def parse_novelty_score_from_report(report_text: str) -> Optional[int]:
    """Parses integer novelty score (1-10) from LLM reviewer report string.

    Returns None if no score pattern is matched (never silently defaults to a number).
    """
    if not report_text:
        return None
    match = re.search(r"Novelty Score:\s*(\d+)", report_text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def get_novelty_band(score: Optional[int]) -> str:
    """Maps 1-10 integer score to novelty band, guarding against None."""
    if score is None:
        return "UNSCORED"
    elif score >= 8:
        return "HIGH"
    elif score >= 5:
        return "MEDIUM"
    else:
        return "LOW"


def run_single_eval_case(case: Dict[str, Any], runner: Runner, session_service: InMemorySessionService) -> Dict[str, Any]:
    """Runs a single test case through the IP-Guard pipeline and returns actual output metrics."""
    session = session_service.create_session_sync(user_id="eval_user", app_name="eval_app")
    
    input_data = {
        "data": {
            "title": case.get("title", ""),
            "submitter": "Eval Submitter",
            "department": "R&D",
            "description": case.get("description", ""),
            "libraries_used": case.get("libraries_used", []),
            "date": "2026-07-09"
        }
    }
    
    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=json.dumps(input_data))]
    )
    
    events = list(
        runner.run(
            new_message=message,
            user_id="eval_user",
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
    )
    
    # Inspect output events for fast_reject or human_review interrupt
    fast_reject_output = None
    for e in events:
        if e.output is not None:
            if isinstance(e.output, dict) and e.output.get("status") == "REJECTED":
                fast_reject_output = e.output
            elif hasattr(e.output, "status") and getattr(e.output, "status") == "REJECTED":
                fast_reject_output = e.output

    is_security_event = False
    novelty_score = None
    matched_patent_id = None
    status = "UNKNOWN"
    
    if fast_reject_output:
        status = "REJECTED"
        if isinstance(fast_reject_output, dict):
            is_security_event = bool(fast_reject_output.get("is_security_event", False))
        else:
            is_security_event = bool(getattr(fast_reject_output, "is_security_event", False))
        novelty_score = 1  # Fast reject receives lowest novelty band score
    else:
        # Reached human approval interrupt
        for event in events:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call and part.function_call.name == "adk_request_input":
                        args = part.function_call.args
                        msg = str(args.get("message", "")) if isinstance(args, dict) else str(args)
                        if "SECURITY / COMPLIANCE WARNING" in msg:
                            is_security_event = True
                            status = "SECURITY_FLAGGED"
                            novelty_score = 1
                        elif "DISCREPANCY DETECTED BETWEEN RETRIEVAL TIER AND NOVELTY SCORE" in msg or "ceiling_override_needed" in msg:
                            is_security_event = False
                            status = "CEILING_ESCALATED"
                            novelty_score = None  # Explicitly no numeric guess for escalated cases
                        else:
                            is_security_event = False
                            status = "PAUSED_FOR_REVIEW"
                            novelty_score = parse_novelty_score_from_report(msg)
                            if novelty_score is None:
                                status = "PARSE_FAILURE"
                        break

    # Task 2: Extract matched_patent_id directly from actual pipeline run events/state_delta
    report_text = None
    for e in events:
        if hasattr(e, "actions") and e.actions and hasattr(e.actions, "state_delta") and e.actions.state_delta:
            if "innovation_analysis" in e.actions.state_delta:
                report_text = e.actions.state_delta["innovation_analysis"]
                break
                
    if report_text:
        m = re.search(r"Patent\s+(US[0-9A-Z]+)", report_text)
        if m:
            matched_patent_id = m.group(1)

    actual_novelty_band = get_novelty_band(novelty_score)
    
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "status": status,
        "novelty_score": novelty_score,
        "actual_novelty_band": actual_novelty_band,
        "matched_patent_id": matched_patent_id,
        "is_security_event": is_security_event
    }


def evaluate_all_cases() -> Dict[str, Any]:
    """Executes the full evaluation harness against all eval cases."""
    if not os.path.exists(_EVAL_SET_PATH):
        raise FileNotFoundError(f"Evaluation set missing at {_EVAL_SET_PATH}")
        
    with open(_EVAL_SET_PATH, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)
        
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, session_service=session_service, app_name="eval_app")
    
    results = []
    
    auto_answered_novelty_count = 0
    correct_novelty_count = 0
    correct_conflict_count = 0
    correct_security_count = 0
    total_escalated_count = 0
    total_parse_failure_count = 0
    
    category_stats = {}
    
    for case in eval_cases:
        actual = run_single_eval_case(case, runner, session_service)
        gt = case["ground_truth"]
        cat = case["category"]
        
        if cat not in category_stats:
            category_stats[cat] = {
                "total": 0,
                "auto_answered": 0,
                "novelty_correct": 0,
                "escalated": 0,
                "parse_failures": 0,
                "conflict_correct": 0,
                "security_correct": 0
            }
            
        category_stats[cat]["total"] += 1
        
        # Dimension 1: Novelty band match (computed ONLY on auto-answered numeric scores)
        status = actual["status"]
        novelty_match = None
        if status == "CEILING_ESCALATED":
            total_escalated_count += 1
            category_stats[cat]["escalated"] += 1
        elif status == "PARSE_FAILURE":
            total_parse_failure_count += 1
            category_stats[cat]["parse_failures"] += 1
        elif actual["novelty_score"] is not None:
            auto_answered_novelty_count += 1
            category_stats[cat]["auto_answered"] += 1
            novelty_match = (actual["actual_novelty_band"] == gt["expected_novelty_band"])
            if novelty_match:
                correct_novelty_count += 1
                category_stats[cat]["novelty_correct"] += 1
            
        # Dimension 2: Conflict identification match (from real tool call events)
        expected_conflict = gt["expected_conflict_patent_id"]
        actual_conflict = actual["matched_patent_id"]
        conflict_match = (actual_conflict == expected_conflict)
        if conflict_match:
            correct_conflict_count += 1
            category_stats[cat]["conflict_correct"] += 1
            
        # Dimension 3: Security event match
        security_match = (actual["is_security_event"] == gt["expected_security_event"])
        if security_match:
            correct_security_count += 1
            category_stats[cat]["security_correct"] += 1
            
        results.append({
            "case_id": case["case_id"],
            "title": case["title"],
            "category": cat,
            "ground_truth": gt,
            "actual": actual,
            "scores": {
                "novelty_match": novelty_match,
                "conflict_match": conflict_match,
                "security_match": security_match
            }
        })

    total_cases = len(eval_cases)
    novelty_acc = round((correct_novelty_count / auto_answered_novelty_count) * 100, 1) if auto_answered_novelty_count > 0 else 0.0
    escalation_rate = round((total_escalated_count / total_cases) * 100, 1)
    
    metrics = {
        "timestamp": datetime.datetime.now().isoformat(),
        "total_cases": total_cases,
        "auto_answered_cases": auto_answered_novelty_count,
        "escalated_cases": total_escalated_count,
        "parse_failure_count": total_parse_failure_count,
        "escalation_rate_percent": escalation_rate,
        "overall_accuracy": {
            "novelty_band_accuracy": novelty_acc,
            "conflict_id_accuracy": round((correct_conflict_count / total_cases) * 100, 1),
            "security_detection_accuracy": round((correct_security_count / total_cases) * 100, 1)
        },
        "category_breakdown": {
            cat: {
                "total": stats["total"],
                "auto_answered": stats["auto_answered"],
                "novelty_correct": stats["novelty_correct"],
                "escalated": stats["escalated"],
                "parse_failures": stats["parse_failures"],
                "novelty_acc": round((stats["novelty_correct"] / stats["auto_answered"]) * 100, 1) if stats["auto_answered"] > 0 else 0.0,
                "conflict_acc": round((stats["conflict_correct"] / stats["total"]) * 100, 1),
                "security_acc": round((stats["security_correct"] / stats["total"]) * 100, 1)
            }
            for cat, stats in category_stats.items()
        },
        "case_details": results
    }
    
    # Save detailed JSON results
    os.makedirs(_RESULTS_DIR, exist_ok=True)
    filename = f"eval_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    result_path = os.path.join(_RESULTS_DIR, filename)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    # Print summary table
    print("=" * 95)
    print("IP-GUARD EVALUATION HARNESS REPORT (BUG-FREE Measurement)")
    print("=" * 95)
    print(f"Timestamp: {metrics['timestamp']} | Total Cases: {total_cases}")
    print(f"Auto-Answered Cases: {auto_answered_novelty_count} | Escalated: {total_escalated_count} ({escalation_rate}%) | Parse Failures: {total_parse_failure_count}")
    print(f"Saved Full Detail To: {result_path}\n")
    
    if total_parse_failure_count > 0:
        print(f"⚠️ WARNING: {total_parse_failure_count} parse failures detected! Inspect report regex patterns.")
        
    print("--- OVERALL ACCURACY METRICS ---")
    print(f"1. Novelty Band Accuracy (Auto-Answered): {metrics['overall_accuracy']['novelty_band_accuracy']}%")
    print(f"2. Escalation Rate                       : {escalation_rate}%")
    print(f"3. Conflict ID Accuracy (Event Sourced)  : {metrics['overall_accuracy']['conflict_id_accuracy']}%")
    print(f"4. Security Detection Acc.               : {metrics['overall_accuracy']['security_detection_accuracy']}%")
    
    print("\n--- CATEGORY BREAKDOWN ---")
    print(f"{'Category':<20} | {'Total':<5} | {'AutoAns':<7} | {'Correct':<7} | {'Escalated':<9} | {'ParseFail':<9} | {'NoveltyAcc':<10} | {'ConflictAcc':<11}")
    print("-" * 95)
    for cat, stat in metrics["category_breakdown"].items():
        print(f"{cat:<20} | {stat['total']:<5} | {stat['auto_answered']:<7} | {stat['novelty_correct']:<7} | {stat['escalated']:<9} | {stat['parse_failures']:<9} | {stat['novelty_acc']:<9}% | {stat['conflict_acc']:<10}%")
    print("=" * 95)
    
    return metrics


if __name__ == "__main__":
    evaluate_all_cases()
