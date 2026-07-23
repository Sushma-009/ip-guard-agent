import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "ip_guard_tenant.db"
)

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def initialize_db():
    conn = get_connection()
    try:
        # Create organizations table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                org_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (org_id) REFERENCES organizations(org_id) ON DELETE CASCADE
            );
        """)
        
        # Create submissions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                submission_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                libraries_used TEXT,
                status TEXT NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (org_id) REFERENCES organizations(org_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
        """)
        
        # Create audit_logs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                audit_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                submission_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                query_audit TEXT,
                verifier_audit TEXT,
                arbiter_audit TEXT,
                FOREIGN KEY (org_id) REFERENCES organizations(org_id) ON DELETE CASCADE,
                FOREIGN KEY (submission_id) REFERENCES submissions(submission_id) ON DELETE CASCADE
            );
        """)
        conn.commit()
    finally:
        conn.close()

# Seeding / creation helpers
def create_organization(org_id: str, name: str):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO organizations (org_id, name) VALUES (?, ?);",
            (org_id, name)
        )
        conn.commit()
    finally:
        conn.close()

def create_user(user_id: str, org_id: str, email: str, role: str, password_hash: str):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO users (user_id, org_id, email, role, password_hash) VALUES (?, ?, ?, ?, ?);",
            (user_id, org_id, email, role, password_hash)
        )
        conn.commit()
    finally:
        conn.close()

def get_user_by_email(email: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT user_id, org_id, email, role, password_hash FROM users WHERE email = ?;",
            (email,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

# Scoped submission helpers
def create_submission(submission_id: str, org_id: str, user_id: str, title: str, description: str, libraries_used: list, status: str, reason: str) -> str:
    conn = get_connection()
    try:
        libs_serialized = json.dumps(libraries_used)
        conn.execute(
            "INSERT INTO submissions (submission_id, org_id, user_id, title, description, libraries_used, status, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
            (submission_id, org_id, user_id, title, description, libs_serialized, status, reason)
        )
        conn.commit()
        return submission_id
    finally:
        conn.close()

def get_submission(org_id: str, submission_id: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT submission_id, org_id, user_id, title, description, libraries_used, status, reason, created_at FROM submissions WHERE org_id = ? AND submission_id = ?;",
            (org_id, submission_id)
        ).fetchone()
        if row:
            res = dict(row)
            res["libraries_used"] = json.loads(res["libraries_used"]) if res["libraries_used"] else []
            return res
        return None
    finally:
        conn.close()

def list_submissions(org_id: str, user_id: str = None) -> list:
    conn = get_connection()
    try:
        if user_id:
            rows = conn.execute(
                "SELECT submission_id, org_id, user_id, title, description, libraries_used, status, reason, created_at FROM submissions WHERE org_id = ? AND user_id = ? ORDER BY created_at DESC;",
                (org_id, user_id)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT submission_id, org_id, user_id, title, description, libraries_used, status, reason, created_at FROM submissions WHERE org_id = ? ORDER BY created_at DESC;",
                (org_id,)
            ).fetchall()
            
        results = []
        for r in rows:
            res = dict(r)
            res["libraries_used"] = json.loads(res["libraries_used"]) if res["libraries_used"] else []
            results.append(res)
        return results
    finally:
        conn.close()

def update_submission_status(org_id: str, submission_id: str, status: str, reason: str):
    conn = get_connection()
    try:
        # Enforce org_id scoping during update
        conn.execute(
            "UPDATE submissions SET status = ?, reason = ? WHERE org_id = ? AND submission_id = ?;",
            (status, reason, org_id, submission_id)
        )
        conn.commit()
    finally:
        conn.close()

# Scoped audit logging helpers
def create_audit_log(org_id: str, submission_id: str, query_audit: dict, verifier_audit: list, arbiter_audit: dict):
    conn = get_connection()
    try:
        import uuid
        audit_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO audit_logs (audit_id, org_id, submission_id, query_audit, verifier_audit, arbiter_audit) VALUES (?, ?, ?, ?, ?, ?);",
            (
                audit_id,
                org_id,
                submission_id,
                json.dumps(query_audit) if query_audit else None,
                json.dumps(verifier_audit) if verifier_audit else None,
                json.dumps(arbiter_audit) if arbiter_audit else None
            )
        )
        conn.commit()
    finally:
        conn.close()

def list_audit_logs(org_id: str) -> list:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT audit_id, org_id, submission_id, timestamp, query_audit, verifier_audit, arbiter_audit FROM audit_logs WHERE org_id = ? ORDER BY timestamp DESC;",
            (org_id,)
        ).fetchall()
        results = []
        for r in rows:
            res = dict(r)
            res["query_audit"] = json.loads(res["query_audit"]) if res["query_audit"] else None
            res["verifier_audit"] = json.loads(res["verifier_audit"]) if res["verifier_audit"] else []
            res["arbiter_audit"] = json.loads(res["arbiter_audit"]) if res["arbiter_audit"] else None
            results.append(res)
        return results
    finally:
        conn.close()
