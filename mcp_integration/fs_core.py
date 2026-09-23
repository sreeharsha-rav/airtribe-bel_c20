"""Pure filesystem logic for the Filesystem MCP Server.

No MCP or LangChain decoration lives here -- filesystem_mcp_server.py wraps
these functions as MCP tools. Kept separate so the sandboxing/extraction
logic can be unit-tested without spinning up a server.
"""

import threading
import uuid
from dataclasses import dataclass, field
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
        # as_posix() keeps the reported path forward-slash-separated on every
        # OS (notably Windows) so MCP tool results are portable regardless of
        # the host filesystem.
        "path": path.relative_to(settings.ROOT_DIR).as_posix(),
        "extension": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def is_allowed_extension(path: Path) -> bool:
    return path.suffix.lower() in settings.ALLOWED_EXTENSIONS


def exceeds_max_size(path: Path) -> bool:
    return path.stat().st_size > settings.MAX_FILE_SIZE_BYTES


@dataclass
class _WatchState:
    directory: Path
    recursive: bool
    allowed_extensions: set[str] | None
    poll_interval_seconds: float
    stop_event: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)
    known: dict[str, dict] = field(default_factory=dict)
    pending_events: list[dict] = field(default_factory=list)
    active: bool = True
    thread: threading.Thread | None = None


_watches: dict[str, _WatchState] = {}


def _scan(state: "_WatchState") -> dict[str, int]:
    # pathlib's glob()/rglob() silently swallow OSError from the underlying
    # scandir() call (a CPython implementation detail), so scanning a
    # directory that has been deleted out from under the watch quietly
    # returns an empty result instead of raising. Check explicitly so a
    # deleted watch directory surfaces as the runtime failure spec §7
    # describes, rather than the watch going silently and permanently inert.
    if not state.directory.is_dir():
        raise FileNotFoundError(f"Watched directory no longer exists: {state.directory}")
    walker = state.directory.rglob("*") if state.recursive else state.directory.glob("*")
    found = {}
    for path in walker:
        if not path.is_file():
            continue
        if state.allowed_extensions and path.suffix.lower() not in state.allowed_extensions:
            continue
        # as_posix() keeps the reported path forward-slash-separated on every
        # OS (notably Windows), matching file_metadata's convention -- see the
        # comment there.
        found[path.relative_to(state.directory).as_posix()] = path.stat().st_size
    return found


def _watch_loop(state: "_WatchState") -> None:
    try:
        while not state.stop_event.is_set():
            current = _scan(state)
            now = datetime.now(timezone.utc).isoformat()
            with state.lock:
                for rel_path, size in current.items():
                    entry = state.known.get(rel_path)
                    if entry is None:
                        state.known[rel_path] = {"size": size, "stable": False, "detected_at": now}
                        state.pending_events.append(
                            {"path": rel_path, "filename": Path(rel_path).name, "detected_at": now, "ready": False}
                        )
                    elif not entry["stable"]:
                        if entry["size"] == size:
                            entry["stable"] = True
                            state.pending_events.append(
                                {"path": rel_path, "filename": Path(rel_path).name,
                                 "detected_at": entry["detected_at"], "ready": True}
                            )
                        else:
                            entry["size"] = size
            state.stop_event.wait(state.poll_interval_seconds)
    except Exception as exc:
        with state.lock:
            state.pending_events.append({"type": "error", "message": f"Watch loop failed: {exc}"})
    finally:
        with state.lock:
            state.active = False


def start_watch(
    directory_path: str,
    recursive: bool = False,
    allowed_extensions: list[str] | None = None,
    poll_interval_seconds: float | None = None,
) -> dict:
    try:
        target = resolve_within_root(directory_path)
    except ValueError as exc:
        return {"success": False, "error": {"code": "PATH_ESCAPES_ROOT", "message": str(exc)}}

    if not target.exists() or not target.is_dir():
        return {"success": False, "error": {"code": "NOT_FOUND", "message": f"Directory not found: {directory_path}"}}

    normalized_exts = None
    if allowed_extensions:
        normalized_exts = {
            ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in allowed_extensions
        }

    state = _WatchState(
        directory=target,
        recursive=recursive,
        allowed_extensions=normalized_exts,
        poll_interval_seconds=poll_interval_seconds or settings.WATCH_POLL_INTERVAL_SECONDS,
    )
    now = datetime.now(timezone.utc).isoformat()
    for rel_path, size in _scan(state).items():
        state.known[rel_path] = {"size": size, "stable": True, "detected_at": now}

    watch_id = uuid.uuid4().hex
    state.thread = threading.Thread(target=_watch_loop, args=(state,), daemon=True)
    _watches[watch_id] = state
    state.thread.start()

    return {"success": True, "watch_id": watch_id, "error": None}


def poll_watch(watch_id: str) -> dict:
    state = _watches.get(watch_id)
    if state is None:
        return {"success": False, "error": {"code": "VALIDATION_ERROR", "message": f"Unknown watch_id: {watch_id}"}}

    with state.lock:
        events = state.pending_events[:]
        state.pending_events.clear()
        active = state.active

    return {"success": True, "watch_id": watch_id, "events": events, "active": active, "error": None}


def stop_watch(watch_id: str) -> dict:
    state = _watches.pop(watch_id, None)
    if state is None:
        return {"success": False, "error": {"code": "VALIDATION_ERROR", "message": f"Unknown watch_id: {watch_id}"}}

    state.stop_event.set()
    if state.thread is not None:
        state.thread.join(timeout=max(state.poll_interval_seconds * 2, 2))

    return {"success": True, "watch_id": watch_id, "stopped": True, "error": None}
