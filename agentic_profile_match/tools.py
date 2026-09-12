"""The Human Feedback Loop's tool belt (Phase 2), plus the shared mutable
session container these tools close over.

The inner conversational agent (matching_agent.get_conversational_agent) runs
its own separate tool-execution loop, not the outer graph's ToolNode, so it
can't use LangGraph's InjectedState to read/mutate AgentState directly (see
DESIGN.md's Phase 2 Overview). Instead, matching_agent.human_feedback_loop
copies the relevant AgentState fields into `session` right before invoking
the agent each turn, and copies the (possibly tool-mutated) values back out
afterward.
"""

import difflib
from dataclasses import dataclass, field

from langchain.chat_models import init_chat_model
from langchain.tools import tool
from pydantic import BaseModel, Field

import config
from fs_tools import read_file
from jd_parser import extract_must_have_requirements, extract_nice_to_have_requirements, split_job_sections
from ranking import MatchResult, score_and_rank
from retrieval import embed_text, semantic_search


@dataclass
class Session:
    """The active screening session's business state, as of the most recent
    turn -- mirrors a subset of AgentState (see matching_agent.human_feedback_loop
    for the sync-in/sync-out).
    """

    match_results: list[MatchResult] = field(default_factory=list)
    must_haves: list[str] = field(default_factory=list)
    nice_to_haves: list[str] = field(default_factory=list)
    jd_text: str = ""
    jd_sections: dict[str, str] = field(default_factory=dict)
    candidate_pool: list[dict] = field(default_factory=list)


session = Session()


def _resolve_candidate(identifier: str, match_results: list[MatchResult]) -> tuple[MatchResult | None, str | None]:
    """Fuzzy-resolves a candidate name or resume_path against the current
    shortlist. Returns (result, None) on a clean match, or (None, message)
    with a "not found, did you mean X" / disambiguation message otherwise.
    """
    for result in match_results:
        if result.resume_path == identifier:
            return result, None

    identifier_lower = identifier.lower()
    substring_matches = [
        result for result in match_results if result.candidate_name and identifier_lower in result.candidate_name.lower()
    ]
    if len(substring_matches) == 1:
        return substring_matches[0], None
    if len(substring_matches) > 1:
        names = ", ".join(result.candidate_name for result in substring_matches)
        return None, f"'{identifier}' matches multiple candidates in the current shortlist ({names}) -- please be more specific."

    names = [result.candidate_name for result in match_results if result.candidate_name]
    suggestion = difflib.get_close_matches(identifier, names, n=1)
    if suggestion:
        return None, f"'{identifier}' not found in the current shortlist. Did you mean '{suggestion[0]}'?"
    return None, f"'{identifier}' not found in the current shortlist."


# --- search_resumes ------------------------------------------------------------

class SearchResumesInput(BaseModel):
    """Input for a loose natural-language resume search."""

    query: str = Field(
        description=(
            "Loose natural-language description of the candidate you're looking for, e.g. "
            "'React developer with 3+ years experience'. Not JD-shaped text -- plain prose."
        ),
    )
    must_have_keywords: list[str] = Field(
        default_factory=list,
        description="Hard-requirement skill/technology keywords, e.g. ['react', 'aws']. Candidates missing any are excluded.",
    )
    min_experience_years: float | None = Field(
        default=None,
        description="Minimum total years of professional experience required, if any.",
    )


@tool("search_resumes", args_schema=SearchResumesInput)
def search_resumes(
    query: str,
    must_have_keywords: list[str] | None = None,
    min_experience_years: float | None = None,
) -> dict:
    """Search the resume corpus with a loose natural-language query and optional hard filters.
    REPLACES the session's active shortlist -- this is both the ad-hoc search tool and the
    entire criteria-refinement mechanism; every call overwrites match_results/candidate_pool.
    """
    must_haves: list[str] = []
    if min_experience_years is not None:
        must_haves.append(f"{int(min_experience_years)}+ years of professional experience.")
    must_haves.extend(f"Experience with {keyword}." for keyword in (must_have_keywords or []))

    vectors = embed_text(query)
    pool_size = max(config.MATCH_TOP_K * 3, 15)
    candidate_pool = semantic_search(vectors, top_k=pool_size)
    match_results = score_and_rank(candidate_pool, must_haves, session.nice_to_haves)[: config.MATCH_TOP_K]

    session.candidate_pool = candidate_pool
    session.match_results = match_results
    session.must_haves = must_haves

    return {
        "query": query,
        "must_haves_applied": must_haves,
        "match_count": len(match_results),
        "match_results": [result.model_dump() for result in match_results],
    }


