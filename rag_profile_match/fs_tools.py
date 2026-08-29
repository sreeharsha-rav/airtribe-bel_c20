"""Filesystem tools for the RAG Profile Matcher.

All tools are sandboxed to ROOT_DIR — the agent may only list and read 
files inside this single directory. Resume files may be .txt,
.docx, or .pdf; read_file/search_in_file transparently extract text from
whichever format the file is in.
"""

from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from langchain.tools import tool
from pydantic import BaseModel, Field
from pypdf import PdfReader

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
    """Input for reading a resume file's text content."""

    filepath: str = Field(
        description=(
            "Path relative to root_dir/ of the file to read, e.g. "
            "'engineering/backend_alice.txt'. Supports .txt, .docx, and .pdf files."
        ),
    )


@tool("read_file", args_schema=ReadFileInput)
def read_file(filepath: str) -> dict:
    """Read a resume file (.txt, .docx, or .pdf), extract its text content, and return it with file metadata."""
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
        description="Path relative to root_dir/ to list, e.g. 'engineering' or '.' for everything. Listed recursively.",
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
