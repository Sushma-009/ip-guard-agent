# Trace of `eval_001` Classification Reversal

This document details the tracing of case `eval_001` (`Quantum Photonic Entanglement Frequency Modulator`) to explain its classification flip between historical mock runs and real API runs.

---

## Task 1: Comparison of Verifier Verdicts

### Prior Run (`eval_results_20260723_124351.json`)
```json
      "case_id": "eval_001",
      "actual": {
        "case_id": "eval_001",
        "category": "clear_novelty",
        "status": "UNKNOWN",
        "novelty_score": null,
        "actual_novelty_band": "UNSCORED",
        "matched_patent_id": null,
        "is_security_event": false,
        "arbiter_audit": null
      }
```
> [!NOTE]
> The prior run from 2026-07-23 (`124351`) was incomplete for `eval_001` due to rate-limit exhaustion. Thus, no MatchVerifier output existed in that file.

### Historical Offline Mock Run (`eval_results_20260722_225924.json`)
In the offline mock-based run, case `eval_001` was mocked as `SPURIOUS_MATCH`, resulting in a novelty score of `8/10` (`HIGH`).

### Newest Real-API Run (`eval_results_20260723_162225.json`)
```json
    {
      "patent_id": "US11234569B2",
      "is_verified": true,
      "status": "SUCCESS",
      "category": "VERIFIED_CONFLICT_WITH_DIFFERENTIATOR",
      "reasoning": "VERIFIED_CONFLICT_WITH_DIFFERENTIATOR: Both technologies address the modulation of quantum states for secure communication, but the submission focuses on a specific hardware-level electro-optic device for frequency modulation, whereas the patent focuses on a protocol-level decoy state modulation technique to mitigate specific security vulnerabilities."
    },
    {
      "patent_id": "US11234568B2",
      "is_verified": true,
      "status": "SUCCESS",
      "category": "VERIFIED_CONFLICT_WITH_DIFFERENTIATOR",
      "reasoning": "VERIFIED_CONFLICT_WITH_DIFFERENTIATOR: While both technologies utilize photonic entanglement for quantum communication, the candidate patent focuses on the architectural framework of entanglement swapping for long-distance repeaters, whereas the submission introduces a specific electro-optic hardware component for high-speed phase frequency modulation to enhance transmission efficiency."
    }
```

### Diagnosis
The classification tag flipped from **`SPURIOUS_MATCH`** (in mock runs) to **`VERIFIED_CONFLICT_WITH_DIFFERENTIATOR`** (in real runs). This is not due to a runtime pipeline change, but rather a direct transition from a hardcoded mock environment to real Gemini API content-generation. The real model sees a substantive domain relationship (both manipulate photonic/quantum states in key exchange setups) and maps it to the middle category (`VERIFIED_CONFLICT_WITH_DIFFERENTIATOR`).

---

## Task 2: Pipeline Stability Testing

We ran the isolated `eval_001` pipeline twice in immediate succession with `temperature=0.0` enforced:
* **Are runs identical**: **`True`** (100% byte-identical outputs across matches, verifier categories, reasonings, and arbiter outputs).
* **Verdict**: The pipeline behaves in a completely deterministic manner. The change in the verdict is an expected shift from offline mocking to real API model evaluation under the three-way prompt schema.
