import re

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "from", "to", "for", "with", "by", "of", "and", "or",
    "but", "not", "this", "that", "these", "those", "into", "onto", "prior",
    "after", "before", "without", "about", "against", "through", "during",
    "under", "over", "such", "than", "then", "there", "their", "them", "they",
    "it", "its", "itself", "whose", "which", "whom", "who", "what", "where",
    "when", "why", "how", "all", "any", "both", "each", "few", "more", "most",
    "other", "some", "only", "own", "same", "so", "than", "too", "very", "can",
    "will", "just", "should", "would"
}

def clean_words(text: str) -> list[str]:
    # Convert to lowercase and replace non-alphanumeric (except hyphen) with spaces
    normalized = text.lower()
    normalized = re.sub(r"[^a-z0-9\s-]", " ", normalized)
    return [w.strip() for w in normalized.split() if w.strip()]

def audit_query(original_description: str, generated_query: str) -> dict:
    """Verifies that the generated search query does not drift from the original description.

    If term coverage of key noun/technical words drops below 70%, flags drift and generates
    a corrected query combining the generated query with missing key terms.
    """
    original_tokens = clean_words(original_description)
    query_tokens = set(clean_words(generated_query))
    
    # Expand query tokens to include parts of hyphenated words
    search_words = set()
    for token in query_tokens:
        search_words.add(token)
        if "-" in token:
            search_words.update(token.split("-"))
            
    # Extract key terms from the original description
    original_terms = set()
    for token in original_tokens:
        subparts = token.split("-") if "-" in token else [token]
        for sub in subparts:
            if len(sub) >= 4 and sub not in STOP_WORDS:
                original_terms.add(sub)
                
    if not original_terms:
        return {
            "is_drifted": False,
            "corrected_query": generated_query,
            "reason": "No original description key terms to verify query against."
        }
        
    # Check present terms
    present_terms = {t for t in original_terms if t in search_words}
    coverage = len(present_terms) / len(original_terms)
    is_drifted = coverage < 0.70
    
    corrected_query = generated_query
    reason = f"Query preserves {len(present_terms)}/{len(original_terms)} ({coverage:.1%}) of description key terms."
    
    if is_drifted:
        missing_terms = sorted(original_terms - search_words)
        corrected_query = generated_query + " " + " ".join(missing_terms)
        reason = f"Query drift detected (coverage: {coverage:.1%}). Missing terms: {missing_terms}."
        
    return {
        "is_drifted": is_drifted,
        "corrected_query": corrected_query,
        "reason": reason
    }
