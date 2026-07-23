import pytest
from unittest.mock import patch, MagicMock
from expense_agent.query_auditor import audit_query
from expense_agent.match_verifier import verify_match, match_verifier_agent
from expense_agent.conflict_arbiter import arbitrate, conflict_arbiter_agent
from expense_agent.vector_store import search_prior_art_vectors

def test_query_auditor_catches_known_drift_case():
    original_desc = (
        "A secondary transaction aggregator compressing off-chain state updates "
        "into zero-knowledge validity proofs prior to committing state roots "
        "onto a primary layer-1 public blockchain ledger."
    )
    drifted_query = (
        "Layer-2 Rollup Batch State Compression Engine zero-knowledge validity "
        "proofs state roots layer-1 blockchain"
    )
    
    res = audit_query(original_desc, drifted_query)
    assert res["is_drifted"] is True
    assert "Query drift detected" in res["reason"]
    
    corrected = res["corrected_query"]
    search_res = search_prior_art_vectors(corrected, top_k=3)
    assert search_res["status"] == "MATCH_FOUND"
    assert search_res["matches"][0]["patent_id"] == "US9123460B2"

def test_query_auditor_ignores_faithful_query():
    original_desc = (
        "A secondary transaction aggregator compressing off-chain state updates "
        "into zero-knowledge validity proofs prior to committing state roots "
        "onto a primary layer-1 public blockchain ledger."
    )
    faithful_query = (
        "transaction aggregator compressing state updates zero-knowledge validity "
        "proofs state roots layer-1 public blockchain ledger"
    )
    
    res = audit_query(original_desc, faithful_query)
    assert res["is_drifted"] is False
    assert res["corrected_query"] == faithful_query

def test_match_verifier_rejects_eval_001_spurious_match():
    # eval_001 GHz electro-optic hardware vs decoy state software protocol US11234569B2
    submission_title = "Quantum Photonic Entanglement Frequency Modulator"
    submission_desc = (
        "An electro-optic device that modulates the phase frequency of entangled "
        "photon pairs at gigahertz clock speeds to accelerate ultra-secure quantum communications."
    )
    matched_patent = {
        "patent_id": "US11234569B2",
        "title": "Quantum Key Distribution Protocol with Decoy State Modulation",
        "abstract_snippet": "A software QKD protocol modulating decoy states to prevent splitting attacks."
    }
    
    res = verify_match(submission_desc, submission_title, matched_patent)
    assert res["is_verified"] is False
    assert res["status"] == "SUCCESS"
    assert "SPURIOUS_MATCH" in res["reasoning"]

def test_match_verifier_rejects_cross_category_vocabulary_overlap():
    # Technical test asserting that hardware vs software is rejected as SPURIOUS_MATCH
    submission_title = "Quantum Photonic Entanglement Frequency Modulator"
    submission_desc = (
        "An electro-optic device that modulates the phase frequency of entangled "
        "photon pairs at gigahertz clock speeds to accelerate ultra-secure quantum communications."
    )
    matched_patent = {
        "patent_id": "US11234569B2",
        "title": "Quantum Key Distribution Protocol with Decoy State Modulation",
        "abstract_snippet": "A software QKD protocol modulating decoy states to prevent splitting attacks."
    }
    
    res = verify_match(submission_desc, submission_title, matched_patent)
    assert res["is_verified"] is False
    assert res["status"] == "SUCCESS"
    assert "SPURIOUS_MATCH" in res["reasoning"]

def test_match_verifier_accepts_genuine_conflict():
    # eval_007 Distributed Ledger Secondary Arbiter vs US9123456B2 supervisor consensus
    submission_title = "Distributed Ledger Secondary Arbiter Consensus Protocol"
    submission_desc = (
        "A secondary consensus validation system featuring supervisor nodes to resolve "
        "transaction partition lockouts in high-throughput ledgers."
    )
    matched_patent = {
        "patent_id": "US9123456B2",
        "title": "Distributed Ledger Supervisor Consensus Protocol",
        "abstract_snippet": "Methods for resolving transaction lockouts by designating supervisor validator nodes."
    }
    
    res = verify_match(submission_desc, submission_title, matched_patent)
    assert res["is_verified"] is True
    assert res["status"] == "SUCCESS"
    assert "VERIFIED_CONFLICT" in res["reasoning"]

