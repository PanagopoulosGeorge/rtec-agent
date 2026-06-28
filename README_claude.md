# Running RTEC-MCP with Claude Code

[Claude Code](https://claude.com/claude-code) is an MCP client, so you can use it to drive
RTEC synthesis — generate event descriptions from natural language, compile, run, and
self-refine. No build required; just the published image.

> **Isolation note.** Claude Code ships built-in shell/file tools (`Bash`, `Read`, …). For a
> clean run, restrict it to **only** the `rtec` MCP tools, so the agent works exclusively
> through the RTEC tool surface and cannot read anything else on disk.

---

## 1. Prerequisites

- Docker
- Claude Code
- The maritime dataset `brest_critical.csv` (download in step 3)

## 2. Get the server

```bash
docker pull georgepanag/rtec-mcp
```

## 3. Get the dataset

Download **"Critical point streams"** from:
`https://owncloud.skel.iit.demokritos.gr/index.php/s/67dJSuymyIw1Mng`
and save it as `**brest_critical.csv`** (≈ 961 MB). Note its absolute path.

## 4. Create a clean working directory

```bash
mkdir -p ~/rtec-claude-run/workspace
cd ~/rtec-claude-run
```

(Keep this directory free of any `CLAUDE.md` so no project memory leaks in). Copy the maritime dataset to the rtec-claude-run folder.

## 5. Generate the authoring context (system prompt)

The RTEC language, the domain signature, and the synthesize→compile→run→refine procedure
are produced from the image:

```bash
docker run --rm georgepanag/rtec-mcp \
  python -c "from mcp_server.context import build_system_prompt; print(build_system_prompt('maritime'))" > rtec_guide.md
```

## 6. Add the RTEC MCP server

Mount the dataset in and a workspace out (use **absolute** paths; the dataset file must exist):

```bash
claude mcp add rtec -- docker run -i --rm \
  -v "$HOME/rtec-claude-run/brest_critical.csv:/app/examples/maritime/dataset/csv/brest_critical.csv \
  -v "$HOME/rtec-claude-run/workspace:/app/examples/maritime/workspace" \
  georgepanag/rtec-mcp
claude mcp list      # confirm `rtec` is listed
```

## 7. Launch Claude Code — fresh session, RTEC tools only

```bash
cd ~/rtec-claude-run
claude \
  --append-system-prompt "$(cat rtec_guide.md)" \
  --allowedTools "mcp__rtec__inspect_stream,mcp__rtec__inspect_background,mcp__rtec__rtec_compile,mcp__rtec__rtec_run,mcp__rtec__read_rules" \
  --disallowedTools "Bash,Read,Edit,Write,Glob,Grep,NotebookEdit,WebFetch,WebSearch,Task,TodoWrite"
```

- Do **not** pass `--continue`/`--resume` → fresh session, no retained memory.
- `--disallowedTools` blocks shell/file access → the agent uses **only** the RTEC tools.

## 8. Verify isolation, then synthesize

First message in the session:

```
list your tools
```

You must see **only** the five `mcp__rtec__`* tools (no `Bash`/`Read`). If a shell tool
appears, stop and relaunch with the `--disallowedTools` above.

Then feed the target activities **one per turn**, in dependency order. The injected guide
already tells the agent to `read_rules` → reuse defined fluents → add each new one with
`rtec_compile(mode="append")` → verify with `rtec_run`. Example first turn:

```
"lowSpeed": The activity starts when the vessel starts moving at a low speed. The activity
ends when the vessel stops moving at a low speed. When there is a gap in signal
transmissions, we can no longer assume that the vessel continues moving at a low speed.
```

Full maritime set order:
`gap, lowSpeed, changingSpeed, movingSpeed, highSpeedNearCoast, trawlSpeed, tuggingSpeed, sarSpeed, trawlingMovement, sarMovement, anchoredOrMoored, drifting, trawling, tugging, inSAR, pilotOps, loitering`.

The synthesized program accumulates in `~/rtec-claude-run/workspace/rules.prolog`; check it
after each fluent:

```bash
ls -la ~/rtec-claude-run/workspace/
```

