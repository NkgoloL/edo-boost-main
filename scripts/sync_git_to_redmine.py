#!/usr/bin/env python3
import sys
import re
import subprocess

# Redmine User ID for NkgoloL
USER_ID = 5

# Issue ID Mapping
ISSUE_MAP = {
    "gamification": 1, "badge": 1, "xp": 1, "streak": 1, "reward": 1,
    "parent": 2, "guardian": 2, "consent": 2, "family": 2, "verification": 2,
    "diagnostic": 3, "irt": 3, "assessment": 3, "item": 3, "test": 3,
    "study plan": 4, "plan": 4, "refresh": 4, "rationale": 4,
    "fourth estate": 5, "estate": 5, "audit_events": 5,
    "judiciary": 6, "compliance": 6, "policy": 6,
    "profiler": 7, "archetype": 7, "profile": 7,
    "schema": 8, "orm": 8, "migration": 8, "table": 8, "db": 8, "constitutional": 8,
    "orchestrator": 9, "operation": 9, "request": 9,
    "audit": 10, "log": 10, "event": 10,
    "lesson": 11, "catalog": 11, "content": 11,
    "learner": 12, "onboarding": 12, "nickname": 12,
    "infra": 13, "docker": 13, "devops": 13, "deploy": 13, "redmine": 13, "sync": 13,
    "test": 14, "qa": 14, "coverage": 14, "vitest": 14, "pytest": 14,
}

def get_latest_commits(n=5):
    try:
        cmd = ["git", "log", f"-n {n}", "--pretty=format:%h|%an|%ad|%s", "--date=short"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip().split("\n")
    except Exception as e:
        print(f"Error getting git log: {e}")
        return []

def get_issue_id(message):
    message = message.lower()
    for kw, issue_id in ISSUE_MAP.items():
        if kw in message:
            return issue_id
    return None

def sync():
    commits = get_latest_commits(10)
    
    for line in commits:
        if not line: continue
        parts = line.split("|")
        if len(parts) < 4: continue
        hash_id, author, date_str, message = parts[0], parts[1], parts[2], "|".join(parts[3:])
        
        issue_id = get_issue_id(message)
        if not issue_id: continue
        
        notes = f"Commit {hash_id} by {author} on {date_str}: {message}"
        notes_escaped = notes.replace("'", "''").replace("\\", "\\\\")
        
        # Check and Insert Journal
        sql = f"USE redmine; INSERT INTO journals (journalized_id, journalized_type, user_id, notes, created_on) " \
              f"SELECT {issue_id}, 'Issue', {USER_ID}, '{notes_escaped}', NOW() " \
              f"WHERE NOT EXISTS (SELECT 1 FROM journals WHERE notes LIKE 'Commit {hash_id}%');"
        
        # Heuristic for progress
        if any(kw in message.lower() for kw in ["complete", "done", "finish", "final"]):
             sql += f" UPDATE issues SET done_ratio = 100, status_id = 3, updated_on = NOW() WHERE id = {issue_id};"
        elif any(kw in message.lower() for kw in ["feat", "add", "implement"]):
             sql += f" UPDATE issues SET done_ratio = GREATEST(COALESCE(done_ratio, 0), 70), status_id = 2, updated_on = NOW() WHERE id = {issue_id};"
        elif any(kw in message.lower() for kw in ["fix", "bug", "hotfix"]):
             sql += f" UPDATE issues SET done_ratio = GREATEST(COALESCE(done_ratio, 0), 90), status_id = 2, updated_on = NOW() WHERE id = {issue_id};"
        else:
             sql += f" UPDATE issues SET done_ratio = GREATEST(COALESCE(done_ratio, 0), 30), status_id = 2, updated_on = NOW() WHERE id = {issue_id};"
        
        # Run SQL via mariadb CLI
        subprocess.run(["mariadb", "-u", "redmine", "-e", sql])

if __name__ == "__main__":
    sync()
