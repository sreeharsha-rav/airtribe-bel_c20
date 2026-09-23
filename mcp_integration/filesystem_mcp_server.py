"""Filesystem MCP Server -- Part A deliverable.

Wraps fs_core.py's sandboxed filesystem logic as MCP tools over Streamable
HTTP. Every tool keeps returning a structured {success, ..., error} dict
(never raises for app-level failures) so an MCP client can branch on the
result without needing to catch a protocol-level error.
"""

import asyncio
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

import fs_core
from config import settings
from utils import logger

mcp = FastMCP(
    name="filesystem-mcp-server",
    instructions=(
        "Filesystem tools for a sandboxed directory of candidate resumes. "
        "All paths are relative to the sandbox root and may be .txt, .docx, "
        "or .pdf. Use list_files to discover what's available before "
        "reading or searching a specific file."
    ),
)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.tool
def list_files(
    directory: Annotated[
        str,
        Field(description="Path relative to the sandbox root to list, e.g. 'engineering' or '.' for everything. Listed recursively."),
    ] = ".",
    extension: Annotated[
        str | None,
        Field(description="Optional file extension filter, e.g. '.pdf' or 'txt'. If omitted, files of every type are returned."),
    ] = None,
) -> list[dict]:
    """Recursively list files under a directory inside the sandbox root, optionally filtered by extension, with name/size/modified metadata for each."""
    logger.info(f"list_files(directory={directory!r}, extension={extension!r})")
    try:
        target = fs_core.resolve_within_root(directory)
    except ValueError as exc:
        return [{"success": False, "error": {"code": "PATH_ESCAPES_ROOT", "message": str(exc)}}]

    if not target.exists():
        return [{"success": False, "error": {"code": "NOT_FOUND", "message": f"Path not found: {directory}"}}]
    if not target.is_dir():
        return [{"success": False, "error": {"code": "VALIDATION_ERROR", "message": f"Not a directory: {directory}"}}]

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
        entries.append(fs_core.file_metadata(path))
    return entries


@mcp.tool
def read_file(
    filepath: Annotated[
        str,
        Field(description="Path relative to the sandbox root of the file to read, e.g. 'engineering/backend_alice.txt'. Supports .txt, .docx, and .pdf files."),
    ],
) -> dict:
    """Read a resume file (.txt, .docx, or .pdf), extract its text content, and return it with file metadata."""
    logger.info(f"read_file(filepath={filepath!r})")
    try:
        target = fs_core.resolve_within_root(filepath)
    except ValueError as exc:
        return {
            "success": False, "filepath": filepath, "content": None, "metadata": None,
            "error": {"code": "PATH_ESCAPES_ROOT", "message": str(exc)},
        }

    if not target.exists() or not target.is_file():
        return {
            "success": False, "filepath": filepath, "content": None, "metadata": None,
            "error": {"code": "NOT_FOUND", "message": f"File not found: {filepath}"},
        }

    try:
        content = fs_core.extract_text(target)
    except ValueError as exc:
        return {
            "success": False, "filepath": filepath, "content": None,
            "metadata": fs_core.file_metadata(target),
            "error": {"code": "UNSUPPORTED_FORMAT", "message": str(exc)},
        }
    except Exception as exc:
        return {
            "success": False, "filepath": filepath, "content": None,
            "metadata": fs_core.file_metadata(target),
            "error": {"code": "FILE_PROCESSING_ERROR", "message": f"Could not read '{filepath}': {exc}"},
        }

    return {
        "success": True, "filepath": filepath, "content": content,
        "metadata": fs_core.file_metadata(target), "error": None,
    }


@mcp.tool
def search_in_file(
    filepath: Annotated[
        str,
        Field(description="Path relative to the sandbox root of the file to search, e.g. 'engineering/backend_alice.txt'. Supports .txt, .docx, and .pdf files."),
    ],
    keyword: Annotated[str, Field(description="The keyword or phrase to search for, case-insensitive.")],
) -> dict:
    """Search for a keyword or phrase inside one resume file (.txt, .docx, or .pdf), returning every match with surrounding context. Case-insensitive."""
    logger.info(f"search_in_file(filepath={filepath!r}, keyword={keyword!r})")
    empty_result = {"success": False, "filepath": filepath, "keyword": keyword, "matches": [], "match_count": 0}

    if not keyword.strip():
        return {**empty_result, "error": {"code": "VALIDATION_ERROR", "message": "Please provide a non-empty search keyword."}}

    try:
        target = fs_core.resolve_within_root(filepath)
    except ValueError as exc:
        return {**empty_result, "error": {"code": "PATH_ESCAPES_ROOT", "message": str(exc)}}

    if not target.exists() or not target.is_file():
        return {**empty_result, "error": {"code": "NOT_FOUND", "message": f"File not found: {filepath}"}}

    try:
        content = fs_core.extract_text(target)
    except Exception as exc:
        return {**empty_result, "error": {"code": "FILE_PROCESSING_ERROR", "message": f"Could not read '{filepath}': {exc}"}}

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
        "success": True, "filepath": filepath, "keyword": keyword,
        "matches": matches, "match_count": len(matches), "error": None,
    }


