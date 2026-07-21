import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from expense_agent.agent import root_agent

with open("eval/eval_set.json", "r", encoding="utf-8") as f:
    eval_cases = json.load(f)

target_cases = ["eval_013", "eval_015", "eval_016"]
s_svc = InMemorySessionService()
runner = Runner(agent=root_agent, session_service=s_svc, app_name="eval_app")

for case_id in target_cases:
    case = next(c for c in eval_cases if c["case_id"] == case_id)
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
    
    raw_msg = "NO_INTERRUPT_MESSAGE_FOUND"
    for event in events:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call and part.function_call.name == "adk_request_input":
                    args = part.function_call.args
                    raw_msg = str(args.get("message", "")) if isinstance(args, dict) else str(args)
                    break
                    
    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{case_id}_raw_message.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(raw_msg)
    print(f"Wrote raw message for {case_id} to {out_file}")
