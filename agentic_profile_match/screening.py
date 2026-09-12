"""Deep Analysis + Recommendation (Phase 3's Multi-Round Screening): a
full-resume-grounded structured-output LLM call per shortlisted candidate,
plus a deterministic (non-LLM) hire/no-hire verdict.

The batching pattern (.with_structured_output + .batch(return_exceptions=True),
per-item error isolation) mirrors rag_profile_match/resume_rag.py's
extract_fields_batch -- these two calls just target different schemas over
different (full resume text + must-haves/nice-to-haves, or deep-analysis
output) input.
"""

from typing import Literal, cast

from langchain_core.language_models import LanguageModelInput
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model

import config
from fs_tools import read_file
from prompts.deep_screening import DEEP_ANALYSIS_SYSTEM_PROMPT, RECOMMENDATION_SYSTEM_PROMPT
from ranking import MatchResult


class DeepAnalysisOutput(BaseModel):
    """What the LLM actually produces for one candidate's deep analysis --
    candidate_name/resume_path are deliberately NOT part of this schema.
    Early testing found the model would otherwise invent a plausible-looking
    but wrong path/name (e.g. "alice_chen_resume.txt" instead of the real
    "resumes/engineering/backend_alice.txt") instead of echoing back the
    identifiers given in the prompt -- which then silently broke
    generate_recommendations' resume_path-keyed lookup. DeepAnalysisResult
    sets those fields programmatically from the MatchResult instead.
    """

    strengths: list[str] = Field(default_factory=list, description="Concrete strengths, grounded in the full resume text")
    gaps: list[str] = Field(default_factory=list, description="Concrete gaps against the job's requirements")
    nice_to_have_coverage: list[str] = Field(
        default_factory=list, description="Nice-to-have bullets the full resume actually supports"
    )
    must_have_discrepancy: str | None = Field(
        default=None,
        description="Set only if the full resume contradicts an earlier chunk-based must-have match; null otherwise",
    )


class DeepAnalysisResult(BaseModel):
    """One candidate's full-resume-grounded strengths/gaps analysis.
    candidate_name/resume_path are always set from the originating
    MatchResult, never from the LLM (see DeepAnalysisOutput).
    """

    candidate_name: str | None = Field(default=None, description="Candidate's name")
    resume_path: str = Field(description="Path (relative to root_dir/) of the analyzed resume")
    strengths: list[str] = Field(default_factory=list, description="Concrete strengths, grounded in the full resume text")
    gaps: list[str] = Field(default_factory=list, description="Concrete gaps against the job's requirements")
    nice_to_have_coverage: list[str] = Field(
        default_factory=list, description="Nice-to-have bullets the full resume actually supports"
    )
    must_have_discrepancy: str | None = Field(
        default=None,
        description="Set only if the full resume contradicts an earlier chunk-based must-have match; null otherwise",
    )


class RecommendationOutput(BaseModel):
    """What the LLM actually produces for one candidate's recommendation --
    the verdict itself is computed deterministically by compute_verdict, not
    requested from the model.
    """

    justification: str = Field(description="Concise explanation of the given verdict, grounded in strengths/gaps/discrepancy")
    improvement_suggestions: list[str] = Field(
        default_factory=list,
        description="Concrete improvements that would strengthen this candidate's fit -- only when the verdict is Borderline",
    )


class Recommendation(BaseModel):
    """One candidate's final verdict + justification."""

    candidate_name: str | None = Field(default=None, description="Candidate's name")
    resume_path: str = Field(description="Path (relative to root_dir/) of the recommended-on resume")
    verdict: Literal["Strong Hire", "Hire", "Borderline", "No Hire"]
    justification: str = Field(description="LLM-authored explanation of the verdict")
    improvement_suggestions: list[str] = Field(
        default_factory=list, description="Populated only when verdict == 'Borderline'"
    )


