"""Mocked regression smoke test for matching_agent's compiled graph and
tools.py's conversational tools -- no live Qdrant/OpenRouter calls, no test
framework. Formalizes the checks used while building Phases 1-3 into one
re-runnable script.

This is a plumbing/regression check, not a substitute for docs/TEST_SCENARIOS.md:
it verifies the graph wiring, routing, checkpointing, and deterministic logic
behave as designed with retrieval/LLM calls stubbed out. It does NOT verify
real model behavior (tool-calling quality, structured-output accuracy) --
that needs a working OPENROUTER_API_KEY and the manual conversation flows in
docs/TEST_SCENARIOS.md.

Run from agentic_profile_match/: `uv run python scripts/smoke_test.py`.
Exits non-zero on any failed check.
"""

import sys
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain.messages import AIMessage, HumanMessage
from langgraph.types import Command

import matching_agent
import tools
from ranking import MatchResult
from screening import DeepAnalysisOutput, DeepAnalysisResult, Recommendation, RecommendationOutput, compute_verdict
from screening import deep_analyze_candidates, generate_recommendations

FAILURES: list[str] = []


def check(label: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        FAILURES.append(label)


MARIA_HIT = {
    "file_path": "resumes/engineering/backend_maria.txt",
    "metadata": {
        "file_path": "resumes/engineering/backend_maria.txt",
        "candidate_name": "Maria Kowalski",
        "skills": ["python", "django", "postgresql", "aws", "docker", "kubernetes"],
        "total_experience_years": 7.0,
    },
    "score": 0.9,
    "excerpts": ["7 years of backend engineering with Python and Django."],
}
KAVYA_HIT = {
    "file_path": "resumes/engineering/backend_junior_kavya.txt",
    "metadata": {
        "file_path": "resumes/engineering/backend_junior_kavya.txt",
        "candidate_name": "Kavya Reddy",
        "skills": ["python", "flask"],
        "total_experience_years": 1.5,
    },
    "score": 0.4,
    "excerpts": ["1.5 years junior backend developer."],
}


class FakeConversationalAgent:
    """Stands in for create_agent(model, tools=TOOLS) -- returns a canned
    reply with no tool call, so Phase 2's turn-taking can be exercised
    without a real model.
    """

    def invoke(self, payload):
        messages = payload["messages"]
        return {"messages": messages + [AIMessage(content="Maria ranked highest on RRF score and satisfied every must-have.")]}


def test_phase1_happy_path() -> None:
    print("\n=== Phase 1: happy path ===")
    graph = matching_agent.build_graph()
    with patch("matching_agent.embed_job_description", return_value={"dense": [], "sparse": {"indices": [], "values": []}}), \
         patch("matching_agent.semantic_search", return_value=[MARIA_HIT, KAVYA_HIT]):
        thread_id = str(uuid.uuid4())
        state = graph.invoke(
            {"thread_id": thread_id, "jd_source_path": "jobs/senior_backend_engineer.txt", "deep_screening_requested": False},
            {"configurable": {"thread_id": thread_id}},
        )
    check("no error", state.get("error") is None)
    check("Kavya filtered out by must-have hard filter", len(state["match_results"]) == 1)
    check("Maria is the survivor", state["match_results"][0].candidate_name == "Maria Kowalski")
    check("round == 'shortlist' (deep screening not requested)", state.get("round") == "shortlist")
    check("report rendered", "Candidate Shortlist" in state["report"])
    check("paused at human_feedback_loop's interrupt()", "__interrupt__" in state)
    check("first message seeded with the report", len(state["messages"]) == 1 and isinstance(state["messages"][0], AIMessage))


def test_phase1_error_paths() -> None:
    print("\n=== Phase 1: error paths ===")
    graph = matching_agent.build_graph()

    thread_id = str(uuid.uuid4())
    state = graph.invoke(
        {"thread_id": thread_id, "jd_source_path": "jobs/does_not_exist.txt"},
        {"configurable": {"thread_id": thread_id}},
    )
    check("missing JD file sets error", bool(state.get("error")))
    check("missing JD file never reaches human_feedback_loop", "__interrupt__" not in state)

    thread_id2 = str(uuid.uuid4())
    state2 = graph.invoke(
        {"thread_id": thread_id2, "jd_source_path": "../../etc/passwd"},
        {"configurable": {"thread_id": thread_id2}},
    )
    check("sandbox-escaping path rejected", bool(state2.get("error")))

    with patch("matching_agent.embed_job_description", return_value={"dense": [], "sparse": {"indices": [], "values": []}}), \
         patch("matching_agent.semantic_search", return_value=[KAVYA_HIT]):
        thread_id3 = str(uuid.uuid4())
        state3 = graph.invoke(
            {"thread_id": thread_id3, "jd_source_path": "jobs/senior_backend_engineer.txt"},
            {"configurable": {"thread_id": thread_id3}},
        )
    check("no qualifying candidates -> empty match_results, no crash", state3["match_results"] == [])
    check("empty-shortlist report message rendered", "No candidates satisfied" in state3["report"])


def test_phase2_conversation_turns() -> None:
    print("\n=== Phase 2: Human Feedback Loop turns ===")
    graph = matching_agent.build_graph()
    with patch("matching_agent.embed_job_description", return_value={"dense": [], "sparse": {"indices": [], "values": []}}), \
         patch("matching_agent.semantic_search", return_value=[MARIA_HIT]), \
         patch("matching_agent.get_conversational_agent", return_value=FakeConversationalAgent()):

        thread_id = str(uuid.uuid4())
        thread_config = {"configurable": {"thread_id": thread_id}}
        state = graph.invoke(
            {"thread_id": thread_id, "jd_source_path": "jobs/senior_backend_engineer.txt"},
            thread_config,
        )

        seen = len(state["messages"])
        state = graph.invoke(Command(resume="Why did Alice rank higher?"), thread_config)
        new_messages = state["messages"][seen:]
        check("turn appended a HumanMessage + AIMessage", len(new_messages) == 2 and isinstance(new_messages[0], HumanMessage))
        check("session still open after a normal turn", state.get("session_ended") is False)

        state = graph.invoke(Command(resume="clear"), thread_config)
        check("'clear' wipes messages", state["messages"] == [])
        check("'clear' leaves business state untouched", len(state["match_results"]) == 1)

        state = graph.invoke(Command(resume="exit"), thread_config)
        check("'exit' ends the session", state.get("session_ended") is True)
        check("'exit' reaches END (no further interrupt)", "__interrupt__" not in state)


def test_phase2_tools() -> None:
    print("\n=== Phase 2: conversational tools ===")
    tools.session.match_results = [
        MatchResult(candidate_name="Maria Kowalski", resume_path="resumes/engineering/backend_maria.txt", match_score=100.0, matched_skills=["python"], reasoning="..."),
        MatchResult(candidate_name="Devon Okafor", resume_path="resumes/engineering/fullstack_devon.md", match_score=90.0, matched_skills=["python"], reasoning="..."),
    ]

    result = tools.compare_candidates.invoke({"candidate_identifiers": ["Maria Kowalski", "Bob Nobody", "Devon"]})
    comparisons = {c["identifier"]: c for c in result["comparisons"]}
    check("exact/substring match resolves", comparisons["Maria Kowalski"]["found"] and comparisons["Devon"]["found"])
    check("unresolvable identifier reports not-found, doesn't raise", comparisons["Bob Nobody"]["found"] is False)

    gq = tools.generate_interview_questions.invoke({"candidate_identifier": "Nobody"})
    check("generate_interview_questions not-found path short-circuits before any LLM call", gq["found"] is False)


def test_phase3_verdict_thresholds() -> None:
    print("\n=== Phase 3: verdict threshold table ===")
    check("Strong Hire: score>=80, no discrepancy", compute_verdict(85, None) == "Strong Hire")
    check("Hire: score 60-79, no discrepancy", compute_verdict(70, None) == "Hire")
    check("Borderline: score 40-59, no discrepancy", compute_verdict(50, None) == "Borderline")
    check("Borderline: score>=60 WITH discrepancy (downgrade)", compute_verdict(90, "discrepancy") == "Borderline")
    check("No Hire: score<40", compute_verdict(30, None) == "No Hire")
    check("No Hire: already-Borderline WITH discrepancy", compute_verdict(45, "discrepancy") == "No Hire")


def test_phase3_batching_error_isolation() -> None:
    print("\n=== Phase 3: batched analysis/recommendation, per-item error isolation ===")
    match_results = [
        # A real file (needed here -- unlike the other tests, this one calls
        # the actual deep_analyze_candidates, which really reads the resume).
        MatchResult(candidate_name="Maria Kowalski", resume_path="resumes/engineering/backend_maria.txt", match_score=95.0, reasoning="..."),
        MatchResult(candidate_name="Ghost Candidate", resume_path="resumes/does_not_exist.txt", match_score=50.0, reasoning="..."),
    ]

    class FakeDeepAnalysisModel:
        """Returns a DeepAnalysisOutput -- the real LLM-facing schema, which
        deliberately has no candidate_name/resume_path fields at all (a live
        run once found the model would invent a plausible-but-wrong path
        instead of echoing the real one, silently breaking
        generate_recommendations' resume_path-keyed lookup).
        """

        def batch(self, prompts, config=None, return_exceptions=False):
            return [DeepAnalysisOutput(strengths=["7 yrs Python"])]

    analyses = deep_analyze_candidates(match_results, ["5+ years Python"], ["AWS"], model=FakeDeepAnalysisModel())
    by_path = {a.resume_path: a for a in analyses}
    check("unreadable resume gets an error-carrying fallback, not a crash", "Could not read resume" in by_path["resumes/does_not_exist.txt"].gaps[0])
    check(
        "DeepAnalysisResult.resume_path always comes from MatchResult, never the LLM output "
        "(regression: a live run once got an empty recommendations list because the model "
        "invented its own resume_path, breaking generate_recommendations' lookup)",
        by_path["resumes/engineering/backend_maria.txt"].resume_path == "resumes/engineering/backend_maria.txt",
    )

    class FakeRecommendationModel:
        def batch(self, prompts, config=None, return_exceptions=False):
            return [
                RecommendationOutput(justification="Strong fit.", improvement_suggestions=["should be dropped"]),
                Exception("LLM call failed"),
            ]

    recs = generate_recommendations(match_results, analyses, model=FakeRecommendationModel())
    by_path = {r.resume_path: r for r in recs}
    check("Strong Hire verdict discards improvement_suggestions", by_path["resumes/engineering/backend_maria.txt"].improvement_suggestions == [])
    check("a raised batch exception isolates to that candidate only", "failed" in by_path["resumes/does_not_exist.txt"].justification.lower())


def test_phase3_full_graph_path() -> None:
    print("\n=== Phase 3: full 3-round screening graph path ===")
    graph = matching_agent.build_graph()
    fake_analyses = [DeepAnalysisResult(candidate_name="Maria Kowalski", resume_path="resumes/engineering/backend_maria.txt", strengths=["7 yrs Python"], nice_to_have_coverage=["AWS"])]
    fake_recs = [Recommendation(candidate_name="Maria Kowalski", resume_path="resumes/engineering/backend_maria.txt", verdict="Strong Hire", justification="Excellent fit.")]

    with patch("matching_agent.embed_job_description", return_value={"dense": [], "sparse": {"indices": [], "values": []}}), \
         patch("matching_agent.semantic_search", return_value=[MARIA_HIT]), \
         patch("matching_agent.run_deep_analysis", return_value=fake_analyses) as mock_deep, \
         patch("matching_agent.run_generate_recommendations", return_value=fake_recs) as mock_rec:
        thread_id = str(uuid.uuid4())
        state = graph.invoke(
            {"thread_id": thread_id, "jd_source_path": "jobs/senior_backend_engineer.txt", "deep_screening_requested": True},
            {"configurable": {"thread_id": thread_id}},
        )

    check("Deep Analysis node ran", mock_deep.called)
    check("Recommendation node ran", mock_rec.called)
    check("round == 'recommendation'", state.get("round") == "recommendation")
    check("verdict rendered in report", "Strong Hire" in state["report"])

    # Regression: deep_screening_requested=False must never touch Phase 3 nodes.
    with patch("matching_agent.embed_job_description", return_value={"dense": [], "sparse": {"indices": [], "values": []}}), \
         patch("matching_agent.semantic_search", return_value=[MARIA_HIT]), \
         patch("matching_agent.run_deep_analysis") as mock_deep2, \
         patch("matching_agent.run_generate_recommendations") as mock_rec2:
        thread_id2 = str(uuid.uuid4())
        state2 = graph.invoke(
            {"thread_id": thread_id2, "jd_source_path": "jobs/senior_backend_engineer.txt", "deep_screening_requested": False},
            {"configurable": {"thread_id": thread_id2}},
        )
    check("deep_screening_requested=False skips Phase 3 nodes entirely", not mock_deep2.called and not mock_rec2.called)
    check("report has no verdict section when Phase 3 skipped", "Verdict" not in state2["report"])


def test_phase3_tools() -> None:
    print("\n=== Phase 3: on-demand conversational tools ===")
    tools.session.match_results = [
        MatchResult(candidate_name="Maria Kowalski", resume_path="resumes/engineering/backend_maria.txt", match_score=95.0, reasoning="..."),
        MatchResult(candidate_name="Devon Okafor", resume_path="resumes/engineering/fullstack_devon.md", match_score=70.0, reasoning="..."),
    ]
    tools.session.deep_analysis = []
    tools.session.recommendations = []

    fake_analysis = [DeepAnalysisResult(candidate_name="Maria Kowalski", resume_path="resumes/engineering/backend_maria.txt", strengths=["strong"])]
    with patch("tools.run_deep_analysis", return_value=fake_analysis):
        result = tools.deep_analyze_candidates.invoke({"candidate_identifiers": ["Maria Kowalski", "Nobody"]})
    check("deep_analyze_candidates tool stores results in the session", len(tools.session.deep_analysis) == 1)
    check("deep_analyze_candidates tool reports unresolvable identifiers", result["not_found"][0]["identifier"] == "Nobody")

    fake_rec = [Recommendation(candidate_name="Maria Kowalski", resume_path="resumes/engineering/backend_maria.txt", verdict="Strong Hire", justification="Great fit.")]
    with patch("tools.run_generate_recommendations", return_value=fake_rec):
        result = tools.generate_recommendation.invoke({"candidate_identifiers": ["Maria Kowalski", "Devon Okafor"]})
    check("generate_recommendation runs for candidates with a deep analysis", len(result["recommendations"]) == 1)
    check("generate_recommendation reports (not silently skips) a missing deep analysis", result["missing_deep_analysis"][0]["candidate_name"] == "Devon Okafor")


def main() -> int:
    test_phase1_happy_path()
    test_phase1_error_paths()
    test_phase2_conversation_turns()
    test_phase2_tools()
    test_phase3_verdict_thresholds()
    test_phase3_batching_error_isolation()
    test_phase3_full_graph_path()
    test_phase3_tools()

    print(f"\n{'=' * 60}")
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED:")
        for label in FAILURES:
            print(f"  - {label}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
