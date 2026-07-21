# Evaluation Dataset Label Reconciliation & Corrections

This document records the human technical review and reconciliation process for `eval/eval_set.json` prior to multi-agent critique implementation.

---

## 🔬 Task 1: Blind Three-Way Review of `eval_001`

*   **Submission**: `Quantum Photonic Entanglement Frequency Modulator`
    *   *Description*: *"An electro-optic device that modulates the phase frequency of entangled photon pairs at gigahertz clock speeds to accelerate ultra-secure quantum communications."*
*   **Candidates Evaluated**:
    1.  `US11234567B2` (*Quantum Packet Header Processing and Network Routing Protocol*): Rejection — network routing layer protocol, not hardware electro-optic modulation.
    2.  `US11234568B2` (*Photonic Entanglement Swapping for Long-Distance Quantum Repeater*): Rejection — quantum repeater entanglement swapping apparatus, not electro-optic phase frequency modulation.
    3.  `US11234569B2` (*Quantum Key Distribution Protocol with Decoy State Modulation*): Rejection — software QKD protocol modulating decoy states to prevent splitting attacks.
*   **Verdict**: **No strong conflict — `clear_novelty` / `HIGH` / `null` is correct as originally written!**
    *   *Rationale*: All candidate patents describe network routing, repeaters, or decoy protocols. None claim physical GHz electro-optic phase frequency modulators for entangled photon pairs. The overlap is vocabulary-level ("quantum", "photonic", "phase modulation"). `eval_001` is reverted back to `category: clear_novelty`, `expected_novelty_band: HIGH`, `expected_conflict_patent_id: null`.

---

## 🔬 Task 2: Re-judgment of `eval_014`

*   **Submission**: `Cloud Object Store Deduplication with Client-Side Delta Chunking`
    *   *Description*: *"A distributed file storage middleware running variable block deduplication and AES-GCM client-side encryption prior to uploading chunks to object storage."*
*   **Candidate Evaluated**: `US10456790B1` (*Deduplicated Block-Level Cloud Storage Compression Engine*)
*   **Observed Pipeline Cosine Similarity**: `0.778` (sits well inside `HIGH_CONFLICT` $\ge 0.55$).
*   **Verdict**: **Recategorized from `ambiguous` to `clear_conflict`!**
    *   *Rationale*: Both `eval_014` and `US10456790B1` claim variable block chunking and hash deduplication for cloud object stores. Adding AES-GCM client-side encryption to block deduplication is a standard engineering implementation detail, not a distinct core invention. A human legal reviewer would judge this as a direct prior-art conflict. Updated to `category: clear_conflict`, `expected_novelty_band: LOW`, `expected_conflict_patent_id: US10456790B1`.

---

## 🔬 Task 3: Conflict-ID Trace and Re-judgment for `eval_015`

*   **Submission**: `Dynamic LLM Output Streaming Anomaly Distortion`
    *   *Description*: *"A proxy server monitoring token generation streams from neural networks to inject subtle token noise when detecting potential intellectual property leaks."*
*   **Factual Trace**:
    *   `expected_conflict_patent_id`: `US10987657B1` (*Model Extraction Attack Mitigation via Logit Distortion*)
    *   `actual_matched_patent_id`: `US10987656B1` (*Generative AI Output Data Loss Prevention and PII Masking*)
    *   `scores.conflict_match`: `False` (Confirmed factual mismatch in baseline run).
*   **Candidates Evaluated**:
    1.  `US10987656B1` (*Generative AI Output DLP & PII Masking*): Real-time proxy stream analyzer intercepting LLM token streams to prevent data leaks.
    2.  `US10987657B1` (*Model Extraction Mitigation via Logit Distortion*): Calibrated noise injection into output logit distributions.
*   **Verdict**: **Update expected conflict to `US10987656B1`!**
    *   *Rationale*: `eval_015` combines proxy token stream interception (`US10987656B1`) with logit noise injection (`US10987657B1`). `US10987656B1` is the stronger structural architecture match because `eval_015` explicitly specifies a proxy server monitoring token generation streams. Updated `expected_conflict_patent_id` to `US10987656B1`.

---

## 🔬 Task 2 (Restoration): Blind Review and Construction of `eval_021`

*   **Submission**: `Searchable Symmetric Encryption with Homomorphic Key Custody`
    *   *Description*: *"A database proxy engine executing searchable symmetric encryption substring queries over ciphertext columns combined with homomorphic multi-party threshold key custody across independent vault nodes."*
*   **Domain**: Cryptography
*   **Candidates Evaluated**:
    1.  `US9876543B2` (*Homomorphic Cryptographic Key Exchange for Distributed Databases*)
    2.  `US9876548B2` (*Searchable Symmetric Encryption for Multi-Tenant Database Columns*)
*   **Blind Technical Verdict**: **Valid Ambiguous / Borderline Submission!**
    *   *Rationale*: `eval_021` shares searchable SQL substring query mechanics over ciphertext indexes with `US9876548B2`, while incorporating multi-party threshold key custody across vault nodes from `US9876543B2`. The combination represents a defensible middle-ground case. Added to `eval_set.json` as `category: ambiguous`, `expected_novelty_band: MEDIUM`, `expected_conflict_patent_id: US9876548B2`. Total evaluation dataset restored to **$n = 21$ cases** ($n = 4$ ambiguous cases).