@mcp.tool
def write_file(
    filepath: Annotated[
        str,
        Field(description="Path relative to the sandbox root for the new file, e.g. 'shortlist_eng.txt'. Must not already exist."),
    ],
    content: Annotated[str, Field(description="The full text content to write to the file.")],
) -> dict:
    """Create a new text file inside the sandbox root with the given content, creating parent directories as needed. Refuses to overwrite an existing file."""
    logger.info(f"write_file(filepath={filepath!r}, content_length={len(content)})")
    try:
        target = fs_core.resolve_within_root(filepath)
    except ValueError as exc:
        return {"success": False, "filepath": filepath, "error": {"code": "PATH_ESCAPES_ROOT", "message": str(exc)}}

    if target.is_dir():
        return {
            "success": False, "filepath": filepath,
            "error": {"code": "VALIDATION_ERROR", "message": f"Cannot write to '{filepath}': it is a directory."},
        }
    if target.exists():
        return {
            "success": False, "filepath": filepath,
            "error": {"code": "VALIDATION_ERROR", "message": f"Refusing to overwrite existing file: {filepath}"},
        }

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return {
            "success": False, "filepath": filepath,
            "error": {"code": "PERMISSION_DENIED", "message": f"Could not write '{filepath}': {exc}"},
        }

    return {"success": True, "filepath": filepath, "bytes_written": len(content.encode("utf-8")), "error": None}


@mcp.tool
async def batch_process(
    files: Annotated[
        list[str] | None,
        Field(description="Explicit list of paths (relative to the sandbox root) to process. Mutually exclusive with 'directory'."),
    ] = None,
    directory: Annotated[
        str | None,
        Field(description="Directory (relative to the sandbox root) to expand into a file list, the same way list_files would. Mutually exclusive with 'files'."),
    ] = None,
    extension: Annotated[
        str | None,
        Field(description="Optional extension filter when expanding 'directory', e.g. '.pdf'."),
    ] = None,
    recursive: Annotated[
        bool,
        Field(description="Whether to recurse into subdirectories when expanding 'directory'."),
    ] = True,
) -> dict:
    """Read and extract text/metadata for many files at once (bounded concurrency), returning per-file status and aggregate counts. Provide either 'files' or 'directory', not both."""
    logger.info(f"batch_process(files={files!r}, directory={directory!r}, extension={extension!r}, recursive={recursive!r})")

    if files and directory:
        return {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Provide either 'files' or 'directory', not both."}}
    if not files and not directory:
        return {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Provide either 'files' or 'directory'."}}

    if directory is not None:
        try:
            target_dir = fs_core.resolve_within_root(directory)
        except ValueError as exc:
            return {"success": False, "error": {"code": "PATH_ESCAPES_ROOT", "message": str(exc)}}
        if not target_dir.exists() or not target_dir.is_dir():
            return {"success": False, "error": {"code": "NOT_FOUND", "message": f"Directory not found: {directory}"}}

        normalized_ext = None
        if extension:
            normalized_ext = extension.lower()
            if not normalized_ext.startswith("."):
                normalized_ext = f".{normalized_ext}"

        walker = target_dir.rglob("*") if recursive else target_dir.glob("*")
        candidates = [
            # as_posix() keeps expanded paths forward-slash-separated on every
            # OS (notably Windows), matching fs_core.file_metadata's "path".
            p.relative_to(settings.ROOT_DIR).as_posix() for p in sorted(walker)
            if p.is_file() and (normalized_ext is None or p.suffix.lower() == normalized_ext)
        ]
    else:
        candidates = list(files)

    semaphore = asyncio.Semaphore(settings.BATCH_MAX_CONCURRENCY)

    async def process_one(rel_path: str) -> dict:
        async with semaphore:
            try:
                target = fs_core.resolve_within_root(rel_path)
            except ValueError as exc:
                return {"path": rel_path, "status": "error", "error": {"code": "PATH_ESCAPES_ROOT", "message": str(exc)}}

            if not target.exists() or not target.is_file():
                return {"path": rel_path, "status": "error", "error": {"code": "NOT_FOUND", "message": f"File not found: {rel_path}"}}
            if not fs_core.is_allowed_extension(target):
                return {"path": rel_path, "status": "skipped", "reason": f"Extension '{target.suffix}' is not in ALLOWED_EXTENSIONS."}
            if fs_core.exceeds_max_size(target):
                return {"path": rel_path, "status": "skipped", "reason": f"File exceeds MAX_FILE_SIZE_BYTES ({settings.MAX_FILE_SIZE_BYTES})."}

            try:
                content = await asyncio.to_thread(fs_core.extract_text, target)
            except Exception as exc:
                return {"path": rel_path, "status": "error", "error": {"code": "FILE_PROCESSING_ERROR", "message": f"Unable to process '{rel_path}': {exc}"}}

            return {
                "path": rel_path, "status": "success",
                "result": {"content": content, "metadata": fs_core.file_metadata(target)},
            }

    results = await asyncio.gather(*(process_one(p) for p in candidates))

    processed = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "error")
    skipped = sum(1 for r in results if r["status"] == "skipped")

    return {
        "success": True,
        "total_files": len(results),
        "processed": processed,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }


if __name__ == "__main__":
    mcp.run(transport="http", host=settings.MCP_HOST, port=settings.MCP_PORT)