def test_conflict_arbiter_confirms_eval_021_medium():
    # eval_021: SSE + homomorphic threshold custody. Matched to US9876548B2
    submission_desc = (
        "A database proxy engine executing searchable symmetric encryption substring "
        "queries over ciphertext columns combined with homomorphic multi-party threshold "
        "key custody across independent vault nodes."
    )
    matched_patent = {
        "patent_id": "US9876548B2",
        "title": "Searchable Symmetric Encryption for Multi-Tenant Database Columns",
        "abstract_snippet": "Symmetric encryption scheme allowing SQL substring queries against database columns."
    }
    reviewer_reasoning = "The novelty is low because it utilizes searchable symmetric encryption to query secure columns."
    
    res = arbitrate(submission_desc, matched_patent, reviewer_reasoning)
    assert res["final_band"] == "MEDIUM"
    assert res["status"] == "SUCCESS"

def test_conflict_arbiter_rejects_eval_016_style_weak_differentiator():
    # Closed-loop hydroponics with oxygenation. Matched to US7654324B2
    submission_desc = (
        "An automated agricultural dosing apparatus monitoring electrical conductivity "
        "to balance macro-nutrients and oxygenation levels in commercial crop beds."
    )
    matched_patent = {
        "patent_id": "US7654324B2",
        "title": "Closed-Loop Hydroponic Nutrient Dosing and Salinity Monitoring",
        "abstract_snippet": "Automated water recirculating system measuring EC and pH to inject micro-nutrient solutions."
    }
    reviewer_reasoning = "Novelty is low because the automated closed-loop EC dosing matches the prior art."
    
    res = arbitrate(submission_desc, matched_patent, reviewer_reasoning)
    assert res["final_band"] == "LOW"
    assert res["status"] == "SUCCESS"

def test_match_verifier_parse_failure_escalates():
    submission_title = "Test title"
    submission_desc = "Test description"
    matched_patent = {
        "patent_id": "US123",
        "title": "Test patent",
        "abstract_snippet": "Test abstract"
    }
    
    # Mock model response with junk output
    mock_res = MagicMock()
    mock_res.text = "This is a random non-compliant LLM answer."
    
    with patch("google.genai.models.Models.generate_content", return_value=mock_res):
        res = verify_match(submission_desc, submission_title, matched_patent)
        assert res["is_verified"] is None
        assert res["status"] == "PARSE_FAILURE"

def test_conflict_arbiter_parse_failure_escalates():
    submission_desc = "Test description"
    matched_patent = {
        "patent_id": "US123",
        "title": "Test patent",
        "abstract_snippet": "Test abstract"
    }
    reviewer_reasoning = "Novelty is low."
    
    # Mock model response with junk output
    mock_res = MagicMock()
    mock_res.text = "This is a random non-compliant LLM answer."
    
    with patch("google.genai.models.Models.generate_content", return_value=mock_res):
        res = arbitrate(submission_desc, matched_patent, reviewer_reasoning)
        assert res["final_band"] is None
        assert res["status"] == "PARSE_FAILURE"

def test_match_verifier_has_no_mock_callback():
    assert match_verifier_agent.before_model_callback is None

def test_conflict_arbiter_has_no_mock_callback():
    assert conflict_arbiter_agent.before_model_callback is None

def test_match_verifier_real_model_smoke():
    # Make a fast check to verify real non-mocked response
    matched_patent = {
        "patent_id": "US123",
        "title": "Test patent",
        "abstract_snippet": "Test abstract"
    }
    res = verify_match("Test", "Test", matched_patent)
    # Asserting response isn't empty and contains reasoning text
    assert len(res["reasoning"]) > 5
    assert res["status"] in ("SUCCESS", "PARSE_FAILURE")

def test_conflict_arbiter_real_model_smoke():
    matched_patent = {
        "patent_id": "US123",
        "title": "Test patent",
        "abstract_snippet": "Test abstract"
    }
    res = arbitrate("Test", matched_patent, "Novelty is low.")
    assert len(res["reasoning"]) > 5
    assert res["status"] in ("SUCCESS", "PARSE_FAILURE")

