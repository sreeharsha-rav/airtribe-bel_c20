"""Filesystem tools for the Agentic Profile Matcher.

Duplicated from llm_file_assistant/fs_tools.py (DESIGN.md's Reuse strategy,
Q1) with one change: ROOT_DIR points at rag_profile_match's root_dir/ (the
shared jobs/ and resumes/ tree), not a project-local one. All tools are
sandboxed to ROOT_DIR. Resume/job files may be .txt, .docx, or .pdf;
read_file/search_in_file transparently extract text from whichever format
the file is in.
"""

from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from langchain.tools import tool
from pydantic import BaseModel, Field
from pypdf import PdfReader

from utils import logger

ROOT_DIR = (Path(__file__).parent.parent / "rag_profile_match" / "root_dir").resolve()


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


def _extract_text(path: Path) -> str:
    """Extracts plain text content from a .txt, .docx, or .pdf file."""
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8")
    if suffix == ".docx":
        document = Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    raise ValueError(f"Unsupported file type '{suffix}'. Supported types: .txt, .docx, .pdf")


def _file_metadata(path: Path) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path.relative_to(ROOT_DIR)),
        "extension": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


class ReadFileInput(BaseModel):
    """Input for reading a job/resume file's text content."""

    filepath: str = Field(
        description=(
            "Path relative to root_dir/ of the file to read, e.g. "
            "'jobs/senior_backend_engineer.txt'. Supports .txt, .docx, and .pdf files."
        ),
    )


@tool("read_file", args_schema=ReadFileInput)
def read_file(filepath: str) -> dict:
    """Read a job or resume file (.txt, .docx, or .pdf), extract its text content, and return it with file metadata."""
    logger.info(f"read_file(filepath={filepath!r})")
    try:
        target = _resolve_within_root(filepath)
    except ValueError as exc:
        return {"success": False, "filepath": filepath, "content": None, "metadata": None, "error": str(exc)}

    if not target.exists() or not target.is_file():
        return {
            "success": False,
            "filepath": filepath,
            "content": None,
            "metadata": None,
            "error": f"File not found: {filepath}",
        }

    try:
        content = _extract_text(target)
    except Exception as exc:
        return {
            "success": False,
            "filepath": filepath,
            "content": None,
            "metadata": _file_metadata(target),
            "error": f"Could not read '{filepath}': {exc}",
        }

    return {
        "success": True,
        "filepath": filepath,
        "content": content,
        "metadata": _file_metadata(target),
        "error": None,
    }


class ListFilesInput(BaseModel):
    """Input for recursively listing files under a directory inside root_dir/."""

    directory: str = Field(
        default=".",
        description="Path relative to root_dir/ to list, e.g. 'resumes' or '.' for everything. Listed recursively.",
    )
    extension: str | None = Field(
        default=None,
        description="Optional file extension filter, e.g. '.pdf' or 'txt'. If omitted, files of every type are returned.",
    )


@tool("list_files", args_schema=ListFilesInput)
def list_files(directory: str = ".", extension: str | None = None) -> list:
    """Recursively list files under a directory inside root_dir/, optionally filtered by extension, with name/size/modified metadata for each."""
    logger.info(f"list_files(directory={directory!r}, extension={extension!r})")
    try:
        target = _resolve_within_root(directory)
    except ValueError as exc:
        return [{"error": str(exc)}]

    if not target.exists():
        return [{"error": f"Path not found: {directory}"}]
    if not target.is_dir():
        return [{"error": f"Not a directory: {directory}"}]

    normalized_ext = None
    if extension:
        normalized_ext = extension.lower()
        if not normalized_ext.startswith("."):
            normalized_ext = f".{normalized_ext}"

    entries = []
    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        if normalized_ext and path.suffix.lower() != normalized_ext:
            continue
        entries.append(_file_metadata(path))
    return entries


class WriteFileInput(BaseModel):
    """Input for creating a new file inside root_dir/."""

    filepath: str = Field(
        description="Path relative to root_dir/ for the new file, e.g. 'shortlist_backend.txt'. Must not already exist.",
    )
    content: str = Field(description="The full text content to write to the file.")


@tool("write_file", args_schema=WriteFileInput)
def write_file(filepath: str, content: str) -> dict:
    """Create a new text file inside root_dir/ with the given content, creating parent directories as needed. Refuses to overwrite an existing file."""
    logger.info(f"write_file(filepath={filepath!r}, content_length={len(content)})")
    try:
        target = _resolve_within_root(filepath)
    except ValueError as exc:
        return {"success": False, "filepath": filepath, "error": str(exc)}

    if target.is_dir():
        return {"success": False, "filepath": filepath, "error": f"Cannot write to '{filepath}': it is a directory."}
    if target.exists():
        return {"success": False, "filepath": filepath, "error": f"Refusing to overwrite existing file: {filepath}"}

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return {"success": False, "filepath": filepath, "error": f"Could not write '{filepath}': {exc}"}

    return {
        "success": True,
        "filepath": filepath,
        "bytes_written": len(content.encode("utf-8")),
        "error": None,
    }


class SearchInFileInput(BaseModel):
    """Input for a case-insensitive keyword/phrase search within a single file."""

    filepath: str = Field(
        description=(
            "Path relative to root_dir/ of the file to search, e.g. "
            "'resumes/engineering/backend_alice.txt'. Supports .txt, .docx, and .pdf files."
        ),
    )
    keyword: str = Field(description="The keyword or phrase to search for, case-insensitive.")


@tool("search_in_file", args_schema=SearchInFileInput)
def search_in_file(filepath: str, keyword: str) -> dict:
    """Search for a keyword or phrase inside one job/resume file (.txt, .docx, or .pdf), returning every match with surrounding context. Case-insensitive."""
    logger.info(f"search_in_file(filepath={filepath!r}, keyword={keyword!r})")
    empty_result = {"success": False, "filepath": filepath, "keyword": keyword, "matches": [], "match_count": 0}

    if not keyword.strip():
        return {**empty_result, "error": "Please provide a non-empty search keyword."}

    try:
        target = _resolve_within_root(filepath)
    except ValueError as exc:
        return {**empty_result, "error": str(exc)}

    if not target.exists() or not target.is_file():
        return {**empty_result, "error": f"File not found: {filepath}"}

    try:
        content = _extract_text(target)
    except Exception as exc:
        return {**empty_result, "error": f"Could not read '{filepath}': {exc}"}

    context_window = 60
    keyword_lower = keyword.lower()
    content_lower = content.lower()
    matches = []
    search_from = 0
    while True:
        idx = content_lower.find(keyword_lower, search_from)
        if idx == -1:
            break
        line_number = content.count("\n", 0, idx) + 1
        ctx_start = max(0, idx - context_window)
        ctx_end = min(len(content), idx + len(keyword) + context_window)
        context = " ".join(content[ctx_start:ctx_end].split())
        matches.append({"line_number": line_number, "context": context})
        search_from = idx + len(keyword_lower)

    return {
        "success": True,
        "filepath": filepath,
        "keyword": keyword,
        "matches": matches,
        "match_count": len(matches),
        "error": None,
    }
