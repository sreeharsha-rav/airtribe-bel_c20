# RAG Based Profile Matching

A two-part RAG pipeline that matches candidate resumes to a job description.
**`resume_rag.py`** and **`job_matcher.py`** are function libraries only — no
top-level execution — and **`rag_analysis.ipynb`** is the actual entry point:
it imports from both modules and runs the pipeline cell by cell, with inline
inspection of intermediate results.

**Implementation status:** chunking + metadata extraction are implemented and
working; embeddings, vector storage, job matching, and performance metrics
are scaffolded (function signatures + docstrings only, each raising
`NotImplementedError`) pending further implementation. `metrics.py` holds the
retrieval-accuracy/latency evaluation scaffold.

## Design

### Document Processing (`resume_rag.py`)

- **Loading** — resumes (`.txt`, `.docx`, `.pdf`) are read from `root_dir/resumes/`
  using the sandboxed filesystem tools carried over from the `llm_file_assistant`
  project (Milestone 1). *Implemented.*
- **Chunking** — resumes follow a consistent section structure (Summary, Skills,
  Experience, Education), so chunking is section-aware rather than fixed-size,
  keeping each section intact as its own chunk. *Implemented.*
- **Metadata extraction** — Name, Skills, Experience (years), and Education are
  extracted per resume via a structured-output OpenRouter chat model, batched
  with `.batch()` for concurrency. *Implemented.*
- **Embeddings** — *Scaffolded.* `langchain-openrouter` has no embeddings
  class, so this will use OpenRouter's OpenAI-compatible `/embeddings`
  endpoint via `langchain-openai`'s `OpenAIEmbeddings` (not yet a dependency).
- **Vector store** — *Scaffolded.* [Qdrant](https://qdrant.tech/), run locally
  via `docker-compose.yml`; `config.py` already constructs a `QdrantClient`.
  Each chunk will be stored with metadata for filtering once
  `ensure_qdrant_collection`/`upsert_chunks` are implemented.

### Job Matching (`job_matcher.py`) — *Scaffolded*

- **Semantic search** — the job description is embedded and used to retrieve
  the top-K (K=10) most similar resume chunks from Qdrant.
- **Hybrid search** — semantic similarity is combined with keyword matching for
  critical/must-have skills (e.g. required tools, "5+ years Python").
- **Scoring & ranking** — matches are scored on a 0–100 scale, with reasoning
  describing which resume sections drove the match, then filtered against any
  must-have requirements.
- **Output** — a `MatchResult` per candidate: `candidate_name`, `resume_path`,
  `match_score`, `matched_skills`, `relevant_excerpts`, and `reasoning`.

### Performance Metrics (`metrics.py`) — *Scaffolded*

- **Retrieval accuracy** — precision@k/recall@k of `job_matcher.semantic_search`
  against a hand-labeled ground-truth mapping of job → expected resumes.
- **Latency** — per-stage wall-clock timing (embedding, Qdrant query, scoring)
  to identify slow stages.

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Docker (to run Qdrant locally)
- An [OpenRouter](https://openrouter.ai/) API key (used for both embeddings and
  chat/reasoning models)
- Jupyter (`ipykernel` + `jupyterlab`), to run `rag_analysis.ipynb` — installed
  via this project's `pyproject.toml`, no separate install needed

## Setup

1. From the repo root, sync the whole `uv` workspace (this repo shares one
   `.venv` across `backend-django`/`llm_file_assistant`/`rag_profile_match`;
   syncing just this member with `--package` will uninstall packages the
   other members need, and a bare `uv sync` targets the root project only):
   ```bash
   uv sync --all-packages
   ```
2. Configure environment variables:
   ```bash
   cd rag_profile_match
   cp sample.env .env
   ```
   Edit `.env` and set `OPENROUTER_API_KEY` to your key.
3. Start Qdrant:
   ```bash
   docker compose up -d
   ```
   The REST API is available at `http://localhost:6333`.

## Running the notebook

`resume_rag.py`, `job_matcher.py`, and `metrics.py` are function libraries
with no top-level execution — the pipeline itself runs from
`rag_analysis.ipynb`.

1. From `rag_profile_match/`, launch Jupyter:
   ```bash
   uv run jupyter lab
   ```
   (Or, in VS Code, open `rag_analysis.ipynb` and select this workspace
   member's `.venv` as the kernel — no separate Jupyter server needed.)
2. Open `rag_analysis.ipynb` and run cells top to bottom:
   - **Sections 1–4** (discover resumes, batch-extract metadata, chunk,
     write `extractions.json`/`chunks.json`) are implemented and will run
     end-to-end against `root_dir/resumes/`.
   - **Sections 5–7** (embeddings + Qdrant upsert, job matching, performance
     metrics) are scaffolded — the underlying functions in `resume_rag.py`,
     `job_matcher.py`, and `metrics.py` raise `NotImplementedError` until
     filled in; running those cells will stop at that error until then.
