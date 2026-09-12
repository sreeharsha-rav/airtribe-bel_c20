"""Must-have hard filtering, score normalization, and the MatchResult schema.

Duplicated from rag_profile_match/job_matcher.py (DESIGN.md's Reuse
strategy, Q1), extended with nice_to_haves_satisfied: score_and_rank now
also runs keyword_match_score against nice_to_haves for survivors (Phase 1's
Rank Candidates node) so the nice-to-haves Extract Requirements already
extracts have somewhere to be displayed -- purely informational, this never
gates or affects match_score.
"""

import re

from pydantic import BaseModel, Field

MUST_HAVE_FILLER_WORDS = {
    "years", "year", "of", "with", "a", "an", "the", "and", "or", "using",
    "in", "experience", "hands-on", "hands", "on", "professional",
    "proven", "demonstrated", "history",
}
QUANTIFIER_PATTERN = re.compile(r"^(\d+)\+?\s*years?\b", re.IGNORECASE)


class MatchResult(BaseModel):
    """One ranked candidate match for a job description.

    Field names mirror rag_profile_match's MatchResult, plus
    nice_to_haves_satisfied (Phase 1's addition, informational only).
    """

    candidate_name: str | None = Field(default=None, description="Matched candidate's name")
    resume_path: str = Field(description="Path (relative to root_dir/) of the matched resume")
    match_score: float = Field(description="Overall match score, 0-100")
    matched_skills: list[str] = Field(default_factory=list, description="Candidate skills relevant to the job's must-haves")
    nice_to_haves_satisfied: list[str] = Field(
        default_factory=list,
        description="Nice-to-have bullets this candidate's skills also satisfy (informational only -- doesn't affect match_score)",
    )
    relevant_excerpts: list[str] = Field(default_factory=list, description="Resume chunk excerpts that drove the match")
    reasoning: str = Field(description="Explanation of which resume sections/skills drove the score")


def _topic_tokens(bullet: str) -> list[str]:
    """Extracts meaningful topic tokens from a requirement bullet: lowercases,
    strips punctuation, drops the leading quantifier and filler words.
    """
    text = QUANTIFIER_PATTERN.sub("", bullet)
    text = re.sub(r"[^\w\s-]", " ", text.lower())
    return [token for token in text.split() if token not in MUST_HAVE_FILLER_WORDS]


def keyword_match_score(
    candidate_skills: list[str],
    candidate_experience_years: float | None,
    requirements: list[str],
) -> dict:
    """Scores how many requirement bullets (must-have or nice-to-have) a
    candidate satisfies.

    A deliberately simple heuristic, not full NLU: a quantified bullet
    ("N+ years...") checks total_experience_years >= N, plus a topic-token
    match against the candidate's normalized skills list when the bullet
    names a concrete technology. A broad domain-experience bullet with no
    matching skill token (e.g. "5+ years of data engineering experience" --
    "data"/"engineering" often aren't literal skill-list entries) falls
    back to a years-only check; the posting's other bullets (which do name
    concrete tech) keep the overall hard filter meaningful. An unquantified
    bullet ("Experience with X") checks topic-token overlap only. Topic
    tokens are matched with OR logic (any token matching is enough) -- an
    approximation, not true parsing of "X and Y" vs. "X or Y" phrasing.
    """
    skills_lower = [skill.lower() for skill in candidate_skills]
    satisfied: list[str] = []
    missed: list[str] = []
    matched_skills: list[str] = []

    for bullet in requirements:
        quantifier_match = QUANTIFIER_PATTERN.match(bullet)
        required_years = int(quantifier_match.group(1)) if quantifier_match else None
        topic_tokens = _topic_tokens(bullet)

        skill_hits = [
            skill
            for skill, skill_lower in zip(candidate_skills, skills_lower)
            if any(token in skill_lower or skill_lower in token for token in topic_tokens)
        ]

        if required_years is not None:
            years_ok = candidate_experience_years is not None and candidate_experience_years >= required_years
            ok = years_ok and bool(skill_hits) if skill_hits else years_ok
        else:
            ok = bool(skill_hits)

        if ok:
            satisfied.append(bullet)
            matched_skills.extend(skill_hits)
        else:
            missed.append(bullet)

    return {
        "satisfied": satisfied,
        "missed": missed,
        "matched_skills": sorted(set(matched_skills)),
    }


def score_and_rank(
    semantic_hits: list[dict],
    must_haves: list[str],
    nice_to_haves: list[str] | None = None,
) -> list[MatchResult]:
    """Combines RRF semantic similarity with must-have satisfaction into a
    0-100 match_score. Candidates failing any must-have are excluded (hard
    filter). Survivors' raw RRF scores are min-max normalized to 0-100.
    Nice-to-have overlap is also computed for survivors, for display only.
    """
    nice_to_haves = nice_to_haves or []
    survivors = []
    for hit in semantic_hits:
        metadata = hit["metadata"]
        must_km = keyword_match_score(metadata["skills"], metadata.get("total_experience_years"), must_haves)
        if must_km["missed"]:
            continue
        nice_km = keyword_match_score(metadata["skills"], metadata.get("total_experience_years"), nice_to_haves)
        survivors.append((hit, must_km, nice_km))

    if not survivors:
        return []

    scores = [hit["score"] for hit, _, _ in survivors]
    min_score, max_score = min(scores), max(scores)

    results = []
    for hit, must_km, nice_km in survivors:
        metadata = hit["metadata"]
        normalized = 100 * (hit["score"] - min_score) / (max_score - min_score) if max_score > min_score else 100.0

        reasoning = (
            f"Matched via hybrid dense+sparse similarity (RRF score {hit['score']:.4f}); "
            f"satisfied all {len(must_haves)} must-have requirement(s)"
            + (f", including {', '.join(must_km['matched_skills'])}" if must_km["matched_skills"] else "")
            + "."
        )

        results.append(
            MatchResult(
                candidate_name=metadata.get("candidate_name"),
                resume_path=metadata["file_path"],
                match_score=normalized,
                matched_skills=must_km["matched_skills"],
                nice_to_haves_satisfied=nice_km["satisfied"],
                relevant_excerpts=hit["excerpts"],
                reasoning=reasoning,
            )
        )

    results.sort(key=lambda result: result.match_score, reverse=True)
    return results
