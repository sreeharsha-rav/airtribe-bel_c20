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

# Add Qdrant client initialization here, if needed for your application.
client = QdrantClient("http://localhost:6333")

# Batch metadata extraction (resume_rag.py)
EXTRACTION_MODEL_NAME = "openai/gpt-oss-120b"
EXTRACTION_MODEL_PROVIDER = "openrouter"
EXTRACTION_BATCH_SIZE = 10
EXTRACTION_MAX_CONCURRENCY = 10
EXTRACTION_MAX_RETRIES = 2

# Embeddings + vector store (resume_rag.py) -- SCAFFOLD, not yet implemented.
# langchain-openrouter has no embeddings class; OpenRouter's OpenAI-compatible
# /embeddings endpoint (https://openrouter.ai/api/v1/embeddings) is reachable
# via langchain-openai's OpenAIEmbeddings pointed at OPENROUTER_BASE_URL.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
EMBEDDING_MODEL_NAME = "openai/text-embedding-3-small"
QDRANT_COLLECTION_NAME = "resume_chunks"

# Job matching (job_matcher.py) -- SCAFFOLD, not yet implemented.
MATCH_TOP_K = 10