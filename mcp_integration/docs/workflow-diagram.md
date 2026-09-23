# Workflow: one agent <-> MCP interaction

```mermaid
stateDiagram-v2
    [*] --> Discovery
    Discovery: MCPAdapter connects, calls list_tools()
    Discovery --> AgentReady: tools registered on the LangGraph agent

    AgentReady --> ModelTurn: user sends a message
    ModelTurn: chat model decides to call a tool
    ModelTurn --> ToolCall: AIMessage with tool_calls

    ToolCall --> MCPRoundTrip: MCPAdapter sends tools/call over Streamable HTTP
    MCPRoundTrip --> ServerFilesystemOp: filesystem_mcp_server.py's @mcp.tool runs
    ServerFilesystemOp --> StructuredResult: {success, ..., error} dict returned
    StructuredResult --> ToolMessage: MCPAdapter wraps it as a ToolMessage

    ToolMessage --> ModelTurn: agent loop continues with the tool result
    ModelTurn --> FinalAnswer: model responds with no further tool_calls
    FinalAnswer --> [*]
```

Every arrow from `ToolCall` through `ToolMessage` is visible live in the REPL
via the existing `Tool call: {name}({args})` / `Tool result (...)` panels --
no bespoke MCP-event plumbing was needed for this.
