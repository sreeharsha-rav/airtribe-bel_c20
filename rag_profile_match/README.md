# RAG Based Profile Matching

A two-part RAG pipeline that matches candidate resumes to a job description.
**`resume_rag.py`** ingests resumes into a vector store; **`job_matcher.py`**
takes a job description and returns ranked, scored candidate matches with
reasoning.

## Design

### Document Processing (`resume_rag.py`)

- **Loading** — resumes (`.txt`, `.docx`, `.pdf`) are read from `root_dir/resumes/`
  using the sandboxed filesystem tools carried over from the `llm_file_assistant`
  project (Milestone 1).
- **Chunking** — resumes follow a consistent section structure (Summary, Skills,
  Experience, Education), so chunking is section-aware rather than fixed-size,
  keeping each section intact as its own chunk.
- **Embeddings** — generated via OpenRouter (chat model also served through
  OpenRouter, same `OPENROUTER_API_KEY`).
- **Vector store** — [Qdrant](https://qdrant.tech/), run locally via
  `docker-compose.yml`. Each chunk is stored with metadata for filtering.
- **Metadata extraction** — Name, Skills, Experience (years), and Education are
  extracted per resume and stored alongside embeddings.

### Job Matching (`job_matcher.py`)

- **Semantic search** — the job description is embedded and used to retrieve
  the top-K (K=10) most similar resume chunks from Qdrant.
- **Hybrid search** — semantic similarity is combined with keyword matching for
  critical/must-have skills (e.g. required tools, "5+ years Python").
- **Scoring & ranking** — matches are scored on a 0–100 scale, with reasoning
  describing which resume sections drove the match, then filtered against any
  must-have requirements.
- **Output** — a JSON report per job description, listing top matches with
  `candidate_name`, `resume_path`, `match_score`, `matched_skills`,
  `relevant_excerpts`, and `reasoning`.

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Docker (to run Qdrant locally)
- An [OpenRouter](https://openrouter.ai/) API key (used for both embeddings and
  chat/reasoning models)

## Setup

1. From the repo root, sync dependencies for this workspace member:
   ```bash
   uv sync
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

## Running

1. Ingest resumes into the vector store:
   ```bash
   uv run resume_rag.py
   ```
   Reads and chunks every resume under `root_dir/resumes/`, extracts metadata,
   and upserts embeddings into Qdrant.
2. Match resumes against a job description:
   ```bash
   uv run job_matcher.py
   ```
   Embeds the job description, retrieves and scores candidate matches, and
   prints the JSON match report.
