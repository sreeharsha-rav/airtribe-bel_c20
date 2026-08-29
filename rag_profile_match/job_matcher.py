"""
2. Semantic Search
- Accept job description as input
- Convert JD to embedding
- Retrieve top-K similar resumes (K=10)
- Implement hybrid search (semantic + keyword for critical skills)

2. Ranking & Scoring
- Score matches (0-100 scale)
- Provide match reasoning (which sections matched)
- Filter by must-have requirements (e.g., "5+ years Python")

Mirrors resume_rag.py's pattern: this module defines the functions only,
with no top-level execution; see rag_analysis.ipynb for the actual pipeline
run.
"""

import re

from fastembed import SparseTextEmbedding
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, Field
from qdrant_client import models as qdrant_models

import config
from resume_rag import build_embedding_model, build_sparse_embedding_model

JOB_SECTION_HEADING_PATTERN = re.compile(
    r"^(About the role|Responsibilities|Must-have requirements|Nice-to-have)\s*$",
    re.MULTILINE,
)

MUST_HAVE_FILLER_WORDS = {
    "years", "year", "of", "with", "a", "an", "the", "and", "or", "using",
    "in", "experience", "hands-on", "hands", "on", "professional",
    "proven", "demonstrated", "history",
}
QUANTIFIER_PATTERN = re.compile(r"^(\d+)\+?\s*years?\b", re.IGNORECASE)


class MatchResult(BaseModel):
    """One ranked candidate match for a job description.

    Field names mirror the report shape described in README.md.
    """

    candidate_name: str | None = Field(default=None, description="Matched candidate's name")
    resume_path: str = Field(description="Path (relative to root_dir/) of the matched resume")
    match_score: float = Field(description="Overall match score, 0-100")
    matched_skills: list[str] = Field(default_factory=list, description="Candidate skills relevant to the job")
    relevant_excerpts: list[str] = Field(default_factory=list, description="Resume chunk excerpts that drove the match")
    reasoning: str = Field(description="Explanation of which resume sections/skills drove the score")


def split_job_sections(text: str) -> dict[str, str]:
    """Splits a job description into its named sections.

    Every posting under root_dir/jobs/ uses the same 4 headings ("About the
    role", "Responsibilities", "Must-have requirements", "Nice-to-have"),
    each alone on its own line. Text before the first heading (title +
    company/location line) becomes "header". If no heading is found,
    everything falls into "header".
    """
    sections = {
        "header": "",
        "about_the_role": "",
        "responsibilities": "",
        "must_have_requirements": "",
        "nice_to_have": "",
    }
    heading_keys = {
        "About the role": "about_the_role",
        "Responsibilities": "responsibilities",
        "Must-have requirements": "must_have_requirements",
        "Nice-to-have": "nice_to_have",
    }

    matches = list(JOB_SECTION_HEADING_PATTERN.finditer(text))
    if not matches:
        sections["header"] = text.strip()
        return sections

    sections["header"] = text[: matches[0].start()].strip()

    for i, match in enumerate(matches):
        key = heading_keys[match.group(1)]
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[key] = text[start:end].strip()

    return sections


def extract_must_have_requirements(jd_text: str) -> list[str]:
    """Extracts the individual bullet requirements from a job description's
    "Must-have requirements" section (e.g. "5+ years of hands-on Python
    development.").
    """
    section = split_job_sections(jd_text)["must_have_requirements"]
    bullets: list[str] = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("-"):
            bullets.append(line.lstrip("-").strip())
        elif bullets:
            # a wrapped continuation of the previous bullet, not a new one
            bullets[-1] = f"{bullets[-1]} {line}"
    return bullets


def embed_job_description(
    jd_text: str,
    embedding_model: Embeddings | None = None,
    sparse_model: SparseTextEmbedding | None = None,
) -> dict:
    """Embeds a job description's descriptive prose (header + About the role
    + Responsibilities) with the same dense+sparse models used for resume
    chunks, so vectors are directly comparable. Must-have/Nice-to-have
    bullets are deliberately excluded here -- they're matched via
    keyword_match_score instead of semantic similarity.
    """
    embedding_model = embedding_model or build_embedding_model()
    sparse_model = sparse_model or build_sparse_embedding_model()

    sections = split_job_sections(jd_text)
    query_text = "\n\n".join(
        sections[key] for key in ("header", "about_the_role", "responsibilities") if sections[key]
    )

    dense_vector = embedding_model.embed_query(query_text)
    sparse_vector = list(sparse_model.embed([query_text]))[0]

    return {
        "dense": dense_vector,
        "sparse": {
            "indices": sparse_vector.indices.tolist(),
            "values": sparse_vector.values.tolist(),
        },
    }


