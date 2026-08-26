# LLM File System Assistant

A terminal chat agent, built with LangChain + LangGraph, that manages files inside a
single sandboxed directory (`root_dir/`). It's demoed here as a **Resume Filing
Clerk**: `root_dir/` holds candidate resumes organized by role, and the agent can
list, read, keyword-search, and write files there — nothing outside that directory.

The LLM never touches the filesystem directly. It proposes a tool call (e.g.
"search for Kubernetes in engineering/"), the code executes it and returns the
result, and the LLM continues from there. Tool calls stream live in the terminal
as the model makes them.

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
call each one:

- **`list_directory(path=".")`** — lists immediate files/subfolders under a path,
  tagged `DIR`/`FILE`. Used to discover what role folders and candidates exist
  before reading or searching anything.
- **`read_file(path)`** — returns one file's full text. The system prompt
  requires the agent to actually read a resume before describing it, rather than
  guessing from a filename.
- **`keyword_search(query, path=".")`** — a plain-Python, case-insensitive
  substring grep. If `path` is a directory it recursively scans every `.txt`
  file under it; if it's a single file, only that file is scanned. Each hit is
  returned as `relative_path:line_no: line_text`, so results carry enough
  context for the model to decide whether it's a real match without opening the
  file. No indexing — every call re-scans the files.
- **`write_file(path, content)`** — creates a new file (e.g. a shortlist),
  creating parent folders as needed. Blocked by the sandbox guard above and the
  no-overwrite rule.

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

Then chat with the Resume Filing Clerk, e.g. "list the engineering candidates" or
"which resumes mention Kubernetes?". Built-in REPL commands:

- `clear` — clear the current chat history
- `load` — show the current thread's message history
- `reasoning` — toggle display of the model's reasoning
- `exit` / `quit` — end the session
