"""Phase 1 pipeline: Parse JD -> Extract Requirements -> Search Resumes ->
Rank Candidates -> Generate Report -> END.

A single, non-interactive StateGraph pass -- no LLM call anywhere in this
phase, no Human Feedback Loop yet (Phase 2). See DESIGN.md's "Phase 1 --
node-by-node spec" and AGENT_ARCHITECTURE.md for the full design this
implements.
"""

import uuid
from typing import Literal, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from rich.console import Console
from rich.table import Table

import config
from fs_tools import read_file
from jd_parser import extract_must_have_requirements, extract_nice_to_have_requirements, split_job_sections
from ranking import MatchResult, score_and_rank
from retrieval import embed_job_description, semantic_search

console = Console(record=True)


class AgentState(TypedDict, total=False):
    thread_id: str
    jd_source_path: str
    jd_text: str
    jd_sections: dict[str, str]
    must_haves: list[str]
    nice_to_haves: list[str]
    candidate_pool: list[dict]
    match_results: list[MatchResult]
    report: str
    error: str | None


# --- Nodes -------------------------------------------------------------------

def parse_jd(state: AgentState) -> dict:
    """Reads the JD file via the sandboxed fs_tools.read_file. Sets `error`
    (short-circuiting to END) on a bad/missing path -- no retry loop in
    Phase 1, that's conversational territory (Phase 2).
    """
    result = read_file.invoke({"filepath": state["jd_source_path"]})
    if not result["success"]:
        return {"error": result["error"]}
    return {"jd_text": result["content"]}


def route_after_parse_jd(state: AgentState) -> Literal["extract_requirements", "__end__"]:
    if state.get("error"):
        return END
    return "extract_requirements"


def extract_requirements(state: AgentState) -> dict:
    """Purely algorithmic (Q3, Phase 1) -- every posting under
    rag_profile_match/root_dir/jobs/ already follows the same 4-heading
    format jd_parser's regex parses correctly.
    """
    jd_text = state["jd_text"]
    return {
        "jd_sections": split_job_sections(jd_text),
        "must_haves": extract_must_have_requirements(jd_text),
        "nice_to_haves": extract_nice_to_have_requirements(jd_text),
    }


def search_resumes(state: AgentState) -> dict:
    """Embeds jd_sections' descriptive prose (must-haves deliberately
    excluded -- see retrieval.embed_job_description) and runs hybrid RRF
    search. Over-fetches (max(top_k*3, 15)) so Rank Candidates' hard
    must-have filter has headroom before shrinking the pool.
    """
    jd_vectors = embed_job_description(state["jd_sections"])
    pool_size = max(config.MATCH_TOP_K * 3, 15)
    candidate_pool = semantic_search(jd_vectors, top_k=pool_size)
    return {"candidate_pool": candidate_pool}


def rank_candidates(state: AgentState) -> dict:
    """Hard must-have filter + min-max score normalization, plus a
    nice-to-have overlap check for survivors (display only).
    """
    match_results = score_and_rank(
        state["candidate_pool"],
        state["must_haves"],
        state["nice_to_haves"],
    )
    return {"match_results": match_results[: config.MATCH_TOP_K]}


def _render_report(match_results: list[MatchResult], jd_source_path: str) -> str:
    if not match_results:
        table_or_message = "[yellow]No candidates satisfied every must-have requirement.[/yellow]"
        console.print(table_or_message)
        return console.export_text(clear=True)

    table = Table(title=f"Candidate Shortlist — {jd_source_path}")
    table.add_column("Rank", justify="right")
    table.add_column("Candidate")
    table.add_column("Score", justify="right")
    table.add_column("Matched Skills")
    table.add_column("Nice-to-haves Present")
    table.add_column("Reasoning")
    table.add_column("Best Excerpt")

    for rank, result in enumerate(match_results, start=1):
        best_excerpt = result.relevant_excerpts[0] if result.relevant_excerpts else "—"
        if len(best_excerpt) > 200:
            best_excerpt = best_excerpt[:200] + "..."
        table.add_row(
            str(rank),
            result.candidate_name or result.resume_path,
            f"{result.match_score:.1f}",
            ", ".join(result.matched_skills) or "—",
            ", ".join(result.nice_to_haves_satisfied) or "—",
            result.reasoning,
            best_excerpt,
        )

    console.print(table)
    return console.export_text(clear=True)


def generate_report(state: AgentState) -> dict:
    """Deterministic rich-rendered table -- no LLM call. Report text is kept
    in state (not just printed) so Phase 2's conversational agent can seed
    it as the first turn's context.
    """
    report = _render_report(state["match_results"], state["jd_source_path"])
    return {"report": report}


# --- Graph ---------------------------------------------------------------------

def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("parse_jd", parse_jd)
    builder.add_node("extract_requirements", extract_requirements)
    builder.add_node("search_resumes", search_resumes)
    builder.add_node("rank_candidates", rank_candidates)
    builder.add_node("generate_report", generate_report)

    builder.add_edge(START, "parse_jd")
    builder.add_conditional_edges("parse_jd", route_after_parse_jd)
    builder.add_edge("extract_requirements", "search_resumes")
    builder.add_edge("search_resumes", "rank_candidates")
    builder.add_edge("rank_candidates", "generate_report")
    builder.add_edge("generate_report", END)

    return builder.compile(checkpointer=InMemorySaver())


# --- CLI entrypoint --------------------------------------------------------------

def main() -> None:
    load_dotenv()
    graph = build_graph()

    jd_source_path = console.input("[bold blue]JD path[/bold blue] (relative to root_dir/, e.g. jobs/senior_backend_engineer.txt): ").strip()

    thread_id = str(uuid.uuid4())
    config_dict = {"configurable": {"thread_id": thread_id}}
    initial_state: AgentState = {"thread_id": thread_id, "jd_source_path": jd_source_path}

    result = graph.invoke(initial_state, config_dict)

    if result.get("error"):
        console.print(f"[bold red]Error:[/bold red] {result['error']}")
        return


if __name__ == "__main__":
    main()
