# Demo script

Mapped to the assignment's suggested 9-step sequence.

1. **Architecture intro** -- show `docs/architecture.md`'s diagram; explain
   the two-process split and why the server is dockerized but the agent isn't.
2. **Server config & startup** -- show `.env`, then `docker compose up --build`;
   point out the healthcheck reaching "healthy".
3. **Discovery** -- `curl .../mcp` `tools/list`, or the
   `test_discovery_includes_migrated_tools` test, showing all 8 tools with
   their generated schemas.
4. **A migrated op** -- ask the agent "what's in engineering/backend_alice.txt?";
   show the `read_file` tool-call panel and the extracted content.
5. **`batch_process`** -- ask the agent to summarize every engineering resume
   at once; show the aggregate `{total_files, processed, failed, skipped}`
   counts in the tool result panel.
6. **`watch_directory`** -- ask the agent to watch `sales/` for new resumes;
   drop a new file into `sample_data/resumes/sales/` from a second terminal;
   ask the agent to check for updates and show it picking up the new file via
   `poll_watch`.
7. **Full agent run** -- a multi-turn conversation exercising `list_files` ->
   `search_in_file` -> `write_file` (e.g. "find everyone who knows Python and
   write a shortlist").
8. **Results, logs, tests** -- `uv run pytest tests/ -v` (all green, 30/30);
   show the `CustomLogger` output in the server container's logs
   (`docker compose logs -f`). Note: `PERMISSION_DENIED` is exercised via a
   mocked `OSError` (`test_write_file_permission_denied_on_os_error`) rather
   than a real OS-level permission failure, since the latter isn't portably
   testable across OSes -- it's code-reviewed, not verified against a real
   permission fault.
9. **Scope note** -- state explicitly that the bonus multi-MCP integration was
   not implemented (spec §13), and why (time-boxed to the core two-part
   assignment).
