# Agent Tool Use

An experimental Python project about how an AI agent uses a local tool and tools discovered through the Model Context Protocol (MCP). The example is a fictional parcel shipping assistant. It calculates billable weight, fetches shipping options, and recommends one that fits the user's budget and deadline. In booking mode, it can create a fictional shipment after the user approves the exact action.

The project explores tool sequencing, argument validation, MCP access control, approval before a state-changing call, and how the agent responds to missing information or tool failures. All rates and shipment records are synthetic; nothing contacts a carrier or charges money.

## Commands

Run these from the repository root after [configuring `.env`](#set-up):

| Command | What it does |
| --- | --- |
| `make run` | Install locked dependencies if needed, start the MCP server, and run the recommendation agent. |
| `make book` | Do the same with fictional shipment creation available after approval. |
| `make test` | Install test dependencies if needed and run the test suite. |

`make run` and `make book` ask for a shipping request in the terminal. They stop their MCP server when the agent exits. You need `uv`, `make`, and access to an OpenAI-compatible chat-completions endpoint; `uv` manages Python 3.11 or newer and the project packages.

## Set up

On first setup, create the local configuration file:

```bash
cp .env.example .env
```

Keep an existing configured `.env` rather than copying over it. Edit the new file with these values:

| Variable | Purpose |
| --- | --- |
| `LLM_BASE_URL` | Model endpoint base URL, typically ending in `/v1`. |
| `LLM_MODEL` | Model name accepted by that endpoint. |
| `LLM_API_KEY` | Credential for the endpoint; it must be nonempty even if a local endpoint ignores it. |
| `MCP_READ_TOKEN` | Private token used by the recommendation agent for read access. |
| `MCP_WRITE_TOKEN` | Different private token used by the booking agent for read and write access. |
| `MCP_PORT` | Local MCP server port; defaults to `8000`. |

Generate two different random values for the MCP tokens. The `.env` file is ignored by Git; `.env.example` contains placeholders only. The launcher starts the server on `127.0.0.1` and sets the agent's MCP URL to that local server for each run, so a value of `MCP_URL` in `.env` is not used by `make run` or `make book`. The chosen port must be free.

## Try the assistant

Start the recommendation agent:

```bash
make run
```

At `Shipping question:`, enter:

```text
Find domestic shipping for a 40 x 30 x 20 cm parcel weighing 3 kg, within 3 days, for at most €12.
```

The local tool calculates a billable weight of **4.8 kg**. The MCP tool returns three fictional options: Economy (€8, 5 days), Standard (€11, 3 days), and Express (€16, 1 day). Standard is the least expensive option that meets both limits. The answer and a short status for each tool call appear in the terminal. If details such as dimensions are missing, the agent should ask for them before calling tools.

To try fictional booking, start the booking agent:

```bash
make book
```

At `Shipping question:`, enter:

```text
Book a 40 x 30 x 20 cm domestic parcel weighing 3 kg within 3 days for at most €12.
```

The agent should select Standard. Before calling `create_shipment`, the client displays the tool name and arguments and prompts `Type approve to continue:`. Enter `approve` to allow the fictional creation, or anything else to decline. The server separately checks write permission and the selected option. A successful call returns a fictional shipment ID.

Each run starts a fresh server process. Shipment records and duplicate-request handling last only for that process; a later `make book` run starts with an empty store.

## Reading the output

Each line identifies which part of the application produced it. For the example parcel, the tool trace looks like this:

```text
[launcher] MCP server ready
[MCP client] Discovering shipping tools
[agent] Input: your request and task instructions
[agent] Output: call calculate_billable_weight
[local tool] Billable weight: 4.8 kg
[agent] Input: conversation and latest tool results: calculate_billable_weight (ok)
[agent] Output: call get_shipping_options
[MCP client] Calling get_shipping_options
[MCP server] Shipping options: economy (€8, 5 days), standard (€11, 3 days), express (€16, 1 day)
[MCP client] get_shipping_options completed
[agent] Input: conversation and latest tool results: get_shipping_options (ok)
[agent] Output: answer to user
[agent] Answer:
...
[launcher] MCP server stopped
```

`[agent] Input` identifies the context the agent uses for its next decision; `[agent] Output` shows the action or answer it chooses. The full conversation stays in context even when the line names only the latest tool result. In booking mode, `[approval]` shows the proposed arguments and whether the user approved. A declined request is marked `blocked` and produces no `[MCP client] Calling create_shipment` line. Routine HTTP access logs are hidden so the tool and approval steps are easier to follow.

## How it works

| Component | Responsibility |
| --- | --- |
| Agent loop and model adapter | Send tool definitions to the model, validate calls, execute allowed tools, and return results to the model. |
| Local `calculate_billable_weight` tool | Validate dimensions and actual weight, then calculate billable weight. |
| MCP client | Discover the shipping tools and call the server over Streamable HTTP with a bearer token. |
| MCP server | Offer fictional shipping options and shipment creation; check token permissions and shipping inputs. |
| Launcher | Start and stop the local MCP server around the terminal agent. |

The recommendation agent sees only the read-only shipping tool; booking mode also exposes `create_shipment`. Approval is checked by the client before calling that tool, while the server enforces write permission even for a caller that bypasses the agent. Retrying the same request ID with identical shipment details returns the existing fictional shipment; reusing the ID with different details is rejected.

The [study guide](docs/study-guide.md) covers the workflow, shipping rules, code walkthrough, exercises, evaluation cases, and dated observations. The [project spec](docs/SPEC.md) records the research questions and planned work.

## Tests and observations

`make test` checks calculations, invalid arguments, MCP authentication, client/server calls, approval and rejection, and duplicate shipment requests. The tests use scripted model responses and a local MCP HTTP app, so they need no live model endpoint or separately running server. The suite currently contains 28 tests.

For an exploratory local-model run with a malicious instruction embedded in a synthetic tool result, use:

```bash
uv run --locked python -m examples.shipping.evaluate_adversarial
```

That command uses an in-process options client instead of the MCP HTTP server. It checks one model response to untrusted tool data; it does not test MCP authentication or establish general prompt-injection resistance. Live-model observations and their limits are recorded in the [study guide](docs/study-guide.md#evaluation-cases).

## Limits

This is a local demonstration with fixed domestic rates, static bearer tokens without automatic expiry, and process-local shipment state. It does not implement OAuth sign-in, a real carrier integration, payment, durable records, or a general security guarantee. Model decisions can vary; scripted tests establish the software boundaries, while individual live runs are observations rather than reliability measurements.

## Project layout

| Path | Contents |
| --- | --- |
| `src/agent_tool_use/core/` | Reusable agent loop, model adapter, configuration, and local-tool wrapper. |
| `src/agent_tool_use/mcp/` | Reusable authenticated MCP client/server setup and tool discovery. |
| `examples/shipping/` | Shipping calculations in `tools.py`, shipment state in `shipments.py`, and application wiring in `agent.py` and `server.py`. |
| `tests/` | Unit and local MCP integration tests. |
| `docs/` | Study guide with the use case and evaluation notes, plus the project spec. |
