# Formal Evidentiary & Security Review: Digital Chain of Custody

> **Document ID:** EVID-SEC-2026-09-04  
> **Status:** Approved / Enforced  
> **Statutory Basis:** Section 63 of Bharatiya Sakshya Adhiniyam, 2023 (BSA) / Section 65B of Indian Evidence Act, 1872 (IEA); Sections 36 & 49 of Legal Metrology Act, 2009.  
> **Applicable Task:** `E4-04` per `07_IMPLEMENTATION_PLAN.md` and `08_TRACKER.md`.

---

## 1. Executive Summary & Purpose

In regulatory enforcement operations, field officers capture photos of offending commodity labels to issue statutory compound notices, seize non-compliant inventory, or initiate prosecutions before Judicial Magistrates.
Under Indian evidentiary jurisprudence:
- Electronic evidence must satisfy strict admissibility criteria demonstrating that the computer and digital imaging pipeline operated reliably and without human tampering.
- An AI finding or OCR extraction alone cannot serve as conclusive evidence in court; the officer makes the final ruling, and every piece of digital proof must remain cryptographically linked to the exact pixels captured in the field.

This document details the formal security review, cryptographic controls, and immutability architecture implemented across NiyamDrishti to guarantee courtroom defensibility.

---

## 2. Threat Model & Attack Vectors

| Attack Vector | Threat Description | Architectural Mitigation | Enforcement Layer |
|---|---|---|---|
| **Image Tampering / Replacement** | Replacing or manipulating a captured label photo on disk or storage bucket to alter evidence. | Image SHA-256 fingerprint generated at the moment of intake/upload and stored on `inspection_images`. | `save_image_bytes`, `InspectionImage.sha256_hash`, `EvidenceVerificationService` |
| **Audit Log Retraction / Alteration** | Malicious officer or compromised DB admin modifying or deleting prior review override entries to hide changes. | `audit_logs` table is strictly append-only; SQLAlchemy event listeners intercept and reject `UPDATE` and `DELETE` operations with `PermissionError`. | SQLAlchemy ORM event listeners (`before_update`, `before_delete`) |
| **Database Row Insertion / Forgery** | Direct SQL insertion of forged audit events into the database. | Sequential Merkle/hash-chaining: each entry computes `entry_hash = SHA-256(prev_hash + actor + action + entity + before + after)`. An out-of-band insertion breaks the hash chain. | `compute_audit_log_hash`, `verify_evidence_chain` |
| **Rule Engine Version Drift** | Changing rule definitions retroactively to alter past compliance verdicts. | Confirm-and-freeze: `inspections.rule_pack_version` is frozen at creation time. Rule packs are versioned and immutable once activated. | `RulePack` schema, Section 36 immutability rule |
| **Bounding Box Disconnect** | Alleging a declaration was absent or malformed without visual proof. | Every `ExtractedField` strictly references its parent `InspectionImage` and preserves normalized coordinate bounding boxes `{x, y, w, h}`. | `extracted_fields`, `violations`, Evidence Viewer |

---

## 3. Cryptographic Controls Architecture

### 3.1 Photographic Fingerprinting
When an image is received via multipart form upload or batch offline sync:
```python
sha256_hash = hashlib.sha256(file_bytes).hexdigest()
image_record = InspectionImage(
    ...,
    sha256_hash=sha256_hash,
)
```
Upon verification, the system reads the physical file bytes from storage and re-verifies `hashlib.sha256(disk_bytes).hexdigest() == stored_hash`. Any byte alteration immediately trips `file_integrity = "hash_mismatch"` and flags `overall_status = "COMPROMISED"`.

### 3.2 Audit Log Cryptographic Hash Chaining
Every entry in `audit_logs` is cryptographically chained to its predecessor:
```
[GENESIS] -> Entry 1 (Hash: a1b2...) -> Entry 2 (Prev: a1b2..., Hash: c3d4...) -> Entry 3 ...
```
If an adversary updates or deletes any row in the audit trail, the cryptographic chain is broken.

### 3.3 Inspection Evidence Master Digest
The system computes a whole-case master digest (`evidence_chain_hash`):
```
SHA-256("INSPECTION:" + id + ":RULE_PACK:" + version + ":IMAGES:" + sorted_image_hashes + ":FIELDS:" + sorted_field_digests + ":VIOLATIONS:" + sorted_violation_ids)
```
This master hash uniquely identifies the state of the case at the time of finalization.

---

## 4. Statutory Electronic Evidence Certification

NiyamDrishti exposes an official certificate generator pursuant to:
- **Section 63 of Bharatiya Sakshya Adhiniyam, 2023 (BSA)**
- **Section 65B of Indian Evidence Act, 1872 (IEA)**

### Endpoint: `GET /api/v1/inspections/{id}/evidence/certificate`
The resulting certificate contains:
1. **Certificate Identifier & Statutory Header**
2. **Deponent Details:** Officer Name, Badge/Role, Official Email, Department Jurisdiction.
3. **Computer System & Software Environment:** Operating system, software version, cryptographic algorithms (FIPS PUB 180-4 compliant SHA-256).
4. **Photographic Evidence Schedule:**
   - Panel role (`front_pdp`, `back_panel`, `sticker`, etc.)
   - Capture timestamp
   - Cryptographic SHA-256 fingerprint
   - Resolution and optical calibration scale (mm/px)
   - Integrity verdict (`verified`)
5. **Chain of Custody & Audit Trail:** Chronological log of officer confirmations and corrections with SHA-256 entry hashes.
6. **Master Evidence Chain Digest:** (`evidence_chain_hash`)
7. **Statutory Attestation:**
   Formal affirmation under oath certifying that the computing systems were operating normally and without error, and that electronic evidence has remained unaltered and tamper-free.

---

## 5. Verification Endpoint & Operations

### Endpoint: `GET /api/v1/inspections/{id}/evidence/verify`
Officers, supervisors, and judicial evaluators can execute real-time evidentiary audits:
- **`overall_status`**: `"VERIFIED"` (100% intact), `"COMPROMISED"` (tampering detected), or `"INCOMPLETE"`.
- **`is_tamper_free`**: Boolean flag.
- Granular breakdown of verified vs. compromised images and audit log hash verification.
