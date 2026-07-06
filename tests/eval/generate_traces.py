import os
import json
import base64
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions import InMemorySessionService
from google.genai import types
from app.agent import root_agent

def make_serializable(obj):
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(x) for x in obj]
    elif isinstance(obj, bytes):
        return base64.b64encode(obj).decode("utf-8")
    return obj

def main():
    dataset_path = "tests/eval/datasets/basic-dataset.json"
    output_dir = "artifacts/traces"
    output_path = os.path.join(output_dir, "generated_traces.json")
    
    os.makedirs(output_dir, exist_ok=True)
    
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Dataset not found at {dataset_path}")
        
    with open(dataset_path) as f:
        dataset = json.load(f)
        
    eval_cases = dataset.get("eval_cases", [])
    output_cases = []
    
    print(f"Generating traces for {len(eval_cases)} cases...")
    
    for case in eval_cases:
        case_id = case["eval_case_id"]
        prompt_text = case["prompt"]["parts"][0]["text"]
        print(f"\nProcessing case: {case_id}")
        
        session_service = InMemorySessionService()
        session = session_service.create_session_sync(user_id="eval_user", app_name="app")
        runner = Runner(agent=root_agent, session_service=session_service, app_name="app")
        
        turns = []
        turn_index = 0
        
        # Turn 0: User initial query
        initial_user_event = {
            "author": "user",
            "content": {
                "role": "user",
                "parts": [{"text": prompt_text}]
            }
        }
        current_turn_events = [initial_user_event]
        
        # Run step 1
        events = list(runner.run(
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=prompt_text)]),
            user_id="eval_user",
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE)
        ))
        
        interrupted = False
        interrupt_id = None
        final_output = None
        
        for e in events:
            if e.content:
                # Check for human_approval interrupt
                for part in e.content.parts or []:
                    if part.function_call and part.function_call.name == "adk_request_input":
                        interrupted = True
                        interrupt_id = part.function_call.id
                current_turn_events.append({
                    "author": e.author or "expense_approval_workflow",
                    "content": e.content.model_dump(exclude_none=True)
                })
            if e.output:
                final_output = e.output
                
        turns.append({
            "turn_index": turn_index,
            "events": current_turn_events
        })
        turn_index += 1
        
        # Handle human review interrupt
        if interrupted:
            # Automate decision:
            # - Reject prompt injection or explicit manual_reject cases
            # - Approve clean cases
            decision = "APPROVE"
            if "prompt_injection" in case_id or "reject" in case_id:
                decision = "REJECT"
                
            print(f"  System interrupted with '{interrupt_id}'. Automating human response: {decision}")
            
            resume_message = types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            id=interrupt_id,
                            name="adk_request_input",
                            response={"decision": decision}
                        )
                    )
                ]
            )
            
            user_resume_event = {
                "author": "user",
                "content": resume_message.model_dump(exclude_none=True)
            }
            current_turn_events = [user_resume_event]
            
            events_resumed = list(runner.run(
                new_message=resume_message,
                user_id="eval_user",
                session_id=session.id,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE)
            ))
            
            for e in events_resumed:
                if e.content:
                    current_turn_events.append({
                        "author": e.author or "expense_approval_workflow",
                        "content": e.content.model_dump(exclude_none=True)
                    })
                if e.output:
                    final_output = e.output
                    
            if final_output:
                output_data = final_output
                if hasattr(final_output, "model_dump"):
                    output_data = final_output.model_dump()
                current_turn_events.append({
                    "author": "expense_approval_workflow",
                    "content": {
                        "role": "model",
                        "parts": [{"text": json.dumps(output_data)}]
                    }
                })
                
            turns.append({
                "turn_index": turn_index,
                "events": current_turn_events
            })
            
        else:
            # Auto-approved (no interrupt), append outcome to Turn 0
            if final_output:
                output_data = final_output
                if hasattr(final_output, "model_dump"):
                    output_data = final_output.model_dump()
                turns[-1]["events"].append({
                    "author": "expense_approval_workflow",
                    "content": {
                        "role": "model",
                        "parts": [{"text": json.dumps(output_data)}]
                    }
                })
                
        output_data = final_output
        if hasattr(final_output, "model_dump"):
            output_data = final_output.model_dump()
        final_output_str = json.dumps(output_data) if output_data else ""
        
        prompt_content = {
            "role": "user",
            "parts": [{"text": prompt_text}]
        }
        
        responses_content = [
            {
                "response": {
                    "role": "model",
                    "parts": [{"text": final_output_str}]
                }
            }
        ]
        
        output_cases.append({
            "eval_case_id": case_id,
            "prompt": prompt_content,
            "responses": responses_content,
            "agent_data": {
                "agents": {
                    "expense_approval_workflow": {
                        "agent_id": "expense_approval_workflow",
                        "instruction": "Workflow that handles expense reports, auto-approving under $100 and utilizing LLM & Human review for $100+"
                    }
                },
                "turns": turns
            }
        })
        
    with open(output_path, "w") as f:
        json.dump({"eval_cases": make_serializable(output_cases)}, f, indent=2)
        
    print(f"\nSaved generated traces to {output_path}")

if __name__ == "__main__":
    main()
