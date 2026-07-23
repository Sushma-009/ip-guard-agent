import os
import dotenv
from google.genai import Client, types
from google.adk.agents import LlmAgent
from google.adk.models import Gemini

from .config import Config

dotenv.load_dotenv()

# LlmAgent instance for configuration checks and anti-mock regression guards
conflict_arbiter_agent = LlmAgent(
    name="conflict_arbiter",
    model=Gemini(model=Config.MODEL),
    instruction=(
        "You are a conflict arbiter. Given a submission description, a candidate patent "
        "abstract, and the reviewer's reasoning, decide if a specific, non-trivial technical "
        "differentiator exists to justify upgrading the novelty band from LOW to MEDIUM. "
        "Identify and state the final band explicitly: final_band: LOW or final_band: MEDIUM."
    )
)

def arbitrate(submission_description: str, matched_patent: dict, llm_reviewer_reasoning: str) -> dict:
    """Arbitrates whether a verified prior art conflict contains a significant differentiator to justify a MEDIUM novelty score.

    Strict no-silent-default policy: returns status = 'PARSE_FAILURE' if output format is unexpected.
    """
    client = Client()
    prompt = (
        f"Submission Description: {submission_description}\n\n"
        f"Matched Patent Abstract: {matched_patent.get('abstract_snippet', matched_patent.get('abstract', ''))}\n\n"
        f"Reviewer Reasoning:\n{llm_reviewer_reasoning}\n\n"
        "Instructions:\n"
        "This submission has a verified strong match to an existing patent. "
        "First, argue why it should still be scored LOW (the default). "
        "Second, argue whether there is a specific, non-trivial technical differentiator "
        "that would justify a MEDIUM score instead. "
        "A non-trivial technical differentiator is a structural or security paradigm addition "
        "from a different technical domain (e.g. combining searchable symmetric encryption with "
        "homomorphic multi-party threshold key custody across independent vault nodes) that fundamentally "
        "changes the architecture or security model. "
        "Do NOT accept minor implementation details (e.g. choice of programming library, adding encryption "
        "or standard oxygenation levels to an otherwise identical mechanism) as sufficient. "
        "State your final verdict explicitly at the end as either 'final_band: LOW' or 'final_band: MEDIUM'."
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
                print(f"ConflictArbiter: 429 Rate limit hit. Retrying in {backoff} seconds...")
                time.sleep(backoff)
            else:
                raise e
                
    if not res:
        raise RuntimeError("ConflictArbiter: API calls exhausted due to rate limits.")
        
    text = res.text or ""
    
    final_band = None
    status = "PARSE_FAILURE"
    differentiator = None
    
    if "final_band: LOW" in text:
        final_band = "LOW"
        status = "SUCCESS"
    elif "final_band: MEDIUM" in text:
        final_band = "MEDIUM"
        status = "SUCCESS"
        # Attempt simple differentiator extraction from text
        import re
        m = re.search(r"(?:differentiator|differentiating factor)[:\s]+([^\n\.]+)", text, re.IGNORECASE)
        if m:
            differentiator = m.group(1).strip()
            
    return {
        "final_band": final_band,
        "status": status,
        "differentiator": differentiator,
        "reasoning": text.strip()
    }
