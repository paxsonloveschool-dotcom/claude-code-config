"""JARVIS SessionStart hook — registers each Claude session as an active agent in the task registry.

Fails gracefully if jarvis.client isn't available yet (never crashes the session).
"""
import os
import sys

# Session identity
session_name = (
    os.environ.get("CLAUDE_SESSION_NAME")
    or (sys.argv[1] if len(sys.argv) > 1 else None)
    or "unknown"
)

# Try to find jarvis.client in known locations
_search_paths = [
    os.path.expanduser(r"~\.claude\jarvis"),
    os.path.join(os.path.dirname(__file__), "..", "jarvis"),
    os.path.join(os.path.expanduser("~"), "projects", "claude-code-config", "jarvis"),
]
for p in _search_paths:
    p = os.path.normpath(p)
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

try:
    from client import claim_task  # type: ignore
    task_id = claim_task(owner=session_name, objective=f"Claude session {session_name} active")
    print(f"JARVIS: session {session_name} registered as task {task_id}")
except ImportError:
    print(f"JARVIS: session {session_name} started (registry client not yet available — skipping registration)")
except Exception as e:
    print(f"JARVIS: session {session_name} started (registration error: {e})")

sys.exit(0)
