# Agentic Profile Matching

A conversational, multi-round resume-screening agent: a single LangGraph
`StateGraph` that combines `llm_file_assistant`'s sandboxed filesystem tools
and `rag_profile_match`'s hybrid dense+sparse RAG retrieval into one
screening pipeline with a human-in-the-loop chat phase on top. Both sibling
projects' *logic* is duplicated here (not cross-imported — see
`docs/DESIGN.md`'s [Reuse strategy](docs/DESIGN.md#reuse-strategy)); their
*data* (the Qdrant `resume_chunks` collection, `root_dir/jobs/` and
`root_dir/resumes/`) is shared, not duplicated.

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
  (mocked plumbing/regression checks), and `docs/TEST_SCENARIOS.md` (8
  manual conversation-flow specs for exercising real model behavior).

See `docs/DESIGN.md` for the full design rationale, `docs/AGENT_ARCHITECTURE.md`
for a step-by-step technical reference (state/nodes/edges/tools/checkpointing),
and `docs/TEST_SCENARIOS.md` for worked example conversations.

## Project layout

```
agentic_profile_match/
├── config.py, fs_tools.py       # env/Qdrant config; sandboxed FS tools (ROOT_DIR -> ../rag_profile_match/root_dir)
├── jd_parser.py, retrieval.py,  # JD section/requirement parsing; hybrid RRF retrieval;
│   ranking.py                   #   must-have filtering + score normalization (Phase 1)
├── screening.py                 # Deep Analysis / Recommendation: batched LLM analysis + deterministic verdicts (Phase 3)
├── tools.py                     # the conversational agent's tool belt + shared session container (Phase 2/3)
├── matching_agent.py            # AgentState, the StateGraph itself: nodes, edges, checkpointer
├── prompts/                     # system prompt strings, kept separate from the wiring/logic that uses them
├── cli/main.py                  # the actual entrypoint: upfront prompts + the interrupt()/resume chat loop
├── scripts/smoke_test.py        # mocked regression checks (no live API) -- run before trusting a change
└── docs/                        # DESIGN.md, AGENT_ARCHITECTURE.md, TEST_SCENARIOS.md
```

No `utils/` folder — `utils.py`'s single small `CustomLogger` class doesn't
warrant one. No `data/` folder — `root_dir/` is intentionally shared with
`rag_profile_match`, not duplicated locally.

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Docker (to run the shared Qdrant instance)
- An [OpenRouter](https://openrouter.ai/) API key (embeddings + chat model)
- **`rag_profile_match`'s Qdrant collection must already be populated**
  (`resume_chunks`) — this project reads it, it never writes/reindexes it.
  If it's empty, run `rag_profile_match/rag_analysis.ipynb`'s indexing cells
  first.

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
3. Start the shared Qdrant instance from `rag_profile_match` (this project
   has no `docker-compose.yml` of its own — see `docs/DESIGN.md`'s
   [Reuse strategy](docs/DESIGN.md#reuse-strategy) for why):
   ```bash
   cd ../rag_profile_match && docker compose up -d && cd ../agentic_profile_match
   ```
   Verify the collection exists and has points:
   ```bash
   curl http://localhost:6333/collections/resume_chunks
   ```

## Running it

From `agentic_profile_match/`:

```bash
uv run python cli/main.py
```

You'll be prompted for a JD path (e.g. `jobs/senior_backend_engineer.txt`,
relative to `root_dir/`) and whether to run full 3-round screening. The
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
`OPENROUTER_API_KEY` and the populated `resume_chunks` collection; e.g. the
first flow is just `jobs/senior_backend_engineer.txt` through
`cli/main.py` with 3-round screening declined.

Both layers have been run end-to-end against a live OpenRouter key and a
populated Qdrant collection at least once, including the full 3-round
screening path.
