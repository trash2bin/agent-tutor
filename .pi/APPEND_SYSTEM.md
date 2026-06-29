# SYSTEM RULES — READ BEFORE EVERY RESPONSE

## REQUIRED: Context-Mode Usage

You MUST call `ctx_search "<terms>"` at the start of EVERY response that
involves the codebase — before any Read, Bash, or Grep call.
No exceptions. This is a hard rule, not a suggestion.

You MUST use `ctx_execute` instead of Bash/Read for any operation
that produces output >1KB.

## Tool Routing

### Knowledge graph
- Architecture/structure questions: use graphify native tools (`graphify_query`, `graphify_path`,
  `graphify_explain`) — these are native Pi extensions, not bash calls
- Fast orientation/search: `ctx_search "<terms>"` (searches indexed GRAPH_REPORT.md)
- Never read `graphify-out/` files directly — query via tools above only

### File access
- Any output >1KB → `ctx_execute` / `ctx_batch_execute` instead of Read/Bash
- Before grep/glob — try graphify first, graph traversal is faster and token-free

### Priority for codebase questions
1. `ctx_search` → orient via graph index
2. graphify tools → structured lookup
3. `ctx_execute` script → only if graph has no answer
4. `ask_user_ext` → if direction is unclear or task has drifted from original goal

## Graphify — Knowledge Graph for agent-tutor

The project has a pre-built knowledge graph in `graphify-out/`: **2430 nodes, 4234 edges, 170 communities**.
It covers Go (`data-service`, `mcp-gateway`) and Python (`rag`, `mcp_server`, `demo/api`, `demo/web`, `agent-tutor-sdk`).

### Graphify tools and when to use them

| Tool | When | Example |
|---|---|---|
| `graphify_query` (bfs) | "What is X connected to?" | `graphify_query({ question: "How does LLMAgent call MCP tools?", mode: "bfs" })` |
| `graphify_query` (dfs) | "How does data flow from A to B?" | `graphify_query({ question: "How does a user request reach ChromaDB?", mode: "dfs" })` |
| `graphify_path` | Shortest path between two concepts | `graphify_path({ from: "LLMAgent", to: "ChromaDBVectorStore" })` |
| `graphify_explain` | Everything connected to a concept | `graphify_explain({ concept: "orchestrator.py" })` |
| `graphify_update` | After code changes (free, no LLM cost) | `graphify_update({ path: "." })` |
| `graphify_add` | Add external doc/paper to corpus | `graphify_add({ url: "https://arxiv.org/abs/..." })` |
| `graphify_export_callflow` | Architecture diagram in Mermaid | `graphify_export_callflow({})` → `graphify-out/callflow.html` |
| `graphify_save_result` | Save Q&A to graph memory (feedback loop) | After correct/incorrect answer, save for `reflect` |
| `graphify_reflect` | Aggregate saved results into LESSONS.md | Accumulate best-practices across sessions |

### Key community hubs (fast navigation)

| Community | Covers |
|---|---|
| `University MCP Server` (25 nodes) | `mcp_server/` — Python MCP server, tools, health |
| `Data Service Tools` (19 nodes) | HTTP wrappers of MCP tools over data-service |
| `Data Service HTTP Client` (23 nodes) | `AsyncDataServiceClient` + `RagClient` in SDK |
| `ChromaDB Vector Store` (29 nodes) | `rag/vector_store.py` + tests + interfaces |
| `LLM Agent Streaming` (34 nodes) | `demo/api/agent/orchestrator.py` — agent loop, SSE |
| `Agent Type Definitions` (33 nodes) | `types.py` — Message, ToolCall, EventData, SessionId |
| `Conversation History Manager` (24 nodes) | `conversation.py` — dialog memory, locks |
| `Tool Call Parser` (23 nodes) | `tool_parser.py` — native + JSON tool call parsing |
| `MCP HTTP Client` | `mcp_client.py` — long-lived MCP session |

### Usage rules

- **Architecture questions**: graphify first, then read files. The graph already knows 144 files' relationships.
- **After code changes**: run `graphify_update` (no API cost, incremental).
- **After large refactors**: `graphify_update` with `--force`.
- **Ripple-effect**: `graphify_path` or `graphify_explain` around the changed node before editing.
- **NEVER read `graphify-out/graph.json` or `graphify-out/GRAPH_REPORT.md` directly** — they are huge (2.3MB / 51KB). Use graphify tools instead.
- **Do NOT delete `graphify-out/`** — rebuilding costs API tokens.
- **Graph freshness**: graph built from commit `932288d0`. Check `git rev-parse HEAD` vs `built_at_commit` in `graph.json`. If diverged → `graphify_update`.
- **Weak areas**: graph has low coverage for `.env`, environment variables, and `scripts/dev.sh`. Use `ctx_execute`/Bash for those.

---

## Subagent Delegation

### Delegate automatically when:
- Task will touch >5 files or require >10 tool calls
- Independent review of completed work is needed
- Context is >50% full and task is not done
- Multiple independent subtasks can run in parallel

### Which template for which situation:
| Situation | Command |
|---|---|
| Requirements are unclear | `/gather-context-and-clarify` |
| Need to research before implementing | `/parallel-research` or `/parallel-context-build` |
| Plan exists, need implementation | `/parallel-handoff-plan` |
| Changes done, need verification | `/parallel-review` |
| Iterative fix-and-check loop | `/review-loop` |
| Cleanup or refactor pass | `/parallel-cleanup` |

### Do not delegate for:
- Single-file edits
- Quick lookups (use `ctx_search` / graphify instead)
- Tasks under ~5 tool calls

### Default flow for non-trivial tasks:
