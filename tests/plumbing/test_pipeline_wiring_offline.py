import pytest
from unittest.mock import patch, MagicMock
import json
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from app.agent import root_agent

@pytest.fixture(autouse=True)
def mock_api_client_generic():
    class MockResponseDict(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.headers = {}
            
    class MockSyncResponse:
        def __init__(self, text):
            self.headers = {}
            self.response_stream = [text]
            
    def get_generic_mock_text(prompt_str: str) -> str:
        # MatchVerifier prompts
        if "Classify the technical relationship" in prompt_str:
            return "VERIFIED_CONFLICT_WITH_DIFFERENTIATOR: mock verifier placeholder"
                
        # ConflictArbiter prompts
        elif "This submission has a verified strong match" in prompt_str:
            return "final_band: MEDIUM\nmock arbiter placeholder"
                
        # Reviewer prompts
        else:
            return "### Technical Evaluation\n\n#### 1. Novelty Assessment\nNovelty Score: 7/10\n\n#### 3. Prior Art Check Results\n- US9876548B2 (HIGH_CONFLICT)"

    async def mock_async_request(*args, **kwargs):
        req = args[1] if len(args) > 1 else kwargs.get("http_request")
        json_data = req.data if req else {}
        sys_instruction = str(json_data.get("systemInstruction", ""))
        contents = str(json_data.get("contents", []))
        prompt_str = sys_instruction + "\n" + contents
        
        is_tool_turn = "functionResponse" in contents
        
        if not ("Classify the technical relationship" in prompt_str or "This submission has a verified strong match" in prompt_str):
            if not is_tool_turn:
                # Reviewer first turn: call tool check_prior_art
                mock_data = {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "functionCall": {
                                            "name": "check_prior_art",
                                            "args": {
                                                "query": "check_prior_art_query"
                                            }
                                        }
                                    }
                                ]
                            },
                            "role": "model"
                        }
                    ]
                }
            else:
                text_content = get_generic_mock_text(prompt_str)
                mock_data = {
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": text_content}],
                                "role": "model"
                            },
                            "finishReason": "STOP"
                        }
                    ]
                }
        else:
            text_content = get_generic_mock_text(prompt_str)
            mock_data = {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": text_content}],
                            "role": "model"
                        },
                        "finishReason": "STOP"
                    }
                ]
            }
            
        class MockStream:
            def __init__(self, data):
                self.data = MockResponseDict(data)
                self.headers = {}
                self.read_done = False
            def __aiter__(self):
                return self
            async def __anext__(self):
                if self.read_done:
                    raise StopAsyncIteration
                self.read_done = True
                return self.data
                
        return MockStream(mock_data)

    def mock_request(*args, **kwargs):
        req = args[1] if len(args) > 1 else kwargs.get("http_request")
        json_data = req.data if req else {}
        sys_instruction = str(json_data.get("systemInstruction", ""))
        contents = str(json_data.get("contents", []))
        prompt_str = sys_instruction + "\n" + contents
        
        text_content = get_generic_mock_text(prompt_str)
        mock_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": text_content}],
                        "role": "model"
                    },
                    "finishReason": "STOP"
                }
            ]
        }
        return MockSyncResponse(text=json.dumps(mock_data))

    with patch("google.genai._api_client.BaseApiClient._async_request", new=mock_async_request), \
         patch("google.genai._api_client.BaseApiClient._request", new=mock_request):
        yield

def test_pipeline_wiring_runs_offline():
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="test_user", app_name="test")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    input_data = {
        "data": {
            "title": "Generic Submission Title",
            "submitter": "Alice",
            "department": "R&D",
            "description": "This is a generic description to test pipeline wiring and function calling.",
            "libraries_used": ["numpy"],
            "date": "2026-07-09"
        }
    }
    message = types.Content(
        role="user", parts=[types.Part.from_text(text=json.dumps(input_data))]
    )

    mock_search = {
        "status": "MATCH_FOUND",
        "matches": [
            {
                "patent_id": "US9876548B2",
                "title": "Searchable Symmetric Encryption for Multi-Tenant Database Columns",
                "domain_tag": "cryptography",
                "raw_similarity_score": 0.605,
                "similarity_tier": "HIGH_CONFLICT",
                "abstract_snippet": "Symmetric encryption scheme allowing SQL substring queries against database columns."
            }
        ]
    }

    with patch("expense_agent.agent.search_prior_art_vectors", return_value=mock_search):
        events = list(
            runner.run(
                new_message=message,
                user_id="test_user",
                session_id=session.id,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            )
        )
    
    sess = session_service.get_session_sync(app_name="test", user_id="test_user", session_id=session.id)
    assert sess.state.get("verifier_audit") is not None
    assert sess.state.get("arbiter_audit") is not None
    assert "mock verifier placeholder" in str(sess.state["verifier_audit"])
    assert "mock arbiter placeholder" in str(sess.state["arbiter_audit"])
