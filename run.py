"""
run.py

Convenience entry point. Prefer running directly:
    uv run uvicorn competitive_programming_factory.app:app --reload --port 8391
"""
import subprocess
import sys

if __name__ == "__main__":
    sys.exit(subprocess.call([
        "uv", "run", "uvicorn", "competitive_programming_factory.app:app",
        "--reload", "--port", "8391",
    ]))
