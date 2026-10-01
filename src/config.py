"""
config.py — tiny .env loader (stdlib only, no new dependency)
================================================================

WHY THIS EXISTS
---------------
You do NOT have to set OPENROUTER_API_KEY / USE_MOCK in PyCharm or export them in the
terminal every time. Just put them in a `.env` file at the repo root (already git-ignored)
and this module loads them automatically at startup.

PROFESSOR / ANYONE ELSE (no .env)
---------------------------------
If there is no `.env`, nothing breaks: the code falls back to MOCK offline mode by default
(see rag_pipeline.py). So the repo runs end-to-end with ZERO configuration.

PRECEDENCE
----------
Values already in os.environ (e.g. set in PyCharm run config, or exported in the shell)
WIN over the .env file. This means an explicit environment variable is never silently
overridden by a committed .env.
"""

import os


def load_dotenv(path=".env"):
    """Read KEY=VALUE pairs from `path` into os.environ (only if not already set).

    Looks for the file relative to the current working directory. Returns True if a
    .env file was found and loaded.
    """
    if not os.path.exists(path):
        return False
    loaded = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key or not value:
                continue                      # skip blank/empty values (e.g. an unset key)
            if key not in os.environ:         # explicit env wins
                os.environ[key] = value
                loaded.append(key)
    if loaded:
        print(f"[config] loaded from .env: {', '.join(loaded)}")
    return True


if __name__ == "__main__":
    load_dotenv()
    print("OPENROUTER_API_KEY set:", bool(os.environ.get("OPENROUTER_API_KEY")))
    print("USE_MOCK:", os.environ.get("USE_MOCK"))
