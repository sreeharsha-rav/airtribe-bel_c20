"""Job description section splitting and requirement bullet extraction.

Duplicated from rag_profile_match/job_matcher.py (DESIGN.md's Reuse
strategy, Q1), plus a new extract_nice_to_have_requirements — the same
bullet-parsing logic pointed at the "Nice-to-have" section instead of
"Must-have requirements". Purely algorithmic (Q3, Phase 1): every posting
under rag_profile_match/root_dir/jobs/ follows the same 4-heading format
this regex parses correctly.
"""

import re

JOB_SECTION_HEADING_PATTERN = re.compile(
    r"^(About the role|Responsibilities|Must-have requirements|Nice-to-have)\s*$",
    re.MULTILINE,
)


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


def _parse_bullets(section_text: str) -> list[str]:
    """Parses a section's "- " bullet list, folding wrapped continuation
    lines (no leading "-") into the previous bullet.
    """
    bullets: list[str] = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("-"):
            bullets.append(line.lstrip("-").strip())
        elif bullets:
            bullets[-1] = f"{bullets[-1]} {line}"
    return bullets


def extract_must_have_requirements(jd_text: str) -> list[str]:
    """Extracts the individual bullet requirements from a job description's
    "Must-have requirements" section (e.g. "5+ years of hands-on Python
    development.").
    """
    return _parse_bullets(split_job_sections(jd_text)["must_have_requirements"])


def extract_nice_to_have_requirements(jd_text: str) -> list[str]:
    """Extracts the individual bullet requirements from a job description's
    "Nice-to-have" section. Informational only in Phase 1 — displayed
    alongside must-haves, but doesn't gate or affect match_score (see
    ranking.score_and_rank).
    """
    return _parse_bullets(split_job_sections(jd_text)["nice_to_have"])
