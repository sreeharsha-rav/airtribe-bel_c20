"""
Performance metrics for the RAG profile matching pipeline.

- Retrieval accuracy: whether job_matcher.semantic_search's top-K actually
  contains the resumes that should match a given job description. Needs a
  small hand-labeled ground-truth mapping of job path -> expected candidate
  resume paths (see rag_analysis.ipynb).
- Latency: wall-clock time per pipeline stage (embedding, Qdrant query,
  scoring), to spot slow stages.

SCAFFOLD -- no working logic yet. Depends on resume_rag.py's
embedding/vector-store functions and job_matcher.py's search/scoring
functions being implemented first.
"""

from dataclasses import dataclass
from typing import Callable


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
    computes precision@k / recall@k against that job's expected resume paths.

    SCAFFOLD -- not yet implemented.
    """
    raise NotImplementedError


@dataclass
class LatencyResult:
    stage: str
    duration_seconds: float


def measure_latency(stage: str, fn: Callable, *args, **kwargs) -> tuple[LatencyResult, object]:
    """Times a single pipeline stage call (e.g. embed_job_description,
    semantic_search, score_and_rank) and returns (LatencyResult, fn's result).

    SCAFFOLD -- not yet implemented. Sketch:
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        return LatencyResult(stage, time.perf_counter() - start), result
    """
    raise NotImplementedError


def summarize_latencies(results: list[LatencyResult]) -> dict:
    """Aggregates a list of LatencyResult into per-stage min/mean/max/p95,
    for reporting in the notebook.

    SCAFFOLD -- not yet implemented.
    """
    raise NotImplementedError
