# LLM File System Assistant

A terminal chat agent, built with LangChain + LangGraph, that manages files inside a
single sandboxed directory (`root_dir/`). It's demoed here as a **Resume Filing
Clerk**: `root_dir/` holds candidate resumes organized by role, in `.txt`, `.docx`,
or `.pdf` format, and the agent can list, read, keyword-search, and write files
there — nothing outside that directory.

The LLM never touches the filesystem directly. It proposes a tool call (e.g.
"search for Python in resume_john_doe.pdf"), the code executes it and returns a
structured result, and the LLM continues from there. Tool calls stream live in the
terminal as the model makes them.

## Design

### Sandboxing

Every tool call is resolved through one guard, `_resolve_within_root` in `fs_tools.py`,
before it touches disk:

1. **Reject upfront** — an absolute path or any `..` segment in the LLM-supplied
   path is rejected immediately. This closes a real pathlib gotcha where
   `Path(root) / "/etc/passwd"` silently discards `root` instead of raising.
2. **Verify after resolving** — the path is resolved to a real absolute path and
   checked to actually be `root_dir/` or a descendant of it, as defense in depth.

A violation returns a plain string (e.g. `"...escapes the root_dir/ sandbox."`)
instead of raising, so the agent sees it as a normal tool result, not a crash.
`write_file` adds one more rule on top: it refuses to overwrite a path that
already exists, so the agent can only create new files, never clobber one.

### Tools

Each tool has a pydantic `args_schema` giving the model an explicit name,
description, and per-argument description, so it knows exactly when and how to
call each one. Every tool returns a structured `dict` (or `list[dict]`) rather
than plain text — a `success`/`error` field the model can act on, not just a
string to interpret:

- **`list_files(directory=".", extension=None)`** — recursively lists every file
  under a directory (`directory="."` covers the whole sandbox), optionally
  filtered to one extension (`".pdf"`, or just `"pdf"`). Returns a list of
  `{name, path, extension, size_bytes, modified}` dicts. Used to discover what
  candidates and formats exist before reading or searching anything.
- **`read_file(filepath)`** — extracts and returns one file's full text plus
  metadata, regardless of whether it's `.txt`, `.docx` (via `python-docx`), or
  `.pdf` (via `pypdf`). The system prompt requires the agent to actually read a
  resume before describing it, rather than guessing from a filename.
- **`search_in_file(filepath, keyword)`** — a plain-Python, case-insensitive
  substring search *within a single file* (any of the three formats). Returns
  every match as `{line_number, context}`, where `context` is a character
  window around the hit. Because it's single-file, finding "who mentions X"
  across candidates means the agent lists files first, then searches each one —
  no hidden batch/recursive search. No indexing — every call re-scans the file.
- **`write_file(filepath, content)`** — creates a new text file (e.g. a
  shortlist), creating parent folders as needed. Blocked by the sandbox guard
  above and a no-overwrite rule (refuses to touch a path that already exists).

## Prerequisites

- Python >= 3.12
- An [OpenRouter](https://openrouter.ai/) API key

## Setup

```bash
cd llm_file_assistant
pip install -e .          # or: uv sync
cp sample.env .env
```

Edit `.env` and set `OPENROUTER_API_KEY` to your key.

## Running

```bash
python main.py
```

Then chat with the Resume Filing Clerk, e.g. "list all the PDF resumes" or "find
resumes mentioning Python experience". Built-in REPL commands:

- `clear` — clear the current chat history
- `load` — show the current thread's message history
- `reasoning` — toggle display of the model's reasoning
- `exit` / `quit` — end the session
