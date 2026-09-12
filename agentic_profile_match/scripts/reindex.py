"""Runs the full indexing pipeline against data/resumes/ and upserts into
this project's own Qdrant instance (docker-compose.yml, config.client).

Idempotent: point IDs are derived from (file_path, section), so re-running
this after adding/editing resumes upserts in place rather than duplicating.

Run from agentic_profile_match/ (Qdrant must already be up --
`docker compose up -d`): `uv run python scripts/reindex.py`.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from indexing import (
    build_chunks,
    build_extraction_model,
    discover_resume_files,
    embed_chunks,
    ensure_qdrant_collection,
    extract_fields_batch,
    upsert_chunks,
)
from retrieval import build_embedding_model, build_sparse_embedding_model


def main() -> None:
    entries = discover_resume_files()
    print(f"Found {len(entries)} resume files")

    extraction_model = build_extraction_model()
    records = extract_fields_batch(entries, extraction_model=extraction_model)
    print(f"Extracted metadata for {len(records)} resumes")

    failed = [r for r in records if r["candidate_name"] is None and not r["skills"]]
    if failed:
        print(f"WARNING: {len(failed)} resume(s) got an empty extraction fallback (LLM call failed) -- aborting")
        raise SystemExit(1)

    data_dir = Path(__file__).resolve().parent.parent / "data"
    with open(data_dir / "extractions.json", "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    chunks = build_chunks(records)
    with open(data_dir / "chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    print(f"Built {len(chunks)} chunks from {len(records)} resumes")

    dense_model = build_embedding_model()
    sparse_model = build_sparse_embedding_model()
    embedded_chunks = embed_chunks(chunks, embedding_model=dense_model, sparse_model=sparse_model)

    vector_size = len(embedded_chunks[0]["dense_embedding"])
    ensure_qdrant_collection(vector_size)
    upsert_chunks(embedded_chunks)

    count = config.client.count(config.QDRANT_COLLECTION_NAME).count
    print(f"Collection '{config.QDRANT_COLLECTION_NAME}' has {count} points (expected {len(chunks)})")


if __name__ == "__main__":
    main()
