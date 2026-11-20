"""Tekken agent harness package.

Loads the repo-root .env on import so that module-level os.environ reads
(capture.py, agent.py, llm.py) see the configured values no matter which
entry point runs first. Real environment variables take precedence over
.env (override=False).
"""

from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    # python-dotenv not installed; fall back to plain environment variables.
    pass
