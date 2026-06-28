# RTEC: Run-Time Event Calculus

RTEC is an open-source [Event Calculus](https://en.wikipedia.org/wiki/Event_calculus) dialect optimised for data stream reasoning. It is written in Prolog and has been tested under [SWI-Prolog](https://www.swi-prolog.org/) in Linux, MacOS and Windows.

This repository also ships an **MCP server** so a tool-use LLM agent can synthesize RTEC event descriptions from natural language, run them, and self-refine. See **[Run RTEC from an LLM agent](#run-rtec-from-an-llm-agent-mcp)** below.

# License

RTEC comes with ABSOLUTELY NO WARRANTY. This is free software, and you are welcome to redistribute it under certain conditions; see the [GNU Lesser General Public License v3 for more details](http://www.gnu.org/licenses/lgpl-3.0.html).

# Documentation

Latest [documentation](docs/contents.md).

# Run RTEC from an LLM agent (MCP)

A prebuilt MCP server image is published — **no build required**.

### Prerequisites

- Docker
- An MCP-capable consumer (e.g. [Goose](https://block.github.io/goose/), Claude Code)
- For the maritime app: the dataset `brest_critical.csv` (download link in `examples/maritime/dataset/csv/dataset_download.txt`)

### Install

```bash
docker pull georgepanag/rtec-mcp
```

> The image is `linux/arm64` (Apple Silicon / ARM hosts).

### Configure it in your consumer

The server runs over stdio. Point your consumer at it, mounting the dataset in and a workspace out (replace `/ABS/…` with absolute paths).

Generic MCP client (`mcpServers` config):

```json
{
  "mcpServers": {
    "rtec": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
               "-v", "/ABS/brest_critical.csv:/app/examples/maritime/dataset/csv/brest_critical.csv",
               "-v", "/ABS/workspace:/app/examples/maritime/workspace",
               "georgepanag/rtec-mcp"]
    }
  }
}
```

Goose (`~/.config/goose/config.yaml`, under `extensions:`) — full walkthrough in **[README_goose.md](README_goose.md)**:

```yaml
rtec:
  enabled: true
  type: stdio
  cmd: docker
  args: [run, -i, --rm,
         -v, /ABS/brest_critical.csv:/app/examples/maritime/dataset/csv/brest_critical.csv,
         -v, /ABS/workspace:/app/examples/maritime/workspace,
         georgepanag/rtec-mcp]
  timeout: 300
```

Claude Code:

```bash
claude mcp add rtec -- docker run -i --rm \
  -v /ABS/brest_critical.csv:/app/examples/maritime/dataset/csv/brest_critical.csv \
  -v /ABS/workspace:/app/examples/maritime/workspace georgepanag/rtec-mcp
```

### Reproduce a result

1. Configure a consumer (above) with a **tool-calling** model.
2. **Invoke `synthesize_fluent`** for a target fluent (args: `app`, `nl_description`):
  - **Claude Code** (surfaces MCP prompts): run `/mcp__rtec__synthesize_fluent`, set
   `app = maritime`, and paste the description, e.g. for `lowSpeed`:
    > "lowSpeed": The activity starts when the vessel starts moving at a low speed. The
    > activity ends when the vessel stops moving at a low speed. When there is a gap in
    > signal transmissions, we can no longer assume that the vessel continues moving at a
    > low speed.
  - **Consumers without MCP-prompt support** (e.g. some Goose setups): pull the same
  context out of the image and use it as the system prompt, then send the NL as a turn:
    ```bash
    docker run --rm georgepanag/rtec-mcp \
      python -c "from mcp_server.context import build_system_prompt; print(build_system_prompt('maritime'))" > system.md
    # e.g. Goose:  goose session --system "$(cat system.md)"   # then paste the NL
    ```
   The agent calls the tools and writes its program to your mounted `workspace/`.
3. **Score it** against the held-out reference (needs a repo clone — the image has no
  ground truth)

# Feedback

For more information and feedback, do not hesitate sending us an [email](mailto:a.artikis@gmail.com,periklismant1@gmail.com) or adding an issue in this repository.

# Related Software

- [iRTEC](https://github.com/eftsilio/Incremental_RTEC): Incremental RTEC. iRTEC supports incremental reasoning, handling efficiently the delays and retractions in data streams.
- [oPIEC](https://github.com/Periklismant/oPIEC): Online Probabilistic Interval-Based Event Calculus. oPIEC supports Event Calculus reasoning over data streams under uncertainty.
- [Wayeb](https://github.com/ElAlev/Wayeb): Wayeb is a Complex Event Processing and Forecasting (CEP/F) engine written in Scala. It is based on symbolic automata and Markov models.

