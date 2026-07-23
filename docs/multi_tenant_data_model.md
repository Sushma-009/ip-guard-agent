# Multi-Tenant Data Model & Scoped Functions

This document outlines the SQLite schema, entity relationships, and scoped data-access functions for the multi-tenant enforcement layer.

---

## 💾 Database Schema

### 1. `organizations`
*   `org_id` (TEXT, PRIMARY KEY): Unique string or UUID.
*   `name` (TEXT): Name of the organization.
*   `created_at` (TIMESTAMP): Time of organization creation.

### 2. `users`
*   `user_id` (TEXT, PRIMARY KEY): Unique identifier.
*   `org_id` (TEXT, NOT NULL, FOREIGN KEY -> `organizations(org_id)`): Associated tenant organization.
*   `email` (TEXT, UNIQUE): Login email.
*   `role` (TEXT, NOT NULL): Role restricting actions (`submitter` | `counsel` | `admin`).
*   `password_hash` (TEXT, NOT NULL): Secure hash of the user password using `bcrypt` package, cost factor 12 (specifically `bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12))`).
*   `created_at` (TIMESTAMP): Time of user creation.

### 3. `submissions`
*   `submission_id` (TEXT, PRIMARY KEY): Unique identifier (session ID in ADK).
*   `org_id` (TEXT, NOT NULL, FOREIGN KEY -> `organizations(org_id)`): Tenant owner of the submission.
*   `user_id` (TEXT, NOT NULL, FOREIGN KEY -> `users(user_id)`): Submitter.
*   `title` (TEXT, NOT NULL)
*   `description` (TEXT, NOT NULL)
*   `libraries_used` (TEXT): JSON-serialized list of libraries.
*   `status` (TEXT, NOT NULL): Current status (`PAUSED_FOR_REVIEW`, `APPROVED_FOR_FILING`, `REJECTED`, `MALFORMED`).
*   `reason` (TEXT): Decision justification.
*   `created_at` (TIMESTAMP)

### 4. `audit_logs`
*   `audit_id` (TEXT, PRIMARY KEY): Unique identifier.
*   `org_id` (TEXT, NOT NULL, FOREIGN KEY -> `organizations(org_id)`): Tenant owner.
*   `submission_id` (TEXT, NOT NULL, FOREIGN KEY -> `submissions(submission_id)`): Target submission.
*   `timestamp` (TIMESTAMP): Log event time.
*   `query_audit` (TEXT): JSON-serialized query auditor data.
*   `verifier_audit` (TEXT): JSON-serialized verifier audit logs.
*   `arbiter_audit` (TEXT): JSON-serialized arbiter logs.

---

## 🔐 Authentication & Session Security
*   **Access Token Expiry**: 1 hour.
*   **Refresh Tokens**: Explicitly deferred (not in scope for this phase).
*   **Secret Management**: Loaded from environment variable `JWT_SECRET` at startup. If the environment variable is absent or empty, the application will fail loudly at boot and raise a `RuntimeError` during module initialization.

---

## 🔍 Cross-Tenant Resource Isolation Policy
*   **Reads**: In `GET /submissions/{submission_id}` (and any other single-resource-by-ID endpoint), when the resource exists but belongs to a different `org_id` than the authenticated user's, the server will return exactly **`404 Not Found`** (not `403 Forbidden`) to avoid leaking the existence of submissions across tenant boundaries.

---

## 🔄 Migration Policy
*   **Policy**: All existing single-tenant development/test data (e.g. prior local session files, old vector run logs) will be discarded and not carried forward into the new multi-tenant database. No database migration scripts are needed as we are in pre-production local development. Any new schema enforcement will apply to new tenant data generated going forward.

---

## 🔒 Scoped Functions Checklist

The following data-access functions are completed and have been verified to correctly enforce tenant scoping using the named passing tests in `test_multi_tenant.py`:

- [x] `create_submission(org_id: str, user_id: str, title: str, description: str, libraries_used: list) -> str` (Verified by `test_cross_tenant_write_blocked`)
- [x] `get_submission(org_id: str, submission_id: str) -> dict` (Verified by `test_cross_tenant_read_blocked`)
- [x] `list_submissions(org_id: str, user_id: str = None) -> list` (Verified by `test_cross_tenant_read_blocked`)
- [x] `update_submission_status(org_id: str, submission_id: str, status: str, reason: str)` (Verified by `test_role_boundary_within_org`)
- [x] `create_audit_log(org_id: str, submission_id: str, query_audit: dict, verifier_audit: list, arbiter_audit: dict)` (Verified by `test_audit_log_isolation`)
- [x] `list_audit_logs(org_id: str) -> list` (Verified by `test_audit_log_isolation`)

---

## 🔍 ChromaDB Collection Policy
*   **Patent Corpus Reference Collection (`patent_prior_art`)**: Remaining a globally shared read-only collection since it represents standard public patent data. No tenant scoping is applied to the patent data.
*   **Submission Embeddings (if any)**: Not used. Submissions are only stored in the scoped SQLite database `ip_guard_tenant.db`.
