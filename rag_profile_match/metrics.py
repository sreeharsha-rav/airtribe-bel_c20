"""
Performance metrics for the RAG profile matching pipeline.

- Retrieval accuracy: whether job_matcher.match_job's results actually
  contain the resumes that should match a given job description. Needs a
  small hand-labeled ground-truth mapping of job path -> expected candidate
  resume paths (see rag_analysis.ipynb).
- Latency: wall-clock time per pipeline stage (embedding, Qdrant query,
  scoring), to spot slow stages.

This module defines the functions only, with no top-level execution; see
rag_analysis.ipynb for the actual pipeline run.
"""

import time
from dataclasses import dataclass
from statistics import mean
from typing import Callable

from fs_tools import read_file
from job_matcher import match_job


@dataclass
class RetrievalAccuracyResult:
    job_path: str
    expected_resume_paths: list[str]
    retrieved_resume_paths: list[str]
    precision_at_k: float
    recall_at_k: float


def measure_retrieval_accuracy(
    ground_truth: dict[str, list[str]], top_k: int = 10
) -> list[RetrievalAccuracyResult]:
    """Runs job_matcher.match_job for each job_path in ground_truth and
    computes precision@k / recall@k against that job's expected resume
    paths.
    """
    results = []
    for job_path, expected_paths in ground_truth.items():
        jd_text = read_file.invoke({"filepath": job_path})["content"]
        matches = match_job(jd_text, top_k=top_k)
        retrieved_paths = [match.resume_path for match in matches]

        expected_set = set(expected_paths)
        retrieved_set = set(retrieved_paths)
        true_positives = len(expected_set & retrieved_set)

        precision_at_k = true_positives / len(retrieved_paths) if retrieved_paths else 0.0
        recall_at_k = true_positives / len(expected_set) if expected_set else 0.0

        results.append(
            RetrievalAccuracyResult(
                job_path=job_path,
                expected_resume_paths=expected_paths,
                retrieved_resume_paths=retrieved_paths,
                precision_at_k=precision_at_k,
                recall_at_k=recall_at_k,
            )
        )
    return results


@dataclass
class LatencyResult:
    stage: str
    duration_seconds: float


def measure_latency(stage: str, fn: Callable, *args, **kwargs) -> tuple[LatencyResult, object]:
    """Times a single pipeline stage call (e.g. embed_job_description,
    semantic_search, score_and_rank) and returns (LatencyResult, fn's
    result).
    """
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return LatencyResult(stage, time.perf_counter() - start), result


def summarize_latencies(results: list[LatencyResult]) -> dict:
    """Aggregates a list of LatencyResult into per-stage min/mean/max/p95,
    for reporting in the notebook.

    With the small sample counts this pipeline actually produces (often a
    single run per stage), p95 is a nearest-rank approximation over
    whatever samples exist -- not a statistically meaningful percentile.
    """
    by_stage: dict[str, list[float]] = {}
    for result in results:
        by_stage.setdefault(result.stage, []).append(result.duration_seconds)

    summary = {}
    for stage, durations in by_stage.items():
        sorted_durations = sorted(durations)
        p95_index = min(len(sorted_durations) - 1, int(0.95 * len(sorted_durations)))
        summary[stage] = {
            "count": len(durations),
            "min": min(durations),
            "mean": mean(durations),
            "max": max(durations),
            "p95": sorted_durations[p95_index],
        }
    return summary
