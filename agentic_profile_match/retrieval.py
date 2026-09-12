"""JD embedding + hybrid dense/sparse retrieval against the shared
resume_chunks Qdrant collection.

Duplicated from rag_profile_match/resume_rag.py + job_matcher.py (DESIGN.md's
Reuse strategy, Q1) — same shared Qdrant instance and collection populated by
rag_profile_match's indexing notebook; no reindexing happens here. Unlike
job_matcher.embed_job_description (which takes raw jd_text and splits it
itself), this version takes already-split jd_sections directly, since the
Search Resumes node runs after Extract Requirements has already produced them.
"""

from fastembed import SparseTextEmbedding
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr
from qdrant_client import models as qdrant_models

import config


def build_embedding_model() -> Embeddings:
    """Builds the dense embedding client, via OpenRouter's OpenAI-compatible
    /embeddings endpoint (langchain-openrouter itself exports no embeddings
    class, only ChatOpenRouter).
    """
    return OpenAIEmbeddings(
        model=config.EMBEDDING_MODEL_NAME,
        base_url=config.OPENROUTER_BASE_URL,
        api_key=SecretStr(config.OPENROUTER_API_KEY),
    )


def build_sparse_embedding_model() -> SparseTextEmbedding:
    """Builds the sparse (lexical/keyword) embedding model for hybrid search.

    Uses fastembed's BM25 model ("Qdrant/bm25"), the same one
    rag_profile_match indexed resume chunks with — dense/sparse vectors must
    come from matching models on both sides for RRF fusion to be meaningful.
    """
    return SparseTextEmbedding(model_name="Qdrant/bm25")


def embed_job_description(
    jd_sections: dict[str, str],
    embedding_model: Embeddings | None = None,
    sparse_model: SparseTextEmbedding | None = None,
) -> dict:
    """Embeds a job description's descriptive prose (header + About the role
    + Responsibilities) with the same dense+sparse models used for resume
    chunks, so vectors are directly comparable. Must-have/Nice-to-have
    bullets are deliberately excluded here -- they're matched via
    ranking.keyword_match_score instead of semantic similarity.
    """
    embedding_model = embedding_model or build_embedding_model()
    sparse_model = sparse_model or build_sparse_embedding_model()

    query_text = "\n\n".join(
        jd_sections[key] for key in ("header", "about_the_role", "responsibilities") if jd_sections.get(key)
    )

    dense_vector = embedding_model.embed_query(query_text)
    sparse_vector = list(sparse_model.embed([query_text]))[0]

    return {
        "dense": dense_vector,
        "sparse": {
            "indices": sparse_vector.indices.tolist(),
            "values": sparse_vector.values.tolist(),
        },
    }


def semantic_search(jd_vectors: dict, top_k: int = config.MATCH_TOP_K) -> list[dict]:
    """Queries Qdrant for the top_k resume candidates whose chunks best match
    the job description, fusing dense + sparse similarity via Reciprocal
    Rank Fusion (RRF).

    The collection is chunk-level (up to 4 chunks per resume), so raw hits
    are grouped by metadata.file_path, keeping each candidate's best (max)
    fused score and up to 2 distinct matched chunk excerpts. top_k here
    controls the candidate *pool* size returned, not the final ranked
    result count (that's ranking.score_and_rank's job, after must-have
    filtering).
    """
    prefetch_limit = max(top_k * 4, 40)
    response = config.client.query_points(
        collection_name=config.QDRANT_COLLECTION_NAME,
        prefetch=[
            qdrant_models.Prefetch(query=jd_vectors["dense"], using="dense", limit=prefetch_limit),
            qdrant_models.Prefetch(
                query=qdrant_models.SparseVector(**jd_vectors["sparse"]), using="sparse", limit=prefetch_limit
            ),
        ],
        query=qdrant_models.FusionQuery(fusion=qdrant_models.Fusion.RRF),
        limit=prefetch_limit,
        with_payload=True,
    )

    candidates: dict[str, dict] = {}
    for point in response.points:
        assert point.payload is not None
        metadata = point.payload["metadata"]
        file_path = metadata["file_path"]
        excerpt = point.payload["page_content"]

        existing = candidates.get(file_path)
        if existing is None:
            candidates[file_path] = {
                "file_path": file_path,
                "metadata": metadata,
                "score": point.score,
                "excerpts": [excerpt],
            }
        else:
            existing["score"] = max(existing["score"], point.score)
            if excerpt not in existing["excerpts"] and len(existing["excerpts"]) < 2:
                existing["excerpts"].append(excerpt)

    ranked = sorted(candidates.values(), key=lambda c: c["score"], reverse=True)
    return ranked[:top_k]
