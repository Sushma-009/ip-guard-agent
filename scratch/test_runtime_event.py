import asyncio
import os
import json

# Setup env variables
os.environ["INTEGRATION_TEST"] = "TRUE"

from app.agent_runtime_app import agent_runtime

async def main():
    agent_runtime.set_up()
    message = '{"data": {"amount": 45.50, "submitter": "Alice", "category": "Meals", "description": "Client lunch with partners", "date": "2026-07-01"}}'
    print("SENDING MESSAGE...")
    async for event in agent_runtime.async_stream_query(message=message, user_id="test"):
        print("EVENT:", event)
        print("TYPE:", type(event))

asyncio.run(main())
