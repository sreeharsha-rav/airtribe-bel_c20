# Agentic Profile Matching

A conversational, multi-round resume-screening agent: a single LangGraph
`StateGraph` that combines `llm_file_assistant`'s sandboxed filesystem tools
and a `rag_profile_match`-style hybrid dense+sparse RAG retrieval pipeline
into one screening flow with a human-in-the-loop chat phase on top. Code
is duplicated from both sibling projects (not cross-imported — see
`docs/DESIGN.md`'s [Reuse strategy](docs/DESIGN.md#reuse-strategy)); data
is fully independent — this project owns its own Qdrant instance and its
own mock corpus (`.txt`/`.md` only), not `rag_profile_match`'s.

**Implementation status:** Phases 1–4 are all implemented —

- **Phase 1** — a deterministic pipeline (`Parse JD` → `Extract
  Requirements` → `Search Resumes` → `Rank Candidates` → `Generate Report`),
  no LLM call anywhere in it.
- **Phase 2** — `Human Feedback Loop`: a single graph node, re-entered via a
  self-loop edge, that hands each conversational turn to a stateless
  tool-calling agent (search/refine, compare candidates, draft interview
  questions, screen a brand-new JD, ...).
- **Phase 3** — opt-in multi-round screening: `Deep Analysis` (full-resume-
  grounded strengths/gaps per candidate) and `Recommendation` (a
  deterministic hire/no-hire verdict + LLM justification), gated behind an
  upfront CLI prompt.
- **Phase 4** — polish: the folder layout below, `scripts/smoke_test.py`
  (mocked plumbing/regression checks), `docs/TEST_SCENARIOS.md` (8 manual
  conversation-flow specs), and — most recently — this project's own
  `data/` corpus, own Qdrant (`docker-compose.yml`), and own indexing
  pipeline (`indexing.py` + `scripts/reindex.py`), replacing the earlier
  design of reading `rag_profile_match`'s shared Qdrant/corpus.

See `docs/DESIGN.md` for the full design rationale, `docs/AGENT_ARCHITECTURE.md`
for a step-by-step technical reference (state/nodes/edges/tools/checkpointing),
and `docs/TEST_SCENARIOS.md` for worked example conversations.

## Project layout

```
agentic_profile_match/
├── config.py, fs_tools.py       # env/Qdrant config; sandboxed FS tools (ROOT_DIR -> data/, .txt/.md only)
├── jd_parser.py, retrieval.py,  # JD section/requirement parsing; hybrid RRF retrieval;
│   ranking.py                   #   must-have filtering + score normalization (Phase 1)
├── indexing.py                  # metadata extraction, chunking, embedding+upsert -- this project's own indexing pipeline
├── screening.py                 # Deep Analysis / Recommendation: batched LLM analysis + deterministic verdicts (Phase 3)
├── tools.py                     # the conversational agent's tool belt + shared session container (Phase 2/3)
├── matching_agent.py            # AgentState, the StateGraph itself: nodes, edges, checkpointer
├── prompts/                     # system prompt strings, kept separate from the wiring/logic that uses them
├── cli/main.py                  # the actual entrypoint: upfront prompts + the interrupt()/resume chat loop
├── scripts/                     # smoke_test.py (mocked regression checks); reindex.py (runs indexing.py's pipeline)
├── docker-compose.yml           # this project's own Qdrant (host port 6350, independent of rag_profile_match's 6333)
├── data/                        # jobs/ (3 postings) + resumes/<dept>/ (12 resumes) -- the mock corpus, .txt/.md only
└── docs/                        # DESIGN.md, AGENT_ARCHITECTURE.md, TEST_SCENARIOS.md
```

No `utils/` folder — `utils.py`'s single small `CustomLogger` class doesn't
warrant one.

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Docker (to run this project's own Qdrant instance)
- An [OpenRouter](https://openrouter.ai/) API key (embeddings + chat model)

## Setup

1. From the repo root, sync the whole `uv` workspace (this repo shares one
   `.venv` across `backend-django`/`llm_file_assistant`/`rag_profile_match`/
   `agentic_profile_match`; a bare `uv sync` targets only the root project,
   and `--package` would uninstall packages the other members need):
   ```bash
   uv sync --all-packages
   ```
2. Configure environment variables:
   ```bash
   cd agentic_profile_match
   cp sample.env .env
   ```
   Edit `.env` and set `OPENROUTER_API_KEY` to your key.
3. Start this project's own Qdrant instance (host port `6350` — a
   different port than `rag_profile_match`'s `6333`, so both can run at
   once without conflict):
   ```bash
   docker compose up -d
   ```
4. Index the mock corpus (`data/jobs/`, `data/resumes/<dept>/`) into it —
   idempotent, safe to re-run after editing/adding resumes:
   ```bash
   uv run python scripts/reindex.py
   ```
   Verify it worked:
   ```bash
   curl http://localhost:6350/collections/resume_chunks
   ```

## Running it

From `agentic_profile_match/`:

```bash
uv run python cli/main.py
```

You'll be prompted for a JD path (e.g. `jobs/senior_backend_engineer.txt`,
`jobs/data_scientist.txt`, or `jobs/product_marketing_manager.md` — all
relative to `data/`) and whether to run full 3-round screening. The
pipeline runs once, prints a ranked shortlist (plus, if you opted in, a
per-candidate deep analysis and verdict), then drops into a chat loop —
ask it to compare candidates, refine the search, draft interview questions,
or paste in a whole new job description. Type `clear` to wipe chat history
without losing the shortlist, `exit`/`quit` to end the session.

## Testing

```bash
uv run python scripts/smoke_test.py
```

Runs a mocked regression check (no live Qdrant/OpenRouter calls) across all
three phases: graph routing, checkpointing/interrupt behavior, must-have
filtering, verdict thresholds, and per-item error isolation in the batched
Phase 3 calls. It does **not** verify real model behavior — for that, work
through `docs/TEST_SCENARIOS.md`'s 8 sample conversation flows (happy path,
every Phase 2 tool, full 3-round screening, edge cases) against a real
`OPENROUTER_API_KEY` and the indexed corpus; e.g. the first flow is just
`jobs/senior_backend_engineer.txt` through `cli/main.py` with 3-round
screening declined.

Both layers have been run end-to-end against a live OpenRouter key and
this project's own indexed Qdrant collection, including the full 3-round
screening path across all three sample job postings.
