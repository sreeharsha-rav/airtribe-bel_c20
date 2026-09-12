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

# This project's own Qdrant instance (docker-compose.yml), independent of
# rag_profile_match's -- a different host port (6350) so both can run at the
# same time without conflict. See DESIGN.md's Reuse strategy.
client = QdrantClient("http://localhost:6350")

# Embeddings (retrieval.py, indexing.py)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
EMBEDDING_MODEL_NAME = "openai/text-embedding-3-small"
QDRANT_COLLECTION_NAME = "resume_chunks"

# Job matching (ranking.py / matching_agent.py)
MATCH_TOP_K = 10

# Batch metadata extraction (indexing.py) -- same pattern as
# rag_profile_match/resume_rag.py's extract_fields_batch.
EXTRACTION_MODEL_NAME = "openai/gpt-oss-120b"
EXTRACTION_MODEL_PROVIDER = "openrouter"
EXTRACTION_BATCH_SIZE = 10
EXTRACTION_MAX_CONCURRENCY = 10
EXTRACTION_MAX_RETRIES = 2

# Chat model (tools.py's generate_interview_questions, matching_agent's
# conversational agent, screening.py's Deep Analysis/Recommendation) -- same
# model llm_file_assistant/rag_profile_match use.
MODEL_NAME = "openai/gpt-oss-120b"
MODEL_PROVIDER = "openrouter"

# Multi-round screening (screening.py) -- one structured-output LLM call per
# shortlisted candidate, per node; bounded by MATCH_TOP_K (default 10), so a
# single un-chunked .batch() call is fine (see rag_profile_match's
# EXTRACTION_BATCH_SIZE for why a much larger corpus needs chunking and this
# doesn't).
SCREENING_MAX_CONCURRENCY = 10
SCREENING_MAX_RETRIES = 2
