# Agent Tool Use: Project Spec

**Status:** Working specification, 2026-11-19. The core implementation is present; evaluation remains in progress.

## Goal

Study how an AI agent uses direct local tools and tools exposed by an MCP server. Demonstrate the full path from a user request to tool selection, validated execution, returned data, and a final answer. Examine failure handling and the controls needed around a state-changing action. Keep runtime and MCP mechanics separate from shipping-specific rules.

The output is a runnable repository, repeatable checks, and a clear account of what was observed. This is an experiment and learning project; it should explain limits rather than claim that the agent or MCP connection is generally reliable or secure.

## Questions to investigate

These questions concern agent tool use in general. The shipping assistant below supplies concrete cases for studying them.

1. How do tool names, descriptions, and input schemas influence which tools an agent chooses, their order, and the arguments it supplies?
2. What changes when a tool is registered in the agent process versus discovered and called through a separate tool server?
3. Which parts of tool use should be deterministic application behavior, and which parts depend on the model's decisions?
4. How should a runtime reject unavailable tools, malformed arguments, failed calls, and repeated calls while still giving the agent enough information to respond accurately?
5. Where should tool visibility, user approval, authentication, authorization, and input validation be enforced across the agent, client, and server?
6. How can an agent use tool descriptions and results as task data without treating untrusted content as instructions that override its task or controls?
7. Which traces and repeatable tests distinguish a software boundary that works from a model behavior observed only once?
8. Which design assumptions affect whether a tool integration can work across different domains and model endpoints?

## Scenario

A fictional parcel shipping assistant receives a package's dimensions and weight, destination, budget, and delivery deadline. It calculates billable weight with a local tool, requests available shipping options from a separate MCP server over HTTP, and recommends an option with its price and delivery estimate. In booking mode, it can create a fictional shipment after explicit approval.

Use fixed, synthetic rates, destinations, and shipments. This experiment does not require knowledge-base search, retrieval, or long-term memory. No real carrier account, payment, address, or external shipping API is required.

## Scope

The experiment uses three tools: one local calculation, one remote read, and one remote state-changing action. Their rules and records are synthetic. The project does not need retrieval, a knowledge base, long-term memory, multiple agents, carrier APIs, addresses, payments, or an OAuth sign-in flow. Add a capability only when it helps answer one of the questions above.

The assistant is a terminal application. `make run` allows recommendations; `make book` also allows an approved fictional creation. Both start a separate local MCP server process and stop it when the agent exits. The project is designed for inspection and learning, not for production shipping.

## Design and responsibilities

| Component | Responsibility | Location |
| --- | --- | --- |
| Agent loop | Present allowed tools, collect model decisions, validate tool arguments, request approval when required, execute handlers, and return results to the model. | `src/agent_tool_use/core/loop.py` |
| Model adapter | Translate between the loop's messages and an OpenAI-compatible chat-completions endpoint. | `src/agent_tool_use/core/model.py` |
| Local tool wrapper | Bind a Python function to the same tool contract used by the agent loop. | `src/agent_tool_use/core/tools.py` |
| MCP client and discovery | Connect with a bearer token, discover server tools, allow only selected names, and bind remote calls to the loop. | `src/agent_tool_use/mcp/` |
| MCP server setup | Configure token verification and a baseline read scope; expose a helper for tool-specific scope checks. | `src/agent_tool_use/mcp/server.py` |
| Shipping application | Keep shipping rules in `tools.py`, process-local state in `shipments.py`, local tool setup and tool selection in `agent.py`, and MCP handlers, registration, and token mapping in `server.py`. | `examples/shipping/` |

The model chooses among tool calls and answers. Application code enforces tool registration, JSON-schema validation, approval, and server authorization. A tool result returns as a tool message in the next agent input. The loop has a finite model-call limit so repeated tool requests cannot continue indefinitely. Keep generic mechanics in `src/`; keep shipping policy and data in `examples/shipping/`.

The MCP server is a separate process even when it runs on the same computer. The client reaches it over Streamable HTTP through the Python MCP SDK rather than implementing MCP messages by hand. The locked MCP SDK is 2.3.0 and the documented protocol target is revision 2026-07-28; update both statements if dependencies change.

## Tool contracts

