# Running RTEC-MCP with Goose

[Goose](https://block.github.io/goose/) is an open-source MCP agent — a good open,
model-swappable consumer for driving RTEC synthesis. This guide covers setup end to end.

> **Use the CLI, run it from a terminal.** The macOS **desktop app** runs with a restricted
> PATH and often can't find `docker`/`swipl`. The CLI launched from a normal terminal
> inherits your full PATH and also lets you capture a clean trace log. Both share the same
> `~/.config/goose/config.yaml`.

---

## 1. Install the Goose CLI
```bash
curl -fsSL https://github.com/block/goose/releases/download/stable/download_cli.sh | CONFIGURE=false bash
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"
goose --version
```
(Verify the URL at https://block.github.io/goose/docs/getting-started/installation. The
`block-goose` Homebrew **cask** installs only the desktop GUI — not this CLI.)

## 2. Get the server
```bash
docker pull georgepanag/rtec-mcp        # the published stdio MCP server (arm64)
```

## 3. Configure a model
```bash
goose configure        # Configure Providers -> pick your provider
```
The model **must support tool-calling** (the loop calls `rtec_*`). Good choices: a frontier
model, or an agentic open model (e.g. Ollama `devstral-2:123b-cloud`). Pure code models often
don't tool-call. With Ollama, ensure `ollama serve` is running (and you're signed in for
`:cloud` models).

## 4. Add the RTEC extension
Edit `~/.config/goose/config.yaml`, under `extensions:`. **Docker variant** (mount the
dataset in and a workspace out — use **absolute** paths, and the dataset file must exist):
```yaml
  rtec:
    enabled: true                 # required, or it won't load
    type: stdio
    cmd: docker
    args: [run, -i, --rm,
           -v, /ABS/brest_critical.csv:/app/examples/maritime/dataset/csv/brest_critical.csv,
           -v, /ABS/workspace:/app/examples/maritime/workspace,
           georgepanag/rtec-mcp]
    timeout: 300
```
**Local-server variant** (if you cloned the repo; no Docker, dataset already in place — set
`envs.PATH` so the server can find `swipl`):
```yaml
  rtec:
    enabled: true
    type: stdio
    cmd: /ABS/RTEC-mcp/.venv/bin/python
    args: [/ABS/RTEC-mcp/mcp_server/server.py]
    timeout: 300
    envs: { PATH: "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin" }
```
Verify it loads:
```bash
goose doctor
```

## 4b. Disable filesystem/shell extensions (REQUIRED for valid results)
Goose ships extensions like **`developer`** (shell + file read/write), `apps`, `analyze`,
`skills`, `summon`, `extensionmanager`. If any are enabled, the agent can `cat` the held-out
reference (`examples/<app>/resources/patterns/rules.prolog`) and the gold — a **leak that
invalidates the experiment** — and it may ignore the MCP tools and crawl your filesystem
instead. Enable **only** `rtec` (plus harmless `todo`/`tom`); disable the rest in
`~/.config/goose/config.yaml`:
```yaml
  developer:        { enabled: false }   # shell + file access — the critical one
  apps:             { enabled: false }
  analyze:          { enabled: false }
  skills:           { enabled: false }
  summon:           { enabled: false }
  extensionmanager: { enabled: false }   # else the agent can re-enable the others
```
Re-check with `goose doctor` — only `rtec` (and `todo`/`tom`) should be active.

## 5. Configure the system prompt (`.goosehints`)
MCP can't set Goose's system prompt — you do, via a project-local **`.goosehints`** file that
Goose loads as standing instructions every turn. Generate it (incremental/multi-turn mode is
already embedded in the context):
```bash
# from the image (no repo needed):
docker run --rm georgepanag/rtec-mcp \
  python -c "from mcp_server.context import build_system_prompt; print(build_system_prompt('maritime'))" > .goosehints
# or, if you cloned the repo:
# .venv/bin/python -c "from mcp_server.context import build_system_prompt; print(build_system_prompt('maritime'))" > .goosehints
```
Launch Goose **from the directory that contains `.goosehints`**. (Avoid the global
`~/.config/goose/.goosehints` — it would inject the RTEC guide into unrelated sessions.)

## 6. Run the experiment (interactive, with a trace log)
```bash
mkdir -p logs
script -q logs/maritime-exp.log goose session --name maritime-exp
```
In the session, feed the target fluents **one per turn**. The `.goosehints` already tells the
agent to: `read_rules` → reuse defined fluents → add each new one with
`rtec_compile(mode="append")` → verify with `rtec_run`. For the full maritime experiment, feed
the 17 fluents in dependency order:
`gap, lowSpeed, changingSpeed, movingSpeed, highSpeedNearCoast, trawlSpeed, tuggingSpeed,
sarSpeed, trawlingMovement, sarMovement, anchoredOrMoored, drifting, trawling, tugging, inSAR,
pilotOps, loitering`.