# --- extract_requirements --------------------------------------------------------

class ExtractRequirementsInput(BaseModel):
    """Input for parsing a wholesale new job description pasted mid-conversation."""

    jd_text: str = Field(description="Full text of a new job description, replacing the currently active one.")


@tool("extract_requirements", args_schema=ExtractRequirementsInput)
def extract_requirements(jd_text: str) -> dict:
    """Parse a new job description's sections and must-have/nice-to-have requirements,
    overwriting the session's active JD. Typically followed by a search_resumes call
    in the same turn to shortlist against it.
    """
    sections = split_job_sections(jd_text)
    must_haves = extract_must_have_requirements(jd_text)
    nice_to_haves = extract_nice_to_have_requirements(jd_text)

    session.jd_text = jd_text
    session.jd_sections = sections
    session.must_haves = must_haves
    session.nice_to_haves = nice_to_haves

    return {"jd_sections": sections, "must_haves": must_haves, "nice_to_haves": nice_to_haves}


# --- compare_candidates -----------------------------------------------------------

class CompareCandidatesInput(BaseModel):
    """Input for a read-only side-by-side candidate comparison."""

    candidate_identifiers: list[str] = Field(
        description="Candidate names or resume paths to compare, as they appeared in the current shortlist/report.",
    )


@tool("compare_candidates", args_schema=CompareCandidatesInput)
def compare_candidates(candidate_identifiers: list[str]) -> dict:
    """Read-only side-by-side comparison of candidates already in the current shortlist
    (score, matched skills, reasoning, excerpts). An unresolvable identifier comes back
    as a "not found, did you mean X" entry rather than raising.
    """
    comparisons = []
    for identifier in candidate_identifiers:
        result, error = _resolve_candidate(identifier, session.match_results)
        if result is None:
            comparisons.append({"identifier": identifier, "found": False, "error": error})
            continue
        comparisons.append(
            {
                "identifier": identifier,
                "found": True,
                "candidate_name": result.candidate_name,
                "resume_path": result.resume_path,
                "match_score": result.match_score,
                "matched_skills": result.matched_skills,
                "nice_to_haves_satisfied": result.nice_to_haves_satisfied,
                "reasoning": result.reasoning,
                "relevant_excerpts": result.relevant_excerpts,
            }
        )
    return {"comparisons": comparisons}


# --- generate_interview_questions --------------------------------------------------

class InterviewQuestions(BaseModel):
    """LLM-drafted interview questions for one candidate."""

    questions: list[str] = Field(
        description="Interview questions targeting this candidate's gaps and the job's must-have "
        "requirements, each grounded in a specific detail from their full resume text."
    )


def _build_interview_question_model():
    model = init_chat_model(model=config.MODEL_NAME, model_provider=config.MODEL_PROVIDER)
    return model.with_structured_output(InterviewQuestions)


class GenerateInterviewQuestionsInput(BaseModel):
    """Input for drafting interview questions for one shortlisted candidate."""

    candidate_identifier: str = Field(
        description="Candidate name or resume path from the current shortlist to draft interview questions for.",
    )


@tool("generate_interview_questions", args_schema=GenerateInterviewQuestionsInput)
def generate_interview_questions(candidate_identifier: str) -> dict:
    """Draft interview questions for one candidate, grounded in their FULL resume text
    (re-read from disk, not just the 1-2 stored excerpts) and the job's must-haves.
    """
    result, error = _resolve_candidate(candidate_identifier, session.match_results)
    if result is None:
        return {"candidate_identifier": candidate_identifier, "found": False, "error": error}

    read_result = read_file.invoke({"filepath": result.resume_path})
    if not read_result["success"]:
        return {
            "candidate_identifier": candidate_identifier,
            "found": True,
            "error": f"Could not read resume '{result.resume_path}': {read_result['error']}",
        }

    prompt = (
        f"Candidate: {result.candidate_name or result.resume_path}\n\n"
        f"Full resume text:\n{read_result['content']}\n\n"
        "Job must-have requirements:\n" + "\n".join(f"- {bullet}" for bullet in session.must_haves) + "\n\n"
        f"Skills already confirmed to match: {', '.join(result.matched_skills) or 'none recorded'}\n\n"
        "Draft 4-6 targeted interview questions that probe this candidate's gaps against the "
        "must-have requirements and verify specific claims in their resume. Ground every question "
        "in a detail from the resume text above -- do not ask generic questions."
    )
    questions = _build_interview_question_model().invoke(prompt)

    return {
        "candidate_identifier": candidate_identifier,
        "found": True,
        "candidate_name": result.candidate_name,
        "questions": questions.questions,
    }
