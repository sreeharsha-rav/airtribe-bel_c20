"""Pure filesystem logic for the Filesystem MCP Server.

No MCP or LangChain decoration lives here -- filesystem_mcp_server.py wraps
these functions as MCP tools. Kept separate so the sandboxing/extraction
logic can be unit-tested without spinning up a server.
"""

from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from config import settings


def resolve_within_root(relative_path: str) -> Path:
    """Resolves a relative path to an absolute path inside settings.ROOT_DIR.

    Rejects absolute paths and ".." segments before joining, since
    `Path(root) / "/abs/path"` would otherwise silently discard `root`
    and resolve to an unrelated absolute path.
    """
    candidate_parts = Path(relative_path)
    if candidate_parts.is_absolute() or ".." in candidate_parts.parts:
        raise ValueError(f"Path '{relative_path}' is not allowed -- it must stay inside the sandbox root.")

    candidate = (settings.ROOT_DIR / candidate_parts).resolve()
    if candidate != settings.ROOT_DIR and settings.ROOT_DIR not in candidate.parents:
        raise ValueError(f"Path '{relative_path}' escapes the sandbox root.")
    return candidate


def extract_text(path: Path) -> str:
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


def file_metadata(path: Path) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path.relative_to(settings.ROOT_DIR)),
        "extension": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def is_allowed_extension(path: Path) -> bool:
    return path.suffix.lower() in settings.ALLOWED_EXTENSIONS


def exceeds_max_size(path: Path) -> bool:
    return path.stat().st_size > settings.MAX_FILE_SIZE_BYTES