def test_match_verifier_preserves_eval_021_for_arbitration():
    submission_title = "Searchable Symmetric Encryption with Homomorphic Key Custody"
    submission_desc = (
        "A database proxy engine executing searchable symmetric encryption substring "
        "queries over ciphertext columns combined with homomorphic multi-party threshold "
        "key custody across independent vault nodes."
    )
    matched_patent = {
        "patent_id": "US9876548B2",
        "title": "Searchable Symmetric Encryption for Multi-Tenant Database Columns",
        "abstract_snippet": "Symmetric encryption scheme allowing SQL substring queries against database columns."
    }
    res = verify_match(submission_desc, submission_title, matched_patent)
    assert res["category"] == "VERIFIED_CONFLICT_WITH_DIFFERENTIATOR"
    assert res["is_verified"] is True
    assert res["status"] == "SUCCESS"

def test_match_verifier_preserves_eval_013_for_arbitration():
    submission_title = "Layer-2 Rollup Batch State Compression Engine"
    submission_desc = (
        "A secondary transaction aggregator compressing off-chain state updates "
        "into zero-knowledge validity proofs prior to committing state roots "
        "onto a primary layer-1 public blockchain ledger."
    )
    matched_patent = {
        "patent_id": "US9123460B2",
        "title": "Optimistic Rollup State Validation Protocol",
        "abstract_snippet": "A fraud-proof validation system utilizing challenge periods to verify state transitions in optimistic rollups."
    }
    res = verify_match(submission_desc, submission_title, matched_patent)
    assert res["category"] == "VERIFIED_CONFLICT_WITH_DIFFERENTIATOR"
    assert res["is_verified"] is True
    assert res["status"] == "SUCCESS"

def test_conflict_arbiter_actually_invoked_for_eval_021():
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.agents.run_config import RunConfig, StreamingMode
    from google.genai import types
    from app.agent import root_agent
    import json
    from unittest.mock import patch, MagicMock
    
    # Mock responses in sequence
    mock_verifier_res = MagicMock()
    mock_verifier_res.text = "VERIFIED_CONFLICT_WITH_DIFFERENTIATOR: same class of technique, but with threshold custody."
    
    mock_reviewer_res = MagicMock()
    mock_reviewer_res.text = "### Technical Evaluation\n\n#### 1. Novelty Assessment\nNovelty Score: 9/10\n\n#### 3. Prior Art Check Results\n- US9876548B2 (HIGH_CONFLICT)"
    
    mock_arbiter_res = MagicMock()
    mock_arbiter_res.text = "final_band: MEDIUM\nBecause threshold custody is a non-trivial differentiator."
    
    calls = [mock_verifier_res, mock_arbiter_res]
    call_idx = 0
    
    def generate_content_side_effect(*args, **kwargs):
        nonlocal call_idx
        res = calls[call_idx]
        call_idx += 1
        return res
    
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="test_user", app_name="test")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    input_data = {
        "data": {
            "title": "Searchable Symmetric Encryption with Homomorphic Key Custody",
            "submitter": "Alice",
            "department": "R&D",
            "description": "A database proxy engine executing searchable symmetric encryption substring queries over ciphertext columns combined with homomorphic multi-party threshold key custody across independent vault nodes.",
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
    with patch("google.genai.models.Models.generate_content", side_effect=generate_content_side_effect), \
         patch("expense_agent.agent.search_prior_art_vectors", return_value=mock_search):
        events = list(
            runner.run(
                new_message=message,
                user_id="test_user",
                session_id=session.id,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            )
        )
    
    # Verify that conflict_arbiter was called and output was stored in state
    sess = session_service.get_session_sync(app_name="test", user_id="test_user", session_id=session.id)
    arbiter_audit = sess.state.get("arbiter_audit")
    assert arbiter_audit is not None, "ConflictArbiter was not invoked for eval_021"
    assert arbiter_audit.get("status") == "SUCCESS"
    assert arbiter_audit.get("final_band") == "MEDIUM"
