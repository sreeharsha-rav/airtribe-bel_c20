"""Filesystem tools for the Resume Filing Clerk agent.

All tools are sandboxed to ROOT_DIR — the agent may only list, read, search,
and write files inside this single directory.
"""

from pathlib import Path

from langchain.tools import tool
from pydantic import BaseModel, Field

from utils import logger

ROOT_DIR = (Path(__file__).parent / "root_dir").resolve()


def _resolve_within_root(relative_path: str) -> Path:
    """Resolves a relative path to an absolute path inside ROOT_DIR.

    Rejects absolute paths and ".." segments before joining, since
    `Path(root) / "/abs/path"` would otherwise silently discard `root`
    and resolve to an unrelated absolute path.
    """
    candidate_parts = Path(relative_path)
    if candidate_parts.is_absolute() or ".." in candidate_parts.parts:
        raise ValueError(f"Path '{relative_path}' is not allowed — it must stay inside root_dir/.")

    candidate = (ROOT_DIR / candidate_parts).resolve()
    if candidate != ROOT_DIR and ROOT_DIR not in candidate.parents:
        raise ValueError(f"Path '{relative_path}' escapes the root_dir/ sandbox.")
    return candidate


class ListDirectoryInput(BaseModel):
    """Input for listing the contents of a directory inside root_dir/."""

    path: str = Field(
        default=".",
        description="Path relative to root_dir/ to list, e.g. 'engineering' or '.' for the top level.",
    )


@tool("list_directory", args_schema=ListDirectoryInput)
def list_directory(path: str = ".") -> str:
    """List the files and subfolders under a path inside the root_dir/ sandbox."""
    logger.info(f"list_directory(path={path!r})")
    try:
        target = _resolve_within_root(path)
    except ValueError as exc:
        return str(exc)

    if not target.exists():
        return f"Path not found: {path}"
    if not target.is_dir():
        return f"Not a directory: {path}"

    entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    if not entries:
        return "(empty)"
    lines = [
        f"{'DIR ' if entry.is_dir() else 'FILE'} {entry.relative_to(ROOT_DIR)}"
        for entry in entries
    ]
    return "\n".join(lines)


class ReadFileInput(BaseModel):
    """Input for reading the full text of one file inside root_dir/."""

    path: str = Field(
        description="Path relative to root_dir/ of the file to read, e.g. 'engineering/backend_alice.txt'.",
    )


@tool("read_file", args_schema=ReadFileInput)
def read_file(path: str) -> str:
    """Read and return the full text contents of a single file inside root_dir/."""
    logger.info(f"read_file(path={path!r})")
    try:
        target = _resolve_within_root(path)
    except ValueError as exc:
        return str(exc)

    if not target.exists() or not target.is_file():
        return f"File not found: {path}"
    return target.read_text(encoding="utf-8")


class KeywordSearchInput(BaseModel):
    """Input for a case-insensitive keyword/phrase search across text files."""

    query: str = Field(description="The keyword or phrase to search for, case-insensitive.")
    path: str = Field(
        default=".",
        description=(
            "Path relative to root_dir/ to search under. If it points to a directory, "
            "all .txt files under it are searched recursively; if it points to a file, "
            "only that file is searched."
        ),
    )


@tool("keyword_search", args_schema=KeywordSearchInput)
def keyword_search(query: str, path: str = ".") -> str:
    """Search for a keyword or phrase across .txt files inside root_dir/, returning matching filenames and line numbers."""
    logger.info(f"keyword_search(query={query!r}, path={path!r})")
    if not query.strip():
        return "Please provide a non-empty search query."

    try:
        target = _resolve_within_root(path)
    except ValueError as exc:
        return str(exc)

    if not target.exists():
        return f"Path not found: {path}"

    files = [target] if target.is_file() else sorted(target.rglob("*.txt"))
    query_lower = query.lower()
    results = []
    for file in files:
        rel = file.relative_to(ROOT_DIR)
        for line_no, line in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
            if query_lower in line.lower():
                results.append(f"{rel}:{line_no}: {line.strip()}")

    return "\n".join(results) if results else f"No matches for '{query}'."


class WriteFileInput(BaseModel):
    """Input for creating a new file inside root_dir/."""

    path: str = Field(
        description="Path relative to root_dir/ for the new file, e.g. 'shortlist_eng.txt'. Must not already exist.",
    )
    content: str = Field(description="The full text content to write to the file.")


@tool("write_file", args_schema=WriteFileInput)
def write_file(path: str, content: str) -> str:
    """Create a new file inside root_dir/ with the given content. Refuses to overwrite an existing file."""
    logger.info(f"write_file(path={path!r}, content_length={len(content)})")
    try:
        target = _resolve_within_root(path)
    except ValueError as exc:
        return str(exc)

    if target.is_dir():
        return f"Cannot write to '{path}': it is a directory."
    if target.exists():
        return f"Refusing to overwrite existing file: {path}"

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"Could not write '{path}': {exc}"
    return f"Wrote {len(content)} characters to {path}"