| Tool | Inputs | Output | Validation and boundary |
| --- | --- | --- | --- |
| `calculate_billable_weight` | Length, width, height in cm; actual weight in kg. | `billable_weight_kg`. | Local function requires finite positive numbers. Dimensional weight is `length × width × height ÷ 5,000`; return the greater of dimensional and actual weight. |
| `get_shipping_options` | Billable weight in kg; destination zone. | Option IDs, prices in euros, delivery days. | MCP read call requires an authenticated token with `shipping:read`. The server supports fictional `domestic` shipping up to 5 kg; above that it returns no options. |
| `create_shipment` | Option ID, billable weight, destination zone, request ID. | Fictional shipment ID, chosen option, price, delivery days. | Client approval is required before the call. The server independently requires `shipping:write`, validates the selected option, and uses the request ID to avoid duplicate creation within one process. |

Descriptions and JSON schemas must tell the model what each tool accepts. The loop rejects an unknown name or schema-invalid arguments before a handler runs. The server validates shipping inputs independently because a direct MCP caller can bypass the agent. The full fictional option set and an example recommendation are in the [study guide](study-guide.md#shipping-rules).

## Python environment

Use `uv` to create and maintain the Python environment and package dependencies. Declare dependencies in `pyproject.toml` and commit `uv.lock`. The project targets Python 3.11 or newer; do not commit `.venv`. `make run` and `make book` install locked runtime dependencies and manage the local server. `make test` installs the test extra if needed and runs deterministic checks. The prerequisites are `make`, `uv`, and a reachable OpenAI-compatible model endpoint for live runs; tests do not need that endpoint.

## Model configuration

Load `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY` from the process environment or a local `.env` file. Existing process variables take precedence over `.env`. The API key must be nonempty, even for a local endpoint that ignores it. `MCP_READ_TOKEN` and `MCP_WRITE_TOKEN` must be different private values; the server needs both, while the client chooses one based on the command. `MCP_PORT` selects the local server port. The one-command launcher points the agent at that server for the run, overriding any `MCP_URL` value in `.env`.

Commit `.env.example` with placeholders, never `.env` or other local secrets. Keep credentials out of source, tests, terminal traces, and documentation. A model connection failure should be reported clearly; an unavailable MCP server should likewise produce a clear connection message.

## Code ownership

```text
src/agent_tool_use/core/   agent loop, model adapter, config, local tool wrapper
src/agent_tool_use/mcp/    authenticated client/server setup and tool discovery
examples/shipping/tools.py  shipping calculation and option rules
examples/shipping/          process-local state, server, agent, launcher
tests/                    unit and local MCP integration checks
docs/                     specification and study guide with evaluation evidence
```

The shipping rates are defined in example code. Do not create empty modules or duplicate protocol machinery for the sake of a symmetrical layout. The study guide is the place for explanations and dated results; the README is the short entry point.

## Execution and failure behavior

1. The agent receives the request and only the tools allowed for the selected command. In read mode, the remote creation tool is not exposed to the agent.
2. A tool call must name a registered tool and supply arguments accepted by its JSON schema. Invalid requests do not reach the handler. Shipping functions also check their own domain rules.
3. Successful tool results are returned to the agent for the next decision. A valid call may still return no eligible options; the agent should explain that instead of inventing an option.
4. The agent should ask for missing task information before choosing tools that need it. This behavior depends on the model and task instructions, so observe it with live runs rather than treating it as a deterministic guard.
5. If the user declines a protected call, the client returns a blocked result to the agent without contacting the MCP server. If the server rejects a call, the agent must not claim that creation succeeded.
6. Startup connection failures should produce a clear terminal message. The current code handles observed connection failures; failures during an active remote call and malformed model responses beyond the checked non-object arguments need further evaluation.

Terminal traces label `[agent]`, `[local tool]`, `[MCP client]`, `[MCP server]`, `[approval]`, and `[launcher]`. They summarize decisions and tool outcomes without printing credentials. The answer remains the final agent output; the launcher then reports that it stopped the server.

## Control and trust boundaries

| Boundary | Required control | What it does not prove |
| --- | --- | --- |
| Agent tool list | The client exposes only selected remote tools. | A direct caller can still contact the server. |
| Agent to tool handler | The loop validates the tool name and JSON-schema arguments. | The model's answer or shipping choice is not automatically correct. |
| User to protected action | The client shows the exact creation arguments and requires explicit approval. | Approval does not grant server permission. |
| MCP caller to server | The server checks the bearer token and requires `shipping:write` for creation. | Static local tokens are not an OAuth deployment or a general security solution. |
| Tool result to agent | Tool output is treated as task data, including in the synthetic instruction-in-result experiment. | One compliant model response does not establish prompt-injection resistance. |

The server requires `shipping:read` at the MCP resource boundary and checks `shipping:write` inside `create_shipment`. A read-only caller must be denied even when it bypasses the agent. The server checks request validity and option availability independently. State is process-local; duplicate prevention does not survive a restart. Token values and model credentials must never be included in recorded traces.

## Milestones

| Milestone | Deliverable | Status |
| --- | --- | --- |
| 1. Local baseline | Agent loop, tool contract, local weight tool, argument validation, and trace. | Implemented; deterministic checks pass. |
| 2. MCP read path | Separate HTTP server, authenticated discovery and quote call, selected tool exposure, and a runnable recommendation flow. | Implemented; local MCP integration and individual live runs observed. |
| 3. Protected action | Client approval, server-enforced write scope, validated fictional creation, and duplicate-request handling. | Implemented; approved and declined paths covered with scripted-model and MCP checks. |
| 4. Evaluation and evidence | Document test evidence, capture varied live runs, explain failures and limits, and identify reusable parts. | In progress. A case table and one test-run summary exist; earlier live transcripts were not archived. |

Each milestone should leave a runnable, understandable project. Avoid unrelated MCP features that do not help answer the research questions.

## Verification plan and evidence

| Case | Check | Evidence type |
| --- | --- | --- |
| Normal recommendation | Correct local weight, authenticated options call, and an answer using returned prices and times. | Unit and scripted-model integration tests; separate live-model observation. |
| Missing or invalid inputs | Missing measurements prompt for clarification; invalid numeric or schema arguments never reach the handler. | Live-model observation for clarification; deterministic checks for validation. |
| No eligible option | The server returns no options for an overweight parcel; the agent explains the absence. | Unit check for empty options; individual live-model observation for the answer. |
| MCP connection or authorization failure | Startup connection failure is clear; missing bearer token receives HTTP 401; read token cannot create. | Manual connection check and local MCP HTTP integration tests. |
| Protected action | Decline blocks the call; approval permits it only with write access; retry with the same request ID does not duplicate the record. | Scripted-model and local MCP integration tests; individual live decline observation. |
| Untrusted tool output | Insert an instruction into synthetic tool data and observe the model's response. | Exploratory live-model run; no general security claim. |

For repeatable checks, run `make test` and retain the command, date, exit status, test count, and relevant assertions. For live-model observations, record the exact prompt, model name, endpoint type, tool trace, answer, and any failure. Distinguish a scripted model that supplies expected calls from a live model that chose them itself. Do not infer a success rate from isolated runs. The [study guide's evaluation table](study-guide.md#evaluation-cases) and [test run evidence](study-guide.md#test-run-evidence) hold the current results and their limits.

The existing integration tests exercise a real MCP client against a local MCP HTTP app. They do not require a separately launched server or a live model. A future claim about runtime reliability would need repeated, archived live runs across varied prompts and failure conditions. An approved live booking, mid-run connection failure, and malformed model response remain gaps in the recorded live evidence.

## Documentation and completion criteria

- The README must let a new reader configure the project, run recommendation and booking modes, run tests, and understand the system's limits.
- The study guide must explain the workflow, shipping rules, code path, control boundaries, exercises, and dated evidence without hiding untested cases.
- Tests must cover tool input rules, agent-loop validation and approval, MCP authentication, direct read-token denial, successful write-token creation, and duplicate handling without requiring model credentials.
- Documented claims must link to the relevant test or retained live artifact. If a live run has no saved transcript, label it as an unarchived observation.
- Keep code concise and readable without Python comments or docstrings; give model-facing tools explicit descriptions in schemas or registration metadata.
- The repository should not contain credentials, real shipping data, or claims of OAuth or production security.

## Current progress and next work

The read-only and protected booking paths are implemented. `make test` passed 28 checks in the recorded 2026-11-19 run. The study guide records individual live observations for recommendation, missing data, no options, declined creation, and one synthetic malicious tool result. An unavailable MCP server was also reproduced. These observations are not reliability measurements, and the earlier live terminal transcripts were not saved in the repository.

Next, capture repeatable live traces before making claims about model behavior. Expand error-case checks where they close a concrete gap, especially failures during an active MCP call. Summarize the resulting evidence and limits in the study guide.
