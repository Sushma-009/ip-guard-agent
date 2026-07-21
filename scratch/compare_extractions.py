import json
import re
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from expense_agent.agent import root_agent
from expense_agent.vector_store import search_prior_art_vectors

with open("eval/eval_set.json", "r", encoding="utf-8") as f:
    eval_cases = json.load(f)

s_svc = InMemorySessionService()
runner = Runner(agent=root_agent, session_service=s_svc, app_name="eval_app")

print(f"=== TASK 2 DUAL EXTRACTION COMPARISON (n={len(eval_cases)}) ===")
print(f"{'CASE_ID':<10} | {'OLD_MATCH_ID':<15} | {'NEW_MATCH_ID':<15} | {'STATUS'}")
print("-" * 55)

divergence_count = 0

for case in eval_cases:
    session = s_svc.create_session_sync(user_id="eval_user", app_name="eval_app")
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
    message = types.Content(role="user", parts=[types.Part.from_text(text=json.dumps(input_data))])
    
    events = list(runner.run(new_message=message, user_id="eval_user", session_id=session.id, run_config=RunConfig(streaming_mode=StreamingMode.SSE)))
    
    # 1. Old method (parallel RAG search)
    rag_result = search_prior_art_vectors(case.get("description", ""), top_k=3)
    old_matched_id = None
    if rag_result.get("matches"):
        top_m = rag_result["matches"][0]
        if top_m.get("similarity_tier") in ["HIGH_CONFLICT", "MODERATE_OVERLAP"]:
            old_matched_id = top_m["patent_id"]
            
    # 2. New method (extracted from actual run events / state_delta / report)
    new_matched_id = None
    report_text = None
    for e in events:
        if hasattr(e, "actions") and e.actions and hasattr(e.actions, "state_delta") and e.actions.state_delta:
            if "innovation_analysis" in e.actions.state_delta:
                report_text = e.actions.state_delta["innovation_analysis"]
                break
    
    if report_text:
        m = re.search(r"Patent\s+(US[0-9A-Z]+)", report_text)
        if m:
            new_matched_id = m.group(1)
            
    match_status = "MATCH" if old_matched_id == new_matched_id else "DIVERGE"
    if old_matched_id != new_matched_id:
        divergence_count += 1
        
    print(f"{case['case_id']:<10} | {str(old_matched_id):<15} | {str(new_matched_id):<15} | {match_status}")

print("-" * 55)
print(f"Total Divergences: {divergence_count}")