def semantic_search(jd_vectors: dict, top_k: int = config.MATCH_TOP_K) -> list[dict]:
    """Queries Qdrant for the top_k resume candidates whose chunks best match
    the job description, fusing dense + sparse similarity via Reciprocal
    Rank Fusion (RRF).

    The collection is chunk-level (up to 4 chunks per resume), so raw hits
    are grouped by metadata.file_path, keeping each candidate's best (max)
    fused score and up to 2 distinct matched chunk excerpts. top_k here
    controls the candidate *pool* size returned, not necessarily
    match_job's final result count.
    """
    prefetch_limit = max(top_k * 4, 40)
    response = config.client.query_points(
        collection_name=config.QDRANT_COLLECTION_NAME,
        prefetch=[
            qdrant_models.Prefetch(query=jd_vectors["dense"], using="dense", limit=prefetch_limit),
            qdrant_models.Prefetch(
                query=qdrant_models.SparseVector(**jd_vectors["sparse"]), using="sparse", limit=prefetch_limit
            ),
        ],
        query=qdrant_models.FusionQuery(fusion=qdrant_models.Fusion.RRF),
        limit=prefetch_limit,
        with_payload=True,
    )

    candidates: dict[str, dict] = {}
    for point in response.points:
        assert point.payload is not None
        metadata = point.payload["metadata"]
        file_path = metadata["file_path"]
        excerpt = point.payload["page_content"]

        existing = candidates.get(file_path)
        if existing is None:
            candidates[file_path] = {
                "file_path": file_path,
                "metadata": metadata,
                "score": point.score,
                "excerpts": [excerpt],
            }
        else:
            existing["score"] = max(existing["score"], point.score)
            if excerpt not in existing["excerpts"] and len(existing["excerpts"]) < 2:
                existing["excerpts"].append(excerpt)

    ranked = sorted(candidates.values(), key=lambda c: c["score"], reverse=True)
    return ranked[:top_k]


def _topic_tokens(bullet: str) -> list[str]:
    """Extracts meaningful topic tokens from a must-have bullet: lowercases,
    strips punctuation, drops the leading quantifier and filler words.
    """
    text = QUANTIFIER_PATTERN.sub("", bullet)
    text = re.sub(r"[^\w\s-]", " ", text.lower())
    return [token for token in text.split() if token not in MUST_HAVE_FILLER_WORDS]


def keyword_match_score(
    candidate_skills: list[str],
    candidate_experience_years: float | None,
    must_haves: list[str],
) -> dict:
    """Scores how many must-have requirements a candidate satisfies.

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

    for bullet in must_haves:
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


def score_and_rank(semantic_hits: list[dict], must_haves: list[str]) -> list[MatchResult]:
    """Combines RRF semantic similarity with must-have satisfaction into a
    0-100 match_score. Candidates failing any must-have are excluded (hard
    filter). Survivors' raw RRF scores are min-max normalized to 0-100.
    """
    survivors = []
    for hit in semantic_hits:
        metadata = hit["metadata"]
        km = keyword_match_score(metadata["skills"], metadata.get("total_experience_years"), must_haves)
        if km["missed"]:
            continue
        survivors.append((hit, km))

    if not survivors:
        return []

    scores = [hit["score"] for hit, _ in survivors]
    min_score, max_score = min(scores), max(scores)

    results = []
    for hit, km in survivors:
        metadata = hit["metadata"]
        normalized = 100 * (hit["score"] - min_score) / (max_score - min_score) if max_score > min_score else 100.0

        reasoning = (
            f"Matched via hybrid dense+sparse similarity (RRF score {hit['score']:.4f}); "
            f"satisfied all {len(must_haves)} must-have requirement(s)"
            + (f", including {', '.join(km['matched_skills'])}" if km["matched_skills"] else "")
            + "."
        )

        results.append(
            MatchResult(
                candidate_name=metadata.get("candidate_name"),
                resume_path=metadata["file_path"],
                match_score=normalized,
                matched_skills=km["matched_skills"],
                relevant_excerpts=hit["excerpts"],
                reasoning=reasoning,
            )
        )

    results.sort(key=lambda result: result.match_score, reverse=True)
    return results


def match_job(jd_text: str, top_k: int = config.MATCH_TOP_K) -> list[MatchResult]:
    """End-to-end job matching entry point: embed_job_description ->
    semantic_search -> extract_must_have_requirements -> score_and_rank.

    Fetches a wider candidate pool (max(top_k * 3, 15)) than the final
    top_k before must-have filtering -- otherwise the hard filter could
    shrink the result below top_k even when qualifying candidates exist
    further down the semantic ranking. This is the single function the
    notebook should call.
    """
    jd_vectors = embed_job_description(jd_text)
    must_haves = extract_must_have_requirements(jd_text)
    semantic_hits = semantic_search(jd_vectors, top_k=max(top_k * 3, 15))
    return score_and_rank(semantic_hits, must_haves)[:top_k]
