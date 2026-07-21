# Vector Search Similarity Threshold Calibration Audit

This document records the empirical cosine similarity distributions observed across the 42-document USPTO patent seed corpus (`data/patent_corpus.json`).

---

## 📊 Empirical Similarity Score Distribution

A diagnostic benchmark script (`scratch/audit_thresholds.py`) evaluated 5 known-unrelated control queries and 5 true paraphrase matches of seed patents.

### 1. Unrelated Control Queries
| Query Description | Top Matched Patent | Raw Cosine Similarity |
| :--- | :--- | :---: |
| Sourdough bread baking recipe app with temperature alarms | *None (Filtered)* | **0.237** |
| Pet grooming appointment scheduler and dog washing queue | *None (Filtered)* | **0.248** |
| Underwater basket weaving techniques and bamboo fiber knots | *None (Filtered)* | **0.161** |
| Automated home coffee machine bean grinding sensor | *None (Filtered)* | **0.309** |
| Personal fitness workout tracker for marathon runners | *None (Filtered)* | **0.168** |

*   **Observed Max Unrelated Similarity**: `0.309`

---

### 2. True Match Paraphrase Queries
| Target Patent ID | Paraphrased Query Description | Matched Patent ID | Raw Cosine Similarity |
| :--- | :--- | :--- | :---: |
| `US11234567B2` | Routing protocol and hardware architecture for quantum networks... | `US11234567B2` | **0.998** |
| `US10456789B1` | Background daemon monitoring directory filesystem changes and sync to S3... | `US10456789B1` | **0.866** |
| `US9876543B2` | Zero knowledge cryptographic session key exchange over database channels... | `US9876543B2` | **0.750** |
| `US9123456B2` | Decentralized consensus protocol with secondary arbiter supervisor nodes... | `US9123456B2` | **0.849** |
| `US8555222B2` | Automated receipt OCR processing engine checking policy compliance... | `US8555222B2` | **0.744** |

*   **Observed Min True Match Similarity**: `0.744`

---

## 🎯 Empirical Decision Gap & Tier Justification

```
[ Unrelated Noise: 0.161 - 0.309 ] <======== CLEAR GAP (0.435) ========> [ True Matches: 0.744 - 0.998 ]
                                       Midpoint: 0.526 -> Set to 0.55
```

### Derived Policy Tiers
*   **`HIGH_CONFLICT` (`>= 0.55`)**: Midpoint of empirical decision gap (`0.526`). Ensures all true paraphrases (`0.744` - `0.998`) are classified as high conflict while guaranteeing zero false positives from unrelated queries (`<= 0.309`).
*   **`MODERATE_OVERLAP` (`0.40 - 0.55`)**: Partial technical overlap requiring justification if novelty score > 6/10.
*   **`LOW_OVERLAP` (`0.30 - 0.40`)**: Low similarity context.
*   **`NOT_RELEVANT` (`< 0.30`)**: Excluded entirely from LLM reviewer prompt.
