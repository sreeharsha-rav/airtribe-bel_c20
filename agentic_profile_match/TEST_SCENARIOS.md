# Test Scenarios

Eight conversation flows covering every phase's design decisions, as
documented behavioral specs (not automated tests — see
[`DESIGN.md`'s Phase 4](DESIGN.md#phase-4--polish) for why). Each is meant
to be run manually against the real implementation once it exists, checking
the "Expect" line against actual behavior. All reference the same running
example: `jobs/senior_backend_engineer.txt` against the shared
`rag_profile_match` resume corpus, unless noted otherwise.

## 1. Happy path — single-shot screen, no deep screening

**Setup:** CLI prompts for a JD path → `jobs/senior_backend_engineer.txt`.
CLI prompts "run full 3-round screening? [y/N]" → `N`.

**Expect:** `Parse JD` → `Extract Requirements` → `Search Resumes` →
`Rank Candidates` → conditional edge skips `Deep Analysis`/`Recommendation`
(`deep_screening_requested=False`) → `Generate Report` prints a plain ranked
table (rank, candidate, score, matched skills, must-haves satisfied,
nice-to-haves present, reasoning, best excerpt) — no per-candidate deep
analysis or verdict sections. Graph then enters `Human Feedback Loop`,
paused at its one `interrupt()`, waiting for the first turn.

## 2. Post-report Q&A — `compare_candidates`

**Setup:** continues from Scenario 1's session.

**Turn:** *"Why did Alice rank higher than the other backend candidates?"*

**Expect:** the tool-calling helper calls
`compare_candidates(candidate_identifiers=[...])` with names it read off
`state["report"]` (already seeded into context — no tool call needed just
to "see" the shortlist). Returns a structured side-by-side comparison
(score, matched skills, reasoning, excerpts per candidate). The reply
explains the ranking using that data, not invented detail. Session stays
open (`session_ended` still `False`).

**Edge check:** if the human names someone not in the current
`match_results` (e.g. a misspelled name), `compare_candidates` returns a
structured "not found, did you mean X" entry for that identifier — the
reply should surface that, not silently guess or fabricate a comparison.

## 3. Iterative refinement — adjusting criteria mid-conversation

**Turn:** *"Actually, also require AWS experience."*

**Expect:** the helper calls `search_resumes(query=..., must_have_keywords=
[..., "aws"], min_experience_years=...)`, carrying forward the earlier
criteria plus the new one. This **replaces** `match_results`/
`candidate_pool` entirely (not a delta/patch). The reply narrates what
changed — who dropped off, who moved up — by comparing this turn's tool
output against what it said in the previous turn, not via any separate
diff-computation.

## 4. Ad-hoc exploratory query, unrelated to the active JD

**Turn:** *"Forget the current role for a second — find me candidates with
React and 3+ years experience."*

**Expect:** `search_resumes(query="React, 3+ years experience",
must_have_keywords=["react"], min_experience_years=3.0)` is called — a
loose NL query, not JD-shaped text. **Design consequence worth explicitly
checking:** this call also **overwrites** the active job's `match_results`/
`candidate_pool`, same as any other `search_resumes` call (Q2, Phase 2
round 1 — one search tool, always mutates the active shortlist). A
follow-up question about the *original* backend-engineer shortlist should
no longer see it unless the human re-establishes it (e.g. re-pasting the
JD, or asking to re-run the original search). Confirm this is what actually
happens, not a design bug being silently patched around at implementation
time.

## 5. `generate_interview_questions`

**Turn:** *"Give me some interview questions for Alice Chen."*

**Expect:** the helper resolves "Alice Chen" against current
`match_results`, then calls
`generate_interview_questions(candidate_identifier="Alice Chen")`. The tool
re-reads the candidate's **full** resume text via `fs_tools.read_file` (not
just the 1–2 chunks in `relevant_excerpts`), then drafts questions
targeting gaps/must-haves. Confirm at least one drafted question references
something *outside* the excerpts already shown in the report — proof the
full-resume read is actually being used, not just re-summarizing what was
already visible.

## 6. A brand-new JD pasted mid-conversation

**Turn:** *"Actually, let's screen for this role instead:"* followed by the
full text of `jobs/product_marketing_manager.txt` pasted directly into the
chat.

**Expect:** the helper calls `extract_requirements(jd_text=<pasted text>)`
— overwrites `jd_text`/`jd_sections`/`must_haves`/`nice_to_haves` in the
shared session — then, in the same turn, calls `search_resumes(...)` against
the new JD's descriptive prose. The reply presents a shortlist for the
*new* role. Confirm the outer graph's `Parse JD`/`Search Resumes`/
`Rank Candidates` nodes are never re-entered — this all happens through
Phase 2 tools acting on the same shared session (Q4, Phase 2 round 2).

## 7. Full 3-round screening, including a Borderline verdict

**Setup:** CLI prompts "run full 3-round screening? [y/N]" → `Y`
(`deep_screening_requested=True`).

**Expect:** after `Rank Candidates`, the graph runs `Deep Analysis` (one
full-resume-grounded structured-output call per shortlisted candidate,
producing `strengths`/`gaps`/`nice_to_have_coverage`/
`must_have_discrepancy`) then `Recommendation` (deterministic verdict from
the threshold table, plus one LLM call for justification —
`improvement_suggestions` populated only where the verdict is
`Borderline`). `Generate Report` renders all of it: verdict, justification,
and — for at least one candidate landing in the 40–59 score band, or 60+
with a `must_have_discrepancy` — visible improvement suggestions. Confirm a
`Strong Hire`/`Hire` candidate's section has **no** `improvement_suggestions`
(field only appears for `Borderline`).

## 8. Edge cases

- **8a — bad JD path:** CLI prompts for a JD path; supply a nonexistent
  file (`jobs/does_not_exist.txt`) or a path attempting to escape the
  sandbox. Expect: `Parse JD` sets `error`, routes straight to `END`, the
  CLI prints the error, the process exits — `Human Feedback Loop` is never
  reached, no interrupt ever fires.
- **8b — ambiguous/missing candidate identifier:** in the feedback loop,
  ask to compare a name not present in the current shortlist (e.g. *"compare
  Bob and Alice"* when there's no Bob). Expect: `compare_candidates` returns
  a "not found, did you mean X" entry for "Bob"; the reply surfaces that
  rather than fabricating a comparison or silently dropping him.
- **8c — `clear`:** type `clear`. Expect: `messages` is wiped
  (`RemoveMessage(REMOVE_ALL_MESSAGES)`), but `match_results`/`must_haves`/
  etc. are untouched — no tool call happens this turn, and the next turn's
  reply should still reflect the *same* active shortlist as before `clear`,
  just with no memory of the prior chat.
- **8d — `exit`:** type `exit`. Expect: `session_ended=True` is set, the
  node returns immediately with no tool call, the conditional edge routes
  to `END`, and the CLI process exits gracefully.