def build_deep_analysis_model() -> Runnable[LanguageModelInput, DeepAnalysisOutput]:
    """`with_structured_output` is typed as returning `Runnable[LanguageModelInput,
    dict[str, Any] | BaseModel]` regardless of the schema passed in -- passing the
    DeepAnalysisOutput class (not include_raw=True) always yields a DeepAnalysisOutput
    instance at runtime, so the cast narrows that back to the real type.
    """
    model = init_chat_model(model=config.MODEL_NAME, model_provider=config.MODEL_PROVIDER)
    structured_model = model.with_structured_output(DeepAnalysisOutput).with_retry(
        stop_after_attempt=config.SCREENING_MAX_RETRIES
    )
    return cast(Runnable[LanguageModelInput, DeepAnalysisOutput], structured_model)


def build_recommendation_model() -> Runnable[LanguageModelInput, RecommendationOutput]:
    model = init_chat_model(model=config.MODEL_NAME, model_provider=config.MODEL_PROVIDER)
    structured_model = model.with_structured_output(RecommendationOutput).with_retry(
        stop_after_attempt=config.SCREENING_MAX_RETRIES
    )
    return cast(Runnable[LanguageModelInput, RecommendationOutput], structured_model)


def _deep_analysis_messages(
    result: MatchResult, resume_text: str, must_haves: list[str], nice_to_haves: list[str]
) -> list[tuple[str, str]]:
    return [
        ("system", DEEP_ANALYSIS_SYSTEM_PROMPT),
        (
            "user",
            f"Candidate: {result.candidate_name or result.resume_path}\n\n"
            f"Full resume text:\n{resume_text}\n\n"
            "Must-have requirements:\n" + "\n".join(f"- {bullet}" for bullet in must_haves) + "\n\n"
            "Nice-to-have:\n" + "\n".join(f"- {bullet}" for bullet in nice_to_haves) + "\n\n"
            f"Skills already matched from a chunk-level search: {', '.join(result.matched_skills) or 'none recorded'}",
        ),
    ]


def deep_analyze_candidates(
    match_results: list[MatchResult],
    must_haves: list[str],
    nice_to_haves: list[str],
    model: Runnable[LanguageModelInput, DeepAnalysisOutput] | None = None,
) -> list[DeepAnalysisResult]:
    """Re-reads each candidate's FULL resume text (not just relevant_excerpts'
    1-2 stored chunks) and makes one batched structured-output LLM call per
    candidate. A candidate whose resume can't be read, or whose LLM call
    fails, gets a DeepAnalysisResult carrying the error in `gaps` rather than
    aborting the whole batch (return_exceptions=True, per-item isolation).
    """
    model = model or build_deep_analysis_model()

    readable: list[tuple[MatchResult, str]] = []
    for result in match_results:
        read_result = read_file.invoke({"filepath": result.resume_path})
        if not read_result["success"]:
            readable.append((result, None))
        else:
            readable.append((result, read_result["content"]))

    prompts = [
        _deep_analysis_messages(result, resume_text, must_haves, nice_to_haves)
        for result, resume_text in readable
        if resume_text is not None
    ]
    prompt_targets = [result for result, resume_text in readable if resume_text is not None]

    outputs = (
        model.batch(prompts, config={"max_concurrency": config.SCREENING_MAX_CONCURRENCY}, return_exceptions=True)
        if prompts
        else []
    )

    output_by_path = {}
    for result, output in zip(prompt_targets, outputs):
        if isinstance(output, BaseException):
            output_by_path[result.resume_path] = DeepAnalysisResult(
                candidate_name=result.candidate_name,
                resume_path=result.resume_path,
                gaps=[f"Deep analysis failed: {output}"],
            )
        else:
            output_by_path[result.resume_path] = DeepAnalysisResult(
                candidate_name=result.candidate_name,
                resume_path=result.resume_path,
                strengths=output.strengths,
                gaps=output.gaps,
                nice_to_have_coverage=output.nice_to_have_coverage,
                must_have_discrepancy=output.must_have_discrepancy,
            )

    analyses = []
    for result, resume_text in readable:
        if result.resume_path in output_by_path:
            analyses.append(output_by_path[result.resume_path])
        else:
            analyses.append(
                DeepAnalysisResult(
                    candidate_name=result.candidate_name,
                    resume_path=result.resume_path,
                    gaps=[f"Could not read resume for deep analysis: {result.resume_path}"],
                )
            )
    return analyses