Traces: `logs/maritime-exp.log` (human) and `~/.local/share/goose/sessions/maritime-exp.jsonl`
(structured tool calls). Resume with `goose session --resume --name maritime-exp`. The
agent's program accumulates in your mounted `workspace/rules.prolog`.

## 7. Score (host-side, needs the cloned repo)
Scoring compares the **agent's recognitions** (TEST) against the **reference / ground-truth
recognitions** (GOLD). Both must be produced by **running RTEC over identical execution
parameters** — same `window`/`step`/`start_time`/`end_time` and the same input stream.
Otherwise the two result files aren't comparable and the F1 is meaningless. So there are
always **two RTEC runs before `evaluate.py`** — one over the reference rules, one over the
agent's generated rules — with matching params.

Pick one window and use it for **both** runs:
```bash
START=1443650401; END=1443844800; W=36000; S=36000   # maritime default window/step = 36000
```

**Run A — GROUND TRUTH** (the held-out reference rules; `run_rtec.sh` compiles + runs
`resources/patterns/rules.prolog` from `defaults.toml`, which uses window=step=36000):
```bash
cd "execution scripts"
./run_rtec.sh --app=maritime --start-time=$START --end-time=$END
# -> ../examples/maritime/results/log-swi-36000-36000-csv-file-recognised-intervals.txt
```

**Run B — GENERATED** (the agent's program). Run it over the **same** params via the MCP tool
(in your Goose session, or any MCP client):
```
rtec_run(app="maritime", start_time=1443650401, end_time=1443844800, window=36000, step=36000)
# writes -> <workspace>/results/log-swi-36000-36000-csv-file-recognised-intervals.txt
```
`<workspace>` is wherever you mounted/configured it (Docker: your mounted host dir, e.g.
`rtec-mcp-test/workspace`; local-server: `examples/maritime/workspace`). The two filenames
must carry the **same** `-36000-36000-` because both runs used the same window/step.

**Compare** (filter both to the measured fluents, then one `evaluate.py` call):
```bash
cd "execution scripts"
GOLD=../examples/maritime/results/log-swi-${W}-${S}-csv-file-recognised-intervals.txt
TEST=/ABS/path/to/workspace/results/log-swi-${W}-${S}-csv-file-recognised-intervals.txt
M=',(gap|lowSpeed|changingSpeed|movingSpeed|highSpeedNearCoast|trawlSpeed|tuggingSpeed|sarSpeed|trawlingMovement|sarMovement|anchoredOrMoored|drifting|trawling|tugging|inSAR|pilotOps|loitering),'
grep -E "$M" "$GOLD" > /tmp/gold.txt
grep -E "$M" "$TEST" > /tmp/test.txt
cd scoring && python3 evaluate.py --gt /tmp/gold.txt --test /tmp/test.txt --out /tmp/maritime_F1.csv
column -s, -t /tmp/maritime_F1.csv
```

Notes:
- Runs A and B differ **only** in the rules; identical params mean window/`+1` boundary
  effects are the same on both sides and cancel out.
- `evaluate.py` reports per-fluent `tp/fp/fn/precision/recall/F1` plus micro/macro. It
  amalgamates intervals itself.
- The `grep -E "$M"` keeps only the 17 measured fluents (excludes the taught `withinArea`).

## Troubleshooting
| Symptom | Cause / fix |
|---|---|
| Agent chats but never calls `rtec_*` | Model isn't tool-calling → switch model (e.g. `devstral-2:123b-cloud`). |
| `docker`/`swipl` not found | Goose's PATH. Run the **CLI from a terminal**; or use an absolute `cmd` and set `envs.PATH`. |
| RTEC can't read the stream / empty results | Mount path was relative or the host CSV didn't exist → use **absolute** paths; the file must exist before launch. |
| `rtec` extension doesn't appear | Missing `enabled: true`, or `goose doctor` shows a parse error. |
| `rtec_run` says "no compiled agent rules" | Call `rtec_compile` first (the agent does this; if scoring manually, compile the workspace rules). |
| Compile "success" but `rtec_run` produces nothing | Missing `grounding/1` — see the "0 output entities (cachingOrder2)" warning from `rtec_compile`. |
