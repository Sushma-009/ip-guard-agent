import asyncio
import os
import json

# Setup env variables
os.environ["INTEGRATION_TEST"] = "TRUE"

from app.agent_runtime_app import agent_runtime

async def run_case(amount, description):
    print(f"\n==================================================")
    print(f"TEST CASE: ${amount} - {description}")
    print(f"==================================================")
    
    # We re-initialize or reuse session
    message = json.dumps({
        "data": {
            "amount": amount,
            "submitter": "Test Employee",
            "category": "Meals",
            "description": description,
            "date": "2026-07-06"
        }
    })
    
    events = []
    async for event in agent_runtime.async_stream_query(message=message, user_id="test_user"):
        events.append(event)
        # Check if it yields a RequestInput (human review prompt)
        actions = event.get("actions", {})
        if "requested_auth_configs" in event or "requested_tool_confirmations" in event or any("human_approval" in str(k) for k in actions.get("requested_tool_confirmations", {})) or "interrupt_id" in str(event):
            print(">>> HUMAN-IN-THE-LOOP PAUSE DETECTED! <<<")
            
        # Or look for RequestInput in action payload
        if "human_approval" in str(event):
            print(">>> REQUESTINPUT DETECTED! <<<")
            print(f"Prompt Message:\n{event}")
            
    print("\nFINAL OUTPUT RECEIVED:")
    for event in events:
        if event.get("output"):
            print(json.dumps(event.get("output"), indent=2))

async def main():
    agent_runtime.set_up()
    
    # Test Case 1: $50 auto-approval
    await run_case(50.00, "Lunch with potential hire")
    
    # Test Case 2: $150 human-in-the-loop escalation
    await run_case(150.00, "Dinner with key client")

asyncio.run(main())
