import os
from warnings import warn

from dotenv import load_dotenv
from qdrant_client import QdrantClient

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

# Shared Qdrant instance -- rag_profile_match's, not a project-owned one. This
# project has no docker-compose.yml of its own; start rag_profile_match's
# Qdrant first (see DESIGN.md's Reuse strategy).
client = QdrantClient("http://localhost:6333")

# Embeddings (retrieval.py) -- same models/collection rag_profile_match indexed with.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
EMBEDDING_MODEL_NAME = "openai/text-embedding-3-small"
QDRANT_COLLECTION_NAME = "resume_chunks"

# Job matching (ranking.py / matching_agent.py)
MATCH_TOP_K = 10
