import os
import dotenv
from google.genai import Client, types
from google.adk.agents import LlmAgent
from google.adk.models import Gemini

dotenv.load_dotenv()

from .config import Config

# LlmAgent instance for configuration checks and anti-mock regression guards
match_verifier_agent = LlmAgent(
    name="match_verifier",
    model=Gemini(model=Config.MODEL),
    instruction=(
        "You are a prior art match verifier. Given a submission details "
        "and a candidate patent's title and abstract, classify the match as "
        "SPURIOUS_MATCH, VERIFIED_CONFLICT, or VERIFIED_CONFLICT_WITH_DIFFERENTIATOR. "
        "Answer with the exact tag and explain in one sentence."
    )
)

def verify_match(submission_description: str, submission_title: str, matched_patent: dict) -> dict:
    """Verifies if the retrieved prior art match is structurally real, spurious, or real but differentiated.

    Strict no-silent-default policy: returns status = 'PARSE_FAILURE' if output format is unexpected.
    """
    client = Client()
    prompt = (
        f"Submission Title: {submission_title}\n"
        f"Submission Description: {submission_description}\n\n"
        f"Candidate Patent ID: {matched_patent.get('patent_id')}\n"
        f"Candidate Patent Title: {matched_patent.get('title')}\n"
        f"Candidate Patent Abstract: {matched_patent.get('abstract_snippet', matched_patent.get('abstract', ''))}\n\n"
        "Instructions:\n"
        "1. Intermediate Reasoning Step:\n"
        "Before classifying, identify the concrete implementation category of both the submission and the candidate patent (e.g., physical hardware device, software protocol, algorithmic method, chemical process, biological system). State both categories explicitly.\n\n"
        "2. Classify the technical relationship between the submission and the candidate patent into exactly one of three categories:\n"
        "- SPURIOUS_MATCH: The submission and candidate patent share only surface-level vocabulary (lexical overlaps) or general high-level domain concepts (e.g., both are generally 'quantum' or 'hydroponic' or 'database' related), but their concrete technical mechanisms and structural architectures are completely different (e.g., a hardware optoelectronic device vs. a software protocol, or a microbial fuel cell vs. fluid dosing loops). If the core engineering mechanisms do not overlap, it is a SPURIOUS_MATCH.\n"
        "  - Hard Rule: If the submission and candidate patent belong to different implementation categories (e.g., one is a physical hardware apparatus and the other is a software protocol or algorithm), this is strong evidence for SPURIOUS_MATCH even if they operate in the same domain and share technical vocabulary — a hardware device and a software protocol cannot share a 'core mechanism' in the sense required for VERIFIED_CONFLICT or VERIFIED_CONFLICT_WITH_DIFFERENTIATOR, regardless of vocabulary overlap.\n"
        "- VERIFIED_CONFLICT: The submission and candidate patent share the same core technical mechanism/architecture with no meaningful technical differentiation.\n"
        "- VERIFIED_CONFLICT_WITH_DIFFERENTIATOR: The submission and candidate patent share a real, substantive technical relationship (they use the same underlying concrete class of technique/mechanism for the same technical problem), but the submission introduces a specific, non-trivial technical difference or structural differentiator (e.g., adding homomorphic multi-party threshold key custody to a database columns search mechanism, or utilizing validity ZK-proofs instead of optimistic fraud-proof rollups for compression).\n"
        "  - Differentiator Category Boundary: VERIFIED_CONFLICT_WITH_DIFFERENTIATOR requires both items to share the same implementation category AND the same core technique within that category, with only a specific structural or capability-level difference (e.g., two software protocols differing in cryptographic primitive; two hardware devices differing in a specific added subsystem). Do not use this category to connect items from different implementation categories.\n\n"
        "Format your response exactly as follows:\n"
        "Reasoning:\n"
        "- Submission implementation category: <category>\n"
        "- Candidate Patent implementation category: <category>\n"
        "- Analysis: <short analysis>\n\n"
        "Classification: [SPURIOUS_MATCH, VERIFIED_CONFLICT, or VERIFIED_CONFLICT_WITH_DIFFERENTIATOR], followed by explanation in one sentence."
    )
    
    import time
    res = None
    for attempt in range(4):
        try:
            res = client.models.generate_content(
                model=Config.MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0)
            )
            break
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                backoff = 2 ** attempt + 2
                print(f"MatchVerifier: 429 Rate limit hit. Retrying in {backoff} seconds...")
                time.sleep(backoff)
            else:
                raise e
                
    if not res:
        raise RuntimeError("MatchVerifier: API calls exhausted due to rate limits.")
        
    text = res.text or ""
    
    is_verified = None
    category = None
    status = "PARSE_FAILURE"
    
    if "VERIFIED_CONFLICT_WITH_DIFFERENTIATOR" in text:
        is_verified = True
        status = "SUCCESS"
        category = "VERIFIED_CONFLICT_WITH_DIFFERENTIATOR"
    elif "VERIFIED_CONFLICT" in text:
        is_verified = True
        status = "SUCCESS"
        category = "VERIFIED_CONFLICT"
    elif "SPURIOUS_MATCH" in text:
        is_verified = False
        status = "SUCCESS"
        category = "SPURIOUS_MATCH"
        
    return {
        "is_verified": is_verified,
        "status": status,
        "category": category,
        "reasoning": text.strip()
    }
