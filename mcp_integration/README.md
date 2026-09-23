# MCP Integration

An MCP-based rebuild of `llm_file_assistant`'s filesystem tooling: the
sandboxed file tools move out of a directly-imported LangChain tool module
and behind a standalone **Filesystem MCP Server**, and the chat agent
(**`matching_agent.py`**) is refactored to discover and call those tools
exclusively through an MCP client — no direct filesystem access from the
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
implementation plan live in [`docs/spec.md`](docs/spec.md).

**Status**: design spec complete, implementation in progress. This README
will be filled in with concrete setup/run instructions as `filesystem_mcp_server.py`,
`matching_agent.py`, and the Docker packaging land.

## Prerequisites

- Python >= 3.12
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Docker (to run the MCP server)
- An [OpenRouter](https://openrouter.ai/) API key (agent side)

## Planned layout

See [`docs/spec.md`](docs/spec.md) §3 for the full repository layout and §14
for the phase-by-phase build order.
