# MCP Integration

An MCP-based rebuild of `llm_file_assistant`'s filesystem tooling: the
sandboxed file tools move out of a directly-imported LangChain tool module
and behind a standalone **Filesystem MCP Server**, and the chat agent
(**`matching_agent.py`**) is refactored to discover and call those tools
exclusively through an MCP client -- no direct filesystem access from the
agent's primary path.

Two processes:

```
matching_agent.py (LangGraph agent + REPL, host)
        |  langchain.mcp.MCPAdapter, MCP over Streamable HTTP
        v
filesystem_mcp_server.py (FastMCP, Docker)
        |
        v
sample_data/resumes/
```

Full design rationale, tool specs, error handling, and the phased
implementation plan live in [`docs/spec.md`](docs/spec.md);
[`docs/architecture.md`](docs/architecture.md) and
[`docs/workflow-diagram.md`](docs/workflow-diagram.md) cover the runtime
picture in more depth.

## Prerequisites

- Python >= 3.12
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Docker (to run the MCP server)
- An [OpenRouter](https://openrouter.ai/) API key (agent side)

## Setup

```bash
cp sample.env .env
# fill in OPENROUTER_API_KEY (and optionally LANGSMITH_*) in .env
uv sync
```

## Running

Start the MCP server (Docker):

```bash
docker compose up --build
```

In a second terminal, run the agent (always on the host):

```bash
uv run python matching_agent.py
```

REPL commands: `clear` (wipe chat history), `load` (show previous history),
`reasoning` (toggle showing the model's reasoning), `exit`/`quit`.

## Testing

```bash
uv run pytest tests/ -v
```

`tests/test_mcp_server.py`, `test_batch_process.py`, and
`test_watch_directory.py` run against the `FastMCP` server in-process (no
Docker needed). `tests/test_matching_agent_mcp.py` spins up a real local HTTP
instance of the server and connects to it through `MCPAdapter`, with the chat
model stubbed -- no live `OPENROUTER_API_KEY` required to run the suite.

## Repository layout

See [`docs/spec.md`](docs/spec.md) §3.
