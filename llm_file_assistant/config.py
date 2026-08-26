import os
from warnings import warn
from dotenv import load_dotenv


load_dotenv()

if not (OPENROUTER_API_KEY := os.getenv("OPENROUTER_API_KEY", "")):
    raise ValueError("OPENROUTER_API_KEY is not set. Please set it in the environment variables or in a .env file.")

LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "")
if LANGSMITH_TRACING == "true":
    if not LANGSMITH_API_KEY:
        raise ValueError("LANGSMITH_TRACING is set but LANGSMITH_API_KEY is not set. Please set it in the environment variables or in a .env file.")
else:
    warn("LANGSMITH_TRACING is not set. Tracing will be disabled. If you want to enable tracing, please set LANGSMITH_TRACING to \"true\" in the environment variables or in a .env file.")
