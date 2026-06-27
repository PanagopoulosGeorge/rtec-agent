# RTEC-MCP — Drive RTEC from any MCP agent

This repository wraps **RTEC** (Run-Time Event Calculus, a Prolog engine for composite
event recognition) as an **MCP server**, so a tool-use LLM agent can synthesize RTEC event
descriptions from natural language, run them, and self-refine — without ground truth in the
loop. The engine itself is documented in [`README.md`](README.md); this file is about the
**MCP layer and how to use it from a consumer**.

```
NL description ─▶ consumer agent ─▶ (MCP, stdio) ─▶ RTEC-MCP server ─▶ swipl / RTEC engine
```

---

## What the server exposes

| Kind | Name | Purpose |
|---|---|---|
| tool | `inspect_stream(app, event_type?, entity?, t_from?, t_to?, limit?)` | discover events/entities/time-range in the input stream |
| tool | `inspect_background(app, pattern)` | grep the background knowledge (thresholds, types, helpers) |
| tool | `rtec_compile(app, rules?, mode?)` | write + compile an event description (`mode=overwrite\|append`) |
| tool | `read_rules(app)` | read the agent's current workspace program + its defined fluents |
| tool | `rtec_run(app, start_time?, end_time?, window?, step?, fluent?)` | run recognition, return the agent's own recognised intervals |
| resource | `rtec://authoring/core` | domain-agnostic RTEC authoring guide |
| resource | `rtec://authoring/domain/{app}` | per-domain signature (events, fluents, background) |
| prompt | `synthesize_fluent(app, nl_description)` | full context (guide + domain + procedure + NL) as one message |

The agent works only in an **isolated workspace** (`examples/<app>/workspace/`); it never
reads or writes the held-out reference rules.

## Prerequisites
- **Docker** (recommended), or a local install: **SWI-Prolog** (`swipl` on PATH) + **Python ≥3.11**.
- A consumer that speaks MCP (Goose, Claude Code, Claude Desktop, Cursor, the MCP Inspector, …).
- For the maritime app: the dataset `brest_critical.csv` (see `examples/maritime/dataset/csv/dataset_download.txt`).

## Quick start — Docker (recommended)
```bash
docker build -t rtec-mcp .
# smoke test (uses the small baked 'toy' app, no mounts):
npx @modelcontextprotocol/inspector docker run -i --rm rtec-mcp
```
The image bundles swipl + the engine + the server and **excludes all reference rules**
(gold isolation is physical). For maritime, mount the dataset in and the workspace out:
```bash
docker run -i --rm \
  -v /ABS/brest_critical.csv:/app/examples/maritime/dataset/csv/brest_critical.csv \
  -v /ABS/workspace:/app/examples/maritime/workspace \
  rtec-mcp
```

## Quick start — local (no Docker)
```bash
uv venv && uv pip install mcp        # or: bash install.sh
.venv/bin/python -m mcp_server.server          # stdio server
# inspect it:
.venv/bin/mcp dev mcp_server/server.py
```

---

## Configuring the MCP tools in a consumer (general)

Almost every MCP client launches a **stdio** server by running a command and talking
JSON-RPC over its stdin/stdout. The generic config is "a name → a command + args" entry.
Use **`-i`** for Docker (keep stdin open); use **absolute paths** locally.

**Generic JSON** (Claude Desktop / Cursor / most clients — usually under `mcpServers`):
```jsonc
{
  "mcpServers": {
    "rtec": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
               "-v", "/ABS/brest_critical.csv:/app/examples/maritime/dataset/csv/brest_critical.csv",
               "-v", "/ABS/workspace:/app/examples/maritime/workspace",
               "rtec-mcp"]
    }
  }
}
```
**Generic JSON — local (no Docker).** Run the server file by path; no `cwd` needed (the
server resolves its own paths):
```jsonc
{
  "mcpServers": {
    "rtec": {
      "command": "/ABS/RTEC-mcp/.venv/bin/python",
      "args": ["/ABS/RTEC-mcp/mcp_server/server.py"]
    }
  }
}
```

**Goose** (`~/.config/goose/config.yaml`, under `extensions:`):
```yaml
rtec:
  type: stdio
  cmd: docker
  args: [run, -i, --rm,
         -v, /ABS/brest_critical.csv:/app/examples/maritime/dataset/csv/brest_critical.csv,
         -v, /ABS/workspace:/app/examples/maritime/workspace,
         rtec-mcp]
  timeout: 300
```

**Claude Code** (CLI):
```bash
claude mcp add rtec -- docker run -i --rm \
  -v /ABS/brest_critical.csv:/app/examples/maritime/dataset/csv/brest_critical.csv \
  -v /ABS/workspace:/app/examples/maritime/workspace rtec-mcp
```

**MCP Inspector** (interactive testing): `npx @modelcontextprotocol/inspector docker run -i --rm … rtec-mcp`.

> Tip (local, no Docker): replace `command/cmd` with the venv Python and `args` with the
> absolute path to `mcp_server/server.py`.

## Using it

Give the agent the RTEC authoring context, then just the natural-language description of
one composite activity:
- **Single-shot:** invoke the MCP prompt `synthesize_fluent(app, nl_description)` — it
  bundles the guide + domain signature + procedure + your NL.
- **Multi-turn / harness:** inject the durable guide once as the system prompt and send
  each fluent's NL as a turn:
  ```bash
  python -c "from mcp_server.context import build_system_prompt; print(build_system_prompt('maritime'))"
  ```

The agent then: `inspect_stream`/`inspect_background` → writes a complete program (rules +
`grounding`/`dynamicDomain`) via `rtec_compile` → `rtec_run` on a bounded window → refines.
Output lands in `examples/<app>/workspace/`.

## Scoring (host-side, external)
Gold is used once, outside the loop. After the agent produces a program:
```bash
python scripts/score_fluent.py --app maritime --fluent lowSpeed \
    --start 1443650401 --end 1443700000 --window 36000 --step 36000
```
Re-runs the agent's compiled artifact and the reference over the same window → precision/
recall/F1 (via `execution scripts/scoring/evaluate.py`).

## Repository layout (MCP layer)
```
mcp_server/        the MCP server + pure-Python wrappers (discovery, rtec_runner, context, server)
resources/authoring/  the injected authoring context (core guide + per-domain signatures)
scripts/score_fluent.py   one-command external scoring
Dockerfile, .dockerignore  the containerised (stdio) server
examples/<app>/    datasets, background knowledge, and the agent workspace
```

## More
- **[README.md](README.md)** — the RTEC engine itself and its documentation.
