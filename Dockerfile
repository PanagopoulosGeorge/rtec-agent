# RTEC MCP server — stdio variant.
#
# Bundles SWI-Prolog + Python + the MCP SDK + the RTEC repo so any MCP consumer can
# drive RTEC over stdio via `docker run -i --rm`. The large maritime dataset CSV and the
# agent's workspace are MOUNTED at runtime (see below), not baked into the image.
#
# Build:
#   docker build -t rtec-mcp .
#
# Run (what an MCP consumer launches; -i keeps stdin open for JSON-RPC, no -t):
#   docker run -i --rm \
#     -v /host/brest_critical.csv:/app/examples/maritime/dataset/csv/brest_critical.csv \
#     -v /host/workspace:/app/examples/maritime/workspace \
#     rtec-mcp
#
# Models/consumers (Goose, Ollama, Claude Code) run on the HOST; this container is only
# the RTEC tool server and needs no network — just the stdio pipe.

FROM python:3.12-slim

# SWI-Prolog: the RTEC engine runtime (lands `swipl` on PATH, which rtec_runner shells to).
RUN apt-get update \
    && apt-get install -y --no-install-recommends swi-prolog \
    && rm -rf /var/lib/apt/lists/*

# Python runtime dependency: the MCP SDK only (pinned for reproducibility).
RUN pip install --no-cache-dir "mcp==1.28.0"

WORKDIR /app

# Copy the repo. The large maritime CSV, .venv, workspace, and results are excluded via
# .dockerignore (CSV + workspace are mounted at runtime instead).
COPY . /app

# stdio MCP hygiene: unbuffered I/O so JSON-RPC flushes promptly. The protocol travels
# over stdout and logs go to stderr (FastMCP default) — nothing must print to stdout.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Launch the stdio server; the consumer attaches via the container's stdin/stdout.
CMD ["python", "-m", "mcp_server.server"]