def compute_verdict(match_score: float, must_have_discrepancy: str | None) -> str:
    """Deterministic verdict from the match score + Deep Analysis's
    discrepancy flag -- the LLM never decides the label, only justifies it.

    | Verdict     | Rule                                                          |
    |-------------|----------------------------------------------------------------|
    | Strong Hire | match_score >= 80, no discrepancy                              |
    | Hire        | match_score 60-79, no discrepancy                              |
    | Borderline  | match_score 40-59, or 60+ with a discrepancy                   |
    | No Hire     | match_score < 40, or an already-Borderline candidate (40-59)    |
    |             | with a discrepancy                                              |
    """
    has_discrepancy = must_have_discrepancy is not None

    if match_score >= 60 and has_discrepancy:
        return "Borderline"
    if match_score >= 80:
        return "Strong Hire"
    if match_score >= 60:
        return "Hire"
    if match_score >= 40:
        return "No Hire" if has_discrepancy else "Borderline"
    return "No Hire"


def _recommendation_messages(result: MatchResult, analysis: DeepAnalysisResult, verdict: str) -> list[tuple[str, str]]:
    return [
        ("system", RECOMMENDATION_SYSTEM_PROMPT),
        (
            "user",
            f"Candidate: {result.candidate_name or result.resume_path}\n"
            f"Match score: {result.match_score:.1f}\n"
            f"Verdict: {verdict}\n\n"
            "Strengths:\n" + "\n".join(f"- {s}" for s in analysis.strengths) + "\n\n"
            "Gaps:\n" + "\n".join(f"- {g}" for g in analysis.gaps) + "\n\n"
            f"Must-have discrepancy: {analysis.must_have_discrepancy or 'None'}\n\n"
            f"Nice-to-have coverage: {', '.join(analysis.nice_to_have_coverage) or 'None'}",
        ),
    ]


def generate_recommendations(
    match_results: list[MatchResult],
    deep_analysis: list[DeepAnalysisResult],
    model: Runnable[LanguageModelInput, RecommendationOutput] | None = None,
) -> list[Recommendation]:
    """Computes each candidate's verdict deterministically, then makes one
    batched structured-output LLM call per candidate for the justification
    prose (and, for Borderline candidates only, improvement suggestions).
    Candidates in match_results with no matching deep_analysis entry are
    skipped -- Deep Analysis is expected to have run over the same
    match_results first.
    """
    model = model or build_recommendation_model()
    analysis_by_path = {analysis.resume_path: analysis for analysis in deep_analysis}

    items = []
    for result in match_results:
        analysis = analysis_by_path.get(result.resume_path)
        if analysis is None:
            continue
        verdict = compute_verdict(result.match_score, analysis.must_have_discrepancy)
        items.append((result, analysis, verdict))

    if not items:
        return []

    prompts = [_recommendation_messages(result, analysis, verdict) for result, analysis, verdict in items]
    outputs = model.batch(prompts, config={"max_concurrency": config.SCREENING_MAX_CONCURRENCY}, return_exceptions=True)

    recommendations = []
    for (result, _analysis, verdict), output in zip(items, outputs):
        if isinstance(output, BaseException):
            recommendations.append(
                Recommendation(
                    candidate_name=result.candidate_name,
                    resume_path=result.resume_path,
                    verdict=verdict,
                    justification=f"Justification generation failed: {output}",
                )
            )
            continue
        recommendations.append(
            Recommendation(
                candidate_name=result.candidate_name,
                resume_path=result.resume_path,
                verdict=verdict,
                justification=output.justification,
                improvement_suggestions=output.improvement_suggestions if verdict == "Borderline" else [],
            )
        )
    return recommendations
