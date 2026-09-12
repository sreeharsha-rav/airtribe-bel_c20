# Design

`agentic_profile_match` wraps `llm_file_assistant`'s sandboxed filesystem
pattern and `rag_profile_match`'s hybrid RAG retrieval into a single
conversational, multi-round resume-screening agent. It reuses both sibling
projects' *data and logic* (duplicated, not cross-imported — see
[Reuse strategy](#reuse-strategy)) rather than re-solving either problem.

This document is the full architecture (Part A deliverable): the complete
`AgentState` schema and the target graph shape, phase-annotated so it's clear
what Phase 1 actually builds versus what later phases add on top of the same
shape. **Phase 1**, **Phase 2**, and **Phase 3** are designed down to the
node level; **Phase 4** gets its own detailed design pass when we get there.

## Architecture shape: hybrid graph

Two execution models compose, not one:

1. An outer **`StateGraph`** runs the fixed, deterministic screening pipeline
   — auditable, no LLM deciding control flow, matches how `rag_profile_match`
   itself is built (pure functions, `job_matcher`/`metrics` have no agent).
2. Reaching the `Human Feedback Loop` node runs, **once per conversational
   turn**, a stateless tool-calling helper (`create_agent(model,
   tools=TOOLS)`, no checkpointer of its own) for Part B's free-form turns
   ("compare the top 3", "why did John rank higher") — genuinely open-ended
   NL that a fixed graph can't route without hand-written intent
   classification for every phrasing. It is *not* a second, independently
   persisted graph — see [Phase 2](#phase-2--interactivity) for why.

See [State Machine Diagram](#state-machine-diagram) for the full,
consolidated node/edge graph across all phases.

Solid-boundary nodes (`Parse JD` → `Generate Report`) are **Phase 1**: a
single, non-interactive pass that, by default, prints a report and exits
(`END` reached directly, no feedback loop yet). `Human Feedback Loop` is
Phase 2 — a single graph node re-entered via a self-loop edge, not a
hand-off to a separate node or graph. `Deep Analysis`/`Recommendation` are
Phase 3 — two extra nodes, skipped unless the CLI's upfront prompt opted
into full 3-round screening (see [Phase 3](#phase-3--multi-round-screening)).

## State Machine Diagram

The Guidelines' "state machine diagram (visual representation)" deliverable
(Q4, Phase 4) — one definitive graph, all phases, superseding the
incremental per-phase sketches used while designing:

```mermaid
flowchart TD
    CLI["CLI: prompt for JD path\n+ deep_screening_requested? (Phase 3)"] --> START
    START --> A["Parse JD"]
    A -- "path invalid / not found" --> ENDERR(("END\nerror printed"))
    A -- "ok" --> B["Extract Requirements"]
    B --> C["Search Resumes\nwrites round='broad'"]
    C --> D["Rank Candidates\nwrites round='shortlist'"]
    D -- "deep_screening_requested" --> DA["Deep Analysis (Phase 3)\nwrites round='deep_dive'"]
    D -- "not requested" --> E["Generate Report\n(no LLM call)"]
    DA --> REC["Recommendation (Phase 3)\nwrites round='recommendation'"]
    REC --> E
    E --> F{{"Human Feedback Loop (Phase 2)\none interrupt() per turn"}}
    F -- "'exit'/'quit'" --> ENDOK(("END\nsession closed"))
    F -- "'clear', or a normal turn\n(tool-calling helper runs)" --> F

    classDef phase1 fill:#dfe,stroke:#333;
    classDef phase2 fill:#eef,stroke:#333,stroke-dasharray: 4 3;
    classDef phase3 fill:#fed,stroke:#333,stroke-dasharray: 2 2;
    classDef term fill:#fdd,stroke:#333;
    class A,B,C,D,E phase1;
    class F phase2;
    class DA,REC phase3;
    class ENDERR,ENDOK term;
```

Two distinct `END`s are worth calling out explicitly since they're easy to
conflate: `Parse JD`'s error path (bad/missing JD file — a same-turn,
no-conversation exit) versus `Human Feedback Loop`'s `exit`/`quit` path (a
graceful close after however many conversational turns). Once
`matching_agent.py` exists, regenerating this from the real compiled graph
(`graph.get_graph().draw_mermaid()`) is a good way to check the
implementation actually matches this design.

## `AgentState` schema (full, all phases)

| Field | Type | Written by | Phase | Purpose |
|---|---|---|---|---|
| `thread_id` | `str` | CLI entrypoint | 1 | LangGraph checkpointer thread key (one per screening session) |
| `jd_source_path` | `str` | `Parse JD` | 1 | Sandboxed path the JD was read from (Q6: free path input, not a picklist) |
| `jd_text` | `str` | `Parse JD` | 1 | Raw job description text |
| `jd_sections` | `dict[str, str]` | `Extract Requirements` | 1 | `header`/`about_the_role`/`responsibilities`/`must_have_requirements`/`nice_to_have` |
| `must_haves` | `list[str]` | `Extract Requirements` | 1 | Hard-filter bullets |
| `nice_to_haves` | `list[str]` | `Extract Requirements` | 1 | Informational only in Phase 1 (see [Known limitations](#known-limitations--backlog)) |
| `candidate_pool` | `list[dict]` | `Search Resumes` | 1 | Raw RRF hits grouped by resume, pre-filter |
| `match_results` | `list[MatchResult]` | `Rank Candidates` | 1 | Final ranked, must-have-filtered candidates |
| `report` | `str` | `Generate Report` | 1 | Rendered CLI report text (kept in state so Phase 2's conversational agent can reference it as context) |
| `messages` | `Annotated[list[AnyMessage], add_messages]` | `Human Feedback Loop` | 2 | Full conversational record — every human turn, tool call, tool result, and reply. The single source of truth for chat history; no separate log field duplicates it (see Phase 2's [Known limitations](#known-limitations--backlog-1)) |
| `session_ended` | `bool` (default `False`) | `Human Feedback Loop` | 2 | Set when the human types `exit`/`quit`; read by the outer conditional edge to route to `END` instead of looping back |
| `deep_screening_requested` | `bool` | CLI entrypoint | 3 | Collected upfront (alongside `jd_source_path`), before the graph is invoked; the conditional edge after `Rank Candidates` reads it — no second `interrupt()` |
| `round` | `Literal["broad","shortlist","deep_dive","recommendation"]` | outer graph | 3 | Which stage produced the current `match_results` — `"broad"`/`"shortlist"` map to `Search Resumes`/`Rank Candidates`, `"deep_dive"`/`"recommendation"` to the two new Phase 3 nodes |
| `deep_analysis` | `list[DeepAnalysisResult]` | `Deep Analysis` | 3 | Per-candidate strengths/gaps/nice-to-have-coverage, grounded in the *full* resume text |
| `recommendations` | `list[Recommendation]` | `Recommendation` | 3 | Per-candidate verdict (deterministic) + LLM-authored justification |
| `error` | `str \| None` | any node | 1 | Set on a recoverable failure (e.g. JD path not found); short-circuits to `END` in Phase 1 |

Deciding this shape fully now (Q2) means Phase 2/3 only *add* nodes that
read/write already-reserved fields — no retrofitting existing Phase 1 node
return types.

## Reuse strategy

`rag_profile_match` isn't installed as an importable dependency of
`agentic_profile_match` (its modules do bare `import config` / `import
fs_tools`, the same cwd-relative pattern `llm_file_assistant` uses — not
package-qualified), so cross-package Python imports between uv workspace
siblings would be fragile. Instead:

- **Data is shared, code is duplicated.** `agentic_profile_match` points its
  own `config.client` at the *same* running Qdrant (`http://localhost:6333`,
  collection `resume_chunks`) that `rag_profile_match` already populated —
  no reindexing, no separate collection.
- **`fs_tools.py`** is copied over (same sandboxing design as
  `llm_file_assistant`), with `ROOT_DIR` pointed at
  `../rag_profile_match/root_dir` (covers both `jobs/` and `resumes/` —
  Phase 1 only reads `jobs/`, but Phase 2's `compare_candidates` /
  `generate_interview_questions` will want full resume text, not just a
  chunk excerpt, so the sandbox boundary is set once here rather than
  reconfigured later).
- **Duplicate only what the graph actually needs as separate, node-callable
  pieces** (Q4: `Search Resumes` and `Rank Candidates` are two real nodes,
  not one call to `job_matcher.match_job()`):
  - `jd_parser.py` — `split_job_sections`, `extract_must_have_requirements`
    (copied from `job_matcher.py`), plus a new `extract_nice_to_have_requirements`
    (same bullet-parsing logic, pointed at the `nice_to_have` section).
  - `retrieval.py` — `embed_job_description`, `semantic_search`, and the
    embedding-model builders (`build_embedding_model`,
    `build_sparse_embedding_model`, copied from `resume_rag.py` — no
    chunking/indexing code needed here, Phase 1 never writes to Qdrant).
  - `ranking.py` — `keyword_match_score`, `score_and_rank`, `MatchResult`
    (copied from `job_matcher.py`).
  - `matching_agent.py` stays graph/state/node wiring only — `AgentState`,
    the `StateGraph` build, each node function (a thin call into the
    modules above), the checkpointer, and the CLI entrypoint. It imports
    from the sibling modules the same way `llm_file_assistant/main.py`
    imports from `fs_tools.py`.
- **No `docker-compose.yml` of its own.** The one currently scaffolded in
  `agentic_profile_match/` is byte-identical to `rag_profile_match`'s except
  for its named volume — running it would either fail to bind port `6333`
  (already held by `rag_profile_match`'s container) or silently start a
  second, empty Qdrant with no `resume_chunks` collection. **Delete it.**
  Setup instructions instead say: start `rag_profile_match`'s Qdrant first
  (`cd ../rag_profile_match && docker compose up -d`).

## File map

| File | Responsibility | Phase |
|---|---|---|
| `config.py` | Env vars, model names, Qdrant client pointed at the shared instance | 1 |
| `fs_tools.py` | Sandboxed FS tools; `ROOT_DIR` → `../rag_profile_match/root_dir` | 1 |
| `jd_parser.py` | JD section splitting, must-have/nice-to-have bullet extraction (algorithmic) | 1 |
| `retrieval.py` | JD embedding (dense+sparse) + hybrid RRF search against `resume_chunks` | 1 |
| `ranking.py` | Must-have hard filtering, score normalization, `MatchResult` | 1 |
| `matching_agent.py` | `AgentState`, `StateGraph` nodes/edges, checkpointer, CLI entrypoint | 1 (extended in 2, 3) |
| `tools.py` | `search_resumes`, `extract_requirements`, `compare_candidates`, `generate_interview_questions`, `deep_analyze_candidates`, `generate_recommendation` — the inner tool-calling helper's tool belt, plus the shared mutable session container they close over | 2 (+3) |
| `screening.py` | `DeepAnalysisResult`/`Recommendation` schemas, batched full-resume-grounded LLM analysis, deterministic verdict thresholds | 3 |
| `utils.py` | `CustomLogger` (already scaffolded) | 1 |

## Phase 1 — node-by-node spec

### `Parse JD`
- **Input:** a sandboxed file path (Q6: user supplies any path under
  `jobs/`, no picklist), read via `fs_tools.read_file`.
- **Writes:** `jd_text`, `jd_source_path`.
- **Failure path:** path outside the sandbox or not found → `error` is set,
  the node routes straight to `END` and the CLI prints the error. No retry
  loop in Phase 1 — that's conversational territory (Phase 2).

### `Extract Requirements`
- **Input:** `jd_text`.
- **Action:** `jd_parser.split_job_sections` → `jd_sections`;
  `extract_must_have_requirements` → `must_haves`;
  `extract_nice_to_have_requirements` → `nice_to_haves`. Purely algorithmic
  (Q3) — every posting under `rag_profile_match/root_dir/jobs/` already
  follows the same 4-heading format this regex parses correctly.
- **Writes:** `jd_sections`, `must_haves`, `nice_to_haves`.
- **Backlog (Q3):** revisit as an LLM structured-output step (mirroring
  `resume_rag.ResumeFields`) if job postings stop following the fixed
  heading convention.

### `Search Resumes`
- **Input:** `jd_sections` (header + about_the_role + responsibilities —
  must-haves are deliberately excluded from the embedded query text, same
  rationale as `rag_profile_match`: exact requirements are better served by
  keyword filtering than fuzzy similarity).
- **Action:** `retrieval.embed_job_description` → dense+sparse query
  vectors; `retrieval.semantic_search` → RRF-fused hits grouped by resume
  (`max(top_k * 3, 15)` pool size, same over-fetch rationale as
  `job_matcher.match_job` — the must-have filter downstream can shrink the
  pool, so it needs headroom before filtering).
- **Writes:** `candidate_pool`.
- Does **not** consume `must_haves` — kept as a separate, later step.

### `Rank Candidates`
- **Input:** `candidate_pool`, `must_haves`, `nice_to_haves`.
- **Action:** `ranking.keyword_match_score` per candidate against
  `must_haves` (hard filter — any miss excludes the candidate);
  `ranking.score_and_rank` min-max normalizes survivors' RRF scores to
  0–100. Additionally runs the *same* `keyword_match_score` against
  `nice_to_haves` for survivors only, purely for display — this doesn't
  gate or affect `match_score` in Phase 1, it just avoids extracting
  nice-to-haves in the prior node and then never surfacing them anywhere
  (see [Known limitations](#known-limitations--backlog)).
- **Writes:** `match_results` (`MatchResult` list, each carrying which
  nice-to-haves it also happens to satisfy).

### `Generate Report`
- **Input:** `match_results`, `nice_to_haves` overlap, `jd_source_path`.
- **Action:** deterministic `rich`-rendered table (rank, candidate, score,
  matched skills, must-haves satisfied, nice-to-haves present, reasoning,
  best excerpt) — **no LLM call**, matching Q5. Console-only in Phase 1;
  stays manual/on-demand-only permanently (Q3, Phase 4) rather than
  becoming automatic — see [Phase 3](#phase-3--multi-round-screening)'s
  `Generate Report` note.
- **Writes:** `report`. Graph reaches `END`.

### Known limitations / backlog

- **Nice-to-haves are informational only** — extracted and displayed, not
  scored. Whether/how they should influence `match_score` is an explicit
  open question, not decided here.
- **`Extract Requirements` is regex/heading-based**, not LLM-based (Q3). Fine
  while every posting follows the 4-heading convention; revisit with
  structured LLM extraction if that assumption breaks.
- **No standalone Qdrant for this project** (Q2/round 3) — the scaffolded
  `docker-compose.yml` here should be deleted; `rag_profile_match`'s Qdrant
  is the single shared instance both projects read.
- **`InMemorySaver` checkpointer** (Q3/round 1) — a session doesn't survive
  a process restart. Acceptable for Phase 1 (single-shot, no feedback loop
  yet); revisit if a screening session needs to be resumed across restarts.

## Phase 2 — Interactivity

### Overview

`Human Feedback Loop` is one graph node, re-entered via a self-loop edge —
**one node execution per conversational turn**, not a Python loop inside the
node. This matters because of a real LangGraph edge case: when a node
resumes from `interrupt()`, the *entire node function re-runs from the top*
(earlier `interrupt()` calls just replay their cached value instantly). A
node with several `interrupt()` calls in a Python `while` loop would
silently re-execute every earlier turn's side effects — re-invoking the
tool-calling helper, re-printing replies — on every resume. Keeping exactly
one `interrupt()` call, at the very top of the node, with nothing
side-effecting before it, avoids that entirely; the graph's own edges
provide the multi-turn loop instead.

There is no second, independently-persisted graph for "the conversational
agent." `create_agent(model, tools=TOOLS)` is built **without** a
checkpointer and invoked fresh, once, per turn — the outer graph's own
checkpointer/thread already persists `state["messages"]` across turns, so
the inner helper doesn't need to remember anything itself; it just runs one
turn's full tool-calling loop (which can still involve several tool calls
before it replies) and hands back the resulting messages.

```mermaid
sequenceDiagram
    participant CLI
    participant Graph as human_feedback_loop (one node)
    participant Session as shared session container (tools.py)
    participant Inner as create_agent(model, tools=TOOLS) — stateless

    CLI->>Graph: Command(resume=user_text)
    Note over Graph: interrupt() returns user_text (the only interrupt() in this node)
    alt user_text is "exit"/"quit"
        Graph-->>CLI: session_ended=True
    else user_text is "clear"
        Graph-->>CLI: messages wiped, business state untouched
    else normal turn
        Graph->>Session: sync match_results, must_haves,\nnice_to_haves, jd_text, jd_sections, candidate_pool
        Graph->>Inner: invoke({"messages": state.messages + [user_text]})
        Inner->>Session: tool calls read/mutate session in place
        Inner-->>Graph: final messages for this turn
        Graph->>Session: read back (possibly mutated) session
        Graph-->>CLI: state update (messages, match_results, ...)
    end
    Note over CLI,Graph: conditional edge: session_ended? END : human_feedback_loop
```

### `human_feedback_loop` — per-turn spec

1. `interrupt()` — the *only* one in this node, called first — waits for
   `Command(resume=<user text>)` from the CLI's REPL loop.
2. REPL-level commands are handled before anything reaches the tool-calling
   helper (same precedent as `llm_file_assistant/main.py`'s `clear`/`load`/
   `reasoning`): `exit`/`quit` → set `session_ended=True`, return
   immediately (no tool calls this turn). `clear` → wipe `messages`
   (`RemoveMessage(REMOVE_ALL_MESSAGES)`), leave `match_results`/`must_haves`/
   etc. untouched, return without invoking the helper this turn either.
3. Otherwise: copy `match_results`, `must_haves`, `nice_to_haves`, `jd_text`,
   `jd_sections`, `candidate_pool` from `AgentState` into the shared session
   container in `tools.py` that the tool functions close over.
4. Invoke the stateless helper with
   `{"messages": state["messages"] + [HumanMessage(user_text)]}`. It runs
   its own internal loop — model call → any tool calls it decides to make →
   model call again → ... — until it produces a final reply with no more
   tool calls.
5. Read the (possibly mutated) session container back out.
6. Return the `AgentState` update: the turn's new messages appended, and
   `match_results`/`must_haves`/`nice_to_haves`/`jd_text`/`jd_sections`/
   `candidate_pool` set to whatever the session container now holds.
7. Conditional edge: `session_ended` → `END`; otherwise → `human_feedback_loop`
   again (next turn).

The very first entry into this node (from `Generate Report`) seeds
`state["messages"]` with `state["report"]` as an initial message (Q5, round
1) — the human's first free-form turn already has the shortlist in context,
no tool round-trip needed just to "see" what Phase 1 already computed.

### Tool belt (`tools.py`)

The inner helper's `TOOLS` list is `fs_tools`'s existing four
(`list_files`, `read_file`, `search_in_file`, `write_file`) plus four new
ones:

- **`search_resumes(query: str, must_have_keywords: list[str] = [],
  min_experience_years: float | None = None) -> dict`** — `query` is loose
  NL ("candidates with React and 3+ years"), *not* JD-shaped text; the LLM
  itself is responsible for pulling out `must_have_keywords`/
  `min_experience_years` when it decides to call this. Embeds `query` (via
  the same embedding builders `retrieval.py` uses), runs
  `retrieval.semantic_search`, applies `ranking.keyword_match_score`/
  `score_and_rank` using whatever structured filters were supplied (or
  none), and **replaces** the session's `match_results`/`candidate_pool` —
  this is both the ad-hoc search tool and the entire refinement mechanism
  (Q2, round 1): every call overwrites the active shortlist, and the LLM
  narrates the difference from what it saw before, in its own reply.
- **`extract_requirements(jd_text: str) -> dict`** — for a wholesale new JD
  pasted mid-conversation. Calls the same `jd_parser.split_job_sections` +
  `extract_must_have_requirements` + `extract_nice_to_have_requirements`
  Phase 1 uses, overwrites `jd_text`/`jd_sections`/`must_haves`/
  `nice_to_haves` in the session. Typically followed by the model calling
  `search_resumes` next, in the same turn.
- **`compare_candidates(candidate_identifiers: list[str]) -> dict`** —
  read-only. Resolves each identifier by fuzzy match (name substring or
  exact `resume_path`) against the session's *current* `match_results` (Q3,
  round 1 — the model itself is expected to pass names/paths it already saw
  in the report or a prior tool result, not "top N" phrasing for the tool
  to parse). Returns a side-by-side structured comparison (score, matched
  skills, reasoning, excerpts per candidate); an unresolvable identifier
  comes back as a structured "not found, did you mean X" entry rather than
  raising.
- **`generate_interview_questions(candidate_identifier: str) -> dict`** —
  resolves the identifier the same way, then re-reads the candidate's
  *full* resume text via `fs_tools.read_file` (Q4, round 1 — not just the
  1–2 chunks `MatchResult.relevant_excerpts` happened to keep) before an
  LLM call drafts questions targeting gaps and must-haves.

### Known limitations / backlog

- **No cross-session persistence.** `InMemorySaver` means the whole
  thread — Phase 1's pipeline result *and* every chat turn — disappears
  when the process exits. Revisit only if "resume a screening session
  tomorrow" becomes an actual requirement.
- **`search_resumes` always re-embeds and re-queries Qdrant from scratch**
  (~0.6s per `rag_profile_match`'s measured latency), even for a pure
  must-have tweak that doesn't change the descriptive query text. Fine at
  this corpus size; caching `candidate_pool` and only re-ranking on a
  criteria-only change is a possible later optimization, not designed now.
- **Identifier resolution is plain fuzzy substring matching**, not a
  specified algorithm — two candidates matching the same substring should
  surface as a disambiguation question rather than an arbitrary pick, but
  the exact matching logic is an implementation detail, not an architecture
  decision.

## Phase 3 — Multi-Round Screening

### Overview

The brief's "Initial screen (top 10 from 100) → Second round (deep analysis
of top 10) → Final round (hire/no-hire)" maps onto the pipeline as **two new
outer-graph nodes**, `Deep Analysis` and `Recommendation`, appended after
`Rank Candidates` — not a re-run of `Search Resumes`/`Rank Candidates` at
different fidelity. `round`'s four literals now correspond one-to-one with
pipeline stages: `Search Resumes` produces `"broad"`, `Rank Candidates`
produces `"shortlist"`, `Deep Analysis` produces `"deep_dive"`,
`Recommendation` produces `"recommendation"`.

These two nodes are **opt-in, not automatic** (Q1): the CLI asks "run full
3-round screening? [y/N]" *upfront*, alongside the JD path prompt, before
the graph is invoked at all — `deep_screening_requested` goes into the
initial state, and the conditional edge after `Rank Candidates` reads it.
This keeps Phase 1's fast, no-LLM-call default path intact, since Deep
Analysis + Recommendation are meaningfully more expensive (one LLM call per
shortlisted candidate, per node — roughly 2×10 = 20 extra LLM round-trips
for a 10-candidate shortlist) than everything before them. No second
`interrupt()` is introduced — the gate is a plain upfront input, consistent
with Phase 2's invariant of exactly one pause point in the whole graph.

The same underlying functions these nodes call are also exposed as two more
Phase 2 tools (`deep_analyze_candidates`, `generate_recommendation`) —
following the precedent already set by `search_resumes`/`Search Resumes` —
so a user can ask for a deep dive or a verdict on specific candidates
conversationally later, without re-running the whole pipeline.

### `Deep Analysis`

- **Input:** `match_results` (the shortlist survivors), `must_haves`,
  `nice_to_haves`.
- **Action:** for each candidate, re-reads the *full* resume text via
  `fs_tools.read_file` (not just `MatchResult.relevant_excerpts`'s 1–2
  stored chunks — Q2) and makes one structured-output LLM call (mirroring
  `resume_rag.ResumeFields`'s pattern: `.with_structured_output`, batched via
  `.batch()` with `return_exceptions=True` and per-item error isolation,
  same as `resume_rag.extract_fields_batch`) producing a `DeepAnalysisResult`:
  `candidate_name`, `resume_path`, `strengths: list[str]`,
  `gaps: list[str]`, `nice_to_have_coverage: list[str]` (which
  `nice_to_haves` the full resume actually supports — a refinement of
  Phase 1's chunk-level overlap check), and `must_have_discrepancy: str |
  None` (set when the full resume text *contradicts* the original
  chunk-based must-have check — this is what gives the round real teeth,
  rather than just producing decorative prose).
- **Writes:** `deep_analysis`, `round = "deep_dive"`.

### `Recommendation`

- **Input:** `match_results`, `deep_analysis`.
- **Action:** the verdict **label** is computed deterministically (Q3) —
  starting-default thresholds, tunable later as a plain config constant:

  | Verdict | Rule |
  |---|---|
  | Strong Hire | `match_score ≥ 80` and no `must_have_discrepancy` |
  | Hire | `match_score` 60–79 and no `must_have_discrepancy` |
  | Borderline | `match_score` 40–59, **or** 60+ with a `must_have_discrepancy` (automatic one-tier downgrade) |
  | No Hire | `match_score < 40`, or an already-Borderline candidate with a `must_have_discrepancy` |

  One LLM call per candidate then writes the justification prose, grounded
  in `deep_analysis`'s `strengths`/`gaps`/`must_have_discrepancy` — the
  model explains an already-decided verdict, it doesn't choose it. The same
  structured-output schema also carries `improvement_suggestions:
  list[str]`, populated only when the verdict is `Borderline` (Q1, Phase 4)
  — nearly free, since the call and the grounding context already exist for
  the justification; no second call.
- **Writes:** `recommendations` (`Recommendation`: `candidate_name`,
  `resume_path`, `verdict`, `justification`,
  `improvement_suggestions: list[str]`), `round = "recommendation"`.
- `Generate Report` (unchanged node, extended behavior — still **no LLM
  call**, Q2/Phase 4): when `deep_screening_requested`, the rendered report
  adds a per-candidate section for `deep_analysis` (strengths/gaps/nice-to-have
  coverage) and `recommendations` (verdict, justification, and improvement
  suggestions when present) — every word comes from already-computed
  structured fields, nothing newly generated at render time. When
  `deep_screening_requested` is `False`, it's exactly Phase 1's plain ranked
  table. `write_file`-based persistence stays manual/on-demand only (Q3,
  Phase 4) — the human can ask the conversational agent to save a copy via
  the existing `write_file` tool; the report is never auto-persisted.

### Corpus growth (Q4)

31 resumes isn't enough to make "top 10 from 100" or a hire/no-hire
recommendation demo convincing — most postings' ground truth has only 1–7
true matches, so a "deep dive on the top 10" round has little real spread to
show. Since Phase 1 (Q2, round 1) committed to sharing `rag_profile_match`'s
exact Qdrant collection rather than forking the dataset, growing the corpus
is necessarily a **cross-project** change (Q2, this phase):

1. Add synthetic resumes (across departments, a mix of strong/weak/borderline
   fits against the existing 6 job postings) into
   `rag_profile_match/root_dir/resumes/`.
2. Re-run `rag_profile_match/rag_analysis.ipynb`'s indexing cells so the new
   resumes' chunks land in the same `resume_chunks` Qdrant collection.
3. Update `rag_analysis.ipynb`'s hand-labeled `JOB_GROUND_TRUTH` to include
   the new candidates — otherwise `rag_profile_match`'s own already-reported
   precision/recall numbers go stale.

Actual resume authoring is deferred to implementation time, not part of this
design pass.

### Known limitations / backlog

- **Verdict thresholds are a starting default**, not empirically tuned —
  expect to adjust the cutoffs once real Deep Analysis output exists to
  sanity-check against.
- **`must_have_discrepancy` is a single optional string**, not a structured
  list — if full-resume re-checking ever finds more than one contradiction
  worth surfacing, this will need to become a list before it silently drops
  information.
- **Deep Analysis + Recommendation double the corpus-growth stakes**: with
  more resumes now feeding a per-candidate LLM call each, per-run cost/latency
  scales with shortlist size — still bounded by `top_k` (default 10), so this
  stays bounded even as the underlying corpus grows.

## Phase 4 — Polish

Lighter than Phases 1–3: no new execution-model decisions, just what the
deliverables actually contain.

- **Improvement suggestions** (Q1) are a field on `Recommendation`'s
  existing per-candidate structured-output call
  (`improvement_suggestions: list[str]`), populated only for `Borderline`
  verdicts — see [Phase 3's `Recommendation` spec](#recommendation).
- **`Generate Report` stays pure rendering** (Q2) — richer per-candidate
  sections when Phase 3 data exists, but still zero LLM calls in this node;
  see the updated spec under [Phase 1](#generate-report) and
  [Phase 3](#recommendation).
- **No automatic report persistence** (Q3) — `write_file` stays a
  human-invoked action via the conversational agent, never an automatic
  side effect of `Generate Report`.
- **One consolidated state machine diagram** (Q4) — see
  [State Machine Diagram](#state-machine-diagram), which now supersedes the
  incremental per-phase flowcharts used while designing.
- **Test scenarios** (Q5) are documented conversation transcripts, not
  automated tests (no test infrastructure exists anywhere in this workspace
  yet — introducing one, plus an LLM-mocking strategy, is a separate
  decision from "what are the 5+ flows"). Written out in
  [`TEST_SCENARIOS.md`](TEST_SCENARIOS.md): the 8 flows agreed in Phase 4's
  grilling round, covering the happy path, every Phase 2 tool, the full
  Phase 3 escalation, and the error/edge cases (bad JD path, ambiguous
  candidate identifier, `exit`/`clear`).

### Known limitations / backlog

- **`improvement_suggestions` only exists for `Borderline` verdicts** —
  `No Hire` candidates get a justification but no suggestions; revisit if a
  use case for "why this candidate was rejected and what would need to
  change" emerges.
- **The state diagram is hand-drawn, not yet verified against real code**
  (nothing has been implemented). Once `matching_agent.py` exists, diffing
  it against `graph.get_graph().draw_mermaid()`'s actual output is worth
  doing before trusting this document over the code.
- **Test scenarios are a QA script, not a safety net** — nothing prevents a
  future change from silently breaking one of the 8 flows; if that becomes
  a real pain point, revisit automating some of them (and, at that point,
  decide how to handle LLM non-determinism — real model calls in tests vs.
  a mocking/recording strategy).
